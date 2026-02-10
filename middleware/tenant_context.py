"""
Tenant Context Middleware
- Enforces data isolation between organizations
- Provides permission-based authorization
- Implements three-tier access control:
  1. Super Admin: Can access all organizations
  2. Organization Admin: Full access within their organization
  3. Employee: Limited access to own data
"""

from functools import wraps
from flask import g, session, request, jsonify, redirect, url_for
import sqlite3
import json
import os

def get_db():
    """Get database connection"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inventory.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_current_user():
    """Get currently logged in user from session"""
    user_id = session.get('user_id')
    if not user_id:
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_id, email, first_name, last_name, role,
               permissions, can_switch_organizations, current_organization_id, active
        FROM users
        WHERE id = ? AND active = 1
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)

def get_organization_by_id(org_id):
    """Get organization by ID"""
    if not org_id:
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_name, slug, owner_name, owner_email,
               plan_type, subscription_status, active
        FROM organizations
        WHERE id = ? AND active = 1
    """, (org_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)

def get_organization_by_slug(slug):
    """Get organization by subdomain slug"""
    if not slug:
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_name, slug, owner_name, owner_email,
               plan_type, subscription_status, active
        FROM organizations
        WHERE slug = ? AND active = 1
    """, (slug,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)

def get_subdomain_from_host(host):
    """Extract subdomain from hostname"""
    # Example: joes-pizza.wontech.com -> joes-pizza
    #          localhost:5001 -> None
    #          admin.wontech.com -> admin

    if 'localhost' in host or '127.0.0.1' in host:
        return None

    parts = host.split('.')
    if len(parts) >= 3:  # subdomain.domain.com
        return parts[0]

    return None

def user_has_permission(user, required_permission):
    """
    Check if user has a specific permission

    Args:
        user: User dict with 'role' and 'permissions' keys
        required_permission: String like 'inventory.view' or 'payroll.process'

    Returns:
        Boolean
    """
    if not user or not user.get('active'):
        return False

    # Super admin has all permissions
    if user.get('role') == 'super_admin' and user.get('can_switch_organizations'):
        return True

    # Check user's permissions
    user_permissions = user.get('permissions', '[]')
    if isinstance(user_permissions, str):
        try:
            user_permissions = json.loads(user_permissions)
        except:
            user_permissions = []

    # Wildcard permission
    if '*' in user_permissions:
        return True

    # Exact match
    if required_permission in user_permissions:
        return True

    # Category wildcard (e.g., user has 'inventory.*' and checks 'inventory.view')
    category = required_permission.split('.')[0]
    if f"{category}.*" in user_permissions:
        return True

    return False

def set_tenant_context():
    """
    Called before EVERY request - sets up g.user and g.organization
    This enforces data isolation and permission checking
    """
    user = get_current_user()

    if not user:
        # Check for clock terminal session (employee code login, no user_id)
        if 'clock_employee_id' in session and 'organization_id' in session:
            # Clock terminal session - set up context from session
            org_id = session.get('organization_id')
            g.user = {
                'id': session.get('clock_employee_id'),
                'first_name': session.get('clock_employee_name', '').split()[0] if session.get('clock_employee_name') else '',
                'last_name': ' '.join(session.get('clock_employee_name', '').split()[1:]) if session.get('clock_employee_name') else '',
                'role': 'employee',
                'organization_id': org_id
            }
            g.organization = get_organization_by_id(org_id)
            g.is_super_admin = False
            g.is_organization_admin = False
            g.is_employee = True
            return

        # No user and no clock terminal session
        g.user = None
        g.organization = None
        g.is_super_admin = False
        g.is_organization_admin = False
        g.is_employee = False
        return

    # Set user
    g.user = user

    # Determine user type
    g.is_super_admin = (user['role'] == 'super_admin' and user['can_switch_organizations'])
    g.is_organization_admin = (user['role'] == 'organization_admin')
    g.is_employee = (user['role'] == 'employee')

    # Set organization context based on user type
    if g.is_super_admin:
        # Super Admin: Can switch organizations via session
        # Use current_organization_id from session (set when they click "Enter Dashboard")
        org_id = session.get('current_organization_id') or user.get('current_organization_id')
        g.organization = get_organization_by_id(org_id) if org_id else None
    else:
        # REGULAR USER (Organization Admin or Employee)
        # LOCKED to their organization_id - CANNOT change
        # This is the CRITICAL security boundary
        if user['organization_id']:
            g.organization = get_organization_by_id(user['organization_id'])
        else:
            g.organization = None

    # Detect subdomain and enforce organization
    host = request.host
    subdomain = get_subdomain_from_host(host)

    if subdomain and subdomain != 'admin':
        org = get_organization_by_slug(subdomain)

        if org:
            # If user is NOT super admin, enforce they can only access their org's subdomain
            if not g.is_super_admin:
                if user['organization_id'] != org['id']:
                    # User trying to access another organization's subdomain
                    g.organization = None
                    return  # Will trigger 403 in route handlers

            # Set organization from subdomain
            g.organization = org

def log_audit(action, entity_type=None, entity_id=None, changes=None):
    """
    Log user action to audit log

    Args:
        action: String describing the action (e.g., 'created_product', 'deleted_employee')
        entity_type: Type of entity (e.g., 'product', 'employee', 'organization')
        entity_id: ID of the entity
        changes: Dict of before/after values (will be JSON serialized)
    """
    if not hasattr(g, 'user') or not g.user:
        return

    org_id = g.organization['id'] if hasattr(g, 'organization') and g.organization else None
    user_id = g.user['id']

    changes_json = json.dumps(changes) if changes else None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log
        (organization_id, user_id, action, entity_type, entity_id, changes, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        org_id,
        user_id,
        action,
        entity_type,
        entity_id,
        changes_json,
        request.remote_addr,
        request.headers.get('User-Agent')
    ))
    conn.commit()
    conn.close()

# ==========================================
# AUTHENTICATION DECORATORS
# ==========================================

def login_required(f):
    """Require user to be logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Require super admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))

        if not g.is_super_admin:
            if request.is_json:
                return jsonify({'error': 'Super admin access required'}), 403
            return jsonify({'error': 'Access denied - Super admin only'}), 403

        return f(*args, **kwargs)
    return decorated_function

