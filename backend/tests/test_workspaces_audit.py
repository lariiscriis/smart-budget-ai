import json
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import AuditLog, Category, WorkspaceMembership
from test_financial_entries_api import client, category, entry
from test_auth_security import other_client


def context(client, actor=None):
    return {"workspace_id": client.test_workspace_id, "actor_id": actor or client.test_user_id}


def test_two_members_share_records_and_aggregated_dashboard(client):
    other = other_client(client)
    assert other.get('/auth/me').json()['workspace']['id'] == client.test_workspace_id
    expense = category(client, name='Ingredientes')
    income = category(client, 'income', 'Produtos')
    campaign = client.post('/campaigns', json={'name': 'Natal'}).json()['id']
    assert other.post('/expenses', json=entry(expense, amount='10.50', campaign_id=campaign)).status_code == 201
    assert client.post('/expenses', json=entry(expense, amount='4.50', campaign_id=campaign)).status_code == 201
    assert other.post('/incomes', json=entry(income, 'income', amount='50.00', campaign_id=campaign)).status_code == 201
    assert client.post('/budgets', json={'category_id': expense, 'year': 2026, 'month': 11, 'amount': '100.00'}).status_code == 201
    for path in ['/categories', '/campaigns', '/budgets', '/expenses?year=2026&month=11', '/incomes?year=2026&month=11', '/dashboard/analytics?year=2026&month=11', '/alerts?year=2026&month=11']:
        assert client.get(path).json() == other.get(path).json(), path
    analytics = other.get('/dashboard/analytics?year=2026&month=11').json()
    assert analytics['expense_total'] == '15.00' and analytics['income_total'] == '50.00'
    assert analytics['categories'][0]['actual'] == '15.00'
    assert analytics['campaigns'][0]['expenses'] == '15.00'
    assert analytics['monthly'][-1]['expense_count'] == 2
    rows = other.get('/expenses?year=2026&month=11').json()
    assert {row['created_by_user']['email'] for row in rows} == {'test@example.com', 'other@example.com'}
    assert all(row['workspace_id'] == client.test_workspace_id for row in rows)


def test_members_share_import_idempotency_and_can_confirm_each_others_preview(client):
    other = other_client(client)
    expense = category(client)
    content = f'categoria_id;descricao;data;valor\n{expense};Compartilhada;2026-11-05;10.00\n'.encode()
    first = client.post('/imports/expenses/preview', files={'file': ('shared.csv', content)}).json()
    second = other.post('/imports/expenses/preview', files={'file': ('shared.csv', content)}).json()
    assert first['import_id'] == second['import_id']
    confirmed = other.post(f"/imports/{first['import_id']}/confirm", json={})
    assert confirmed.status_code == 200 and confirmed.json()['saved_count'] == 1
    assert client.post(f"/imports/{first['import_id']}/confirm", json={}).json()['already_completed'] is True
    shared = client.get(f"/imports/{first['import_id']}").json()
    assert shared['created_by_user']['email'] == 'test@example.com'
    assert shared['updated_by_user']['email'] == 'other@example.com'
    assert client.get('/automations').json() == other.get('/automations').json()
    assert len(client.get('/expenses?year=2026&month=11').json()) == 1


def test_revoked_membership_invalidates_existing_session_and_external_workspace_is_hidden(client):
    other = other_client(client)
    user = other.get('/auth/me').json()['user']['id']
    category(client)
    with Session(client.test_engine) as db:
        db.get(WorkspaceMembership, (client.test_workspace_id, user)).active = False
        db.commit()
    assert other.get('/categories').status_code == 401
    assert other.get('/audit').status_code == 401
    assert other.get('/auth/me').status_code == 401


def test_demo_registration_can_be_disabled_and_workspace_cannot_be_supplied(client, monkeypatch):
    from app.config import settings
    payload = {'email': 'new@example.com', 'password': 'Password8!'}
    assert client.post('/auth/register', json={**payload, 'workspace_id': client.test_workspace_id}).status_code == 422
    monkeypatch.setattr(settings, 'demo_registration_enabled', False)
    assert client.post('/auth/register', json=payload).status_code == 403


