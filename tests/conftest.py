"""Configure pytest for the ExpenseTracker tests."""
import os
import sys

# Add the project root directory to the Python path for all tests
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)