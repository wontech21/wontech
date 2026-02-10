"""
Authentication Routes
- Login / Logout
- Password management
"""

from flask import Blueprint, jsonify, request, session, redirect, render_template, g
import sqlite3

from db_manager import get_master_db, get_org_db
from utils.auth import hash_password, verify_password
from middleware.tenant_context_separate_db import login_required, organization_required

auth_bp = Blueprint('auth', __name__)

from utils.audit import log_audit


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'GET':
        # Check if already logged in
        if 'user_id' in session:
            if hasattr(g, 'is_super_admin') and g.is_super_admin:
                return redirect('/admin/dashboard')
            return redirect('/dashboard')
        return render_template('login.html')

    # POST - Handle login
    data = request.json if request.is_json else request.form
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        if request.is_json:
            return jsonify({'error': 'Email and password required'}), 400
        return render_template('login.html', error='Email and password required')

    # Check credentials in master database
    conn = get_master_db()
    cursor = conn.cursor()

    # Try to query with last_password_change column (for backward compatibility)
    try:
        cursor.execute("""
            SELECT id, organization_id, password_hash, role, active, first_name, last_name, last_password_change
            FROM users
            WHERE email = ?
        """, (email,))
    except sqlite3.OperationalError as e:
        # Column doesn't exist yet (pre-migration), query without it
        if 'no such column: last_password_change' in str(e):
            cursor.execute("""
                SELECT id, organization_id, password_hash, role, active, first_name, last_name
                FROM users
                WHERE email = ?
            """, (email,))
        else:
            raise

    user = cursor.fetchone()
    conn.close()

    if not user:
        if request.is_json:
            return jsonify({'error': 'Invalid credentials'}), 401
        return render_template('login.html', error='Invalid email or password')

    if not user['active']:
        if request.is_json:
            return jsonify({'error': 'Account is inactive'}), 403
        return render_template('login.html', error='Your account has been deactivated')

    if not verify_password(password, user['password_hash']):
        if request.is_json:
            return jsonify({'error': 'Invalid credentials'}), 401
        return render_template('login.html', error='Invalid email or password')

    # Set session with password change timestamp for session invalidation
    session['user_id'] = user['id']
    user_dict = dict(user)
    if 'last_password_change' in user_dict:
        session['last_password_change'] = user_dict['last_password_change']

    # Update last login
    conn = get_master_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
    """, (user['id'],))
    conn.commit()
    conn.close()

    # Redirect based on user role
    if user['role'] == 'super_admin':
        redirect_url = '/admin/dashboard'
    elif user['role'] == 'employee':
        redirect_url = '/employee/portal'
    else:
        # organization_admin and others go to business dashboard
        redirect_url = '/dashboard'

    if request.is_json:
        return jsonify({
            'success': True,
            'redirect': redirect_url,
            'user': {
                'name': f"{user['first_name']} {user['last_name']}",
                'role': user['role']
            }
        })

    return redirect(redirect_url)

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """User logout"""
    session.clear()
    return redirect('/login')

@auth_bp.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password - requires current password verification"""
    data = request.json

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    # Validate input
    if not current_password or not new_password:
        return jsonify({'error': 'Current password and new password are required'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    # Check if user is authenticated
    if not hasattr(g, 'user') or not g.user:
        return jsonify({'error': 'User not authenticated'}), 401

    # Get current user from master database
    conn = get_master_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, email, password_hash
            FROM users
            WHERE id = ?
        """, (g.user['id'],))

        user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        # Verify current password
        if not verify_password(current_password, user['password_hash']):
            conn.close()
            log_audit('failed_password_change', 'user', user['id'], user['email'], {
                'reason': 'incorrect_current_password'
            })
            return jsonify({'error': 'Current password is incorrect'}), 401

        # Hash new password
        new_password_hash = hash_password(new_password)

        # Update password in database and set timestamp to invalidate all sessions
        # Try with last_password_change column first (for backward compatibility)
        try:
            cursor.execute("""
                UPDATE users
                SET password_hash = ?,
                    last_password_change = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_password_hash, user['id']))

            # Get the new last_password_change timestamp to update current session
            cursor.execute("""
                SELECT last_password_change FROM users WHERE id = ?
            """, (user['id'],))
            updated_user = cursor.fetchone()
            new_timestamp = updated_user['last_password_change'] if updated_user else None

        except sqlite3.OperationalError as e:
            # Column doesn't exist yet (pre-migration), update without it
            if 'no such column: last_password_change' in str(e):
                cursor.execute("""
                    UPDATE users
                    SET password_hash = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_password_hash, user['id']))
                new_timestamp = None
            else:
                raise

        conn.commit()
        conn.close()

        # Update current session with new timestamp to keep THIS session valid
        # This invalidates all OTHER sessions but keeps the current one active
        if new_timestamp:
            session['last_password_change'] = new_timestamp

        # Log successful password change
        log_audit('changed_password', 'user', user['id'], user['email'], {
            'action': 'password_changed'
        })

        return jsonify({
            'success': True,
            'message': 'Password changed successfully. All other sessions have been logged out for security.'
        })

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error in change_password: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500
