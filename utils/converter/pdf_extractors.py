"""
Bank statement PDF parsers.

Supports:
  - Eastern Bank (month-abbreviation dates, word-level positional parsing)
  - TD Bank (MM/DD dates, section-based classification)
  - Generic table extraction
  - Auto-detection via detect_pdf_format()
"""

import re
from datetime import datetime

import pdfplumber

from .merchant_normalizer import clean_merchant_description, normalize_merchant_name

# Shared regex
AMT_RE = re.compile(r"^[\d,]+\.\d{2}$")
DATE_MONTHS = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}


# ============================================================
# Format detection
# ============================================================

def detect_pdf_format(pdf_path):
    """Detect whether PDF is a bank statement or a table format.

    Returns:
        'bank_statement'      – month-abbreviation dates (Eastern Bank)
        'bank_statement_mmdd' – MM/DD dates (TD Bank)
        'table'               – structured tables
        None                  – cannot determine
    """
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return None

        text = pdf.pages[0].extract_text()
        if not text:
            return None

        lines = text.split('\n')
        bank_statement_matches = 0
        mmdd_statement_matches = 0

        for line in lines:
            if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}', line):
                bank_statement_matches += 1
            if re.match(r'^\d{2}/\d{2}\s+', line):
                mmdd_statement_matches += 1

        if bank_statement_matches >= 3:
            return 'bank_statement'
        if mmdd_statement_matches >= 3:
            return 'bank_statement_mmdd'

        # Check for table format
        tables = pdf.pages[0].extract_tables()
        if tables and len(tables) > 0:
            first_table = tables[0]
            if first_table and len(first_table) > 0:
                headers = first_table[0]
                header_text = ' '.join([str(h).lower() if h else '' for h in headers])
                if any(kw in header_text for kw in ['date', 'payer', 'purpose', 'amount', 'description']):
                    return 'table'

        return 'bank_statement'


# ============================================================
# Generic table extraction
# ============================================================

def extract_table_from_pdf(pdf_path):
    """Extract structured table data from PDF."""
    all_rows = []
    headers = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                if not table:
                    continue
                if headers is None:
                    headers = [str(cell).strip() if cell else '' for cell in table[0]]
                    data_rows = table[1:]
                else:
                    data_rows = table
                for row in data_rows:
                    if row and any(cell for cell in row):
                        cleaned_row = [str(cell).strip() if cell else '' for cell in row]
                        all_rows.append(cleaned_row)

    return {'headers': headers, 'rows': all_rows}


# ============================================================
# Eastern Bank parser (word-level positional)
# ============================================================

def _group_words_into_lines(words, tolerance=4):
    """Group words by vertical position into line lists."""
    lines = []
    current_line = []
    current_top = -999
    for w in words:
        if abs(w["top"] - current_top) > tolerance:
            if current_line:
                lines.append((current_top, current_line))
            current_line = [w]
            current_top = w["top"]
        else:
            current_line.append(w)
    if current_line:
        lines.append((current_top, current_line))
    return lines


def _clean_merchant(text):
    """Extract a clean merchant name from a bank-statement continuation line."""
    text = re.sub(r"XXXXXXXXXXXX\w+", "", text)
    text = re.sub(r"SEQ\s*#\s*\d+", "", text)
    text = re.sub(r"\d{4}\s+\d{4}", "", text)
    text = re.sub(
        r"\s+(MA|NH|CT|NY|NJ|RI|ME|VT|PA|CA|FL|TX|OH|IL|GA|NC|VA)\s*$",
        "", text.strip(),
    )
    text = text.strip()
    return text.title() if text else ""


