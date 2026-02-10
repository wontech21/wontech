#!/usr/bin/env python3
"""
Migration: Add sale pricing columns to sales_history table
- original_price: The product's regular selling price
- sale_price: The actual price charged (may be discounted)
- discount_amount: Dollar amount of discount (original_price - sale_price)
- discount_percent: Percentage discount
"""
import sqlite3

INVENTORY_DB = 'inventory.db'

def add_sale_pricing_columns():
    """Add pricing and discount columns to sales_history table"""
    conn = sqlite3.connect(INVENTORY_DB)
    cursor = conn.cursor()

    print("Adding pricing columns to sales_history table...")

    columns_to_add = [
        ('original_price', 'REAL'),
        ('sale_price', 'REAL'),
        ('discount_amount', 'REAL'),
        ('discount_percent', 'REAL')
    ]

    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(f"""
                ALTER TABLE sales_history
                ADD COLUMN {column_name} {column_type}
            """)
            print(f"✓ Added column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"✓ Column {column_name} already exists")
            else:
                raise

    conn.commit()
    print("\n✓ Successfully added all pricing columns")
    conn.close()

if __name__ == '__main__':
    add_sale_pricing_columns()
