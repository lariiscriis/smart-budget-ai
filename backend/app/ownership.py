"""Workspace isolation and transactional, allowlisted financial auditing."""
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.models import AuditLog, WorkspaceMembership, WorkspaceRecord, WorkspaceScoped

AUDIT_FIELDS = {
    "categories": ("name", "type"),
    "campaigns": ("name",),
    "budgets": ("category_id", "year", "month", "amount"),
    "expenses": ("category_id", "campaign_id", "description", "expense_date", "amount", "import_id"),
    "incomes": ("category_id", "campaign_id", "description", "income_date", "amount"),
    "import_batches": ("filename", "status", "saved_count"),
    "automation_jobs": ("import_id", "year", "month", "status", "attempts", "last_error"),
}


def json_value(value):
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, (datetime, date)): return value.isoformat()
    return value


@event.listens_for(Session, "do_orm_execute")
def restrict_reads(state):
    workspace_id = state.session.info.get("workspace_id")
    if workspace_id is None and state.session.info.get("http_request"):
        descriptions = getattr(state.statement, "column_descriptions", ())
        owned_query = any(
            isinstance(item.get("entity"), type) and issubclass(item["entity"], WorkspaceScoped)
            for item in descriptions
        )
        if owned_query or not state.is_orm_statement:
            raise RuntimeError("An authenticated workspace is required for financial queries.")
    if workspace_id is not None:
        if not state.is_select:
            raise RuntimeError("Bulk writes are not permitted in an authenticated session.")
        state.statement = state.statement.options(
            with_loader_criteria(WorkspaceScoped, lambda entity: entity.workspace_id == workspace_id, include_aliases=True),
        )


@event.listens_for(Session, "before_flush")
def restrict_writes(session, flush_context, instances):
    workspace_id, actor_id = session.info.get("workspace_id"), session.info.get("actor_id")
    queue = session.info.setdefault("audit_pending", [])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = [obj for obj in session.new | session.dirty | session.deleted if isinstance(obj, WorkspaceRecord)]
    if records:
        if workspace_id is None or actor_id is None:
            raise RuntimeError("An authenticated workspace and actor are required for financial writes.")
        membership = session.get(WorkspaceMembership, (workspace_id, actor_id))
        if membership is None or not membership.active:
            raise RuntimeError("The actor is not an active workspace member.")
    for instance in session.new | session.dirty | session.deleted:
        if isinstance(instance, AuditLog) and (instance in session.dirty or instance in session.deleted):
            raise RuntimeError("Audit history is append-only.")
        if not isinstance(instance, WorkspaceRecord): continue
        is_new, is_deleted = instance in session.new, instance in session.deleted
        state = inspect(instance)
        if is_new and instance.workspace_id is None: instance.workspace_id = workspace_id
        if instance.workspace_id != workspace_id:
            raise RuntimeError("A financial record belongs to another workspace.")
        if not is_new and any(state.attrs[key].history.has_changes() for key in ("workspace_id", "created_by", "created_at", "attribution_source")):
            raise RuntimeError("Workspace and creation attribution are immutable.")
        changes = {}
        for key in AUDIT_FIELDS[instance.__tablename__]:
            history = state.attrs[key].history
            value = getattr(instance, key)
            if is_new: changes[key] = {"after": json_value(value)}
            elif is_deleted: changes[key] = {"before": json_value(value)}
            elif history.has_changes():
                if history.deleted:
                    previous = history.deleted[0]
                else:
                    table = instance.__table__
                    previous = session.connection().scalar(select(table.c[key]).where(
                        table.c.id == instance.id, table.c.workspace_id == workspace_id,
                    ))
                changes[key] = {"before": json_value(previous), "after": json_value(value)}
        if not is_new and not is_deleted and not session.is_modified(instance, include_collections=False): continue
        if is_new:
            instance.created_by, instance.created_at, instance.attribution_source = actor_id, now, "recorded"
        instance.updated_by, instance.updated_at = actor_id, now
        queue.append((instance, "create" if is_new else "delete" if is_deleted else "update", changes,
                      actor_id, workspace_id, session.info.get("actor_kind", "user"), now))


@event.listens_for(Session, "after_flush_postexec")
def append_audit(session, flush_context):
    for obj, action, changes, actor, workspace, kind, now in session.info.pop("audit_pending", []):
        session.add(AuditLog(workspace_id=workspace, actor_id=actor, actor_kind=kind, action=action,
                             entity=obj.__tablename__, entity_id=str(obj.id), occurred_at=now, changes=changes))


@event.listens_for(Session, "after_soft_rollback")
def discard_pending_audit(session, previous_transaction):
    session.info.pop("audit_pending", None)
