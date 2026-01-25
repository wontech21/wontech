#!/usr/bin/env python3
"""
Migration: Add last_password_change column to users table
Adds password change tracking for session invalidation
"""

import sqlite3
import os

def run_migration():
    """Add last_password_change column to users table in master.db"""

    # Get database path
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'master.db')

    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'last_password_change' in columns:
            print("✅ Column 'last_password_change' already exists")
            conn.close()
            return True

        # Add the column
        print("📝 Adding 'last_password_change' column to users table...")
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN last_password_change TIMESTAMP
        """)

        # Set default value for existing users
        print("📝 Setting default timestamp for existing users...")
        cursor.execute("""
            UPDATE users
            SET last_password_change = CURRENT_TIMESTAMP
            WHERE last_password_change IS NULL
        """)

        conn.commit()
        print("✅ Migration completed successfully!")
        print(f"   - Added 'last_password_change' column")
        print(f"   - Updated {cursor.rowcount} existing user records")

        conn.close()
        return True

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🔄 Running Migration: Add last_password_change column")
    print("="*60 + "\n")

    success = run_migration()

    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")

    print("\n" + "="*60 + "\n")
