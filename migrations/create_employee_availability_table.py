"""
Create employee_availability table for scheduling preferences
"""

import sqlite3
import os

def run_migration(db_path):
    """Create employee_availability table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='employee_availability'
        """)

        if cursor.fetchone():
            print(f"  ⊙ Table 'employee_availability' already exists in {db_path}")
            conn.close()
            return True

        # Create employee_availability table
        cursor.execute("""
            CREATE TABLE employee_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,

                -- Availability details
                day_of_week INTEGER NOT NULL, -- 0=Sunday, 1=Monday, etc.
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,

                -- Optional date range (for temporary availability)
                effective_from DATE,
                effective_until DATE,

                -- Type
                availability_type TEXT DEFAULT 'recurring', -- recurring, temporary, unavailable
                notes TEXT,

                -- Audit
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (organization_id) REFERENCES organizations(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX idx_availability_employee
            ON employee_availability(employee_id)
        """)

        cursor.execute("""
            CREATE INDEX idx_availability_day
            ON employee_availability(day_of_week)
        """)

        cursor.execute("""
            CREATE INDEX idx_availability_org
            ON employee_availability(organization_id)
        """)

        conn.commit()
        print(f"  ✓ Created 'employee_availability' table in {db_path}")
        print(f"  ✓ Created indexes on employee_id, day_of_week, organization_id")
        return True

    except Exception as e:
        print(f"  ✗ Error creating employee_availability table in {db_path}: {e}")
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
    print("Creating Employee Availability Table")
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
