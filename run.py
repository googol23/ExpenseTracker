from web.app import app

# Allow running from project root: `python web/app.py`
app.run(host='0.0.0.0', port=5000, debug=True)