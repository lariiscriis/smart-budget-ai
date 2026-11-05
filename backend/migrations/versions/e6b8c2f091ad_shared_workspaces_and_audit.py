"""Move existing financial records to Aurora demo, preserving every row and ID.

Revision ID: e6b8c2f091ad
Revises: d4a71b9f0832
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "e6b8c2f091ad"
down_revision = "d4a71b9f0832"
branch_labels = None
depends_on = None

TABLES = ("categories", "campaigns", "import_batches", "budgets", "expenses", "incomes", "automation_jobs")
LINKS = (
    ("budgets", "category_id", "categories", "category"),
    ("expenses", "category_id", "categories", "category"),
    ("expenses", "campaign_id", "campaigns", "campaign"),
    ("expenses", "import_id", "import_batches", "import"),
    ("incomes", "category_id", "categories", "category"),
    ("incomes", "campaign_id", "campaigns", "campaign"),
    ("automation_jobs", "import_id", "import_batches", "import"),
)
NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "uq": "uq_%(table_name)s_%(column_0_name)s"}


def reflected_name(item, table, kind, dialect):
    if item.get("name"): return item["name"]
    if dialect != "sqlite": raise RuntimeError(f"Constraint sem nome reconhecível em {table}; nenhum DDL executado.")
    # Explicit naming convention for SQLite reflection only. MySQL uses real names.
    if kind == "fk": return f"fk_{table}_{item['constrained_columns'][0]}_{item['referred_table']}"
    return f"uq_{table}_{item['column_names'][0]}"


def rename_conflicts(bind, table_name):
    """Use database collation for comparisons, not Python case-sensitive grouping."""
    columns = [sa.column("id", sa.Integer()), sa.column("name", sa.String(100))]
    if table_name == "categories": columns.append(sa.column("type", sa.String(7)))
    table = sa.table(table_name, *columns)
    keys = [table.c.name] + ([table.c.type] if table_name == "categories" else [])
    conflicts = bind.execute(sa.select(*keys).group_by(*keys).having(sa.func.count() > 1)).all()
    renamed = {}
    for conflict in conflicts:
        criterion = table.c.name == conflict[0]
        if table_name == "categories": criterion = sa.and_(criterion, table.c.type == conflict[1])
        rows = bind.execute(sa.select(table.c.id, table.c.name).where(criterion).order_by(table.c.id)).all()
        for row in rows[1:]:
            counter = 1
            while True:
                suffix = f" [legado {row.id}{'-' + str(counter) if counter > 1 else ''}]"
                candidate = row.name[:100 - len(suffix)] + suffix
                taken = table.c.name == candidate
                if table_name == "categories": taken = sa.and_(taken, table.c.type == conflict[1])
                if bind.scalar(sa.select(sa.func.count()).select_from(table).where(taken)) == 0: break
                counter += 1
            bind.execute(table.update().where(table.c.id == row.id).values(name=candidate))
            renamed[str(row.id)] = {"before": row.name, "after": candidate}
    return renamed


def upgrade():
    if op.get_context().as_sql: raise RuntimeError("Migração de espaços exige introspecção e execução online.")
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if any(name in inspector.get_table_names() for name in ("workspaces", "workspace_memberships", "audit_logs")):
        raise RuntimeError("Tabelas de espaço já existem fora desta revisão; nenhum DDL executado.")
    plan, counts = {}, {}
    for name in TABLES:
        column_info = inspector.get_columns(name)
        columns = {column["name"] for column in column_info}
        if "owner_id" not in columns: raise RuntimeError(f"Esquema anterior inesperado em {name}; nenhum DDL executado.")
        if columns.intersection({"workspace_id", "created_by", "updated_by", "updated_at", "attribution_source", "dedup_key"}):
            raise RuntimeError(f"Colunas novas já existem fora desta revisão em {name}; nenhum DDL executado.")
        unique_rows = inspector.get_unique_constraints(name)
        expected = {"categories": ["owner_id", "name", "type"], "campaigns": ["owner_id", "name"], "import_batches": ["owner_id", "file_hash"]}.get(name)
        if expected and not all(any(row["column_names"] == fields for row in unique_rows) for fields in (expected, ["owner_id", "id"])):
            raise RuntimeError(f"Unicidade anterior inesperada em {name}; nenhum DDL executado.")
        plan[name] = {
            "created_at": "created_at" in columns,
            "created_default": next((column.get("default") for column in column_info if column["name"] == "created_at"), None),
            "fks": [reflected_name(item, name, "fk", bind.dialect.name) for item in inspector.get_foreign_keys(name) if "owner_id" in item["constrained_columns"]],
            "uniques": [reflected_name(item, name, "uq", bind.dialect.name) for item in unique_rows if "owner_id" in item["column_names"]],
            "indexes": [item["name"] for item in inspector.get_indexes(name) if "owner_id" in item["column_names"] and not item.get("unique")],
        }
        counts[name] = bind.scalar(sa.select(sa.func.count()).select_from(sa.table(name)))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    workspaces = op.create_table("workspaces",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False), sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("slug", name="uq_workspaces_slug"))
    bind.execute(workspaces.insert().values(name="Aurora", slug="aurora-demo", is_demo=True, created_at=now))
    workspace_id = bind.scalar(sa.select(workspaces.c.id).where(workspaces.c.slug == "aurora-demo"))
    memberships = op.create_table("workspace_memberships",
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("joined_at", sa.DateTime(), nullable=False))
    users = sa.table("users", sa.column("id", sa.Integer()))
    for user_id in bind.scalars(sa.select(users.c.id)).all():
        bind.execute(memberships.insert().values(workspace_id=workspace_id, user_id=user_id, active=True, joined_at=now))

    for name in TABLES:
        for column in (
            sa.Column("workspace_id", sa.Integer(), nullable=True), sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True), sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("attribution_source", sa.String(20), nullable=True, server_default="recorded"),
        ): op.add_column(name, column)
        if not plan[name]["created_at"]: op.add_column(name, sa.Column("created_at", sa.DateTime(), nullable=True))
        table = sa.table(name, sa.column("owner_id", sa.Integer()), sa.column("workspace_id", sa.Integer()),
                         sa.column("created_by", sa.Integer()), sa.column("updated_by", sa.Integer()),
                         sa.column("updated_at", sa.DateTime()), sa.column("created_at", sa.DateTime()), sa.column("attribution_source", sa.String(20)))
        values = dict(workspace_id=workspace_id, created_by=table.c.owner_id, updated_by=table.c.owner_id, updated_at=now, attribution_source="legacy_owner")
        if not plan[name]["created_at"]: values["created_at"] = now
        bind.execute(table.update().values(**values))

    op.add_column("import_batches", sa.Column("dedup_key", sa.String(64), nullable=True))
    imports = sa.table("import_batches", sa.column("id", sa.String(36)), sa.column("file_hash", sa.String(64)),
                       sa.column("status", sa.String(20)), sa.column("created_at", sa.DateTime()), sa.column("dedup_key", sa.String(64)))
    seen = set()
    for row in bind.execute(sa.select(imports.c.id, imports.c.file_hash).order_by((imports.c.status == "completed").desc(), imports.c.created_at, imports.c.id)).all():
        fingerprint = row.file_hash.lower()
        if fingerprint not in seen:
            bind.execute(imports.update().where(imports.c.id == row.id).values(dedup_key=fingerprint))
            seen.add(fingerprint)
    renames = {name: rename_conflicts(bind, name) for name in ("categories", "campaigns")}

    audit = op.create_table("audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_kind", sa.String(20), nullable=False), sa.Column("action", sa.String(10), nullable=False),
        sa.Column("entity", sa.String(50), nullable=False), sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False), sa.Column("changes", sa.JSON(), nullable=False),
        sa.CheckConstraint("action IN ('create', 'update', 'delete', 'migrate')", name="ck_audit_logs_action"))
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    for name in TABLES:
        id_type = sa.String(36) if name == "import_batches" else sa.Integer()
        table = sa.table(name, sa.column("id", id_type), sa.column("owner_id", sa.Integer()))
        for record in bind.execute(sa.select(table.c.id, table.c.owner_id)).all():
            changes = {"scope": {"before": {"owner_id": record.owner_id}, "after": {"workspace_id": workspace_id}},
                       "attribution_source": {"after": "legacy_owner"}}
            if str(record.id) in renames.get(name, {}): changes["name"] = renames[name][str(record.id)]
            bind.execute(audit.insert().values(workspace_id=workspace_id, actor_id=record.owner_id, actor_kind="migration",
                         action="migrate", entity=name, entity_id=str(record.id), occurred_at=now, changes=changes))

    # Remove child references to owner keys before altering any parent key.
    for name in TABLES:
        with op.batch_alter_table(name, naming_convention=NAMING) as batch:
            for fk in plan[name]["fks"]: batch.drop_constraint(fk, type_="foreignkey")
    for name in TABLES:
        with op.batch_alter_table(name, naming_convention=NAMING) as batch:
            for unique in plan[name]["uniques"]: batch.drop_constraint(unique, type_="unique")
            for index in plan[name]["indexes"]: batch.drop_index(index)
            batch.drop_column("owner_id")
            for column, type_ in (("workspace_id", sa.Integer()), ("created_by", sa.Integer()), ("updated_by", sa.Integer()),
                                   ("created_at", sa.DateTime()), ("updated_at", sa.DateTime()), ("attribution_source", sa.String(20))):
                options = {}
                if column == "attribution_source": options["existing_server_default"] = sa.text("'recorded'")
                elif column == "created_at" and plan[name]["created_default"] is not None:
                    options["existing_server_default"] = sa.text(str(plan[name]["created_default"]))
                batch.alter_column(column, existing_type=type_, nullable=False, **options)
            batch.create_foreign_key(f"fk_{name}_workspace", "workspaces", ["workspace_id"], ["id"], ondelete="RESTRICT")
            batch.create_foreign_key(f"fk_{name}_created_by", "users", ["created_by"], ["id"], ondelete="RESTRICT")
            batch.create_foreign_key(f"fk_{name}_updated_by", "users", ["updated_by"], ["id"], ondelete="RESTRICT")
            batch.create_index(f"ix_{name}_workspace_id", ["workspace_id"])
            if name in ("categories", "campaigns", "import_batches"):
                batch.create_unique_constraint(f"uq_{name}_workspace_id", ["workspace_id", "id"])
                fields = {"categories": ["workspace_id", "name", "type"], "campaigns": ["workspace_id", "name"], "import_batches": ["workspace_id", "dedup_key"]}[name]
                key = {"categories": "uq_categories_workspace_name_type", "campaigns": "uq_campaigns_workspace_name", "import_batches": "uq_import_batches_workspace_dedup"}[name]
                batch.create_unique_constraint(key, fields)
    for name, column, parent, label in LINKS:
        with op.batch_alter_table(name) as batch:
            batch.create_foreign_key(f"fk_{name}_workspace_{label}", parent, ["workspace_id", column], ["workspace_id", "id"])

    op.add_column("auth_sessions", sa.Column("workspace_id", sa.Integer(), nullable=True))
    sessions = sa.table("auth_sessions", sa.column("workspace_id", sa.Integer()))
    bind.execute(sessions.update().values(workspace_id=workspace_id))
    with op.batch_alter_table("auth_sessions") as batch:
        batch.alter_column("workspace_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_auth_sessions_workspace", "workspaces", ["workspace_id"], ["id"], ondelete="RESTRICT")
        batch.create_index("ix_auth_sessions_workspace_id", ["workspace_id"])
    for name, before in counts.items():
        after = bind.scalar(sa.select(sa.func.count()).select_from(sa.table(name)))
        if after != before: raise RuntimeError(f"Contagem de registros alterada em {name}.")


def downgrade():
    raise RuntimeError("Reversão automática bloqueada: o compartilhamento não pode ser dividido sem perder autoria e auditoria. Restaure um backup validado.")
