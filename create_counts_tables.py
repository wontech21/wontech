#!/usr/bin/env python3
"""
Create inventory counts tables in the inventory database
"""
import sqlite3

def create_counts_tables():
    print("\n" + "="*70)
    print("📊 CREATING INVENTORY COUNTS TABLES")
    print("="*70 + "\n")

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    try:
        # Create inventory_counts table
        print("1. Creating inventory_counts table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                count_number TEXT UNIQUE NOT NULL,
                count_date TEXT NOT NULL,
                counted_by TEXT,
                notes TEXT,
                reconciled TEXT DEFAULT 'NO',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create count_line_items table
        print("2. Creating count_line_items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS count_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                count_id INTEGER NOT NULL,
                ingredient_code TEXT NOT NULL,
                ingredient_name TEXT NOT NULL,
                quantity_counted REAL NOT NULL,
                quantity_expected REAL,
                variance REAL,
                unit_of_measure TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (count_id) REFERENCES inventory_counts(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        print("3. Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_count_line_items_count_id
            ON count_line_items(count_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_count_line_items_ingredient_code
            ON count_line_items(ingredient_code)
        """)

        conn.commit()

        print("\n✓ Inventory counts tables created successfully!")
        print("  - inventory_counts: Stores count header information")
        print("  - count_line_items: Stores individual item counts")
        print("  - Indexes created for performance\n")

    except Exception as e:
        print(f"\n✗ Error: {str(e)}\n")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    create_counts_tables()
