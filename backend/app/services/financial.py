from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, Expense
from app.schemas import FinancialSummary
from app.services.calculations import calculate_summary


def get_monthly_summary(
    db: Session,
    year: int,
    month: int,
) -> FinancialSummary:
    start = date(year, month, 1)
    end = (
        date(year + 1, 1, 1)
        if month == 12
        else date(year, month + 1, 1)
    )

    planned = db.scalar(
        select(func.sum(Budget.amount)).where(
            Budget.year == year,
            Budget.month == month,
        )
    )

    actual = db.scalar(
        select(func.sum(Expense.amount)).where(
            Expense.expense_date >= start,
            Expense.expense_date < end,
        )
    )

    return calculate_summary(
        year=year,
        month=month,
        planned=planned if planned is not None else Decimal("0.00"),
        actual=actual if actual is not None else Decimal("0.00"),
    )