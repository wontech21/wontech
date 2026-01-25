"""
Tenant Context Middleware - Separate Database Architecture

Key differences from shared DB approach:
- Uses master.db for user/org lookups
- Sets g.org_db_path to route business data queries
- Complete physical isolation between organizations
"""

from functools import wraps
from flask import g, session, request, jsonify, redirect, url_for
import sqlite3
import json
import os

def get_master_db():
    """Get master database connection"""
    from db_manager import get_master_db as _get_master_db
    return _get_master_db()

def get_current_user():
    """Get currently logged in user from master database"""
    user_id = session.get('user_id')
    if not user_id:
        return None

    conn = get_master_db()
    cursor = conn.cursor()

    # Try to query with last_password_change column (for backward compatibility)
    try:
        cursor.execute("""
            SELECT id, organization_id, email, first_name, last_name, role,
                   permissions, can_switch_organizations, current_organization_id, active,
                   last_password_change
            FROM users
            WHERE id = ? AND active = 1
        """, (user_id,))
    except sqlite3.OperationalError as e:
        # Column doesn't exist yet (pre-migration), query without it
        if 'no such column: last_password_change' in str(e):
            cursor.execute("""
                SELECT id, organization_id, email, first_name, last_name, role,
                       permissions, can_switch_organizations, current_organization_id, active
                FROM users
                WHERE id = ? AND active = 1
            """, (user_id,))
        else:
            raise

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    user = dict(row)

    # Check if password was changed - invalidate session if timestamps don't match
    # Only if the column exists
    if 'last_password_change' in user:
        session_password_timestamp = session.get('last_password_change')
        db_password_timestamp = user.get('last_password_change')

        if session_password_timestamp and db_password_timestamp:
            if session_password_timestamp != db_password_timestamp:
                # Password was changed - clear session to force re-login
                session.clear()
                return None

    return user

def get_organization_by_id(org_id):
    """Get organization by ID from master database"""
    if not org_id:
        return None

    conn = get_master_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_name, slug, db_filename, owner_name, owner_email,
               plan_type, subscription_status, active, logo_url
        FROM organizations
        WHERE id = ? AND active = 1
    """, (org_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)

def get_organization_by_slug(slug):
    """Get organization by subdomain slug from master database"""
    if not slug:
        return None

    conn = get_master_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_name, slug, db_filename, owner_name, owner_email,
               plan_type, subscription_status, active, logo_url
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
    if 'localhost' in host or '127.0.0.1' in host:
        return None

    parts = host.split('.')
    if len(parts) >= 3:
        return parts[0]

    return None

def user_has_permission(user, required_permission):
    """Check if user has a specific permission"""
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

    # Category wildcard
    category = required_permission.split('.')[0]
    if f"{category}.*" in user_permissions:
        return True

    return False

def set_tenant_context():
    """
    Called before EVERY request
    Sets g.user, g.organization, and g.org_db_path
    """
    user = get_current_user()

    # Check for clock terminal session (employee code login)
    if not user and 'clock_employee_id' in session and 'clock_org_id' in session:
        # Set minimal context for clock terminal
        g.user = None
        g.is_super_admin = False
        g.is_organization_admin = False
        g.is_employee = True

        # Set organization from clock terminal session
        org_id = session.get('clock_org_id')
        g.organization = get_organization_by_id(org_id)

        if g.organization:
            from db_manager import get_org_db_path
            g.org_db_path = get_org_db_path(g.organization['id'])
        else:
            g.org_db_path = None
        return

    if not user:
        g.user = None
        g.organization = None
        g.org_db_path = None
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

    # Set organization context
    if g.is_super_admin:
        # Super Admin: Can switch organizations
        org_id = session.get('current_organization_id') or user.get('current_organization_id')
        g.organization = get_organization_by_id(org_id) if org_id else None
    else:
        # Regular User: LOCKED to their organization
        if user['organization_id']:
            g.organization = get_organization_by_id(user['organization_id'])
        else:
            g.organization = None

    # Set database path for business data queries
    if g.organization:
        from db_manager import get_org_db_path
        g.org_db_path = get_org_db_path(g.organization['id'])
    else:
        g.org_db_path = None

    # Detect subdomain and enforce organization
    host = request.host
    subdomain = get_subdomain_from_host(host)

    if subdomain and subdomain != 'admin':
        org = get_organization_by_slug(subdomain)

        if org:
            # If user is NOT super admin, enforce they can only access their org's subdomain
            if not g.is_super_admin:
                if user['organization_id'] != org['id']:
                    g.organization = None
                    g.org_db_path = None
                    return

            # Set organization from subdomain
            g.organization = org
            from db_manager import get_org_db_path
            g.org_db_path = get_org_db_path(org['id'])

def log_audit(action, entity_type=None, entity_id=None, changes=None):
    """Log user action to audit log in master database"""
    if not hasattr(g, 'user') or not g.user:
        return

    org_id = g.organization['id'] if hasattr(g, 'organization') and g.organization else None
    user_id = g.user['id']

    changes_json = json.dumps(changes) if changes else None

    conn = get_master_db()
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
# AUTHENTICATION DECORATORS (Same as before)
# ==========================================

def login_required(f):
    """Require user to be logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Require super admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))

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
            return redirect(url_for('login'))

        if not (g.is_super_admin or g.is_organization_admin):
            if request.is_json:
                return jsonify({'error': 'Organization admin access required'}), 403
            return jsonify({'error': 'Access denied - Admin only'}), 403

        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    """Require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('login'))

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
    """Require user to only access their own data (for employees)"""
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

            # Get user's employee record from organization database
            from db_manager import get_org_db
            conn = get_org_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM employees
                WHERE user_id = ?
            """, (g.user['id'],))

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
                conn = get_org_db()
                cursor = conn.cursor()
                cursor.execute("SELECT employee_id FROM paychecks WHERE id = ?", (entity_id,))
                paycheck = cursor.fetchone()
                conn.close()

                if not paycheck or paycheck['employee_id'] != employee_id:
                    return jsonify({'error': 'Access denied'}), 403
            elif entity_type == 'time_entry':
                conn = get_org_db()
                cursor = conn.cursor()
                cursor.execute("SELECT employee_id FROM time_entries WHERE id = ?", (entity_id,))
                entry = cursor.fetchone()
                conn.close()

                if not entry or entry['employee_id'] != employee_id:
                    return jsonify({'error': 'Access denied'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
