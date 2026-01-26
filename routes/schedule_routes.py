"""
Schedule Management Routes
Handles employee scheduling, shift management, and change requests
"""

from flask import Blueprint, jsonify, request, g
import sqlite3
from datetime import datetime, timedelta
from db_manager import get_org_db
from middleware import (
    login_required,
    organization_required,
    permission_required,
    log_audit
)

schedule_bp = Blueprint('schedule', __name__, url_prefix='/api/schedules')

# ========================================
# ADMIN SCHEDULE MANAGEMENT
# ========================================

@schedule_bp.route('', methods=['GET'])
@login_required
@organization_required
def get_schedules():
    """Get all schedules with optional filters"""
    # Query parameters
    employee_id = request.args.get('employee_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    department = request.args.get('department')
    position = request.args.get('position')
    status = request.args.get('status')
    change_request_status = request.args.get('change_request_status')

    conn = get_org_db()
    cursor = conn.cursor()

    # Build query with joins to get employee info
    query = """
        SELECT
            s.*,
            e.first_name,
            e.last_name,
            e.first_name || ' ' || e.last_name as employee_name,
            e.employee_code,
            e.position as employee_position,
            e.department as employee_department
        FROM schedules s
        JOIN employees e ON s.employee_id = e.id
        WHERE s.organization_id = ?
    """
    params = [g.organization['id']]

    # Apply filters
    if employee_id:
        query += " AND s.employee_id = ?"
        params.append(employee_id)

    if start_date:
        query += " AND s.date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND s.date <= ?"
        params.append(end_date)

    if department:
        query += " AND e.department = ?"
        params.append(department)

    if position:
        query += " AND (s.position = ? OR e.position = ?)"
        params.append(position)
        params.append(position)

    if status and status != 'all':
        query += " AND s.status = ?"
        params.append(status)
    else:
        # By default, exclude cancelled schedules from calendar view
        query += " AND s.status != 'cancelled'"

    if change_request_status:
        query += " AND s.change_request_status = ?"
        params.append(change_request_status)

    query += " ORDER BY s.date, s.start_time"

    cursor.execute(query, params)
    schedules = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'schedules': schedules})