def test_demo_registration_never_joins_a_real_department(client):
    from app.models import Workspace
    with Session(client.test_engine) as db:
        db.get(Workspace, client.test_workspace_id).is_demo = False
        db.commit()
    assert client.post('/auth/register', json={'email': 'external@example.com', 'password': 'Password8!'}).status_code == 403


def test_audit_tracks_create_update_delete_with_correct_actors_and_old_values(client):
    other = other_client(client)
    actor = other.get('/auth/me').json()['user']['id']
    row = client.post('/categories', json={'name': 'Original'}).json()
    assert row['created_by'] == row['updated_by'] == client.test_user_id
    assert row['created_at'].endswith('Z') and row['updated_at'].endswith('Z')
    with Session(client.test_engine, info=context(client, actor)) as db:
        record = db.get(Category, row['id'])
        record.name = 'Atualizada'
        db.commit()
    changed = other.get('/categories').json()[0]
    assert changed['created_by'] == client.test_user_id and changed['updated_by'] == actor
    assert changed['created_at'] == row['created_at']
    with Session(client.test_engine, info=context(client, actor)) as db:
        db.delete(db.get(Category, row['id']))
        db.commit()
    history = [item for item in client.get('/audit?limit=100').json() if item['entity'] == 'categories' and item['entity_id'] == str(row['id'])]
    assert [item['action'] for item in history] == ['delete', 'update', 'create']
    assert [item['actor_id'] for item in history] == [actor, actor, client.test_user_id]
    assert history[1]['changes']['name'] == {'before': 'Original', 'after': 'Atualizada'}
    assert history[0]['changes']['name'] == {'before': 'Atualizada'}
    assert all(item['occurred_at'].endswith('Z') for item in history)


def test_audit_is_transactional_append_only_scoped_and_excludes_auth_secrets(client):
    category(client)
    original = client.get('/audit?limit=100').json()
    with Session(client.test_engine, info=context(client)) as db:
        db.add(Category(name='Rollback', type='expense'))
        db.flush()
        db.rollback()
    assert client.get('/audit?limit=100').json() == original
    assert client.post('/categories', json={'name': 'Vendas'}).status_code == 409
    assert client.get('/audit?limit=100').json() == original
    with Session(client.test_engine, info=context(client)) as db:
        record = db.scalar(select(AuditLog))
        record.action = 'delete'
        import pytest
        with pytest.raises(RuntimeError, match='append-only'): db.commit()
    outsider = other_client(client, separate_workspace=True)
    assert outsider.get('/audit').json() == []
    serialized = json.dumps(client.get('/audit?limit=100').json())
    for secret in ('password_hash', 'csrf_token', 'token_hash', 'api_token', 'gemini_api_key', 'db_password'):
        assert secret not in serialized


def test_repeated_pending_legacy_import_cannot_duplicate_completed_rows(client):
    from app.models import ImportBatch
    from uuid import uuid4
    expense = category(client)
    content = f'categoria_id;descricao;data;valor\n{expense};Compartilhada;2026-11-05;10.00\n'.encode()
    canonical = client.post('/imports/expenses/preview', files={'file': ('one.csv', content)}).json()
    assert client.post(f"/imports/{canonical['import_id']}/confirm", json={}).status_code == 200
    duplicate_id = str(uuid4())
    with Session(client.test_engine, info=context(client)) as db:
        source = db.get(ImportBatch, canonical['import_id'])
        db.add(ImportBatch(id=duplicate_id, file_hash=source.file_hash, dedup_key=None, filename='legacy.csv', status='pending', report=source.report, saved_count=0))
        db.commit()
    result = client.post(f'/imports/{duplicate_id}/confirm', json={})
    assert result.status_code == 409
    assert canonical['import_id'] in result.json()['detail']
    assert len(client.get('/expenses?year=2026&month=11').json()) == 1
