"""
Migration: Create Master Database (Separate Database Architecture)

Database Structure:
- master.db - Users, organizations, sessions, invitations
- databases/org_{id}.db - Each organization's business data (completely isolated)

This provides COMPLETE PHYSICAL ISOLATION between organizations.
Even if code has a bug, impossible to access another org's data.
"""

import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def migrate():
    # Use script directory (simple and works everywhere)
    script_dir = os.path.dirname(os.path.dirname(__file__))
    base_dir = script_dir

    # Create databases directory
    db_dir = os.path.join(base_dir, 'databases')
    os.makedirs(db_dir, exist_ok=True)

    master_db_path = os.path.join(base_dir, 'master.db')

    print("\n" + "="*60)
    print("🏢 CREATING MASTER DATABASE (Separate DB Architecture)")
    print("="*60)

    conn = sqlite3.connect(master_db_path)
    cursor = conn.cursor()

    try:
        # ==========================================
        # ORGANIZATIONS TABLE
        # ==========================================
        print("\n1️⃣  Creating organizations table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                db_filename TEXT NOT NULL UNIQUE,  -- e.g., "org_1.db"
                owner_name TEXT NOT NULL,
                owner_email TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip_code TEXT,

                -- Branding
                logo_url TEXT,
                primary_color TEXT DEFAULT '#2563eb',

                -- Subscription & Billing
                plan_type TEXT DEFAULT 'basic',
                subscription_status TEXT DEFAULT 'active',
                monthly_price DECIMAL(10,2) DEFAULT 99.00,
                billing_email TEXT,

                -- Limits
                max_employees INTEGER DEFAULT 50,
                max_products INTEGER DEFAULT 1000,
                max_storage_mb INTEGER DEFAULT 5000,

                -- Features
                features TEXT,  -- JSON: ["barcode_scanning", "payroll", "invoicing"]

                -- Status
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✓ Organizations table created")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_organizations_active ON organizations(active)")

        # ==========================================
        # USERS TABLE
        # ==========================================
        print("\n2️⃣  Creating users table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER,  -- NULL for super_admin, set for org users

                -- Authentication
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,

                -- Profile
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT,
                avatar_url TEXT,

                -- Three-Tier Role System
                role TEXT NOT NULL,  -- super_admin, organization_admin, employee

                -- Granular Permissions (JSON array)
                permissions TEXT,  -- ["inventory.view", "payroll.process", "sales.create"]

                -- Organization Switching (Super Admin Only)
                can_switch_organizations BOOLEAN DEFAULT 0,
                current_organization_id INTEGER,

                -- Status
                active BOOLEAN DEFAULT 1,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (current_organization_id) REFERENCES organizations(id) ON DELETE SET NULL,

                CHECK (
                    (role = 'super_admin' AND organization_id IS NULL) OR
                    (role != 'super_admin' AND organization_id IS NOT NULL)
                )
            )
        """)
        print("   ✓ Users table created")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_organization ON users(organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

        # ==========================================
        # PERMISSION DEFINITIONS
        # ==========================================
        print("\n3️⃣  Creating permission definitions...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_key TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                required_role TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        permissions = [
            ('inventory.view', 'inventory', 'View inventory items', 'employee'),
            ('inventory.create', 'inventory', 'Create new inventory items', 'organization_admin'),
            ('inventory.edit', 'inventory', 'Edit existing inventory items', 'organization_admin'),
            ('inventory.delete', 'inventory', 'Delete inventory items', 'organization_admin'),
            ('inventory.count', 'inventory', 'Perform inventory counts', 'employee'),
            ('employees.view', 'employees', 'View employee list and profiles', 'organization_admin'),
            ('employees.create', 'employees', 'Add new employees', 'organization_admin'),
            ('employees.edit', 'employees', 'Edit employee information', 'organization_admin'),
            ('employees.delete', 'employees', 'Delete employees', 'organization_admin'),
            ('employees.view_own', 'employees', 'View own employee profile', 'employee'),
            ('employees.edit_own', 'employees', 'Edit own employee profile', 'employee'),
            ('payroll.view', 'payroll', 'View payroll information', 'organization_admin'),
            ('payroll.process', 'payroll', 'Process payroll runs', 'organization_admin'),
            ('payroll.approve', 'payroll', 'Approve paychecks', 'organization_admin'),
            ('payroll.view_own', 'payroll', 'View own paystubs', 'employee'),
            ('timeclock.clockin', 'timeclock', 'Clock in/out', 'employee'),
            ('timeclock.view_own', 'timeclock', 'View own time entries', 'employee'),
            ('timeclock.view_all', 'timeclock', 'View all time entries', 'organization_admin'),
            ('timeclock.edit_all', 'timeclock', 'Edit any time entries', 'organization_admin'),
            ('sales.view', 'sales', 'View sales records', 'employee'),
            ('sales.create', 'sales', 'Record new sales', 'employee'),
            ('sales.edit', 'sales', 'Edit sales records', 'organization_admin'),
            ('sales.delete', 'sales', 'Delete sales records', 'organization_admin'),
            ('products.view', 'products', 'View products and recipes', 'employee'),
            ('products.create', 'products', 'Create new products', 'organization_admin'),
            ('products.edit', 'products', 'Edit products and recipes', 'organization_admin'),
            ('products.delete', 'products', 'Delete products', 'organization_admin'),
            ('invoices.view', 'invoices', 'View invoices', 'employee'),
            ('invoices.create', 'invoices', 'Create new invoices', 'organization_admin'),
            ('invoices.edit', 'invoices', 'Edit invoices', 'organization_admin'),
            ('invoices.delete', 'invoices', 'Delete invoices', 'organization_admin'),
            ('reports.view', 'reports', 'View reports and analytics', 'organization_admin'),
            ('reports.export', 'reports', 'Export report data', 'organization_admin'),
            ('settings.view', 'settings', 'View organization settings', 'organization_admin'),
            ('settings.edit', 'settings', 'Edit organization settings', 'organization_admin'),
            ('settings.billing', 'settings', 'Manage billing and subscription', 'organization_admin'),
            ('users.view', 'users', 'View user list', 'organization_admin'),
            ('users.create', 'users', 'Invite new users', 'organization_admin'),
            ('users.edit', 'users', 'Edit user permissions', 'organization_admin'),
            ('users.delete', 'users', 'Delete users', 'organization_admin'),
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO permission_definitions
            (permission_key, category, description, required_role)
            VALUES (?, ?, ?, ?)
        """, permissions)
        print(f"   ✓ {len(permissions)} permissions defined")

        # ==========================================
        # ROLE TEMPLATES
        # ==========================================
        print("\n4️⃣  Creating role templates...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                default_permissions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        role_templates = [
            ('super_admin', 'Super Administrator', 'Full access to all organizations', '["*"]'),
            ('organization_admin', 'Organization Administrator', 'Full access within organization',
             '["inventory.*", "employees.*", "payroll.*", "timeclock.*", "sales.*", "products.*", "invoices.*", "reports.*", "settings.*", "users.*", "schedules.*"]'),
            ('employee', 'Employee', 'Limited access to own data',
             '["inventory.view", "inventory.count", "employees.view_own", "employees.edit_own", "payroll.view_own", "timeclock.clockin", "timeclock.view_own", "sales.view", "sales.create", "products.view", "invoices.view"]')
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO role_templates
            (role_name, display_name, description, default_permissions)
            VALUES (?, ?, ?, ?)
        """, role_templates)
        print("   ✓ Role templates created")

        # ==========================================
        # USER SESSIONS
        # ==========================================
        print("\n5️⃣  Creating user sessions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT NOT NULL UNIQUE,
                organization_id INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
        print("   ✓ User sessions table created")

        # ==========================================
        # ORGANIZATION INVITATIONS
        # ==========================================
        print("\n6️⃣  Creating organization invitations table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL,
                permissions TEXT,
                invited_by INTEGER NOT NULL,
                invitation_token TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'pending',
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invitations_token ON organization_invitations(invitation_token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invitations_email ON organization_invitations(email)")
        print("   ✓ Organization invitations table created")

        # ==========================================
        # AUDIT LOG
        # ==========================================
        print("\n7️⃣  Creating audit log table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                changes TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_organization ON audit_log(organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
        print("   ✓ Audit log table created")

        # ==========================================
        # CREATE DEFAULT ORGANIZATION
        # ==========================================
        print("\n8️⃣  Creating default organization...")
        cursor.execute("""
            INSERT OR IGNORE INTO organizations
            (id, organization_name, slug, db_filename, owner_name, owner_email, plan_type, features)
            VALUES
            (1, 'Default Organization', 'default', 'org_1.db', 'System Admin', 'admin@wontech.com', 'enterprise',
             '["barcode_scanning", "payroll", "invoicing", "multi_location"]')
        """)
        print("   ✓ Default organization created (will use existing inventory.db)")

        # ==========================================
        # CREATE SUPER ADMIN
        # ==========================================
        print("\n9️⃣  Creating super admin user...")
        admin_email = 'admin@wontech.com'
        admin_password = 'admin123'
        password_hash = hash_password(admin_password)

        cursor.execute("""
            INSERT OR IGNORE INTO users
            (organization_id, email, password_hash, first_name, last_name, role,
             can_switch_organizations, permissions, active)
            VALUES
            (NULL, ?, ?, 'Super', 'Admin', 'super_admin', 1, '["*"]', 1)
        """, (admin_email, password_hash))

        print(f"   ✓ Super admin created")
        print(f"   📧 Email: {admin_email}")
        print(f"   🔑 Password: {admin_password}")
        print(f"   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")

        conn.commit()

        print("\n" + "="*60)
        print("✅ MASTER DATABASE CREATED SUCCESSFULLY!")
        print("="*60)

        print("\n📊 Database Structure:")
        print("   📁 master.db - Users, organizations, sessions, invitations")
        print("   📁 databases/")
        print("      └── org_1.db - Default organization (from existing inventory.db)")
        print("      └── org_2.db - Future organizations")
        print("      └── org_3.db - ...")

        print("\n🔐 Complete Physical Isolation:")
        print("   ✓ Each organization has separate database file")
        print("   ✓ Impossible to access another org's data (even with code bug)")
        print("   ✓ Easy to backup individual clients")
        print("   ✓ Can delete entire client by removing database file")

        print("\n📝 Next Steps:")
        print("   1. Run: python migrations/convert_existing_data.py")
        print("   2. This will copy inventory.db → databases/org_1.db")
        print("   3. Update app.py to use dynamic database connections")
        print("   4. Start using the new architecture!")

        print("\n" + "="*60)

    except sqlite3.Error as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
