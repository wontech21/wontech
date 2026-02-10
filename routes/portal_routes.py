"""
Portal Routes
- Index / landing page
- Employee clock terminal (login, clock, logout)
- Employee portal
- Dashboard pages
- Test scanner
"""

from flask import Blueprint, jsonify, request, session, redirect, render_template, g

from db_manager import get_master_db, get_org_db
from middleware.tenant_context_separate_db import login_required, organization_required

portal_bp = Blueprint('portal', __name__)


@portal_bp.route('/')
def index():
    """Main dashboard - redirect based on authentication"""
    if 'user_id' not in session:
        return redirect('/login')

    # Redirect all authenticated users to dashboard
    return redirect('/dashboard')

@portal_bp.route('/clock/<int:org_id>')
def employee_clock_login_page_with_org(org_id):
    """Clock terminal login for specific organization"""
    # Verify organization exists and set context
    master_conn = get_master_db()
    cursor = master_conn.cursor()
    cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
    org = cursor.fetchone()
    master_conn.close()

    if not org:
        return "Organization not found", 404

    # Store org in session for clock terminal
    session['clock_org_id'] = org['id']

    # Set g.organization for template
    g.organization = dict(org)

    # If already logged in, go to clock page
    if 'clock_employee_id' in session:
        return redirect('/employee/clock')

    return render_template('employee_clock_login.html')

@portal_bp.route('/employee/clock/login-page')
def employee_clock_login_page():
    """Show employee code login page for clock terminal"""
    # If already logged in via clock terminal, redirect to clock page
    if 'clock_employee_id' in session and 'clock_org_id' in session:
        return redirect('/employee/clock')

    # Check if org is in session from previous access
    if 'clock_org_id' in session:
        master_conn = get_master_db()
        cursor = master_conn.cursor()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (session['clock_org_id'],))
        org = cursor.fetchone()
        master_conn.close()
        if org:
            g.organization = dict(org)
            return render_template('employee_clock_login.html')

    # Check if organization context is available from middleware
    if hasattr(g, 'organization') and g.organization:
        session['clock_org_id'] = g.organization['id']
        return render_template('employee_clock_login.html')

    # No organization context - provide help
    return """
    <html>
    <head><title>Clock Terminal</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; min-height: 100vh; }
        .box { background: white; color: #333; padding: 40px; border-radius: 20px; max-width: 600px; margin: 0 auto; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        a { color: #667eea; text-decoration: none; font-weight: bold; }
        code { background: #f4f4f4; padding: 5px 10px; border-radius: 5px; color: #667eea; }
    </style>
    </head>
    <body>
        <div class="box">
            <h1>⏰ Clock Terminal</h1>
            <p>To access the clock terminal, use:</p>
            <p><code>http://localhost:5001/clock/1</code></p>
            <p style="font-size: 0.9em; color: #666;">(Replace '1' with your organization ID)</p>
            <br>
            <a href="/login">← Back to Main Login</a>
        </div>
    </body>
    </html>
    """, 200

