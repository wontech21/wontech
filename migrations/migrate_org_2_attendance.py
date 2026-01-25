#!/usr/bin/env python3
"""
Migrate Organization 2 database to support attendance tracking
Adds missing columns and creates attendance table
"""

import sqlite3
import os

def migrate_org_2():
    """Migrate org_2.db to match org_1.db schema"""

    db_path = 'databases/org_2.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return

    print(f"🔄 Migrating {db_path}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Step 1: Add organization_id column to employees
        print("\n1️⃣  Adding organization_id column to employees table...")
        cursor.execute("ALTER TABLE employees ADD COLUMN organization_id INTEGER DEFAULT 2")
        print("   ✓ Added organization_id column")

        # Step 2: Add status column to employees
        print("\n2️⃣  Adding status column to employees table...")
        cursor.execute("ALTER TABLE employees ADD COLUMN status TEXT DEFAULT 'active'")
        print("   ✓ Added status column")

        # Step 3: Update status based on active column
        print("\n3️⃣  Migrating active → status values...")
        cursor.execute("UPDATE employees SET status = CASE WHEN active = 1 THEN 'active' ELSE 'inactive' END")
        rows_updated = cursor.rowcount
        print(f"   ✓ Updated {rows_updated} employee records")

        # Step 4: Add other missing columns
        print("\n4️⃣  Adding other missing columns...")

        # Check if columns exist before adding
        cursor.execute("PRAGMA table_info(employees)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        columns_to_add = [
            ("hourly_rate", "REAL DEFAULT 0"),
            ("salary", "REAL DEFAULT 0"),
            ("employment_type", "TEXT DEFAULT 'full-time'"),
            ("notes", "TEXT")
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}")
                print(f"   ✓ Added {col_name} column")
            else:
                print(f"   ⊘ {col_name} already exists")

        # Step 5: Migrate pay_rate to hourly_rate if data exists
        if 'pay_rate' in existing_columns:
            print("\n5️⃣  Migrating pay_rate → hourly_rate...")
            cursor.execute("UPDATE employees SET hourly_rate = pay_rate WHERE pay_type = 'hourly'")
            cursor.execute("UPDATE employees SET salary = pay_rate WHERE pay_type = 'salary'")
            print(f"   ✓ Migrated pay data")

        # Step 6: Create attendance table
        print("\n6️⃣  Creating attendance table...")
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
        print("   ✓ Created attendance table")

        # Commit all changes
        conn.commit()

        # Verify migration
        print("\n" + "="*60)
        print("📊 MIGRATION SUMMARY")
        print("="*60)

        cursor.execute("SELECT COUNT(*) FROM employees")
        emp_count = cursor.fetchone()[0]
        print(f"✓ Employees table: {emp_count} records")

        cursor.execute("SELECT COUNT(*) FROM attendance")
        att_count = cursor.fetchone()[0]
        print(f"✓ Attendance table: {att_count} records")

        cursor.execute("SELECT COUNT(*) FROM employees WHERE organization_id = 2")
        org_count = cursor.fetchone()[0]
        print(f"✓ Employees with organization_id=2: {org_count}")

        print("="*60)
        print("\n✅ Migration completed successfully!")
        print("\n🎯 Organization 2 (TEST) is now ready for clock terminal!")
        print("   Access at: http://localhost:5001/clock/2")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_org_2()
