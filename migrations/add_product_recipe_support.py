#!/usr/bin/env python3
"""
Migration: Add Products-as-Ingredients Support
Date: 2026-01-20
Description: Adds source_type column to recipes table to enable products to be used as ingredients in other products
"""

import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import get_db_connection, INVENTORY_DB


def run_migration():
    """Add source_type column to recipes table"""
    print("=" * 60)
    print("Migration: Add Products-as-Ingredients Support")
    print("=" * 60)

    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("PRAGMA table_info(recipes)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'source_type' in columns:
            print("✓ Column 'source_type' already exists in recipes table")
            print("  Migration already applied, skipping...")
            conn.close()
            return True

        print("\n1. Adding source_type column to recipes table...")
        cursor.execute("""
            ALTER TABLE recipes
            ADD COLUMN source_type TEXT DEFAULT 'ingredient' NOT NULL
        """)
        print("   ✓ Column added successfully")

        print("\n2. Verifying existing recipes have default value...")
        cursor.execute("SELECT COUNT(*) FROM recipes WHERE source_type = 'ingredient'")
        count = cursor.fetchone()[0]
        print(f"   ✓ {count} existing recipes set to 'ingredient'")

        print("\n3. Creating index on source_type column...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recipes_source_type
            ON recipes(source_type)
        """)
        print("   ✓ Index created successfully")

        conn.commit()
        conn.close()

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("- All existing recipes are marked as 'ingredient' type")
        print("- New recipes can use source_type='product' for products")
        print("- Backward compatibility maintained")

        return True

    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def rollback_migration():
    """Remove source_type column from recipes table"""
    print("=" * 60)
    print("Rollback: Remove Products-as-Ingredients Support")
    print("=" * 60)

    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # SQLite doesn't support DROP COLUMN directly, need to recreate table
        print("\n1. Creating backup of recipes table...")
        cursor.execute("""
            CREATE TABLE recipes_backup AS
            SELECT id, product_id, ingredient_id, quantity_needed, unit_of_measure, notes
            FROM recipes
        """)
        print("   ✓ Backup created")

        print("\n2. Dropping original recipes table...")
        cursor.execute("DROP TABLE recipes")
        print("   ✓ Table dropped")

        print("\n3. Recreating recipes table without source_type...")
        cursor.execute("""
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                quantity_needed REAL NOT NULL,
                unit_of_measure TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
            )
        """)
        print("   ✓ Table recreated")

        print("\n4. Restoring data from backup...")
        cursor.execute("""
            INSERT INTO recipes (id, product_id, ingredient_id, quantity_needed, unit_of_measure, notes)
            SELECT id, product_id, ingredient_id, quantity_needed, unit_of_measure, notes
            FROM recipes_backup
        """)
        print("   ✓ Data restored")

        print("\n5. Dropping backup table...")
        cursor.execute("DROP TABLE recipes_backup")
        print("   ✓ Backup removed")

        conn.commit()
        conn.close()

        print("\n" + "=" * 60)
        print("Rollback completed successfully!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ Rollback failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Manage products-as-ingredients migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    if args.rollback:
        success = rollback_migration()
    else:
        success = run_migration()

    sys.exit(0 if success else 1)
