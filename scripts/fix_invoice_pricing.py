#!/usr/bin/env python3
"""
Fix unrealistic pricing in test invoices
Apply market-realistic prices based on ingredient categories
"""

import sqlite3
import random

# Database paths
INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

# Realistic price ranges per lb/unit (in dollars)
PRICE_RANGES = {
    # Proteins
    'Ground Beef': (4.50, 6.50),
    'Beef Brisket': (8.00, 12.00),
    'Ribeye Steak': (15.00, 22.00),
    'Pork Chops': (3.50, 5.50),
    'Bacon': (5.00, 7.50),
    'Sausage Links': (3.00, 5.00),
    'Italian Sausage': (3.50, 5.50),
    'Chicken Breast': (2.50, 4.00),
    'Chicken Thighs': (1.75, 3.00),
    'Chicken Wings': (2.00, 3.50),
    'Turkey Breast': (3.00, 5.00),
    'Ground Turkey': (3.00, 5.00),
    'Salmon Fillets': (12.00, 18.00),
    'Shrimp 16/20': (8.00, 14.00),
    'Cod Fillets': (6.00, 10.00),
    'Tuna Steaks': (10.00, 16.00),
    'Tilapia': (4.00, 7.00),
    'Eggs': (3.00, 5.00),
    'Flour All Purpose': (0.35, 0.65),
    'Sugar Granulated': (0.50, 0.90),
    'Salt': (0.25, 0.50),
    'Black Pepper': (8.00, 15.00),
}

def get_realistic_price(ingredient_name):
    """Get realistic price for an ingredient"""
    # Try exact match first
    if ingredient_name in PRICE_RANGES:
        price_range = PRICE_RANGES[ingredient_name]
        return round(random.uniform(price_range[0], price_range[1]), 2)

    # Default fallback prices by category keywords
    name_lower = ingredient_name.lower()

    if any(word in name_lower for word in ['beef', 'steak', 'brisket']):
        return round(random.uniform(5.00, 12.00), 2)
    elif any(word in name_lower for word in ['chicken', 'turkey', 'poultry']):
        return round(random.uniform(2.00, 4.50), 2)
    elif any(word in name_lower for word in ['pork', 'bacon', 'sausage']):
        return round(random.uniform(3.00, 6.00), 2)
    elif any(word in name_lower for word in ['fish', 'salmon', 'shrimp', 'seafood', 'cod', 'tuna', 'tilapia']):
        return round(random.uniform(6.00, 14.00), 2)
    elif any(word in name_lower for word in ['cheese', 'milk', 'cream', 'butter', 'dairy']):
        return round(random.uniform(3.00, 6.00), 2)
    elif any(word in name_lower for word in ['lettuce', 'tomato', 'onion', 'pepper', 'vegetable', 'produce', 'carrot', 'celery', 'mushroom', 'potato', 'garlic', 'avocado', 'lemon', 'lime']):
        return round(random.uniform(0.75, 3.00), 2)
    elif any(word in name_lower for word in ['pasta', 'rice', 'flour', 'grain', 'bread', 'bun', 'tortilla']):
        return round(random.uniform(0.50, 2.50), 2)
    elif any(word in name_lower for word in ['oil', 'vinegar']):
        return round(random.uniform(4.00, 12.00), 2)
    elif any(word in name_lower for word in ['spice', 'seasoning', 'powder', 'basil', 'oregano', 'thyme', 'paprika', 'cumin']):
        return round(random.uniform(7.00, 15.00), 2)
    elif any(word in name_lower for word in ['sauce', 'ketchup', 'mustard', 'dressing', 'condiment', 'mayonnaise', 'pickle']):
        return round(random.uniform(2.50, 5.50), 2)
    elif any(word in name_lower for word in ['can', 'beans', 'broth', 'corn', 'peas']):
        return round(random.uniform(1.00, 3.00), 2)
    elif any(word in name_lower for word in ['frozen', 'fries', 'ring']):
        return round(random.uniform(1.50, 3.50), 2)
    elif any(word in name_lower for word in ['beverage', 'cola', 'pepsi', 'sprite', 'juice', 'coffee', 'tea']):
        return round(random.uniform(0.75, 6.00), 2)
    else:
        # Generic fallback
        return round(random.uniform(2.00, 8.00), 2)

