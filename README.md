# ExpenseTracker — Simple Web Frontend

This project contains a small group expense tracker (core logic in `core/expense_tracker.py`).
I added a minimal Flask web server and a single-page frontend to interact with it located under `web/`.

How to run

1. Create a virtual environment and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start the server from the project root:

```bash
python web/app.py
```

3. Open your browser at http://localhost:5000 to use the SPA.

Notes
- The server uses a SQLite DB file at `web/../expenses.db` by default. You can delete it to reset data.
- This is a minimal, local-only UI for quick testing and development.
