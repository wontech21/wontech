"""
Migration: Add Barcode Support
- Adds barcode columns to ingredients and products tables
- Creates barcode_cache table for external API lookups
- Adds indexes for fast barcode lookup
"""

import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inventory.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Starting barcode support migration...")

    try:
        # Add barcode column to ingredients table
        print("1. Adding barcode column to ingredients table...")
        cursor.execute("""
            ALTER TABLE ingredients ADD COLUMN barcode TEXT
        """)

        # Create index on ingredients barcode
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ingredients_barcode
            ON ingredients(barcode)
        """)
        print("   ✓ Ingredients barcode column and index added")

        # Add barcode column to products table
        print("2. Adding barcode column to products table...")
        cursor.execute("""
            ALTER TABLE products ADD COLUMN barcode TEXT
        """)

        # Create index on products barcode
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_barcode
            ON products(barcode)
        """)
        print("   ✓ Products barcode column and index added")

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
