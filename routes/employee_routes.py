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

# NOTE: The /employee/portal route is defined in app.py to render the comprehensive portal
# This blueprint only contains API endpoints for employee data

# ==========================================
# PROFILE MANAGEMENT
# ==========================================

@employee_bp.route('/profile')
@login_required
@organization_required
def profile_page():
    """Employee profile page"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return render_template('employee/profile.html', employee=dict(employee))

@employee_bp.route('/profile/data')
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

@employee_bp.route('/profile/upload-picture', methods=['POST'])
@login_required
@organization_required
def upload_profile_picture():
    """Upload profile picture for employee"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    if 'profile_picture' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['profile_picture']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Check file extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), 400

    # Create uploads directory if it doesn't exist
    import os
    from werkzeug.utils import secure_filename

    upload_dir = os.path.join('static', 'uploads', 'profiles')
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    filename = f"employee_{employee['id']}_{int(datetime.now().timestamp())}.{file_ext}"
    filename = secure_filename(filename)
    filepath = os.path.join(upload_dir, filename)

    # Save file
    file.save(filepath)

    # Update database with profile picture path
    profile_picture_url = f"/static/uploads/profiles/{filename}"

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE employees
        SET profile_picture = ?
        WHERE id = ? AND organization_id = ?
    """, (profile_picture_url, employee['id'], g.organization['id']))

    conn.commit()
    conn.close()

    log_audit('updated_profile_picture', 'employee', employee['id'], {
        'profile_picture': profile_picture_url
    })

    return jsonify({
        'success': True,
        'message': 'Profile picture updated successfully',
        'profile_picture': profile_picture_url
    })

# ==========================================
# TIME CLOCK - REMOVED
# Clock in/out functionality removed from comprehensive portal
# Clock terminal uses /api/attendance/* endpoints instead
# ==========================================

# ==========================================
# TIME ENTRIES HISTORY
# ==========================================

@employee_bp.route('/time-entries')
@login_required
@organization_required
def time_entries_page():
    """Time entries page"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return render_template('employee/time_entries.html', employee=dict(employee))

@employee_bp.route('/time-entries/data')
@login_required
@organization_required
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

    # Query attendance table (not time_entries)
    # Get all attendance records for this employee, sorted by date
    cursor.execute("""
        SELECT * FROM attendance
        WHERE employee_id = ? AND organization_id = ? AND clock_in IS NOT NULL
        ORDER BY clock_in DESC
    """, (employee['id'], g.organization['id']))

    entries = [dict(row) for row in cursor.fetchall()]

    # Calculate total hours - attendance uses total_hours column
    total_hours = sum(entry.get('total_hours', 0) or 0 for entry in entries)

    # Map attendance fields to match expected time_entries format
    for entry in entries:
        entry['hours_worked'] = entry.get('total_hours', 0)

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

    # Render the schedule template - JavaScript will fetch data via API
    return render_template('employee/schedule.html', employee=dict(employee))

# ==========================================
# PTO/TIME OFF REQUESTS
# ==========================================

@employee_bp.route('/time-off')
@login_required
@organization_required
def time_off_page():
    """Time off request page"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return render_template('employee/time_off.html', employee=dict(employee))

@employee_bp.route('/pto-balance')
@login_required
@organization_required
@permission_required('employees.view_own')
def get_pto_balance():
    """Get current employee's PTO balance"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return jsonify({
        'success': True,
        'available': employee.get('pto_hours_available', 80.0),
        'used': employee.get('pto_hours_used', 0.0),
        'total': employee.get('pto_hours_available', 80.0) + employee.get('pto_hours_used', 0.0),
        'accrual_rate': employee.get('pto_accrual_rate', 0.0385)
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

    cursor.execute("""
        SELECT * FROM time_off_requests
        WHERE employee_id = ? AND organization_id = ?
        ORDER BY created_at DESC
    """, (employee['id'], g.organization['id']))

    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'requests': requests})

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

    # Validate required fields
    required_fields = ['start_date', 'end_date', 'request_type', 'total_hours']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Validate PTO balance if request type is PTO
    if data['request_type'] == 'pto':
        pto_available = employee.get('pto_hours_available', 0)
        if data['total_hours'] > pto_available:
            return jsonify({
                'error': f'Insufficient PTO balance. Available: {pto_available} hours, Requested: {data["total_hours"]} hours'
            }), 400

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO time_off_requests
            (organization_id, employee_id, start_date, end_date, request_type, total_hours, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            g.organization['id'],
            employee['id'],
            data['start_date'],
            data['end_date'],
            data['request_type'],
            data['total_hours'],
            data.get('reason', '')
        ))

        request_id = cursor.lastrowid
        conn.commit()

        log_audit('submitted_time_off_request', 'time_off_request', request_id)

        return jsonify({
            'success': True,
            'request_id': request_id,
            'message': 'Time off request submitted successfully'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@employee_bp.route('/time-off-requests/<int:request_id>', methods=['DELETE'])
@login_required
@organization_required
@permission_required('employees.view_own')
def cancel_time_off_request(request_id):
    """Cancel a pending time off request"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # First check if the request exists and belongs to this employee
        cursor.execute("""
            SELECT status FROM time_off_requests
            WHERE id = ? AND employee_id = ? AND organization_id = ?
        """, (request_id, employee['id'], g.organization['id']))

        result = cursor.fetchone()

        if not result:
            conn.close()
            return jsonify({'error': 'Time off request not found'}), 404

        if result['status'] != 'pending':
            conn.close()
            return jsonify({'error': 'Can only cancel pending requests'}), 400

        # Delete the request
        cursor.execute("""
            DELETE FROM time_off_requests
            WHERE id = ? AND employee_id = ? AND organization_id = ?
        """, (request_id, employee['id'], g.organization['id']))

        conn.commit()

        log_audit('cancelled_time_off_request', 'time_off_request', request_id)

        return jsonify({
            'success': True,
            'message': 'Time off request cancelled successfully'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# ============================================================================
# Availability Management Endpoints
# ============================================================================

@employee_bp.route('/availability-page')
@login_required
@organization_required
def availability_page():
    """Availability management page"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    return render_template('employee/availability.html', employee=dict(employee))

@employee_bp.route('/availability')
@login_required
@organization_required
@permission_required('employees.view_own')
def get_availability():
    """Get current employee's availability preferences"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM employee_availability
        WHERE employee_id = ? AND organization_id = ?
        ORDER BY day_of_week, start_time
    """, (employee['id'], g.organization['id']))

    availability = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'availability': availability})

