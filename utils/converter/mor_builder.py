"""
Monthly Operating Report (MOR) builder.

Generates Official Form 425C Monthly Operating Reports by:
  1. Reading the previous month's MOR to extract carryover values
  2. Filling the MOR form template by drawing text overlays (flat PDF)
  3. Generating Exhibit C (deposits) and Exhibit D (withdrawals) tables
  4. Merging everything with the bank statement into a single PDF
"""

import json
import os
import re
from datetime import datetime
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


# ============================================================
# 1. PREVIOUS MOR PARSER
# ============================================================

def parse_previous_mor(pdf_path):
    """Extract carryover values from the previous month's filled MOR.

    First checks for a companion JSON sidecar file (same name with .json
    extension) which is written during MOR generation.  Falls back to
    parsing PDF form fields if no sidecar exists.

    Returns a dict with:
        ending_balance, proj_receipts, proj_disbursements, proj_net,
        prof_fees_filing, employees_filed, employees_current,
        questionnaire, case_info
    """
    # Try JSON sidecar first (reliable — avoids pypdf field-loss issues)
    json_path = os.path.splitext(pdf_path)[0] + ".json"
    if os.path.exists(json_path):
        with open(json_path) as f:
            return json.load(f)

    # Fall back to PDF form field parsing
    reader = PdfReader(pdf_path)

    fields = reader.get_fields() or {}
    if not fields:
        fields = {}
        for page in reader.pages[:4]:
            if "/Annots" not in page:
                continue
            for annot in page["/Annots"]:
                obj = annot.get_object()
                name = str(obj.get("/T", ""))
                val = obj.get("/V", "")
                if name:
                    fields[name] = {"/V": val}

    def fval(name, default=""):
        f = fields.get(name)
        if f is None:
            return default
        v = f.get("/V", default) if isinstance(f, dict) else f
        return str(v) if v else default

    def fnum(name, default=0.0):
        raw = fval(name, "")
        if not raw:
            return default
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            return default

    ending_balance = fnum("fld.1.4")
    proj_receipts = fnum("fld.1.13")
    proj_disbursements = fnum("fld.1.14")
    proj_net = fnum("fld.1.15")
    prof_fees_filing = fnum("fld.1.8")

    employees_filed = fval("fld.1.10", "28")
    employees_current = fval("fld.1.11", "30")

    questionnaire = {}
    for i in range(18):
        key = f"Check Box.{i}.0"
        questionnaire[key] = fval(key, "/Off")
    for i in range(5):
        key = f"Check Box.18.{i}"
        questionnaire[key] = fval(key, "/Off")

    case_info = {
        "Debtor 1": fval("Debtor 1", ""),
        "Case number": fval("Case number", ""),
        "Bankruptcy District Information": fval("Bankruptcy District Information", ""),
        "Text1.2": fval("Text1.2", ""),
        "Check if this is an amended": fval("Check if this is an amended", "/Off"),
    }

    return {
        "ending_balance": ending_balance,
        "proj_receipts": proj_receipts,
        "proj_disbursements": proj_disbursements,
        "proj_net": proj_net,
        "prof_fees_filing": prof_fees_filing,
        "employees_filed": employees_filed,
        "employees_current": employees_current,
        "questionnaire": questionnaire,
        "case_info": case_info,
    }


# ============================================================
# 2. FORM FIELD BUILDER
# ============================================================

