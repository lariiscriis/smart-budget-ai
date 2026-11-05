from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.copilot_schemas import CopilotRequest
from app.schemas import FinancialSummary
from app.services import copilot


def test_mock_uses_summary_without_calling_google(monkeypatch):
    monkeypatch.setattr(copilot.settings, "ai_mode", "mock")
    calls = []
    fake_db = object()

    def fake_summary(db, year, month):
        calls.append((db, year, month))

        return FinancialSummary(
            year=year,
            month=month,
            currency="BRL",
            planned=Decimal("1000.00"),
            actual=Decimal("250.50"),
            balance=Decimal("749.50"),
            utilization_percentage=Decimal("25.05"),
        )

    def forbidden_client(*args, **kwargs):
        pytest.fail("O modo mock não pode criar um cliente Gemini.")

    monkeypatch.setattr(copilot, "get_monthly_summary", fake_summary)
    monkeypatch.setattr(copilot.genai, "Client", forbidden_client)

    result = copilot.ask_copilot(
        fake_db,
        CopilotRequest(
            question="Como está o orçamento?",
            year=2026,
            month=12,
        ),
    )

    assert calls == [(fake_db, 2026, 12)]
    assert result.mode == "mock"
    assert len(result.tools_used) == 1
    assert result.tools_used[0].result.balance == Decimal("749.50")


@pytest.mark.parametrize(
    "function_calls, expected_message",
    [
        ([], "ferramenta esperada"),
        (
            [
                SimpleNamespace(
                    name="delete_expenses",
                    args={"year": 2026, "month": 12},
                )
            ],
            "ferramenta esperada",
        ),
        (
            [
                SimpleNamespace(
                    name="get_budget_summary",
                    args={"year": 2026, "month": 11},
                )
            ],
            "período diferente",
        ),
        (
            [
                SimpleNamespace(
                    name="get_budget_summary",
                    args={"year": 2026, "month": 12},
                ),
                SimpleNamespace(
                    name="get_budget_summary",
                    args={"year": 2026, "month": 12},
                ),
            ],
            "ferramenta esperada",
        ),
    ],
)
def test_rejects_invalid_tool_requests(
    monkeypatch,
    function_calls,
    expected_message,
):
    monkeypatch.setattr(copilot.settings, "ai_mode", "gemini")
    monkeypatch.setattr(
        copilot.settings,
        "gemini_api_key",
        SecretStr("fake-key-for-unit-test"),
    )

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def generate_content(self, **kwargs):
            return SimpleNamespace(function_calls=function_calls)

    def forbidden_summary(*args, **kwargs):
        pytest.fail("Uma chamada rejeitada não pode consultar o resumo.")

    monkeypatch.setattr(copilot.genai, "Client", FakeClient)
    monkeypatch.setattr(copilot, "get_monthly_summary", forbidden_summary)

    with pytest.raises(RuntimeError, match=expected_message):
        copilot.ask_copilot(
            object(),
            CopilotRequest(
                question="Como está o orçamento?",
                year=2026,
                month=12,
            ),
        )


def test_mock_routes_category_question_to_comparison(monkeypatch):
    from app.copilot_schemas import CategoryComparison

    monkeypatch.setattr(copilot.settings, "ai_mode", "mock")
    calls = []

    def fake_comparison(db, year, month):
        calls.append((year, month))
        return CategoryComparison(
            summary=FinancialSummary(
                year=year,
                month=month,
                currency="BRL",
                planned=Decimal("0.00"),
                actual=Decimal("0.00"),
                balance=Decimal("0.00"),
                utilization_percentage=None,
            ),
            categories=[],
        )

    def forbidden_summary(*args, **kwargs):
        pytest.fail("Esta pergunta deve utilizar a comparação.")

    def forbidden_client(*args, **kwargs):
        pytest.fail("O mock não pode acessar o Gemini.")

    monkeypatch.setattr(copilot, "get_category_comparison", fake_comparison)
    monkeypatch.setattr(copilot, "get_monthly_summary", forbidden_summary)
    monkeypatch.setattr(copilot.genai, "Client", forbidden_client)

    result = copilot.ask_copilot(
        object(),
        CopilotRequest(
            question="Compare as categorias.",
            year=2026,
            month=12,
        ),
    )

    assert calls == [(2026, 12)]
    assert result.tools_used[0].name == "compare_categories"

@pytest.mark.parametrize(
    "actual, expected_code",
    [
        ("79.99", None),
        ("100.01", "over_budget"),
    ],
)
def test_mock_returns_financial_alerts(
    monkeypatch,
    actual,
    expected_code,
):
    from app.services.category_comparison import build_comparison

    monkeypatch.setattr(copilot.settings, "ai_mode", "mock")
    calls = []

    def fake_comparison(db, year, month):
        calls.append((year, month))

        return build_comparison(
            year=year,
            month=month,
            names=[(1, "Tecnologia")],
            planned={1: Decimal("100.00")},
            actual={1: Decimal(actual)},
        )

    def forbidden_summary(*args, **kwargs):
        pytest.fail("A consulta deve utilizar a comparação para gerar alertas.")

    def forbidden_client(*args, **kwargs):
        pytest.fail("O mock não pode acessar o Gemini.")

    monkeypatch.setattr(
        copilot,
        "get_category_comparison",
        fake_comparison,
    )
    monkeypatch.setattr(
        copilot,
        "get_monthly_summary",
        forbidden_summary,
    )
    monkeypatch.setattr(copilot.genai, "Client", forbidden_client)

    result = copilot.ask_copilot(
        object(),
        CopilotRequest(
            question="Quais categorias precisam de atenção?",
            year=2026,
            month=12,
        ),
    )

    assert calls == [(2026, 12)]
    assert result.mode == "mock"
    assert len(result.tools_used) == 1

    execution = result.tools_used[0]

    assert execution.name == "get_financial_alerts"
    assert execution.result.actual == Decimal(actual)

    if expected_code is None:
        assert execution.alerts == []
        assert "Nenhuma categoria" in result.answer
    else:
        assert len(execution.alerts) == 1
        assert execution.alerts[0].code == expected_code
        assert execution.alerts[0].category_name == "Tecnologia"
        assert execution.alerts[0].balance == Decimal("-0.01")
        assert "Tecnologia" in result.answer

        serialized = result.model_dump(mode="json")
        alert = serialized["tools_used"][0]["alerts"][0]

        assert alert["code"] == expected_code
        assert alert["actual"] == "100.01"