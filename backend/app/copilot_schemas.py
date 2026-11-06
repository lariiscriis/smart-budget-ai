from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import FinancialSummary
from decimal import Decimal
from datetime import date
from app.dashboard_schemas import CampaignAnalytics, DashboardAnalytics

class SummaryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=2000, le=2100, strict=True)
    month: int = Field(ge=1, le=12, strict=True)


class ReviewArguments(SummaryArguments):
    focus: Literal["budget", "alerts", "decision"] = "budget"


class ExpenseReviewArguments(SummaryArguments):
    expense_id: int | None = Field(default=None, gt=0, strict=True)


class CampaignReviewArguments(SummaryArguments):
    campaign_id: int | None = Field(default=None, gt=0, strict=True)
    campaign_name: str | None = Field(default=None, min_length=1, max_length=100)


class ExpenseEvidence(BaseModel):
    id: int
    category_id: int
    category_name: str
    campaign_id: int | None
    description: str
    expense_date: date
    amount: Decimal


class AnalysisEvidence(BaseModel):
    status: Literal["available", "missing_identifier", "not_found", "ambiguous"] = "available"
    expense: ExpenseEvidence | None = None
    campaign: CampaignAnalytics | None = None
    # Campaign currently has no budget field or campaign budget relation.
    # Never substitute a category budget, a user assertion, or a policy number.
    campaign_limit: Decimal | None = None
    analytics: DashboardAnalytics | None = None
    missing_data: list[str] = Field(default_factory=list)
    alert_policy_sources: dict[str, list[str]] = Field(default_factory=dict)


class CopilotRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    question: str = Field(min_length=1, max_length=2000)
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)

class CategoryBreakdown(BaseModel):
    category_id: int
    category_name: str
    summary: FinancialSummary


class CategoryComparison(BaseModel):
    summary: FinancialSummary
    categories: list[CategoryBreakdown]

class FinancialAlert(BaseModel):
    category_id: int
    category_name: str
    code: Literal["unbudgeted", "over_budget", "near_limit"]
    severity: Literal["warning", "critical"]
    message: str
    planned: Decimal
    actual: Decimal
    balance: Decimal

class PolicySource(BaseModel):
    source_id: str
    document_id: str
    version: str
    section_id: str
    section_title: str
    text: str
    similarity: float


class PolicyAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported: bool
    answer: str = Field(min_length=1)
    source_ids: list[str]


class ToolExecution(BaseModel):
    name: str
    arguments: ExpenseReviewArguments | CampaignReviewArguments | ReviewArguments | SummaryArguments
    result: FinancialSummary | None = None
    categories: list[CategoryBreakdown] = Field(default_factory=list)
    alerts: list[FinancialAlert] = Field(default_factory=list)
    sources: list[PolicySource] = Field(default_factory=list)
    cited_source_ids: list[str] = Field(default_factory=list)
    evidence: AnalysisEvidence | None = None


class CopilotResponse(BaseModel):
    mode: Literal["mock", "gemini"]
    answer: str
    tools_used: list[ToolExecution]
