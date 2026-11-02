from decimal import Decimal, ROUND_HALF_UP

from app.schemas import FinancialSummary


def calculate_summary(
    year: int,
    month: int,
    planned: Decimal,
    actual: Decimal,
) -> FinancialSummary:
    utilization = None

    if planned > 0:
        utilization = (
            actual / planned * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return FinancialSummary(
        year=year,
        month=month,
        currency="BRL",
        planned=planned,
        actual=actual,
        balance=planned - actual,
        utilization_percentage=utilization,
    )