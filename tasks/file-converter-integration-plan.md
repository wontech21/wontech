# File Converter Integration — Add to WONTECH Reports Section

## Context

A standalone file converter app exists at `/Users/dell/Desktop/MVP SaaS/Programs/file-converter/` — a Python HTTP server (`BaseHTTPRequestHandler`, port 8080, ~5500 lines) that converts bank statement PDFs into exhibit files and builds Monthly Operating Reports (MORs) for Chapter 11 bankruptcy cases. The user wants this baked into the existing **Reports & Exports** section of WONTECH — not as a separate standalone page, but as additional tabs/capabilities within the reports page at `/dashboard/reports`.

**What ports over:** Bank statement converter, MOR builder, client profiles, file history.
**What gets dropped:** Raw HTTP server, macOS-specific features (osascript folder picker, `subprocess.open`), embedded HTML templates, hand-rolled multipart parsing, Budget Builder (Firing Up-specific with hardcoded vendor names — defer).

### Frontend Integration Approach

The existing `reports.html` page currently shows a flat report catalog (category pills + report cards). We'll add **top-level tab navigation** to the reports page:

```
[Reports]  [Converter]  [MOR Builder]  [Profiles]  [History]
```

- **Reports tab** — existing report catalog (unchanged)
- **Converter tab** — bank statement → exhibit conversion
- **MOR Builder tab** — monthly operating report generation
- **Profiles tab** — client/debtor profile management
- **History tab** — file history across converter + MOR

The page title stays "Reports & Exports" (or adjusts to "Reports & Tools"). The dashboard home card already exists. No new section routing needed.

---

## Phase 1: Backend Infrastructure

### 1A. Dependencies

**Modify:** `requirements.txt` — add:
```
pdfplumber>=0.10.0
pandas>=2.0.0
pypdf>=4.0.0
```

Note: `pypdf` (not `PyPDF2`) — the modern package used by `generate_mor.py` for proper AcroForm field filling.

### 1B. Processing Modules — `utils/converter/`

Port the pure Python processing functions from `file-converter-web.py`. These have zero HTTP dependency — they take file paths, return structured data.

**Create:** `utils/converter/__init__.py` (~5 lines)

**Create:** `utils/converter/pdf_extractors.py` (~900 lines)
Merges the best of both sources — `generate_mor.py` for Eastern Bank (word-level positional parsing) and the standalone app for TD Bank + multi-bank detection.

From `generate_mor.py` (`/Users/dell/Downloads/generate_mor.py`):
- `_group_words_into_lines(words, tolerance=4)` (line 156) — groups pdfplumber words by vertical position
- `_clean_merchant(text)` (line 174) — targeted merchant cleaning (state abbrevs, card numbers, seq numbers)
- `_clean_description(desc, next_cont_line)` (line 188) — handles POS/Debit Card Purchase/Square/Preauthorized Credit/Electronic Payment patterns
- `parse_bank_statement(pdf_path)` (line 231) — **primary Eastern Bank parser**, word-level positional extraction, classifies by column x-position (withdrawal < 450, deposit < 520), extracts statement period + summary totals, returns `{deposits, withdrawals, checks, summary, period, month_name, year}`
- `_parse_check_summary(pdf)` (line 360) — word-level check summary parsing with triplet grouping

From standalone app (`file-converter-web.py`):
- `detect_pdf_format(pdf_path)` (line 45) — multi-bank format detection (month-abbrev vs MM/DD vs table)
- `extract_bank_statement_mmdd_from_pdf(pdf_path)` (line 642) — TD Bank MM/DD format with section tracking, internal transfer detection
- `extract_table_from_pdf(pdf_path)` (line 101) — generic structured table extraction

New router function:
- `extract_transactions_from_pdf(pdf_path)` — calls `detect_pdf_format()`, dispatches to `parse_bank_statement()` (Eastern) or `extract_bank_statement_mmdd_from_pdf()` (TD Bank), normalizes output format

**Verification logic** from `generate_mor.py`: after parsing, compare parsed deposit/withdrawal totals against the statement's own summary totals and flag mismatches.

These need imports from `merchant_normalizer` for TD Bank path.

**Create:** `utils/converter/merchant_normalizer.py` (~200 lines)
Copy verbatim:
- `get_merchant_normalization_map()` (line 134) — 200+ merchant name → standardized name mappings
- `normalize_merchant_name(description)` (line 268) — strip city/state, apply map
- `clean_merchant_description(description)` (line 306) — remove POS, card numbers, transaction codes
- `normalize_transaction_name(text)` (line 873) — extract uppercase sequences

