# WONTECH Project Status

**Last Updated:** 2026-02-17

> For detailed task tracking, see `/tasks/todo.md`
> For POS build details, see `/docs/POS_BUILD_PLAN.md`

---

## Architecture

- **Stack**: Flask 3.1.2 + vanilla JS + SQLite (separate DB per tenant)
- **Architecture**: Multi-tenant SaaS — super admin (WONTECH) / org admin / employee tiers
- **Routes**: `app.py` (342 lines) + 16,700+ lines across `routes/*.py` (13 blueprints)
- **Frontend**: `dashboard.js` (8,343 lines), `dashboard.html` (3,563 lines), `pos.html` (4,606 lines)
- **Database**: `db_manager.py` — canonical schema (30 tables, 9 views for org; 7 tables for master)

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

### Foundation Repair (A1-A4 Complete)
- A1: Schema consolidation — db_manager.py single source of truth
- A2: Route extraction — app.py from 6,921 → 342 lines across 13 blueprints
- A3: Connection context managers — `master_db()` and `org_db()`
- A4: Shared function deduplication — utils/auth.py, utils/audit.py

### Data
- Historical data simulation — 94,992 sales, 372 invoices, 2,916 attendance, 120 payroll records
- Audit log backfill for all simulated data (32,113 entries)

---

## Not Started

- **AI integration** — insights over existing data (core WONTECH differentiator)
- **Meta admin layer** — WONTECH's operational dashboard for managing clients + Growth Partners
- **Vertical abstraction** — adapting platform beyond restaurants (not needed until client #2)
- **Frontend refactoring (A5-A11)** — split dashboard.js, shared utils, CSS variable system, API envelope standardization, migration infrastructure

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

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask app entry, blueprint registration |
| `db_manager.py` | Canonical schema, DB creation, context managers |
| `routes/*.py` | 13 route blueprints (pos, auth, portal, attendance, etc.) |
| `middleware/tenant_context_separate_db.py` | Multi-tenant middleware |
| `sales_operations.py` | Sales pipeline + inventory deduction |
| `templates/pos.html` | POS frontend (4,606 lines) |
| `templates/dashboard.html` | Admin dashboard frontend |
| `static/js/dashboard.js` | Dashboard logic |
| `static/js/voice-ai.js` | Voice AI frontend |
| `tasks/todo.md` | Master task tracking |
