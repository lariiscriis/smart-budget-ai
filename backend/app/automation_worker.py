import argparse

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.models import AutomationJob
from app.schemas import FinancialSummary
from app.services.alerts import FinancialAlert


class WorkflowAlerts(BaseModel):
    year: int
    month: int
    rules_version: str
    count: int
    alerts: list[FinancialAlert]


class WorkflowResult(BaseModel):
    summary: FinancialSummary
    alerts: WorkflowAlerts


def validate_workflow_result(
    data: object,
    year: int,
    month: int,
) -> WorkflowResult:
    result = WorkflowResult.model_validate(data)

    if (
        result.summary.year != year
        or result.summary.month != month
        or result.alerts.year != year
        or result.alerts.month != month
    ):
        raise ValueError("O workflow retornou outro período.")

    if result.alerts.count != len(result.alerts.alerts):
        raise ValueError("A contagem de alertas é inconsistente.")

    return result


def process_one() -> bool:
    with Session(engine) as db:
        job = db.scalar(
            select(AutomationJob)
            .where(AutomationJob.status == "pending")
            .order_by(AutomationJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        if job is None:
            return False

        job.status = "running"
        job.attempts += 1

        job_id = job.id
        payload = {
            "job_id": job.id,
            "import_id": job.import_id,
            "year": job.year,
            "month": job.month,
        }

        db.commit()

    result_data = None
    last_error = None

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                settings.n8n_webhook_url,
                json=payload,
            )
            response.raise_for_status()

        validated = validate_workflow_result(
            response.json(),
            payload["year"],
            payload["month"],
        )
        result_data = validated.model_dump(mode="json")
        final_status = "succeeded"

    except (httpx.HTTPError, ValueError) as error:
        final_status = "failed"
        last_error = type(error).__name__

    with Session(engine) as db:
        job = db.get(AutomationJob, job_id)

        if job is None:
            raise RuntimeError("A tarefa processada não foi encontrada.")

        job.status = final_status
        job.result = result_data
        job.last_error = last_error
        db.commit()

    print(f"Tarefa {job_id}: {final_status}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit deve ser maior que zero.")

    processed = 0

    try:
        while processed < args.limit and process_one():
            processed += 1
    finally:
        engine.dispose()

    print(f"Tarefas processadas: {processed}")


if __name__ == "__main__":
    main()