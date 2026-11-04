from decimal import Decimal

import pytest

from app.services.alerts import build_alerts
from app.services.category_comparison import build_comparison


@pytest.mark.parametrize(
    "planned, actual, expected_code",
    [
        ("0.00", "0.00", None),
        ("0.00", "50.00", "unbudgeted"),
        ("100.00", "79.99", None),
        ("100.00", "80.00", "near_limit"),
        ("100.00", "100.00", "near_limit"),
        ("100.00", "100.01", "over_budget"),
    ],
)
def test_alert_boundaries(planned, actual, expected_code):
    comparison = build_comparison(
        year=2026,
        month=12,
        names=[(1, "Categoria teste")],
        planned={1: Decimal(planned)},
        actual={1: Decimal(actual)},
    )

    result = build_alerts(comparison)

    if expected_code is None:
        assert result == []
    else:
        assert len(result) == 1
        assert result[0].code == expected_code
        assert result[0].category_id == 1