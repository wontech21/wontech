"""
Super Admin Routes
- Organization management (CRUD)
- Organization switching
- User management across all orgs
- System-wide analytics
- Billing and subscription management
"""

from flask import Blueprint, jsonify, request, session, render_template, g
import sqlite3
import json
import secrets
import os
from datetime import datetime, timedelta
from utils.auth import hash_password

# Import master database connection
from db_manager import get_master_db

from middleware import (
    super_admin_required,
    login_required,
    log_audit
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Use get_master_db() from db_manager - no local get_db() needed
# All admin routes query master.db for users and organizations

# ==========================================
# SUPER ADMIN DASHBOARD
# ==========================================

@admin_bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """Super admin dashboard - overview of all organizations"""
    conn = get_master_db()
    cursor = conn.cursor()

    # Get all organizations with stats from master.db
    cursor.execute("""
        SELECT
            o.id,
            o.organization_name,
            o.slug,
            o.owner_name,
            o.owner_email,
            o.plan_type,
            o.subscription_status,
            o.monthly_price,
            o.created_at,
            (SELECT COUNT(*) FROM users WHERE organization_id = o.id) as user_count
        FROM organizations o
        WHERE o.active = 1
        ORDER BY o.created_at DESC
    """)

    organizations = [dict(row) for row in cursor.fetchall()]

    # For each organization, get stats from their separate database
    from db_manager import get_org_db_path
    import sqlite3

    for org in organizations:
        org_db_path = get_org_db_path(org['id'])
        if org_db_path and os.path.exists(org_db_path):
            try:
                org_conn = sqlite3.connect(org_db_path)
                org_conn.row_factory = sqlite3.Row
                org_cursor = org_conn.cursor()

                # Count employees
                try:
                    org_cursor.execute("SELECT COUNT(*) as count FROM employees")
                    org['employee_count'] = org_cursor.fetchone()['count']
                except:
                    org['employee_count'] = 0

                # Count products
                try:
                    org_cursor.execute("SELECT COUNT(*) as count FROM products")
                    org['product_count'] = org_cursor.fetchone()['count']
                except:
                    org['product_count'] = 0

                # Count recent sales
                try:
                    org_cursor.execute("SELECT COUNT(*) as count FROM sales WHERE date >= date('now', '-30 days')")
                    org['sales_last_30_days'] = org_cursor.fetchone()['count']
                except:
                    org['sales_last_30_days'] = 0

                org_conn.close()
            except Exception as e:
                print(f"Error getting stats for org {org['id']}: {e}")
                org['employee_count'] = 0
                org['product_count'] = 0
                org['sales_last_30_days'] = 0
        else:
            org['employee_count'] = 0
            org['product_count'] = 0
            org['sales_last_30_days'] = 0

    # Get system-wide stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_orgs,
            SUM(CASE WHEN subscription_status = 'active' THEN 1 ELSE 0 END) as active_subscriptions,
            SUM(CASE WHEN subscription_status = 'active' THEN monthly_price ELSE 0 END) as total_mrr
        FROM organizations
        WHERE active = 1
    """)
    stats = dict(cursor.fetchone())

    cursor.execute("""
        SELECT COUNT(*) as total_users FROM users WHERE active = 1
    """)
    stats['total_users'] = cursor.fetchone()['total_users']

    conn.close()

    return render_template('admin/dashboard.html',
                         organizations=organizations,
                         stats=stats)

# ==========================================
# ORGANIZATION MANAGEMENT
# ==========================================

@admin_bp.route('/organizations')
@login_required
@super_admin_required
def list_organizations():
    """Get list of all organizations"""
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            o.id,
            o.organization_name,
            o.slug,
            o.owner_name,
            o.owner_email,
            o.phone,
            o.plan_type,
            o.subscription_status,
            o.monthly_price,
            o.max_employees,
            o.active,
            o.created_at,
            (SELECT COUNT(*) FROM users WHERE organization_id = o.id) as user_count
        FROM organizations o
        ORDER BY o.created_at DESC
    """)

    organizations = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Get employee count from each organization's database
    from db_manager import get_org_db_path
    import sqlite3

    for org in organizations:
        org_db_path = get_org_db_path(org['id'])
        if org_db_path and os.path.exists(org_db_path):
            try:
                org_conn = sqlite3.connect(org_db_path)
                org_cursor = org_conn.cursor()
                org_cursor.execute("SELECT COUNT(*) as count FROM employees")
                org['employee_count'] = org_cursor.fetchone()[0]
                org_conn.close()
            except:
                org['employee_count'] = 0
        else:
            org['employee_count'] = 0

    return jsonify({'organizations': organizations})

