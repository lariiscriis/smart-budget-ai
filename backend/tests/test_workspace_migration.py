import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from test_auth_migration import legacy, migration as owner_migration

path = Path(__file__).resolve().parents[1] / 'migrations/versions/e6b8c2f091ad_shared_workspaces_and_audit.py'
spec = importlib.util.spec_from_file_location('workspace_migration', path)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_migration_preserves_all_ids_amounts_links_sessions_and_handles_collisions(legacy):
    db, operations = legacy
    owner_migration.upgrade()
    metadata = sa.MetaData()
    metadata.reflect(db)
    users = metadata.tables['users']
    first = db.scalar(sa.select(users.c.id))
    second = db.execute(users.insert().values(email='second@example.com', password_hash='unchanged-test-hash', active=True)).inserted_primary_key[0]
    db.execute(metadata.tables['categories'].insert().values(id=12, name='Embalagens', type='expense', owner_id=second))
    db.execute(metadata.tables['campaigns'].insert().values(id=21, name='Natal', owner_id=second))
    db.execute(metadata.tables['import_batches'].insert().values(id='second-import', file_hash='a' * 64, filename='same.csv', status='completed', report={'valid_count': 1}, saved_count=1, owner_id=second))
    db.execute(metadata.tables['budgets'].insert().values(id=31, category_id=12, year=2026, month=11, amount='90.00', owner_id=second))
    db.execute(metadata.tables['expenses'].insert().values(id=41, category_id=12, campaign_id=21, import_id='second-import', description='Preservar', expense_date=__import__('datetime').date(2026, 11, 5), amount='7.00', owner_id=second))
    db.execute(metadata.tables['incomes'].insert().values(id=51, category_id=11, campaign_id=20, description='Receita', income_date=__import__('datetime').date(2026, 11, 5), amount='30.00', owner_id=first))
    db.execute(metadata.tables['automation_jobs'].insert().values(id=61, import_id='second-import', year=2026, month=11, status='succeeded', attempts=1, owner_id=second))
    expires = datetime(2030, 1, 1)
    db.execute(metadata.tables['auth_sessions'].insert().values(token_hash='d' * 64, user_id=second, expires_at=expires))
    before_ids = {name: list(db.scalars(sa.text(f'SELECT id FROM {name} ORDER BY id'))) for name in migration.TABLES}
    before_expenses = db.execute(sa.text('SELECT id,category_id,campaign_id,import_id,amount FROM expenses ORDER BY id')).all()
    before_income = db.scalar(sa.text('SELECT SUM(amount) FROM incomes'))
    before_hash = db.scalar(sa.text('SELECT password_hash FROM users WHERE id=:id'), {'id': second})
    created_default = next(column['default'] for column in sa.inspect(db).get_columns('import_batches') if column['name'] == 'created_at')
    with patch.object(migration, 'op', operations): migration.upgrade()
    workspace = db.execute(sa.text('SELECT id,name,is_demo FROM workspaces')).one()
    assert workspace.name == 'Aurora' and workspace.is_demo
    for name, ids in before_ids.items():
        assert list(db.scalars(sa.text(f'SELECT id FROM {name} ORDER BY id'))) == ids
        assert db.scalar(sa.text(f'SELECT COUNT(*) FROM {name} WHERE workspace_id=:id'), {'id': workspace.id}) == len(ids)
        assert 'owner_id' not in [col['name'] for col in sa.inspect(db).get_columns(name)]
    assert db.execute(sa.text('SELECT id,category_id,campaign_id,import_id,amount FROM expenses ORDER BY id')).all() == before_expenses
    assert db.scalar(sa.text('SELECT SUM(amount) FROM incomes')) == before_income
    assert db.scalar(sa.text('SELECT password_hash FROM users WHERE id=:id'), {'id': second}) == before_hash
    assert next(column['default'] for column in sa.inspect(db).get_columns('import_batches') if column['name'] == 'created_at') == created_default
    assert db.scalar(sa.text('SELECT COUNT(*) FROM workspace_memberships WHERE active=1')) == 2
    assert db.scalar(sa.text('SELECT created_by FROM expenses WHERE id=41')) == second
    assert db.scalar(sa.text('SELECT attribution_source FROM expenses WHERE id=41')) == 'legacy_owner'
    assert db.scalar(sa.text('SELECT name FROM categories WHERE id=10')) == 'Embalagens'
    assert db.scalar(sa.text('SELECT name FROM categories WHERE id=12')) == 'Embalagens [legado 12]'
    assert db.scalar(sa.text('SELECT name FROM campaigns WHERE id=21')) == 'Natal [legado 21]'
    assert db.scalar(sa.text("SELECT dedup_key FROM import_batches WHERE id='second-import'")) == 'a' * 64
    assert db.scalar(sa.text("SELECT dedup_key FROM import_batches WHERE id='legacy-import'")) is None
    assert db.scalar(sa.text('SELECT COUNT(*) FROM audit_logs')) == sum(len(ids) for ids in before_ids.values())
    session = db.execute(sa.text('SELECT token_hash,workspace_id,expires_at FROM auth_sessions')).one()
    assert session.token_hash == 'd' * 64 and session.workspace_id == workspace.id
    assert str(session.expires_at).startswith('2030-01-01')
    assert db.execute(sa.text('PRAGMA foreign_key_check')).all() == []
    assert db.scalar(sa.text('SELECT COUNT(*) FROM policy_embeddings')) == 1
    with patch.object(migration, 'op', operations), pytest.raises(RuntimeError, match='Reversão automática bloqueada'):
        migration.downgrade()


def test_workspace_parent_is_current_auth_head():
    assert migration.down_revision == 'd4a71b9f0832'


def test_unrecognized_old_schema_aborts_before_creating_workspace(legacy):
    db, operations = legacy
    with patch.object(migration, 'op', operations), pytest.raises(RuntimeError, match='nenhum DDL'):
        migration.upgrade()
    assert 'workspaces' not in sa.inspect(db).get_table_names()


def test_name_conflicts_use_database_collation_and_do_not_overwrite_existing_suffixes():
    engine = sa.create_engine('sqlite://')
    with engine.begin() as db:
        table = sa.Table('categories', sa.MetaData(), sa.Column('id', sa.Integer(), primary_key=True),
                         sa.Column('name', sa.String(100, collation='NOCASE')), sa.Column('type', sa.String(7)))
        table.create(db)
        db.execute(table.insert(), [
            {'id': 1, 'name': 'EMBALAGENS', 'type': 'expense'},
            {'id': 2, 'name': 'embalagens', 'type': 'expense'},
            {'id': 3, 'name': 'embalagens [legado 2]', 'type': 'expense'},
        ])
        changes = migration.rename_conflicts(db, 'categories')
        assert changes['2'] == {'before': 'embalagens', 'after': 'embalagens [legado 2-2]'}
        assert db.scalar(sa.select(sa.func.count()).select_from(table)) == 3
        assert db.scalar(sa.select(table.c.name).where(table.c.id == 1)) == 'EMBALAGENS'
        db.execute(sa.text('CREATE UNIQUE INDEX uq_names ON categories (name,type)'))
    engine.dispose()