def _clean_description(desc, next_cont_line=""):
    """Clean up a transaction-line description."""
    if any(k in desc for k in ("Debit Card Purchase", "POS REFUND", "POS Refund", "Debit Card Refund")):
        merchant = _clean_merchant(next_cont_line)
        if merchant:
            if "REFUND" in desc.upper() or "Refund" in desc:
                return f"POS Refund {merchant}"
            return merchant
        return desc.title()

    if desc.upper().startswith("SQ ") or "SQ *" in desc.upper():
        merchant = _clean_merchant(next_cont_line)
        if merchant:
            return merchant
        return desc.title()

    if "Preauthorized Credit" in desc:
        desc = re.sub(r"BANKCARD\s+\d+\s+MTOT\s+DEP\s+\d+", "Bankcard 1869 Mtot Dep", desc)
        desc = re.sub(r"\d{15,}", "", desc).strip()
        return desc

    if "Electronic Payment" in desc:
        detail = desc.replace("Electronic Payment", "").strip()
        detail = re.sub(r"\s+", " ", detail)
        return f"Electronic Payment {detail}"

    for keep in ("NSF", "Overdraft", "Service Charge", "Deposit"):
        if keep in desc:
            return desc

    return desc.title() if desc.isupper() else desc


def _parse_check_summary(pdf):
    """Parse the Check Summary section(s) from a bank statement."""
    date_re = re.compile(r"^\d{2}/\d{2}$")
    checks = []

    for page in pdf.pages:
        text = page.extract_text() or ""
        if "Check Summary" not in text:
            continue

        words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))

        cs_top = None
        for w in words:
            if w["text"] == "Check":
                companions = [
                    w2 for w2 in words
                    if abs(w2["top"] - w["top"]) < 3 and w2["text"] == "Summary"
                ]
                if companions:
                    cs_top = w["top"]
                    break

        if cs_top is None:
            continue

        below = [w for w in words if w["top"] > cs_top + 25]
        lines = _group_words_into_lines(below)

        for _, line_words in lines:
            line_text = " ".join(w["text"] for w in line_words)
            if any(k in line_text for k in ("Check No", "Total", "Balance", "Indicates", "081EB")):
                continue

            data_words = sorted(
                [w for w in line_words if w["text"] != "o"], key=lambda w: w["x0"]
            )

            i = 0
            while i < len(data_words) - 2:
                w_num = data_words[i]
                w_date = data_words[i + 1]
                w_amt = data_words[i + 2]

                check_no_raw = w_num["text"].replace("*", "").replace("\u2020", "")
                if (
                    check_no_raw.isdigit()
                    and date_re.match(w_date["text"])
                    and AMT_RE.match(w_amt["text"])
                ):
                    amount = float(w_amt["text"].replace(",", ""))
                    checks.append((int(check_no_raw), w_date["text"], amount))
                    i += 3
                else:
                    i += 1

    return checks


