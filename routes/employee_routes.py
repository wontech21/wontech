"""
Employee Self-Service Portal Routes
- View own profile
- Clock in/out
- View own paystubs
- View own time entries
- Update personal information
"""

from flask import Blueprint, jsonify, request, g, render_template
import sqlite3
import os
from datetime import datetime, timedelta

# Import organization database connection
from db_manager import get_org_db

from middleware import (
    login_required,
    organization_required,
    permission_required,
    own_data_only,
    log_audit
)

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

# Use get_org_db() from db_manager - no local get_db() needed
# All employee routes query organization-specific databases

def get_current_employee():
    """Get employee record for current user"""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM employees
        WHERE user_id = ? AND organization_id = ?
    """, (g.user['id'], g.organization['id']))

    employee = cursor.fetchone()
    conn.close()

    if not employee:
        return None

    return dict(employee)

# ==========================================
# EMPLOYEE PORTAL DASHBOARD
# ==========================================

@employee_bp.route('/portal')
@login_required
@organization_required
def employee_portal():
    """Employee self-service portal homepage"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return render_template('employee_portal.html', employee=employee)

# ==========================================
# PROFILE MANAGEMENT
# ==========================================

@employee_bp.route('/profile')
@login_required
@organization_required
@permission_required('employees.view_own')
def get_own_profile():
    """Get current employee's profile"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return jsonify({'employee': employee})

@employee_bp.route('/profile/update', methods=['PUT'])
@login_required
@organization_required
@permission_required('employees.edit_own')
def update_own_profile():
    """Update current employee's editable profile fields"""
    data = request.json
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    # Only allow updating certain fields
    allowed_fields = ['phone', 'address', 'city', 'state', 'zip_code', 'emergency_contact_name', 'emergency_contact_phone']
    update_fields = []
    update_values = []

    for field in allowed_fields:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if not update_fields:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400

    update_values.append(employee['id'])
    update_values.append(g.organization['id'])

    cursor.execute(f"""
        UPDATE employees
        SET {', '.join(update_fields)}
        WHERE id = ? AND organization_id = ?
    """, update_values)

    conn.commit()
    conn.close()

    log_audit('updated_own_profile', 'employee', employee['id'], data)

    return jsonify({'success': True, 'message': 'Profile updated successfully'})

# ==========================================
# TIME CLOCK
# ==========================================

@employee_bp.route('/clock/status')
@login_required
@organization_required
@permission_required('timeclock.clockin')
def get_clock_status():
    """Get current clock in/out status"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    # Check for open time entry (clocked in but not clocked out)
    cursor.execute("""
        SELECT * FROM time_entries
        WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
        ORDER BY clock_in DESC
        LIMIT 1
    """, (employee['id'], g.organization['id']))

    current_entry = cursor.fetchone()
    conn.close()

    if current_entry:
        return jsonify({
            'clocked_in': True,
            'entry': dict(current_entry)
        })
    else:
        return jsonify({
            'clocked_in': False,
            'entry': None
        })

@employee_bp.route('/clock/in', methods=['POST'])
@login_required
@organization_required
@permission_required('timeclock.clockin')
def clock_in():
    """Clock in for work"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    # Check if already clocked in
    cursor.execute("""
        SELECT id FROM time_entries
        WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
    """, (employee['id'], g.organization['id']))

    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Already clocked in'}), 400

    # Create new time entry
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO time_entries (organization_id, employee_id, clock_in)
        VALUES (?, ?, ?)
    """, (g.organization['id'], employee['id'], now))

    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_audit('clocked_in', 'time_entry', entry_id)

    return jsonify({
        'success': True,
        'entry_id': entry_id,
        'clock_in': now,
        'message': 'Clocked in successfully'
    })

@employee_bp.route('/clock/out', methods=['POST'])
@login_required
@organization_required
@permission_required('timeclock.clockin')
def clock_out():
    """Clock out from work"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    # Find open time entry
    cursor.execute("""
        SELECT * FROM time_entries
        WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
        ORDER BY clock_in DESC
        LIMIT 1
    """, (employee['id'], g.organization['id']))

    entry = cursor.fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Not clocked in'}), 400

    # Update time entry with clock out
    now = datetime.now().isoformat()

    # Calculate hours worked
    clock_in = datetime.fromisoformat(entry['clock_in'])
    clock_out = datetime.fromisoformat(now)
    hours_worked = (clock_out - clock_in).total_seconds() / 3600

    cursor.execute("""
        UPDATE time_entries
        SET clock_out = ?, hours_worked = ?
        WHERE id = ? AND organization_id = ?
    """, (now, hours_worked, entry['id'], g.organization['id']))

    conn.commit()
    conn.close()

    log_audit('clocked_out', 'time_entry', entry['id'], {
        'hours_worked': hours_worked
    })

    return jsonify({
        'success': True,
        'entry_id': entry['id'],
        'clock_out': now,
        'hours_worked': round(hours_worked, 2),
        'message': f'Clocked out successfully. Hours worked: {round(hours_worked, 2)}'
    })

# ==========================================
# TIME ENTRIES HISTORY
# ==========================================

