from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Campaign
from app.schemas import CampaignCreate, CampaignRead
from app.services.entry_validation import is_duplicate

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: DbSession):
    campaign = Campaign(name=payload.name)
    db.add(campaign)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if is_duplicate(error):
            raise HTTPException(status_code=409, detail="Já existe uma campanha com esse nome.") from None
        raise
    db.refresh(campaign)
    return campaign


@router.get("", response_model=list[CampaignRead])
def list_campaigns(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return db.scalars(
        select(Campaign).order_by(Campaign.name, Campaign.id).offset(offset).limit(limit)
    ).all()
