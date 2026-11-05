from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Budget
from app.schemas import BudgetCreate, BudgetRead
from app.services.entry_validation import require_category


router = APIRouter(prefix="/budgets", tags=["Budgets"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(payload: BudgetCreate, db: DbSession):
    require_category(db, payload.category_id, "expense")

    budget = Budget(
        category_id=payload.category_id,
        year=payload.year,
        month=payload.month,
        amount=payload.amount,
    )
    db.add(budget)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        mysql_code = error.orig.args[0] if error.orig.args else None

        if mysql_code == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe orçamento para essa categoria e período.",
            ) from None

        if mysql_code == 1452:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A categoria deixou de estar disponível. Consulte novamente.",
            ) from None

        raise

    db.refresh(budget)
    return budget


@router.get("", response_model=list[BudgetRead])
def list_budgets(
    db: DbSession,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    statement = select(Budget)

    if year is not None:
        statement = statement.where(Budget.year == year)

    if month is not None:
        statement = statement.where(Budget.month == month)

    if category_id is not None:
        statement = statement.where(Budget.category_id == category_id)

    statement = (
        statement
        .order_by(Budget.year, Budget.month, Budget.category_id, Budget.id)
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()
