from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import FinancialSummary
from decimal import Decimal

class SummaryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=2000, le=2100, strict=True)
    month: int = Field(ge=1, le=12, strict=True)


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
    arguments: SummaryArguments
    result: FinancialSummary | None = None
    categories: list[CategoryBreakdown] = Field(default_factory=list)
    alerts: list[FinancialAlert] = Field(default_factory=list)
    sources: list[PolicySource] = Field(default_factory=list)
    cited_source_ids: list[str] = Field(default_factory=list)


class CopilotResponse(BaseModel):
    mode: Literal["mock", "gemini"]
    answer: str
    tools_used: list[ToolExecution]