from decimal import Decimal

import pytest
from sqlalchemy import select

from test_financial_entries_api import client, category, entry  # shared isolated HTTP fixture
from app.models import Campaign


def analytics(client, year=2026, month=11, months=12):
    response = client.get('/dashboard/analytics', params={'year': year, 'month': month, 'months': months})
    assert response.status_code == 200, response.text
    return response.json()


def post(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_empty_dashboard_and_period_bounds(client):
    result = analytics(client)
    assert result['income_total'] == result['expense_total'] == result['cash_balance'] == '0.00'
    assert result['budget_summary']['utilization_percentage'] is None
    assert result['categories'] == result['campaigns'] == []
    assert len(result['monthly']) == 12
    assert (result['monthly'][0]['year'], result['monthly'][0]['month']) == (2025, 12)
    assert all(row['income_count'] == row['expense_count'] == 0 for row in result['monthly'])
    assert len(analytics(client, 2000, 1, 24)['monthly']) == 1


@pytest.mark.parametrize('query', [
    'year=1999&month=11', 'year=2101&month=1', 'year=2026&month=0',
    'year=2026&month=13', 'year=2026&month=11&months=0', 'year=2026&month=11&months=25',
])
def test_invalid_period_rejected(client, query):
    assert client.get(f'/dashboard/analytics?{query}').status_code == 422


def test_monthly_history_dates_decimal_precision_and_old_summary(client):
    expense = category(client, 'expense')
    income = category(client, 'income')
    for day, amount in [('2025-12-01', '0.10'), ('2025-12-31', '0.20'), ('2026-11-30', '7.25'), ('2026-12-01', '99.00'), ('2025-11-30', '99.00')]:
        post(client, '/expenses', entry(expense, expense_date=day, amount=amount))
    for day, amount in [('2025-12-31', '20.00'), ('2026-11-01', '3.00'), ('2026-11-30', '0.50'), ('2026-12-01', '500.00')]:
        post(client, '/incomes', entry(income, 'income', income_date=day, amount=amount))
    result = analytics(client)
    assert result['monthly'][0]['expenses'] == '0.30'
    assert result['monthly'][0]['expense_count'] == 2
    assert result['monthly'][1]['income'] == '0.00'
    assert result['income_total'] == '3.50'
    assert result['expense_total'] == '7.25'
    assert result['cash_balance'] == '-3.75'
    assert result['budget_summary'] == client.get('/dashboard/summary?year=2026&month=11').json()
    assert len(analytics(client, 2026, 11, 6)['monthly']) == 6
    assert analytics(client, 2026, 12, 1)['expense_total'] == '99.00'


def test_budget_and_category_breakdowns_include_missing_sides(client):
    spent = category(client, name='Embalagens')
    unused = category(client, name='Ferramentas')
    unbudgeted = category(client, name='Entregas')
    category(client, 'income', 'Embalagens')  # same name, distinct ID, no expense contribution
    for cat, amount in [(spent, '100.00'), (unused, '20.00')]:
        post(client, '/budgets', {'category_id': cat, 'year': 2026, 'month': 11, 'amount': amount})
    post(client, '/expenses', entry(spent, amount='30.00'))
    post(client, '/expenses', entry(unbudgeted, amount='10.00'))
    result = analytics(client)
    rows = {row['category_id']: row for row in result['categories']}
    assert set(rows) == {spent, unused, unbudgeted}
    assert rows[spent]['expense_share_percentage'] == '75.00'
    assert rows[unused]['actual'] == rows[unused]['expense_share_percentage'] == '0.00'
    assert rows[unbudgeted]['planned'] == '0.00'
    assert rows[unbudgeted]['balance'] == '-10.00'
    assert result['budget_summary']['planned'] == '120.00'
    assert result['budget_summary']['actual'] == '40.00'
    assert [row['category_id'] for row in result['categories']] == [spent, unbudgeted, unused]


def test_campaign_aggregations_avoid_join_multiplication_and_include_unassigned(client):
    income = category(client, 'income')
    expense = category(client)
    campaign = post(client, '/campaigns', {'name': 'Natal'})['id']
    income_only = post(client, '/campaigns', {'name': 'Assinaturas'})['id']
    expense_only = post(client, '/campaigns', {'name': 'Lançamento'})['id']
    post(client, '/campaigns', {'name': 'Sem movimento'})
    for amount in ['10.00', '20.00', '30.00']:
        post(client, '/incomes', entry(income, 'income', amount=amount, campaign_id=campaign))
    for amount in ['3.00', '4.00']:
        post(client, '/expenses', entry(expense, amount=amount, campaign_id=campaign))
    post(client, '/incomes', entry(income, 'income', amount='5.00', campaign_id=income_only))
    post(client, '/expenses', entry(expense, amount='2.00', campaign_id=expense_only))
    post(client, '/incomes', entry(income, 'income', amount='1.00'))
    post(client, '/expenses', entry(expense, amount='0.50'))
    post(client, '/expenses', entry(expense, amount='900.00', campaign_id=campaign, expense_date='2026-12-01'))
    result = analytics(client)
    rows = {row['campaign_id']: row for row in result['campaigns']}
    assert len(rows) == 4
    assert rows[campaign]['income'] == '60.00'
    assert rows[campaign]['expenses'] == '7.00'
    assert rows[campaign]['balance'] == '53.00'
    assert rows[campaign]['income_count'] == 3
    assert rows[campaign]['expense_count'] == 2
    assert rows[income_only]['expenses'] == '0.00'
    assert rows[expense_only]['income'] == '0.00'
    assert rows[None]['campaign_name'] == 'Sem campanha'
    assert rows[None]['balance'] == '0.50'
    assert sum(Decimal(row['income']) for row in rows.values()) == Decimal(result['income_total'])
    assert sum(Decimal(row['expenses']) for row in rows.values()) == Decimal(result['expense_total'])


def test_analytics_are_not_truncated_by_entry_pagination(client):
    from sqlalchemy.orm import Session
    from app.models import Expense
    from datetime import date

    expense = category(client)
    with Session(client.test_engine) as db:
        db.add_all([Expense(category_id=expense, amount=Decimal('0.01'), description='Teste', expense_date=date(2026, 11, 5)) for _ in range(105)])
        db.commit()
        before = list(db.scalars(select(Campaign)).all())
    result = analytics(client)
    assert result['expense_total'] == '1.05'
    assert result['monthly'][-1]['expense_count'] == 105
    with Session(client.test_engine) as db:
        assert list(db.scalars(select(Campaign)).all()) == before