@admin_bp.route('/organizations/<int:org_id>')
@login_required
@super_admin_required
def get_organization(org_id):
    """Get single organization details"""
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM organizations WHERE id = ?
    """, (org_id,))

    org = cursor.fetchone()

    if not org:
        conn.close()
        return jsonify({'error': 'Organization not found'}), 404

    org_dict = dict(org)

    # Get users in this organization
    cursor.execute("""
        SELECT id, email, first_name, last_name, role, active, created_at
        FROM users
        WHERE organization_id = ?
        ORDER BY created_at DESC
    """, (org_id,))

    org_dict['users'] = [dict(row) for row in cursor.fetchall()]

    # Get recent activity
    cursor.execute("""
        SELECT
            a.action,
            a.entity_type,
            a.created_at,
            u.first_name || ' ' || u.last_name as user_name
        FROM audit_log a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.organization_id = ?
        ORDER BY a.created_at DESC
        LIMIT 20
    """, (org_id,))

    org_dict['recent_activity'] = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify(org_dict)

@admin_bp.route('/organizations/<int:org_id>/update', methods=['PUT'])
@login_required
@super_admin_required
def update_organization(org_id):
    """Update organization details"""
    data = request.json

    conn = get_master_db()
    cursor = conn.cursor()

    try:
        # Get current organization
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        org = cursor.fetchone()

        if not org:
            conn.close()
            return jsonify({'error': 'Organization not found'}), 404

        old_data = dict(org)

        # Update fields
        update_fields = []
        update_values = []

        allowed_fields = [
            'organization_name', 'owner_name', 'owner_email', 'phone',
            'address', 'city', 'state', 'zip_code', 'logo_url', 'primary_color',
            'plan_type', 'monthly_price', 'max_employees', 'max_products',
            'max_storage_mb', 'subscription_status', 'active'
        ]

        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])

        if 'features' in data:
            update_fields.append("features = ?")
            update_values.append(json.dumps(data['features']))

        if not update_fields:
            conn.close()
            return jsonify({'error': 'No fields to update'}), 400

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        update_values.append(org_id)

        cursor.execute(f"""
            UPDATE organizations
            SET {', '.join(update_fields)}
            WHERE id = ?
        """, update_values)

        conn.commit()

        # Log changes
        changes = {k: {'old': old_data.get(k), 'new': data[k]}
                  for k in data.keys() if k in old_data and old_data.get(k) != data[k]}

        log_audit('updated_organization', 'organization', org_id, changes)

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Organization updated successfully'
        })

    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@admin_bp.route('/organizations/<int:org_id>/deactivate', methods=['POST'])
@login_required
@super_admin_required
def deactivate_organization(org_id):
    """Deactivate an organization (soft delete)"""
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE organizations SET active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (org_id,))

    # Deactivate all users in this organization
    cursor.execute("""
        UPDATE users SET active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE organization_id = ?
    """, (org_id,))

    conn.commit()

    log_audit('deactivated_organization', 'organization', org_id)

    conn.close()

    return jsonify({
        'success': True,
        'message': 'Organization deactivated successfully'
    })

# ==========================================
# CREATE ORGANIZATION
# ==========================================

@admin_bp.route('/organizations/create', methods=['POST'])
@login_required
@super_admin_required
def create_organization():
    """Create a new client organization with its own database"""
    data = request.json

    # Validate required fields
    required_fields = ['organization_name', 'slug', 'owner_name', 'owner_email', 'plan_type', 'subscription_status']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Sanitize slug
    slug = data['slug'].lower().strip()
    if not slug.replace('-', '').isalnum():
        return jsonify({'error': 'Slug can only contain lowercase letters, numbers, and hyphens'}), 400

    conn = get_master_db()
    cursor = conn.cursor()

    try:
        # Check if slug or email already exists
        cursor.execute("SELECT id FROM organizations WHERE slug = ? OR owner_email = ?",
                      (slug, data['owner_email']))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Organization with this slug or owner email already exists'}), 400

        # Get next organization ID
        cursor.execute("SELECT MAX(id) FROM organizations")
        max_id = cursor.fetchone()[0]
        next_id = (max_id or 0) + 1

        # Database filename
        db_filename = f"org_{next_id}.db"

        # Insert organization
        cursor.execute("""
            INSERT INTO organizations (
                organization_name,
                slug,
                db_filename,
                owner_name,
                owner_email,
                phone,
                plan_type,
                subscription_status,
                monthly_price,
                active,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        """, (
            data['organization_name'],
            slug,
            db_filename,
            data['owner_name'],
            data['owner_email'],
            data.get('phone', ''),
            data['plan_type'],
            data['subscription_status'],
            float(data.get('monthly_price', 0))
        ))

        org_id = cursor.lastrowid
        conn.commit()

        # Create organization database from template
        from db_manager import create_org_database
        create_org_database(org_id)

        log_audit('created_organization', 'organization', org_id, {
            'organization_name': data['organization_name'],
            'slug': slug
        })

        conn.close()

        return jsonify({
            'success': True,
            'organization_id': org_id,
            'message': f'Organization "{data["organization_name"]}" created successfully'
        })

    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Failed to create organization: {str(e)}'}), 500

# ==========================================
# ORGANIZATION SWITCHING (Super Admin)
# ==========================================

@admin_bp.route('/switch-organization', methods=['POST'])
@login_required
@super_admin_required
def switch_organization():
    """
    Switch to a different organization's context
    Super admin only - allows viewing and managing client data
    """
    data = request.json
    organization_id = data.get('organization_id')

    if not organization_id:
        return jsonify({'error': 'organization_id required'}), 400

    conn = get_master_db()
    cursor = conn.cursor()

    # Verify organization exists and is active
    cursor.execute("""
        SELECT id, organization_name, slug
        FROM organizations
        WHERE id = ? AND active = 1
    """, (organization_id,))

    org = cursor.fetchone()

    if not org:
        conn.close()
        return jsonify({'error': 'Organization not found or inactive'}), 404

    # Update session
    session['current_organization_id'] = organization_id

    # Update user's current_organization_id in database
    cursor.execute("""
        UPDATE users
        SET current_organization_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (organization_id, g.user['id']))

    conn.commit()

    # Log the switch
    log_audit('admin_entered_organization', 'organization', organization_id, {
        'organization_name': org['organization_name']
    })

    conn.close()

    return jsonify({
        'success': True,
        'organization': {
            'id': org['id'],
            'name': org['organization_name'],
            'slug': org['slug']
        },
        'message': f'Switched to {org["organization_name"]}'
    })

