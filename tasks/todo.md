# WONTECH Refactoring + POS Build — Master Plan

> Started: 2026-02-08
> Reference: `/docs/CODEBASE_AUDIT_2026-02-08.md`, `/docs/POS_BUILD_PLAN.md`

---

## Track A — Foundation Repair

- [x] **A1. Schema consolidation** — db_manager.py becomes single source of truth
  - [x] Audit all 4 schema locations, build canonical schema from the most complete definitions
  - [x] Update db_manager.py with canonical schema (30 tables, 9 views, all indexes for org; 7 tables for master)
  - [x] Remove inline table creation from app.py (create_databases_inline, ensure_database_initialized)
  - [x] Remove/deprecate create_db_inline.py (deleted from scripts/)
  - [x] Remove schema duplication from init_database.py (now delegates to db_manager)
  - [x] Verify org_1.db matches canonical schema (975 ingredients, 30,814 sales — all intact)
  - [x] Test: app starts (222 routes), all features still work

- [x] **A2. Extract routes from app.py** — monolith → blueprints
  - [x] Create routes/auth_routes.py (3 routes: login, logout, change-password)
  - [x] Create routes/portal_routes.py (10 routes: page views, clock, scanner)
  - [x] Create routes/attendance_routes.py (8 routes: clock in/out, breaks, history)
  - [x] Create routes/employee_mgmt_routes.py (6 routes: CRUD + logo upload)
  - [x] Create routes/inventory_app_routes.py (43 routes: ingredients, products, recipes, counts, categories, suppliers, invoices)
  - [x] Create routes/analytics_app_routes.py (46 routes: widgets, analytics data, CSV exports)
  - [x] Create utils/auth.py + utils/audit.py (shared helpers)
  - [x] app.py reduced from 6,921 → 336 lines
  - [x] Test: all 222 routes load correctly across 13 modules

- [x] **A3. Connection context managers** — `master_db()` and `org_db()` context managers added to db_manager.py
  - [x] Context managers auto-close connections on exit (including exceptions)
  - [x] Org path caching already in place (_org_path_cache dict)
  - [x] Backward compatible — existing `get_master_db()`/`get_org_db()` still work
  - [x] Test: verified auto-close behavior, 222 routes intact

- [x] **A4. Deduplicate shared functions** — one copy of everything
  - [x] utils/auth.py canonical `hash_password`/`verify_password` (created in A2)
  - [x] utils/audit.py canonical org-level `log_audit` (created in A2)
  - [x] Replaced inline hashlib in app.py seed function → `from utils.auth import hash_password`
  - [x] Replaced inline hashlib in admin_routes.py → `from utils.auth import hash_password`
  - [x] Removed dead `log_audit` closure from sales_operations.py (defined but never called)
  - [x] Identified sales_tracking.py as dead code (not imported anywhere, uses legacy inventory.db)
  - [x] Test: 222 routes, 7 users, 975 ingredients — all intact

## Track B — POS Build

- [ ] **B1. POS Phase 1 — Order Persistence + Sales Recording**
- [ ] **B2. POS Phase 2 — Inventory Deduction on Sale**
- [ ] **B3. POS Phase 3 — Employee Assignment + POS Auth**
- [ ] **B4. POS Phase 4 — Order Lifecycle + Status Tracking**
- [ ] **B5. POS Phase 5 — Tips → Payroll Pipeline**
- [ ] **B6. POS Phase 6 — Register Management + Settlement**
- [ ] **B7. POS Phase 7 — Receipt System**
- [ ] **B8. POS Phase 8 — Customer Profiles + History**

## Track C — Housekeeping

- [x] **C1. Clean root directory** — move non-core files to proper locations
  - [x] Create /scripts/, /data/test/, /tests/, /logs/ directories
  - [x] Move 33 scripts to /scripts/
  - [x] Move 43 CSV test data files to /data/test/
  - [x] Move 4 SQL schema files to /data/sql/
  - [x] Move 5 test files to /tests/
  - [x] Move 4 log files to /logs/
  - [x] Delete dead files: database.db, data/master.db, data/org_1.db
  - [x] Delete backup files: app.py.backup, dashboard.js.backup, inventory_backup_*.db

- [x] **C2. Update .gitignore** — cleaned duplicates, added backups/, data/test/, proper structure
- [x] **C3. Consolidate documentation** — 54 root .md files organized into docs/ (guides/, deployment/, archive/), 3 stray scripts moved to scripts/

## Track A (continued) — Frontend

- [ ] **A5. Split dashboard.js** into domain modules
- [ ] **A6. Create shared utils.js**
- [ ] **A7. Remove debug artifacts**
- [ ] **A8. CSS variable system**
- [ ] **A9. Extract inline styles from HTML**
- [ ] **A10. Standardize API response envelope across all endpoints**
- [ ] **A11. Migration infrastructure with version tracking**
