from datetime import timedelta
import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, csrf_token, utcnow
from app.main import app
from app.models import AuthSession, AutomationJob, Category, Campaign, Expense, ImportBatch, User, Workspace, WorkspaceMembership
from app.passwords import hash_password, verify_password
from test_financial_entries_api import client, category, entry

PASSWORD = "Uma frase de senha segura 2026!"


def other_client(client, separate_workspace=False):
    other = TestClient(app)
    other.headers.update({"Origin": "http://localhost:5173", "X-Aurora-Request": "1"})
    response = other.post("/auth/register", json={"email": "other@example.com", "password": PASSWORD})
    assert response.status_code == 201, response.text
    other.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    if separate_workspace:
        user_id = response.json()["user"]["id"]
        with Session(client.test_engine) as db:
            workspace = Workspace(name="Outro departamento", slug="private", is_demo=False)
            db.add(workspace)
            db.flush()
            db.get(WorkspaceMembership, (client.test_workspace_id, user_id)).active = False
            db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user_id, active=True))
            db.commit()
        login = other.post("/auth/login", json={"email": "other@example.com", "password": PASSWORD})
        assert login.status_code == 200, login.text
        other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return other


def test_password_hash_salted_and_verifiable():
    first = hash_password(PASSWORD)
    assert PASSWORD not in first
    assert first != hash_password(PASSWORD)
    assert verify_password(PASSWORD, first)
    assert not verify_password("outra senha", first)
    assert not verify_password(PASSWORD, "invalid")


def test_session_cookie_is_httponly_and_database_has_only_token_hash(client):
    token = client.cookies.get(COOKIE_NAME)
    with Session(client.test_engine) as db:
        session = db.scalar(select(AuthSession))
        assert session.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert session.token_hash != token
        assert db.get(User, client.test_user_id).password_hash.startswith("scrypt$")
    me = client.get("/auth/me")
    assert me.json()["user"]["email"] == "test@example.com"
    assert "password" not in me.text and token not in me.text
    assert me.headers["cache-control"] == "no-store"
    login = client.post("/auth/login", json={"email": " TEST@EXAMPLE.COM ", "password": "Senha de teste segura 2026!"})
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]
    with Session(client.test_engine) as db:
        assert db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()) is None


def test_secure_cookie_default_can_be_enabled(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    response = client.post("/auth/login", json={"email": "test@example.com", "password": "Senha de teste segura 2026!"})
    assert "Secure" in response.headers["set-cookie"]
    assert "__Host-aurora_session=" in response.headers["set-cookie"]
    assert "Domain=" not in response.headers["set-cookie"]


def test_logout_revokes_session_and_expiration_is_server_validated(client):
    token = client.cookies.get(COOKIE_NAME)
    assert client.post("/auth/logout").status_code == 204
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/auth/me").status_code == 401
    client.cookies.clear()
    login = client.post("/auth/login", json={"email": "test@example.com", "password": "Senha de teste segura 2026!"})
    assert login.status_code == 200
    with Session(client.test_engine) as db:
        session = db.get(AuthSession, hashlib.sha256(client.cookies.get(COOKIE_NAME).encode()).hexdigest())
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/categories").status_code == 401


def test_unauthenticated_financial_routes_fail_closed(client):
    anonymous = TestClient(app)
    for path in ["/categories", "/campaigns", "/budgets", "/expenses?year=2026&month=11", "/incomes?year=2026&month=11", "/imports", "/automations", "/alerts?year=2026&month=11", "/dashboard/summary?year=2026&month=11", "/dashboard/analytics?year=2026&month=11"]:
        assert anonymous.get(path).status_code == 401, path
    for path in ["/categories", "/campaigns", "/budgets", "/expenses", "/incomes", "/copilot/chat", "/imports/expenses/preview", "/automations/1/retry"]:
        assert anonymous.post(path, json={}).status_code == 401, path
    assert anonymous.get("/health").status_code == 200


def test_csrf_and_origin_protect_writes_including_login_and_upload(client):
    old = client.headers.pop("X-CSRF-Token")
    assert client.post("/categories", json={"name": "Inválida"}).status_code == 403
    assert client.post("/imports/expenses/preview", files={"file": ("test.csv", b"x")}).status_code == 403
    client.headers["X-CSRF-Token"] = old
    client.headers["Origin"] = "https://attacker.example"
    assert client.post("/categories", json={"name": "Inválida"}).status_code == 403
    assert client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD}).status_code == 403
    assert TestClient(app).post("/auth/register", json={"email": "a@example.com", "password": PASSWORD}).status_code == 403


