from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import AutomationJob, ImportBatch
from app.schemas import record_metadata
from app.automation_schemas import WorkflowResult, validate_workflow_result
from app.services.automation_summary import build_automation_result, job_context


router = APIRouter(prefix="/automations", tags=["Automations"])
DbSession = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)


def job_response(job: AutomationJob) -> dict:
    return {
        **record_metadata(job),
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


@router.get("/{job_id}/analysis", response_model=WorkflowResult)
def automation_analysis(job_id: int, db: DbSession):
    # Only a short-lived capability issued by the worker can invoke this route.
    if db.info.get("automation_job_id") != job_id or db.info.get("actor_kind") != "automation":
        raise HTTPException(403, "Esta consulta exige a credencial restrita da tarefa.")
    job = db.scalar(select(AutomationJob).where(AutomationJob.id == job_id)
                    .with_for_update().execution_options(populate_existing=True))
    if (job is None or job.status != "running"
        or job.attempts != db.info.get("automation_attempt")):
        raise HTTPException(409, "A tentativa não está mais ativa.")
    batch = db.get(ImportBatch, job.import_id)
    if batch is None or batch.status != "completed":
        raise HTTPException(409, "A importação ainda não foi concluída.")
    try:
        if job.result is not None:
            # Reuse a completed analysis after timeout/retry; no repeated RAG.
            result = validate_workflow_result(job.result, job.year, job.month)
            result.context.attempt = job.attempts
        else:
            result = build_automation_result(db, job)
        result = validate_workflow_result(result, job.year, job.month, job_context(job))
        job.result = result.model_dump(mode="json")
        db.commit()
        return result
    except Exception as error:
        db.rollback()
        # Exception text/provider responses can contain secrets or request data.
        logger.warning("Falha na análise automática: %s", type(error).__name__)
        raise HTTPException(503, "Não foi possível gerar a análise com políticas. Tente novamente após verificar o RAG.") from None


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
    # Preserve a cached analysis if delivery failed after it was generated.
    db.commit()
    db.refresh(job)

    return job_response(job)