@admin_bp.route('/exit-organization', methods=['POST'])
@login_required
@super_admin_required
def exit_organization():
    """Exit current organization context and return to admin dashboard"""
    organization_id = session.get('current_organization_id')

    # Clear session
    session.pop('current_organization_id', None)

    # Update database
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET current_organization_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (g.user['id'],))

    conn.commit()

    if organization_id:
        log_audit('admin_exited_organization', 'organization', organization_id)

    conn.close()

    return jsonify({
        'success': True,
        'message': 'Exited organization context'
    })

@admin_bp.route('/current-organization')
@login_required
@super_admin_required
def get_current_organization():
    """Get currently selected organization for super admin"""
    org_id = session.get('current_organization_id')

    if not org_id:
        return jsonify({'organization': None})

    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, organization_name, slug, owner_name
        FROM organizations
        WHERE id = ? AND active = 1
    """, (org_id,))

    org = cursor.fetchone()
    conn.close()

    if not org:
        return jsonify({'organization': None})

    return jsonify({'organization': dict(org)})

@admin_bp.route('/quick-list')
@login_required
@super_admin_required
def quick_organization_list():
    """Quick list for organization switcher dropdown"""
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, organization_name, slug
        FROM organizations
        WHERE active = 1
        ORDER BY organization_name ASC
    """)

    organizations = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'organizations': organizations})

