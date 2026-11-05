from pydantic import BaseModel, ConfigDict, Field, field_serializer
from decimal import Decimal
from datetime import date, datetime, timezone
from typing import Literal

CategoryType = Literal["income", "expense"]


class AttributionUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str


class RecordMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    workspace_id: int
    created_by: int
    updated_by: int
    created_by_user: AttributionUser
    updated_by_user: AttributionUser
    created_at: datetime
    updated_at: datetime
    attribution_source: str

    @field_serializer("created_at", "updated_at")
    def utc_date(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def record_metadata(record) -> dict:
    return RecordMetadata.model_validate(record).model_dump(mode="json")


class CategoryCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=100)
    type: CategoryType = "expense"


class CategoryRead(RecordMetadata):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: CategoryType


class BudgetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: int = Field(gt=0)
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Field(
        ge=0,
        max_digits=14,
        decimal_places=2,
        allow_inf_nan=False,
    )


class BudgetRead(RecordMetadata):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    year: int
    month: int
    amount: Decimal

class ExpenseCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    category_id: int = Field(gt=0)
    campaign_id: int | None = Field(default=None, gt=0)
    description: str = Field(min_length=1, max_length=255)
    expense_date: date
    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
        allow_inf_nan=False,
    )


class ExpenseRead(RecordMetadata):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    campaign_id: int | None = None
    description: str
    expense_date: date
    amount: Decimal


class CampaignCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class CampaignRead(RecordMetadata):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class IncomeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category_id: int = Field(gt=0)
    campaign_id: int | None = Field(default=None, gt=0)
    description: str = Field(min_length=1, max_length=255)
    income_date: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)


class IncomeRead(RecordMetadata):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    campaign_id: int | None
    description: str
    income_date: date
    amount: Decimal


class FinancialSummary(BaseModel):
    year: int
    month: int
    currency: str
    planned: Decimal
    actual: Decimal
    balance: Decimal
    utilization_percentage: Decimal | None
