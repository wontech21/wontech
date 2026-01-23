#!/usr/bin/env python3
"""
Generate 90 days of historical sales, invoice, and inventory count data
- $600k in sales data focusing on top 15-20 products
- $200k in invoice data for key ingredients
- Bi-weekly inventory counts with realistic variances
"""

import sqlite3
import random
from datetime import datetime, timedelta
from collections import defaultdict

INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

# Constants for data generation
DAYS_TO_GENERATE = 90
TARGET_SALES_REVENUE = 600000  # $600k
TARGET_INVOICE_TOTAL = 200000  # $200k
COUNTS_PER_WEEK = 2  # Count everything twice per week

# Day of week sales patterns (Monday=0, Sunday=6)
DAY_SALES_MULTIPLIER = {
    0: 0.7,   # Monday - slower
    1: 0.8,   # Tuesday
    2: 0.9,   # Wednesday
    3: 1.0,   # Thursday
    4: 1.3,   # Friday - busier
    5: 1.5,   # Saturday - busiest
    6: 1.2,   # Sunday - busy
}

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_top_products_with_recipes():
    """Get top 15 products by sales (or all products with recipes if no sales data)"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Try to get top products by existing sales
    cursor.execute("""
        SELECT
            p.id,
            p.product_name,
            p.selling_price,
            COALESCE(SUM(sh.revenue), 0) as total_revenue
        FROM products p
        LEFT JOIN sales_history sh ON sh.product_id = p.id
        WHERE EXISTS (SELECT 1 FROM recipes r WHERE r.product_id = p.id)
        GROUP BY p.id
        ORDER BY total_revenue DESC, p.id
        LIMIT 15
    """)

    products = []
    for row in cursor.fetchall():
        product = dict(row)

        # Get recipe for this product
        cursor.execute("""
            SELECT
                r.ingredient_id,
                r.quantity_needed,
                r.unit_of_measure,
                r.source_type,
                i.ingredient_code,
                i.ingredient_name,
                i.brand,
                i.supplier_name,
                i.unit_cost
            FROM recipes r
            JOIN ingredients i ON r.ingredient_id = i.id
            WHERE r.product_id = ?
        """, (product['id'],))

        product['recipe'] = [dict(r) for r in cursor.fetchall()]
        products.append(product)

    conn.close()
    return products

def get_all_active_ingredients():
    """Get all active ingredients for inventory counts"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            ingredient_code,
            ingredient_name,
            brand,
            supplier_name,
            quantity_on_hand,
            unit_of_measure,
            unit_cost
        FROM ingredients
        WHERE active = 1
    """)

    ingredients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return ingredients

def generate_sales_data(products, start_date, end_date):
    """Generate sales data for 90 days backwards"""
    print(f"\n📊 Generating sales data from {start_date.date()} to {end_date.date()}...")

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Calculate daily target revenue
    daily_target = TARGET_SALES_REVENUE / DAYS_TO_GENERATE

    sales_records = []
    total_revenue = 0

    current_date = start_date
    while current_date <= end_date:
        # Adjust for day of week
        dow = current_date.weekday()
        daily_revenue_target = daily_target * DAY_SALES_MULTIPLIER[dow]

        # Distribute sales across top products for this day
        daily_revenue = 0
        day_sales = []

        # Random variation (±20%)
        daily_revenue_target *= random.uniform(0.8, 1.2)

        while daily_revenue < daily_revenue_target and len(day_sales) < 500:  # Max 500 sales per day
            # Pick a product (weighted towards top sellers)
            product = random.choices(
                products,
                weights=[1.0 / (i + 1) for i in range(len(products))],
                k=1
            )[0]

            # Random quantity (most sales are 1-3 items)
            quantity = random.choices([1, 2, 3, 4, 5], weights=[50, 30, 12, 5, 3])[0]

            # Calculate costs
            revenue = product['selling_price'] * quantity

            # Calculate COGS from recipe
            cogs_per_unit = sum(
                item['quantity_needed'] * item['unit_cost']
                for item in product['recipe']
                if item['unit_cost'] is not None
            )
            total_cogs = cogs_per_unit * quantity
            profit = revenue - total_cogs

            # Random time during business hours (11 AM - 10 PM)
            hour = random.randint(11, 21)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            sale_time = f"{hour:02d}:{minute:02d}:{second:02d}"

            # Random discount (10% chance of 5-15% discount)
            discount_percent = 0
            if random.random() < 0.1:
                discount_percent = random.randint(5, 15)

            original_price = product['selling_price']
            sale_price = original_price * (1 - discount_percent / 100)
            discount_amount = original_price - sale_price
            final_revenue = sale_price * quantity

            day_sales.append({
                'sale_date': current_date.strftime('%Y-%m-%d'),
                'sale_time': sale_time,
                'product_id': product['id'],
                'product_name': product['product_name'],
                'quantity_sold': quantity,
                'original_price': original_price,
                'sale_price': sale_price,
                'discount_amount': discount_amount,
                'discount_percent': discount_percent,
                'revenue': final_revenue,
                'cost_of_goods': total_cogs,
                'gross_profit': final_revenue - total_cogs,
                'processed_date': current_date.strftime('%Y-%m-%d %H:%M:%S')
            })

            daily_revenue += final_revenue

        sales_records.extend(day_sales)
        total_revenue += daily_revenue

        current_date += timedelta(days=1)

    # Insert sales records
    print(f"   Inserting {len(sales_records)} sales records...")
    cursor.executemany("""
        INSERT INTO sales_history (
            sale_date, sale_time, product_id, product_name, quantity_sold,
            original_price, sale_price, discount_amount, discount_percent,
            revenue, cost_of_goods, gross_profit, processed_date
        ) VALUES (
            :sale_date, :sale_time, :product_id, :product_name, :quantity_sold,
            :original_price, :sale_price, :discount_amount, :discount_percent,
            :revenue, :cost_of_goods, :gross_profit, :processed_date
        )
    """, sales_records)

    conn.commit()
    conn.close()

    print(f"   ✅ Generated {len(sales_records)} sales records")
    print(f"   💰 Total revenue: ${total_revenue:,.2f}")
    return sales_records

def get_key_ingredients_from_sales(products, sales_records):
    """Determine which ingredients need to be ordered based on sales"""
    ingredient_usage = defaultdict(float)
    ingredient_info = {}

    # Calculate total usage per ingredient based on sales
    for sale in sales_records:
        # Find the product
        product = next((p for p in products if p['id'] == sale['product_id']), None)
        if not product:
            continue

        # Add ingredient usage
        for item in product['recipe']:
            code = item['ingredient_code']
            usage = item['quantity_needed'] * sale['quantity_sold']
            ingredient_usage[code] += usage

            if code not in ingredient_info:
                ingredient_info[code] = item

    return ingredient_usage, ingredient_info

def generate_invoice_data(ingredient_usage, ingredient_info, start_date, end_date):
    """Generate invoice data for ingredients"""
    print(f"\n📄 Generating invoice data...")

    conn_inv = get_db_connection(INVENTORY_DB)
    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    # Get suppliers
    cursor_inv = conn_inv.cursor()
    cursor_inv.execute("SELECT DISTINCT supplier_name FROM ingredients WHERE supplier_name IS NOT NULL")
    suppliers = [row['supplier_name'] for row in cursor_inv.fetchall()]

    invoices = []
    line_items = []
    total_invoice_amount = 0
    invoice_counter = 1000  # Start invoice numbers at 1000

    # Generate invoices throughout the period
    # Assume ordering happens 2-3 times per week
    current_date = start_date

    # Group ingredients by supplier
    supplier_ingredients = defaultdict(list)
    for code, info in ingredient_info.items():
        if info['supplier_name']:
            supplier_ingredients[info['supplier_name']].append((code, info))

    while current_date <= end_date and total_invoice_amount < TARGET_INVOICE_TOTAL:
        # 2-3 deliveries per week (roughly every 2-3 days)
        days_until_next = random.randint(2, 4)
        current_date += timedelta(days=days_until_next)

        if current_date > end_date:
            break

        # Pick 1-3 suppliers for this delivery day
        delivery_suppliers = random.sample(suppliers, min(random.randint(1, 3), len(suppliers)))

        for supplier in delivery_suppliers:
            supplier_items = supplier_ingredients.get(supplier, [])
            if not supplier_items:
                continue

            # Pick random ingredients from this supplier (30-70% of their catalog)
            num_items = max(1, int(len(supplier_items) * random.uniform(0.3, 0.7)))
            items_to_order = random.sample(supplier_items, num_items)

            invoice_num = f"INV-{invoice_counter:05d}"
            invoice_counter += 1

            invoice_total = 0
            invoice_lines = []

            for code, info in items_to_order:
                # Order quantity based on usage (with some randomness)
                usage = ingredient_usage.get(code, 0)
                # Order enough for ~7-14 days of usage (within our 90-day window)
                # Multiply by factor to reach target invoice amount
                order_qty = max(1, usage * random.uniform(0.5, 1.5))

                # Round to reasonable quantities
                if order_qty < 5:
                    order_qty = round(order_qty, 1)
                elif order_qty < 50:
                    order_qty = round(order_qty)
                else:
                    order_qty = round(order_qty / 5) * 5

                unit_price = info['unit_cost'] if info['unit_cost'] else random.uniform(1, 10)
                # Add price variation (±10%)
                unit_price *= random.uniform(0.9, 1.1)

                line_total = order_qty * unit_price
                invoice_total += line_total

                # Random lot number and expiration
                lot_number = f"LOT-{random.randint(10000, 99999)}"
                expiration_date = (current_date + timedelta(days=random.randint(30, 180))).strftime('%Y-%m-%d')

                invoice_lines.append({
                    'ingredient_code': code,
                    'ingredient_name': info['ingredient_name'],
                    'brand': info['brand'],
                    'quantity_ordered': order_qty,
                    'quantity_received': order_qty,  # Assume full delivery
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
                'payment_status': random.choice(['PAID', 'PAID', 'PAID', 'UNPAID']),  # 75% paid
                'payment_date': (current_date + timedelta(days=random.randint(7, 30))).strftime('%Y-%m-%d') if random.random() < 0.75 else None,
                'reconciled': 'YES',
                'reconciled_date': current_date.strftime('%Y-%m-%d %H:%M:%S'),
                'notes': None
            })

            # Store line items with invoice reference
            for line in invoice_lines:
                line['invoice_number'] = invoice_num
                line_items.append(line)

            total_invoice_amount += invoice_total

            if total_invoice_amount >= TARGET_INVOICE_TOTAL:
                break

    # Insert invoices
    print(f"   Inserting {len(invoices)} invoices...")
    cursor_invoices.executemany("""
        INSERT INTO invoices (
            invoice_number, supplier_name, invoice_date, received_date,
            total_amount, payment_status, payment_date, reconciled, reconciled_date, notes
        ) VALUES (
            :invoice_number, :supplier_name, :invoice_date, :received_date,
            :total_amount, :payment_status, :payment_date, :reconciled, :reconciled_date, :notes
        )
    """, invoices)

    # Get invoice IDs
    invoice_id_map = {}
    for invoice in invoices:
        cursor_invoices.execute("SELECT id FROM invoices WHERE invoice_number = ?", (invoice['invoice_number'],))
        invoice_id_map[invoice['invoice_number']] = cursor_invoices.fetchone()['id']

    # Insert line items with proper invoice_id
    line_items_with_ids = []
    for line in line_items:
        line_copy = line.copy()
        line_copy['invoice_id'] = invoice_id_map[line['invoice_number']]
        del line_copy['invoice_number']
        line_items_with_ids.append(line_copy)

    print(f"   Inserting {len(line_items_with_ids)} invoice line items...")
    cursor_invoices.executemany("""
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
    conn_inv.close()

    print(f"   ✅ Generated {len(invoices)} invoices with {len(line_items)} line items")
    print(f"   💰 Total invoice amount: ${total_invoice_amount:,.2f}")