def fix_invoice_pricing():
    """Fix all invoice pricing to be realistic"""
    inv_db_conn = sqlite3.connect(INVOICES_DB)
    inv_db_conn.row_factory = sqlite3.Row
    inv_conn = sqlite3.connect(INVENTORY_DB)
    inv_conn.row_factory = sqlite3.Row

    inv_db_cursor = inv_db_conn.cursor()

    # Get all invoices created by test generator
    inv_db_cursor.execute("""
        SELECT id, invoice_number, total_amount
        FROM invoices
        WHERE invoice_number LIKE 'INV-202601%'
        ORDER BY invoice_date
    """)

    invoices = inv_db_cursor.fetchall()

    print("=" * 70)
    print("🔧 FIXING INVOICE PRICING")
    print("=" * 70)
    print()

    total_fixed = 0

    for invoice in invoices:
        invoice_id = invoice['id']
        invoice_number = invoice['invoice_number']
        old_total = invoice['total_amount']

        # Get line items
        inv_db_cursor.execute("""
            SELECT id, ingredient_name, quantity_received, unit_price, total_price
            FROM invoice_line_items
            WHERE invoice_id = ?
        """, (invoice_id,))

        line_items = inv_db_cursor.fetchall()
        new_invoice_total = 0

        for item in line_items:
            item_id = item['id']
            ingredient_name = item['ingredient_name']
            quantity = item['quantity_received']
            old_unit_price = item['unit_price']
            old_total_price = item['total_price']

            # Get realistic price
            new_unit_price = get_realistic_price(ingredient_name)
            new_total_price = round(quantity * new_unit_price, 2)
            new_invoice_total += new_total_price

            # Update line item
            inv_db_cursor.execute("""
                UPDATE invoice_line_items
                SET unit_price = ?, total_price = ?
                WHERE id = ?
            """, (new_unit_price, new_total_price, item_id))

        # Update invoice total
        inv_db_cursor.execute("""
            UPDATE invoices
            SET total_amount = ?
            WHERE id = ?
        """, (new_invoice_total, invoice_id))

        inv_db_conn.commit()

        total_fixed += 1
        if total_fixed % 10 == 0:
            print(f"✅ Fixed {total_fixed}/{len(invoices)} invoices...")

    print(f"✅ Fixed all {total_fixed} invoices")
    print()

    # Now recalculate inventory costs
    print("=" * 70)
    print("🔧 RECALCULATING INVENTORY COSTS")
    print("=" * 70)
    print()

    inv_cursor = inv_conn.cursor()

    # Get all ingredients
    inv_cursor.execute("""
        SELECT id, ingredient_code, ingredient_name, quantity_on_hand
        FROM ingredients
        WHERE active = 1 AND quantity_on_hand > 0
    """)

    ingredients = inv_cursor.fetchall()

    fixed_count = 0

    for ingredient in ingredients:
        ingredient_id = ingredient['id']
        ingredient_code = ingredient['ingredient_code']
        current_qty = ingredient['quantity_on_hand']

        # Get all line items for this ingredient ordered by date
        inv_db_cursor.execute("""
            SELECT ili.unit_price, ili.quantity_received, i.invoice_date
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_code = ?
            ORDER BY i.invoice_date
        """, (ingredient_code,))

        purchases = inv_db_cursor.fetchall()

        if not purchases:
            continue

        # Calculate weighted average
        total_cost = 0
        total_qty = 0
        last_price = 0

        for purchase in purchases:
            unit_price = purchase['unit_price']
            qty = purchase['quantity_received']
            total_cost += unit_price * qty
            total_qty += qty
            last_price = unit_price

        if total_qty > 0:
            avg_price = total_cost / total_qty
        else:
            avg_price = 0

        # Update ingredient
        inv_cursor.execute("""
            UPDATE ingredients
            SET unit_cost = ?,
                average_unit_price = ?,
                last_unit_price = ?
            WHERE id = ?
        """, (avg_price, avg_price, last_price, ingredient_id))

        fixed_count += 1

    inv_conn.commit()

    print(f"✅ Recalculated costs for {fixed_count} ingredients")
    print()

    # Show summary
    print("=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)

    inv_db_cursor.execute("SELECT SUM(total_amount) FROM invoices")
    new_total_value = inv_db_cursor.fetchone()[0]

    inv_db_cursor.execute("""
        SELECT MIN(unit_price), MAX(unit_price), AVG(unit_price)
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        WHERE i.invoice_number LIKE 'INV-202601%'
    """)
    price_stats = inv_db_cursor.fetchone()

    print(f"📄 Total Invoices Fixed: {total_fixed}")
    print(f"💰 New Total Invoice Value: ${new_total_value:,.2f}")
    print(f"📊 Unit Price Range: ${price_stats[0]:.2f} - ${price_stats[1]:.2f}")
    print(f"📊 Average Unit Price: ${price_stats[2]:.2f}")
    print()

    # Show sample corrected items
    print("📦 Sample of Corrected Items:")
    inv_db_cursor.execute("""
        SELECT ili.ingredient_name, ili.quantity_received, ili.unit_of_measure,
               printf('$%.2f', ili.unit_price) as unit_price,
               printf('$%.2f', ili.total_price) as total_price
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        WHERE i.invoice_number LIKE 'INV-202601%'
        ORDER BY RANDOM()
        LIMIT 15
    """)

    samples = inv_db_cursor.fetchall()
    for sample in samples:
        print(f"  • {sample['ingredient_name']}: {sample['quantity_received']} {sample['unit_of_measure']} @ {sample['unit_price']} = {sample['total_price']}")

    print()
    print("=" * 70)
    print("✅ PRICING CORRECTION COMPLETE!")
    print("=" * 70)

    inv_db_conn.close()
    inv_conn.close()

if __name__ == '__main__':
    fix_invoice_pricing()
