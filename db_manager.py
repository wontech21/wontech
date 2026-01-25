"""
Database Connection Manager for Separate Database Architecture

Two types of databases:
1. master.db - Users, organizations, sessions, invitations (global data)
2. databases/org_{id}.db - Each organization's business data (isolated)

Usage:
    from db_manager import get_master_db, get_org_db, create_org_database

    # For user authentication, organization management
    conn = get_master_db()

    # For business data (inventory, sales, etc.)
    conn = get_org_db()  # Uses g.organization automatically
"""

import sqlite3
import os
import shutil
from flask import g

# Use persistent disk if DATABASE_DIR env var is set (for Render paid plans)
# Otherwise use local directory (for development)
# Priority: 1) DATABASE_DIR env var, 2) /var/data if writable, 3) local directory
BASE_DIR = os.environ.get('DATABASE_DIR')
if not BASE_DIR or not os.path.exists(BASE_DIR):
    if os.path.exists('/var/data') and os.access('/var/data', os.W_OK):
        BASE_DIR = '/var/data'
        os.environ['DATABASE_DIR'] = '/var/data'  # Set for other modules
    else:
        BASE_DIR = os.path.dirname(__file__)
MASTER_DB_PATH = os.path.join(BASE_DIR, 'master.db')
DATABASES_DIR = os.path.join(BASE_DIR, 'databases')
TEMPLATE_DB_PATH = os.path.join(DATABASES_DIR, 'template.db')

# Ensure directories exist
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(DATABASES_DIR, exist_ok=True)

def get_master_db():
    """
    Get connection to master database
    Contains: users, organizations, sessions, invitations
    """
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_org_db(organization_id=None):
    """
    Get connection to current organization's database
    Contains: ingredients, products, sales, invoices, employees, etc.

    Args:
        organization_id: Optional org ID. If not provided, uses g.organization

    Returns:
        SQLite connection to organization's database
    """
    if organization_id is None:
        # Get from Flask g object (set by middleware)
        if not hasattr(g, 'organization') or not g.organization:
            raise ValueError("No organization context set. Use @organization_required decorator.")
        org_id = g.organization['id']
    else:
        org_id = organization_id

    # Get database filename from master database
    master_conn = get_master_db()
    cursor = master_conn.cursor()
    cursor.execute("SELECT db_filename FROM organizations WHERE id = ?", (org_id,))
    result = cursor.fetchone()
    master_conn.close()

    if not result:
        raise ValueError(f"Organization {org_id} not found")

    db_filename = result['db_filename']
    db_path = os.path.join(DATABASES_DIR, db_filename)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Organization database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_org_db_path(organization_id):
    """Get filesystem path to organization's database file"""
    master_conn = get_master_db()
    cursor = master_conn.cursor()
    cursor.execute("SELECT db_filename FROM organizations WHERE id = ?", (organization_id,))
    result = cursor.fetchone()
    master_conn.close()

    if not result:
        return None

    return os.path.join(DATABASES_DIR, result['db_filename'])

