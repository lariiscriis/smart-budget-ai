from decimal import Decimal

from app.services.category_comparison import build_comparison


def test_comparison_includes_unbudgeted_expenses_and_unused_budgets():
    result = build_comparison(
        year=2026,
        month=12,
        names=[
            (1, "Marketing"),
            (2, "Tecnologia"),
            (3, "Operações"),
        ],
        planned={
            1: Decimal("1000.00"),
            2: Decimal("500.00"),
        },
        actual={
            1: Decimal("100.00"),
            3: Decimal("200.00"),
        },
    )

    assert result.summary.planned == Decimal("1500.00")
    assert result.summary.actual == Decimal("300.00")
    assert result.summary.balance == Decimal("1200.00")
    assert result.summary.utilization_percentage == Decimal("20.00")

    by_id = {item.category_id: item.summary for item in result.categories}

    assert by_id[2].actual == Decimal("0.00")
    assert by_id[2].utilization_percentage == Decimal("0.00")
    assert by_id[3].planned == Decimal("0.00")
    assert by_id[3].balance == Decimal("-200.00")
    assert by_id[3].utilization_percentage is None


def test_comparison_handles_empty_period():
    result = build_comparison(
        year=2026,
        month=12,
        names=[],
        planned={},
        actual={},
    )

    assert result.categories == []
    assert result.summary.planned == Decimal("0.00")
    assert result.summary.actual == Decimal("0.00")
    assert result.summary.utilization_percentage is None