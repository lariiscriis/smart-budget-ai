from decimal import Decimal

from pydantic import BaseModel

from app.schemas import FinancialSummary


class MonthlyFlow(BaseModel):
    year: int
    month: int
    income: Decimal
    expenses: Decimal
    balance: Decimal
    income_count: int
    expense_count: int


class CategoryAnalytics(BaseModel):
    category_id: int
    category_name: str
    planned: Decimal
    actual: Decimal
    balance: Decimal
    expense_share_percentage: Decimal


class CampaignAnalytics(BaseModel):
    campaign_id: int | None
    campaign_name: str
    income: Decimal
    expenses: Decimal
    balance: Decimal
    income_count: int
    expense_count: int


class DashboardAnalytics(BaseModel):
    year: int
    month: int
    currency: str = "BRL"
    income_total: Decimal
    expense_total: Decimal
    cash_balance: Decimal
    budget_summary: FinancialSummary
    monthly: list[MonthlyFlow]
    categories: list[CategoryAnalytics]
    campaigns: list[CampaignAnalytics]
