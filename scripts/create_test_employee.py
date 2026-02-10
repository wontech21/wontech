#!/usr/bin/env python3
"""
Create a test employee with login access
"""

import sqlite3
import hashlib
import secrets
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_manager import get_org_db_path, get_master_db

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def create_test_employee():
    """Create test employee: John Smith with login access"""

    # First, create user account in master.db
    print("Creating user account in master.db...")
    conn_master = get_master_db()
    cursor_master = conn_master.cursor()

    email = "john.smith@wontech.com"
    password = "Employee123!"
    password_hash = hash_password(password)

    # Check if user already exists
    cursor_master.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing = cursor_master.fetchone()

    if existing:
        print(f"❌ User with email {email} already exists (ID: {existing['id']})")
        user_id = existing['id']
    else:
        cursor_master.execute("""
            INSERT INTO users (
                organization_id, email, password_hash, first_name, last_name,
                role, permissions, active
            ) VALUES (1, ?, ?, 'John', 'Smith', 'employee', '["inventory.view"]', 1)
        """, (email, password_hash))

        user_id = cursor_master.lastrowid
        conn_master.commit()
        print(f"✅ Created user account (ID: {user_id})")

    conn_master.close()

    # Now create employee record in org database
    print("\nCreating employee record in org_1.db...")
    org_db_path = get_org_db_path(1)
    conn_org = sqlite3.connect(org_db_path)
    conn_org.row_factory = sqlite3.Row
    cursor_org = conn_org.cursor()

    # Check if employee already exists
    cursor_org.execute("SELECT id FROM employees WHERE user_id = ?", (user_id,))
    existing_emp = cursor_org.fetchone()

    if existing_emp:
        print(f"❌ Employee record already exists (ID: {existing_emp['id']})")
        employee_id = existing_emp['id']
    else:
        employee_code = "JS1001"

        cursor_org.execute("""
            INSERT INTO employees (
                organization_id, user_id, employee_code, first_name, last_name,
                email, phone, position, department, hire_date,
                hourly_rate, employment_type, status
            ) VALUES (1, ?, ?, 'John', 'Smith', ?, '(555) 123-4567',
                     'Line Cook', 'Kitchen', date('now'), 18.50, 'full-time', 'active')
        """, (user_id, employee_code, email))

        employee_id = cursor_org.lastrowid
        conn_org.commit()
        print(f"✅ Created employee record (ID: {employee_id})")

    conn_org.close()

    print("\n" + "="*60)
    print("✅ TEST EMPLOYEE CREATED SUCCESSFULLY!")
    print("="*60)
    print(f"\n📧 Email: {email}")
    print(f"🔑 Password: {password}")
    print(f"👤 Name: John Smith")
    print(f"💼 Position: Line Cook")
    print(f"🏢 Department: Kitchen")
    print(f"📋 Employee Code: JS1001")
    print(f"\n🔒 Permissions: Inventory View Only")
    print(f"\n🌐 Login at: http://localhost:5001/login")
    print()

if __name__ == '__main__':
    create_test_employee()
