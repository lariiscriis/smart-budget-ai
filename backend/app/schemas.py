from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from datetime import date


class CategoryCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=100)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


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


class BudgetRead(BaseModel):
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
    description: str = Field(min_length=1, max_length=255)
    expense_date: date
    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
        allow_inf_nan=False,
    )


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    description: str
    expense_date: date
    amount: Decimal


class FinancialSummary(BaseModel):
    year: int
    month: int
    currency: str
    planned: Decimal
    actual: Decimal
    balance: Decimal
    utilization_percentage: Decimal | None