@schedule_bp.route('', methods=['POST'])
@login_required
@organization_required
@permission_required('schedules.manage')
def create_schedule():
    """Create a new schedule (Admin only)"""
    data = request.json

    # Validate required fields
    required_fields = ['employee_id', 'date', 'start_time', 'end_time']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    # Check for conflicts
    cursor.execute("""
        SELECT id FROM schedules
        WHERE employee_id = ?
          AND date = ?
          AND status != 'cancelled'
          AND (
              (start_time <= ? AND end_time > ?) OR
              (start_time < ? AND end_time >= ?) OR
              (start_time >= ? AND end_time <= ?)
          )
    """, (
        data['employee_id'],
        data['date'],
        data['start_time'], data['start_time'],
        data['end_time'], data['end_time'],
        data['start_time'], data['end_time']
    ))

    if cursor.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'error': 'Schedule conflict: Employee already has a shift at this time'
        }), 409

    # Create schedule
    cursor.execute("""
        INSERT INTO schedules (
            organization_id, employee_id, date, start_time, end_time,
            shift_type, position, notes, break_duration, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        g.organization['id'],
        data['employee_id'],
        data['date'],
        data['start_time'],
        data['end_time'],
        data.get('shift_type', 'regular'),
        data.get('position'),
        data.get('notes'),
        data.get('break_duration', 30),
        g.user['id']
    ))

    schedule_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_audit('created_schedule', 'schedule', schedule_id, data)

    return jsonify({'success': True, 'schedule_id': schedule_id, 'message': 'Schedule created successfully'})


@schedule_bp.route('/<int:schedule_id>', methods=['PUT'])
@login_required
@organization_required
@permission_required('schedules.manage')
def update_schedule(schedule_id):
    """Update an existing schedule (Admin only)"""
    data = request.json

    conn = get_org_db()
    cursor = conn.cursor()

    # Verify schedule exists and belongs to organization
    cursor.execute("""
        SELECT * FROM schedules
        WHERE id = ? AND organization_id = ?
    """, (schedule_id, g.organization['id']))

    schedule = cursor.fetchone()
    if not schedule:
        conn.close()
        return jsonify({'success': False, 'error': 'Schedule not found'}), 404

    # Build update query
    update_fields = []
    update_values = []

    allowed_fields = [
        'date', 'start_time', 'end_time', 'shift_type',
        'position', 'notes', 'break_duration', 'status'
    ]

    for field in allowed_fields:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if not update_fields:
        conn.close()
        return jsonify({'success': False, 'error': 'No fields to update'}), 400

    # Add audit fields
    update_fields.append("updated_by = ?")
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(g.user['id'])
    update_values.append(schedule_id)
    update_values.append(g.organization['id'])

    # Execute update
    cursor.execute(f"""
        UPDATE schedules
        SET {', '.join(update_fields)}
        WHERE id = ? AND organization_id = ?
    """, update_values)

    conn.commit()
    conn.close()

    log_audit('updated_schedule', 'schedule', schedule_id, data)

    return jsonify({'success': True, 'message': 'Schedule updated successfully'})


@schedule_bp.route('/<int:schedule_id>', methods=['DELETE'])
@login_required
@organization_required
@permission_required('schedules.manage')
def delete_schedule(schedule_id):
    """Delete/cancel a schedule (Admin only - soft delete)"""
    conn = get_org_db()
    cursor = conn.cursor()

    # Verify schedule exists
    cursor.execute("""
        SELECT id FROM schedules
        WHERE id = ? AND organization_id = ?
    """, (schedule_id, g.organization['id']))

    if not cursor.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Schedule not found'}), 404

    # Soft delete by setting status to cancelled
    cursor.execute("""
        UPDATE schedules
        SET status = 'cancelled',
            updated_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND organization_id = ?
    """, (g.user['id'], schedule_id, g.organization['id']))

    conn.commit()
    conn.close()

    log_audit('deleted_schedule', 'schedule', schedule_id, {})

    return jsonify({'success': True, 'message': 'Schedule cancelled successfully'})


@schedule_bp.route('/bulk', methods=['POST'])
@login_required
@organization_required
@permission_required('schedules.manage')
def create_bulk_schedules():
    """Create multiple schedules at once (for patterns)"""
    data = request.json

    if 'schedules' not in data or not isinstance(data['schedules'], list):
        return jsonify({'success': False, 'error': 'schedules array required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    created_ids = []
    errors = []

    for idx, schedule_data in enumerate(data['schedules']):
        try:
            # Validate required fields
            required = ['employee_id', 'date', 'start_time', 'end_time']
            if not all(field in schedule_data for field in required):
                errors.append(f"Schedule {idx}: Missing required fields")
                continue

            # Check for conflicts (skip for now in bulk - could be optimized)
            cursor.execute("""
                INSERT INTO schedules (
                    organization_id, employee_id, date, start_time, end_time,
                    shift_type, position, notes, break_duration, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                g.organization['id'],
                schedule_data['employee_id'],
                schedule_data['date'],
                schedule_data['start_time'],
                schedule_data['end_time'],
                schedule_data.get('shift_type', 'regular'),
                schedule_data.get('position'),
                schedule_data.get('notes'),
                schedule_data.get('break_duration', 30),
                g.user['id']
            ))

            created_ids.append(cursor.lastrowid)

        except Exception as e:
            errors.append(f"Schedule {idx}: {str(e)}")

    conn.commit()
    conn.close()

    log_audit('created_bulk_schedules', 'schedule', None, {
        'count': len(created_ids),
        'schedules': data['schedules']
    })

    return jsonify({
        'success': True,
        'created_count': len(created_ids),
        'created_ids': created_ids,
        'errors': errors if errors else None
    })


# ========================================
# EMPLOYEE SCHEDULE VIEWING
# ========================================

