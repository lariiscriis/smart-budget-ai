from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import AutomationJob


router = APIRouter(prefix="/automations", tags=["Automations"])
DbSession = Annotated[Session, Depends(get_db)]


def job_response(job: AutomationJob) -> dict:
    return {
        "id": job.id,
        "import_id": job.import_id,
        "year": job.year,
        "month": job.month,
        "status": job.status,
        "attempts": job.attempts,
        "last_error": job.last_error,
        "result": job.result,
        "created_at": job.created_at,
    }


@router.get("")
def list_jobs(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    jobs = db.scalars(
        select(AutomationJob)
        .order_by(AutomationJob.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [job_response(job) for job in jobs]


@router.post("/{job_id}/retry")
def retry_job(
    job_id: int,
    db: DbSession,
):
    job = db.scalar(
        select(AutomationJob)
        .where(AutomationJob.id == job_id)
        .with_for_update()
    )

    if job is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    if job.status != "failed":
        raise HTTPException(
            status_code=409,
            detail="Somente tarefas com falha podem voltar à fila.",
        )

    job.status = "pending"
    job.last_error = None
    job.result = None
    db.commit()
    db.refresh(job)

    return job_response(job)