def build_field_values(prev_mor, bank_data, report_date,
                       next_proj_receipts, next_proj_disbursements,
                       responsible_name=None, opening_override=None,
                       template_fields=None):
    """Build the complete dict of PDF form-field values for this month's MOR.

    template_fields: output of parse_previous_mor() on the original blank
                     template; used as fallback for questionnaire and case info
                     when the prev_mor was itself generated and lost checkbox
                     field names during pypdf cloning.

    Returns (fields_dict, cash_summary_dict).
    """
    summary = bank_data["summary"]
    month_name = bank_data["month_name"]

    # Cash activity
    opening = opening_override if opening_override is not None else prev_mor["ending_balance"]
    receipts = summary["deposits"]
    disbursements = summary["withdrawals"]
    net_cf = round(receipts - disbursements, 2)
    ending = round(opening + net_cf, 2)

    # Projections
    prev_proj_rec = prev_mor["proj_receipts"]
    prev_proj_dis = prev_mor["proj_disbursements"]
    prev_proj_net = prev_mor["proj_net"]
    next_proj_net = round(next_proj_receipts - next_proj_disbursements, 2)

    # Use template_fields as fallback for questionnaire and case info
    # (generated MORs may lose checkbox field names during pypdf cloning)
    tf = template_fields or {}

    def _q(key):
        """Get questionnaire value: prefer prev_mor, fall back to template."""
        v = prev_mor["questionnaire"].get(key)
        if v and v != "/Off":
            return v
        tf_q = tf.get("questionnaire", {})
        return tf_q.get(key, "/Off")

    def _ci(key):
        """Get case info: prefer prev_mor, fall back to template."""
        v = prev_mor["case_info"].get(key, "")
        if v:
            return v
        return tf.get("case_info", {}).get(key, "")

    fields = {}

    # Header
    fields["Text1.0"] = month_name
    fields["Text1.1"] = report_date
    fields["Text1.2"] = _ci("Text1.2") or "Food service"
    fields["Text1.4"] = responsible_name or ""
    fields["Text1.5.1"] = ""
    fields["Debtor 1"] = _ci("Debtor 1")
    fields["Case number"] = _ci("Case number")
    fields["Bankruptcy District Information"] = _ci("Bankruptcy District Information")
    fields["Check if this is an amended"] = _ci("Check if this is an amended") or "/Off"

    # Questionnaire & additional-info checkboxes (carry forward with fallback)
    for i in range(18):
        key = f"Check Box.{i}.0"
        fields[key] = _q(key)
    for i in range(5):
        key = f"Check Box.18.{i}"
        fields[key] = _q(key)
    # Always attach bank statements
    fields["Check Box.18.0"] = "/Yes"

    # Cash Activity (Section 5)
    fields["fld.1.0"] = f"{opening:.2f}"
    fields["fld.1.1"] = f"{receipts:.2f}"
    fields["fld.1.2"] = f"{disbursements:.2f}"
    fields["fld.1.3"] = f"{net_cf:.2f}"
    fields["fld.1.4"] = f"{ending:.2f}"

    # Employees (Section 6)
    fields["fld.1.10"] = prev_mor["employees_filed"]
    fields["fld.1.11"] = prev_mor["employees_current"]

    # Professional fees
    fields["fld.1.7"] = "0"
    fields["fld.1.8"] = str(int(prev_mor["prof_fees_filing"]))
    fields["fld.1.9"] = "0"
    fields["fld.1.12"] = "0"

    # Projections (Section 7)
    fields["fld.1.16.0"] = str(int(prev_proj_rec))
    fields["fld.1.16.1"] = str(int(prev_proj_dis))
    fields["fld.1.16.2"] = str(int(prev_proj_net))

    fields["fld.1.17.0"] = f"{receipts:.2f}"
    fields["fld.1.16.3"] = f"{disbursements:.2f}"
    fields["fld.1.17.1"] = f"{net_cf:.2f}"

    fields["fld.1.17.2"] = f"{prev_proj_rec - receipts:.2f}"
    fields["fld.1.17.3"] = f"{prev_proj_dis - disbursements:.2f}"
    fields["fld.1.18.0"] = f"{prev_proj_net - net_cf:.2f}"

    fields["fld.1.13"] = str(int(next_proj_receipts))
    fields["fld.1.14"] = str(int(next_proj_disbursements))
    fields["fld.1.15"] = str(int(next_proj_net))

    return fields, {
        "opening": opening,
        "receipts": receipts,
        "disbursements": disbursements,
        "net_cf": net_cf,
        "ending": ending,
    }


