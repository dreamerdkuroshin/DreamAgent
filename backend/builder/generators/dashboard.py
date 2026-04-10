"""
backend/builder/generators/dashboard.py
Generates a full admin dashboard with charts, sidebar, and dark theme.
"""


def generate(prefs: dict) -> dict:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Admin Dashboard — DreamAgent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --sidebar: #111118; --bg: #0b0b12; --surface: #16161f;
      --surface2: #1e1e2a; --accent: #7c3aed; --accent2: #06b6d4;
      --success: #10b981; --warning: #f59e0b; --danger: #ef4444;
      --text: #e2e2f0; --muted: #7777aa; --border: rgba(255,255,255,0.07);
      --radius: 14px;
    }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text);
      display: flex; min-height: 100vh; }

    /* Sidebar */
    aside {
      width: 240px; min-height: 100vh; background: var(--sidebar);
      border-right: 1px solid var(--border); padding: 1.5rem 1rem;
      display: flex; flex-direction: column; gap: 0.25rem;
      position: sticky; top: 0; height: 100vh; overflow-y: auto;
    }
    .sidebar-brand {
      display: flex; align-items: center; gap: 0.625rem;
      padding: 0.5rem 0.75rem; margin-bottom: 1.5rem;
      font-size: 1.15rem; font-weight: 800; letter-spacing: -0.5px;
    }
    .brand-icon {
      width: 36px; height: 36px; border-radius: 10px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      display: flex; align-items: center; justify-content: center; font-size: 1rem;
    }
    .nav-section { font-size: 0.7rem; font-weight: 700; color: var(--muted);
      letter-spacing: 1px; text-transform: uppercase;
      padding: 1rem 0.75rem 0.4rem; margin-top: 0.25rem; }
    .nav-item {
      display: flex; align-items: center; gap: 0.75rem;
      padding: 0.65rem 0.75rem; border-radius: 10px;
      color: var(--muted); text-decoration: none; font-size: 0.875rem;
      font-weight: 500; cursor: pointer; transition: all 0.2s;
      border: none; background: none; width: 100%; text-align: left;
    }
    .nav-item:hover, .nav-item.active { background: rgba(124,58,237,0.15); color: var(--text); }
    .nav-item.active { color: #a78bfa; }
    .nav-item .icon { font-size: 1rem; width: 20px; text-align: center; }
    .badge-count {
      margin-left: auto; background: var(--accent); color: #fff;
      font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem;
      border-radius: 100px;
    }

    /* Main */
    main { flex: 1; padding: 2rem; overflow-y: auto; }
    .topbar {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 2rem;
    }
    .page-title h1 { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.5px; }
    .page-title p { color: var(--muted); font-size: 0.875rem; margin-top: 0.2rem; }
    .topbar-right { display: flex; align-items: center; gap: 1rem; }
    .search {
      display: flex; align-items: center; gap: 0.5rem;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 0.5rem 1rem;
    }
    .search input { background: none; border: none; color: var(--text);
      font-size: 0.875rem; outline: none; width: 180px; }
    .avatar {
      width: 38px; height: 38px; border-radius: 50%;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 0.875rem; cursor: pointer;
    }

    /* Stat Cards */
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem; margin-bottom: 1.5rem; }
    .stat-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 1.5rem;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .stat-card:hover { transform: translateY(-3px);
      box-shadow: 0 12px 40px rgba(0,0,0,0.2); }
    .stat-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
    .stat-icon { font-size: 1.5rem; }
    .stat-trend {
      display: flex; align-items: center; gap: 0.25rem;
      font-size: 0.78rem; font-weight: 600;
      padding: 0.2rem 0.5rem; border-radius: 6px;
    }
    .trend-up { color: var(--success); background: rgba(16,185,129,0.12); }
    .trend-down { color: var(--danger); background: rgba(239,68,68,0.12); }
    .stat-value { font-size: 2rem; font-weight: 800; letter-spacing: -1px; }
    .stat-label { color: var(--muted); font-size: 0.8rem; margin-top: 0.25rem; }

    /* Charts Row */
    .charts-row { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
    .chart-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 1.5rem;
    }
    .chart-card h3 { font-size: 0.95rem; font-weight: 700; margin-bottom: 1rem; }

    /* Table */
    .table-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 1.5rem;
    }
    .table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
    .table-header h3 { font-size: 0.95rem; font-weight: 700; }
    .table-btn {
      padding: 0.4rem 1rem; border-radius: 8px; background: var(--accent);
      color: #fff; border: none; font-size: 0.8rem; font-weight: 600; cursor: pointer;
    }
    table { width: 100%; border-collapse: collapse; }
    th { text-align: left; font-size: 0.75rem; font-weight: 600; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.5px;
      padding: 0 0.75rem 0.75rem; }
    td { padding: 0.875rem 0.75rem; font-size: 0.875rem;
      border-top: 1px solid var(--border); }
    tr:hover td { background: var(--surface2); }
    .status { display: inline-flex; align-items: center; gap: 0.35rem;
      padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.78rem; font-weight: 600; }
    .status.paid { color: var(--success); background: rgba(16,185,129,0.12); }
    .status.pending { color: var(--warning); background: rgba(245,158,11,0.12); }
    .status.failed { color: var(--danger); background: rgba(239,68,68,0.12); }

    @media(max-width:768px) {
      aside { display: none; }
      .charts-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

  <!-- Sidebar -->
  <aside>
    <div class="sidebar-brand">
      <div class="brand-icon">✦</div>
      DreamAdmin
    </div>
    <span class="nav-section">Main</span>
    <button class="nav-item active" onclick="setActive(this)">
      <span class="icon">📊</span> Dashboard
    </button>
    <button class="nav-item" onclick="setActive(this)">
      <span class="icon">🛒</span> Orders
      <span class="badge-count">24</span>
    </button>
    <button class="nav-item" onclick="setActive(this)">
      <span class="icon">👥</span> Customers
    </button>
    <button class="nav-item" onclick="setActive(this)">
      <span class="icon">📦</span> Products
    </button>
    <span class="nav-section">Analytics</span>
    <button class="nav-item" onclick="setActive(this)">
      <span class="icon">📈</span> Revenue
    </button>
    <button class="nav-item" onclick="setActive(this)">
      <span class="icon">🔍</span> Reports
    </button>
    <span class="nav-section">Settings</span>
    <button class="nav-item" onclick="setActive(this)">
      <span class="icon">⚙️</span> Settings
    </button>
    <button class="nav-item" onclick="setActive(this)">
      <span class="icon">🔐</span> Security
    </button>
  </aside>

  <!-- Main -->
  <main>
    <!-- Topbar -->
    <div class="topbar">
      <div class="page-title">
        <h1>Dashboard</h1>
        <p>Welcome back — here's what's happening today 👋</p>
      </div>
      <div class="topbar-right">
        <div class="search">
          <span>🔍</span>
          <input type="text" placeholder="Search..." />
        </div>
        <div class="avatar">M</div>
      </div>
    </div>

    <!-- Stats -->
    <div class="stats">
      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-icon">💰</span>
          <span class="stat-trend trend-up">↑ 12.5%</span>
        </div>
        <div class="stat-value">$48,295</div>
        <div class="stat-label">Total Revenue</div>
      </div>
      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-icon">🛒</span>
          <span class="stat-trend trend-up">↑ 8.3%</span>
        </div>
        <div class="stat-value">1,284</div>
        <div class="stat-label">Total Orders</div>
      </div>
      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-icon">👥</span>
          <span class="stat-trend trend-up">↑ 22.1%</span>
        </div>
        <div class="stat-value">8,492</div>
        <div class="stat-label">Active Users</div>
      </div>
      <div class="stat-card">
        <div class="stat-header">
          <span class="stat-icon">📦</span>
          <span class="stat-trend trend-down">↓ 2.4%</span>
        </div>
        <div class="stat-value">342</div>
        <div class="stat-label">Products</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="charts-row">
      <div class="chart-card">
        <h3>📈 Revenue Overview</h3>
        <canvas id="revenueChart" height="120"></canvas>
      </div>
      <div class="chart-card">
        <h3>🥧 Traffic Sources</h3>
        <canvas id="donutChart" height="160"></canvas>
      </div>
    </div>

    <!-- Table -->
    <div class="table-card">
      <div class="table-header">
        <h3>Recent Orders</h3>
        <button class="table-btn">View All →</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Order ID</th><th>Customer</th><th>Product</th><th>Amount</th><th>Status</th>
          </tr>
        </thead>
        <tbody id="orders-table"></tbody>
      </table>
    </div>
  </main>

  <script>
    // Nav active state
    function setActive(el) {
      document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
      el.classList.add('active');
    }

    // Revenue Chart
    const ctx1 = document.getElementById('revenueChart').getContext('2d');
    new Chart(ctx1, {
      type: 'line',
      data: {
        labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
        datasets: [{
          label: 'Revenue',
          data: [12000,18000,14000,22000,19000,28000,24000,32000,29000,38000,41000,48000],
          borderColor: '#7c3aed',
          backgroundColor: 'rgba(124,58,237,0.08)',
          tension: 0.4, fill: true,
          borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#7c3aed',
        }]
      },
      options: {
        responsive: true, plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#7777aa', font: { size: 11 } } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#7777aa', font: { size: 11 },
            callback: v => '$' + (v/1000).toFixed(0) + 'k' } }
        }
      }
    });

    // Donut Chart
    const ctx2 = document.getElementById('donutChart').getContext('2d');
    new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: ['Organic', 'Paid', 'Social', 'Direct'],
        datasets: [{ data: [42, 28, 18, 12],
          backgroundColor: ['#7c3aed','#06b6d4','#10b981','#f59e0b'],
          borderWidth: 0, hoverOffset: 6 }]
      },
      options: {
        responsive: true, cutout: '72%',
        plugins: { legend: { position: 'bottom', labels: { color: '#7777aa', font: { size: 11 }, padding: 12 } } }
      }
    });

    // Orders Table
    const ORDERS = [
      { id: '#ORD-0842', customer: 'Alex Johnson', product: 'Pro Headphones', amount: '$89', status: 'paid' },
      { id: '#ORD-0841', customer: 'Maria Garcia', product: 'Smart Watch X', amount: '$149', status: 'paid' },
      { id: '#ORD-0840', customer: 'James Wilson', product: 'GaN Charger', amount: '$39', status: 'pending' },
      { id: '#ORD-0839', customer: 'Sarah Chen', product: 'Laptop Stand', amount: '$59', status: 'paid' },
      { id: '#ORD-0838', customer: 'Mike Davis', product: 'Webcam 4K', amount: '$99', status: 'failed' },
    ];
    document.getElementById('orders-table').innerHTML = ORDERS.map(o => `
      <tr>
        <td style="color:#a78bfa;font-weight:600;">${o.id}</td>
        <td>${o.customer}</td>
        <td style="color:var(--muted);">${o.product}</td>
        <td style="font-weight:700;">${o.amount}</td>
        <td><span class="status ${o.status}">${o.status === 'paid' ? '✓ Paid' : o.status === 'pending' ? '⏳ Pending' : '✗ Failed'}</span></td>
      </tr>
    `).join('');
  </script>
</body>
</html>"""

    return {"index.html": html}