@employee_bp.route('/time-entries')
@login_required
@organization_required
@permission_required('timeclock.view_own')
def get_own_time_entries():
    """Get current employee's time entries"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    # Get date range from query params (default to last 30 days)
    days = int(request.args.get('days', 30))
    start_date = (datetime.now() - timedelta(days=days)).isoformat()

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM time_entries
        WHERE employee_id = ? AND organization_id = ? AND clock_in >= ?
        ORDER BY clock_in DESC
    """, (employee['id'], g.organization['id'], start_date))

    entries = [dict(row) for row in cursor.fetchall()]

    # Calculate total hours
    total_hours = sum(entry['hours_worked'] or 0 for entry in entries)

    conn.close()

    return jsonify({
        'entries': entries,
        'total_hours': round(total_hours, 2),
        'period_days': days
    })

# ==========================================
# PAYSTUBS
# ==========================================

@employee_bp.route('/paystubs')
@login_required
@organization_required
@permission_required('payroll.view_own')
def get_own_paystubs():
    """Get current employee's paystubs"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    # Get paystubs for this employee
    cursor.execute("""
        SELECT
            p.*,
            pr.pay_period_start,
            pr.pay_period_end,
            pr.pay_date,
            pr.status as payroll_status
        FROM paychecks p
        JOIN payroll_runs pr ON p.payroll_run_id = pr.id
        WHERE p.employee_id = ? AND p.organization_id = ?
        ORDER BY pr.pay_date DESC
    """, (employee['id'], g.organization['id']))

    paystubs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'paystubs': paystubs,
        'count': len(paystubs)
    })

@employee_bp.route('/paystubs/<int:paycheck_id>')
@login_required
@organization_required
@permission_required('payroll.view_own')
@own_data_only('paycheck', 'paycheck_id')
def get_own_paystub_detail(paycheck_id):
    """Get detailed view of a specific paystub"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.*,
            pr.pay_period_start,
            pr.pay_period_end,
            pr.pay_date,
            pr.status as payroll_status,
            e.first_name,
            e.last_name,
            e.employee_code
        FROM paychecks p
        JOIN payroll_runs pr ON p.payroll_run_id = pr.id
        JOIN employees e ON p.employee_id = e.id
        WHERE p.id = ? AND p.employee_id = ? AND p.organization_id = ?
    """, (paycheck_id, employee['id'], g.organization['id']))

    paystub = cursor.fetchone()
    conn.close()

    if not paystub:
        return jsonify({'error': 'Paystub not found'}), 404

    return jsonify({'paystub': dict(paystub)})

# ==========================================
# SCHEDULE (If implemented)
# ==========================================

@employee_bp.route('/schedule')
@login_required
@organization_required
@permission_required('employees.view_own')
def get_own_schedule():
    """Get current employee's work schedule"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    # Get date range from query params
    start_date = request.args.get('start_date', datetime.now().date().isoformat())
    end_date = request.args.get('end_date', (datetime.now() + timedelta(days=14)).date().isoformat())

    conn = get_org_db()
    cursor = conn.cursor()

    # Check if schedule table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='schedules'
    """)

    if not cursor.fetchone():
        conn.close()
        return jsonify({
            'message': 'Schedule feature not yet implemented',
            'schedule': []
        })

    cursor.execute("""
        SELECT * FROM schedules
        WHERE employee_id = ? AND organization_id = ?
          AND date >= ? AND date <= ?
        ORDER BY date, start_time
    """, (employee['id'], g.organization['id'], start_date, end_date))

    schedule = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'schedule': schedule,
        'start_date': start_date,
        'end_date': end_date
    })

# ==========================================
# PTO/TIME OFF REQUESTS
# ==========================================

@employee_bp.route('/pto-balance')
@login_required
@organization_required
@permission_required('employees.view_own')
def get_pto_balance():
    """Get current employee's PTO balance"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    # Assuming PTO balance is stored in employees table
    return jsonify({
        'pto_hours_available': employee.get('pto_hours_available', 0),
        'pto_hours_used': employee.get('pto_hours_used', 0),
        'pto_hours_accrued': employee.get('pto_hours_accrued', 0)
    })

@employee_bp.route('/time-off-requests')
@login_required
@organization_required
@permission_required('employees.view_own')
def get_time_off_requests():
    """Get current employee's time off requests"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='time_off_requests'
    """)

    if not cursor.fetchone():
        conn.close()
        return jsonify({
            'message': 'Time off requests feature not yet implemented',
            'requests': []
        })

    cursor.execute("""
        SELECT * FROM time_off_requests
        WHERE employee_id = ? AND organization_id = ?
        ORDER BY request_date DESC
    """, (employee['id'], g.organization['id']))

    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'requests': requests})

@employee_bp.route('/time-off-requests', methods=['POST'])
@login_required
@organization_required
@permission_required('employees.view_own')
def submit_time_off_request():
    """Submit a new time off request"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    data = request.json

    conn = get_org_db()
    cursor = conn.cursor()

    # Check if table exists, if not return message
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='time_off_requests'
    """)

    if not cursor.fetchone():
        conn.close()
        return jsonify({
            'error': 'Time off requests feature not yet implemented'
        }), 501

    cursor.execute("""
        INSERT INTO time_off_requests
        (organization_id, employee_id, start_date, end_date, hours_requested, reason, status, request_date)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        g.organization['id'],
        employee['id'],
        data['start_date'],
        data['end_date'],
        data.get('hours_requested'),
        data.get('reason'),
        datetime.now().isoformat()
    ))

    request_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_audit('submitted_time_off_request', 'time_off_request', request_id)

    return jsonify({
        'success': True,
        'request_id': request_id,
        'message': 'Time off request submitted successfully'
    })
