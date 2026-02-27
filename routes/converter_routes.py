"""
Converter Routes — Bank statement converter, MOR builder, file history.
"""

import hashlib
import os
import tempfile

from flask import Blueprint, jsonify, request, g, send_file
from middleware.tenant_context_separate_db import login_required, organization_required, log_audit
from db_manager import get_org_db, org_db, BASE_DIR

converter_bp = Blueprint('converter', __name__, url_prefix='/api/converter')

UPLOAD_BASE = os.path.join(BASE_DIR, 'static', 'uploads', 'converter')
TEMPLATE_PATH = os.path.join(BASE_DIR, 'static', 'templates', 'mor_template.pdf')


def _org_upload_dir(org_id, subdir='uploads'):
    """Get and create upload directory for an org."""
    path = os.path.join(UPLOAD_BASE, f'org_{org_id}', subdir)
    os.makedirs(path, exist_ok=True)
    return path


def _file_hash(filepath):
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


@converter_bp.route('/download/<int:file_id>')
@login_required
@organization_required
def download_file(file_id):
    """Download a file by its history ID."""
    with org_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM converter_file_history WHERE id = ?", (file_id,))
        row = cursor.fetchone()

    if not row:
        return jsonify({'error': 'File not found'}), 404

    file_data = dict(row)
    filepath = file_data['stored_filepath']

    if not os.path.exists(filepath):
        return jsonify({'error': 'File no longer exists on disk'}), 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=file_data['original_filename'],
    )


# ============================================================
# MOR BUILDER
# ============================================================