def organization_required(f):
    """Require organization context to be set"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'organization') or not g.organization:
            if request.is_json:
                return jsonify({'error': 'Organization context required'}), 400
            return jsonify({'error': 'No organization selected'}), 400
        return f(*args, **kwargs)
    return decorated_function

def organization_admin_required(f):
    """Require organization admin role (or super admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))

        if not (g.is_super_admin or g.is_organization_admin):
            if request.is_json:
                return jsonify({'error': 'Organization admin access required'}), 403
            return jsonify({'error': 'Access denied - Admin only'}), 403

        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    """
    Require specific permission

    Usage:
        @app.route('/api/products')
        @login_required
        @organization_required
        @permission_required('products.view')
        def get_products():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('auth.login'))

            if not user_has_permission(g.user, permission):
                if request.is_json:
                    return jsonify({
                        'error': f'Permission denied',
                        'required_permission': permission
                    }), 403
                return jsonify({'error': f'Access denied - {permission} required'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def own_data_only(entity_type, id_param='id'):
    """
    Require user to only access their own data
    Used for employee self-service features

    Args:
        entity_type: 'employee', 'paycheck', 'time_entry'
        id_param: Name of the route parameter containing the entity ID

    Usage:
        @app.route('/api/employees/<int:id>/paystubs')
        @login_required
        @permission_required('payroll.view_own')
        @own_data_only('employee', 'id')
        def get_own_paystubs(id):
            # User can only access if id matches their employee record
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                return jsonify({'error': 'Authentication required'}), 401

            # Super admin and org admin can access any data
            if g.is_super_admin or g.is_organization_admin:
                return f(*args, **kwargs)

            # Employee: verify they're accessing their own data
            entity_id = kwargs.get(id_param)

            # Get user's employee record
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM employees
                WHERE user_id = ? AND organization_id = ?
            """, (g.user['id'], g.organization['id']))

            employee = cursor.fetchone()
            conn.close()

            if not employee:
                return jsonify({'error': 'Employee record not found'}), 404

            employee_id = employee['id']

            # Verify access based on entity type
            if entity_type == 'employee':
                if int(entity_id) != employee_id:
                    return jsonify({'error': 'Access denied - can only view own data'}), 403
            elif entity_type == 'paycheck':
                # Verify paycheck belongs to this employee
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT employee_id FROM paychecks WHERE id = ?
                """, (entity_id,))
                paycheck = cursor.fetchone()
                conn.close()

                if not paycheck or paycheck['employee_id'] != employee_id:
                    return jsonify({'error': 'Access denied'}), 403
            elif entity_type == 'time_entry':
                # Verify time entry belongs to this employee
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT employee_id FROM time_entries WHERE id = ?
                """, (entity_id,))
                entry = cursor.fetchone()
                conn.close()

                if not entry or entry['employee_id'] != employee_id:
                    return jsonify({'error': 'Access denied'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