def parse_bank_statement(pdf_path):
    """Parse an Eastern Bank statement PDF and return structured data.

    Returns dict with:
        deposits      – [(date_str, description, amount), ...]
        withdrawals   – [(date_str, description, amount), ...]
        checks        – [(check_no:int, date_str, amount), ...]
        summary       – {starting, ending, deposits, withdrawals}
        period        – (start_date_str, end_date_str)
        month_name    – e.g. "December"
        year          – e.g. 2025
    """
    deposits = []
    withdrawals = []
    checks = []
    summary = {}
    period = (None, None)

    with pdfplumber.open(pdf_path) as pdf:
        # Statement period
        first_text = pdf.pages[0].extract_text() or ""
        m = re.search(r"Statement Period:\s*(.+?)\s*thru\s*(.+?)$", first_text, re.MULTILINE)
        if m:
            period = (m.group(1).strip(), m.group(2).strip())

        # Summary totals
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Starting Balance" in text and "Total Deposits" in text:
                ms = re.search(r"Starting Balance:\s*\$?([\d,]+\.\d{2})", text)
                me = re.search(r"Ending Balance:\s*\$?([\d,]+\.\d{2})", text)
                md = re.search(r"Total Deposits/Credits:\s*\$?([\d,]+\.\d{2})", text)
                mw = re.search(r"Total Withdrawals/Debits:\s*\$?([\d,]+\.\d{2})", text)
                summary = {
                    "starting": float(ms.group(1).replace(",", "")) if ms else 0,
                    "ending": float(me.group(1).replace(",", "")) if me else 0,
                    "deposits": float(md.group(1).replace(",", "")) if md else 0,
                    "withdrawals": float(mw.group(1).replace(",", "")) if mw else 0,
                }
                break

        # Transactions
        for pi, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if "Transaction Description" not in text and "STARTING BALANCE" not in text:
                continue

            words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
            all_lines = _group_words_into_lines(words)

            for li, (top, line_words) in enumerate(all_lines):
                if not line_words or len(line_words) < 3:
                    continue
                first = line_words[0]

                if first["text"] not in DATE_MONTHS or first["x0"] > 60:
                    continue

                day_word = line_words[1]
                date_str = f"{first['text']} {day_word['text']}"

                amounts = [
                    (w, w["x1"]) for w in line_words if AMT_RE.match(w["text"])
                ]
                if not amounts:
                    continue

                first_amt_x = amounts[0][0]["x0"]
                desc_words = [
                    w["text"] for w in line_words
                    if w["x0"] > day_word["x1"] + 2 and w["x0"] < first_amt_x - 10
                ]
                raw_desc = " ".join(desc_words)

                cont_text = ""
                if li + 1 < len(all_lines):
                    _, next_words = all_lines[li + 1]
                    if next_words and next_words[0]["x0"] > 70:
                        cont_text = " ".join(w["text"] for w in next_words)

                desc = _clean_description(raw_desc, cont_text)

                for amt_word, x1 in amounts:
                    val = float(amt_word["text"].replace(",", ""))
                    if x1 < 450:
                        withdrawals.append((date_str, desc, val))
                    elif x1 < 520:
                        deposits.append((date_str, desc, val))

        # Check Summary
        checks = _parse_check_summary(pdf)

    # Derive month/year
    month_name = ""
    year = 0
    if period[1]:
        try:
            end_dt = datetime.strptime(period[1], "%b %d, %Y")
            month_name = end_dt.strftime("%B")
            year = end_dt.year
        except ValueError:
            pass

    return {
        "deposits": deposits,
        "withdrawals": withdrawals,
        "checks": checks,
        "summary": summary,
        "period": period,
        "month_name": month_name,
        "year": year,
    }


# ============================================================
# TD Bank parser (MM/DD format)
# ============================================================