@schedule_bp.route('/employee/data', methods=['GET'])
@login_required
@organization_required
def get_employee_schedule_data():
    """Get employee's own schedules + team schedules"""
    from routes.employee_routes import get_current_employee

    employee = get_current_employee()
    if not employee:
        return jsonify({'success': False, 'error': 'Employee record not found'}), 404

    # Query parameters
    start_date = request.args.get('start_date', datetime.now().date().isoformat())
    end_date = request.args.get('end_date', (datetime.now().date() + timedelta(days=7)).isoformat())

    conn = get_org_db()
    cursor = conn.cursor()

    # Get employee's own schedules
    cursor.execute("""
        SELECT s.*, e.first_name, e.last_name,
               e.first_name || ' ' || e.last_name as employee_name,
               e.employee_code
        FROM schedules s
        JOIN employees e ON s.employee_id = e.id
        WHERE s.employee_id = ?
          AND s.organization_id = ?
          AND s.date >= ?
          AND s.date <= ?
          AND s.status != 'cancelled'
        ORDER BY s.date, s.start_time
    """, (employee['id'], g.organization['id'], start_date, end_date))

    own_schedules = [dict(row) for row in cursor.fetchall()]

    # Get team schedules
    cursor.execute("""
        SELECT s.*, e.first_name, e.last_name,
               e.first_name || ' ' || e.last_name as employee_name,
               e.employee_code, e.position, e.department
        FROM schedules s
        JOIN employees e ON s.employee_id = e.id
        WHERE s.organization_id = ?
          AND s.date >= ?
          AND s.date <= ?
          AND s.status != 'cancelled'
        ORDER BY s.date, s.start_time, e.last_name, e.first_name
    """, (g.organization['id'], start_date, end_date))

    team_schedules = [dict(row) for row in cursor.fetchall()]

    # Get attendance overlay
    cursor.execute("""
        SELECT a.*, e.first_name, e.last_name,
               e.first_name || ' ' || e.last_name as employee_name
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE a.organization_id = ?
          AND DATE(a.clock_in) >= ?
          AND DATE(a.clock_in) <= ?
        ORDER BY a.clock_in
    """, (g.organization['id'], start_date, end_date))

    attendance_overlay = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'success': True,
        'own_schedules': own_schedules,
        'team_schedules': team_schedules,
        'attendance_overlay': attendance_overlay
    })


@schedule_bp.route('/employee/team', methods=['GET'])
@login_required
@organization_required
def get_team_schedule():
    """Get full team schedule with filters"""
    # Query parameters
    start_date = request.args.get('start_date', datetime.now().date().isoformat())
    end_date = request.args.get('end_date', (datetime.now().date() + timedelta(days=7)).isoformat())
    filter_position = request.args.get('filter_position')
    filter_department = request.args.get('filter_department')

    conn = get_org_db()
    cursor = conn.cursor()

    query = """
        SELECT s.*, e.first_name, e.last_name,
               e.first_name || ' ' || e.last_name as employee_name,
               e.employee_code, e.position, e.department
        FROM schedules s
        JOIN employees e ON s.employee_id = e.id
        WHERE s.organization_id = ?
          AND s.date >= ?
          AND s.date <= ?
          AND s.status != 'cancelled'
    """
    params = [g.organization['id'], start_date, end_date]

    if filter_position:
        query += " AND (s.position = ? OR e.position = ?)"
        params.extend([filter_position, filter_position])

    if filter_department:
        query += " AND e.department = ?"
        params.append(filter_department)

    query += " ORDER BY s.date, s.start_time, e.last_name, e.first_name"

    cursor.execute(query, params)
    team_schedules = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'schedules': team_schedules})


# ========================================
# CHANGE REQUESTS
# ========================================