@employee_bp.route('/availability', methods=['POST'])
@login_required
@organization_required
@permission_required('employees.view_own')
def add_availability():
    """Add a new availability entry"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    data = request.json

    # Validate required fields
    required_fields = ['day_of_week', 'start_time', 'end_time']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Validate day_of_week is between 0-6
    if not (0 <= data['day_of_week'] <= 6):
        return jsonify({'error': 'day_of_week must be between 0 (Sunday) and 6 (Saturday)'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO employee_availability
            (organization_id, employee_id, day_of_week, start_time, end_time,
             effective_from, effective_until, availability_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            g.organization['id'],
            employee['id'],
            data['day_of_week'],
            data['start_time'],
            data['end_time'],
            data.get('effective_from'),
            data.get('effective_until'),
            data.get('availability_type', 'recurring'),
            data.get('notes', '')
        ))

        availability_id = cursor.lastrowid
        conn.commit()

        log_audit('added_availability', 'employee_availability', availability_id)

        return jsonify({
            'success': True,
            'availability_id': availability_id,
            'message': 'Availability added successfully'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@employee_bp.route('/availability/<int:availability_id>', methods=['PUT'])
@login_required
@organization_required
@permission_required('employees.view_own')
def update_availability(availability_id):
    """Update an existing availability entry"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    data = request.json

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # First check if the availability exists and belongs to this employee
        cursor.execute("""
            SELECT id FROM employee_availability
            WHERE id = ? AND employee_id = ? AND organization_id = ?
        """, (availability_id, employee['id'], g.organization['id']))

        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Availability entry not found'}), 404

        # Build update query dynamically based on provided fields
        update_fields = []
        update_values = []

        allowed_fields = ['day_of_week', 'start_time', 'end_time', 'effective_from',
                         'effective_until', 'availability_type', 'notes']

        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])

        if not update_fields:
            conn.close()
            return jsonify({'error': 'No fields to update'}), 400

        # Add updated_at
        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        update_values.extend([availability_id, employee['id'], g.organization['id']])

        cursor.execute(f"""
            UPDATE employee_availability
            SET {', '.join(update_fields)}
            WHERE id = ? AND employee_id = ? AND organization_id = ?
        """, update_values)

        conn.commit()

        log_audit('updated_availability', 'employee_availability', availability_id)

        return jsonify({
            'success': True,
            'message': 'Availability updated successfully'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@employee_bp.route('/availability/<int:availability_id>', methods=['DELETE'])
@login_required
@organization_required
@permission_required('employees.view_own')
def delete_availability(availability_id):
    """Delete an availability entry"""
    employee = get_current_employee()

    if not employee:
        return jsonify({'error': 'Employee record not found'}), 404

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # First check if the availability exists and belongs to this employee
        cursor.execute("""
            SELECT id FROM employee_availability
            WHERE id = ? AND employee_id = ? AND organization_id = ?
        """, (availability_id, employee['id'], g.organization['id']))

        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Availability entry not found'}), 404

        # Delete the entry
        cursor.execute("""
            DELETE FROM employee_availability
            WHERE id = ? AND employee_id = ? AND organization_id = ?
        """, (availability_id, employee['id'], g.organization['id']))

        conn.commit()

        log_audit('deleted_availability', 'employee_availability', availability_id)

        return jsonify({
            'success': True,
            'message': 'Availability deleted successfully'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
