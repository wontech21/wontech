"""
Migration: Multi-Tenant Architecture with Three-Tier Access Control
- Converts single-tenant system to multi-tenant SaaS platform
- Three access tiers: Super Admin, Organization Admin, Employee
- Organization-level data isolation via organization_id
- Permission-based authorization system
- Subdomain-based tenant routing
"""

import sqlite3
import os
import hashlib
import secrets
from datetime import datetime

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def column_exists(cursor, table, column):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def table_exists(cursor, table):
    """Check if a table exists"""
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    return cursor.fetchone() is not None

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inventory.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("🏢 MULTI-TENANT MIGRATION")
    print("="*60)

    try:
        # ==========================================
        # STEP 1: Create Organizations Table
        # ==========================================
        print("\n1️⃣  Creating organizations table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
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

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_organizations_slug
            ON organizations(slug)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_organizations_active
            ON organizations(active)
        """)

        # ==========================================
        # STEP 2: Create Users Table (Three-Tier Roles)
        # ==========================================
        print("\n2️⃣  Creating users table with three-tier roles...")
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
                can_switch_organizations BOOLEAN DEFAULT 0,  -- Only TRUE for super_admin
                current_organization_id INTEGER,  -- For super admin: which org they're viewing

                -- Status
                active BOOLEAN DEFAULT 1,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (current_organization_id) REFERENCES organizations(id) ON DELETE SET NULL,

                -- CRITICAL CONSTRAINT: Regular users MUST have organization_id
                CHECK (
                    (role = 'super_admin' AND organization_id IS NULL) OR
                    (role != 'super_admin' AND organization_id IS NOT NULL)
                )
            )
        """)
        print("   ✓ Users table created with role constraints")

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_organization
            ON users(organization_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_role
            ON users(role)
        """)

        # ==========================================
        # STEP 3: Create Permission Definitions
        # ==========================================
        print("\n3️⃣  Creating permission definitions...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_key TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,  -- inventory, employees, payroll, sales, settings
                description TEXT NOT NULL,
                required_role TEXT,  -- Minimum role required (super_admin, organization_admin, employee)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Define all available permissions
        permissions = [
            # Inventory Permissions
            ('inventory.view', 'inventory', 'View inventory items', 'employee'),
            ('inventory.create', 'inventory', 'Create new inventory items', 'organization_admin'),
            ('inventory.edit', 'inventory', 'Edit existing inventory items', 'organization_admin'),
            ('inventory.delete', 'inventory', 'Delete inventory items', 'organization_admin'),
            ('inventory.count', 'inventory', 'Perform inventory counts', 'employee'),

            # Employee Management Permissions
            ('employees.view', 'employees', 'View employee list and profiles', 'organization_admin'),
            ('employees.create', 'employees', 'Add new employees', 'organization_admin'),
            ('employees.edit', 'employees', 'Edit employee information', 'organization_admin'),
            ('employees.delete', 'employees', 'Delete employees', 'organization_admin'),
            ('employees.view_own', 'employees', 'View own employee profile', 'employee'),
            ('employees.edit_own', 'employees', 'Edit own employee profile', 'employee'),

            # Payroll Permissions
            ('payroll.view', 'payroll', 'View payroll information', 'organization_admin'),
            ('payroll.process', 'payroll', 'Process payroll runs', 'organization_admin'),
            ('payroll.approve', 'payroll', 'Approve paychecks', 'organization_admin'),
            ('payroll.view_own', 'payroll', 'View own paystubs', 'employee'),

            # Time Clock Permissions
            ('timeclock.clockin', 'timeclock', 'Clock in/out', 'employee'),
            ('timeclock.view_own', 'timeclock', 'View own time entries', 'employee'),
            ('timeclock.view_all', 'timeclock', 'View all time entries', 'organization_admin'),
            ('timeclock.edit_all', 'timeclock', 'Edit any time entries', 'organization_admin'),

            # Sales Permissions
            ('sales.view', 'sales', 'View sales records', 'employee'),
            ('sales.create', 'sales', 'Record new sales', 'employee'),
            ('sales.edit', 'sales', 'Edit sales records', 'organization_admin'),
            ('sales.delete', 'sales', 'Delete sales records', 'organization_admin'),

            # Products & Recipes Permissions
            ('products.view', 'products', 'View products and recipes', 'employee'),
            ('products.create', 'products', 'Create new products', 'organization_admin'),
            ('products.edit', 'products', 'Edit products and recipes', 'organization_admin'),
            ('products.delete', 'products', 'Delete products', 'organization_admin'),

            # Invoices Permissions
            ('invoices.view', 'invoices', 'View invoices', 'employee'),
            ('invoices.create', 'invoices', 'Create new invoices', 'organization_admin'),
            ('invoices.edit', 'invoices', 'Edit invoices', 'organization_admin'),
            ('invoices.delete', 'invoices', 'Delete invoices', 'organization_admin'),

            # Reports Permissions
            ('reports.view', 'reports', 'View reports and analytics', 'organization_admin'),
            ('reports.export', 'reports', 'Export report data', 'organization_admin'),

            # Settings Permissions
            ('settings.view', 'settings', 'View organization settings', 'organization_admin'),
            ('settings.edit', 'settings', 'Edit organization settings', 'organization_admin'),
            ('settings.billing', 'settings', 'Manage billing and subscription', 'organization_admin'),

            # User Management Permissions
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
        # STEP 4: Create Role Templates
        # ==========================================
        print("\n4️⃣  Creating role templates...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                default_permissions TEXT NOT NULL,  -- JSON array of permission keys
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        role_templates = [
            (
                'super_admin',
                'Super Administrator',
                'Full access to all organizations and all features',
                '["*"]'  # Wildcard = all permissions
            ),
            (
                'organization_admin',
                'Organization Administrator',
                'Full access to all features within their organization',
                '''[
                    "inventory.view", "inventory.create", "inventory.edit", "inventory.delete", "inventory.count",
                    "employees.view", "employees.create", "employees.edit", "employees.delete",
                    "payroll.view", "payroll.process", "payroll.approve",
                    "timeclock.view_all", "timeclock.edit_all",
                    "sales.view", "sales.create", "sales.edit", "sales.delete",
                    "products.view", "products.create", "products.edit", "products.delete",
                    "invoices.view", "invoices.create", "invoices.edit", "invoices.delete",
                    "reports.view", "reports.export",
                    "settings.view", "settings.edit", "settings.billing",
                    "users.view", "users.create", "users.edit", "users.delete"
                ]'''
            ),
            (
                'employee',
                'Employee',
                'Limited access to view inventory, clock in/out, and view own information',
                '''[
                    "inventory.view", "inventory.count",
                    "employees.view_own", "employees.edit_own",
                    "payroll.view_own",
                    "timeclock.clockin", "timeclock.view_own",
                    "sales.view", "sales.create",
                    "products.view",
                    "invoices.view"
                ]'''
            )
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO role_templates
            (role_name, display_name, description, default_permissions)
            VALUES (?, ?, ?, ?)
        """, role_templates)
        print("   ✓ Role templates created (super_admin, organization_admin, employee)")

        # ==========================================
        # STEP 5: Create User Sessions Table
        # ==========================================
        print("\n5️⃣  Creating user sessions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT NOT NULL UNIQUE,
                organization_id INTEGER,  -- For super admin: which org they're currently viewing
                ip_address TEXT,
                user_agent TEXT,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_token
            ON user_sessions(session_token)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON user_sessions(user_id)
        """)
        print("   ✓ User sessions table created")

        # ==========================================
        # STEP 6: Create Organization Invitations
        # ==========================================
        print("\n6️⃣  Creating organization invitations table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL,  -- organization_admin or employee
                permissions TEXT,  -- Custom permissions (optional)
                invited_by INTEGER NOT NULL,  -- user_id who sent invitation
                invitation_token TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'pending',  -- pending, accepted, expired, cancelled
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invitations_token
            ON organization_invitations(invitation_token)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invitations_email
            ON organization_invitations(email)
        """)
        print("   ✓ Organization invitations table created")

        # ==========================================
        # STEP 7: Create Audit Log
        # ==========================================
        print("\n7️⃣  Creating audit log table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,  -- admin_entered_dashboard, created_product, deleted_employee, etc.
                entity_type TEXT,  -- organization, user, product, employee, etc.
                entity_id INTEGER,
                changes TEXT,  -- JSON: before/after values
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_organization
            ON audit_log(organization_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user
            ON audit_log(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action
            ON audit_log(action)
        """)
        print("   ✓ Audit log table created")

        # ==========================================
        # STEP 8: Add organization_id to All Existing Tables
        # ==========================================
        print("\n8️⃣  Adding organization_id to existing tables...")

        # First, create a default organization for existing data
        cursor.execute("""
            INSERT OR IGNORE INTO organizations
            (id, organization_name, slug, owner_name, owner_email, plan_type, features)
            VALUES
            (1, 'Default Organization', 'default', 'System Admin', 'admin@firingup.com', 'enterprise',
             '["barcode_scanning", "payroll", "invoicing", "multi_location"]')
        """)
        default_org_id = 1
        print(f"   ✓ Default organization created (ID: {default_org_id})")

        # Tables that need organization_id
        tables_to_modify = [
            'ingredients', 'products', 'recipes', 'invoices',
            'categories', 'sales', 'counts', 'count_items'
        ]

        for table in tables_to_modify:
            if table_exists(cursor, table):
                if not column_exists(cursor, table, 'organization_id'):
                    print(f"   Adding organization_id to {table}...")
                    cursor.execute(f"""
                        ALTER TABLE {table}
                        ADD COLUMN organization_id INTEGER NOT NULL DEFAULT {default_org_id}
                        REFERENCES organizations(id) ON DELETE CASCADE
                    """)

                    # Create index for fast filtering
                    cursor.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_{table}_organization
                        ON {table}(organization_id)
                    """)
                    print(f"   ✓ {table} now has organization_id")
                else:
                    print(f"   ✓ {table} already has organization_id")

        # ==========================================
        # STEP 9: Create Super Admin User
        # ==========================================
        print("\n9️⃣  Creating super admin user...")

        # Check if super admin already exists
        cursor.execute("SELECT id FROM users WHERE role = 'super_admin' LIMIT 1")
        existing_admin = cursor.fetchone()

        if not existing_admin:
            # Create super admin with default password
            admin_email = 'admin@firingup.com'
            admin_password = 'admin123'  # User should change this immediately
            password_hash = hash_password(admin_password)

            cursor.execute("""
                INSERT INTO users
                (organization_id, email, password_hash, first_name, last_name, role,
                 can_switch_organizations, permissions, active)
                VALUES
                (NULL, ?, ?, ?, ?, ?, 1, ?, 1)
            """, (admin_email, password_hash, 'Super', 'Admin', 'super_admin', '["*"]'))

            print(f"   ✓ Super admin created")
            print(f"   📧 Email: {admin_email}")
            print(f"   🔑 Password: {admin_password}")
            print(f"   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
        else:
            print("   ✓ Super admin already exists")

        # ==========================================
        # STEP 10: Commit Changes
        # ==========================================
        conn.commit()

        print("\n" + "="*60)
        print("✅ MULTI-TENANT MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*60)

        print("\n📊 Summary:")
        cursor.execute("SELECT COUNT(*) FROM organizations")
        org_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM permission_definitions")
        perm_count = cursor.fetchone()[0]

        print(f"   Organizations: {org_count}")
        print(f"   Users: {user_count}")
        print(f"   Permissions: {perm_count}")

        print("\n🎯 Three-Tier Access Control System:")
        print("   1️⃣  Super Admin - Access all organizations, switch between clients")
        print("   2️⃣  Organization Admin - Full access within ONE organization")
        print("   3️⃣  Employee - Limited access to own data and basic features")

        print("\n🔐 Super Admin Login:")
        print("   Email: admin@firingup.com")
        print("   Password: admin123")
        print("   ⚠️  CHANGE PASSWORD IMMEDIATELY!")

        print("\n📝 Next Steps:")
        print("   1. Restart Flask application")
        print("   2. Login as super admin")
        print("   3. Change super admin password")
        print("   4. Create your first client organization")
        print("   5. Invite organization admin users")
        print("   6. Configure subdomain routing (*.firingup.com)")

        print("\n" + "="*60)

    except sqlite3.Error as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
