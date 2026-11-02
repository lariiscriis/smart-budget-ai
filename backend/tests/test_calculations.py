from decimal import Decimal

import pytest

from app.services.calculations import calculate_summary


@pytest.mark.parametrize(
    "planned, actual, expected_balance, expected_percentage",
    [
        ("5000.00", "800.00", "4200.00", "16.00"),
        ("100.00", "125.00", "-25.00", "125.00"),
        ("100.00", "100.00", "0.00", "100.00"),
        ("0.00", "0.00", "0.00", None),
        ("0.00", "80.00", "-80.00", None),
        ("3.00", "1.00", "2.00", "33.33"),
        ("200.00", "2.01", "197.99", "1.01"),
        ("0.30", "0.10", "0.20", "33.33"),
    ],
    ids=[
        "within-budget",
        "over-budget",
        "exact-budget",
        "empty-period",
        "expense-without-budget",
        "repeating-percentage",
        "half-up-rounding",
        "decimal-precision",
    ],
)
def test_calculate_summary(
    planned,
    actual,
    expected_balance,
    expected_percentage,
):
    result = calculate_summary(
        year=2026,
        month=11,
        planned=Decimal(planned),
        actual=Decimal(actual),
    )

    assert result.year == 2026
    assert result.month == 11
    assert result.currency == "BRL"
    assert result.planned == Decimal(planned)
    assert result.actual == Decimal(actual)
    assert result.balance == Decimal(expected_balance)

    if expected_percentage is None:
        assert result.utilization_percentage is None
    else:
        assert result.utilization_percentage == Decimal(expected_percentage)