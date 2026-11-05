"""Add authentication and explicitly assign all legacy records to one owner.

Revision ID: d4a71b9f0832
Revises: a9c42e7b1603

Required: alembic -x legacy_owner_email=owner@example.com upgrade head
The legacy account is disabled with NO password until activated locally.
"""
from alembic import context, op
import sqlalchemy as sa
from app.auth_schemas import normalize_email

revision = "d4a71b9f0832"
down_revision = "a9c42e7b1603"
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
NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Esta migração exige execução online e proprietário explícito.")
    email = op.get_context().opts.get("legacy_owner_email")
    if email is None:
        email = context.get_x_argument(as_dictionary=True).get("legacy_owner_email", "")
    try:
        email = normalize_email(email)
    except ValueError:
        raise RuntimeError("Informe -x legacy_owner_email=seu-email antes de upgrade head. Nenhum DDL foi executado.")
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Reflect ALL constraints before DDL, including the originally unnamed hash.
    originals = {}
    for table, columns in (("categories", ["name", "type"]), ("campaigns", ["name"]), ("import_batches", ["file_hash"])):
        matches = [item for item in inspector.get_unique_constraints(table) if item["column_names"] == columns]
        if len(matches) != 1:
            raise RuntimeError(f"Unicidade inesperada em {table}; nenhum DDL executado.")
        name = matches[0]["name"]
        if name is None and bind.dialect.name != "sqlite":
            raise RuntimeError(f"Nome da constraint ausente em {table}; nenhum DDL executado.")
        originals[table] = name or f"uq_{table}_{columns[0]}"

    users = op.create_table(
        "users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    bind.execute(users.insert().values(email=email, password_hash=None, active=False))
    owner_id = bind.scalar(sa.select(users.c.id).where(users.c.email == email))

    for table in TABLES:
        op.add_column(table, sa.Column("owner_id", sa.Integer(), nullable=True))
        data = sa.table(table, sa.column("owner_id", sa.Integer()))
        bind.execute(data.update().values(owner_id=owner_id))
        with op.batch_alter_table(table, naming_convention=NAMING) as batch:
            batch.alter_column("owner_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(f"fk_{table}_owner", "users", ["owner_id"], ["id"], ondelete="RESTRICT")
            batch.create_index(f"ix_{table}_owner_id", ["owner_id"])
            if table in originals:
                batch.drop_constraint(originals[table], type_="unique")
                batch.create_unique_constraint(f"uq_{table}_owner_id", ["owner_id", "id"])
                columns = {"categories": ["owner_id", "name", "type"], "campaigns": ["owner_id", "name"], "import_batches": ["owner_id", "file_hash"]}[table]
                name = {"categories": "uq_categories_owner_name_type", "campaigns": "uq_campaigns_owner_name", "import_batches": "uq_import_batches_owner_hash"}[table]
                batch.create_unique_constraint(name, columns)

    for table, column, parent, label in LINKS:
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"fk_{table}_owner_{label}", parent, ["owner_id", column], ["owner_id", "id"])

    op.create_table(
        "auth_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("automation_jobs.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "auth_attempts", sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Reversão automática bloqueada: remover proprietários pode misturar dados de usuários. Restaure um backup validado.")
