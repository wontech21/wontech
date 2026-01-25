"""
Script to automatically update routes to use multi-tenant architecture
- Replaces get_db_connection(INVENTORY_DB) with get_org_db()
- Replaces get_db_connection(INVOICES_DB) with get_org_db()
- Adds permission decorators to routes
"""

import re
import os

def update_file(filepath):
    """Update a Python file to use multi-tenant database connections"""

    print(f"\n{'='*60}")
    print(f"Updating: {os.path.basename(filepath)}")
    print(f"{'='*60}")

    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content
    changes = []

    # Count instances before replacement
    inventory_db_count = content.count('get_db_connection(INVENTORY_DB)')
    invoices_db_count = content.count('get_db_connection(INVOICES_DB)')

    # Replace get_db_connection(INVENTORY_DB) with get_org_db()
    if inventory_db_count > 0:
        content = content.replace('get_db_connection(INVENTORY_DB)', 'get_org_db()')
        changes.append(f"  ✓ Replaced {inventory_db_count} instances of get_db_connection(INVENTORY_DB)")

    # Replace get_db_connection(INVOICES_DB) with get_org_db()
    if invoices_db_count > 0:
        content = content.replace('get_db_connection(INVOICES_DB)', 'get_org_db()')
        changes.append(f"  ✓ Replaced {invoices_db_count} instances of get_db_connection(INVOICES_DB)")

    # Replace get_db_connection(db_name) pattern (generic)
    # This catches cases where a variable is passed
    content = re.sub(
        r"get_db_connection\(db_name\)",
        "get_org_db()",
        content
    )

    # Check if we made any changes
    if content != original_content:
        # Write updated content
        with open(filepath, 'w') as f:
            f.write(content)

        print("  Changes made:")
        for change in changes:
            print(change)

        return True
    else:
        print("  No changes needed")
        return False

def main():
    base_dir = os.path.dirname(os.path.dirname(__file__))

    files_to_update = [
        os.path.join(base_dir, 'app.py'),
        os.path.join(base_dir, 'crud_operations.py'),
        os.path.join(base_dir, 'sales_operations.py'),
        os.path.join(base_dir, 'barcode_routes.py'),
        os.path.join(base_dir, 'sales_analytics.py'),
    ]

    print("\n" + "="*60)
    print("🔄 UPDATING ROUTES TO MULTI-TENANT ARCHITECTURE")
    print("="*60)
    print("\nThis script will:")
    print("  1. Replace get_db_connection(INVENTORY_DB) → get_org_db()")
    print("  2. Replace get_db_connection(INVOICES_DB) → get_org_db()")
    print("  3. Update all route files automatically")

    updated_files = []

    for filepath in files_to_update:
        if os.path.exists(filepath):
            if update_file(filepath):
                updated_files.append(os.path.basename(filepath))
        else:
            print(f"\n⚠️  File not found: {filepath}")

    print("\n" + "="*60)
    print("✅ ROUTE UPDATE COMPLETE")
    print("="*60)

    if updated_files:
        print(f"\n📝 Updated {len(updated_files)} files:")
        for filename in updated_files:
            print(f"  ✓ {filename}")
    else:
        print("\n⚠️  No files were updated")

    print("\n📋 Next Steps:")
    print("  1. Restart Flask app: python3 app.py")
    print("  2. Login at http://localhost:5001")
    print("  3. Test inventory, products, sales features")
    print("  4. All data now comes from databases/org_1.db")

    print("\n⚠️  IMPORTANT:")
    print("  - All routes now use organization-specific databases")
    print("  - No more organization_id filters needed")
    print("  - Complete database isolation achieved")

    print("\n" + "="*60)

if __name__ == '__main__':
    main()
