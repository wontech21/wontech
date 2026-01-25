#!/usr/bin/env python3
"""
Create attendance table for employee clock in/out tracking
"""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import get_org_db_path

def create_attendance_table():
    """Create attendance table in org_1 database"""

    org_db_path = get_org_db_path(1)
    print(f"Creating attendance table in: {org_db_path}")

    conn = sqlite3.connect(org_db_path)
    cursor = conn.cursor()

    # Create attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            user_id INTEGER,
            clock_in TIMESTAMP,
            clock_out TIMESTAMP,
            break_start TIMESTAMP,
            break_end TIMESTAMP,
            total_hours REAL DEFAULT 0,
            break_duration INTEGER DEFAULT 0,
            status TEXT DEFAULT 'clocked_out',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (id),
            FOREIGN KEY (organization_id) REFERENCES organizations (id)
        )
    """)

    # Create indexes for performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_attendance_employee
        ON attendance (employee_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_attendance_date
        ON attendance (clock_in)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_attendance_status
        ON attendance (status)
    """)

    conn.commit()

    print("✅ Attendance table created successfully!")
    print("✅ Indexes created successfully!")

    # Verify
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
    if cursor.fetchone():
        print("✅ Verified: attendance table exists")

        cursor.execute("PRAGMA table_info(attendance)")
        columns = cursor.fetchall()
        print(f"✅ Table has {len(columns)} columns:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
    else:
        print("❌ ERROR: attendance table not found after creation")

    conn.close()

if __name__ == '__main__':
    create_attendance_table()
