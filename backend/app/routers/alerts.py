from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.alerts import FinancialAlert, build_alerts
from app.services.category_comparison import get_category_comparison


router = APIRouter(prefix="/alerts", tags=["Alerts"])
DbSession = Annotated[Session, Depends(get_db)]


class AlertsResponse(BaseModel):
    year: int
    month: int
    rules_version: str
    count: int
    alerts: list[FinancialAlert]


@router.get("", response_model=AlertsResponse)
def read_alerts(
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
):
    comparison = get_category_comparison(db, year, month)
    alerts = build_alerts(comparison)

    return AlertsResponse(
        year=year,
        month=month,
        rules_version="1.0",
        count=len(alerts),
        alerts=alerts,
    )