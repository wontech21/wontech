#!/usr/bin/env python3
"""
Database Initialization Script
Initializes master.db and creates super admin if database doesn't exist
Safe to run multiple times - only creates if missing
"""

import os
import sys

def init_database():
    """Initialize database if it doesn't exist"""

    # Get paths - use DATABASE_DIR env var if set (for persistent disk on Render)
    # Priority: 1) DATABASE_DIR env var, 2) /var/data if writable, 3) script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.environ.get('DATABASE_DIR')
    if not base_dir or not os.path.exists(base_dir):
        if os.path.exists('/var/data') and os.access('/var/data', os.W_OK):
            base_dir = '/var/data'
            os.environ['DATABASE_DIR'] = '/var/data'
        else:
            base_dir = script_dir

    master_db_path = os.path.join(base_dir, 'master.db')
    databases_dir = os.path.join(base_dir, 'databases')

    print("\n" + "="*70)
    print("🔄 DATABASE INITIALIZATION CHECK")
    print("="*70)
    print(f"\n📁 Working directory: {os.getcwd()}")
    print(f"📁 Script directory: {script_dir}")
    print(f"📁 Database path: {master_db_path}")
    print(f"📁 Databases directory: {databases_dir}")

    # Check if master.db exists
    if os.path.exists(master_db_path):
        print(f"\n✅ Database already exists at: {master_db_path}")
        file_size = os.path.getsize(master_db_path)
        print(f"   File size: {file_size} bytes")
        print("   Skipping initialization...")
        print("\n" + "="*70 + "\n")
        return True

    print(f"\n⚠️  Database not found at: {master_db_path}")
    print("   Creating new database...")

    # Ensure databases directory exists
    os.makedirs(databases_dir, exist_ok=True)
    print(f"   ✓ Created databases directory: {databases_dir}")

    # Run the master database creation script
    try:
        # Import and run the migration
        sys.path.insert(0, os.path.join(script_dir, 'migrations'))
        from create_master_database import migrate

        print("\n📝 Running master database creation script...")
        migrate()

        # Create org_1.db for default organization (without importing db_manager to avoid Flask dependency)
        print("\n📝 Creating default organization database...")

        org_1_db_path = os.path.join(databases_dir, 'org_1.db')

        if os.path.exists(org_1_db_path):
            print(f"   ✓ Organization database already exists: {org_1_db_path}")
        else:
            # Create fresh org database with full schema
            import sqlite3
            conn = sqlite3.connect(org_1_db_path)
            cursor = conn.cursor()

            print(f"   Creating organization database with business tables...")

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

            # Recipes table
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
                    invoice_number TEXT NOT NULL UNIQUE,
                    supplier_name TEXT NOT NULL,
                    invoice_date DATE NOT NULL,
                    received_date DATE,
                    total_amount REAL DEFAULT 0,
                    payment_status TEXT DEFAULT 'pending',
                    reconciled BOOLEAN DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Invoice line items
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoice_line_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    ingredient_id INTEGER,
                    product_id INTEGER,
                    description TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit_price REAL NOT NULL,
                    total_price REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE SET NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
                )
            """)

            # Counts table
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

            # Time entries
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

            # Payroll runs
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

            # Paychecks
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

            # Barcode cache
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

            # Barcode API usage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS barcode_api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_name TEXT NOT NULL,
                    request_date TEXT NOT NULL,
                    request_count INTEGER DEFAULT 1,
                    UNIQUE(api_name, request_date)
                )
            """)

            # Purchase orders
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_number TEXT UNIQUE NOT NULL,
                    supplier_name TEXT NOT NULL,
                    order_date TEXT NOT NULL,
                    expected_delivery TEXT,
                    status TEXT DEFAULT 'PENDING',
                    total_amount REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # PO line items
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS po_line_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_id INTEGER NOT NULL,
                    ingredient_id INTEGER,
                    item_name TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit TEXT,
                    unit_price REAL NOT NULL,
                    total_price REAL NOT NULL,
                    received_quantity REAL DEFAULT 0,
                    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
                )
            """)

            # Reconciliation log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    ingredient_id INTEGER NOT NULL,
                    quantity_added REAL NOT NULL,
                    unit_cost REAL NOT NULL,
                    reconciled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    reconciled_by TEXT,
                    notes TEXT,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ingredients_barcode ON ingredients(barcode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipes_product ON recipes(product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_entries_employee ON time_entries(employee_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_paychecks_employee ON paychecks(employee_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_reconciled ON invoices(reconciled)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_line_items(invoice_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(po_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_line_items_po ON po_line_items(po_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recon_log_invoice ON reconciliation_log(invoice_id)")

            conn.commit()
            conn.close()

            print(f"   ✓ Created organization database: {org_1_db_path}")

        print("\n✅ DATABASE INITIALIZATION COMPLETE!")
        print("\n🔐 Default Super Admin Credentials:")
        print("   📧 Email: admin@firingup.com")
        print("   🔑 Password: admin123")
        print("   ⚠️  CHANGE PASSWORD IMMEDIATELY AFTER FIRST LOGIN!")

        print("\n📊 Database Structure:")
        print(f"   📁 {master_db_path}")
        print(f"   📁 {org_1_db_path}")

        print("\n" + "="*70 + "\n")
        return True

    except Exception as e:
        print(f"\n❌ Database initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70 + "\n")
        return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
