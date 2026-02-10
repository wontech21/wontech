"""
Employee Management Routes
- Organization logo upload
- Employee CRUD operations
"""

from flask import Blueprint, jsonify, request, g
import os
import sqlite3
from db_manager import get_org_db, get_master_db
from utils.auth import hash_password
from utils.audit import log_audit
from middleware.tenant_context_separate_db import login_required, organization_required, organization_admin_required

employee_mgmt_bp = Blueprint('employee_mgmt', __name__)


@employee_mgmt_bp.route('/api/organization/upload-logo', methods=['POST'])
@login_required
@organization_required
def upload_organization_logo():
    """Upload logo for current organization"""
    try:
        if 'logo' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['logo']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file type
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp'}
        file_ext = os.path.splitext(file.filename)[1].lower()

        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, SVG, GIF, WEBP'}), 400

        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'logos')
        os.makedirs(uploads_dir, exist_ok=True)

        # Generate unique filename
        import hashlib
        import secrets
        org_id = g.organization['id']
        timestamp = hashlib.md5(str(secrets.token_hex(8)).encode()).hexdigest()[:8]
        filename = f"org_{org_id}_{timestamp}{file_ext}"
        filepath = os.path.join(uploads_dir, filename)

        # Save file
        file.save(filepath)

        # Update database with logo URL
        logo_url = f"/static/uploads/logos/{filename}"

        conn = get_master_db()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE organizations
            SET logo_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (logo_url, org_id))

        conn.commit()
        conn.close()

        # Log the action
        log_audit('updated_organization_logo', 'organization', org_id, g.organization['organization_name'], {
            'logo_url': logo_url
        })

        return jsonify({
            'success': True,
            'logo_url': logo_url,
            'message': 'Logo uploaded successfully'
        })

    except Exception as e:
        print(f"Error uploading logo: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


# ==========================================
# EMPLOYEE MANAGEMENT ENDPOINTS
# ==========================================

@employee_mgmt_bp.route('/api/employees', methods=['GET'])
@login_required
@organization_required
def get_employees():
    """Get all employees for current organization"""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM employees
        WHERE organization_id = ?
        ORDER BY last_name, first_name
    """, (g.organization['id'],))

    employees = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'success': True,
        'employees': employees
    })


@employee_mgmt_bp.route('/api/employees/<int:employee_id>', methods=['GET'])
@login_required
@organization_required
def get_employee(employee_id):
    """Get single employee details"""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM employees
        WHERE id = ? AND organization_id = ?
    """, (employee_id, g.organization['id']))

    employee = cursor.fetchone()
    conn.close()

    if not employee:
        return jsonify({'error': 'Employee not found'}), 404

    return jsonify({
        'success': True,
        'employee': dict(employee)
    })


