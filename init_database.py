#!/usr/bin/env python3
"""
Database Initialization Script
Delegates to db_manager.py — the single source of truth for all schemas.
Safe to run multiple times (all statements use IF NOT EXISTS).

Usage:
    python init_database.py
"""

import os
import sys
import hashlib
import secrets
import sqlite3


def init_database():
    """Initialize master.db and default org database if they don't exist."""
    # Ensure we can import db_manager from the same directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, script_dir)

    from db_manager import (
        create_master_db,
        create_org_database,
        MASTER_DB_PATH,
        DATABASES_DIR,
    )

    print("Database initialization check...")

    # 1. Create/verify master database schema
    create_master_db()

    # 2. Seed default organization + admin user
    conn = sqlite3.connect(MASTER_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO organizations
        (id, organization_name, slug, db_filename, owner_name, owner_email, plan_type, features)
        VALUES
        (1, 'Default Organization', 'default', 'org_1.db', 'System Admin', 'admin@wontech.com', 'enterprise',
         '["barcode_scanning", "payroll", "invoicing"]')
    """)

    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256(('admin123' + salt).encode()).hexdigest()
    password_hash = f"{salt}${pwd_hash}"

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (organization_id, email, password_hash, first_name, last_name, role,
         can_switch_organizations, permissions, active)
        VALUES
        (1, 'admin@wontech.com', ?, 'Admin', 'User', 'organization_admin', 0, '["*"]', 1)
    """, (password_hash,))

    conn.commit()
    conn.close()

    # 3. Create/verify default org database
    org_db_path = os.path.join(DATABASES_DIR, 'org_1.db')
    if not os.path.exists(org_db_path):
        create_org_database(1)
        print(f"Created org database: {org_db_path}")
    else:
        # Still run to pick up any new tables/indexes
        create_org_database(1)
        print(f"Org database verified: {org_db_path}")

    print("Database initialization complete.")
    print("Default admin: admin@wontech.com / admin123")
    return True


if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