@portal_bp.route('/employee/clock/login', methods=['POST'])
def employee_clock_login():
    """Authenticate employee by code for clock terminal"""
    data = request.json
    employee_code = data.get('employee_code', '').strip()

    if not employee_code:
        return jsonify({'error': 'Employee code required'}), 400

    # Get organization ID from session or g context
    org_id = session.get('clock_org_id')
    if not org_id and hasattr(g, 'organization') and g.organization:
        org_id = g.organization['id']

    if not org_id:
        return jsonify({'error': 'Organization context required. Please refresh the page.'}), 400

    # Get organization database connection
    import sqlite3
    from db_manager import get_org_db_path

    org_db_path = get_org_db_path(org_id)
    conn = sqlite3.connect(org_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find employee by code
    cursor.execute("""
        SELECT *
        FROM employees
        WHERE employee_code = ? AND organization_id = ? AND status = 'active'
    """, (employee_code, org_id))

    employee = cursor.fetchone()
    conn.close()

    if not employee:
        return jsonify({'error': 'Invalid employee code'}), 401

    # Create session for clock terminal (limited access)
    session['clock_employee_id'] = employee['id']
    session['clock_employee_code'] = employee['employee_code']
    session['clock_employee_name'] = f"{employee['first_name']} {employee['last_name']}"
    session['organization_id'] = org_id
    session['clock_org_id'] = org_id  # Store for clock terminal access

    return jsonify({'success': True, 'message': 'Login successful'})

@portal_bp.route('/employee/clock')
def employee_clock_terminal():
    """Simple clock in/out terminal - employee code authenticated"""
    # Get org_id from session for redirect
    org_id = session.get('clock_org_id', 1)

    # Check if authenticated via employee code
    if 'clock_employee_id' not in session:
        return redirect(f'/clock/{org_id}')

    # Verify organization context
    if 'organization_id' not in session:
        return redirect(f'/clock/{org_id}')

    # Get employee info from session
    employee_info = {
        'id': session.get('clock_employee_id'),
        'employee_code': session.get('clock_employee_code'),
        'first_name': session.get('clock_employee_name', '').split()[0] if session.get('clock_employee_name') else '',
        'last_name': ' '.join(session.get('clock_employee_name', '').split()[1:]) if session.get('clock_employee_name') else ''
    }

    # Set g.user for template context (clock terminal mode)
    g.user = {
        'id': session.get('clock_employee_id'),
        'first_name': employee_info['first_name'],
        'last_name': employee_info['last_name'],
        'role': 'employee'
    }

    return render_template('employee_portal.html', is_clock_terminal=True)

@portal_bp.route('/employee/clock/logout')
def employee_clock_logout():
    """Logout from clock terminal"""
    # Get org_id before clearing session
    org_id = session.get('clock_org_id', 1)  # Default to org 1 if not found

    # Clear employee session but keep organization context
    session.pop('clock_employee_id', None)
    session.pop('clock_employee_code', None)
    session.pop('clock_employee_name', None)
    # Keep clock_org_id and organization_id in session

    return redirect(f'/clock/{org_id}')

@portal_bp.route('/employee/portal')
@login_required
@organization_required
def employee_portal():
    """Comprehensive employee portal with email/password login"""
    # Verify user is an employee
    if not hasattr(g, 'user') or not g.user or g.user.get('role') != 'employee':
        return redirect('/dashboard')

    # Get employee record for the logged-in user
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM employees
        WHERE user_id = ? AND organization_id = ?
    """, (g.user['id'], g.organization['id']))

    employee = cursor.fetchone()
    conn.close()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return render_template('employee/portal.html', employee=dict(employee), is_clock_terminal=False)

@portal_bp.route('/dashboard')
@login_required
def dashboard_home():
    """Landing page showing Inventory & Sales and Attendance Management sections"""
    return render_template('dashboard_home.html')

@portal_bp.route('/dashboard/<section>')
@login_required
def dashboard_section(section):
    """Dashboard filtered to specific section (inventory, attendance, or pos)"""
    if section not in ['inventory', 'attendance', 'pos', 'kitchen']:
        return redirect('/dashboard')

    if section == 'pos':
        return render_template('pos_home.html')

    if section == 'kitchen':
        return render_template('kitchen.html')

    return render_template('dashboard.html', section=section)

@portal_bp.route('/dashboard/pos/<subsection>')
@login_required
def pos_section(subsection):
    """POS sub-pages: register, orders, settings"""
    if subsection == 'register':
        return render_template('pos.html')
    elif subsection == 'orders':
        return render_template('pos_orders.html')
    elif subsection == 'settings':
        return render_template('pos_settings.html')
    return redirect('/dashboard/pos')

@portal_bp.route('/test-scanner')
def test_scanner():
    """Barcode scanner diagnostic page"""
    return render_template('test_scanner.html')
