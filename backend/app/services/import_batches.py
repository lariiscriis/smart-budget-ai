from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, Expense, ImportBatch
from app.schemas import ExpenseCreate
from app.services.import_preview import preview_expenses


def batch_response(batch: ImportBatch) -> dict:
    return {
        "import_id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "saved_count": batch.saved_count,
        "report": batch.report,
    }


def register_preview(
    db: Session,
    filename: str,
    content: bytes,
    frame: pd.DataFrame,
) -> dict:
    fingerprint = sha256(content).hexdigest()

    existing = db.scalar(
        select(ImportBatch).where(ImportBatch.file_hash == fingerprint)
    )

    if existing is not None:
        return batch_response(existing)

    report = preview_expenses(frame, db)

    batch = ImportBatch(
        id=str(uuid4()),
        file_hash=fingerprint,
        filename=filename[:255],
        status="pending",
        report=report,
        saved_count=0,
    )
    db.add(batch)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        if error.orig.args and error.orig.args[0] == 1062:
            existing = db.scalar(
                select(ImportBatch).where(
                    ImportBatch.file_hash == fingerprint
                )
            )

            if existing is not None:
                return batch_response(existing)

        raise

    db.refresh(batch)
    return batch_response(batch)


def confirm_import(
    db: Session,
    import_id: str,
    accept_valid_only: bool,
) -> dict:
    batch = db.scalar(
        select(ImportBatch)
        .where(ImportBatch.id == import_id)
        .with_for_update()
    )

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="Importação não encontrada.",
        )

    if batch.status == "completed":
        result = {
            "import_id": batch.id,
            "status": batch.status,
            "saved_count": batch.saved_count,
            "already_completed": True,
        }
        db.commit()
        return result

    report = batch.report

    if report["valid_count"] == 0:
        raise HTTPException(
            status_code=409,
            detail="A importação não possui registros válidos.",
        )

    has_rejected_rows = (
        report["invalid_count"] > 0 or report["duplicate_count"] > 0
    )

    if has_rejected_rows and not accept_valid_only:
        raise HTTPException(
            status_code=409,
            detail=(
                "Existem erros ou duplicatas. Revise a prévia e envie "
                "accept_valid_only=true para salvar apenas os válidos."
            ),
        )

    payloads = [
        ExpenseCreate.model_validate(item["data"])
        for item in report["valid_rows"]
    ]

    category_ids = {payload.category_id for payload in payloads}
    existing_ids = set(
        db.scalars(
            select(Category.id).where(Category.id.in_(category_ids))
        ).all()
    )

    if existing_ids != category_ids:
        raise HTTPException(
            status_code=409,
            detail="Uma categoria da prévia não existe mais. Nenhuma despesa foi salva.",
        )

    for payload in payloads:
        db.add(
            Expense(
                category_id=payload.category_id,
                description=payload.description,
                expense_date=payload.expense_date,
                amount=payload.amount,
                import_id=batch.id,
            )
        )

    batch.status = "completed"
    batch.saved_count = len(payloads)

    result = {
        "import_id": batch.id,
        "status": batch.status,
        "saved_count": batch.saved_count,
        "already_completed": False,
    }

    db.commit()
    return result