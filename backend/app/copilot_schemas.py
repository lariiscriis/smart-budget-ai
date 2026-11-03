from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import FinancialSummary


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


class ToolExecution(BaseModel):
    name: str
    arguments: SummaryArguments
    result: FinancialSummary
    categories: list[CategoryBreakdown] = Field(default_factory=list)


class CopilotResponse(BaseModel):
    mode: Literal["mock", "gemini"]
    answer: str
    tools_used: list[ToolExecution]