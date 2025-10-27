from flask import Flask, request, jsonify, send_from_directory
import os

from core import ExpenseTracker, calculate_settlements

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'expenses.db')

app = Flask(__name__, static_folder='static', static_url_path='/static')


def _with_tracker(func):
    """Helper to create an ExpenseTracker instance per request and ensure it's closed."""
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
    return send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')


@app.route('/api/members', methods=['GET'])
@_with_tracker
def list_members(tracker):
    with tracker._managed_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM Member ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
    return jsonify(names)


@app.route('/api/members', methods=['POST'])
@_with_tracker
def add_member(tracker):
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Missing "name" field'}), 400
    tracker.add_member(name)
    return jsonify({'status': 'ok', 'name': name}), 201


@app.route('/api/expenses', methods=['GET'])
@_with_tracker
def list_expenses(tracker):
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
def create_expense(tracker):
    data = request.get_json() or {}
    description = data.get('description')
    amount = data.get('amount')
    paid_by = data.get('paid_by')
    shares = data.get('shares', None)

    if not description or amount is None or not paid_by:
        return jsonify({'error': 'Missing required fields (description, amount, paid_by)'}), 400

    # Accept shares as null, list, or dict
    try:
        tracker.add_expense(description, float(amount), paid_by, shares)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    return jsonify({'status': 'ok'}), 201


@app.route('/api/balances', methods=['GET'])
@_with_tracker
def get_balances(tracker):
    df = tracker.get_net_balances()
    records = df[['name', 'net_balance']].to_dict('records')
    # Format amounts as numbers
    for r in records:
        r['net_balance'] = float(r['net_balance'])
    return jsonify(records)


@app.route('/api/settlements', methods=['GET'])
@_with_tracker
def get_settlements(tracker):
    df = tracker.get_net_balances()
    settlements = calculate_settlements(df)
    return jsonify(settlements)

