"""
Migration: Add Barcode Support
- Adds barcode columns to ingredients and products tables
- Creates barcode_cache table for external API lookups
- Adds indexes for fast barcode lookup
"""

import sqlite3
import os

def column_exists(cursor, table, column):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inventory.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Starting barcode support migration...")

    try:
        # Add barcode column to ingredients table (if not exists)
        print("1. Checking ingredients table...")
        if not column_exists(cursor, 'ingredients', 'barcode'):
            print("   Adding barcode column to ingredients table...")
            cursor.execute("""
                ALTER TABLE ingredients ADD COLUMN barcode TEXT
            """)
            print("   ✓ Ingredients barcode column added")
        else:
            print("   ✓ Ingredients barcode column already exists")

        # Create index on ingredients barcode
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ingredients_barcode
            ON ingredients(barcode)
        """)

        # Add barcode column to products table (if not exists)
        print("2. Checking products table...")
        if not column_exists(cursor, 'products', 'barcode'):
            print("   Adding barcode column to products table...")
            cursor.execute("""
                ALTER TABLE products ADD COLUMN barcode TEXT
            """)
            print("   ✓ Products barcode column added")
        else:
            print("   ✓ Products barcode column already exists")

        # Create index on products barcode
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_barcode
            ON products(barcode)
        """)

        # Create barcode_cache table for external API results
        print("3. Creating barcode_cache table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barcode_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                data_source TEXT NOT NULL,
                product_name TEXT,
                brand TEXT,
                category TEXT,
                unit_of_measure TEXT,
                quantity TEXT,
                image_url TEXT,
                raw_data TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(barcode, data_source)
            )
        """)

        # Create index on barcode for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_barcode_cache_barcode
            ON barcode_cache(barcode)
        """)

        # Create index on data_source
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_barcode_cache_source
            ON barcode_cache(data_source)
        """)

        print("   ✓ Barcode cache table created with indexes")

        # Create barcode_api_usage table to track free tier limits
        print("4. Creating barcode_api_usage tracking table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barcode_api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                request_date TEXT NOT NULL,
                request_count INTEGER DEFAULT 1,
                UNIQUE(api_name, request_date)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_barcode_api_usage_date
            ON barcode_api_usage(api_name, request_date)
        """)

        print("   ✓ API usage tracking table created")

        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("- Restart the Flask app to load new endpoints")
        print("- Use barcode scanner in Count interface")
        print("- External APIs: Open Food Facts, UPCitemdb, Barcode Lookup")

    except sqlite3.Error as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