# ==========================================
# USER INVITATION SYSTEM
# ==========================================

@admin_bp.route('/organizations/<int:org_id>/invite', methods=['POST'])
@login_required
@super_admin_required
def invite_user_to_organization(org_id):
    """
    Invite a user to join an organization
    Super admin can invite users to any organization
    """
    data = request.json

    required_fields = ['email', 'role', 'first_name', 'last_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    if data['role'] not in ['organization_admin', 'employee']:
        return jsonify({'error': 'Invalid role. Must be organization_admin or employee'}), 400

    conn = get_master_db()
    cursor = conn.cursor()

    try:
        # Verify organization exists
        cursor.execute("SELECT id FROM organizations WHERE id = ? AND active = 1", (org_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Organization not found'}), 404

        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (data['email'],))
        if cursor.fetchone():
            return jsonify({'error': 'User with this email already exists'}), 400

        # Check if invitation already exists
        cursor.execute("""
            SELECT id FROM organization_invitations
            WHERE organization_id = ? AND email = ? AND status = 'pending'
        """, (org_id, data['email']))

        if cursor.fetchone():
            return jsonify({'error': 'Invitation already sent to this email'}), 400

        # Create invitation
        invitation_token = secrets.token_urlsafe(32)
        expires_at = (datetime.now() + timedelta(days=7)).isoformat()

        # Get role permissions
        cursor.execute("""
            SELECT default_permissions FROM role_templates WHERE role_name = ?
        """, (data['role'],))

        role_template = cursor.fetchone()
        default_permissions = role_template['default_permissions'] if role_template else '[]'

        cursor.execute("""
            INSERT INTO organization_invitations
            (organization_id, email, role, permissions, invited_by, invitation_token, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            org_id,
            data['email'],
            data['role'],
            default_permissions,
            g.user['id'],
            invitation_token,
            expires_at
        ))

        invitation_id = cursor.lastrowid
        conn.commit()

        log_audit('invited_user', 'invitation', invitation_id, {
            'email': data['email'],
            'role': data['role']
        })

        conn.close()

        # TODO: Send invitation email
        invitation_url = f"https://wontech.com/accept-invitation?token={invitation_token}"

        return jsonify({
            'success': True,
            'invitation_id': invitation_id,
            'invitation_url': invitation_url,
            'message': f'Invitation sent to {data["email"]}'
        })

    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

# ==========================================
# SYSTEM ANALYTICS
# ==========================================

# ==========================================
# MANAGE ORGANIZATION MODAL API ENDPOINTS
# ==========================================

@admin_bp.route('/api/organizations/<int:org_id>')
@login_required
@super_admin_required
def get_organization_details(org_id):
    """Get organization details for manage modal"""
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM organizations WHERE id = ?
    """, (org_id,))

    org = cursor.fetchone()
    conn.close()

    if not org:
        return jsonify({'error': 'Organization not found'}), 404

    return jsonify({'success': True, 'organization': dict(org)})

@admin_bp.route('/api/organizations/<int:org_id>/users')
@login_required
@super_admin_required
def get_organization_users(org_id):
    """Get users in an organization"""
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, first_name, last_name, role, active, created_at
        FROM users
        WHERE organization_id = ?
        ORDER BY created_at DESC
    """, (org_id,))

    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'users': users})

@admin_bp.route('/api/organizations/<int:org_id>/activity')
@login_required
@super_admin_required
def get_organization_activity(org_id):
    """Get recent activity for an organization"""
    conn = get_master_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.action,
            a.entity_type,
            a.entity_id,
            a.created_at,
            u.email as user_email
        FROM audit_log a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.organization_id = ?
        ORDER BY a.created_at DESC
        LIMIT 50
    """, (org_id,))

    activities = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'activities': activities})

