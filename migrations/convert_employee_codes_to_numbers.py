#!/usr/bin/env python3
"""
Convert existing employee codes to numbers-only format
"""

import sqlite3
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def convert_employee_codes():
    """Convert all employee codes to 4-digit numbers"""

    # Connect to databases
    db_path = 'databases/org_1.db'

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all employees
    cursor.execute("SELECT id, employee_code, first_name, last_name FROM employees")
    employees = cursor.fetchall()

    print(f"Found {len(employees)} employees")
    print("\nConverting employee codes to 4-digit numbers...\n")

    used_codes = set()
    updates = []

    for employee in employees:
        old_code = employee['employee_code']

        # Try to extract numbers from existing code
        numbers_in_code = ''.join(filter(str.isdigit, old_code))

        if numbers_in_code and len(numbers_in_code) >= 4:
            # Use first 4 digits if available
            new_code = numbers_in_code[:4]
        else:
            # Generate random 4-digit code
            while True:
                new_code = str(random.randint(1000, 9999))
                if new_code not in used_codes:
                    break

        # Ensure uniqueness
        while new_code in used_codes:
            new_code = str(random.randint(1000, 9999))

        used_codes.add(new_code)
        updates.append((new_code, employee['id']))

        print(f"✓ {employee['first_name']} {employee['last_name']}: {old_code} → {new_code}")

    # Apply updates
    print("\nApplying updates...")
    for new_code, emp_id in updates:
        cursor.execute("UPDATE employees SET employee_code = ? WHERE id = ?", (new_code, emp_id))

    conn.commit()
    conn.close()

    print(f"\n✅ Successfully converted {len(updates)} employee codes to numbers!")

if __name__ == '__main__':
    convert_employee_codes()
