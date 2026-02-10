#!/usr/bin/env python3
"""
Remove UNIQUE constraint from ingredient_code to allow multiple lots/dates
"""
import sqlite3

def fix_unique_constraint():
    print("\n" + "="*70)
    print("🔧 REMOVING UNIQUE CONSTRAINT FROM ingredient_code")
    print("="*70 + "\n")

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    try:
        # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
        print("1. Creating backup of ingredients table...")
        cursor.execute("CREATE TABLE ingredients_backup AS SELECT * FROM ingredients")
        
        print("2. Dropping old ingredients table...")
        cursor.execute("DROP TABLE ingredients")
        
        print("3. Creating new ingredients table without UNIQUE constraint on ingredient_code...")
        cursor.execute("""
            CREATE TABLE ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_code TEXT NOT NULL,
                ingredient_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_of_measure TEXT NOT NULL,
                quantity_on_hand REAL NOT NULL DEFAULT 0,
                unit_cost REAL NOT NULL,
                supplier_name TEXT,
                supplier_contact TEXT,
                reorder_level REAL DEFAULT 0,
                reorder_quantity REAL,
                storage_location TEXT,
                expiration_date TEXT,
                lot_number TEXT,
                date_received TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                brand TEXT,
                last_unit_price REAL,
                average_unit_price REAL,
                units_per_case REAL DEFAULT 1
            )
        """)
        
        print("4. Copying data back...")
        cursor.execute("""
            INSERT INTO ingredients 
            SELECT * FROM ingredients_backup
        """)
        
        print("5. Recreating indexes...")
        cursor.execute("CREATE INDEX idx_ingredient_code ON ingredients(ingredient_code)")
        cursor.execute("CREATE INDEX idx_ingredient_category ON ingredients(category)")
        
        print("6. Dropping backup table...")
        cursor.execute("DROP TABLE ingredients_backup")
        
        conn.commit()
        print("\n✓ UNIQUE constraint removed successfully!")
        print("✓ Ingredients table now allows multiple entries per ingredient_code")
        print("  (different lots and dates can now be tracked separately)\n")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}\n")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    fix_unique_constraint()
