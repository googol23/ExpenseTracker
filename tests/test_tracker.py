import unittest
import os
import pandas as pd
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from core import ExpenseTracker, calculate_settlements

class TestExpenseTracker(unittest.TestCase):

    def setUp(self):
        """Set up a new in-memory database for each test."""
        self.db_name = ":memory:"
        self.tracker = ExpenseTracker(self.db_name)
        # Suppress print statements during tests
        self.original_print = print
        globals()['print'] = lambda *args, **kwargs: None

    def tearDown(self):
        """Restore print function and remove the temporary database file."""
        globals()['print'] = self.original_print
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_add_member(self):
        self.tracker.add_member("Alice")
        with self.tracker._managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM Member WHERE name = 'Alice'")
            self.assertIsNotNone(cursor.fetchone())

    def test_add_member_duplicate(self):
        self.tracker.add_member("Alice")
        self.tracker.add_member("Alice") # Should not raise an error, just print
        with self.tracker._managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Member WHERE name = 'Alice'")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_add_expense_equal_split_all(self):
        self.tracker.add_member("Alice")
        self.tracker.add_member("Bob")
        self.tracker.add_expense("Lunch", 30.00, "Alice", shares=None)

        balances = self.tracker.get_net_balances()
        alice_balance = balances[balances['name'] == 'Alice']['net_balance'].iloc[0]
        bob_balance = balances[balances['name'] == 'Bob']['net_balance'].iloc[0]

        self.assertAlmostEqual(alice_balance, 15.00) # Paid 30, owed 15
        self.assertAlmostEqual(bob_balance, -15.00) # Paid 0, owed 15

    def test_add_expense_equal_split_subset(self):
        self.tracker.add_member("Alice")
        self.tracker.add_member("Bob")
        self.tracker.add_member("Charlie")
        self.tracker.add_expense("Movie Tickets", 20.00, "Bob", shares=['Alice', 'Bob'])

        balances = self.tracker.get_net_balances()
        alice_balance = balances[balances['name'] == 'Alice']['net_balance'].iloc[0]
        bob_balance = balances[balances['name'] == 'Bob']['net_balance'].iloc[0]
        charlie_balance = balances[balances['name'] == 'Charlie']['net_balance'].iloc[0]

        self.assertAlmostEqual(alice_balance, -10.00)
        self.assertAlmostEqual(bob_balance, 10.00)
        self.assertAlmostEqual(charlie_balance, 0.00)

    def test_add_expense_manual_split(self):
        self.tracker.add_member("Alice")
        self.tracker.add_member("Bob")
        self.tracker.add_expense("Dinner", 100.00, "Alice", shares={'Alice': 40.00, 'Bob': 60.00})

        balances = self.tracker.get_net_balances()
        alice_balance = balances[balances['name'] == 'Alice']['net_balance'].iloc[0]
        bob_balance = balances[balances['name'] == 'Bob']['net_balance'].iloc[0]

        self.assertAlmostEqual(alice_balance, 60.00) # Paid 100, share was 40
        self.assertAlmostEqual(bob_balance, -60.00) # Paid 0, share was 60

    def test_calculate_settlements(self):
        data = {
            'name': ['Alice', 'Bob', 'Charlie'],
            'net_balance': [50, -20, -30]
        }
        balances_df = pd.DataFrame(data)
        settlements = calculate_settlements(balances_df)

        self.assertEqual(len(settlements), 2)

        # The order might vary, so check for presence
        s1 = {'from': 'Charlie', 'to': 'Alice', 'amount': 30.0}
        s2 = {'from': 'Bob', 'to': 'Alice', 'amount': 20.0}

        self.assertIn(s1, settlements)
        self.assertIn(s2, settlements)

    def test_empty_settlements(self):
        data = {
            'name': ['Alice', 'Bob'],
            'net_balance': [0.0, 0.0]
        }
        balances_df = pd.DataFrame(data)
        settlements = calculate_settlements(balances_df)
        self.assertEqual(settlements, [])


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)