@schedule_bp.route('/<int:schedule_id>/request-change', methods=['POST'])
@login_required
@organization_required
def request_schedule_change(schedule_id):
    """Request a shift change (Employee)"""
    from routes.employee_routes import get_current_employee

    employee = get_current_employee()
    if not employee:
        return jsonify({'success': False, 'error': 'Employee record not found'}), 404

    data = request.json
    if 'reason' not in data:
        return jsonify({'success': False, 'error': 'Reason required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    # Verify schedule belongs to employee
    cursor.execute("""
        SELECT * FROM schedules
        WHERE id = ? AND employee_id = ? AND organization_id = ?
    """, (schedule_id, employee['id'], g.organization['id']))

    schedule = cursor.fetchone()
    if not schedule:
        conn.close()
        return jsonify({'success': False, 'error': 'Schedule not found'}), 404

    # Update schedule with change request
    cursor.execute("""
        UPDATE schedules
        SET change_requested_by = ?,
            change_request_reason = ?,
            change_request_status = 'pending',
            change_request_date = CURRENT_TIMESTAMP
        WHERE id = ? AND organization_id = ?
    """, (employee['id'], data['reason'], schedule_id, g.organization['id']))

    conn.commit()
    conn.close()

    log_audit('requested_schedule_change', 'schedule', schedule_id, {
        'reason': data['reason'],
        'requested_changes': data.get('requested_changes')
    })

    return jsonify({'success': True, 'message': 'Change request submitted successfully'})


@schedule_bp.route('/<int:schedule_id>/approve-change', methods=['PUT'])
@login_required
@organization_required
@permission_required('schedules.manage')
def approve_schedule_change(schedule_id):
    """Approve or deny a change request (Admin only)"""
    data = request.json

    if 'approved' not in data:
        return jsonify({'success': False, 'error': 'approved field required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    # Verify schedule exists
    cursor.execute("""
        SELECT * FROM schedules
        WHERE id = ? AND organization_id = ? AND change_request_status = 'pending'
    """, (schedule_id, g.organization['id']))

    schedule = cursor.fetchone()
    if not schedule:
        conn.close()
        return jsonify({'success': False, 'error': 'Pending change request not found'}), 404

    new_status = 'approved' if data['approved'] else 'denied'

    if data['approved']:
        # When approved, cancel the original shift
        cursor.execute("""
            UPDATE schedules
            SET status = 'cancelled',
                change_request_status = ?,
                updated_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?
        """, (new_status, g.user['id'], schedule_id, g.organization['id']))
    else:
        # When denied, just update the request status
        cursor.execute("""
            UPDATE schedules
            SET change_request_status = ?,
                updated_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?
        """, (new_status, g.user['id'], schedule_id, g.organization['id']))

    conn.commit()
    conn.close()

    log_audit('approved_schedule_change' if data['approved'] else 'denied_schedule_change',
              'schedule', schedule_id, data)

    message = 'Change request approved and shift cancelled' if data['approved'] else 'Change request denied'

    # Return the schedule details if approved so frontend can prompt for replacement
    if data['approved']:
        return jsonify({
            'success': True,
            'message': message,
            'cancelled_shift': {
                'date': schedule['date'],
                'start_time': schedule['start_time'],
                'end_time': schedule['end_time'],
                'position': schedule['position']
            }
        })

    return jsonify({'success': True, 'message': message})


# ========================================
# ATTENDANCE OVERLAY
# ========================================

@schedule_bp.route('/attendance-overlay', methods=['GET'])
@login_required
@organization_required
def get_attendance_overlay():
    """Get attendance data for scheduled dates"""
    employee_id = request.args.get('employee_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_org_db()
    cursor = conn.cursor()

    query = """
        SELECT a.*, e.first_name, e.last_name,
               e.first_name || ' ' || e.last_name as employee_name,
               e.employee_code
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE a.organization_id = ?
    """
    params = [g.organization['id']]

    if employee_id:
        query += " AND a.employee_id = ?"
        params.append(employee_id)

    if start_date:
        query += " AND DATE(a.clock_in) >= ?"
        params.append(start_date)

    if end_date:
        query += " AND DATE(a.clock_in) <= ?"
        params.append(end_date)

    query += " ORDER BY a.clock_in"

    cursor.execute(query, params)
    attendance_records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'attendance': attendance_records})

# ============================================================================
# Admin Time Off Management Endpoints
# ============================================================================

@schedule_bp.route('/time-off-requests')
@login_required
@organization_required
@permission_required('schedules.view')
def get_all_time_off_requests():
    """Get all time off requests (admin)"""
    employee_id = request.args.get('employee_id')
    status = request.args.get('status', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_org_db()
    cursor = conn.cursor()

    query = """
        SELECT
            t.*,
            e.first_name || ' ' || e.last_name as employee_name,
            e.position,
            e.department
        FROM time_off_requests t
        JOIN employees e ON t.employee_id = e.id
        WHERE t.organization_id = ?
    """
    params = [g.organization['id']]

    if employee_id:
        query += " AND t.employee_id = ?"
        params.append(employee_id)

    if status != 'all':
        query += " AND t.status = ?"
        params.append(status)

    if start_date:
        query += " AND t.start_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND t.end_date <= ?"
        params.append(end_date)

    query += " ORDER BY t.created_at DESC"

    cursor.execute(query, params)
    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'requests': requests})

@schedule_bp.route('/time-off-requests/<int:request_id>/approve', methods=['PUT'])
@login_required
@organization_required
@permission_required('schedules.edit')
def approve_time_off_request(request_id):
    """Approve a time off request (admin)"""
    data = request.json or {}
    admin_notes = data.get('admin_notes', '')

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get the time off request details
        cursor.execute("""
            SELECT employee_id, request_type, total_hours, status
            FROM time_off_requests
            WHERE id = ? AND organization_id = ?
        """, (request_id, g.organization['id']))

        time_off = cursor.fetchone()

        if not time_off:
            conn.close()
            return jsonify({'error': 'Time off request not found'}), 404

        if time_off['status'] != 'pending':
            conn.close()
            return jsonify({'error': 'Can only approve pending requests'}), 400

        # Update the request status
        cursor.execute("""
            UPDATE time_off_requests
            SET status = 'approved',
                admin_notes = ?,
                reviewed_by = ?,
                reviewed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (admin_notes, g.user['id'], request_id))

        # If request type is PTO, deduct hours from employee's balance
        if time_off['request_type'] == 'pto':
            cursor.execute("""
                UPDATE employees
                SET pto_hours_available = pto_hours_available - ?,
                    pto_hours_used = pto_hours_used + ?
                WHERE id = ? AND organization_id = ?
            """, (time_off['total_hours'], time_off['total_hours'],
                  time_off['employee_id'], g.organization['id']))

        conn.commit()

        log_audit('approved_time_off_request', 'time_off_request', request_id)

        return jsonify({
            'success': True,
            'message': 'Time off request approved successfully'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@schedule_bp.route('/time-off-requests/<int:request_id>/deny', methods=['PUT'])
@login_required
@organization_required
@permission_required('schedules.edit')
def deny_time_off_request(request_id):
    """Deny a time off request (admin)"""
    data = request.json or {}
    reason = data.get('reason', '')
    admin_notes = data.get('admin_notes', '')

    if not reason:
        return jsonify({'error': 'Reason for denial is required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get the time off request details
        cursor.execute("""
            SELECT status FROM time_off_requests
            WHERE id = ? AND organization_id = ?
        """, (request_id, g.organization['id']))

        time_off = cursor.fetchone()

        if not time_off:
            conn.close()
            return jsonify({'error': 'Time off request not found'}), 404

        if time_off['status'] != 'pending':
            conn.close()
            return jsonify({'error': 'Can only deny pending requests'}), 400

        # Update the request status
        cursor.execute("""
            UPDATE time_off_requests
            SET status = 'denied',
                reason = ?,
                admin_notes = ?,
                reviewed_by = ?,
                reviewed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reason, admin_notes, g.user['id'], request_id))

        conn.commit()

        log_audit('denied_time_off_request', 'time_off_request', request_id)

        return jsonify({
            'success': True,
            'message': 'Time off request denied'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@schedule_bp.route('/employee/<int:employee_id>/availability')
@login_required
@organization_required
@permission_required('schedules.view')
def get_employee_availability(employee_id):
    """Get an employee's availability preferences (admin)"""
    conn = get_org_db()
    cursor = conn.cursor()

    # Verify employee belongs to this organization
    cursor.execute("""
        SELECT id FROM employees
        WHERE id = ? AND organization_id = ?
    """, (employee_id, g.organization['id']))

    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Employee not found'}), 404

    cursor.execute("""
        SELECT * FROM employee_availability
        WHERE employee_id = ? AND organization_id = ?
        ORDER BY day_of_week, start_time
    """, (employee_id, g.organization['id']))

    availability = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'availability': availability})
