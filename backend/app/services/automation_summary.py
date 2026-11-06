"""Reuse the copilot's fixed decision analysis, without model tool selection."""
from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.automation_schemas import AutomationContext, WorkflowAlerts, WorkflowResult
from app.config import settings
from app.copilot_schemas import CopilotResponse, ReviewArguments
from app.models import AutomationJob
from app.services.copilot import execute_selected_tool
from app.services.copilot_analysis import render_analysis


def job_context(job: AutomationJob) -> AutomationContext:
    return AutomationContext(
        job_id=job.id, import_id=job.import_id, workspace_id=job.workspace_id,
        year=job.year, month=job.month, attempt=job.attempts,
    )


def build_automation_result(db: Session, job: AutomationJob) -> WorkflowResult:
    if (db.info.get("workspace_id") != job.workspace_id
        or db.info.get("actor_kind") != "automation"
        or db.info.get("automation_job_id") != job.id):
        raise RuntimeError("Contexto de automação inválido.")
    key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
    if settings.ai_mode != "gemini" or not key:
        raise RuntimeError("Configure o RAG para gerar o resumo automático.")
    with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000)) as client:
        execution = execute_selected_tool(
            "review_budget_policy", db,
            ReviewArguments(year=job.year, month=job.month, focus="decision"),
            question=("Prepare resumo financeiro mensal após importação: números do backend, "
                      "políticas pertinentes, dúvidas, riscos e sugestões para revisão humana. "
                      "Não aprovar despesas nem alterar dados financeiros."),
            client=client,
        )
    answer = (
        f"Resumo após a importação {job.import_id}. "
        "Os números abrangem todo o mês no espaço de trabalho, incluindo outros lançamentos; "
        "não são totais exclusivos deste arquivo.\n\n" + render_analysis(execution)
    )
    return WorkflowResult(
        context=job_context(job), summary=execution.result,
        alerts=WorkflowAlerts(year=job.year, month=job.month,
                              count=len(execution.alerts), alerts=execution.alerts),
        analysis=CopilotResponse(mode="gemini", answer=answer, tools_used=[execution]),
    )
