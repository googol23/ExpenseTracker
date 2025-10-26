const api = {
  members: '/api/members',
  expenses: '/api/expenses',
  balances: '/api/balances',
  settlements: '/api/settlements'
};

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

document.getElementById('add-member-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('member-name').value.trim();
  if (!name) return;
  await fetch(api.members, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name }) });
  document.getElementById('member-name').value = '';
  await fetchMembers();
  await fetchBalances();
});

document.getElementById('refresh-balances').addEventListener('click', fetchBalances);

document.getElementById('add-expense-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const description = document.getElementById('expense-desc').value.trim();
  const amount = parseFloat(document.getElementById('expense-amount').value);
  const paid_by = document.getElementById('expense-paid-by').value.trim();
  const method = document.getElementById('split-method').value;
  const splitInput = document.getElementById('split-input').value.trim();

  let shares = null;
  if (method === 'subset' && splitInput) {
    shares = splitInput.split(',').map(s => s.trim()).filter(Boolean);
  } else if (method === 'manual' && splitInput) {
    // parse name:amount pairs
    shares = {};
    splitInput.split(',').map(p => p.trim()).filter(Boolean).forEach(pair => {
      const [name, val] = pair.split(':').map(x => x.trim());
      shares[name] = parseFloat(val);
    });
  }

  await fetch(api.expenses, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ description, amount, paid_by, shares })
  });

  document.getElementById('expense-desc').value = '';
  document.getElementById('expense-amount').value = '';
  document.getElementById('expense-paid-by').value = '';
  document.getElementById('split-input').value = '';

  await fetchExpenses();
  await fetchBalances();
});

// Initial load
fetchMembers();
fetchBalances();
fetchExpenses();