@converter_bp.route('/mor/generate', methods=['POST'])
@login_required
@organization_required
def generate_mor():
    """Full MOR generation pipeline."""
    from utils.converter.pdf_extractors import parse_bank_statement, verify_parsed_totals
    from utils.converter.mor_builder import (
        parse_previous_mor, build_field_values, fill_mor_form,
        create_exhibit_pdf, merge_pdfs,
    )

    if 'bank_statement' not in request.files:
        return jsonify({'error': 'bank_statement file is required'}), 400

    month_year = request.form.get('month_year', '')
    if not month_year:
        return jsonify({'error': 'month_year is required'}), 400

    report_date = request.form.get('report_date', '')
    proj_receipts = request.form.get('proj_receipts', 0, type=float)
    proj_disbursements = request.form.get('proj_disbursements', 0, type=float)
    responsible = request.form.get('responsible', '')
    opening_balance = request.form.get('opening_balance', type=float)

    org_id = g.organization['id']
    user_id = g.user['id'] if g.user else None
    mor_dir = _org_upload_dir(org_id, 'mor')
    upload_dir = _org_upload_dir(org_id, 'uploads')

    # Save bank statement
    bs_file = request.files['bank_statement']
    safe_bs = bs_file.filename.replace('..', '').replace('/', '_')
    bs_path = os.path.join(upload_dir, f"bs_{month_year}_{safe_bs}")
    bs_file.save(bs_path)

    # Record bank statement upload
    bs_size = os.path.getsize(bs_path)
    with org_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO converter_file_history
            (file_type, file_category, original_filename, stored_filepath,
             file_size_bytes, month_year, created_by)
            VALUES ('bank_statement', 'uploaded', ?, ?, ?, ?, ?)
        """, (safe_bs, bs_path, bs_size, month_year, user_id))
        conn.commit()
        bs_file_id = cursor.lastrowid

    # Parse bank statement
    try:
        bank_data = parse_bank_statement(bs_path)
    except Exception as e:
        return jsonify({'error': f'Failed to parse bank statement: {e}'}), 400

    verification = verify_parsed_totals(bank_data)

    # Get previous MOR carryover
    prev_mor = None

    if 'prev_mor' in request.files:
        pm_file = request.files['prev_mor']
        if pm_file.filename:
            safe_pm = pm_file.filename.replace('..', '').replace('/', '_')
            prev_mor_path = os.path.join(upload_dir, f"prevmor_{month_year}_{safe_pm}")
            pm_file.save(prev_mor_path)
            try:
                prev_mor = parse_previous_mor(prev_mor_path)
            except Exception as e:
                return jsonify({'error': f'Failed to parse previous MOR: {e}'}), 400

    # If no uploaded previous MOR, try DB carryover
    if prev_mor is None:
        with org_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM converter_mor_log
                WHERE month_year < ?
                ORDER BY month_year DESC LIMIT 1
            """, (month_year,))
            prev_row = cursor.fetchone()

        if prev_row:
            prev_data = dict(prev_row)
            org_name = g.organization.get('organization_name', '')
            prev_mor = {
                "ending_balance": prev_data.get('line_23_ending_balance', 0) or 0,
                "proj_receipts": prev_data.get('proj_receipts', 0) or 0,
                "proj_disbursements": prev_data.get('proj_disbursements', 0) or 0,
                "proj_net": (prev_data.get('proj_receipts', 0) or 0) - (prev_data.get('proj_disbursements', 0) or 0),
                "prof_fees_filing": prev_data.get('prof_fees_cumulative', 0) or 0,
                "employees_filed": prev_data.get('employees_current', '28'),
                "employees_current": prev_data.get('employees_current', '30'),
                "questionnaire": {},
                "case_info": {
                    "Debtor 1": org_name,
                    "Text1.2": "Food service",
                },
            }
        else:
            # First-time — use org info
            org_name = g.organization.get('organization_name', '')
            prev_mor = {
                "ending_balance": 0,
                "proj_receipts": 0,
                "proj_disbursements": 0,
                "proj_net": 0,
                "prof_fees_filing": 0,
                "employees_filed": "28",
                "employees_current": "30",
                "questionnaire": {},
                "case_info": {
                    "Debtor 1": org_name,
                    "Text1.2": "Food service",
                },
            }

    # Fill MOR form
    template = TEMPLATE_PATH
    if not os.path.exists(template):
        return jsonify({'error': 'MOR template not found'}), 500

    # Parse template for questionnaire/case info fallback
    # (needed when prev_mor was itself generated and lost checkbox names)
    template_fields = parse_previous_mor(template)

    # Build field values
    fields, cash = build_field_values(
        prev_mor, bank_data, report_date,
        proj_receipts, proj_disbursements,
        responsible_name=responsible or None,
        opening_override=opening_balance,
        template_fields=template_fields,
    )

    form_tmp = os.path.join(mor_dir, f"mor_form_{month_year}.pdf")
    fill_mor_form(template, fields, form_tmp)

    # Generate exhibits
    month_label = f"{bank_data['month_name']} {bank_data['year']}"
    exhibit_buf = create_exhibit_pdf(
        bank_data["deposits"], bank_data["withdrawals"],
        bank_data["checks"], month_label
    )

    # Merge final PDF
    final_path = os.path.join(mor_dir, f"MOR_{month_year}.pdf")
    merge_pdfs(form_tmp, exhibit_buf, bs_path, final_path)

    # Clean up temp form file
    if os.path.exists(form_tmp):
        os.remove(form_tmp)

    # Write JSON sidecar with carryover values (for reliable chained generation)
    import json as _json
    sidecar = {
        "ending_balance": cash["ending"],
        "proj_receipts": proj_receipts,
        "proj_disbursements": proj_disbursements,
        "proj_net": round(proj_receipts - proj_disbursements, 2),
        "prof_fees_filing": prev_mor.get("prof_fees_filing", 0),
        "employees_filed": prev_mor.get("employees_filed", "28"),
        "employees_current": prev_mor.get("employees_current", "30"),
        "questionnaire": {
            k: fields[k] for k in fields if k.startswith("Check Box.")
        },
        "case_info": {
            "Debtor 1": fields.get("Debtor 1", ""),
            "Case number": fields.get("Case number", ""),
            "Bankruptcy District Information": fields.get(
                "Bankruptcy District Information", ""
            ),
            "Text1.2": fields.get("Text1.2", ""),
            "Check if this is an amended": fields.get(
                "Check if this is an amended", "/Off"
            ),
        },
    }
    json_sidecar_path = os.path.splitext(final_path)[0] + ".json"
    with open(json_sidecar_path, "w") as jf:
        _json.dump(sidecar, jf, indent=2)

    # Record generated files in history
    final_size = os.path.getsize(final_path)
    with org_db() as conn:
        cursor = conn.cursor()

        # MOR file
        cursor.execute("""
            INSERT INTO converter_file_history
            (file_type, file_category, original_filename, stored_filepath,
             file_size_bytes, month_year, created_by)
            VALUES ('mor', 'generated', ?, ?, ?, ?, ?)
        """, (f"MOR_{month_year}.pdf", final_path, final_size, month_year, user_id))
        mor_file_id = cursor.lastrowid

        # MOR log
        cursor.execute("""
            INSERT OR REPLACE INTO converter_mor_log
            (month_year, report_date,
             line_19_opening_balance, line_20_receipts, line_21_disbursements,
             line_22_net_cash_flow, line_23_ending_balance,
             proj_receipts, proj_disbursements, proj_net,
             employees_current, responsible_party,
             bank_statement_file_id, mor_file_id,
             verification_deposits_ok, verification_withdrawals_ok,
             created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            month_year, report_date,
            cash['opening'], cash['receipts'], cash['disbursements'],
            cash['net_cf'], cash['ending'],
            proj_receipts, proj_disbursements,
            round(proj_receipts - proj_disbursements, 2),
            prev_mor.get('employees_current', '30'),
            responsible or None,
            bs_file_id, mor_file_id,
            1 if verification.get('deposits_ok', True) else 0,
            1 if verification.get('withdrawals_ok', True) else 0,
            user_id,
        ))
        conn.commit()

    log_audit('CREATE', 'converter_mor', mor_file_id, f"MOR {month_year}", 'Generated Monthly Operating Report')

    return jsonify({
        'success': True,
        'cash_activity': cash,
        'verification': verification,
        'files': {
            'mor': {'file_id': mor_file_id, 'filename': f"MOR_{month_year}.pdf"},
            'bank_statement': {'file_id': bs_file_id},
        },
        'month_label': month_label,
    })


@converter_bp.route('/mor/history')
@login_required
@organization_required
def mor_history():
    """Get MOR generation log."""
    with org_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM converter_mor_log
            ORDER BY month_year DESC
            LIMIT 24
        """)
        rows = [dict(r) for r in cursor.fetchall()]
    return jsonify({'success': True, 'history': rows})


