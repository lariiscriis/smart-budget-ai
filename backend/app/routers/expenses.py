from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseRead
from app.services.entry_validation import require_category, require_campaign


router = APIRouter(prefix="/expenses", tags=["Expenses"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(payload: ExpenseCreate, db: DbSession):
    require_category(db, payload.category_id, "expense")
    require_campaign(db, payload.campaign_id)

    expense = Expense(
        category_id=payload.category_id,
        campaign_id=payload.campaign_id,
        description=payload.description,
        expense_date=payload.expense_date,
        amount=payload.amount,
    )
    db.add(expense)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        if error.orig.args and error.orig.args[0] == 1452:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A categoria ou campanha deixou de estar disponível. Consulte novamente.",
            ) from None

        raise

    db.refresh(expense)
    return expense


@router.get("", response_model=list[ExpenseRead])
def list_expenses(
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    category_id: Annotated[int | None, Query(gt=0)] = None,
    campaign_id: Annotated[int | None, Query(gt=0)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    start = date(year, month, 1)
    end = (
        date(year + 1, 1, 1)
        if month == 12
        else date(year, month + 1, 1)
    )

    statement = select(Expense).where(
        Expense.expense_date >= start,
        Expense.expense_date < end,
    )

    if category_id is not None:
        statement = statement.where(Expense.category_id == category_id)
    if campaign_id is not None:
        statement = statement.where(Expense.campaign_id == campaign_id)

    statement = (
        statement
        .order_by(Expense.expense_date, Expense.id)
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()
