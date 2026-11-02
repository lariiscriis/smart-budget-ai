from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Category
from app.schemas import CategoryCreate, CategoryRead


router = APIRouter(prefix="/categories", tags=["Categories"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(payload: CategoryCreate, db: DbSession):
    category = Category(name=payload.name)
    db.add(category)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        if error.orig.args and error.orig.args[0] == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma categoria com esse nome.",
            ) from None

        raise

    db.refresh(category)
    return category


@router.get("", response_model=list[CategoryRead])
def list_categories(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    statement = (
        select(Category)
        .order_by(Category.name, Category.id)
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()