#!/usr/bin/env python3
"""
WONTECH Business Management Platform
Flask web application for multi-tenant business management.
Multi-Tenant SaaS Platform with Separate Database Architecture.
"""

from flask import Flask, jsonify, request, g, session
import sqlite3
import os
from utils.auth import hash_password

# Multi-tenant database management
from db_manager import get_master_db, get_org_db, create_master_db, create_org_database

# Multi-tenant middleware
from middleware.tenant_context_separate_db import set_tenant_context

# Legacy route modules (old register_* pattern)
from crud_operations import register_crud_routes
from sales_operations import register_sales_routes
from sales_analytics import register_analytics_routes
from barcode_routes import register_barcode_routes

# Blueprint route modules
from routes import (
    admin_bp, employee_bp, pos_bp,
    auth_bp, portal_bp, attendance_bp,
    employee_mgmt_bp, inventory_app_bp, analytics_app_bp,
    storefront_bp, menu_admin_bp,
)
from routes.schedule_routes import schedule_bp
from routes.payroll_routes import payroll_bp
from routes.share_routes import share_bp

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'firing-up-secret-key-CHANGE-ME-IN-PRODUCTION')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ---------------------------------------------------------------------------
# Database initialization at startup
# Delegates to db_manager.py — the single source of truth for all schemas.
# Never creates truncated schemas, never deletes existing databases.
# ---------------------------------------------------------------------------
def _seed_default_org_and_admin():
    """Insert default organization + admin user if they don't exist yet."""
    from db_manager import MASTER_DB_PATH
    conn = sqlite3.connect(MASTER_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO organizations
        (id, organization_name, slug, db_filename, owner_name, owner_email, plan_type, features)
        VALUES
        (1, 'Default Organization', 'default', 'org_1.db', 'System Admin', 'admin@wontech.com', 'enterprise',
         '["barcode_scanning", "payroll", "invoicing"]')
    """)

    password_hash = hash_password('admin123')

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (organization_id, email, password_hash, first_name, last_name, role,
         can_switch_organizations, permissions, active)
        VALUES
        (1, 'admin@wontech.com', ?, 'Admin', 'User', 'organization_admin', 0, '["*"]', 1)
    """, (password_hash,))

    conn.commit()
    conn.close()


def ensure_databases_exist():
    """Ensure master.db and default org database exist with full canonical schema."""
    from db_manager import MASTER_DB_PATH, DATABASES_DIR

    create_master_db()
    _seed_default_org_and_admin()

    org_db_path = os.path.join(DATABASES_DIR, 'org_1.db')
    if not os.path.exists(org_db_path):
        create_org_database(1)

    print("Databases verified.")


ensure_databases_exist()

