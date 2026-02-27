# WONTECH

Business management platform for small and mid-size businesses ($1-10M revenue). Each client gets a customized technical build — AI-powered insights, vertically integrated digital infrastructure, and data management delivered through human consultants ("Growth Partners").

**First client:** Firing Up (pizzeria) — proof of concept with full operational deployment.

## Stack

- **Backend:** Python 3.13, Flask 3.1.2
- **Database:** SQLite (separate DB per tenant)
- **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3
- **AI:** OpenAI GPT-4o-mini (insights), OpenAI Realtime API (voice)
- **Charts:** Chart.js 4.4.0

## Quick Start

```bash
git clone https://github.com/wontech21/wontech.git
cd wontech
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
# → http://localhost:5001
```

## Architecture

```
WONTECH/
├── app.py                          # Flask entry point, blueprint registration
├── db_manager.py                   # Canonical schema, DB creation, context managers
├── middleware/
│   ├── tenant_context_separate_db.py  # Multi-tenant auth + org routing
│   └── feature_gating.py          # Feature flag middleware
├── routes/                         # 18 route blueprints
│   ├── auth_routes.py             # Login, logout, password
│   ├── portal_routes.py           # Page views, navigation
│   ├── pos_routes.py              # POS orders, register, payments
│   ├── attendance_routes.py       # Clock in/out, breaks
│   ├── employee_mgmt_routes.py    # Employee CRUD
│   ├── inventory_app_routes.py    # Ingredients, products, recipes, invoices
│   ├── analytics_app_routes.py    # Widgets, charts, CSV exports
│   ├── insights_routes.py         # AI-powered business insights
│   ├── kpi_routes.py              # 8 real-time business KPIs
│   ├── reports_routes.py          # Report generation + exports
│   ├── converter_routes.py        # MOR builder + file management
│   ├── voice_routes.py            # Voice AI (OpenAI Realtime)
│   ├── share_routes.py            # Email/SMS (SendGrid, Twilio)
│   ├── admin_routes.py            # Super admin operations
│   └── ...
├── utils/
│   ├── converter/                 # MOR builder, bank statement parser
│   ├── report_data_functions.py   # Report data queries
│   ├── report_formatters.py       # CSV/PDF formatters
│   ├── response.py                # Standardized API envelope
│   └── schema.py                  # Safe DB migration helpers
├── static/
│   ├── js/
│   │   ├── dashboard.js           # Core init + navigation
│   │   ├── analytics.js           # Charts, widgets
│   │   ├── inventory.js           # Ingredient management
│   │   ├── products.js            # Product/recipe management
│   │   ├── invoices.js            # Invoice CRUD
│   │   ├── counts.js              # Physical inventory counts
│   │   ├── settings.js            # Settings, theming
│   │   ├── reports.js             # Reports + MOR builder
│   │   ├── voice-ai.js            # Voice AI frontend
│   │   └── utils.js               # Shared API helpers, formatting
│   └── css/
│       ├── style.css              # Main styles
│       ├── dashboard-components.css # Component tokens
│       └── voice-ai.css           # Voice AI immersive UI
├── templates/
│   ├── dashboard.html             # Admin dashboard
│   ├── dashboard_home.html        # Home tab with KPIs + insights
│   ├── pos.html                   # Point of sale terminal
│   ├── reports.html               # Reports + MOR builder
│   ├── insights.html              # Full insights page
│   └── ...
├── databases/                     # Per-tenant SQLite databases
├── migrations/                    # Database migration scripts
└── tasks/todo.md                  # Master task tracking
```

## Features

### Operations
- **Inventory** — ingredients, products, recipes, barcode scanning, supplier management
- **Sales** — POS terminal, order lifecycle, payment processing (cash/card/mobile)
- **Invoices** — upload, reconciliation, cost tracking
- **HR** — employees, scheduling, shift swaps, time off/PTO
- **Attendance** — clock in/out, breaks, admin timesheet editing
- **Payroll** — regular/OT/tips calculation, weekly/monthly periods, paystubs
- **Register** — multi-register support, cash reconciliation, settlement reports
- **Receipts** — print, email (SendGrid), SMS (Twilio)
- **Customers** — auto-created profiles, order history, phone lookup

### Intelligence
- **AI Insights** — GPT-4o-mini daily business analysis with day-of-week focus rotation
- **KPI Dashboard** — 8 metrics (food cost, gross margin, labor cost, prime cost, avg ticket, rev/labor hr, inventory turnover, invoice cycle) with industry benchmarks and trends
- **Voice AI** — OpenAI Realtime API via WebRTC, 12 read tools + 7 write actions, full-screen immersive UI
- **Reports** — configurable report catalog with CSV/PDF export and audit logging

### Tools
- **MOR Builder** — Monthly Operating Report generator for Chapter 11 cases (bank statement parsing, exhibit generation, AcroForm filling, PDF merging)

### Platform
- **Multi-tenant** — separate SQLite DB per organization, super admin / org admin / employee tiers
- **Theming** — 10 gradient themes + custom background images
- **Audit logging** — full system history across all operations

## API

18 blueprints, 250+ routes. Key endpoint groups:

| Prefix | Purpose |
|--------|---------|
| `/api/pos/` | POS orders, register, payments, tips, receipts |
| `/api/inventory/` | Ingredients, products, recipes, counts |
| `/api/invoices/` | Invoice CRUD, reconciliation |
| `/api/analytics/` | Widgets, sales data, CSV exports |
| `/api/insights/` | AI-generated business insights |
| `/api/kpi/` | Real-time business KPIs |
| `/api/reports/` | Report generation + export |
| `/api/converter/` | MOR builder, file history |
| `/api/voice/` | Voice AI sessions + actions |
| `/api/attendance/` | Clock in/out, breaks, timesheets |
| `/api/employees/` | Employee CRUD, scheduling |
| `/api/payroll/` | Payroll calculation, paystubs |

## Data

Firing Up (org_1) has 14 months of operational data:
- ~135K sales records (Jan 2025 - Feb 2026)
- ~460 invoices with line items
- ~3,000 attendance records
- ~130 payroll records across weekly + monthly periods
- 975 ingredient variants, 40+ products with recipes

## License

Private — All rights reserved.