# ============================================================
# 3. FORM FILLER
# ============================================================

def fill_mor_form(template_path, field_values, output_path):
    """Fill the MOR form by drawing text/marks directly onto template pages.

    Instead of setting PDF form field values (which render inconsistently
    across viewers), this function:
      1. Strips all form annotations from the template pages
      2. Creates transparent overlays with text drawn at exact field positions
      3. Merges overlays onto the stripped template pages

    The result is a flat PDF that looks identical in every viewer.
    """
    from reportlab.pdfgen import canvas as rl_canvas

    reader = PdfReader(template_path)

    # Field-position map gathered from template annotation Rect values.
    # Format: (page, x, y, width, font_size, alignment)
    TEXT_FIELDS = {
        # Page 0 — header
        "Text1.0":       (0, 110, 559, 103, 10, "L"),
        "Text1.1":       (0, 484, 559, 66, 9, "L"),
        "Text1.2":       (0, 110, 534, 124, 10, "L"),
        "Text1.4":       (0, 185, 467, 200, 9, "L"),
        "Bankruptcy District Information": (0, 161, 705, 160, 8, "L"),
        # Debtor 1 & Case number on each page
        "Debtor 1_p0":   (0, 82, 730, 255, 9, "L"),
        "Case number_p0":(0, 84, 683, 165, 9, "L"),
        "Debtor 1_p1":   (1, 84, 736, 255, 9, "L"),
        "Case number_p1":(1, 409, 736, 165, 9, "L"),
        "Debtor 1_p2":   (2, 83, 736, 255, 9, "L"),
        "Case number_p2":(2, 409, 736, 165, 9, "L"),
        "Debtor 1_p3":   (3, 83, 736, 255, 9, "L"),
        "Case number_p3":(3, 409, 736, 165, 9, "L"),
        # Page 1 — Cash Activity (right-aligned numbers)
        "fld.1.0":       (1, 521, 600, 51, 9, "R"),
        "fld.1.1":       (1, 432, 491, 51, 9, "R"),
        "fld.1.2":       (1, 436, 399, 51, 9, "R"),
        "fld.1.3":       (1, 521, 359, 51, 9, "R"),
        "fld.1.4":       (1, 521, 291, 51, 9, "R"),
        # Page 2 — Employees
        "fld.1.10":      (2, 524, 549, 52, 9, "R"),
        "fld.1.11":      (2, 524, 532, 52, 9, "R"),
        # Page 2 — Professional fees
        "fld.1.7":       (2, 524, 467, 52, 9, "R"),
        "fld.1.8":       (2, 524, 450, 52, 9, "R"),
        "fld.1.9":       (2, 524, 430, 52, 9, "R"),
        "fld.1.12":      (2, 524, 410, 52, 9, "R"),
        # Page 2 — Projections Section 7
        "fld.1.16.0":    (2, 192, 223, 52, 8, "R"),
        "fld.1.17.0":    (2, 306, 223, 52, 8, "R"),
        "fld.1.17.2":    (2, 414, 223, 52, 8, "R"),
        "fld.1.16.1":    (2, 192, 204, 52, 8, "R"),
        "fld.1.16.3":    (2, 306, 204, 52, 8, "R"),
        "fld.1.17.3":    (2, 414, 204, 52, 8, "R"),
        "fld.1.16.2":    (2, 192, 181, 52, 8, "R"),
        "fld.1.17.1":    (2, 306, 181, 52, 8, "R"),
        "fld.1.18.0":    (2, 414, 181, 52, 8, "R"),
        # Page 2 — Next month projections
        "fld.1.13":      (2, 524, 153, 52, 9, "R"),
        "fld.1.14":      (2, 524, 132, 52, 9, "R"),
        "fld.1.15":      (2, 527, 109, 55, 9, "R"),
    }

    # Yes/No/NA checkbox positions: (page, yes_x, no_x, na_x, center_y)
    CHECKBOXES = {
        "Check Box.0.0":  (0, 512.3, 544.3, 575.7, 341.6),
        "Check Box.1.0":  (0, 512.3, 544.3, 575.7, 326.1),
        "Check Box.2.0":  (0, 512.3, 544.3, 575.7, 308.6),
        "Check Box.3.0":  (0, 512.3, 544.3, 575.7, 291.2),
        "Check Box.4.0":  (0, 512.3, 544.3, 575.7, 274.5),
        "Check Box.5.0":  (0, 512.3, 544.3, 575.7, 258.0),
        "Check Box.6.0":  (0, 512.3, 544.3, 575.7, 240.5),
        "Check Box.7.0":  (0, 512.3, 544.3, 575.7, 223.0),
        "Check Box.8.0":  (0, 512.3, 544.3, 575.7, 206.5),
        "Check Box.9.0":  (0, 512.3, 544.3, 575.7, 171.9),
        "Check Box.10.0": (0, 512.3, 544.3, 575.7, 152.4),
        "Check Box.11.0": (0, 512.3, 544.3, 575.7, 133.9),
        "Check Box.12.0": (0, 512.3, 544.3, 575.7, 115.4),
        "Check Box.13.0": (0, 512.3, 544.3, 575.7, 97.4),
        "Check Box.14.0": (0, 512.3, 544.3, 575.7, 79.9),
        "Check Box.15.0": (0, 512.3, 544.3, 575.7, 62.4),
        "Check Box.16.0": (1, 511.2, 544.2, 575.7, 700.3),
        "Check Box.17.0": (1, 511.2, 544.2, 575.7, 682.8),
    }

    # Page 3 — additional info checkboxes (single checkbox each)
    SINGLE_CHECKBOXES = {
        "Check Box.18.0": (3, 57.9, 652.3),
        "Check Box.18.1": (3, 57.9, 629.2),
        "Check Box.18.2": (3, 57.9, 605.0),
        "Check Box.18.3": (3, 57.9, 580.9),
        "Check Box.18.4": (3, 57.9, 556.8),
    }

    # Build per-page overlay PDFs
    page_overlays = {}

    for page_idx in range(4):
        buf = BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=letter)

        # Draw text fields for this page
        for field_key, (pg, x, y, w, fsize, align) in TEXT_FIELDS.items():
            if pg != page_idx:
                continue
            base_key = field_key.split("_p")[0]
            val = field_values.get(field_key) or field_values.get(base_key, "")
            if not val:
                continue
            c.setFont("Helvetica", fsize)
            if align == "R":
                c.drawRightString(x + w, y + 2, val)
            elif align == "C":
                c.drawCentredString(x + w / 2, y + 2, val)
            else:
                c.drawString(x, y + 2, val)

        # Draw Yes/No checkboxes for this page
        for cb_key, (pg, yes_x, no_x, na_x, cy) in CHECKBOXES.items():
            if pg != page_idx:
                continue
            val = field_values.get(cb_key, "/Off")
            if val == "/Yes":
                _draw_checkmark(c, yes_x, cy)
            elif val == "/No":
                _draw_checkmark(c, no_x, cy)

        # Draw single checkboxes (page 3)
        for cb_key, (pg, cx, cy) in SINGLE_CHECKBOXES.items():
            if pg != page_idx:
                continue
            val = field_values.get(cb_key, "/Off")
            if val == "/Yes":
                _draw_checkmark(c, cx, cy)

        c.save()
        buf.seek(0)
        page_overlays[page_idx] = buf

    # Strip annotations and merge overlays
    writer = PdfWriter()

    for page_idx in range(min(4, len(reader.pages))):
        base_page = reader.pages[page_idx]

        # Remove form annotations so fields don't appear as editable
        if "/Annots" in base_page:
            del base_page["/Annots"]

        # Merge overlay
        if page_idx in page_overlays:
            overlay_reader = PdfReader(page_overlays[page_idx])
            base_page.merge_page(overlay_reader.pages[0])

        writer.add_page(base_page)

    # Remove AcroForm from document root if present
    if "/AcroForm" in writer._root_object:
        del writer._root_object["/AcroForm"]

    with open(output_path, "wb") as f:
        writer.write(f)


