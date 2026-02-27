# WONTECH Project Status

**Last Updated:** 2026-02-27

> For detailed task tracking, see `/tasks/todo.md`

---

## Architecture

- **Stack**: Flask 3.1.2 + vanilla JS + SQLite (separate DB per tenant)
- **Architecture**: Multi-tenant SaaS — super admin (WONTECH) / org admin / employee tiers
- **Routes**: `app.py` (342 lines) + 18 blueprints across `routes/*.py`
- **Frontend**: Domain-split JS modules (analytics, counts, inventory, invoices, products, settings, reports, utils) + dashboard.js (~800 lines core)
- **Templates**: dashboard.html, dashboard_home.html, pos.html, reports.html, insights.html
- **Database**: `db_manager.py` — canonical schema (33+ tables, 9 views for org; 7 tables for master)

---

## Completed Features

### Core Platform
- Inventory management (ingredients, products, recipes, barcode scanning)
- Sales recording + analytics (13 dashboard widgets, period filters, CSV export)
- Invoice management + reconciliation
- HR / employee management + self-service portal
- Attendance / time tracking (clock in/out, breaks, admin timesheet editing)
- Scheduling (shifts, swaps, conflicts, availability management)
- Payroll (regular/OT/tips calculation, paystubs)
- Time off / PTO (requests, approval, accrual)
- Multi-tenant architecture + auth + role-based permissions
- Theming (10 gradient themes + custom background images)
- Audit logging (full system history)

### POS System (B1-B8 Complete)
- **B1** Order persistence + sales recording — atomic pipeline, 7 tables populated per order
- **B2** Inventory deduction on sale — recipe lookup, auto-deduction, 86'd system with groups
- **B3** Employee assignment + POS auth — employee overlay, session management, void permissions
- **B4** Order lifecycle + status tracking — status transitions, void with inventory reversal
- **B5** Tips → payroll pipeline — tip UI, aggregation endpoint, payroll integration
- **B6** Register management + settlement — open/close/current, multi-register, cash reconciliation
- **B7** Receipt system — print/email/SMS, SendGrid + Twilio infrastructure
- **B8** Customer profiles + history — auto-create on order, phone lookup, customer notes

### Voice AI (D1-D6 Complete)
- OpenAI Realtime API via WebRTC
- 12 read tools (sales, inventory, suppliers, invoices, employees, schedules, attendance, payroll, analytics, POS, menu, ad-hoc SQL)
- 7 write action tools (attendance, schedule, orders, 86, inventory, payroll, menu)
- Full-screen immersive UI with data visualization (5 render patterns)
- Fuzzy name resolution, verbal confirmation enforcement

### AI Integration (F1-F4 Complete)
- **F1** Today's Intelligence — GPT-4o-mini daily insights with rule-based fallback, day-of-week focus rotation, hero card on dashboard home, full insights page
- **F2** KPI Dashboard Strip — 8 business metrics (food cost, gross margin, labor cost, prime cost, avg ticket, rev/labor hr, inventory turnover, invoice cycle) with industry benchmarks, trends, and status indicators
- **F3** Reports & Exports — report registry with data functions, formatters, CSV/PDF export, audit logging
- **F4** MOR Builder — Monthly Operating Report generator (bank statement parsing, exhibit generation, flat PDF rendering via canvas overlays, JSON sidecar for chained generation, template fallback)

### Foundation Repair (A1-A11 Complete)
- **A1** Schema consolidation — db_manager.py single source of truth
- **A2** Route extraction — app.py from 6,921 → 342 lines across 18 blueprints
- **A3** Connection context managers — `master_db()` and `org_db()`
- **A4** Shared function deduplication — utils/auth.py, utils/audit.py
- **A5** Dashboard.js split — 8,343 → ~800 lines, 7 domain modules extracted
- **A6** Shared utils.js — API helpers, toast notifications, formatting
- **A7** Debug artifact removal
- **A8** CSS variable system — dashboard-components.css with design tokens
- **A9** Inline style extraction — moved to CSS classes
- **A10** API response envelope — utils/response.py standardized structure
- **A11** Migration infrastructure — version tracking, schema utilities

### Data (E1-E2 Complete)
- Historical data simulation — 94,992 sales, 372 invoices, 2,916 attendance, 120 payroll records (Jan-Dec 2025)
- Gap fill simulation — 9,099+ sales, 12 invoices, 50 attendance, weekly payroll (Jan 24 - Feb 22, 2026)
- Total: ~135K sales, ~464 invoices, ~3,000 attendance, ~130 payroll records

---

## Not Started

- **F5-F9** Advanced AI — insight history/trends, email/SMS digest, anomaly detection, predictive forecasting, voice ↔ insights integration
- **G1-G4** Meta admin layer — WONTECH's operational dashboard for managing clients + Growth Partners
- **Vertical abstraction** — adapting platform beyond restaurants (not needed until client #2)

---

## Infrastructure

| Service | Purpose | Status |
|---------|---------|--------|
| GitHub | Source control | `github.com/wontech21/wontech` |
| Stripe API | Card payments | Working — keys configured |
| Stripe Terminal | Physical card reader | Stubbed — needs reader hardware |
| Google Maps API | Delivery distance/time | Working |
| SendGrid / SMTP | Email receipts | Scaffolded |
| Twilio | SMS receipts | Scaffolded |
| OpenAI Realtime API | Voice AI | Working |
| OpenAI Chat API | Business insights (GPT-4o-mini) | Working |

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask app entry, blueprint registration |
| `db_manager.py` | Canonical schema, DB creation, context managers |
| `routes/*.py` | 18 route blueprints |
| `middleware/tenant_context_separate_db.py` | Multi-tenant middleware |
| `middleware/feature_gating.py` | Feature flag middleware |
| `utils/converter/` | MOR builder, bank statement parser, merchant normalizer |
| `utils/response.py` | Standardized API envelope |
| `utils/schema.py` | Safe DB migration helpers |
| `utils/report_*.py` | Report registry, data functions, formatters |
| `static/js/dashboard.js` | Core init + navigation (~800 lines) |
| `static/js/*.js` | 8 domain modules (analytics, counts, inventory, etc.) |
| `static/js/voice-ai.js` | Voice AI frontend |
| `templates/pos.html` | POS frontend |
| `templates/dashboard.html` | Admin dashboard |
| `templates/dashboard_home.html` | Home tab — KPIs + insights |
| `templates/reports.html` | Reports + MOR builder |
| `tasks/todo.md` | Master task tracking |
