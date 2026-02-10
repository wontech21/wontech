# WONTECH — Master Plan

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

## Track D — Voice AI

- [x] **D1. Voice AI core** — OpenAI Realtime API via WebRTC
  - [x] Backend: `routes/voice_routes.py` — ephemeral session creation, 12 function-calling tools (sales, inventory, suppliers, invoices, employees, schedules, attendance, payroll, analytics, POS, menu, ad-hoc SQL)
  - [x] Frontend: `static/js/voice-ai.js` — WebRTC peer connection, data channel message handler, function call routing (ROUTES lookup table), data visualization renderer (5 patterns: SQL tables, ranked lists, array tables, object arrays, flat stats)
  - [x] CSS: `static/css/voice-ai.css` — full-screen immersive dark glass panel, 16-bar glowing waveform, entrance animation, responsive
  - [x] HTML: Voice AI panel + mic button injected into `dashboard.html` and `dashboard_home.html` (admin-only)
  - [x] `app.py` + `routes/__init__.py` — registered voice blueprint

- [x] **D2. Full-screen chat experience** — ChatGPT-style immersive voice mode
  - [x] Panel: `inset: 0`, dark glass background (`rgba(10,10,15,0.95)`), heavy backdrop-blur
  - [x] Waveform: 16 bars, 80px tall, theme-colored glow, symmetrical animation delays
  - [x] Typography: AI response 18px white, user transcript 14px dim italic
  - [x] Data viz: dark-mode glass cards, white values, theme accents, staggered animations
  - [x] Escape key to close, body scroll lock
  - [x] Entrance animation: `translateY(40px) scale(0.95)` → normal, origin bottom-right

- [x] **D3. Data viz polish**
  - [x] HEADER_MAP: 70+ backend keys → polished display labels (prettifyHeader)
  - [x] BADGE_MAP: collection names → human-friendly labels (prettifyBadge)
  - [x] Bigger stat cards (28px values, 150px min-width), ranked list rows (15px), tables (14px, bordered container)
  - [x] Fix: data viz persists when interrupting AI with another voice prompt (only clear text on speech_started, not data)

- [x] **D4. Date awareness + payroll fix**
  - [x] `_get_data_date_ranges()` queries min/max dates from attendance, payroll, sales, invoices
  - [x] DATA AVAILABILITY section injected into system prompt
  - [x] `get_available_years()` fixed to UNION attendance + payroll_history, always includes current + previous year

- [x] **D5. System prompt optimization**
  - [x] Schema whitelist: 22 essential tables (down from 47) — prompt reduced from ~11K to ~6.2K chars
  - [x] Trimmed verbose instructions → concise 2-sentence format
  - [x] `truncateResult()` in JS: caps function call output at 4K chars, slices arrays to 20 items before sending back to Realtime API (full data still renders locally)

- [ ] **D6. Voice AI write actions** — let AI execute functions (clock in, approve PTO, 86 items, etc.)
  - Plan documented in `/docs/VOICE_AI_ACTIONS_PLAN.md`
  - 7 action tools, ~20 action types
  - Verbal confirmation required before every write
  - Centralized `POST /api/voice/action` endpoint

## Track E — Data

- [x] **E1. Historical data simulation** — `scripts/simulate_historical_data.py`
  - [x] 94,992 sales records (Jan 1 - Oct 24, 2025) with seasonality, DOW patterns, 3% monthly growth
  - [x] 372 invoices + 926 line items (Jan 2 - Oct 27, 2025) matching supplier delivery cadences
  - [x] 2,916 attendance records (Jan 1, 2025 - Jan 24, 2026) with department-specific scheduling
  - [x] 120 payroll records (Jan-Dec 2025, 10 employees × 12 months)
  - [x] Employee hire dates backdated to 2024
  - [x] Database backed up before running (`org_1.db.bak`)

## Track A (continued) — Frontend

- [ ] **A5. Split dashboard.js** into domain modules
- [ ] **A6. Create shared utils.js**
- [ ] **A7. Remove debug artifacts**
- [ ] **A8. CSS variable system**
- [ ] **A9. Extract inline styles from HTML**
- [ ] **A10. Standardize API response envelope across all endpoints**
- [ ] **A11. Migration infrastructure with version tracking**
