import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import ImportBatch
from app.services.import_batches import (
    batch_response,
    confirm_import,
    register_preview,
)
from app.services.import_preview import MAX_FILE_BYTES, read_table


router = APIRouter(prefix="/imports", tags=["Imports"])
logger = logging.getLogger(__name__)

DbSession = Annotated[Session, Depends(get_db)]


class ImportConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept_valid_only: bool = Field(default=False, strict=True)


@router.post("/expenses/preview")
def preview_expense_import(
    db: DbSession,
    file: Annotated[UploadFile, File()],
):
    try:
        content = file.file.read(MAX_FILE_BYTES + 1)
    finally:
        file.file.close()

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="O arquivo ultrapassa o limite de 2 MB.",
        )

    try:
        frame = read_table(file.filename or "", content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except Exception:
        logger.exception("Falha na leitura do arquivo de importação.")
        raise HTTPException(
            status_code=422,
            detail="Não foi possível ler o arquivo. Confira o formato e a codificação.",
        ) from None

    try:
        return register_preview(
            db,
            file.filename or "arquivo",
            content,
            frame,
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Falha ao registrar prévia.")
        raise HTTPException(
            status_code=503,
            detail="Não foi possível registrar a prévia. Tente novamente.",
        ) from None


@router.post("/{import_id}/confirm")
def confirm_expense_import(
    import_id: UUID,
    payload: ImportConfirmation,
    db: DbSession,
):
    try:
        return confirm_import(
            db,
            str(import_id),
            payload.accept_valid_only,
        )
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Falha ao confirmar importação.")
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível confirmar a importação. "
                "Consulte seu status antes de tentar novamente."
            ),
        ) from None


@router.get("")
def list_imports(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    batches = db.scalars(
        select(ImportBatch)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id)
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        {
            "import_id": batch.id,
            "filename": batch.filename,
            "status": batch.status,
            "saved_count": batch.saved_count,
            "created_at": batch.created_at,
            "valid_count": batch.report["valid_count"],
            "invalid_count": batch.report["invalid_count"],
            "duplicate_count": batch.report["duplicate_count"],
        }
        for batch in batches
    ]


@router.get("/{import_id}")
def get_import(import_id: UUID, db: DbSession):
    batch = db.get(ImportBatch, str(import_id))

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="Importação não encontrada.",
        )

    return batch_response(batch)