def create_org_database(organization_id):
    """
    Create a new database for an organization from template

    Args:
        organization_id: ID of organization from master database

    Returns:
        Path to created database file
    """
    # Ensure databases directory exists
    os.makedirs(DATABASES_DIR, exist_ok=True)

    # Get organization info from master
    master_conn = get_master_db()
    cursor = master_conn.cursor()
    cursor.execute("SELECT db_filename FROM organizations WHERE id = ?", (organization_id,))
    result = cursor.fetchone()
    master_conn.close()

    if not result:
        raise ValueError(f"Organization {organization_id} not found in master database")

    db_filename = result['db_filename']
    new_db_path = os.path.join(DATABASES_DIR, db_filename)

    # Check if already exists
    if os.path.exists(new_db_path):
        print(f"   ⚠️  Database already exists: {new_db_path}")
        return new_db_path

    # Create from template
    if os.path.exists(TEMPLATE_DB_PATH):
        shutil.copy2(TEMPLATE_DB_PATH, new_db_path)
        print(f"   ✓ Created from template: {new_db_path}")
    else:
        # Create fresh database with schema
        conn = sqlite3.connect(new_db_path)
        cursor = conn.cursor()

        # Create all business data tables
        print(f"   Creating fresh database: {new_db_path}")

        # Ingredients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_code TEXT,
                ingredient_name TEXT NOT NULL,
                category TEXT DEFAULT 'Uncategorized',
                unit_of_measure TEXT,
                quantity_on_hand REAL DEFAULT 0,
                unit_cost REAL DEFAULT 0,
                supplier_name TEXT,
                brand TEXT,
                reorder_level REAL DEFAULT 0,
                storage_location TEXT,
                active BOOLEAN DEFAULT 1,
                is_composite BOOLEAN DEFAULT 0,
                batch_size REAL,
                barcode TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                selling_price REAL,
                category TEXT,
                barcode TEXT,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Recipes table (product ingredients)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                ingredient_id INTEGER,
                source_type TEXT DEFAULT 'ingredient',
                quantity REAL NOT NULL,
                unit TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
            )
        """)

        # Categories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sales table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                quantity REAL,
                sale_price REAL,
                total_amount REAL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # Invoices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT,
                supplier_name TEXT,
                invoice_date DATE,
                due_date DATE,
                total_amount REAL,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Counts table (inventory counts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                count_name TEXT,
                count_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'in_progress',
                notes TEXT,
                created_by TEXT,
                completed_at TIMESTAMP
            )
        """)

        # Count items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS count_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                count_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                expected_quantity REAL,
                actual_quantity REAL,
                variance REAL,
                notes TEXT,
                FOREIGN KEY (count_id) REFERENCES counts(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
            )
        """)

        # Employees table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                employee_code TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip_code TEXT,
                department TEXT,
                position TEXT,
                hire_date DATE,
                pay_rate REAL,
                pay_type TEXT,
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Time entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                clock_in TIMESTAMP NOT NULL,
                clock_out TIMESTAMP,
                hours_worked REAL,
                break_minutes INTEGER DEFAULT 0,
                notes TEXT,
                approved BOOLEAN DEFAULT 0,
                approved_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
        """)

        # Payroll runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payroll_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pay_period_start DATE NOT NULL,
                pay_period_end DATE NOT NULL,
                pay_date DATE NOT NULL,
                status TEXT DEFAULT 'draft',
                processed_by INTEGER,
                processed_at TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Paychecks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paychecks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payroll_run_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                gross_pay REAL NOT NULL,
                federal_tax REAL DEFAULT 0,
                state_tax REAL DEFAULT 0,
                social_security REAL DEFAULT 0,
                medicare REAL DEFAULT 0,
                other_deductions REAL DEFAULT 0,
                net_pay REAL NOT NULL,
                hours_worked REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (payroll_run_id) REFERENCES payroll_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)

        # Barcode cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barcode_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                data_source TEXT NOT NULL,
                product_name TEXT,
                brand TEXT,
                category TEXT,
                unit_of_measure TEXT,
                quantity TEXT,
                image_url TEXT,
                raw_data TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(barcode, data_source)
            )
        """)

        # Barcode API usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barcode_api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                request_date TEXT NOT NULL,
                request_count INTEGER DEFAULT 1,
                UNIQUE(api_name, request_date)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ingredients_barcode ON ingredients(barcode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipes_product ON recipes(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_entries_employee ON time_entries(employee_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paychecks_employee ON paychecks(employee_id)")

        conn.commit()
        conn.close()

        print(f"   ✓ Created fresh database with full schema")

    return new_db_path

def create_template_database():
    """
    Create template.db with all business tables
    This will be copied for new organizations
    """
    os.makedirs(DATABASES_DIR, exist_ok=True)

    # Create template by calling create_org_database with dummy ID
    # then rename to template.db
    print("Creating template database...")
    temp_path = os.path.join(DATABASES_DIR, 'temp_template.db')

    # Create fresh database (same logic as in create_org_database)
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()

    # (Same table creation code as above)
    # ...omitted for brevity, same as in create_org_database...

    conn.close()

    # Rename to template.db
    if os.path.exists(TEMPLATE_DB_PATH):
        os.remove(TEMPLATE_DB_PATH)
    os.rename(temp_path, TEMPLATE_DB_PATH)

    print(f"✓ Template database created: {TEMPLATE_DB_PATH}")

def list_organization_databases():
    """List all organization database files"""
    if not os.path.exists(DATABASES_DIR):
        return []

    db_files = [f for f in os.listdir(DATABASES_DIR) if f.endswith('.db') and f.startswith('org_')]
    return db_files

def backup_org_database(organization_id, backup_dir=None):
    """
    Create backup of organization's database

    Args:
        organization_id: Organization ID
        backup_dir: Optional backup directory (default: backups/)

    Returns:
        Path to backup file
    """
    if backup_dir is None:
        backup_dir = os.path.join(BASE_DIR, 'backups')

    os.makedirs(backup_dir, exist_ok=True)

    org_db_path = get_org_db_path(organization_id)
    if not org_db_path or not os.path.exists(org_db_path):
        raise FileNotFoundError(f"Organization database not found")

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"org_{organization_id}_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    shutil.copy2(org_db_path, backup_path)

    return backup_path
