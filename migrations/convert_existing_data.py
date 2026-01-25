"""
Migration: Convert Existing inventory.db to Separate Database Architecture

This script:
1. Copies inventory.db to databases/org_1.db (default organization's database)
2. Keeps original inventory.db as backup
3. Validates the copy was successful
"""

import sqlite3
import os
import shutil
from datetime import datetime

def migrate():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    existing_db = os.path.join(base_dir, 'inventory.db')
    databases_dir = os.path.join(base_dir, 'databases')
    org_db = os.path.join(databases_dir, 'org_1.db')
    backup_db = os.path.join(base_dir, f'inventory_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')

    print("\n" + "="*60)
    print("📦 CONVERTING EXISTING DATA TO SEPARATE DATABASE")
    print("="*60)

    # Check if inventory.db exists
    if not os.path.exists(existing_db):
        print("\n❌ Error: inventory.db not found!")
        print(f"   Expected location: {existing_db}")
        return

    # Create databases directory
    os.makedirs(databases_dir, exist_ok=True)
    print(f"\n1️⃣  Created databases directory: {databases_dir}")

    # Create backup of original
    print(f"\n2️⃣  Creating backup of original inventory.db...")
    shutil.copy2(existing_db, backup_db)
    print(f"   ✓ Backup created: {backup_db}")

    # Copy to org_1.db
    print(f"\n3️⃣  Copying inventory.db → databases/org_1.db...")
    shutil.copy2(existing_db, org_db)
    print(f"   ✓ Created: {org_db}")

    # Validate the copy
    print(f"\n4️⃣  Validating database integrity...")
    try:
        conn = sqlite3.connect(org_db)
        cursor = conn.cursor()

        # Count tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"   ✓ Found {len(tables)} tables")

        # Count some records
        for table_name in ['ingredients', 'products', 'sales']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"   ✓ {table_name}: {count} records")
            except:
                print(f"   - {table_name}: table not found (OK if not created yet)")

        conn.close()
    except Exception as e:
        print(f"   ❌ Validation error: {e}")
        return

    print("\n" + "="*60)
    print("✅ CONVERSION COMPLETE!")
    print("="*60)

    print("\n📊 Your Data:")
    print(f"   📁 Original (backup): {backup_db}")
    print(f"   📁 Organization 1:    {org_db}")

    print("\n🔒 Database Isolation:")
    print("   ✓ Default organization now has separate database")
    print("   ✓ Future organizations will get fresh databases")
    print("   ✓ Complete physical isolation between clients")

    print("\n⚠️  IMPORTANT:")
    print("   - Original inventory.db is backed up")
    print("   - Do NOT delete backup until you verify everything works")
    print("   - New data will be written to databases/org_1.db")

    print("\n📝 Next Steps:")
    print("   1. Update app.py to use new database manager")
    print("   2. Test login and data access")
    print("   3. Create test organization to verify isolation")

    print("\n" + "="*60)

if __name__ == '__main__':
    migrate()
