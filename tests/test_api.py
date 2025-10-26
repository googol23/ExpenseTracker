import os
import tempfile
import json

import pytest

from web import app as web_pkg


@pytest.fixture
def client():
    # Create a temporary file to act as the sqlite DB so data persists across requests
    tmp = tempfile.NamedTemporaryFile(prefix='test_expenses_', suffix='.db', delete=False)
    tmp.close()
    db_path = tmp.name

    # Override the DB path used by the app
    web_pkg.DB_PATH = db_path

    # Create a test client
    client = web_pkg.app.test_client()

    yield client

    try:
        os.unlink(db_path)
    except Exception:
        pass


def test_member_and_balance_flow(client):
    # Add two members
    rv = client.post('/api/members', json={'name': 'Alice'})
    assert rv.status_code == 201
    rv = client.post('/api/members', json={'name': 'Bob'})
    assert rv.status_code == 201

    # Add an expense paid by Alice, split equally among both
    rv = client.post('/api/expenses', json={
        'description': 'Lunch',
        'amount': 30.0,
        'paid_by': 'Alice',
        'shares': None
    })
    assert rv.status_code == 201

    # Fetch balances
    rv = client.get('/api/balances')
    assert rv.status_code == 200
    balances = rv.get_json()
    # Convert to dict for easier assertions
    bal_map = {b['name']: float(b['net_balance']) for b in balances}

    # Alice paid 30 and owes 15 -> net +15. Bob owes 15 -> net -15
    assert pytest.approx(bal_map['Alice'], rel=1e-3) == 15.0
    assert pytest.approx(bal_map['Bob'], rel=1e-3) == -15.0


def test_create_expense_with_manual_shares(client):
    client.post('/api/members', json={'name': 'Alice'})
    client.post('/api/members', json={'name': 'Bob'})

    rv = client.post('/api/expenses', json={
        'description': 'Dinner',
        'amount': 100.0,
        'paid_by': 'Bob',
        'shares': {'Alice': 40.0, 'Bob': 60.0}
    })
    assert rv.status_code == 201

    rv = client.get('/api/balances')
    balances = rv.get_json()
    bal_map = {b['name']: float(b['net_balance']) for b in balances}
    assert pytest.approx(bal_map['Bob'], rel=1e-3) == 40.0
    assert pytest.approx(bal_map['Alice'], rel=1e-3) == -40.0
