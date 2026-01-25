"""
Inline database creation - no external dependencies
This creates master.db and org_1.db with all necessary tables
"""
import sqlite3
import os
import hashlib
import secrets

def create_databases():
    """Create both master.db and org_1.db with full schema"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    master_db_path = os.path.join(base_dir, 'master.db')
    databases_dir = os.path.join(base_dir, 'databases')
    org_db_path = os.path.join(databases_dir, 'org_1.db')

    print("\n" + "="*70)
    print("🔧 INLINE DATABASE CREATION")
    print("="*70)
    print(f"📁 Base directory: {base_dir}")
    print(f"📁 Master DB: {master_db_path}")
    print(f"📁 Org DB: {org_db_path}")

    # Ensure directories exist
    os.makedirs(databases_dir, exist_ok=True)

    # Create master.db
    print("\n1️⃣  Creating master.db...")
    conn = sqlite3.connect(master_db_path)
    cursor = conn.cursor()

    # Organizations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            db_filename TEXT NOT NULL UNIQUE,
            owner_name TEXT NOT NULL,
            owner_email TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            logo_url TEXT,
            primary_color TEXT DEFAULT '#2563eb',
            plan_type TEXT DEFAULT 'basic',
            subscription_status TEXT DEFAULT 'active',
            monthly_price DECIMAL(10,2) DEFAULT 99.00,
            billing_email TEXT,
            max_employees INTEGER DEFAULT 50,
            max_products INTEGER DEFAULT 1000,
            max_storage_mb INTEGER DEFAULT 5000,
            features TEXT,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT,
            avatar_url TEXT,
            role TEXT NOT NULL,
            permissions TEXT,
            can_switch_organizations BOOLEAN DEFAULT 0,
            current_organization_id INTEGER,
            active BOOLEAN DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (current_organization_id) REFERENCES organizations(id) ON DELETE SET NULL
        )
    """)

    # Insert default organization
    cursor.execute("""
        INSERT OR IGNORE INTO organizations
        (id, organization_name, slug, db_filename, owner_name, owner_email, plan_type, features)
        VALUES
        (1, 'Default Organization', 'default', 'org_1.db', 'System Admin', 'admin@firingup.com', 'enterprise',
         '["barcode_scanning", "payroll", "invoicing", "multi_location"]')
    """)

    # Create super admin
    salt = secrets.token_hex(16)
    password = 'admin123'
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    password_hash = f"{salt}${pwd_hash}"

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (organization_id, email, password_hash, first_name, last_name, role,
         can_switch_organizations, permissions, active)
        VALUES
        (NULL, 'admin@firingup.com', ?, 'Super', 'Admin', 'super_admin', 1, '["*"]', 1)
    """, (password_hash,))

    conn.commit()
    conn.close()
    print("   ✓ Master database created with 1 org and 1 admin user")

    # Create org_1.db
    print("\n2️⃣  Creating org_1.db...")
    conn = sqlite3.connect(org_db_path)
    cursor = conn.cursor()

    # Ingredients
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

    # Products
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

    # Invoices
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

    conn.commit()
    conn.close()
    print("   ✓ Organization database created with all tables")

    print("\n✅ DATABASE CREATION COMPLETE!")
    print("="*70 + "\n")
    return True

if __name__ == '__main__':
    create_databases()
