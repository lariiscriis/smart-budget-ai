from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Boolean,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr, relationship
from datetime import datetime, timezone
from sqlalchemy import DateTime, JSON, func

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("automation_jobs.id", ondelete="CASCADE"), nullable=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class WorkspaceScoped:
    @declared_attr
    def workspace_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)


class WorkspaceRecord(WorkspaceScoped):
    @declared_attr
    def created_by(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    @declared_attr
    def updated_by(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    @declared_attr
    def created_by_user(cls) -> Mapped[User]:
        return relationship(User, foreign_keys=[cls.created_by], lazy="joined")

    @declared_attr
    def updated_by_user(cls) -> Mapped[User]:
        return relationship(User, foreign_keys=[cls.updated_by], lazy="joined")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    attribution_source: Mapped[str] = mapped_column(String(20), default="recorded", server_default="recorded")


class AuditLog(WorkspaceScoped, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (CheckConstraint("action IN ('create', 'update', 'delete', 'migrate')", name="ck_audit_logs_action"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor: Mapped[User] = relationship(User, lazy="joined")
    actor_kind: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(10))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    changes: Mapped[dict] = mapped_column(JSON)


class Category(WorkspaceRecord, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", "type", name="uq_categories_workspace_name_type"),
        UniqueConstraint("workspace_id", "id", name="uq_categories_workspace_id"),
        CheckConstraint("type IN ('income', 'expense')", name="ck_categories_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(7), default="expense", server_default="expense")


class Campaign(WorkspaceRecord, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_campaigns_workspace_name"),
        UniqueConstraint("workspace_id", "id", name="uq_campaigns_workspace_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Income(WorkspaceRecord, Base):
    __tablename__ = "incomes"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_incomes_amount"),
        ForeignKeyConstraint(["workspace_id", "category_id"], ["categories.workspace_id", "categories.id"], name="fk_incomes_workspace_category"),
        ForeignKeyConstraint(["workspace_id", "campaign_id"], ["campaigns.workspace_id", "campaigns.id"], name="fk_incomes_workspace_campaign"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="RESTRICT"), nullable=True, index=True,
    )
    description: Mapped[str] = mapped_column(String(255))
    income_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class Budget(WorkspaceRecord, Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "year", "month",
            name="uq_budgets_category_period",
        ),
        CheckConstraint("amount >= 0", name="ck_budgets_amount"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_budgets_month"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="ck_budgets_year"),
        ForeignKeyConstraint(["workspace_id", "category_id"], ["categories.workspace_id", "categories.id"], name="fk_budgets_workspace_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

class ImportBatch(WorkspaceRecord, Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("workspace_id", "dedup_key", name="uq_import_batches_workspace_dedup"),
        UniqueConstraint("workspace_id", "id", name="uq_import_batches_workspace_id"),
        CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_import_batches_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64))
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    report: Mapped[dict] = mapped_column(JSON)
    saved_count: Mapped[int] = mapped_column(Integer, default=0)
class Expense(WorkspaceRecord, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount"),
        ForeignKeyConstraint(["workspace_id", "category_id"], ["categories.workspace_id", "categories.id"], name="fk_expenses_workspace_category"),
        ForeignKeyConstraint(["workspace_id", "campaign_id"], ["campaigns.workspace_id", "campaigns.id"], name="fk_expenses_workspace_campaign"),
        ForeignKeyConstraint(["workspace_id", "import_id"], ["import_batches.workspace_id", "import_batches.id"], name="fk_expenses_workspace_import"),
    )
    

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="RESTRICT", name="fk_expenses_campaign_id"),
        nullable=True,
        index=True,
    )
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

class AutomationJob(WorkspaceRecord, Base):
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
        ForeignKeyConstraint(["workspace_id", "import_id"], ["import_batches.workspace_id", "import_batches.id"], name="fk_automation_jobs_workspace_import"),
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
class PolicyEmbedding(Base):
    __tablename__ = "policy_embeddings"

    cache_key: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    chunk_id: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(150))
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
