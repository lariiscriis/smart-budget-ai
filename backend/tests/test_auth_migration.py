import importlib.util
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models import Base

path = Path(__file__).resolve().parents[1] / "migrations/versions/d4a71b9f0832_add_users_sessions_ownership.py"
spec = importlib.util.spec_from_file_location("auth_migration", path)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def legacy_metadata():
    """Rebuild the previous schema's columns, FKs/checks/uniques from inspected models."""
    metadata = sa.MetaData()
    added = {"workspace_id", "created_by", "updated_by", "updated_at", "attribution_source", "dedup_key"}
    for name in (*migration.TABLES, "policy_embeddings"):
        original = Base.metadata.tables[name]
        table = sa.Table(name, metadata, *[
            sa.Column(col.name, col.type, primary_key=col.primary_key, nullable=col.nullable,
                      server_default=sa.func.now() if col.name == "created_at" else col.server_default)
            for col in original.columns if col.name not in added and (col.name != "created_at" or name in {"import_batches", "automation_jobs", "policy_embeddings"})
        ])
        for constraint in original.constraints:
            if isinstance(constraint, sa.CheckConstraint):
                table.append_constraint(sa.CheckConstraint(str(constraint.sqltext), name=constraint.name))
            elif isinstance(constraint, sa.ForeignKeyConstraint) and not added.intersection(constraint.column_keys):
                table.append_constraint(sa.ForeignKeyConstraint(
                    constraint.column_keys, [element.target_fullname for element in constraint.elements],
                    name=constraint.name, ondelete=constraint.ondelete,
                ))
            elif isinstance(constraint, sa.UniqueConstraint) and not added.intersection(constraint.columns.keys()):
                table.append_constraint(sa.UniqueConstraint(*constraint.columns.keys(), name=constraint.name))
    metadata.tables["categories"].append_constraint(sa.UniqueConstraint("name", "type", name="uq_categories_name_type"))
    metadata.tables["campaigns"].append_constraint(sa.UniqueConstraint("name", name="uq_campaigns_name"))
    metadata.tables["import_batches"].append_constraint(sa.UniqueConstraint("file_hash"))
    return metadata


@pytest.fixture
def legacy():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as db:
        # SQLite's batch table rebuilds require FK enforcement off during DDL;
        # check all FK links explicitly afterwards. Production uses MySQL ALTER.
        metadata = legacy_metadata()
        metadata.create_all(db)
        db.execute(metadata.tables["categories"].insert(), [
            {"id": 10, "name": "Embalagens", "type": "expense"},
            {"id": 11, "name": "Vendas", "type": "income"},
        ])
        db.execute(metadata.tables["campaigns"].insert().values(id=20, name="Natal"))
        db.execute(metadata.tables["import_batches"].insert().values(
            id="legacy-import", file_hash="a" * 64, filename="legacy.csv", status="pending", report={"valid_count": 1}, saved_count=0,
        ))
        db.execute(metadata.tables["budgets"].insert().values(id=30, category_id=10, year=2026, month=11, amount="100.00"))
        db.execute(metadata.tables["expenses"].insert().values(id=40, category_id=10, campaign_id=20, import_id="legacy-import", description="Despesa", expense_date=date(2026, 11, 5), amount="5.00"))
        db.execute(metadata.tables["incomes"].insert().values(id=50, category_id=11, campaign_id=20, description="Receita", income_date=date(2026, 11, 5), amount="20.00"))
        db.execute(metadata.tables["automation_jobs"].insert().values(id=60, import_id="legacy-import", year=2026, month=11, status="pending", attempts=0))
        db.execute(metadata.tables["policy_embeddings"].insert().values(cache_key="b" * 64, chunk_id="c" * 64, model_name="embedding", dimensions=768, vector=[1.0] * 768))
        operations = Operations(MigrationContext.configure(db, opts={"legacy_owner_email": " OWNER@example.com "}))
        with patch.object(migration, "op", operations):
            yield db, operations
    engine.dispose()


def test_owner_migration_preserves_all_records_links_and_shared_policies(legacy):
    db, _ = legacy
    before = {name: db.scalar(sa.text(f"SELECT count(*) FROM {name}")) for name in migration.TABLES}
    migration.upgrade()
    user = db.execute(sa.text("SELECT id,email,password_hash,active FROM users")).one()
    assert user.email == "owner@example.com" and user.password_hash is None and not user.active
    for name, count in before.items():
        assert db.scalar(sa.text(f"SELECT count(*) FROM {name}")) == count
        assert db.scalar(sa.text(f"SELECT count(*) FROM {name} WHERE owner_id=:id"), {"id": user.id}) == count
        assert not next(col for col in sa.inspect(db).get_columns(name) if col["name"] == "owner_id")["nullable"]
    expense = db.execute(sa.text("SELECT id, category_id, campaign_id, import_id, amount FROM expenses")).one()
    assert tuple(expense) == (40, 10, 20, "legacy-import", 5)
    assert db.scalar(sa.text("SELECT amount FROM incomes WHERE id=50")) == 20
    assert db.scalar(sa.text("SELECT count(*) FROM policy_embeddings")) == 1
    assert "owner_id" not in [col["name"] for col in sa.inspect(db).get_columns("policy_embeddings")]
    assert db.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    db.execute(sa.text("INSERT INTO users (email,active) VALUES ('second@example.com',1)"))
    other = db.scalar(sa.text("SELECT id FROM users WHERE email='second@example.com'"))
    db.execute(sa.text("INSERT INTO categories (name,type,owner_id) VALUES ('Embalagens','expense',:owner)"), {"owner": other})
    assert db.scalar(sa.text("SELECT count(*) FROM categories WHERE name='Embalagens'")) == 2
    with pytest.raises(RuntimeError, match="Reversão automática bloqueada"):
        migration.downgrade()


def test_missing_owner_aborts_before_ddl(legacy):
    db, operations = legacy
    operations.get_context().opts["legacy_owner_email"] = ""
    with pytest.raises(RuntimeError, match="Nenhum DDL"):
        migration.upgrade()
    assert "users" not in sa.inspect(db).get_table_names()
    assert "owner_id" not in [col["name"] for col in sa.inspect(db).get_columns("expenses")]


def test_parent_is_previous_head():
    assert migration.down_revision == "a9c42e7b1603"