def generate_inventory_counts(ingredients, start_date, end_date):
    """Generate bi-weekly inventory counts with realistic variances"""
    print(f"\n📦 Generating inventory counts...")

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    counts = []
    count_lines = []
    count_number = 1000

    # Count twice per week (every 3-4 days)
    current_date = start_date

    while current_date <= end_date:
        # Move to next count date (3-4 days)
        days_until_next = random.choice([3, 4])
        current_date += timedelta(days=days_until_next)

        if current_date > end_date:
            break

        count_num = f"COUNT-{count_number:05d}"
        count_number += 1

        counts.append({
            'count_number': count_num,
            'count_date': current_date.strftime('%Y-%m-%d'),
            'counted_by': random.choice(['Manager', 'Supervisor', 'Lead', 'Assistant Manager']),
            'notes': None,
            'reconciled': 'YES',
            'created_at': current_date.strftime('%Y-%m-%d %H:%M:%S')
        })

        # Count all ingredients
        for ingredient in ingredients:
            expected_qty = ingredient['quantity_on_hand']

            # Realistic variance scenarios:
            # - 80% of counts: within ±2% (minor counting errors)
            # - 10% of counts: -3% to -8% (waste, theft, spillage)
            # - 5% of counts: -10% to -20% (significant waste/theft)
            # - 5% of counts: exactly as expected

            rand = random.random()
            if rand < 0.05:  # 5% exactly as expected
                variance_pct = 0
                note = None
            elif rand < 0.85:  # 80% minor variance
                variance_pct = random.uniform(-0.02, 0.02)
                note = None
            elif rand < 0.95:  # 10% moderate loss
                variance_pct = random.uniform(-0.08, -0.03)
                note = random.choice([
                    'Spillage noted',
                    'Expired items discarded',
                    'Some waste',
                    None
                ])
            else:  # 5% significant loss
                variance_pct = random.uniform(-0.20, -0.10)
                note = random.choice([
                    'Significant waste - investigate',
                    'Possible theft',
                    'Large batch expired',
                    'Damaged goods removed'
                ])

            variance = expected_qty * variance_pct
            counted_qty = max(0, expected_qty + variance)

            # Round to reasonable precision
            if counted_qty < 1:
                counted_qty = round(counted_qty, 2)
            elif counted_qty < 10:
                counted_qty = round(counted_qty, 1)
            else:
                counted_qty = round(counted_qty)

            count_lines.append({
                'count_number': count_num,
                'ingredient_code': ingredient['ingredient_code'],
                'ingredient_name': ingredient['ingredient_name'],
                'quantity_counted': counted_qty,
                'quantity_expected': expected_qty,
                'variance': round(counted_qty - expected_qty, 2),
                'unit_of_measure': ingredient['unit_of_measure'],
                'notes': note
            })

    # Insert counts
    print(f"   Inserting {len(counts)} count records...")
    cursor.executemany("""
        INSERT INTO inventory_counts (
            count_number, count_date, counted_by, notes, reconciled, created_at
        ) VALUES (
            :count_number, :count_date, :counted_by, :notes, :reconciled, :created_at
        )
    """, counts)

    # Get count IDs
    count_id_map = {}
    for count in counts:
        cursor.execute("SELECT id FROM inventory_counts WHERE count_number = ?", (count['count_number'],))
        count_id_map[count['count_number']] = cursor.fetchone()['id']

    # Insert count line items
    count_lines_with_ids = []
    for line in count_lines:
        line_copy = line.copy()
        line_copy['count_id'] = count_id_map[line['count_number']]
        del line_copy['count_number']
        count_lines_with_ids.append(line_copy)

    print(f"   Inserting {len(count_lines_with_ids)} count line items...")
    cursor.executemany("""
        INSERT INTO count_line_items (
            count_id, ingredient_code, ingredient_name,
            quantity_counted, quantity_expected, variance,
            unit_of_measure, notes
        ) VALUES (
            :count_id, :ingredient_code, :ingredient_name,
            :quantity_counted, :quantity_expected, :variance,
            :unit_of_measure, :notes
        )
    """, count_lines_with_ids)

    conn.commit()
    conn.close()

    print(f"   ✅ Generated {len(counts)} counts with {len(count_lines)} line items")
    print(f"   📊 Average {len(ingredients)} items counted per session")