@admin_bp.route('/api/organizations/<int:org_id>/stats')
@login_required
@super_admin_required
def get_organization_stats(org_id):
    """Get statistics for an organization"""
    conn = get_master_db()
    cursor = conn.cursor()

    # Get org info from master db
    cursor.execute("""
        SELECT created_at,
               (SELECT COUNT(*) FROM users WHERE organization_id = ?) as user_count
        FROM organizations
        WHERE id = ?
    """, (org_id, org_id))

    org_data = cursor.fetchone()
    conn.close()

    stats = {
        'user_count': org_data['user_count'] if org_data else 0,
        'created_at': org_data['created_at'] if org_data else None
    }

    # Get stats from organization database
    from db_manager import get_org_db_path
    org_db_path = get_org_db_path(org_id)

    if org_db_path and os.path.exists(org_db_path):
        try:
            org_conn = sqlite3.connect(org_db_path)
            org_conn.row_factory = sqlite3.Row
            org_cursor = org_conn.cursor()

            # Count employees
            try:
                org_cursor.execute("SELECT COUNT(*) as count FROM employees")
                stats['employee_count'] = org_cursor.fetchone()['count']
            except:
                stats['employee_count'] = 0

            # Count products
            try:
                org_cursor.execute("SELECT COUNT(*) as count FROM products")
                stats['product_count'] = org_cursor.fetchone()['count']
            except:
                stats['product_count'] = 0

            # Count active inventory
            try:
                org_cursor.execute("SELECT COUNT(*) as count FROM inventory WHERE status = 'active'")
                stats['inventory_count'] = org_cursor.fetchone()['count']
            except:
                stats['inventory_count'] = 0

            org_conn.close()

            # Get database file size
            db_size_bytes = os.path.getsize(org_db_path)
            if db_size_bytes < 1024:
                stats['db_size'] = f"{db_size_bytes} B"
            elif db_size_bytes < 1024 * 1024:
                stats['db_size'] = f"{db_size_bytes / 1024:.2f} KB"
            else:
                stats['db_size'] = f"{db_size_bytes / (1024 * 1024):.2f} MB"

        except Exception as e:
            print(f"Error getting stats for org {org_id}: {e}")
            stats['employee_count'] = 0
            stats['product_count'] = 0
            stats['inventory_count'] = 0
            stats['db_size'] = 'N/A'
    else:
        stats['employee_count'] = 0
        stats['product_count'] = 0
        stats['inventory_count'] = 0
        stats['db_size'] = 'N/A'

    return jsonify({'success': True, 'stats': stats})

# ==========================================
# CREATE ADMIN USER
# ==========================================