@converter_bp.route('/mor/previous-balance/<month_year>')
@login_required
@organization_required
def previous_balance(month_year):
    """Get previous month's Line 23 ending balance for auto-population."""
    with org_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT line_23_ending_balance, proj_receipts, proj_disbursements
            FROM converter_mor_log
            WHERE month_year < ?
            ORDER BY month_year DESC LIMIT 1
        """, (month_year,))
        row = cursor.fetchone()

    if not row:
        return jsonify({'success': True, 'found': False, 'balance': 0})

    data = dict(row)
    return jsonify({
        'success': True,
        'found': True,
        'balance': data.get('line_23_ending_balance', 0),
        'prev_proj_receipts': data.get('proj_receipts', 0),
        'prev_proj_disbursements': data.get('proj_disbursements', 0),
    })


@converter_bp.route('/mor/parse-previous', methods=['POST'])
@login_required
@organization_required
def parse_previous_mor_endpoint():
    """Upload a previous MOR PDF and get back extracted carryover values."""
    from utils.converter.mor_builder import parse_previous_mor

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    # Save to temp
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    try:
        file.save(tmp.name)
        prev_data = parse_previous_mor(tmp.name)
        return jsonify({'success': True, 'carryover': prev_data})
    except Exception as e:
        return jsonify({'error': f'Failed to parse MOR: {e}'}), 400
    finally:
        os.unlink(tmp.name)


# ============================================================
# FILE HISTORY
# ============================================================

@converter_bp.route('/history')
@login_required
@organization_required
def file_history():
    """List converter files with optional filters."""
    file_type = request.args.get('file_type')
    month_year = request.args.get('month_year')
    limit = request.args.get('limit', 100, type=int)

    query = "SELECT * FROM converter_file_history WHERE 1=1"
    params = []

    if file_type:
        query += ' AND file_type = ?'
        params.append(file_type)
    if month_year:
        query += ' AND month_year = ?'
        params.append(month_year)

    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)

    with org_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

    return jsonify({'success': True, 'files': rows})


@converter_bp.route('/history/<int:file_id>', methods=['DELETE'])
@login_required
@organization_required
def delete_file_history(file_id):
    """Delete a file entry and its physical file."""
    with org_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM converter_file_history WHERE id = ?", (file_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'File not found'}), 404

        file_data = dict(row)
        filepath = file_data['stored_filepath']

        # Delete physical file
        if filepath and os.path.exists(filepath):
            os.remove(filepath)

        # Delete DB record
        cursor.execute("DELETE FROM converter_file_history WHERE id = ?", (file_id,))
        conn.commit()

    log_audit('DELETE', 'converter_file', file_id, file_data.get('original_filename', ''), 'Deleted converter file')
    return jsonify({'success': True})


# ============================================================
# STATS
# ============================================================

@converter_bp.route('/stats')
@login_required
@organization_required
def converter_stats():
    """Get converter stats for dashboard card."""
    with org_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as cnt FROM converter_file_history")
        file_count = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) as cnt FROM converter_mor_log")
        mor_count = cursor.fetchone()['cnt']

    return jsonify({
        'success': True,
        'files': file_count,
        'mors': mor_count,
    })
