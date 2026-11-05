from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import FinancialSummary
from app.services.financial import get_monthly_summary
from app.dashboard_schemas import DashboardAnalytics
from app.services.dashboard import get_dashboard_analytics


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=FinancialSummary)
def read_monthly_summary(
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
):
    return get_monthly_summary(db, year, month)


@router.get("/analytics", response_model=DashboardAnalytics)
def read_dashboard_analytics(
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    months: Annotated[int, Query(ge=1, le=24)] = 12,
):
    """Monthly history ends in the selected month; other breakdowns use that month."""
    return get_dashboard_analytics(db, year, month, months)
