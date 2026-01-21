#!/usr/bin/env python3
"""
Migration: Add sale_time column to sales_history table
"""
import sqlite3

INVENTORY_DB = 'inventory.db'

def add_sale_time_column():
    """Add sale_time column for tracking time of sales"""
    conn = sqlite3.connect(INVENTORY_DB)
    cursor = conn.cursor()

    print("Adding sale_time column to sales_history table...")

    try:
        # Add the sale_time column
        cursor.execute("""
            ALTER TABLE sales_history
            ADD COLUMN sale_time TEXT
        """)

        conn.commit()
        print("✓ Successfully added sale_time column")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("✓ Column sale_time already exists")
        else:
            raise

    conn.close()

if __name__ == '__main__':
    add_sale_time_column()
