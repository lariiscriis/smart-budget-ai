from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Income
from app.schemas import IncomeCreate, IncomeRead
from app.services.entry_validation import require_campaign, require_category

router = APIRouter(prefix="/incomes", tags=["Incomes"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=IncomeRead, status_code=status.HTTP_201_CREATED)
def create_income(payload: IncomeCreate, db: DbSession):
    require_category(db, payload.category_id, "income")
    require_campaign(db, payload.campaign_id)
    income = Income(**payload.model_dump())
    db.add(income)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if error.orig.args and error.orig.args[0] == 1452:
            raise HTTPException(
                status_code=409,
                detail="A categoria ou campanha deixou de estar disponível. Consulte novamente.",
            ) from None
        raise
    db.refresh(income)
    return income


@router.get("", response_model=list[IncomeRead])
def list_incomes(
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    category_id: Annotated[int | None, Query(gt=0)] = None,
    campaign_id: Annotated[int | None, Query(gt=0)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    statement = select(Income).where(Income.income_date >= start, Income.income_date < end)
    if category_id is not None:
        statement = statement.where(Income.category_id == category_id)
    if campaign_id is not None:
        statement = statement.where(Income.campaign_id == campaign_id)
    return db.scalars(
        statement.order_by(Income.income_date, Income.id).offset(offset).limit(limit)
    ).all()
