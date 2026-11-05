"""Shared validation for references used by financial entry routes."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Campaign, Category
from app.schemas import CategoryType


def require_category(db: Session, category_id: int, expected_type: CategoryType) -> None:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    if category.type != expected_type:
        raise HTTPException(
            status_code=422,
            detail=f"Esta operação exige uma categoria do tipo '{expected_type}'.",
        )


def require_campaign(db: Session, campaign_id: int | None) -> None:
    if campaign_id is not None and db.get(Campaign, campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")


def is_duplicate(error: Exception) -> bool:
    """Recognize unique violations in MySQL and isolated SQLite tests."""
    original = getattr(error, "orig", None)
    args = getattr(original, "args", ())
    return bool(args and args[0] == 1062) or getattr(original, "sqlite_errorname", "") in {
        "SQLITE_CONSTRAINT_UNIQUE", "SQLITE_CONSTRAINT_PRIMARYKEY",
    }
