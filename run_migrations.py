#!/usr/bin/env python3
"""
Database Migration Runner
Runs all pending migrations on master.db and organization databases
"""

import os
import sys

def main():
    """Run all migrations"""
    print("\n" + "="*70)
    print("🔄 WONTECH Database Migration Runner")
    print("="*70 + "\n")

    migrations = [
        {
            'name': 'Add last_password_change column',
            'file': 'migrations/add_last_password_change.py',
            'description': 'Adds password change tracking for session invalidation'
        }
    ]

    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    successful = 0
    failed = 0

    for migration in migrations:
        print(f"📝 Running: {migration['name']}")
        print(f"   Description: {migration['description']}")
        print(f"   File: {migration['file']}\n")

        try:
            # Import and run the migration
            migration_path = migration['file'].replace('/', '.').replace('.py', '')
            module = __import__(migration_path, fromlist=['run_migration'])

            if hasattr(module, 'run_migration'):
                result = module.run_migration()
                if result:
                    successful += 1
                    print(f"   ✅ Success\n")
                else:
                    failed += 1
                    print(f"   ❌ Failed\n")
            else:
                print(f"   ⚠️  No run_migration() function found\n")
                failed += 1

        except Exception as e:
            failed += 1
            print(f"   ❌ Error: {str(e)}\n")
            import traceback
            traceback.print_exc()

    # Summary
    print("="*70)
    print(f"\n📊 Migration Summary:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📋 Total: {len(migrations)}\n")

    if failed > 0:
        print("⚠️  Some migrations failed. Please check the errors above.")
        sys.exit(1)
    else:
        print("✅ All migrations completed successfully!")
        sys.exit(0)

if __name__ == '__main__':
    main()
