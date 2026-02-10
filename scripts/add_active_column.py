#!/usr/bin/env python3
"""
Add active column to ingredients table
"""
import sqlite3

def add_active_column():
    print("\n" + "="*70)
    print("🔧 ADDING ACTIVE COLUMN TO INGREDIENTS TABLE")
    print("="*70 + "\n")

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(ingredients)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'active' in columns:
            print("✓ Active column already exists")
        else:
            print("Adding active column...")
            cursor.execute("""
                ALTER TABLE ingredients
                ADD COLUMN active INTEGER DEFAULT 1
            """)
            print("✓ Active column added successfully")

        # Create index for active status
        print("Creating index...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ingredients_active
            ON ingredients(active)
        """)
        print("✓ Index created")

        conn.commit()

        # Show count of active vs inactive items
        cursor.execute("SELECT COUNT(*) FROM ingredients WHERE active = 1")
        active_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM ingredients WHERE active = 0")
        inactive_count = cursor.fetchone()[0]

        print(f"\n📊 Current Status:")
        print(f"   Active items: {active_count}")
        print(f"   Inactive items: {inactive_count}")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {str(e)}\n")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    add_active_column()
