"""
Attendance Routes
- Clock in/out
- Break start/end
- Attendance history
- Attendance record management
"""

from flask import Blueprint, jsonify, request, session, g
from db_manager import get_org_db
from utils.audit import log_audit
from middleware.tenant_context_separate_db import login_required, organization_required, organization_admin_required
from datetime import datetime, timedelta

attendance_bp = Blueprint('attendance', __name__)


def get_current_employee_id():
    """Get employee ID from either regular login or clock terminal session"""
    # Check if using clock terminal session
    if 'clock_employee_id' in session:
        return session['clock_employee_id']

    # Check if regular employee login
    if hasattr(g, 'user') and g.user:
        conn = get_org_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM employees
            WHERE user_id = ? AND organization_id = ?
        """, (g.user['id'], g.organization['id']))
        employee = cursor.fetchone()
        conn.close()
        return employee['id'] if employee else None

    return None


@attendance_bp.route('/api/attendance/status', methods=['GET'])
@organization_required
def get_attendance_status():
    """Get current attendance status for logged-in employee"""
    employee_id = get_current_employee_id()

    if not employee_id:
        return jsonify({'error': 'Employee not authenticated'}), 401

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get current open attendance record
        cursor.execute("""
            SELECT * FROM attendance
            WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
            ORDER BY clock_in DESC
            LIMIT 1
        """, (employee_id, g.organization['id']))

        current_record = cursor.fetchone()
        conn.close()

        if current_record:
            return jsonify({
                'success': True,
                'status': current_record['status'],
                'clock_in': current_record['clock_in'],
                'break_start': current_record['break_start'],
                'break_end': current_record['break_end'],
                'attendance_id': current_record['id']
            })
        else:
            return jsonify({
                'success': True,
                'status': 'clocked_out'
            })

    except Exception as e:
        conn.close()
        print(f"Error getting attendance status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/api/attendance/clock-in', methods=['POST'])
@organization_required
def clock_in():
    """Clock in employee"""
    employee_id = get_current_employee_id()

    if not employee_id:
        return jsonify({'error': 'Employee not authenticated'}), 401

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get employee info for audit logging
        cursor.execute("""
            SELECT id, first_name, last_name FROM employees
            WHERE id = ? AND organization_id = ?
        """, (employee_id, g.organization['id']))

        employee = cursor.fetchone()
        if not employee:
            conn.close()
            return jsonify({'error': 'Employee record not found'}), 404

        # Check if already clocked in
        cursor.execute("""
            SELECT id FROM attendance
            WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
        """, (employee_id, g.organization['id']))

        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Already clocked in'}), 400

        # Create new attendance record
        user_id = g.user['id'] if g.user else None
        cursor.execute("""
            INSERT INTO attendance (
                organization_id, employee_id, user_id, clock_in, status
            ) VALUES (?, ?, ?, datetime('now', 'localtime'), 'clocked_in')
        """, (g.organization['id'], employee_id, user_id))

        attendance_id = cursor.lastrowid
        conn.commit()

        # Log audit entry
        employee_name = f"{employee['first_name']} {employee['last_name']}"
        log_audit('clock_in', 'attendance', attendance_id, employee_name, "Clocked in")

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Clocked in successfully',
            'attendance_id': attendance_id
        })

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        conn.close()
        print(f"Error clocking in: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/api/attendance/clock-out', methods=['POST'])
@organization_required
def clock_out():
    """Clock out employee"""
    employee_id = get_current_employee_id()

    if not employee_id:
        return jsonify({'error': 'Employee not authenticated'}), 401

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get employee info for audit logging
        cursor.execute("""
            SELECT id, first_name, last_name FROM employees
            WHERE id = ? AND organization_id = ?
        """, (employee_id, g.organization['id']))

        employee = cursor.fetchone()
        if not employee:
            conn.close()
            return jsonify({'error': 'Employee record not found'}), 404

        # Get current open attendance record
        cursor.execute("""
            SELECT * FROM attendance
            WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
            ORDER BY clock_in DESC
            LIMIT 1
        """, (employee_id, g.organization['id']))

        record = cursor.fetchone()
        if not record:
            conn.close()
            return jsonify({'error': 'Not clocked in'}), 400

        # Calculate total hours
        cursor.execute("""
            UPDATE attendance
            SET clock_out = datetime('now', 'localtime'),
                status = 'clocked_out',
                total_hours = ROUND((julianday(datetime('now', 'localtime')) - julianday(clock_in)) * 24, 2),
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (record['id'],))

        conn.commit()

        # Get updated record to return total hours
        cursor.execute("SELECT total_hours FROM attendance WHERE id = ?", (record['id'],))
        updated = cursor.fetchone()

        # Log audit entry
        employee_name = f"{employee['first_name']} {employee['last_name']}"
        log_audit('clock_out', 'attendance', record['id'], employee_name, f"Clocked out ({updated['total_hours']} hrs)")

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Clocked out successfully',
            'total_hours': updated['total_hours']
        })

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        conn.close()
        print(f"Error clocking out: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/api/attendance/break-start', methods=['POST'])
@organization_required
def break_start():
    """Start break"""
    employee_id = get_current_employee_id()

    if not employee_id:
        return jsonify({'error': 'Employee not authenticated'}), 401

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get employee info for audit logging
        cursor.execute("""
            SELECT id, first_name, last_name FROM employees
            WHERE id = ? AND organization_id = ?
        """, (employee_id, g.organization['id']))

        employee = cursor.fetchone()
        if not employee:
            conn.close()
            return jsonify({'error': 'Employee record not found'}), 404

        # Get current open attendance record
        cursor.execute("""
            SELECT * FROM attendance
            WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
            ORDER BY clock_in DESC
            LIMIT 1
        """, (employee_id, g.organization['id']))

        record = cursor.fetchone()
        if not record:
            conn.close()
            return jsonify({'error': 'Not clocked in'}), 400

        if record['break_start'] and not record['break_end']:
            conn.close()
            return jsonify({'error': 'Already on break'}), 400

        # Start break
        cursor.execute("""
            UPDATE attendance
            SET break_start = datetime('now', 'localtime'),
                status = 'on_break',
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (record['id'],))

        conn.commit()

        # Log audit entry
        employee_name = f"{employee['first_name']} {employee['last_name']}"
        log_audit('break_start', 'attendance', record['id'], employee_name, "Started break")

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Break started'
        })

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        conn.close()
        print(f"Error starting break: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/api/attendance/break-end', methods=['POST'])
@organization_required
def break_end():
    """End break"""
    employee_id = get_current_employee_id()

    if not employee_id:
        return jsonify({'error': 'Employee not authenticated'}), 401

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get employee info for audit logging
        cursor.execute("""
            SELECT id, first_name, last_name FROM employees
            WHERE id = ? AND organization_id = ?
        """, (employee_id, g.organization['id']))

        employee = cursor.fetchone()
        if not employee:
            conn.close()
            return jsonify({'error': 'Employee record not found'}), 404

        # Get current open attendance record
        cursor.execute("""
            SELECT * FROM attendance
            WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL
            ORDER BY clock_in DESC
            LIMIT 1
        """, (employee['id'], g.organization['id']))

        record = cursor.fetchone()
        if not record:
            conn.close()
            return jsonify({'error': 'Not clocked in'}), 400

        if not record['break_start'] or record['break_end']:
            conn.close()
            return jsonify({'error': 'Not on break'}), 400

        # End break and calculate duration
        cursor.execute("""
            UPDATE attendance
            SET break_end = datetime('now', 'localtime'),
                status = 'clocked_in',
                break_duration = CAST((julianday(datetime('now', 'localtime')) - julianday(break_start)) * 1440 AS INTEGER),
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (record['id'],))

        conn.commit()

        # Log audit entry
        employee_name = f"{employee['first_name']} {employee['last_name']}"
        log_audit('break_end', 'attendance', record['id'], employee_name, "Ended break")

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Break ended'
        })

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        conn.close()
        print(f"Error ending break: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/api/attendance/history', methods=['GET'])
@login_required
@organization_required
def get_attendance_history():
    """Get attendance history for employee or all employees (admin)"""
    conn = get_org_db()
    cursor = conn.cursor()

    # Optional date range filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    try:
        # Check if admin is requesting all attendance or employee is requesting their own
        if g.user['role'] in ['organization_admin', 'super_admin']:
            # Admin can see all attendance
            query = """
                SELECT a.*, e.first_name, e.last_name,
                       e.first_name || ' ' || e.last_name as employee_name,
                       e.employee_code
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE a.organization_id = ?
            """
            params = [g.organization['id']]

            # Add date filters if provided
            if date_from:
                query += " AND DATE(a.clock_in) >= ?"
                params.append(date_from)
            if date_to:
                query += " AND DATE(a.clock_in) <= ?"
                params.append(date_to)

            query += " ORDER BY a.clock_in DESC"
            cursor.execute(query, params)
        else:
            # Employee can only see their own attendance
            cursor.execute("""
                SELECT id FROM employees
                WHERE user_id = ? AND organization_id = ?
            """, (g.user['id'], g.organization['id']))

            employee = cursor.fetchone()
            if not employee:
                conn.close()
                return jsonify({'error': 'Employee record not found'}), 404

            query = """
                SELECT a.*, e.first_name, e.last_name,
                       e.first_name || ' ' || e.last_name as employee_name,
                       e.employee_code
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE a.employee_id = ?
            """
            params = [employee['id']]

            # Add date filters if provided
            if date_from:
                query += " AND DATE(a.clock_in) >= ?"
                params.append(date_from)
            if date_to:
                query += " AND DATE(a.clock_in) <= ?"
                params.append(date_to)

            query += " ORDER BY a.clock_in DESC"
            cursor.execute(query, params)

        records = cursor.fetchall()
        conn.close()

        # Format records with employee_name for frontend
        formatted_records = []
        for record in records:
            record_dict = dict(record)
            record_dict['employee_name'] = f"{record_dict.get('first_name', '')} {record_dict.get('last_name', '')}".strip()
            formatted_records.append(record_dict)

        return jsonify({
            'success': True,
            'attendance': formatted_records
        })

    except Exception as e:
        conn.close()
        print(f"Error getting attendance history: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/api/attendance/<int:attendance_id>', methods=['GET'])
@login_required
@organization_required
def get_attendance_record(attendance_id):
    """Get a specific attendance record (for editing)"""
    # Only admins can view/edit attendance records
    if g.user['role'] not in ['organization_admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT a.*, e.first_name, e.last_name,
                   e.first_name || ' ' || e.last_name as employee_name,
                   e.employee_code
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.id = ? AND a.organization_id = ?
        """, (attendance_id, g.organization['id']))

        record = cursor.fetchone()
        conn.close()

        if not record:
            return jsonify({'error': 'Attendance record not found'}), 404

        record_dict = dict(record)
        record_dict['employee_name'] = f"{record_dict.get('first_name', '')} {record_dict.get('last_name', '')}".strip()

        return jsonify({
            'success': True,
            'attendance': record_dict
        })

    except Exception as e:
        conn.close()
        print(f"Error getting attendance record: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/api/attendance/<int:attendance_id>', methods=['PUT'])
@login_required
@organization_required
def update_attendance_record(attendance_id):
    """Update an attendance record (admin only)"""
    # Only admins can edit attendance records
    if g.user['role'] not in ['organization_admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Verify record exists and belongs to this organization
        cursor.execute("""
            SELECT * FROM attendance
            WHERE id = ? AND organization_id = ?
        """, (attendance_id, g.organization['id']))

        record = cursor.fetchone()
        if not record:
            conn.close()
            return jsonify({'error': 'Attendance record not found'}), 404

        # Calculate total hours if clock_in and clock_out are provided
        total_hours = data.get('total_hours', record['total_hours'])
        if data.get('clock_in') and data.get('clock_out'):
            from datetime import datetime
            clock_in = datetime.fromisoformat(data['clock_in'].replace('Z', '+00:00'))
            clock_out = datetime.fromisoformat(data['clock_out'].replace('Z', '+00:00'))
            total_seconds = (clock_out - clock_in).total_seconds()
            # Subtract break duration (in seconds)
            break_duration_seconds = int(data.get('break_duration', record['break_duration'] or 0)) * 60
            total_seconds -= break_duration_seconds
            total_hours = max(0, total_seconds / 3600)  # Convert to hours

        # Update attendance record
        cursor.execute("""
            UPDATE attendance
            SET clock_in = ?,
                clock_out = ?,
                break_start = ?,
                break_end = ?,
                total_hours = ?,
                break_duration = ?,
                status = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?
        """, (
            data.get('clock_in', record['clock_in']),
            data.get('clock_out', record['clock_out']),
            data.get('break_start', record['break_start']),
            data.get('break_end', record['break_end']),
            total_hours,
            data.get('break_duration', record['break_duration']),
            data.get('status', record['status']),
            data.get('notes', record['notes']),
            attendance_id,
            g.organization['id']
        ))

        conn.commit()

        # Get employee name for audit log
        cursor.execute("SELECT first_name, last_name FROM employees WHERE id = ?", (record['employee_id'],))
        employee = cursor.fetchone()
        employee_name = f"{employee['first_name']} {employee['last_name']}" if employee else "Unknown"

        log_audit('updated_attendance', 'attendance', attendance_id, employee_name,
                 f"Updated attendance record for {employee_name}")

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Attendance record updated successfully'
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error updating attendance record: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to update attendance: {str(e)}'}), 500
