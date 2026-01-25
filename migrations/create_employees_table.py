#!/usr/bin/env python3
"""
Create employees table in organization database
Employees are linked to users in master.db via user_id
"""

import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import get_org_db_path

def create_employees_table():
    """Create employees table in org_1 database"""
    org_db_path = get_org_db_path(1)

    if not org_db_path or not os.path.exists(org_db_path):
        print(f"❌ Organization database not found: {org_db_path}")
        return False

    print(f"📊 Creating employees table in: {org_db_path}")

    conn = sqlite3.connect(org_db_path)
    cursor = conn.cursor()

    # Create employees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            user_id INTEGER,
            employee_code TEXT UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            position TEXT,
            department TEXT,
            hire_date DATE,
            hourly_rate REAL DEFAULT 0,
            salary REAL DEFAULT 0,
            employment_type TEXT DEFAULT 'full-time',
            status TEXT DEFAULT 'active',
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create index on user_id for fast lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_employees_user_id ON employees(user_id)
    """)

    # Create index on employee_code
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_employees_code ON employees(employee_code)
    """)

    # Create index on status
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status)
    """)

    conn.commit()

    # Verify table was created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees'")
    if cursor.fetchone():
        print("✅ employees table created successfully")

        # Show table structure
        cursor.execute("PRAGMA table_info(employees)")
        columns = cursor.fetchall()
        print(f"\n📋 Table structure ({len(columns)} columns):")
        for col in columns:
            print(f"   - {col[1]}: {col[2]}")

        conn.close()
        return True
    else:
        print("❌ Failed to create employees table")
        conn.close()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("🔧 EMPLOYEES TABLE MIGRATION")
    print("=" * 60)
    print()

    success = create_employees_table()

    print()
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        sys.exit(1)