**Create:** `utils/converter/exhibit_generator.py` (~450 lines)
Copy with minor path adaptations:
- `parse_financial_file(file_path)` (line 904) — reads CSV/XLSX, normalizes columns — **verbatim**
- `generate_exhibit_file(file_path, output_dir, exhibit_type, ...)` (line 963) — main exhibit generator, CSV/XLSX/PDF with totals, internal transfer handling, checks section — **adapt** to accept explicit `output_dir` instead of building paths from hardcoded base
- `csv_to_pdf(csv_path, pdf_path)` (line 1332) — reportlab table rendering — **verbatim**
- `create_header_page(exhibit_label, output_path)` (line 1384) — blank page with "Exhibit X" — **verbatim**

**Create:** `utils/converter/mor_builder.py` (~400 lines)
Port from `generate_mor.py` (`/Users/dell/Downloads/generate_mor.py`) — **not** the standalone app. This uses proper AcroForm field filling instead of coordinate-based overlays.

From `generate_mor.py`:
- `parse_previous_mor(pdf_path)` (line 53) — reads previous month's filled MOR PDF, extracts all carryover values: ending_balance, proj_receipts/disbursements/net, prof_fees_filing, employee counts, questionnaire checkboxes, case header info. Uses `pypdf.PdfReader.get_fields()` with fallback to annotation scanning.
- `build_field_values(prev_mor, bank_data, report_date, next_proj_receipts, next_proj_disbursements, responsible_name, opening_override)` (line 432) — computes complete dict of all MOR form field values: header fields, cash activity (Lines 19-23), employees (Section 6), professional fees, projections Sections 7 columns A/B/C with variance calculations, questionnaire checkboxes carried forward.
- `fill_mor_form(template_path, field_values, output_path)` (line 534) — fills MOR template via `pypdf.PdfWriter.update_page_form_field_values()` on all 4 pages. Sets `NeedAppearances` flag. Proper AcroForm filling.
- `create_exhibit_pdf(deposits, withdrawals, checks, month_label)` (line 566) — generates Exhibit C (deposits) + Exhibit D (withdrawals + checks) as in-memory BytesIO PDF. Reportlab `SimpleDocTemplate` + `Table` with professional styling.
- `merge_pdfs(form_path, exhibit_buffer, bank_stmt_path, output_path)` (line 715) — merges filled form + exhibits + bank statement using `pypdf.PdfWriter`.

**Key advantages over standalone app's approach:**
- Fills **all** MOR fields (projections, variance, professional fees, employees, checkboxes), not just Lines 19-23
- Proper PDF form-field filling vs coordinate-based text overlay
- Carries forward all values from previous MOR (questionnaire answers, employee counts, etc.)
- In-memory exhibit generation (BytesIO) — no temp files needed

### 1C. Database Tables

**Modify:** `db_manager.py` — add 3 tables inside `create_org_database()`:

```sql
CREATE TABLE IF NOT EXISTS converter_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    debtor_name TEXT NOT NULL,
    case_number TEXT,
    bankruptcy_district TEXT,
    ein_tax_id TEXT,
    business_address TEXT,
    phone TEXT,
    email TEXT,
    attorney_name TEXT,
    attorney_firm TEXT,
    attorney_contact TEXT,
    case_filing_date DATE,
    notes TEXT,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS converter_file_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER,
    file_type TEXT NOT NULL,       -- 'mor', 'exhibit_c', 'exhibit_d', 'bank_statement', 'other'
    file_category TEXT NOT NULL,   -- 'uploaded' or 'generated'
    original_filename TEXT NOT NULL,
    stored_filepath TEXT NOT NULL,
    file_size_bytes INTEGER,
    month_year TEXT,               -- 'YYYY-MM'
    file_hash TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES converter_profiles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS converter_mor_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    month_year TEXT NOT NULL,
    report_date TEXT,
    -- Cash Activity (Section 5)
    line_19_opening_balance REAL,
    line_20_receipts REAL,
    line_21_disbursements REAL,
    line_22_net_cash_flow REAL,
    line_23_ending_balance REAL,
    -- Projections (Section 7)
    proj_receipts REAL,              -- next month projected receipts
    proj_disbursements REAL,         -- next month projected disbursements
    proj_net REAL,                   -- next month projected net
    -- Employees & Fees
    employees_current TEXT,
    prof_fees_cumulative REAL,
    responsible_party TEXT,
    -- File references
    bank_statement_file_id INTEGER,
    exhibit_c_file_id INTEGER,
    exhibit_d_file_id INTEGER,
    mor_file_id INTEGER,
    -- Verification
    verification_deposits_ok INTEGER DEFAULT 1,
    verification_withdrawals_ok INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES converter_profiles(id),
    UNIQUE(profile_id, month_year)
);
```

### 1D. MOR Template PDF

