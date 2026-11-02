from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import FinancialSummary
from app.services.financial import get_monthly_summary


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=FinancialSummary)
def read_monthly_summary(
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
):
    return get_monthly_summary(db, year, month)