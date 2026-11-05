from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import AuditLog
from app.schemas import AttributionUser

router = APIRouter(prefix="/audit", tags=["Audit"])


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workspace_id: int
    actor_id: int
    actor: AttributionUser
    actor_kind: str
    action: Literal["create", "update", "delete", "migrate"]
    entity: str
    entity_id: str
    occurred_at: datetime
    changes: dict

    @field_serializer("occurred_at")
    def utc_date(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("", response_model=list[AuditRead])
def list_audit(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit)).all()
