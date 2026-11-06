import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.dependencies import get_db
from app.main import app
from app.models import AutomationJob, Base, Expense, ImportBatch, Workspace


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Workspace(name="Aurora", slug="aurora-demo", is_demo=True))
        db.commit()

    def test_db():
        # Match get_db in production: financial reads require authenticated scope.
        with Session(engine, info={"http_request": True}) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as http:
        http.test_engine = engine
        http.headers.update({"X-Aurora-Request": "1", "Origin": "http://localhost:5173"})
        result = http.post("/auth/register", json={"email": "test@example.com", "password": "Senha de teste segura 2026!"})
        assert result.status_code == 201, result.text
        http.test_user_id = result.json()["user"]["id"]
        http.test_workspace_id = result.json()["workspace"]["id"]
        http.headers["X-CSRF-Token"] = result.json()["csrf_token"]
        yield http
    app.dependency_overrides.clear()
    engine.dispose()


def category(client, type="expense", name="Vendas"):
    response = client.post("/categories", json={"name": name, "type": type})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def entry(category_id, kind="expense", **extra):
    return {
        "category_id": category_id,
        "description": "Lançamento fictício",
        f"{kind}_date": "2026-11-05",
        "amount": "12.34",
        **extra,
    }


def test_category_types_uniqueness_legacy_default_and_filters(client):
    legacy = client.post("/categories", json={"name": "Legada"})
    assert legacy.status_code == 201
    assert legacy.json()["type"] == "expense"
    category(client, "income")
    category(client, "expense")
    duplicate = client.post("/categories", json={"name": "Vendas", "type": "income"})
    assert duplicate.status_code == 409
    assert client.post("/categories", json={"name": "X", "type": "other"}).status_code == 422
    assert len(client.get("/categories").json()) == 3
    assert [item["type"] for item in client.get("/categories?type=income").json()] == ["income"]
    assert len(client.get("/categories?type=expense&offset=1&limit=1").json()) == 1
    assert client.get("/categories?type=other").status_code == 422


def test_wrong_category_type_rejected_for_all_entries(client):
    income = category(client, "income")
    expense = category(client)
    assert client.post("/expenses", json=entry(income)).status_code == 422
    assert client.post("/incomes", json=entry(expense, "income")).status_code == 422
    budget = {"category_id": income, "year": 2026, "month": 11, "amount": "100.00"}
    assert client.post("/budgets", json=budget).status_code == 422
    budget["category_id"] = expense
    assert client.post("/budgets", json=budget).status_code == 201


@pytest.mark.parametrize("kind,route", [("income", "/incomes"), ("expense", "/expenses")])
def test_campaign_optional_and_references_validated(client, kind, route):
    cat = category(client, kind)
    campaign = client.post("/campaigns", json={"name": "Natal"})
    assert campaign.status_code == 201
    campaign_id = campaign.json()["id"]
    assert client.post("/campaigns", json={"name": "Natal"}).status_code == 409
    assert client.get("/campaigns?limit=1").json() == [campaign.json()]
    assert client.post(route, json=entry(cat, kind)).json()["campaign_id"] is None
    linked = client.post(route, json=entry(cat, kind, campaign_id=campaign_id))
    assert linked.status_code == 201
    assert linked.json()["campaign_id"] == campaign_id
    assert linked.json()["amount"] == "12.34"
    assert client.post(route, json=entry(cat, kind, campaign_id=999)).status_code == 404
    assert client.post(route, json=entry(999, kind)).status_code == 404
    params = {"year": 2026, "month": 11, "campaign_id": campaign_id, "category_id": cat}
    assert len(client.get(route, params=params).json()) == 1
    params["month"] = 12
    assert client.get(route, params=params).json() == []


@pytest.mark.parametrize("amount", ["0", "-1", "1.001", "NaN", "Infinity", "1000000000000.00"])
def test_income_rejects_invalid_money(client, amount):
    assert client.post("/incomes", json=entry(1, "income", amount=amount)).status_code == 422


def test_income_listing_pagination_and_december_boundary(client):
    cat = category(client, "income")
    for day in ("2026-12-01", "2026-12-31", "2027-01-01"):
        assert client.post("/incomes", json=entry(cat, "income", income_date=day)).status_code == 201
    assert len(client.get("/incomes?year=2026&month=12").json()) == 2
    assert len(client.get("/incomes?year=2026&month=12&offset=1&limit=1").json()) == 1
    assert client.get("/incomes?year=2026&month=13").status_code == 422


def test_import_without_campaign_and_dashboard_are_preserved(client):
    cat = category(client)
    income_cat = category(client, "income")
    content = f"categoria_id;descricao;data;valor\n{cat};Embalagens;2026-11-05;10,50\n".encode()
    preview = client.post("/imports/expenses/preview", files={"file": ("old.csv", content, "text/csv")})
    assert preview.status_code == 200
    batch = preview.json()
    assert batch["report"]["valid_count"] == 1
    path = f"/imports/{batch['import_id']}/confirm"
    first = client.post(path, json={})
    assert first.status_code == 200
    assert client.post(path, json={}).json()["already_completed"] is True
    expenses = client.get("/expenses?year=2026&month=11").json()
    assert len(expenses) == 1
    assert expenses[0]["campaign_id"] is None
    with Session(client.test_engine, info={"workspace_id": client.test_workspace_id, "actor_id": client.test_user_id}) as db:
        assert len(db.scalars(select(AutomationJob)).all()) == 1
    assert client.post("/incomes", json=entry(income_cat, "income", amount="99.00")).status_code == 201
    summary = client.get("/dashboard/summary?year=2026&month=11").json()
    assert summary["actual"] == "10.50"  # Existing dashboard remains expense-budget based.
    invalid = content.replace(f"{cat};".encode(), f"{income_cat};".encode())
    report = client.post("/imports/expenses/preview", files={"file": ("invalid.csv", invalid)}).json()
    assert report["report"]["invalid_count"] == 1


def test_pending_legacy_preview_revalidates_type_before_confirmation(client):
    cat = category(client, "income")
    # Represents an old persisted preview without the new campaign_id field.
    with Session(client.test_engine, info={"workspace_id": client.test_workspace_id, "actor_id": client.test_user_id}) as db:
        db.add(ImportBatch(
            id="00000000-0000-0000-0000-000000000001", file_hash="a" * 64,
            filename="legacy.csv", status="pending", saved_count=0,
            report={"valid_count": 1, "invalid_count": 0, "duplicate_count": 0,
                    "valid_rows": [{"data": entry(cat)}]},
        ))
        db.commit()
    response = client.post("/imports/00000000-0000-0000-0000-000000000001/confirm", json={})
    assert response.status_code == 409
    with Session(client.test_engine, info={"workspace_id": client.test_workspace_id, "actor_id": client.test_user_id}) as db:
        assert db.scalars(select(Expense)).all() == []
        assert db.scalars(select(AutomationJob)).all() == []