def test_wrong_password_inactive_legacy_and_validation_do_not_expose_secrets(client):
    wrong = client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD})
    absent = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == absent.status_code == 401
    assert wrong.json() == absent.json()
    response = client.post("/auth/register", json={"email": "a@example.com", "password": "short7!"})
    assert response.status_code == 422 and "short7!" not in response.text
    with Session(client.test_engine) as db:
        db.add(User(email="legacy@example.com", active=False, password_hash=None))
        db.commit()
    assert client.post("/auth/register", json={"email": "legacy@example.com", "password": PASSWORD}).status_code == 409
    assert client.post("/auth/login", json={"email": "legacy@example.com", "password": PASSWORD}).status_code == 401


def test_eight_character_password_registers_and_logs_in(client):
    payload = {"email": "eight@example.com", "password": "Abc123!?"}
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.post("/auth/logout").status_code == 204
    assert client.post("/auth/login", json=payload).status_code == 200


@pytest.mark.parametrize("length, accepted", [(7, False), (8, True), (128, True), (129, False)])
def test_password_length_boundaries(length, accepted):
    from pydantic import ValidationError
    from app.auth_schemas import Credentials
    if accepted:
        assert len(Credentials(email="person@example.com", password="a" * length).password.get_secret_value()) == length
    else:
        with pytest.raises(ValidationError):
            Credentials(email="person@example.com", password="a" * length)


def test_all_financial_queries_and_references_are_workspace_isolated(client):
    expense = category(client)
    income = category(client, "income")
    campaign = client.post("/campaigns", json={"name": "Natal"}).json()["id"]
    assert client.post("/budgets", json={"category_id": expense, "year": 2026, "month": 11, "amount": "100.00"}).status_code == 201
    assert client.post("/expenses", json=entry(expense, campaign_id=campaign)).status_code == 201
    assert client.post("/incomes", json=entry(income, "income", campaign_id=campaign)).status_code == 201
    content = f"categoria_id;descricao;data;valor\n{expense};Importada;2026-11-05;10.00\n".encode()
    batch = client.post("/imports/expenses/preview", files={"file": ("test.csv", content)}).json()
    assert client.post(f"/imports/{batch['import_id']}/confirm", json={}).status_code == 200
    job = client.get("/automations").json()[0]
    other = other_client(client, separate_workspace=True)
    for path in ["/categories", "/campaigns", "/budgets", "/expenses?year=2026&month=11", "/incomes?year=2026&month=11", "/imports", "/automations"]:
        assert other.get(path).json() == [], path
    assert other.get(f"/imports/{batch['import_id']}").status_code == 404
    assert other.post(f"/imports/{batch['import_id']}/confirm", json={}).status_code == 404
    assert other.post(f"/automations/{job['id']}/retry").status_code == 404
    for path, data in [("/expenses", entry(expense)), ("/incomes", entry(income, "income")), ("/budgets", {"category_id": expense, "year": 2026, "month": 11, "amount": "10.00"})]:
        assert other.post(path, json=data).status_code == 404
    mine = category(other)
    assert other.post("/expenses", json=entry(mine, campaign_id=campaign)).status_code == 404
    summary = other.get("/dashboard/summary?year=2026&month=11").json()
    assert summary["actual"] == summary["planned"] == "0.00"
    analytics = other.get("/dashboard/analytics?year=2026&month=11").json()
    assert analytics["categories"] == analytics["campaigns"] == []
    assert analytics["income_total"] == analytics["expense_total"] == "0.00"
    assert all(row["income"] == row["expenses"] == "0.00" for row in analytics["monthly"])
    assert other.get("/alerts?year=2026&month=11").json()["alerts"] == []
    answer = other.post("/copilot/chat", json={"question": "Como está o orçamento?", "year": 2026, "month": 11})
    assert answer.status_code == 200
    assert answer.json()["tools_used"][0]["result"]["actual"] == "0.00"
    # Same names and file contents may be used independently by each owner.
    assert other.post("/campaigns", json={"name": "Natal"}).status_code == 201
    other_batch = other.post("/imports/expenses/preview", files={"file": ("test.csv", content)}).json()
    assert other_batch["import_id"] != batch["import_id"]
    assert other_batch["report"]["valid_count"] == 0
    assert client.get("/dashboard/summary?year=2026&month=11").json()["actual"] == "22.34"