**Copy:** `src/MORtemplate.pdf` → `static/templates/mor_template.pdf`

---

## Phase 2: API Routes

**Create:** `routes/converter_routes.py` (~500 lines)

Blueprint: `converter_bp`, url_prefix `/api/converter`. All endpoints `@login_required` + `@organization_required`.

### Profile CRUD (~100 lines)
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/profiles` | List all active profiles for this org |
| GET | `/profiles/<id>` | Get single profile |
| POST | `/profiles` | Create profile |
| PUT | `/profiles/<id>` | Update profile |
| DELETE | `/profiles/<id>` | Soft-delete (active=0) |

### Bank Statement Converter (~120 lines)
| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/convert` | Upload PDF → generate exhibits |
| GET | `/download/<file_id>` | Download file by history ID |

`POST /convert` flow:
1. `request.files['file']` + form: `profile_id`, `exhibit_type`, `exhibit_label`, `exhibit_label2`
2. Save to `static/uploads/converter/org_{id}/uploads/`
3. `extract_transactions_from_pdf()` → `generate_exhibit_file()`
4. Save outputs to `static/uploads/converter/org_{id}/exhibits/`
5. Record in `converter_file_history` + `log_audit()`
6. Return JSON with file IDs + download URLs

### MOR Builder (~200 lines)
| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/mor/generate` | Full MOR generation pipeline |
| GET | `/mor/history/<profile_id>` | MOR generation log for profile |
| GET | `/mor/previous-balance/<profile_id>/<month_year>` | Previous month's Line 23 |
| POST | `/mor/parse-previous` | Parse a previous MOR PDF for carryover values |

`POST /mor/generate` flow:
1. `request.files['bank_statement']` (required) + optional `request.files['prev_mor']` (previous month's MOR PDF)
2. Form data: `profile_id`, `month_year`, `report_date`, `proj_receipts`, `proj_disbursements`, optional `responsible`, optional `opening_balance` override
3. Parse bank statement → extract deposits, withdrawals, checks, summary
4. Get previous month carryover: if `prev_mor` PDF uploaded → `parse_previous_mor()`, else query `converter_mor_log` DB for previous month
5. `build_field_values()` → compute all form fields (Lines 19-23, projections A/B/C, variance, employees, fees, checkboxes)
6. `fill_mor_form()` → proper AcroForm field filling on template
7. `create_exhibit_pdf()` → Exhibit C (deposits) + Exhibit D (withdrawals + checks) in-memory
8. `merge_pdfs()` → combine filled form + exhibits + bank statement
9. Save to `org_{id}/mor/`, record in `converter_file_history` + `converter_mor_log` (all line values + projections)
10. Return JSON: file IDs, all calculated values, download URLs, verification status (parsed vs summary totals)

`POST /mor/parse-previous` — utility endpoint: upload a previous MOR PDF, get back extracted carryover values (for preview in the UI before generating).

### File History (~80 lines)
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/history` | List files (filters: profile_id, file_type, month_year) |
| DELETE | `/history/<id>` | Delete file entry + physical file |

