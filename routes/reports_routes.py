"""
Reports Routes — centralized report center API.
"""

from flask import Blueprint, jsonify, request, make_response, g
from middleware.tenant_context_separate_db import login_required, organization_required, log_audit

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@reports_bp.route('/catalog')
@login_required
@organization_required
def report_catalog():
    """List all available reports grouped by category."""
    from utils.report_registry import list_reports, get_categories

    categories = get_categories()
    grouped = {}
    for cat in categories:
        grouped[cat] = [{
            'key': r['key'],
            'name': r['name'],
            'category': r['category'],
            'description': r['description'],
            'chart_type': r.get('chart_type'),
            'columns': r.get('columns', []),
        } for r in list_reports(category=cat)]

    return jsonify({
        'success': True,
        'categories': categories,
        'reports': grouped,
        'total': sum(len(v) for v in grouped.values()),
    })


@reports_bp.route('/<key>/generate')
@login_required
@organization_required
def generate_report(key):
    """Download a report in CSV, XLSX, or PDF format."""
    from utils.report_registry import get_report
    from utils.report_formatters import generate_csv, generate_xlsx, generate_pdf

    report = get_report(key)
    if not report:
        return jsonify({'error': f'Unknown report: {key}'}), 404

    fmt = request.args.get('format', 'csv').lower()
    if fmt not in ('csv', 'xlsx', 'pdf'):
        return jsonify({'error': 'Format must be csv, xlsx, or pdf'}), 400

    # Gather filter params
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    kwargs = {}
    if date_from:
        kwargs['date_from'] = date_from
    if date_to:
        kwargs['date_to'] = date_to

    # Generate data
    try:
        headers, rows = report['data_fn'](**kwargs)
    except Exception as e:
        return jsonify({'error': f'Failed to generate report data: {str(e)}'}), 500

    # Format output
    report_meta = {
        'key': report['key'],
        'name': report['name'],
        'category': report['category'],
        'description': report['description'],
    }

    generators = {'csv': generate_csv, 'xlsx': generate_xlsx, 'pdf': generate_pdf}
    try:
        file_bytes, mime_type, extension = generators[fmt](headers, rows, report_meta)
    except ImportError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to format report: {str(e)}'}), 500

    # Audit log
    log_audit('report_exported', 'report', None, {
        'report_key': key,
        'format': fmt,
        'row_count': len(rows),
        'date_from': date_from,
        'date_to': date_to,
    })

    filename = f"{key}.{extension}"
    response = make_response(file_bytes)
    response.headers['Content-Type'] = mime_type
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@reports_bp.route('/<key>/preview')
@login_required
@organization_required
def preview_report(key):
    """JSON preview of a report (first 50 rows)."""
    from utils.report_registry import get_report

    report = get_report(key)
    if not report:
        return jsonify({'error': f'Unknown report: {key}'}), 404

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    kwargs = {}
    if date_from:
        kwargs['date_from'] = date_from
    if date_to:
        kwargs['date_to'] = date_to

    try:
        headers, rows = report['data_fn'](**kwargs)
    except Exception as e:
        return jsonify({'error': f'Failed to generate preview: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'report': {
            'key': report['key'],
            'name': report['name'],
            'category': report['category'],
            'description': report['description'],
            'chart_type': report.get('chart_type'),
        },
        'headers': headers,
        'rows': rows[:50],
        'total_rows': len(rows),
        'truncated': len(rows) > 50,
    })


@reports_bp.route('/history')
@login_required
@organization_required
def report_history():
    """Recent export audit log entries for this org."""
    from db_manager import get_master_db

    limit = min(int(request.args.get('limit', 50)), 200)

    conn = get_master_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT al.action, al.changes, al.created_at, u.first_name, u.last_name
        FROM audit_log al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.organization_id = ?
          AND al.action IN ('report_exported', 'csv_exported')
        ORDER BY al.created_at DESC
        LIMIT ?
    """, (g.organization['id'], limit))

    entries = []
    for row in cursor.fetchall():
        import json
        changes = {}
        if row['changes']:
            try:
                changes = json.loads(row['changes'])
            except (json.JSONDecodeError, TypeError):
                pass
        entries.append({
            'action': row['action'],
            'report_key': changes.get('report_key') or changes.get('widget', ''),
            'format': changes.get('format', 'csv'),
            'exported_by': f"{row['first_name']} {row['last_name']}".strip(),
            'exported_at': row['created_at'],
        })

    conn.close()

    return jsonify({'success': True, 'history': entries})
