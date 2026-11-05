from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Category
from app.schemas import CategoryCreate, CategoryRead, CategoryType
from app.services.entry_validation import is_duplicate


router = APIRouter(prefix="/categories", tags=["Categories"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(payload: CategoryCreate, db: DbSession):
    category = Category(name=payload.name, type=payload.type)
    db.add(category)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        if is_duplicate(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma categoria com esse nome e tipo.",
            ) from None

        raise

    db.refresh(category)
    return category


@router.get("", response_model=list[CategoryRead])
def list_categories(
    db: DbSession,
    type: Annotated[CategoryType | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    statement = (
        select(Category)
        .order_by(Category.name, Category.id)
        .offset(offset)
        .limit(limit)
    )

    if type is not None:
        statement = statement.where(Category.type == type)
    return db.scalars(statement).all()