@employee_mgmt_bp.route('/api/employees', methods=['POST'])
@login_required
@organization_required
def create_employee():
    """Create new employee with optional user account"""
    data = request.json

    # Validate required fields
    required_fields = ['first_name', 'last_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    conn_org = get_org_db()
    cursor_org = conn_org.cursor()

    try:
        # Generate employee code if not provided
        employee_code = data.get('employee_code')
        if not employee_code:
            # Auto-generate: first 2 letters of last name + random 4 digits
            import random
            last_name_prefix = data['last_name'][:2].upper()
            random_suffix = random.randint(1000, 9999)
            employee_code = f"{last_name_prefix}{random_suffix}"

        # Check if employee code already exists
        cursor_org.execute("""
            SELECT id FROM employees WHERE employee_code = ? AND organization_id = ?
        """, (employee_code, g.organization['id']))

        if cursor_org.fetchone():
            conn_org.close()
            return jsonify({'error': f'Employee code {employee_code} already exists'}), 400

        # Create user account in master.db if email provided and create_user_account is true
        user_id = None
        if data.get('email') and data.get('create_user_account'):
            conn_master = get_master_db()
            cursor_master = conn_master.cursor()

            # Check if email already exists
            cursor_master.execute("SELECT id FROM users WHERE email = ?", (data['email'],))
            if cursor_master.fetchone():
                conn_master.close()
                conn_org.close()
                return jsonify({'error': f'User with email {data["email"]} already exists'}), 400

            # Create user account with role 'employee'
            password = data.get('password', '').strip()
            default_password = password if password else 'Welcome123!'  # Use Welcome123! if empty
            password_hash = hash_password(default_password)

            cursor_master.execute("""
                INSERT INTO users (
                    organization_id, email, password_hash, first_name, last_name,
                    role, permissions, active
                ) VALUES (?, ?, ?, ?, ?, 'employee', '["inventory.view"]', 1)
            """, (
                g.organization['id'],
                data['email'],
                password_hash,
                data['first_name'],
                data['last_name']
            ))

            user_id = cursor_master.lastrowid
            conn_master.commit()
            conn_master.close()

        # Create employee record
        cursor_org.execute("""
            INSERT INTO employees (
                organization_id, user_id, employee_code, first_name, last_name,
                email, phone, position, department, hire_date,
                hourly_rate, salary, employment_type, status,
                address, city, state, zip_code,
                emergency_contact_name, emergency_contact_phone, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            g.organization['id'],
            user_id,
            employee_code,
            data['first_name'],
            data['last_name'],
            data.get('email', ''),
            data.get('phone', ''),
            data.get('position', ''),
            data.get('department', ''),
            data.get('hire_date'),
            float(data.get('hourly_rate', 0)),
            float(data.get('salary', 0)),
            data.get('employment_type', 'full-time'),
            data.get('status', 'active'),
            data.get('address', ''),
            data.get('city', ''),
            data.get('state', ''),
            data.get('zip_code', ''),
            data.get('emergency_contact_name', ''),
            data.get('emergency_contact_phone', ''),
            data.get('notes', '')
        ))

        employee_id = cursor_org.lastrowid
        conn_org.commit()
        conn_org.close()

        # Log the action
        log_audit('created_employee', 'employee', employee_id, f"{data['first_name']} {data['last_name']}", {
            'employee_code': employee_code,
            'has_user_account': user_id is not None
        })

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'user_id': user_id,
            'employee_code': employee_code,
            'message': f'Employee {data["first_name"]} {data["last_name"]} created successfully'
        })

    except Exception as e:
        conn_org.rollback()
        conn_org.close()
        print(f"Error creating employee: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to create employee: {str(e)}'}), 500


@employee_mgmt_bp.route('/api/employees/<int:employee_id>', methods=['PUT'])
@login_required
@organization_required
def update_employee(employee_id):
    """Update employee details"""
    data = request.json

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Check if employee exists
        cursor.execute("""
            SELECT * FROM employees
            WHERE id = ? AND organization_id = ?
        """, (employee_id, g.organization['id']))

        employee = cursor.fetchone()
        if not employee:
            conn.close()
            return jsonify({'error': 'Employee not found'}), 404

        # Update employee
        cursor.execute("""
            UPDATE employees
            SET first_name = ?,
                last_name = ?,
                email = ?,
                phone = ?,
                position = ?,
                department = ?,
                hire_date = ?,
                hourly_rate = ?,
                salary = ?,
                employment_type = ?,
                status = ?,
                employee_code = ?,
                address = ?,
                city = ?,
                state = ?,
                zip_code = ?,
                emergency_contact_name = ?,
                emergency_contact_phone = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?
        """, (
            data.get('first_name', employee['first_name']),
            data.get('last_name', employee['last_name']),
            data.get('email', employee['email']),
            data.get('phone', employee['phone']),
            data.get('position', employee['position']),
            data.get('department', employee['department']),
            data.get('hire_date', employee['hire_date']),
            float(data.get('hourly_rate', employee['hourly_rate'] or 0)),
            float(data.get('salary', employee['salary'] or 0)),
            data.get('employment_type', employee['employment_type']),
            data.get('status', employee['status']),
            data.get('employee_code', employee['employee_code']),
            data.get('address', employee['address']),
            data.get('city', employee['city']),
            data.get('state', employee['state']),
            data.get('zip_code', employee['zip_code']),
            data.get('emergency_contact_name', employee['emergency_contact_name']),
            data.get('emergency_contact_phone', employee['emergency_contact_phone']),
            data.get('notes', employee['notes']),
            employee_id,
            g.organization['id']
        ))

        conn.commit()

        employee_name = f"{data.get('first_name')} {data.get('last_name')}"

        log_audit('updated_employee', 'employee', employee_id, employee_name, f"Updated employee {employee_name}")

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Employee updated successfully'
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error updating employee: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to update employee: {str(e)}'}), 500


@employee_mgmt_bp.route('/api/employees/<int:employee_id>', methods=['DELETE'])
@login_required
@organization_required
def delete_employee(employee_id):
    """Delete (deactivate) employee"""
    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Check if employee exists
        cursor.execute("""
            SELECT * FROM employees
            WHERE id = ? AND organization_id = ?
        """, (employee_id, g.organization['id']))

        employee = cursor.fetchone()
        if not employee:
            conn.close()
            return jsonify({'error': 'Employee not found'}), 404

        # Soft delete - set status to inactive
        cursor.execute("""
            UPDATE employees
            SET status = 'inactive',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?
        """, (employee_id, g.organization['id']))

        # Also deactivate user account if exists
        if employee['user_id']:
            conn_master = get_master_db()
            cursor_master = conn_master.cursor()
            cursor_master.execute("""
                UPDATE users SET active = 0 WHERE id = ?
            """, (employee['user_id'],))
            conn_master.commit()
            conn_master.close()

        conn.commit()
        conn.close()

        log_audit('deleted_employee', 'employee', employee_id, f"{employee['first_name']} {employee['last_name']}")

        return jsonify({
            'success': True,
            'message': 'Employee deactivated successfully'
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error deleting employee: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to delete employee: {str(e)}'}), 500
