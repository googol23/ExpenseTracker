/**
 * ExpenseTracker Frontend Application
 *
 * This application manages group expenses by tracking shared costs among participants.
 * It allows users to add participants, record expenses, and shows how to settle balances
 * between group members. The application communicates with a Flask backend API.
 */

/**
 * API endpoint configurations
 * @constant {Object}
 * @property {string} members - Endpoint for participant management
 * @property {string} expenses - Endpoint for expense operations
 * @property {string} balances - Endpoint for balance calculations
 * @property {string} settlements - Endpoint for settlement suggestions
 */
const api = {
    members: '/api/members',
    expenses: '/api/expenses',
    balances: '/api/balances',
    settlements: '/api/settlements'
};

/**
 * Fetches and displays the list of participants
 * Updates both the visible participant list and the autocomplete datalist
 * @async
 * @function fetchMembers
 * @throws {Error} When the API request fails
 * @returns {Promise<void>}
 */
async function fetchMembers() {
    const res = await fetch(api.members);
    const names = await res.json();
    const ul = document.getElementById('member-list');
    ul.innerHTML = '';
    names.forEach(n => {
        const li = document.createElement('li');
        li.textContent = n;
        ul.appendChild(li);
    });
}

/**
 * Fetches and displays the current balance for each participant
 * Shows how much each person owes or is owed
 * @async
 * @function fetchBalances
 * @throws {Error} When the API request fails
 * @returns {Promise<void>}
 */
async function fetchBalances() {
    const res = await fetch(api.balances);
    const data = await res.json();
    const tbody = document.querySelector('#balances-table tbody');
    tbody.innerHTML = '';
    data.forEach(r => {
        const tr = document.createElement('tr');
        const nameTd = document.createElement('td');
        nameTd.textContent = r.name;
        const balTd = document.createElement('td');
        balTd.textContent = `$${r.net_balance.toFixed(2)}`;
        tr.appendChild(nameTd);
        tr.appendChild(balTd);
        tbody.appendChild(tr);
    });
}

/**
 * Fetches and displays all recorded expenses
 * Shows expense details including description, amount, payer, and how it was split
 * @async
 * @function fetchExpenses
 * @throws {Error} When the API request fails
 * @returns {Promise<void>}
 */
async function fetchExpenses() {
    const res = await fetch(api.expenses);
    const data = await res.json();
    const ul = document.getElementById('expenses');
    ul.innerHTML = '';
    data.forEach(e => {
        const li = document.createElement('li');
        li.textContent = `${e.description} — $${e.amount.toFixed(2)} (paid by ${e.paid_by || 'Unknown'})`;
        if (e.splits && e.splits.length) {
            const sub = document.createElement('ul');
            e.splits.forEach(s => {
                const sLi = document.createElement('li');
                sLi.textContent = `${s.member}: $${s.share.toFixed(2)}`;
                sub.appendChild(sLi);
            });
            li.appendChild(sub);
        }
        ul.appendChild(li);
    });
}

/**
 * Event handler for adding a new participant
 * @async
 * @param {Event} e - The form submission event
 */
document.getElementById('add-member-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('member-name').value.trim();
    if (!name) return;

    try {
        const response = await fetch(api.members, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name })
        });

        if (!response.ok) {
            throw new Error('Failed to add participant');
        }

        document.getElementById('member-name').value = '';
        await Promise.all([fetchMembers(), fetchBalances()]);
    } catch (error) {
        alert(`Error adding participant: ${error.message}`);
    }
});

// Refresh balances when the refresh button is clicked
document.getElementById('refresh-balances').addEventListener('click', fetchBalances);

/**
 * Event handler for adding a new expense
 * Handles different types of expense splits:
 * - Equal split among all participants
 * - Equal split among a subset of participants
 * - Manual split with specific amounts
 * @async
 * @param {Event} e - The form submission event
 */
document.getElementById('add-expense-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const description = document.getElementById('expense-desc').value.trim();
    const amount = parseFloat(document.getElementById('expense-amount').value);
    const paid_by = document.getElementById('expense-paid-by').value.trim();
    const method = document.getElementById('split-method').value;
    const splitInput = document.getElementById('split-input').value.trim();

    // Calculate shares based on the selected split method
    let shares = null;
    if (method === 'subset' && splitInput) {
        // Split equally among specified participants
        shares = splitInput.split(',').map(s => s.trim()).filter(Boolean);
    } else if (method === 'manual' && splitInput) {
        // Parse manual share amounts (name:amount pairs)
        shares = {};
        splitInput.split(',').map(p => p.trim()).filter(Boolean).forEach(pair => {
            const [name, val] = pair.split(':').map(x => x.trim());
            shares[name] = parseFloat(val);
        });
    }

    try {
        const response = await fetch(api.expenses, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ description, amount, paid_by, shares })
        });

        if (!response.ok) {
            throw new Error('Failed to add expense');
        }

        // Clear form fields
        document.getElementById('expense-desc').value = '';
        document.getElementById('expense-amount').value = '';
        document.getElementById('expense-paid-by').value = '';
        document.getElementById('split-input').value = '';

        // Refresh displays
        await Promise.all([fetchExpenses(), fetchBalances()]);
    } catch (error) {
        alert(`Error adding expense: ${error.message}`);
    }
});

/**
 * Initialize the application
 * Loads initial data when the page loads:
 * - List of participants
 * - Current balances
 * - Expense history
 */
function initializeApp() {
    Promise.all([
        fetchMembers(),
        fetchBalances(),
        fetchExpenses()
    ]).catch(error => {
        console.error('Failed to initialize application:', error);
        alert('Failed to load initial data. Please refresh the page.');
    });
}

// Initialize the application when the DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}
