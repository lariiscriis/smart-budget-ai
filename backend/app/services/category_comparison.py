from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.copilot_schemas import CategoryBreakdown, CategoryComparison
from app.models import Budget, Category, Expense
from app.services.calculations import calculate_summary


def build_comparison(
    year: int,
    month: int,
    names: list[tuple[int, str]],
    planned: dict[int, Decimal],
    actual: dict[int, Decimal],
) -> CategoryComparison:
    zero = Decimal("0.00")
    categories = []

    for category_id, category_name in names:
        summary = calculate_summary(
            year=year,
            month=month,
            planned=planned.get(category_id, zero),
            actual=actual.get(category_id, zero),
        )

        categories.append(
            CategoryBreakdown(
                category_id=category_id,
                category_name=category_name,
                summary=summary,
            )
        )

    total = calculate_summary(
        year=year,
        month=month,
        planned=sum(planned.values(), zero),
        actual=sum(actual.values(), zero),
    )

    return CategoryComparison(
        summary=total,
        categories=categories,
    )


def get_category_comparison(
    db: Session,
    year: int,
    month: int,
) -> CategoryComparison:
    start = date(year, month, 1)
    end = (
        date(year + 1, 1, 1)
        if month == 12
        else date(year, month + 1, 1)
    )

    planned = dict(
        db.execute(
            select(Budget.category_id, func.sum(Budget.amount))
            .where(Budget.year == year, Budget.month == month)
            .group_by(Budget.category_id)
        ).all()
    )

    actual = dict(
        db.execute(
            select(Expense.category_id, func.sum(Expense.amount))
            .where(
                Expense.expense_date >= start,
                Expense.expense_date < end,
            )
            .group_by(Expense.category_id)
        ).all()
    )

    active_ids = set(planned) | set(actual)

    names = []

    if active_ids:
        names = [
            (category_id, name)
            for category_id, name in db.execute(
                select(Category.id, Category.name)
                .where(Category.id.in_(active_ids))
                .order_by(Category.name, Category.id)
            ).all()
        ]

    return build_comparison(
        year,
        month,
        names,
        planned,
        actual,
    )