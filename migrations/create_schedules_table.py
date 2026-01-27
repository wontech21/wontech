"""
Migration: Create Schedules Table
Creates the schedules table for employee shift scheduling and management
"""

import sqlite3
import os

def create_schedules_table(db_path):
    """Create schedules table in the specified database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create schedules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,

            -- Schedule details
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,

            -- Shift information
            shift_type TEXT DEFAULT 'regular',
            position TEXT,
            notes TEXT,

            -- Break information
            break_duration INTEGER DEFAULT 30,

            -- Status tracking
            status TEXT DEFAULT 'scheduled',

            -- Change request tracking
            change_requested_by INTEGER,
            change_request_reason TEXT,
            change_request_status TEXT,
            change_request_date TIMESTAMP,

            -- Audit fields
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Foreign keys
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (updated_by) REFERENCES users(id),
            FOREIGN KEY (change_requested_by) REFERENCES employees(id)
        )
    """)

    # Create indexes for performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedules_employee
        ON schedules(employee_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedules_date
        ON schedules(date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedules_org_date
        ON schedules(organization_id, date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedules_status
        ON schedules(status)
    """)

    conn.commit()
    conn.close()

    print(f"✅ Schedules table created successfully in {db_path}")

def run_migration():
    """Run migration on all organization databases"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    databases_dir = os.path.join(base_dir, 'databases')

    # Get all organization databases
    if os.path.exists(databases_dir):
        for db_file in os.listdir(databases_dir):
            if db_file.startswith('org_') and db_file.endswith('.db'):
                db_path = os.path.join(databases_dir, db_file)
                print(f"\n🔧 Migrating {db_file}...")
                create_schedules_table(db_path)
    else:
        print("⚠️  No databases directory found")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("SCHEDULES TABLE MIGRATION")
    print("="*60)
    run_migration()
    print("\n✨ Migration completed successfully!")
    print("="*60 + "\n")
