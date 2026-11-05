"""Read-only financial aggregations; income and expenses are grouped separately.

Never join raw income and expense rows: that would multiply campaign totals.
The session provides one transaction for the full dashboard response.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.dashboard_schemas import (
    CampaignAnalytics, CategoryAnalytics, DashboardAnalytics, MonthlyFlow,
)
from app.models import Campaign, Expense, Income
from app.services.category_comparison import get_category_comparison

ZERO = Decimal("0.00")


def next_month(year: int, month: int) -> date:
    return date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)


def monthly_totals(db: Session, model, day, start: date, end: date) -> dict:
    year, month = extract("year", day), extract("month", day)
    return {
        (int(row[0]), int(row[1])): (row[2], row[3])
        for row in db.execute(
            select(year, month, func.sum(model.amount), func.count(model.id))
            .where(day >= start, day < end)
            .group_by(year, month)
        ).all()
    }


def campaign_totals(db: Session, model, day, start: date, end: date) -> dict:
    return {
        campaign_id: (amount, count)
        for campaign_id, amount, count in db.execute(
            select(model.campaign_id, func.sum(model.amount), func.count(model.id))
            .where(day >= start, day < end)
            .group_by(model.campaign_id)
        ).all()
    }


def get_dashboard_analytics(
    db: Session, year: int, month: int, months: int = 12,
) -> DashboardAnalytics:
    selected_start = date(year, month, 1)
    end = next_month(year, month)
    # Keep the supported history within the public API's 2000–2100 range.
    start_index = max(2000 * 12, year * 12 + month - months)
    first_year, first_month = divmod(start_index, 12)
    start = date(first_year, first_month + 1, 1)
    incomes = monthly_totals(db, Income, Income.income_date, start, end)
    expenses = monthly_totals(db, Expense, Expense.expense_date, start, end)

    monthly = []
    cursor = start
    while cursor < end:
        key = (cursor.year, cursor.month)
        income, income_count = incomes.get(key, (ZERO, 0))
        expense, expense_count = expenses.get(key, (ZERO, 0))
        monthly.append(MonthlyFlow(
            year=cursor.year, month=cursor.month, income=income, expenses=expense,
            balance=income - expense, income_count=income_count, expense_count=expense_count,
        ))
        cursor = next_month(cursor.year, cursor.month)

    comparison = get_category_comparison(db, year, month)
    categories = [
        CategoryAnalytics(
            category_id=item.category_id, category_name=item.category_name,
            planned=item.summary.planned, actual=item.summary.actual,
            balance=item.summary.balance,
            expense_share_percentage=(
                (item.summary.actual / comparison.summary.actual * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP,
                ) if comparison.summary.actual > 0 else ZERO
            ),
        ) for item in comparison.categories
    ]
    categories.sort(key=lambda item: (-item.actual, item.category_name, item.category_id))

    campaign_income = campaign_totals(db, Income, Income.income_date, selected_start, end)
    campaign_expenses = campaign_totals(db, Expense, Expense.expense_date, selected_start, end)
    active_ids = set(campaign_income) | set(campaign_expenses)
    named_ids = active_ids - {None}
    names = dict(db.execute(
        select(Campaign.id, Campaign.name).where(Campaign.id.in_(named_ids))
    ).all()) if named_ids else {}
    campaigns = []
    for campaign_id in active_ids:
        income, income_count = campaign_income.get(campaign_id, (ZERO, 0))
        expense, expense_count = campaign_expenses.get(campaign_id, (ZERO, 0))
        campaigns.append(CampaignAnalytics(
            campaign_id=campaign_id,
            campaign_name=names[campaign_id] if campaign_id is not None else "Sem campanha",
            income=income, expenses=expense, balance=income - expense,
            income_count=income_count, expense_count=expense_count,
        ))
    campaigns.sort(key=lambda item: (item.campaign_id is None, item.campaign_name, item.campaign_id or 0))
    current = monthly[-1]
    return DashboardAnalytics(
        year=year, month=month, income_total=current.income,
        expense_total=current.expenses, cash_balance=current.balance,
        budget_summary=comparison.summary, monthly=monthly,
        categories=categories, campaigns=campaigns,
    )