# ---------------------------------------------------------------------------
# Register all blueprints
# ---------------------------------------------------------------------------
app.register_blueprint(admin_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(pos_bp)
app.register_blueprint(share_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(portal_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(employee_mgmt_bp)
app.register_blueprint(inventory_app_bp)
app.register_blueprint(analytics_app_bp)
app.register_blueprint(storefront_bp)
app.register_blueprint(menu_admin_bp)

# Register legacy route modules (old register_* pattern)
register_crud_routes(app)
register_sales_routes(app)
register_analytics_routes(app)
register_barcode_routes(app)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
@app.before_request
def before_request_handler():
    """Set tenant context for multi-tenant isolation"""
    try:
        set_tenant_context()
    except Exception as e:
        print(f"Warning: set_tenant_context failed: {type(e).__name__}: {e}")
        g.user = None
        g.organization = None
        g.org_db_path = None
        g.is_super_admin = False
        g.is_organization_admin = False
        g.is_employee = False

# ---------------------------------------------------------------------------
# System endpoints (health check, schema re-init)
# ---------------------------------------------------------------------------
@app.route('/health')
def health_check():
    """Health check endpoint to diagnose deployment issues"""
    possible_dirs = [
        os.environ.get('DATABASE_DIR'),
        '/var/data',
        os.path.dirname(__file__)
    ]

    base_dir = None
    for dir_path in possible_dirs:
        if dir_path and os.path.exists(dir_path):
            base_dir = dir_path
            break
    if not base_dir:
        base_dir = os.path.dirname(__file__)

    master_db_path = os.path.join(base_dir, 'master.db')
    databases_dir = os.path.join(base_dir, 'databases')
    org1_db_path = os.path.join(databases_dir, 'org_1.db')

    health_info = {
        'status': 'healthy',
        'database_dir': base_dir,
        'master_db_exists': os.path.exists(master_db_path),
        'databases_dir_exists': os.path.exists(databases_dir),
        'org1_db_exists': os.path.exists(org1_db_path),
        'errors': []
    }

    try:
        conn = get_master_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM organizations")
        health_info['master_db_orgs'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        health_info['master_db_users'] = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        health_info['errors'].append(f"Master DB error: {str(e)}")
        health_info['status'] = 'unhealthy'

    try:
        if os.path.exists(org1_db_path):
            conn = sqlite3.connect(org1_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ingredients")
            health_info['org1_db_ingredients'] = cursor.fetchone()[0]
            conn.close()
        else:
            health_info['errors'].append("org_1.db does not exist")
            health_info['status'] = 'unhealthy'
    except Exception as e:
        health_info['errors'].append(f"Org DB error: {str(e)}")
        health_info['status'] = 'unhealthy'

    return jsonify(health_info), 200 if health_info['status'] == 'healthy' else 500


@app.route('/force-reinit')
def force_reinit():
    """Re-run schema migrations on existing databases (safe, never deletes data)."""
    from db_manager import MASTER_DB_PATH, DATABASES_DIR
    log = []
    try:
        create_master_db()
        log.append("Master database schema verified.")

        _seed_default_org_and_admin()
        log.append("Default org/admin seeded (or already exists).")

        org1_path = os.path.join(DATABASES_DIR, 'org_1.db')
        create_org_database(1)
        log.append(f"org_1.db schema verified: {os.path.exists(org1_path)}")

        return jsonify({'status': 'success', 'log': log})
    except Exception as e:
        import traceback
        log.append(f"Error: {str(e)}")
        log.append(traceback.format_exc())
        return jsonify({'status': 'error', 'log': log}), 500


# ---------------------------------------------------------------------------
# Legacy migration helpers (kept for one-time use, not called at startup)
# ---------------------------------------------------------------------------
def migrate_database():
    """Add price tracking columns to ingredients table and create categories table if they don't exist"""
    conn = get_org_db()
    cursor = conn.cursor()

    columns_added = False

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO categories (category_name)
            SELECT DISTINCT category FROM ingredients WHERE category IS NOT NULL
        """)

        cursor.execute("PRAGMA table_info(ingredients)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'last_unit_price' not in columns:
            cursor.execute("ALTER TABLE ingredients ADD COLUMN last_unit_price REAL")
            columns_added = True

        if 'average_unit_price' not in columns:
            cursor.execute("ALTER TABLE ingredients ADD COLUMN average_unit_price REAL")
            columns_added = True

        if 'units_per_case' not in columns:
            cursor.execute("ALTER TABLE ingredients ADD COLUMN units_per_case REAL DEFAULT 1")
            columns_added = True

        conn.commit()
        conn.close()

        if columns_added:
            recalculate_all_prices()
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Migration failed: {str(e)}")


def recalculate_all_prices():
    """Recalculate price history for all ingredients from invoice data"""
    try:
        conn_inventory = get_org_db()
        cursor_inventory = conn_inventory.cursor()

        conn_invoices = get_org_db()
        cursor_invoices = conn_invoices.cursor()

        cursor_inventory.execute("SELECT DISTINCT ingredient_code FROM ingredients")
        ingredient_codes = [row['ingredient_code'] for row in cursor_inventory.fetchall()]

        for ingredient_code in ingredient_codes:
            _update_ingredient_prices(ingredient_code, cursor_invoices, cursor_inventory)

        conn_inventory.commit()
        conn_inventory.close()
        conn_invoices.close()
    except Exception as e:
        print(f"Error recalculating prices: {str(e)}")


def _update_ingredient_prices(ingredient_code, cursor_invoices, cursor_inventory):
    """Update last_unit_price and average_unit_price for an ingredient"""
    try:
        cursor_invoices.execute("""
            SELECT ili.unit_price, i.invoice_date, ili.quantity
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_code = ?
            ORDER BY i.invoice_date DESC
        """, (ingredient_code,))

        price_records = cursor_invoices.fetchall()

        if price_records:
            last_price = price_records[0]['unit_price']
            total_cost = sum(rec['unit_price'] * rec['quantity'] for rec in price_records)
            total_quantity = sum(rec['quantity'] for rec in price_records)
            average_price = total_cost / total_quantity if total_quantity > 0 else last_price

            cursor_inventory.execute("""
                UPDATE ingredients
                SET last_unit_price = ?, average_unit_price = ?
                WHERE ingredient_code = ?
            """, (last_price, average_price, ingredient_code))
    except Exception as e:
        print(f"Error updating prices for {ingredient_code}: {str(e)}")


# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("\n" + "="*60)
    print("WONTECH - MULTI-TENANT BUSINESS PLATFORM")
    print("="*60)
    print("\nDashboard starting at: http://localhost:5001")
    print("Master Database: Connected (master.db)")
    print("Organization Databases: databases/org_*.db")
    print("Multi-Tenant Mode: ENABLED")
    print("\nPress CTRL+C to stop the server\n")
    print("="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5001)