def extract_bank_statement_mmdd(pdf_path):
    """Extract transactions from bank statement with MM/DD date format (TD Bank).

    Returns list of dicts: [{date, description, withdrawal, deposit}, ...]
    """
    transactions = []
    current_section = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            i = 0

            while i < len(lines):
                line_stripped = lines[i].strip()
                line_upper = line_stripped.upper()

                # Section headers
                if 'ELECTRONICDEPOSITS' in line_upper.replace(' ', ''):
                    current_section = 'deposits'
                    i += 1
                    continue
                elif 'ELECTRONICPAYMENTS' in line_upper.replace(' ', '') or \
                     'ELECTRONICWITHDRAWALS' in line_upper.replace(' ', ''):
                    current_section = 'payments'
                    i += 1
                    continue
                elif any(marker in line_upper for marker in [
                    'ACCOUNT SUMMARY', 'BALANCE SUMMARY', 'HOW TO BALANCE',
                    'STATEMENT DISCLOSURE', 'TOTAL FOR THIS CYCLE',
                    'DAILYBALANCESUMMARY', 'DAILY BALANCE SUMMARY'
                ]):
                    current_section = None
                    break

                # Match lines starting with MM/DD
                date_match = re.match(r'^(\d{2}/\d{2})\s+(.+)', line_stripped)

                if date_match:
                    date_mmdd = date_match.group(1)
                    rest_of_line = date_match.group(2)

                    # Convert MM/DD to "Mon DD" format
                    month_num, day_num = date_mmdd.split('/')
                    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    month_abbr = months[int(month_num) - 1]
                    date = f"{month_abbr} {int(day_num)}"

                    # Extract amount
                    amount_match = re.search(r'([\d,]+\.\d{2})(?:\s*)$', rest_of_line)

                    if amount_match:
                        amount = amount_match.group(1).replace(',', '')

                        # Extract description
                        desc_end_pos = rest_of_line.rfind(amount_match.group(1))
                        description = rest_of_line[:desc_end_pos].strip()

                        # Check continuation line
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            next_line_upper = next_line.upper()

                            is_continuation = (
                                next_line and
                                not re.match(r'^\d{2}/\d{2}\s+', next_line) and
                                not any(marker in next_line_upper for marker in [
                                    'SUBTOTAL', 'TOTAL', 'ELECTRONIC', 'ACCOUNT',
                                    'BALANCE', 'STATEMENT', 'CALL ', 'WWW.', 'HTTP'
                                ])
                            )

                            if is_continuation:
                                description = next_line
                                i += 1

                        description = clean_merchant_description(description)

                        # Classify
                        withdrawal = ""
                        deposit = ""
                        desc_upper = description.upper()
                        rest_upper = rest_of_line.upper()

                        # Internal transfer detection
                        is_internal_credit = (
                            ('ETRANSFERCREDIT' in rest_upper.replace(' ', '') or
                             'E-TRANSFERCREDIT' in rest_upper.replace(' ', '')) and
                            ('ONLINE' in rest_upper or 'ONLINEXFER' in rest_upper)
                        )
                        is_internal_debit = (
                            ('ETRANSFERDEBIT' in rest_upper.replace(' ', '') or
                             'E-TRANSFERDEBIT' in rest_upper.replace(' ', '')) and
                            ('ONLINE' in rest_upper or 'ONLINEXFER' in rest_upper)
                        )

                        if is_internal_credit:
                            description = description + " *"
                            deposit = "INTERNAL"
                        elif is_internal_debit:
                            description = description + " *"
                            withdrawal = "INTERNAL"
                        else:
                            if current_section == 'deposits':
                                deposit = amount
                            elif current_section == 'payments':
                                withdrawal = amount
                            else:
                                is_deposit = (
                                    'DEPOSIT' in desc_upper or
                                    'CREDIT' in desc_upper or
                                    'REFUND' in desc_upper or
                                    'PAYROLL' in desc_upper or
                                    ('TRANSFER' in desc_upper and 'CREDIT' in rest_upper)
                                )
                                is_withdrawal = (
                                    'DEBIT' in desc_upper or
                                    'PAYMENT' in desc_upper or
                                    'WITHDRAWAL' in desc_upper or
                                    ('ZELLE' in desc_upper and 'SENT' in desc_upper) or
                                    'PURCHASE' in desc_upper or
                                    'FEE' in desc_upper or
                                    'CHARGE' in desc_upper
                                )

                                if is_deposit and not is_withdrawal:
                                    deposit = amount
                                else:
                                    withdrawal = amount

                        transactions.append({
                            'date': date,
                            'description': description,
                            'withdrawal': withdrawal,
                            'deposit': deposit
                        })

                i += 1

    return transactions


# ============================================================
# Router / unified extraction
# ============================================================

def extract_transactions_from_pdf(pdf_path):
    """Auto-detect format and extract transactions.

    For Eastern Bank format, returns the structured dict from parse_bank_statement().
    For TD Bank/table formats, returns the list/dict from those parsers.
    """
    pdf_format = detect_pdf_format(pdf_path)

    if pdf_format == 'table':
        return extract_table_from_pdf(pdf_path)
    elif pdf_format == 'bank_statement_mmdd':
        return extract_bank_statement_mmdd(pdf_path)
    else:
        return parse_bank_statement(pdf_path)


def verify_parsed_totals(bank_data):
    """Compare parsed transaction totals against statement summary.

    Returns dict with verification results.
    """
    summary = bank_data.get("summary", {})
    if not summary:
        return {"deposits_ok": True, "withdrawals_ok": True, "no_summary": True}

    parsed_dep = round(sum(a for _, _, a in bank_data.get("deposits", [])), 2)
    parsed_wd = round(
        sum(a for _, _, a in bank_data.get("withdrawals", []))
        + sum(a for _, _, a in bank_data.get("checks", [])),
        2,
    )

    dep_ok = abs(parsed_dep - summary.get("deposits", 0)) < 0.01
    wd_ok = abs(parsed_wd - summary.get("withdrawals", 0)) < 0.01

    return {
        "deposits_ok": dep_ok,
        "withdrawals_ok": wd_ok,
        "parsed_deposits": parsed_dep,
        "parsed_withdrawals": parsed_wd,
        "summary_deposits": summary.get("deposits", 0),
        "summary_withdrawals": summary.get("withdrawals", 0),
    }
