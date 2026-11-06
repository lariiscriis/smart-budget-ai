"""Versioned, secret-free contract shared by backend, worker and n8n."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.copilot_schemas import CopilotResponse, FinancialAlert
from app.schemas import FinancialSummary


class AutomationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: int = Field(gt=0)
    import_id: str
    workspace_id: int = Field(gt=0)
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    attempt: int = Field(gt=0)
    actor_kind: Literal["automation"] = "automation"


class WorkflowAlerts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int
    month: int
    rules_version: Literal["1.0"] = "1.0"
    count: int
    alerts: list[FinancialAlert]


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["2.0"] = "2.0"
    context: AutomationContext
    summary: FinancialSummary
    alerts: WorkflowAlerts
    analysis: CopilotResponse


def validate_workflow_result(
    data: object, year: int, month: int,
    expected_context: AutomationContext | None = None,
) -> WorkflowResult:
    result = WorkflowResult.model_validate(data)
    if any((item.year, item.month) != (year, month)
           for item in (result.summary, result.alerts, result.context)):
        raise ValueError("O workflow retornou outro período.")
    if expected_context is not None and result.context != expected_context:
        raise ValueError("O workflow retornou outro contexto de automação.")
    if result.alerts.count != len(result.alerts.alerts):
        raise ValueError("A contagem de alertas é inconsistente.")
    tools = result.analysis.tools_used
    if len(tools) != 1:
        raise ValueError("A análise consultiva está ausente.")
    execution = tools[0]
    if (result.analysis.mode != "gemini" or execution.name != "review_budget_policy"
        or getattr(execution.arguments, "focus", None) != "decision"
        or (execution.arguments.year, execution.arguments.month) != (year, month)
        or execution.result != result.summary or execution.alerts != result.alerts.alerts
        or execution.evidence is None):
        raise ValueError("A análise diverge dos agregados ou do contexto esperado.")
    return result
