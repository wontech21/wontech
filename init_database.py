#!/usr/bin/env python3
"""
Database Initialization Script
Initializes master.db and creates super admin if database doesn't exist
Safe to run multiple times - only creates if missing
"""

import os
import sys

def init_database():
    """Initialize database if it doesn't exist"""

    # Get paths - use DATABASE_DIR env var if set (for persistent disk on Render)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.environ.get('DATABASE_DIR', script_dir)
    master_db_path = os.path.join(base_dir, 'master.db')
    databases_dir = os.path.join(base_dir, 'databases')

    print("\n" + "="*70)
    print("🔄 DATABASE INITIALIZATION CHECK")
    print("="*70)
    print(f"\n📁 Working directory: {os.getcwd()}")
    print(f"📁 Script directory: {script_dir}")
    print(f"📁 Database path: {master_db_path}")
    print(f"📁 Databases directory: {databases_dir}")

    # Check if master.db exists
    if os.path.exists(master_db_path):
        print(f"\n✅ Database already exists at: {master_db_path}")
        file_size = os.path.getsize(master_db_path)
        print(f"   File size: {file_size} bytes")
        print("   Skipping initialization...")
        print("\n" + "="*70 + "\n")
        return True

    print(f"\n⚠️  Database not found at: {master_db_path}")
    print("   Creating new database...")

    # Ensure databases directory exists
    os.makedirs(databases_dir, exist_ok=True)
    print(f"   ✓ Created databases directory: {databases_dir}")

    # Run the master database creation script
    try:
        # Import and run the migration
        sys.path.insert(0, os.path.join(script_dir, 'migrations'))
        from create_master_database import migrate

        print("\n📝 Running master database creation script...")
        migrate()

        print("\n✅ DATABASE INITIALIZATION COMPLETE!")
        print("\n🔐 Default Super Admin Credentials:")
        print("   📧 Email: admin@firingup.com")
        print("   🔑 Password: admin123")
        print("   ⚠️  CHANGE PASSWORD IMMEDIATELY AFTER FIRST LOGIN!")

        print("\n" + "="*70 + "\n")
        return True

    except Exception as e:
        print(f"\n❌ Database initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70 + "\n")
        return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