def _draw_checkmark(canvas, cx, cy):
    """Draw an X mark at the given center coordinates."""
    size = 4
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setLineWidth(1.5)
    canvas.line(cx - size, cy - size, cx + size, cy + size)
    canvas.line(cx - size, cy + size, cx + size, cy - size)


# ============================================================
# 4. EXHIBIT GENERATOR
# ============================================================

def create_exhibit_pdf(deposits, withdrawals, checks, month_label):
    """Create Exhibit C (deposits) and Exhibit D (withdrawals) as a PDF buffer.

    Returns a BytesIO with the exhibit pages.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.5 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ExTitle", parent=styles["Title"], fontSize=16, spaceAfter=6)
    header_style = ParagraphStyle("ExHeader", parent=styles["Heading2"], fontSize=12, spaceAfter=12)

    story = []
    col_widths = [60, 340, 80]

    # Exhibit C (Deposits)
    story.append(Paragraph("Exhibit C", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Deposits &amp; Credits — {month_label}", header_style))
    story.append(Spacer(1, 12))

    dep_data = [["Date", "Description", "Deposit"]]
    dep_total = 0.0
    for date, desc, amt in deposits:
        dep_data.append([date, desc, f"${amt:,.2f}"])
        dep_total += amt
    dep_data.append(["", "TOTAL", f"${dep_total:,.2f}"])

    t = Table(dep_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, 0), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(PageBreak())

    # Exhibit D (Withdrawals + Checks)
    story.append(Paragraph("Exhibit D", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Withdrawals &amp; Debits — {month_label}", header_style))
    story.append(Spacer(1, 12))

    wd_data = [["Date", "Description", "Withdrawal"]]
    wd_total = 0.0
    for date, desc, amt in withdrawals:
        wd_data.append([date, desc, f"${amt:,.2f}"])
        wd_total += amt

    if checks:
        wd_data.append(["", "", ""])
        wd_data.append(["", "CHECKS", ""])

        month_abbrevs = {
            "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
            "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
            "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
        }
        sorted_checks = sorted(checks, key=lambda c: (c[1], c[0]))
        for check_no, date_str, amt in sorted_checks:
            mm, dd = date_str.split("/")
            friendly_date = f"{month_abbrevs.get(mm, mm)} {dd}"
            wd_data.append([friendly_date, f"Check #{check_no}", f"${amt:,.2f}"])
            wd_total += amt

    wd_data.append(["", "TOTAL", f"${wd_total:,.2f}"])

    t2 = Table(wd_data, colWidths=col_widths, repeatRows=1)

    checks_row = None
    for i, row in enumerate(wd_data):
        if row[1] == "CHECKS":
            checks_row = i
            break

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]
    if checks_row is not None:
        style_cmds.append(("FONTNAME", (0, checks_row), (-1, checks_row), "Helvetica-Bold"))

    t2.setStyle(TableStyle(style_cmds))
    story.append(t2)
    story.append(PageBreak())

    # Bank Statement cover page
    story.append(Paragraph("Exhibit Bank Statement", title_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ============================================================
# 5. PDF MERGER
# ============================================================

def merge_pdfs(form_path, exhibit_buffer, bank_stmt_path, output_path):
    """Merge filled form + exhibits + bank statement into one PDF."""
    writer = PdfWriter()

    for page in PdfReader(form_path).pages:
        writer.add_page(page)

    for page in PdfReader(exhibit_buffer).pages:
        writer.add_page(page)

    for page in PdfReader(bank_stmt_path).pages:
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)
