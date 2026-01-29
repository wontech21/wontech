"""
Migration to create payroll_history table for storing processed payroll records.
This prevents wage changes from affecting historical payroll calculations.
"""

import sqlite3
import os
from db_manager import get_org_db_path

def run_migration(org_id):
    """Run migration for a specific organization database"""
    db_path = get_org_db_path(org_id)

    if not os.path.exists(db_path):
        print(f"Database for org {org_id} does not exist")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create payroll_history table to store processed payroll records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payroll_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                pay_period_start DATE NOT NULL,
                pay_period_end DATE NOT NULL,
                pay_period_type TEXT NOT NULL DEFAULT 'weekly',

                -- Wage rate at time of processing (locked in)
                hourly_rate_used REAL DEFAULT 0,
                salary_used REAL DEFAULT 0,

                -- Hours
                total_hours REAL DEFAULT 0,
                regular_hours REAL DEFAULT 0,
                ot_hours REAL DEFAULT 0,

                -- Calculated pay (locked in)
                regular_wage REAL DEFAULT 0,
                ot_wage REAL DEFAULT 0,
                tips REAL DEFAULT 0,
                gross_pay REAL DEFAULT 0,

                -- Additional info
                job_classification TEXT,
                position TEXT,
                notes TEXT,

                -- Processing info
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_by INTEGER,

                -- Unique constraint to prevent duplicate processing
                UNIQUE(organization_id, employee_id, pay_period_start, pay_period_end),

                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (processed_by) REFERENCES users(id)
            )
        """)

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payroll_history_period
            ON payroll_history(organization_id, pay_period_start, pay_period_end)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payroll_history_employee
            ON payroll_history(employee_id, pay_period_start)
        """)

        conn.commit()
        print(f"Successfully created payroll_history table for org {org_id}")
        return True

    except Exception as e:
        print(f"Error creating payroll_history table for org {org_id}: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()


def run_for_all_orgs():
    """Run migration for all organization databases"""
    # Find all org databases
    db_dir = os.path.dirname(get_org_db_path(1))

    for filename in os.listdir(db_dir):
        if filename.startswith('org_') and filename.endswith('.db'):
            org_id = int(filename.replace('org_', '').replace('.db', ''))
            run_migration(org_id)


if __name__ == '__main__':
    run_for_all_orgs()
