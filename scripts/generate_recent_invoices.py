#!/usr/bin/env python3
"""
Generate invoice data for the last 30 days to fill the gap
"""

import sqlite3
import random
from datetime import datetime, timedelta
from collections import defaultdict

INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_recent_sales_usage():
    """Get ingredient usage from recent sales (last 30 days)"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get date 30 days ago
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    # Get sales from last 30 days
    cursor.execute("""
        SELECT product_id, product_name, SUM(quantity_sold) as total_qty
        FROM sales_history
        WHERE sale_date >= ?
        GROUP BY product_id
    """, (thirty_days_ago,))

    sales = [dict(row) for row in cursor.fetchall()]

    # Get recipes for these products
    ingredient_usage = defaultdict(float)
    ingredient_info = {}

    for sale in sales:
        cursor.execute("""
            SELECT
                r.ingredient_id,
                r.quantity_needed,
                i.ingredient_code,
                i.ingredient_name,
                i.brand,
                i.supplier_name,
                i.unit_of_measure,
                i.unit_cost
            FROM recipes r
            JOIN ingredients i ON r.ingredient_id = i.id
            WHERE r.product_id = ?
        """, (sale['product_id'],))

        for item in cursor.fetchall():
            item_dict = dict(item)
            code = item_dict['ingredient_code']
            usage = item_dict['quantity_needed'] * sale['total_qty']
            ingredient_usage[code] += usage

            if code not in ingredient_info:
                ingredient_info[code] = item_dict

    conn.close()
    return ingredient_usage, ingredient_info

def generate_invoices_for_last_30_days(ingredient_usage, ingredient_info):
    """Generate invoices for the last 30 days"""
    print("\n📄 Generating invoices for last 30 days...")

    conn_invoices = get_db_connection(INVOICES_DB)
    cursor = conn_invoices.cursor()

    # Get existing invoice numbers to avoid conflicts
    cursor.execute("SELECT MAX(CAST(SUBSTR(invoice_number, 5) AS INTEGER)) FROM invoices WHERE invoice_number LIKE 'INV-%'")
    max_num = cursor.fetchone()[0]
    invoice_counter = (max_num or 1000) + 1

    # Get suppliers
    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()
    cursor_inv.execute("SELECT DISTINCT supplier_name FROM ingredients WHERE supplier_name IS NOT NULL")
    suppliers = [row['supplier_name'] for row in cursor_inv.fetchall()]
    conn_inv.close()

    # Group ingredients by supplier
    supplier_ingredients = defaultdict(list)
    for code, info in ingredient_info.items():
        if info['supplier_name']:
            supplier_ingredients[info['supplier_name']].append((code, info))

    # Generate invoices for last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    invoices = []
    line_items = []
    total_amount = 0

    # Generate 2-3 deliveries per week = ~12 deliveries in 30 days
    current_date = start_date

    while current_date <= end_date:
        # Every 2-3 days
        days_until_next = random.randint(2, 3)
        current_date += timedelta(days=days_until_next)

        if current_date > end_date:
            break

        # Pick 1-2 suppliers per delivery
        delivery_suppliers = random.sample(suppliers, min(random.randint(1, 2), len(suppliers)))

        for supplier in delivery_suppliers:
            supplier_items = supplier_ingredients.get(supplier, [])
            if not supplier_items:
                continue

            # Pick 30-60% of their items
            num_items = max(1, int(len(supplier_items) * random.uniform(0.3, 0.6)))
            items_to_order = random.sample(supplier_items, num_items)

            invoice_num = f"INV-{invoice_counter:05d}"
            invoice_counter += 1

            invoice_total = 0
            invoice_lines = []

            for code, info in items_to_order:
                # Order based on usage
                usage = ingredient_usage.get(code, 0)
                # Order enough for ~7-14 days (more realistic for restaurant)
                order_qty = max(1, usage * random.uniform(0.8, 1.5))

                # Round quantities
                if order_qty < 5:
                    order_qty = round(order_qty, 1)
                elif order_qty < 50:
                    order_qty = round(order_qty)
                else:
                    order_qty = round(order_qty / 5) * 5

                unit_price = info['unit_cost'] if info['unit_cost'] else random.uniform(1, 10)
                unit_price *= random.uniform(0.9, 1.1)  # ±10% variation

                line_total = order_qty * unit_price
                invoice_total += line_total

                lot_number = f"LOT-{random.randint(10000, 99999)}"
                expiration_date = (current_date + timedelta(days=random.randint(30, 180))).strftime('%Y-%m-%d')

                invoice_lines.append({
                    'ingredient_code': code,
                    'ingredient_name': info['ingredient_name'],
                    'brand': info['brand'],
                    'quantity_ordered': order_qty,
                    'quantity_received': order_qty,
                    'unit_of_measure': info['unit_of_measure'],
                    'unit_price': round(unit_price, 2),
                    'total_price': round(line_total, 2),
                    'lot_number': lot_number,
                    'expiration_date': expiration_date
                })

            invoices.append({
                'invoice_number': invoice_num,
                'supplier_name': supplier,
                'invoice_date': current_date.strftime('%Y-%m-%d'),
                'received_date': current_date.strftime('%Y-%m-%d %H:%M:%S'),
                'total_amount': round(invoice_total, 2),
                'payment_status': random.choice(['PAID', 'PAID', 'PAID', 'UNPAID']),
                'payment_date': (current_date + timedelta(days=random.randint(7, 30))).strftime('%Y-%m-%d') if random.random() < 0.75 else None,
                'reconciled': 'YES',
                'reconciled_date': current_date.strftime('%Y-%m-%d %H:%M:%S'),
                'notes': None
            })

            for line in invoice_lines:
                line['invoice_number'] = invoice_num
                line_items.append(line)

            total_amount += invoice_total

    # Insert invoices
    print(f"   Inserting {len(invoices)} invoices...")
    cursor.executemany("""
        INSERT INTO invoices (
            invoice_number, supplier_name, invoice_date, received_date,
            total_amount, payment_status, payment_date, reconciled, reconciled_date, notes
        ) VALUES (
            :invoice_number, :supplier_name, :invoice_date, :received_date,
            :total_amount, :payment_status, :payment_date, :reconciled, :reconciled_date, :notes
        )
    """, invoices)

    # Get invoice IDs and insert line items
    invoice_id_map = {}
    for invoice in invoices:
        cursor.execute("SELECT id FROM invoices WHERE invoice_number = ?", (invoice['invoice_number'],))
        invoice_id_map[invoice['invoice_number']] = cursor.fetchone()['id']

    line_items_with_ids = []
    for line in line_items:
        line_copy = line.copy()
        line_copy['invoice_id'] = invoice_id_map[line['invoice_number']]
        del line_copy['invoice_number']
        line_items_with_ids.append(line_copy)

    print(f"   Inserting {len(line_items_with_ids)} invoice line items...")
    cursor.executemany("""
        INSERT INTO invoice_line_items (
            invoice_id, ingredient_code, ingredient_name, brand,
            quantity_ordered, quantity_received, unit_of_measure,
            unit_price, total_price, lot_number, expiration_date, reconciled_to_inventory
        ) VALUES (
            :invoice_id, :ingredient_code, :ingredient_name, :brand,
            :quantity_ordered, :quantity_received, :unit_of_measure,
            :unit_price, :total_price, :lot_number, :expiration_date, 'YES'
        )
    """, line_items_with_ids)

    conn_invoices.commit()
    conn_invoices.close()

    print(f"   ✅ Generated {len(invoices)} invoices with {len(line_items)} line items")
    print(f"   💰 Total invoice amount: ${total_amount:,.2f}")

    return len(invoices), total_amount

def main():
    print("=" * 70)
    print("🚀 GENERATING INVOICES FOR LAST 30 DAYS")
    print("=" * 70)

    # Get ingredient usage from recent sales
    print("\n🔍 Analyzing recent sales (last 30 days)...")
    ingredient_usage, ingredient_info = get_recent_sales_usage()
    print(f"   Found {len(ingredient_usage)} ingredients used in recent sales")

    # Generate invoices
    count, total = generate_invoices_for_last_30_days(ingredient_usage, ingredient_info)

    print("\n" + "=" * 70)
    print(f"✅ COMPLETE! Generated {count} invoices totaling ${total:,.2f}")
    print("=" * 70)

if __name__ == '__main__':
    main()