### Stats (~30 lines)
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/stats` | Profile count, file count, MOR count for dashboard card |

### Registration
- `routes/__init__.py` — add `converter_bp` import + `__all__`
- `app.py` — import + `app.register_blueprint(converter_bp)`

---

## Phase 3: Frontend

### 3A. Modify existing `templates/reports.html`

Add top-level tab navigation bar below the header, above the toolbar. The existing reports content becomes the "Reports" tab. New tab panels for Converter, MOR Builder, Profiles, History.

**Tab structure added to reports.html:**

```
[Reports]  [Converter]  [MOR Builder]  [Profiles]  [History]
```

**Reports tab** — wraps existing report catalog content (category pills, search, report cards, modal) — no functional changes, just wrapped in a tab panel div.

**Converter tab** (~150 lines of markup):
- Drag-and-drop upload zone for bank statement PDF
- Profile selector dropdown (optional — for file history tracking)
- Exhibit type: Withdrawals / Deposits / Both
- Exhibit label inputs (e.g., "A", "B", "C", "D")
- "Convert" button → results with download links (CSV/XLSX/PDF)
- Transaction preview table

**MOR Builder tab** (~200 lines of markup):
- Profile selector (required)
- Month/Year selector + Report Date input
- Upload zone for bank statement PDF (required)
- Upload zone for previous month's MOR PDF (optional — for first-time or importing from outside WONTECH; if omitted, uses DB carryover)
- Opening Balance field (auto-populated from previous MOR or DB, editable override)
- Projected Receipts + Projected Disbursements inputs (next month projections)
- Responsible Party name (optional override)
- "Generate MOR" button → shows:
  - Cash activity summary (Lines 19-23) in a card
  - Projections variance table (previous projected vs actual vs variance)
  - Verification status (parsed totals vs statement summary — green check or yellow warning)
  - Download links: Filled MOR, Exhibit C, Exhibit D, Complete Package

**Profiles tab** (~100 lines of markup):
- Profile cards grid
- Add/Edit modal: debtor name, case number, district, EIN, address, phone, email, attorney info, case filing date
- Delete with confirmation

**History tab** (~80 lines of markup):
- Filter bar: profile, file type, month/year
- File table: date, profile, type badge, filename, size, download

**CSS additions** (~150 lines): tab bar styling, upload zone, results cards, profile cards, history table — all in existing `<style>` block using WONTECH design tokens.

### 3B. Modify existing `static/js/reports.js`

Add converter functionality alongside existing report functions:
- Top-level tab switching (`switchMainTab()`)
- Profile CRUD functions
- File upload + conversion via `/api/converter/convert`
- MOR generation via `/api/converter/mor/generate`
- Auto-populate opening balance via `/api/converter/mor/previous-balance/`
- File history loading with filters
- Download helper, drag-and-drop handling

~350 lines of new JS added to existing reports.js.

### 3C. Dashboard Home Card Update

**Modify:** `templates/dashboard_home.html` — update existing Reports & Exports card description and stats to reflect the expanded capabilities (bank statement conversion, MOR builder added).

### 3D. No new portal route needed

The converter lives inside `/dashboard/reports` which already exists. No changes to `portal_routes.py`.

---

## File Summary

### Source Files
| Source | Used For |
|--------|----------|
| `/Users/dell/Downloads/generate_mor.py` | MOR builder, Eastern Bank parser, exhibit generator, form filler |
| `/Users/dell/Desktop/MVP SaaS/Programs/file-converter/src/file-converter-web.py` | TD Bank parser, multi-bank detection, merchant normalization, profiles/history DB schema |
| `/Users/dell/Desktop/MVP SaaS/Programs/file-converter/src/database.py` | DB schema reference |

### New Files (6)
| File | Lines |
|------|-------|
| `utils/converter/__init__.py` | ~5 |
| `utils/converter/pdf_extractors.py` | ~900 |
| `utils/converter/merchant_normalizer.py` | ~200 |
| `utils/converter/exhibit_generator.py` | ~450 |
| `utils/converter/mor_builder.py` | ~400 |
| `routes/converter_routes.py` | ~550 |

### Modified Files (6)
| File | Change |
|------|--------|
| `requirements.txt` | +3 deps (pdfplumber, pandas, pypdf) |
| `db_manager.py` | +3 tables in `create_org_database()` |
| `routes/__init__.py` | +import converter_bp |
| `app.py` | +register blueprint |
| `templates/reports.html` | +tab navigation, converter/MOR/profiles/history tabs (~500 lines) |
| `static/js/reports.js` | +converter functions (~350 lines) |

### Also Updated
| File | Change |
|------|--------|
| `templates/dashboard_home.html` | Update Reports card description/stats |

### Binary Asset (1)
- `static/templates/mor_template.pdf` — default MOR template

---

## Execution Order

```
Phase 1A (deps) → 1B (processing modules — can parallelize) → 1C (DB tables) → 1D (template PDF)
    → Phase 2 (routes)
        → Phase 3 (frontend: reports.html tabs + reports.js functions)
```

---

## Verification

1. `pip install -r requirements.txt` succeeds (pdfplumber, pandas, pypdf)
2. Server starts without import errors
3. `/dashboard/reports` loads with 5 tabs: Reports, Converter, MOR Builder, Profiles, History
4. Reports tab — existing report catalog works as before
5. Profiles tab — create/edit/delete profiles with all debtor/case/attorney fields
6. Converter tab — upload bank statement PDF → get Exhibit downloads (CSV/XLSX/PDF), works for both Eastern Bank and TD Bank formats
7. MOR Builder tab — upload bank statement + previous MOR → generates complete filled MOR with:
   - All form fields populated (Lines 19-23, projections A/B/C with variance, professional fees, employees, checkboxes)
   - Exhibit C (deposits) + Exhibit D (withdrawals + checks) generated
   - Verification: parsed totals vs statement summary match check
   - Complete merged PDF (form + exhibits + bank statement)
8. MOR continuity — generate next month → Line 19 auto-populates from previous Line 23 (from DB or uploaded previous MOR)
9. MOR projections carry forward — previous month's "next month projections" appear in column A, actuals in column B, variance in column C
10. History tab — shows all uploaded + generated files with filters
11. `POST /mor/parse-previous` — upload a previous MOR PDF, get back carryover preview
