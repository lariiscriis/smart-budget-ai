from sqlalchemy.orm import Session

from app.models import AutomationJob
from app.schemas import ExpenseCreate


def imported_periods(
    expenses: list[ExpenseCreate],
) -> list[tuple[int, int]]:
    return sorted({
        (expense.expense_date.year, expense.expense_date.month)
        for expense in expenses
    })


def enqueue_import_jobs(
    db: Session,
    import_id: str,
    expenses: list[ExpenseCreate],
) -> None:
    for year, month in imported_periods(expenses):
        db.add(
            AutomationJob(
                import_id=import_id,
                year=year,
                month=month,
                status="pending",
                attempts=0,
            )
        )