def test_database_rejects_cross_workspace_links_even_outside_http(client):
    cat = category(client)
    other = other_client(client, separate_workspace=True)
    identity = other.get("/auth/me").json()
    user_id, workspace_id = identity["user"]["id"], identity["workspace"]["id"]
    with Session(client.test_engine) as db:
        with pytest.raises(IntegrityError):
            db.execute(Expense.__table__.insert().values(workspace_id=workspace_id, created_by=user_id, updated_by=user_id, category_id=cat, amount="1.00", description="Invasão", expense_date=__import__('datetime').date(2026, 11, 5), created_at=utcnow(), updated_at=utcnow(), attribution_source="recorded"))


def test_login_rate_limit_is_persisted(client):
    from app.models import AuthAttempt
    with Session(client.test_engine) as db:
        row = db.scalar(select(AuthAttempt))
        row.count = 20
        db.commit()
    assert client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD}).status_code == 429


def test_request_session_without_owner_cannot_query_or_create_financial_data(client):
    with Session(client.test_engine, info={"http_request": True}) as db:
        with pytest.raises(RuntimeError, match="authenticated workspace"):
            db.scalars(select(Category)).all()
        db.add(Category(name="Não autorizado", type="expense"))
        with pytest.raises(RuntimeError, match="authenticated workspace"):
            db.flush()


def test_automation_capability_cannot_read_other_periods_or_write(client):
    cat = category(client)
    content = f"categoria_id;descricao;data;valor\n{cat};Importada;2026-11-05;10.00\n".encode()
    batch = client.post("/imports/expenses/preview", files={"file": ("test.csv", content)}).json()
    client.post(f"/imports/{batch['import_id']}/confirm", json={})
    token = secrets.token_urlsafe(32)
    with Session(client.test_engine, info={"workspace_id": client.test_workspace_id, "actor_id": client.test_user_id}) as db:
        job = db.scalar(select(AutomationJob))
        job.status = "running"
        db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=client.test_user_id, workspace_id=client.test_workspace_id, job_id=job.id, expires_at=utcnow() + timedelta(minutes=5)))
        db.commit()
    api = TestClient(app)
    api.headers["Authorization"] = f"Bearer {token}"
    assert api.get("/dashboard/summary?year=2026&month=11").status_code == 200
    assert api.get("/alerts?year=2026&month=11").status_code == 200
    assert api.get("/dashboard/summary?year=2026&month=12").status_code == 403
    assert api.get("/categories").status_code == 403
    assert api.post("/expenses", json=entry(cat)).status_code == 403
    assert api.get("/auth/me").status_code == 403


def test_worker_forwards_only_job_capability_and_revokes_it(client, monkeypatch):
    from types import SimpleNamespace
    from app import automation_worker
    cat = category(client)
    content = f"categoria_id;descricao;data;valor\n{cat};Importada;2026-11-05;10.00\n".encode()
    batch = client.post("/imports/expenses/preview", files={"file": ("test.csv", content)}).json()
    client.post(f"/imports/{batch['import_id']}/confirm", json={})
    api = TestClient(app)
    tokens = []
    from app.services import automation_summary, copilot
    from pydantic import SecretStr
    monkeypatch.setattr(automation_summary.settings, "ai_mode", "gemini")
    monkeypatch.setattr(automation_summary.settings, "gemini_api_key", SecretStr("fake-key"))
    class RagClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(automation_summary.genai, "Client", RagClient)
    monkeypatch.setattr(copilot, "search_analysis_policies", lambda *args: [])

    class WorkflowClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json):
            token = json["api_token"]
            tokens.append(token)
            api.headers["Authorization"] = f"Bearer {token}"
            params = {key: json[key] for key in ("year", "month", "workspace_id", "import_id", "attempt")}
            analysis = api.get(f"/automations/{json['job_id']}/analysis", params=params)
            assert analysis.status_code == 200, analysis.text
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: analysis.json())

    monkeypatch.setattr(automation_worker, "engine", client.test_engine)
    monkeypatch.setattr(automation_worker.httpx, "Client", WorkflowClient)
    assert automation_worker.process_one()
    assert client.get("/automations").json()[0]["status"] == "succeeded"
    with Session(client.test_engine) as db:
        assert db.get(AuthSession, hashlib.sha256(tokens[0].encode()).hexdigest()) is None
