from decimal import Decimal

import pytest

from app.copilot_schemas import PolicySource, SummaryArguments
from app.services import copilot
from app.services.category_comparison import build_comparison


@pytest.mark.parametrize(
    "actual, expected_code",
    [
        ("50.00", None),
        ("110.00", "over_budget"),
    ],
)
def test_review_combines_financial_data_and_sources(
    monkeypatch,
    actual,
    expected_code,
):
    fake_db = object()
    fake_client = object()
    calls = []

    def fake_comparison(db, year, month):
        assert db is fake_db
        calls.append(("financial", year, month))

        return build_comparison(
            year=year,
            month=month,
            names=[(1, "Tecnologia")],
            planned={1: Decimal("100.00")},
            actual={1: Decimal(actual)},
        )

    def fake_search(db, client, question):
        assert db is fake_db
        assert client is fake_client
        calls.append(("policy", question))

        return [
            PolicySource(
                source_id="S1",
                document_id="POL-ORC-001",
                version="1.0",
                section_id="ORC-03",
                section_title="Orçamento ultrapassado",
                text="O responsável deve revisar e justificar o desvio.",
                similarity=0.8,
            )
        ]

    monkeypatch.setattr(
        copilot,
        "get_category_comparison",
        fake_comparison,
    )
    monkeypatch.setattr(
        copilot,
        "search_financial_policies",
        fake_search,
    )

    question = "Como estão os gastos e o que a política recomenda?"

    result = copilot.execute_selected_tool(
        "review_budget_policy",
        fake_db,
        SummaryArguments(year=2026, month=11),
        question=question,
        client=fake_client,
    )

    assert calls == [
        ("financial", 2026, 11),
        ("policy", question),
    ]

    assert result.name == "review_budget_policy"
    assert result.result is not None
    assert result.result.actual == Decimal(actual)
    assert len(result.categories) == 1
    assert result.sources[0].section_id == "ORC-03"

    if expected_code is None:
        assert result.alerts == []
    else:
        assert len(result.alerts) == 1
        assert result.alerts[0].code == expected_code