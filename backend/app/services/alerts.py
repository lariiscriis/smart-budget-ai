from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.copilot_schemas import CategoryComparison, FinancialAlert



def build_alerts(comparison: CategoryComparison) -> list[FinancialAlert]:
    alerts = []

    for category in comparison.categories:
        summary = category.summary

        if summary.planned == 0 and summary.actual > 0:
            code = "unbudgeted"
            severity = "critical"
            message = "Há despesas sem orçamento previsto."

        elif summary.planned > 0 and summary.actual > summary.planned:
            code = "over_budget"
            severity = "critical"
            message = "O realizado ultrapassou o orçamento previsto."

        elif (
            summary.planned > 0
            and summary.actual >= summary.planned * Decimal("0.80")
        ):
            code = "near_limit"
            severity = "warning"
            message = "A utilização está entre 80% e 100% do orçamento."

        else:
            continue

        alerts.append(
            FinancialAlert(
                category_id=category.category_id,
                category_name=category.category_name,
                code=code,
                severity=severity,
                message=message,
                planned=summary.planned,
                actual=summary.actual,
                balance=summary.balance,
            )
        )

    return sorted(
        alerts,
        key=lambda alert: (
            0 if alert.severity == "critical" else 1,
            alert.category_name,
            alert.category_id,
        ),
    )