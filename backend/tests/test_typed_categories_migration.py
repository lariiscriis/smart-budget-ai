"""Run the actual revision against an isolated legacy schema, never local MySQL."""
import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from alembic.config import Config


BACKEND = Path(__file__).resolve().parents[1]
PATH = BACKEND / "migrations/versions/a9c42e7b1603_add_typed_categories_campaigns_incomes.py"
spec = importlib.util.spec_from_file_location("typed_categories_migration", PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_revision_is_single_head_with_current_parent():
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == [migration.revision]
    assert scripts.get_revision(migration.revision).down_revision == "5470dd519a0e"


@pytest.fixture
def legacy_connection():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        # Match the unnamed UNIQUE(name) in the original migration.
        legacy = sa.MetaData()
        sa.Table(
            "categories", legacy,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.UniqueConstraint("name"),
        )
        sa.Table(
            "expenses", legacy,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        )
        legacy.create_all(connection)
        connection.execute(sa.text("INSERT INTO categories VALUES (7, 'Embalagens')"))
        connection.execute(sa.text("INSERT INTO expenses VALUES (9, 7, 42.50)"))
        with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            yield connection
    engine.dispose()


def test_upgrade_preserves_legacy_data_and_changes_uniqueness(legacy_connection):
    db = legacy_connection
    migration.upgrade()
    assert db.execute(sa.text("SELECT id, name, type FROM categories")).one() == (7, "Embalagens", "expense")
    assert db.execute(sa.text("SELECT id, category_id, amount, campaign_id FROM expenses")).one() == (9, 7, 42.5, None)
    db.execute(sa.text("INSERT INTO categories (id,name,type) VALUES (8,'Embalagens','income')"))
    with pytest.raises(sa.exc.IntegrityError):
        db.execute(sa.text("INSERT INTO categories (id,name,type) VALUES (10,'Embalagens','expense')"))
    with pytest.raises(sa.exc.IntegrityError):
        db.execute(sa.text("INSERT INTO categories (id,name,type) VALUES (11,'Invalida','other')"))
    with pytest.raises(RuntimeError, match="Downgrade bloqueado"):
        migration.downgrade()
    assert "incomes" in sa.inspect(db).get_table_names()


def test_empty_feature_can_downgrade_without_losing_legacy_data(legacy_connection):
    migration.upgrade()
    migration.downgrade()
    db = legacy_connection
    assert db.execute(sa.text("SELECT id, name FROM categories")).one() == (7, "Embalagens")
    assert db.execute(sa.text("SELECT id, category_id, amount FROM expenses")).one() == (9, 7, 42.5)
    assert "campaigns" not in sa.inspect(db).get_table_names()


def test_mysql_unique_name_is_reflected_and_unknown_schema_aborts_before_ddl():
    operations = Mock()
    operations.get_context.return_value.as_sql = False
    operations.get_bind.return_value.dialect.name = "mysql"
    inspector = Mock()
    inspector.get_unique_constraints.return_value = [{"name": "actual_legacy_index", "column_names": ["name"]}]
    with patch.object(migration, "op", operations), patch.object(migration.sa, "inspect", return_value=inspector):
        assert migration.legacy_name_constraint() == "actual_legacy_index"
        inspector.get_unique_constraints.return_value = []
        with pytest.raises(RuntimeError, match="nenhuma alteração"):
            migration.upgrade()
    operations.batch_alter_table.assert_not_called()
    operations.create_table.assert_not_called()


def test_mysql_upgrade_compiles_using_actual_reflected_index_name():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql", opts={"as_sql": True, "output_buffer": output},
    )
    operations = Mock(wraps=Operations(context))
    # Supply simulated ONLINE reflection; the actual Alembic operations compile
    # MySQL DDL into a buffer. No network or database connection is made.
    operations.get_context.return_value = SimpleNamespace(as_sql=False)
    inspector = Mock()
    inspector.get_unique_constraints.return_value = [
        {"name": "legacy_actual_name", "column_names": ["name"]},
    ]
    with patch.object(migration, "op", operations), patch.object(migration.sa, "inspect", return_value=inspector):
        migration.upgrade()
    sql = output.getvalue()
    assert "DROP INDEX legacy_actual_name" in sql
    assert "UNIQUE (name, type)" in sql
    assert "DEFAULT 'expense'" in sql
    assert "CREATE TABLE incomes" in sql
    assert "fk_expenses_campaign_id" in sql
    assert "DROP TABLE categories" not in sql
    assert "DROP TABLE expenses" not in sql