@admin_bp.route('/api/organizations/<int:org_id>/create-admin', methods=['POST'])
@login_required
@super_admin_required
def create_admin_user(org_id):
    """Create an admin user for an organization directly (no invitation)"""
    data = request.json

    required_fields = ['email', 'first_name', 'last_name', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    role = data.get('role', 'organization_admin')
    if role not in ['organization_admin', 'employee']:
        return jsonify({'error': 'Invalid role. Must be organization_admin or employee'}), 400

    conn = get_master_db()
    cursor = conn.cursor()

    try:
        # Verify organization exists
        cursor.execute("SELECT id, organization_name FROM organizations WHERE id = ? AND active = 1", (org_id,))
        org = cursor.fetchone()
        if not org:
            conn.close()
            return jsonify({'error': 'Organization not found'}), 404

        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (data['email'],))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'User with this email already exists'}), 400

        # Hash password
        password_hash = hash_password(data['password'])

        # Get role permissions
        cursor.execute("""
            SELECT default_permissions FROM role_templates WHERE role_name = ?
        """, (role,))

        role_template = cursor.fetchone()
        default_permissions = role_template['default_permissions'] if role_template else '["*"]'

        # Create user in master database
        cursor.execute("""
            INSERT INTO users
            (organization_id, email, password_hash, first_name, last_name, role, permissions, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            org_id,
            data['email'],
            password_hash,
            data['first_name'],
            data['last_name'],
            role,
            default_permissions
        ))

        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # If role is employee, also create employee record in organization database
        if role == 'employee':
            from db_manager import get_org_db_path
            org_db_path = get_org_db_path(org_id)

            if org_db_path and os.path.exists(org_db_path):
                try:
                    org_conn = sqlite3.connect(org_db_path)
                    org_conn.row_factory = sqlite3.Row
                    org_cursor = org_conn.cursor()

                    # Check if employee code is provided and validate uniqueness
                    employee_code = data.get('employee_code', None)
                    if employee_code:
                        org_cursor.execute("""
                            SELECT id FROM employees WHERE employee_code = ? AND organization_id = ?
                        """, (employee_code, org_id))
                        if org_cursor.fetchone():
                            org_conn.close()
                            # Delete the user we just created in master DB since employee creation will fail
                            master_conn = get_master_db()
                            master_conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                            master_conn.commit()
                            master_conn.close()
                            return jsonify({'error': f'Employee code {employee_code} already exists in this organization'}), 400

                    # Create employee record
                    org_cursor.execute("""
                        INSERT INTO employees
                        (organization_id, user_id, first_name, last_name, email, employee_code, status, employment_type)
                        VALUES (?, ?, ?, ?, ?, ?, 'active', 'full-time')
                    """, (
                        org_id,
                        user_id,
                        data['first_name'],
                        data['last_name'],
                        data['email'],
                        employee_code
                    ))

                    org_conn.commit()
                    org_conn.close()
                except Exception as e:
                    print(f"Error creating employee record: {str(e)}")

        log_audit('created_admin_user', 'user', user_id, {
            'email': data['email'],
            'role': role,
            'organization_id': org_id,
            'organization_name': org['organization_name']
        })

        return jsonify({
            'success': True,
            'user_id': user_id,
            'message': f'User {data["email"]} created successfully for {org["organization_name"]}'
        })

    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@admin_bp.route('/api/organizations/update', methods=['POST'])
@login_required
@super_admin_required
def update_organization_api():
    """Update organization details from manage modal"""
    data = request.json
    org_id = data.get('organization_id')

    if not org_id:
        return jsonify({'error': 'organization_id required'}), 400

    conn = get_master_db()
    cursor = conn.cursor()

    try:
        # Get current organization
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        org = cursor.fetchone()

        if not org:
            conn.close()
            return jsonify({'error': 'Organization not found'}), 404

        # Update organization
        cursor.execute("""
            UPDATE organizations
            SET organization_name = ?,
                slug = ?,
                owner_name = ?,
                owner_email = ?,
                phone = ?,
                plan_type = ?,
                monthly_price = ?,
                subscription_status = ?,
                active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get('organization_name'),
            data.get('slug'),
            data.get('owner_name'),
            data.get('owner_email'),
            data.get('phone', ''),
            data.get('plan_type'),
            float(data.get('monthly_price', 0)),
            data.get('subscription_status'),
            int(data.get('active', 1)),
            org_id
        ))

        conn.commit()

        log_audit('updated_organization', 'organization', org_id, data.get('organization_name'), {
            'updated_fields': list(data.keys())
        })

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Organization updated successfully'
        })

    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500


# ==========================================
# SYSTEM ANALYTICS
# ==========================================

@admin_bp.route('/analytics/overview')
@login_required
@super_admin_required
def analytics_overview():
    """System-wide analytics for super admin"""
    conn = get_master_db()
    cursor = conn.cursor()

    # MRR by plan type
    cursor.execute("""
        SELECT
            plan_type,
            COUNT(*) as organization_count,
            SUM(monthly_price) as total_mrr
        FROM organizations
        WHERE active = 1 AND subscription_status = 'active'
        GROUP BY plan_type
    """)
    mrr_by_plan = [dict(row) for row in cursor.fetchall()]

    # User growth (last 12 months)
    cursor.execute("""
        SELECT
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as new_users
        FROM users
        WHERE created_at >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
    """)
    user_growth = [dict(row) for row in cursor.fetchall()]

    # Organization growth (last 12 months)
    cursor.execute("""
        SELECT
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as new_organizations
        FROM organizations
        WHERE created_at >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
    """)
    org_growth = [dict(row) for row in cursor.fetchall()]

    # Top organizations by activity
    cursor.execute("""
        SELECT
            o.organization_name,
            COUNT(a.id) as activity_count
        FROM organizations o
        LEFT JOIN audit_log a ON o.id = a.organization_id
        WHERE a.created_at >= date('now', '-30 days')
        GROUP BY o.id
        ORDER BY activity_count DESC
        LIMIT 10
    """)
    top_orgs = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'mrr_by_plan': mrr_by_plan,
        'user_growth': user_growth,
        'organization_growth': org_growth,
        'top_organizations': top_orgs
    })
