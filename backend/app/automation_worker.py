"""Durable import outbox consumer. n8n orchestrates; backend owns the analysis."""
import argparse
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.automation_schemas import validate_workflow_result
from app.config import settings
from app.database import engine
from app.models import AutomationJob, AuthSession, ImportBatch
from app.services.automation_summary import job_context


LEASE_SECONDS = 300
WORKFLOW_TIMEOUT_SECONDS = 120


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def revoke_job_capabilities(db: Session, job_id: int) -> None:
    for capability in db.scalars(select(AuthSession).where(AuthSession.job_id == job_id)).all():
        db.delete(capability)


def recover_stale_jobs() -> None:
    """Recover crashed workers using the existing persisted updated_at timestamp.

    A cached result can extend the lease. After this interval every issued
    capability has expired as well. Row locks prevent recovering live requests.
    """
    for _ in range(20):
        with Session(engine) as db:
            job = db.scalar(select(AutomationJob).where(
                AutomationJob.status == "running",
                AutomationJob.updated_at <= utcnow() - timedelta(seconds=LEASE_SECONDS),
            ).order_by(AutomationJob.id).limit(1).with_for_update(skip_locked=True))
            if job is None:
                return
            db.info.update(workspace_id=job.workspace_id, actor_id=job.updated_by, actor_kind="automation")
            job.status, job.last_error = "failed", "WorkerLeaseExpired"
            revoke_job_capabilities(db, job.id)
            db.commit()


def process_one() -> bool:
    recover_stale_jobs()
    with Session(engine) as db:
        job = db.scalar(select(AutomationJob)
            .where(AutomationJob.status == "pending")
            .order_by(AutomationJob.id).limit(1).with_for_update(skip_locked=True))
        if job is None:
            return False
        actor_id, workspace_id = job.updated_by, job.workspace_id
        db.info.update(workspace_id=workspace_id, actor_id=actor_id, actor_kind="automation")
        batch = db.get(ImportBatch, job.import_id)
        if batch is None or batch.status != "completed":
            job.status, job.last_error = "failed", "ImportNotCompleted"
            db.commit()
            return True
        job.status = "running"
        job.attempts += 1
        context = job_context(job)
        api_token = secrets.token_urlsafe(32)
        capability_hash = hashlib.sha256(api_token.encode()).hexdigest()
        revoke_job_capabilities(db, job.id)
        db.add(AuthSession(
            token_hash=capability_hash, user_id=actor_id, workspace_id=workspace_id, job_id=job.id,
            expires_at=utcnow() + timedelta(seconds=LEASE_SECONDS),
        ))
        payload = {**context.model_dump(), "api_token": api_token}
        db.commit()

    validated = None
    last_error = None
    try:
        with httpx.Client(timeout=WORKFLOW_TIMEOUT_SECONDS, follow_redirects=False) as client:
            response = client.post(settings.n8n_webhook_url, json=payload)
            response.raise_for_status()
        validated = validate_workflow_result(response.json(), context.year, context.month, context)
    except Exception as error:
        # Persist only the class; never log URLs, headers, bodies or tokens.
        last_error = type(error).__name__

    with Session(engine) as db:
        db.info.update(workspace_id=workspace_id, actor_id=actor_id, actor_kind="automation")
        job = db.scalar(select(AutomationJob).where(AutomationJob.id == context.job_id)
                        .with_for_update().execution_options(populate_existing=True))
        capability = db.get(AuthSession, capability_hash)
        if job is None:
            raise RuntimeError("A tarefa processada não foi encontrada.")
        # A late response must not overwrite the outcome of a newer attempt.
        if job.status == "running" and job.attempts == context.attempt:
            if validated is not None:
                if capability is None or capability.expires_at <= utcnow():
                    last_error = "CapabilityExpired"
                elif validated.model_dump(mode="json") != job.result:
                    # n8n is a courier, not an authority for financial numbers.
                    last_error = "WorkflowResultMismatch"
            job.status = "failed" if last_error else "succeeded"
            job.last_error = last_error
        if capability is not None:
            db.delete(capability)
        db.commit()
        final_status = job.status
    print(f"Tarefa {context.job_id}: {final_status}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20, help="Máximo de tarefas por ciclo.")
    parser.add_argument("--watch", action="store_true", help="Continuar consultando a fila após cada ciclo.")
    parser.add_argument("--poll-seconds", type=int, default=5)
    args = parser.parse_args()
    if args.limit < 1 or not 1 <= args.poll_seconds <= 30:
        parser.error("--limit deve ser positivo e --poll-seconds deve estar entre 1 e 30.")
    processed = 0
    try:
        while True:
            cycle = 0
            while cycle < args.limit and process_one():
                cycle += 1
                processed += 1
            if not args.watch:
                break
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("Worker interrompido; tarefas persistidas serão preservadas.")
    finally:
        engine.dispose()
    print(f"Tarefas processadas: {processed}")


if __name__ == "__main__":
    main()
