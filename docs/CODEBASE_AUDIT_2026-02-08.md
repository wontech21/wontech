# WONTECH Codebase Audit — 2026-02-08

> Comprehensive inspection of architecture, code quality, organization, and design integrity.
> Every finding is backed by specific files and line numbers.

---

## Executive Summary

WONTECH is a working product with real operational data. The features are genuinely impressive in scope — inventory, HR, payroll, scheduling, analytics, multi-tenant architecture, theming. But it was built fast and it shows. The codebase has grown organically without architectural discipline, and the result is a system that works but can't scale, can't be safely modified, and can't be handed to another developer without a week of orientation.

**By the numbers:**

| Metric | Value | Verdict |
|--------|-------|---------|
| Root directory files | 176 | 72% is clutter |
| app.py | 7,163 lines, 120 routes | Monolith — unmaintainable |
| dashboard.js | 8,342 lines, 227 functions | Monolith — unmaintainable |
| style.css | 8,306 lines, 5 CSS variables | Under-systematized |
| dashboard.html | 3,515 lines, 238 inline styles, 238 inline onclick handlers | Template doing too much |
| pos.html | 3,705 lines, 3,400 lines of embedded CSS | Should be external |
| Database schema definitions | 4 separate locations, inconsistent | No single source of truth |
| Markdown documentation files | 63 in root | Should be 5-8 in root, rest in /docs/ |
| Dead/legacy database files | 5 files, ~48 MB | Weight from pre-multi-tenancy era |
| Duplicate function implementations | log_audit (3x), hash_password (3x), showError (6x), schema creation (4x) | Every duplicate is a future bug |

---

## I. Architecture — The Structural Problems

### 1. The Monolith Problem

**app.py (7,163 lines)** is doing everything:

| Lines | Responsibility | Where It Should Live |
|-------|---------------|---------------------|
| 56-280 | Database creation (230 lines of CREATE TABLE) | `db_manager.py` — single source |
| 285-475 | Before-request middleware, tenant context | `middleware/` — already has this |
| 475-510 | `hash_password()`, `verify_password()` | `utils/auth.py` |
| 517-1687 | Auth, employee management, clock in/out | `routes/employee_routes.py` or `routes/auth_routes.py` |
| 1910-4110 | Inventory CRUD, counts, categories, suppliers | `routes/inventory_routes.py` (doesn't exist) |
| 4159-4375 | Audit log endpoints | `routes/audit_routes.py` (doesn't exist) |
| 4375-7089 | 40+ analytics endpoints (2,700 lines) | `routes/analytics_routes.py` (doesn't exist) |

**Impact:** Every change to any feature risks breaking unrelated features. No developer can hold 7,163 lines in their head. Adding POS backend integration means touching this file, which means risking inventory, payroll, and analytics.

**dashboard.js (8,342 lines, 227 functions)** is the same problem on the frontend:

- 24+ global variables with no encapsulation
- Layers 1-3 explicitly labeled with console.log markers (debug artifacts)
- Pagination logic copy-pasted 5 times (one per table)
- Modal system, form utilities, toast notifications, inventory management, product management, analytics — all in one file
- `testModalSystem()` (86 lines of debug code) still present

### 2. Schema Has No Single Source of Truth

Database tables are defined in **4 independent locations** with **inconsistent schemas**:

| File | Lines | Last Updated | Status |
|------|-------|-------------|--------|
| `app.py` | 56-280 | Feb 8 | **Most minimal** — missing fields like received_date, payment_status, reconciled on invoices |
| `db_manager.py` | 131-377 | Jan 25 | Full schema but uses different column names than others |
| `init_database.py` | 66-382 | Feb 8 | Full schema, matches create_db_inline.py |
| `create_db_inline.py` | 10-174 | Jan 23 | Full schema but not maintained |

**Concrete inconsistency — invoices table:**

| Column | app.py | db_manager.py | init_database.py |
|--------|--------|---------------|-----------------|
| received_date | Missing | Missing | Present |
| payment_status | Missing | Missing (uses "status") | Present |
| reconciled | Missing | Missing | Present |
| due_date | Missing | Present | Missing |
| notes | Missing | Present | Present |

If `app.py`'s `create_databases_inline()` ever runs on an existing org, it would create a truncated schema missing critical fields. This is a data corruption risk.

### 3. No Migration Infrastructure

18 migration files exist but:
- No execution order defined
- No version tracking (no `schema_version` table)
- No way to know which migrations have been applied to which org database
- No rollback capability
- Not integrated into app startup
- Some migrations are superseded by later ones but still present

### 4. Connection Management Is Manual and Fragile

**Zero context managers in the entire codebase.** Every database connection is:

```python
conn = get_org_db()
cursor = conn.cursor()
try:
    # ... work ...
    conn.commit()
except Exception as e:
    conn.rollback()
finally:
    conn.close()  # MISSING IN MANY ROUTES
```

- 93 connections opened in app.py, 153 closed — suggests some error paths leak connections
- `get_org_db()` queries master.db on every call to look up the org's database filename — no caching
- No connection pooling — every request opens a fresh SQLite connection
- `barcode_api.py` uses `ThreadPoolExecutor` with 3 workers hitting SQLite — risk of "database is locked" under load

---

## II. Code Quality — The Craft Problems

### 5. Duplication Is Pervasive

| What | Copies | Files |
|------|--------|-------|
| Database schema creation | 4 | app.py, db_manager.py, init_database.py, create_db_inline.py |
| `log_audit()` | 3 | app.py:475, sales_operations.py:19, middleware (imported) |
| `hash_password()` / `verify_password()` | 3 | app.py:502, create_test_employee.py, migrations/create_master_database.py |
| `showError()` (frontend) | 6 | dashboard.js, attendance.js, employees.js, schedule.js, schedule_admin.js, and fallback patterns |
| `formatDateTime()` / `formatDate()` | 3+ | dashboard.js, schedule.js, others |
| Pagination boilerplate | 5 | dashboard.js — once per table (inventory, products, invoices, unreconciled, history) |
| Theme gradient hardcoded | 5+ | style.css, aesthetic-enhancement.css, pos.html, admin.css, various inline styles |

Every duplicate is a future inconsistency. When you fix a bug in one copy, the other copies still have it.

### 6. Error Handling Is Shallow

**49 bare `except Exception as e:` blocks** in app.py alone. This catches everything — network errors, type errors, actual bugs — and returns a generic 500 with `str(e)`. Problems:

- Can't distinguish user errors from code bugs
- No stack traces recorded anywhere
- No structured logging (uses `print()` statements)
- No log levels, no log files, no persistent error tracking
- Frontend gets unhelpful error messages

### 7. API Response Format Is Inconsistent

Four different response patterns coexist:

```python
# Pattern 1
return jsonify({'success': True, 'message': 'Created'})

# Pattern 2
return jsonify(dict(ingredient))

# Pattern 3
return jsonify({'error': 'Not found'}), 404

# Pattern 4
return jsonify({'success': True, 'count': len(results), 'results': results})
```

Frontend code has to handle all four. No consistent envelope means every new endpoint is a guessing game.

### 8. Security Gaps

**Password hashing uses SHA-256:**
```python
pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
```
SHA-256 is a fast hash — designed for speed, not password storage. Should use bcrypt or argon2 with a work factor.

**Hardcoded default password** in `create_db_inline.py:97`:
```python
password = 'admin123'
```
No forced change on first login.

**Database files committed to git:** `master.db` (contains user credentials), `inventory.db`, `invoices.db` are tracked. Should be in `.gitignore`.

---

## III. Frontend — The Surface Problems

### 9. Inline Everything in HTML

**dashboard.html** — 3,515 lines with:
- **238 inline `style=""` attributes** — hardcoded colors, margins, flexbox layouts
- **238 inline `onclick=""` handlers** — every interactive element uses global function calls
- **1 ARIA attribute** in the entire file — effectively zero accessibility

**pos.html** — 3,705 lines with:
- **3,400+ lines of embedded `<style>` CSS** — an entire stylesheet jammed inside the template
- Should be extracted to `pos.css`

This makes it impossible to maintain visual consistency or implement proper event delegation.

### 10. CSS Variables Are Barely Used

**style.css (8,306 lines)** defines only **5 CSS variables**:
```css
--theme-color-1: #667eea;
--theme-color-2: #764ba2;
--theme-color-1-rgb: 102, 126, 234;
--theme-color-2-rgb: 118, 75, 162;
--theme-gradient: linear-gradient(...);
```

Meanwhile, `#667eea` is hardcoded **28 times** as a literal value. `#764ba2` appears **12+ times** as a literal. The same gradient is copy-pasted in 5+ locations.

**Contrast with employee-portal.css**, which properly defines **49 semantic CSS variables** (`--ep-primary`, `--ep-shadow-md`, `--ep-radius-md`). The employee portal does it right. The main app does it wrong.

### 11. No Module System

All JavaScript is globally scoped. No imports, no exports, no namespacing. Every function in every file is dumped into the global scope. Consequences:

- Can't tree-shake dead code
- Can't test in isolation
- Name collisions are invisible until they break
- `share.js` is the only file that uses an ES6 class (the best-written JS in the codebase)

### 12. Debug Artifacts in Production Code

- **76 console.log statements** in dashboard.js including styled "Layer Complete" banners
- **81 `alert()` calls** mixed with toast notifications — inconsistent user feedback
- **`testModalSystem()` function** — 86 lines of debug code still in dashboard.js
- **`dashboard.js.backup`** — 289KB backup file sitting in static/js/ (use git, not file copies)

---

## IV. Organization — The Housekeeping Problems

### 13. Root Directory Is a Dumping Ground

**176 files in root.** Breakdown:

| Category | Count | Size | Should Be In Root? |
|----------|-------|------|--------------------|
| Core application | 18 | ~400 KB | Yes |
| Essential docs (README, etc.) | 5-8 | ~50 KB | Yes |
| One-off fix/repair scripts | 15 | 123 KB | No → `/scripts/` |
| Data generation scripts | 9 | 129 KB | No → `/scripts/` |
| Test data CSV files | 44 | ~34 KB | No → `/data/test/` |
| Feature/changelog markdown | 54 | 528 KB | No → `/docs/` |
| Legacy database files | 5 | ~48 MB | No → delete or `/data/legacy/` |
| Test scripts | 4 | ~60 KB | No → `/tests/` |
| Backup files | 2 | ~16.4 MB | No → delete (git exists) |
| Log files | 4 | ~35 KB | No → `.gitignore` |

**72% of root directory files don't belong there.**

### 14. Documentation Is Abundant but Chaotic

63 markdown files in root. Many are redundant:

- **Composite Ingredients**: 3 files saying the same thing (FEATURE + GUIDE + INTEGRATION = 30KB)
- **Analytics**: 4 files covering overlapping fixes (EXPORT + UX + COST + WIDGETS = 45KB)
- **Barcode**: 2 files (SUMMARY + GUIDE = 24KB)
- **Layer completions**: 10 files across 4 layers with overlapping test plans, results, and status docs
- **Inventory warnings**: 2 files (SYSTEM + COMPLETE = 23KB)

Could consolidate 54 files into ~12 organized docs under `/docs/`.

### 15. Dead Weight

| Item | Size | Status |
|------|------|--------|
| `inventory.db` | 16 MB | Legacy — pre-multi-tenancy, not used by active code |
| `inventory_backup_20260124_194956.db` | 16 MB | Manual backup — use git |
| `invoices.db` | 228 KB | Legacy — pre-multi-tenancy |
| `database.db` | 0 bytes | Empty file |
| `data/master.db` | 0 bytes | Empty duplicate |
| `data/org_1.db` | 24 KB | Old copy |
| `app.py.backup` | 113 KB | Old backup — use git |
| `dashboard.js.backup` | 289 KB | Old backup — use git |
| 8+ dead database tables | — | Created but never queried (product_transactions, ingredient_clusters, etc.) |

~48 MB of dead weight.

---

## V. What's Actually Good

This isn't all debt. Credit where it's earned:

- **Multi-tenant architecture works.** Separate DB per org with proper isolation is a sound design.
- **Feature depth is real.** Inventory → recipes → invoices → sales → HR → payroll → scheduling → analytics — this is a genuine vertical integration, not a demo.
- **employee-portal.css** is well-written with 49 semantic CSS variables. It's the template for how the rest of the CSS should work.
- **share.js** uses ES6 classes properly — it's the model for frontend modularity.
- **inventory_warnings.py** is clean, focused, single-responsibility. 5 functions that do one thing well.
- **barcode_api.py** handles rate limiting and multi-source fallback properly.
- **Blueprint route files** (admin_routes, employee_routes, schedule_routes, payroll_routes) are a correct architectural pattern — app.py just hasn't finished migrating into them.
- **Audit logging concept** is right — tracking every action with timestamps. Implementation just needs consolidation (3 copies → 1).

---

## VI. Priority Action Plan

### Tier 1 — Structural Risk (fix before building new features)

| # | Action | Why | Impact |
|---|--------|-----|--------|
| 1 | **Consolidate schema to single source** — `db_manager.py` becomes the authority. Remove table creation from app.py, init_database.py, create_db_inline.py | 4 inconsistent schemas = data corruption risk | Prevents future schema drift |
| 2 | **Disable `create_databases_inline()` in app.py** | If this runs, it creates truncated tables missing critical columns | Prevents data loss |
| 3 | **Add `.gitignore` entries** for *.db, *.log, *.backup, *.csv test data | Database files with credentials are in git | Security |
| 4 | **Upgrade password hashing** from SHA-256 to bcrypt/argon2 | SHA-256 is inappropriate for passwords | Security |

### Tier 2 — Maintainability (do before POS build)

| # | Action | Why | Impact |
|---|--------|-----|--------|
| 5 | **Extract routes from app.py** into `routes/inventory_routes.py`, `routes/analytics_routes.py`, `routes/auth_routes.py` | 7,163-line monolith is unmaintainable; POS integration touches this file | Unblocks safe development |
| 6 | **Deduplicate shared functions** — single `log_audit()`, single `hash_password()`, single `showError()` | 3-6 copies of each function | Prevents inconsistent behavior |
| 7 | **Add connection context managers** — replace manual open/close with `with` pattern | Connection leaks under error conditions | Reliability |
| 8 | **Standardize API response envelope** — every endpoint returns `{success, data, error, meta}` | 4 different response formats | Frontend consistency |

### Tier 3 — Organization (do alongside Tier 2)

| # | Action | Why | Impact |
|---|--------|-----|--------|
| 9 | **Clean root directory** — move scripts to `/scripts/`, CSVs to `/data/test/`, docs to `/docs/` | 176 files, 72% clutter | Professional codebase |
| 10 | **Delete dead weight** — legacy .db files, .backup files, empty databases | 48 MB of unused files | Clean repo |
| 11 | **Consolidate documentation** — 54 root markdown files → ~12 organized docs in `/docs/` | Redundant docs (3 files for composite ingredients alone) | Navigable knowledge base |
| 12 | **Delete dead database tables** — product_transactions, ingredient_clusters, etc. | Created but never queried | Clean schema |

### Tier 4 — Frontend Quality (do during/after POS build)

| # | Action | Why | Impact |
|---|--------|-----|--------|
| 13 | **Split dashboard.js** into domain modules (core-ui, inventory, products, analytics) | 8,342-line monolith with 227 global functions | Maintainable frontend |
| 14 | **Create shared utils.js** — formatDateTime, showError, pagination generics | Same functions duplicated in 6 files | DRY frontend |
| 15 | **Extract inline styles from HTML** — 238 instances in dashboard.html | Defeats purpose of stylesheets | Maintainable styling |
| 16 | **Extract pos.html embedded CSS** — 3,400 lines of `<style>` → pos.css | Giant inline stylesheet | Proper separation |
| 17 | **Expand CSS variables** — follow employee-portal.css pattern (49 vars) for main style.css (currently 5 vars) | #667eea hardcoded 28 times blocks theming | Design system foundation |
| 18 | **Remove debug artifacts** — 76 console.logs, testModalSystem(), alert() calls, .backup files | Production code with debug noise | Professional product |

### Tier 5 — Infrastructure (do when scaling)

| # | Action | Why | Impact |
|---|--------|-----|--------|
| 19 | **Build migration runner with version tracking** | 18 unordered migrations, no tracking | Safe schema evolution |
| 20 | **Add structured logging** — proper levels, file output, timestamps | Currently using print() | Debuggability |
| 21 | **Add database indexes** on organization_id across all tenant-isolated tables | Multi-tenant queries lack indexes | Performance |
| 22 | **Cache org database paths** — `get_org_db()` queries master.db on every single request | Unnecessary overhead on every API call | Performance |

---

## VII. Relationship to POS Build

The POS build plan (`/docs/POS_BUILD_PLAN.md`) requires touching `app.py`, `routes/pos_routes.py`, `sales_operations.py`, and creating new database tables. Without Tier 1-2 cleanup first:

- Adding POS order tables means adding them to 4 schema locations (or accepting they'll be inconsistent)
- New POS routes added to app.py push it past 8,000+ lines
- POS → inventory deduction has no connection safety net (context managers)
- POS → payroll tip integration means touching a monolith with no test coverage

**Recommendation:** Complete Tier 1-2 before or during Phase 1 of the POS build. The refactoring makes the POS build safer and faster.