def main():
    print("=" * 70)
    print("🚀 HISTORICAL DATA GENERATION")
    print("=" * 70)

    # Calculate date range (90 days back from today)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS_TO_GENERATE)

    print(f"\n📅 Date Range: {start_date.date()} to {end_date.date()}")
    print(f"💰 Target Sales: ${TARGET_SALES_REVENUE:,}")
    print(f"📄 Target Invoices: ${TARGET_INVOICE_TOTAL:,}")
    print(f"📦 Counts per week: {COUNTS_PER_WEEK}")

    # Step 1: Get top products and recipes
    print("\n🔍 Step 1: Analyzing top products and recipes...")
    products = get_top_products_with_recipes()
    print(f"   Found {len(products)} top products")

    # Step 2: Generate sales data
    print("\n💵 Step 2: Generating sales data...")
    sales_records = generate_sales_data(products, start_date, end_date)

    # Step 3: Calculate ingredient usage from sales
    print("\n🔢 Step 3: Calculating ingredient usage...")
    ingredient_usage, ingredient_info = get_key_ingredients_from_sales(products, sales_records)
    print(f"   Tracking {len(ingredient_usage)} unique ingredients")

    # Step 4: Generate invoice data
    print("\n📦 Step 4: Generating invoice data...")
    generate_invoice_data(ingredient_usage, ingredient_info, start_date, end_date)

    # Step 5: Generate inventory counts
    print("\n📊 Step 5: Generating inventory counts...")
    all_ingredients = get_all_active_ingredients()
    print(f"   Found {len(all_ingredients)} active ingredients")
    generate_inventory_counts(all_ingredients, start_date, end_date)

    print("\n" + "=" * 70)
    print("✅ DATA GENERATION COMPLETE!")
    print("=" * 70)

if __name__ == '__main__':
    main()
