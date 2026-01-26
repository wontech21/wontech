"""
Create time_off_requests table for employee PTO/time off management
"""

import sqlite3
import os

def run_migration(db_path):
    """Create time_off_requests table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='time_off_requests'
        """)

        if cursor.fetchone():
            print(f"  ⊙ Table 'time_off_requests' already exists in {db_path}")
            conn.close()
            return True

        # Create time_off_requests table
        cursor.execute("""
            CREATE TABLE time_off_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,

                -- Request details
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                request_type TEXT NOT NULL, -- pto, sick, unpaid, other
                total_hours REAL NOT NULL,

                -- Status tracking
                status TEXT DEFAULT 'pending', -- pending, approved, denied
                reason TEXT,
                admin_notes TEXT,

                -- Approval workflow
                reviewed_by INTEGER, -- user_id who approved/denied
                reviewed_at TIMESTAMP,

                -- Audit
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (organization_id) REFERENCES organizations(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            )
        """)

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX idx_time_off_employee
            ON time_off_requests(employee_id)
        """)

        cursor.execute("""
            CREATE INDEX idx_time_off_status
            ON time_off_requests(status)
        """)

        cursor.execute("""
            CREATE INDEX idx_time_off_dates
            ON time_off_requests(start_date, end_date)
        """)

        cursor.execute("""
            CREATE INDEX idx_time_off_org
            ON time_off_requests(organization_id)
        """)

        conn.commit()
        print(f"  ✓ Created 'time_off_requests' table in {db_path}")
        print(f"  ✓ Created indexes on employee_id, status, dates, organization_id")
        return True

    except Exception as e:
        print(f"  ✗ Error creating time_off_requests table in {db_path}: {e}")
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
    print("Creating Time Off Requests Table")
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
