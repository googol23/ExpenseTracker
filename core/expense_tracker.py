import sqlite3
import pandas as pd
from contextlib import contextmanager

DATABASE_NAME = 'expenses.db'

class ExpenseTracker:
    class Error(Exception):
        """Base exception for this class."""
        pass

    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        # Enable foreign key support for the lifetime of the connection
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.initialize_database()

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()

    @contextmanager
    def _managed_connection(self):
        """A context manager that yields the existing connection and handles transactions."""
        try:
            yield self.conn
        except Exception:
            self.conn.rollback()
            raise

    def initialize_database(self):
        with self._managed_connection() as conn:
            cursor = conn.cursor()
            # Member Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Member (
                    member_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                );
            ''')
            # Expenses Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Expenses (
                    expense_id INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    paid_by_id INTEGER,
                    FOREIGN KEY (paid_by_id) REFERENCES Member(member_id) ON DELETE CASCADE
                );
            ''')
            # Splits Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Splits (
                    split_id INTEGER PRIMARY KEY,
                    expense_id INTEGER,
                    member_id INTEGER,
                    share_amount REAL NOT NULL,
                    FOREIGN KEY (expense_id) REFERENCES Expenses(expense_id) ON DELETE CASCADE,
                    FOREIGN KEY (member_id) REFERENCES Member(member_id) ON DELETE CASCADE
                );
            ''')
            conn.commit()

    def add_member(self, name):
        try:
            with self._managed_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Member (name) VALUES (?)", (name,))
                conn.commit()
                print(f"✅ Added participant: {name}")
        except sqlite3.IntegrityError:
            print(f"⚠️ Participant {name} already exists.")
    
    def _calculate_shares(self, amount: float, cursor: sqlite3.Cursor, shares: dict[str, float] | list[str] | None) -> dict[str, float]:
        """Helper to determine the final share distribution based on the input."""
        if shares is None:
            # Scenario: Equal split among ALL members
            cursor.execute("SELECT name FROM Member")
            all_members = [row[0] for row in cursor.fetchall()]
            if not all_members:
                raise self.Error("No members in the database to split the expense.")

            num_splitters = len(all_members)
            equal_share = amount / num_splitters
            print(f"ℹ️  Splitting ${amount:.2f} equally among all {num_splitters} members (${equal_share:.2f} each).")
            return {name: equal_share for name in all_members}

        if isinstance(shares, list):
            # Scenario: Equal split among a SUBSET of members
            if not shares:
                raise self.Error("The list of participants for the split cannot be empty.")

            num_splitters = len(shares)
            equal_share = amount / num_splitters
            print(f"ℹ️  Splitting ${amount:.2f} equally among {num_splitters} specified members (${equal_share:.2f} each).")
            return {name: equal_share for name in shares}

        if isinstance(shares, dict):
            # Scenario: Manual split with specified amounts
            total_share_amount = sum(shares.values())
            if not abs(total_share_amount - amount) < 0.01: # Use a tolerance for float comparison
                raise self.Error(f"The sum of shares (${total_share_amount:.2f}) does not match the total expense amount (${amount:.2f}).")
            return shares

        raise self.Error("Invalid type for 'shares' argument. Must be a dict, list, or None.")

    def add_expense(self, description: str, amount: float, paid_by_name: str, shares: dict[str, float] | list[str] | None = None):
        with self._managed_connection() as conn:
            cursor = conn.cursor()
            try:
                # --- 1. Calculate shares ---
                final_shares = self._calculate_shares(amount, cursor, shares)

                # --- 2. Get all relevant member IDs in one query ---
                all_names = list(final_shares.keys()) + [paid_by_name]
                placeholders = ','.join('?' for name in all_names)
                cursor.execute(f"SELECT name, member_id FROM Member WHERE name IN ({placeholders})", all_names)
                member_ids = dict(cursor.fetchall())
                
                # Check if all participants exist
                if paid_by_name not in member_ids:
                    raise self.Error(f"Payer '{paid_by_name}' not found.")
                for name in final_shares.keys():
                    if name not in member_ids:
                        raise self.Error(f"Participant '{name}' in shares not found.")
                
                paid_by_id = member_ids[paid_by_name]

                # --- 3. Insert into database within a transaction ---
                cursor.execute("INSERT INTO Expenses (description, amount, paid_by_id) VALUES (?, ?, ?)",
                               (description, amount, paid_by_id))
                expense_id = cursor.lastrowid
                
                splits_to_insert = [
                    (expense_id, member_ids[name], share)
                    for name, share in final_shares.items() if share > 0
                ]
                if splits_to_insert:
                    cursor.executemany("INSERT INTO Splits (expense_id, member_id, share_amount) VALUES (?, ?, ?)",
                                       splits_to_insert)
                
                conn.commit()
                print(f"✅ Expense '{description}' of ${amount:.2f} added successfully.")
            
            except (self.Error, sqlite3.Error) as e:
                # The context manager will handle the rollback
                print(f"❌ {e}")
                # Re-raise or handle as needed, for now we just print

    def get_net_balances(self):
        with self._managed_connection() as conn:
            # 1. Get total paid by each person
            paid_df = pd.read_sql_query("""
                SELECT M.name, COALESCE(SUM(E.amount), 0) AS total_paid
                FROM Member M
                LEFT JOIN Expenses E ON M.member_id = E.paid_by_id
                GROUP BY M.name
            """, conn)
            # 2. Get total owed by each person
            owed_df = pd.read_sql_query("""
                SELECT M.name, COALESCE(SUM(S.share_amount), 0) AS total_owed
                FROM Member M
                LEFT JOIN Splits S ON M.member_id = S.member_id
                GROUP BY M.name
            """, conn)
            # 3. Merge and Calculate Net Balance
            balances_df = pd.merge(paid_df, owed_df, on='name', how='outer').fillna(0)
            balances_df['net_balance'] = balances_df['total_paid'] - balances_df['total_owed']
        return balances_df

def main():
    tracker = ExpenseTracker(DATABASE_NAME)

    print("💰 Group Expense Tracker 💰")

    # Example setup for demonstration
    tracker.add_member("Alice")
    tracker.add_member("Bob")
    tracker.add_member("Charlie")

    # Example expenses
    tracker.add_expense("Groceries", 50.00, "Alice")
    tracker.add_expense("Hotel", 100.00, "Bob")
    print("\n")

    while True:
        print("\n--- Menu ---")
        print("1. View Balances")
        print("2. Add Expense")
        print("3. Add Participant")
        print("4. Exit")
        choice = input("Enter choice (1-4): ")

        if choice == '1':
            balances = tracker.get_net_balances()
            print("\n--- GLOBAL POOL BALANCE ---")
            print("Positive means they are owed (Creditor). Negative means they owe (Debtor).")
            report_df = balances[['name', 'net_balance']].copy()
            report_df['net_balance_formatted'] = report_df['net_balance'].apply(lambda x: f"${x:+.2f}")
            print(report_df[['name', 'net_balance_formatted']].to_string(index=False))

            if not balances.empty:
                settlements = calculate_settlements(balances)
                print("\n--- MINIMAL SETTLEMENTS NEEDED ---")
                if not settlements:
                    print("Everyone is settled up!")
                else:
                    for s in settlements:
                        print(f"💰 {s['from']} pays {s['to']} **${s['amount']:.2f}**")

        elif choice == '2':
            try:
                description = input("Description: ")
                amount = float(input("Total Amount: $"))
                paid_by = input("Paid by (Name): ")

                shares = None
                split_method = input("How to split? (m)anual, (e)qual, (a)ll [default: a]: ").lower()

                if split_method == 'm':
                    # Manual split: dict
                    shares_input = input("Enter shares (e.g., Alice:10.50,Bob:20): ")
                    shares = {}
                    for item in shares_input.split(','):
                        name, share_val = item.split(':')
                        shares[name.strip()] = float(share_val)

                elif split_method == 'e':
                    # Equal split among subset: list
                    shares_input = input("Enter participants for equal split (e.g., Alice,Bob): ")
                    shares = [name.strip() for name in shares_input.split(',')]

                elif split_method == 'a' or not split_method:
                    # Equal split among all: None
                    shares = None

                else:
                    print("Invalid split method. Aborting.")
                    continue

                tracker.add_expense(description, amount, paid_by, shares)

            except (ValueError, ExpenseTracker.Error) as e:
                print(f"❌ Error adding expense: {e}")
            except Exception as e:
                print(f"❌ An unexpected error occurred: {e}")

        elif choice == '3':
            name = input("Enter new participant's name: ")
            tracker.add_member(name)

        elif choice == '4':
            print("Exiting application. Goodbye! 👋")
            break
        else:
            print("Invalid choice. Please try again.")

def calculate_settlements(balances_df):
    if balances_df.empty or balances_df['net_balance'].abs().sum() < 0.01:
        return []

    debtors = balances_df[balances_df['net_balance'] < 0].copy()
    creditors = balances_df[balances_df['net_balance'] > 0].copy()

    debtors['net_balance'] = debtors['net_balance'].abs()

    debtors_list = debtors.sort_values(by='net_balance', ascending=False).to_dict('records')
    creditors_list = creditors.sort_values(by='net_balance', ascending=False).to_dict('records')

    settlements = []

    while debtors_list and creditors_list:
        debtor = debtors_list[0]
        creditor = creditors_list[0]

        settlement_amount = min(debtor['net_balance'], creditor['net_balance'])

        settlements.append({
            'from': debtor['name'],
            'to': creditor['name'],
            'amount': settlement_amount
        })

        debtor['net_balance'] -= settlement_amount
        creditor['net_balance'] -= settlement_amount

        if debtor['net_balance'] < 0.01:
            debtors_list.pop(0)
        if creditor['net_balance'] < 0.01:
            creditors_list.pop(0)

    return settlements

if __name__ == '__main__':
    main()