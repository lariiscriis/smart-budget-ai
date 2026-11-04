from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from sqlalchemy import DateTime, JSON, func

class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "year", "month",
            name="uq_budgets_category_period",
        ),
        CheckConstraint("amount >= 0", name="ck_budgets_amount"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_budgets_month"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="ck_budgets_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_import_batches_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    report: Mapped[dict] = mapped_column(JSON)
    saved_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount"),
    )
    

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    description: Mapped[str] = mapped_column(String(255))
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    
    import_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

class AutomationJob(Base):
    __tablename__ = "automation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "import_id", "year", "month",
            name="uq_automation_jobs_import_period",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_automation_jobs_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT")
    )
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )