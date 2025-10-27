"""
ExpenseTracker Web API

This module provides a REST API for the ExpenseTracker application. It handles:
- Member management (adding/listing participants)
- Expense tracking (adding/listing expenses)
- Balance calculations
- Settlement suggestions

The API uses SQLite for data storage and Flask for HTTP routing.
All responses are in JSON format.

Typical usage example:
    $ python web/app.py

API Endpoints:
    GET  /api/members          - List all participants
    POST /api/members          - Add a new participant
    GET  /api/expenses         - List all expenses with their splits
    POST /api/expenses         - Add a new expense
    GET  /api/balances         - Get current balance for each participant
    GET  /api/settlements      - Get suggested settlement transactions
"""

from flask import Flask, request, jsonify, send_from_directory
from typing import Dict, List, Union, Optional
import os

from core import ExpenseTracker, calculate_settlements

# Configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'expenses.db')

# Flask application initialization
app = Flask(__name__, static_folder='static', static_url_path='/static')


def _with_tracker(func):
    """
    Decorator that manages ExpenseTracker instance lifecycle for each request.

    Creates a new ExpenseTracker instance for each request and ensures proper cleanup
    by closing the database connection after the request is processed, even if an
    error occurs.

    Args:
        func: The route handler function to wrap.

    Returns:
        wrapper: The wrapped function that handles ExpenseTracker lifecycle.

    Example:
        @app.route('/api/members')
        @_with_tracker
        def list_members(tracker):
            # tracker is automatically created and cleaned up
            ...
    """
    def wrapper(*args, **kwargs):
        tracker = ExpenseTracker(DB_PATH)
        try:
            return func(tracker, *args, **kwargs)
        finally:
            tracker.close()
    wrapper.__name__ = func.__name__
    return wrapper


@app.route('/')
def index():
    """
    Serve the main application HTML page.

    Returns:
        Response: The index.html file from the static directory.
    """
    return send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')


@app.route('/api/members', methods=['GET'])
@_with_tracker
def list_members(tracker: ExpenseTracker) -> List[str]:
    """
    Get a list of all participants.

    Args:
        tracker: ExpenseTracker instance (injected by decorator)

    Returns:
        List[str]: A JSON array of participant names, sorted alphabetically.

    Example response:
        ["Alice", "Bob", "Charlie"]
    """
    with tracker._managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM Member ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
    return jsonify(names)


@app.route('/api/members', methods=['POST'])
@_with_tracker
def add_member(tracker: ExpenseTracker):
    """
    Add a new participant to the expense tracking group.

    Args:
        tracker: ExpenseTracker instance (injected by decorator)

    Request Body:
        {
            "name": string  # Name of the participant to add
        }

    Returns:
        tuple: (JSON response, HTTP status code)
            Success: ({"status": "ok", "name": "<name>"}, 201)
            Error: ({"error": "<error message>"}, 400)

    Example request:
        POST /api/members
        {
            "name": "Alice"
        }

    Example response:
        {
            "status": "ok",
            "name": "Alice"
        }
    """
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Missing "name" field'}), 400
    tracker.add_member(name)
    return jsonify({'status': 'ok', 'name': name}), 201


@app.route('/api/expenses', methods=['GET'])
@_with_tracker
def list_expenses(tracker: ExpenseTracker) -> List[Dict]:
    """
    Get a list of all expenses with their splits.

    Args:
        tracker: ExpenseTracker instance (injected by decorator)

    Returns:
        List[Dict]: A JSON array of expense objects, sorted by ID in descending order.
        Each expense object contains:
            - expense_id: int
            - description: str
            - amount: float
            - paid_by: str (name of the payer)
            - splits: List[Dict] (list of share allocations)

    Example response:
        [
            {
                "expense_id": 1,
                "description": "Dinner",
                "amount": 60.00,
                "paid_by": "Alice",
                "splits": [
                    {"member": "Alice", "share": 20.00},
                    {"member": "Bob", "share": 20.00},
                    {"member": "Charlie", "share": 20.00}
                ]
            },
            ...
        ]
    """
    with tracker._managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT expense_id, description, amount, paid_by_id FROM Expenses ORDER BY expense_id DESC")
        expenses = []
        rows = cursor.fetchall()
        # Fetch member id->name map
        cursor.execute("SELECT member_id, name FROM Member")
        id_name = {r[0]: r[1] for r in cursor.fetchall()}

        for expense_id, description, amount, paid_by_id in rows:
            paid_by = id_name.get(paid_by_id)
            # Get splits
            cursor.execute("SELECT member_id, share_amount FROM Splits WHERE expense_id = ?", (expense_id,))
            splits = [{ 'member': id_name.get(m_id), 'share': share } for m_id, share in cursor.fetchall()]
            expenses.append({
                'expense_id': expense_id,
                'description': description,
                'amount': amount,
                'paid_by': paid_by,
                'splits': splits
            })
    return jsonify(expenses)


@app.route('/api/expenses', methods=['POST'])
@_with_tracker
def create_expense(tracker: ExpenseTracker):
    """
    Add a new expense with its splits.

    Args:
        tracker: ExpenseTracker instance (injected by decorator)

    Request Body:
        {
            "description": string,  # Description of the expense
            "amount": float,        # Total amount of the expense
            "paid_by": string,      # Name of the participant who paid
            "shares": null | List[string] | Dict[string, float]  # Optional: How to split the expense
        }

    The shares parameter can be:
        - null: Split equally among all participants
        - List[string]: Split equally among listed participants
        - Dict[string, float]: Split with specific amounts per participant

    Returns:
        tuple: (JSON response, HTTP status code)
            Success: ({"status": "ok"}, 201)
            Error: ({"error": "<error message>"}, 400)

    Example requests:
        1. Equal split among all:
            {
                "description": "Dinner",
                "amount": 60.00,
                "paid_by": "Alice"
            }

        2. Equal split among subset:
            {
                "description": "Movie tickets",
                "amount": 30.00,
                "paid_by": "Bob",
                "shares": ["Alice", "Bob"]
            }

        3. Manual split:
            {
                "description": "Groceries",
                "amount": 100.00,
                "paid_by": "Charlie",
                "shares": {
                    "Alice": 25.00,
                    "Bob": 35.00,
                    "Charlie": 40.00
                }
            }
    """
    data = request.get_json() or {}
    description = data.get('description')
    amount = data.get('amount')
    paid_by = data.get('paid_by')
    shares = data.get('shares', None)

    if not description or amount is None or not paid_by:
        return jsonify({'error': 'Missing required fields (description, amount, paid_by)'}), 400

    try:
        tracker.add_expense(description, float(amount), paid_by, shares)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    return jsonify({'status': 'ok'}), 201


@app.route('/api/balances', methods=['GET'])
@_with_tracker
def get_balances(tracker: ExpenseTracker) -> List[Dict]:
    """
    Get the current balance for each participant.

    A positive balance means the participant is owed money (they paid more than their share).
    A negative balance means the participant owes money (they paid less than their share).

    Args:
        tracker: ExpenseTracker instance (injected by decorator)

    Returns:
        List[Dict]: A JSON array of balance records, each containing:
            - name: str (participant's name)
            - net_balance: float (positive if owed money, negative if owes money)

    Example response:
        [
            {"name": "Alice", "net_balance": 100.00},    # Alice is owed $100
            {"name": "Bob", "net_balance": -50.00},      # Bob owes $50
            {"name": "Charlie", "net_balance": -50.00}   # Charlie owes $50
        ]
    """
    df = tracker.get_net_balances()
    records = df[['name', 'net_balance']].to_dict('records')
    # Format amounts as numbers
    for r in records:
        r['net_balance'] = float(r['net_balance'])
    return jsonify(records)


@app.route('/api/settlements', methods=['GET'])
@_with_tracker
def get_settlements(tracker: ExpenseTracker) -> List[Dict]:
    """
    Get a list of suggested transactions to settle all balances.

    This endpoint calculates the minimum number of transactions needed to settle
    all debts within the group. It looks at the net balances and suggests
    specific transactions between participants to zero out all balances.

    Args:
        tracker: ExpenseTracker instance (injected by decorator)

    Returns:
        List[Dict]: A JSON array of suggested settlements, each containing:
            - from: str (name of participant who should pay)
            - to: str (name of participant who should receive)
            - amount: float (amount to be paid)

    Example response:
        [
            {
                "from": "Bob",
                "to": "Alice",
                "amount": 30.00
            },
            {
                "from": "Charlie",
                "to": "Alice",
                "amount": 20.00
            }
        ]

    Note:
        - An empty list means everyone is settled up
        - The suggested transactions are optimized to minimize the number of transfers
        - The sum of all suggested transfers will resolve all debts in the group
    """
    df = tracker.get_net_balances()
    settlements = calculate_settlements(df)
    return jsonify(settlements)

