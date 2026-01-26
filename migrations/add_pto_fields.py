"""
Add PTO (Paid Time Off) tracking fields to employees table
"""

import sqlite3
import os

def run_migration(db_path):
    """Add PTO fields to employees table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(employees)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add PTO fields if they don't exist
        if 'pto_hours_available' not in columns:
            cursor.execute("""
                ALTER TABLE employees
                ADD COLUMN pto_hours_available REAL DEFAULT 80.0
            """)
            print(f"  ✓ Added pto_hours_available column to {db_path}")

        if 'pto_hours_used' not in columns:
            cursor.execute("""
                ALTER TABLE employees
                ADD COLUMN pto_hours_used REAL DEFAULT 0.0
            """)
            print(f"  ✓ Added pto_hours_used column to {db_path}")

        if 'pto_accrual_rate' not in columns:
            cursor.execute("""
                ALTER TABLE employees
                ADD COLUMN pto_accrual_rate REAL DEFAULT 0.0385
            """)
            print(f"  ✓ Added pto_accrual_rate column to {db_path}")
            print(f"    (Default rate: 0.0385 hours/day = ~80 hours/year)")

        if 'pto_last_accrual_date' not in columns:
            cursor.execute("""
                ALTER TABLE employees
                ADD COLUMN pto_last_accrual_date DATE
            """)
            print(f"  ✓ Added pto_last_accrual_date column to {db_path}")

        conn.commit()
        return True

    except Exception as e:
        print(f"  ✗ Error adding PTO fields to {db_path}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    # Run on all organization databases
    databases_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'databases')

    if not os.path.exists(databases_dir):
        print("Databases directory not found!")
        exit(1)

    # Find all org databases
    db_files = [f for f in os.listdir(databases_dir) if f.startswith('org_') and f.endswith('.db')]

    if not db_files:
        print("No organization databases found!")
        exit(1)

    print(f"\n{'='*60}")
    print("Adding PTO Fields to Employees Table")
    print(f"{'='*60}\n")

    success_count = 0
    for db_file in sorted(db_files):
        db_path = os.path.join(databases_dir, db_file)
        print(f"Processing {db_file}...")
        if run_migration(db_path):
            success_count += 1
        print()

    print(f"{'='*60}")
    print(f"Migration complete: {success_count}/{len(db_files)} databases updated")
    print(f"{'='*60}\n")
