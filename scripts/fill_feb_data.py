#!/usr/bin/env python3
"""
Fill the gap in sales and invoice data to align with attendance records.

Current state:
  - attendance:  2025-01-01 → 2026-03-31 (fully covered)
  - sales:       2025-01-01 → 2026-02-09 (missing Feb 10 → today)
  - invoices:    2025-01-02 → 2026-01-21 (missing Jan 22 → today)

This script fills:
  - sales_history:  2026-02-10 → 2026-02-11
  - invoices:       2026-01-22 → 2026-02-11
"""

import sqlite3
import random
from datetime import datetime, timedelta, date

DB_PATH = '/Users/dell/WONTECH/databases/org_1.db'
ORG_ID = 1
random.seed(2026)

# ─── Product catalog (same as simulate_historical_data.py) ───
PRODUCTS = [
    (1,  'Beef Tacos (3-pack)',            'Entrees',        12.99, 0.30),
    (2,  'Chicken Burrito',                'Entrees',        10.99, 0.28),
    (4,  'Spanish Rice (side)',            'Sides',           3.99, 0.10),
    (5,  'Black Beans (side)',             'Sides',           3.99, 0.08),
    (6,  'Pico de Gallo',                 'Sauces',          5.99, 0.06),
    (7,  'Classic Burger',                 'Prepared Foods', 12.99, 0.05),
    (8,  'Chicken Pasta Alfredo',          'Prepared Foods', 16.99, 0.04),
    (9,  'Fish and Chips',                 'Prepared Foods', 14.99, 0.04),
    (10, 'Cheese Pizza - Small (10")',     'Pizza',           9.99, 0.03),
    (11, 'Cheese Pizza - Medium (14")',    'Pizza',          13.99, 0.03),
    (12, 'Cheese Pizza - Large (16")',     'Pizza',          16.99, 0.03),
    (13, 'Pepperoni Pizza - Medium (14")', 'Pizza',          15.99, 0.03),
    (14, 'Supreme Pizza - Large (16")',    'Pizza',          20.99, 0.02),
    (18, 'Medium Bacon Pizza',             'Pizza',          16.99, 0.02),
]
_total_w = sum(p[4] for p in PRODUCTS)
for i in range(len(PRODUCTS)):
    PRODUCTS[i] = (*PRODUCTS[i][:4], PRODUCTS[i][4] / _total_w)

# ─── Suppliers ───
SUPPLIERS = [
    ("Eddy's",                 'weekly',   (800, 3500)),
    ("Cheney Brothers",        'biweekly', (100, 600)),
    ("Shamrock Foods",         'monthly',  (2000, 8000)),
    ("Chefs Warehouse",        'biweekly', (500, 4000)),
    ("US Foods",               'weekly',   (800, 3000)),
    ("Gordon Food Service",    'biweekly', (400, 1500)),
    ("LA Specialty Produce",   'weekly',   (300, 1200)),
    ("Baldor Specialty Foods", 'biweekly', (600, 3500)),
    ("Sysco Foods",            'biweekly', (1000, 4000)),
    ("Kings Produce",          'weekly',   (500, 2000)),
    ("Reinhart Foodservice",   'monthly',  (800, 3000)),
    ("Ben E. Keith",           'monthly',  (600, 2500)),
    ("Vistar",                 'weekly',   (1500, 9000)),
    ("Fresh Express",          'biweekly', (200, 800)),
    ("Performance Foodservice",'monthly',  (500, 2000)),
    ("Restaurant Depot",       'biweekly', (800, 3000)),
]

INGREDIENT_SAMPLES = [
    (94,  '10" Roll',           'ea',   3.01),
    (95,  '8" Roll',            'ea',   2.77),
    (96,  'Yeast',              'lbs',  2.58),
    (97,  'Onion Roll',         'ea',   3.32),
    (99,  'White Bread',        'ea',   2.88),
    (109, 'Panko Breadcrumbs',  'case', 1.29),
    (110, 'Basil',              'case', 9.00),
    (111, 'Whole Milk',         'case', 4.49),
    (112, 'Olive Oil',          'each', 5.73),
    (113, 'Peas',               'oz',   1.97),
    (114, 'Salt',               'lb',   0.38),
    (115, 'Ground Beef',        'each', 5.77),
    (116, 'Ranch Dressing',     'lb',   3.56),
    (117, 'Chicken Thighs',     'lb',   1.93),
    (119, 'Cumin',              'lb',  10.17),
    (120, 'French Bread',       'lb',   1.85),
    (121, 'Pepsi',              'each', 2.63),
    (122, 'Italian Sausage',    'gal',  3.88),
    (123, 'Diced Tomatoes',     'gal',  1.51),
    (125, 'Ground Beef',        'case', 4.50),
    (126, 'Balsamic Vinegar',   'oz',   7.64),
    (1043,'16" Pizza Box',      'each', 0.57),
    (1044,'Pizza Dough Ball',   'each', 1.19),
]

MONTHLY_SEASON = {
    1: 0.80, 2: 0.78, 3: 0.88, 4: 0.95, 5: 1.02,  6: 1.10,
    7: 1.12, 8: 1.08, 9: 0.98, 10: 0.95, 11: 0.92, 12: 1.00,
}

DOW_MULT = {
    0: 1.12,  # Sun
    1: 0.65,  # Mon
    2: 0.80,  # Tue
    3: 0.88,  # Wed
    4: 0.95,  # Thu
    5: 1.27,  # Fri
    6: 1.48,  # Sat
}

HOURLY_WEIGHTS = {
    10: 0.30, 11: 0.85, 12: 1.40, 13: 1.20, 14: 0.55,
    15: 0.40, 16: 0.60, 17: 1.10, 18: 1.50, 19: 1.45,
    20: 1.10, 21: 0.70, 22: 0.35,
}
_HOURS = list(HOURLY_WEIGHTS.keys())
_HOUR_W = list(HOURLY_WEIGHTS.values())


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def pick_product():
    r = random.random()
    cumulative = 0
    for pid, name, cat, price, weight in PRODUCTS:
        cumulative += weight
        if r <= cumulative:
            return pid, name, cat, price
    return PRODUCTS[-1][:4]


def generate_sales(conn, start, end):
    """Generate sales data for the given date range."""
    print(f"Generating sales data {start} → {end}...")
    cursor = conn.cursor()

    # Continuation of growth: ~13 months elapsed since Jan 2025
    base_items_per_day = 280
    growth_per_month = 1.03

    rows = []
    for d in daterange(start, end):
        months_elapsed = (d.year - 2025) * 12 + d.month - 1
        growth = growth_per_month ** months_elapsed
        dow_idx = (d.weekday() + 1) % 7
        dow = DOW_MULT[dow_idx]
        season = MONTHLY_SEASON[d.month]

        daily_items = int(base_items_per_day * growth * season * dow * random.uniform(0.85, 1.15))
        daily_items = max(50, daily_items)

        sale_times = sorted([
            f"{random.choices(_HOURS, weights=_HOUR_W, k=1)[0]:02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
            for _ in range(min(daily_items, 600))
        ])

        for idx in range(daily_items):
            pid, pname, cat, base_price = pick_product()
            qty = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]

            discount_pct = 0
            if random.random() < 0.05:
                discount_pct = random.choice([5, 10, 15])

            sale_price = round(base_price * (1 - discount_pct / 100), 2)
            revenue = round(sale_price * qty, 2)
            cogs = round(revenue * random.uniform(0.28, 0.38), 2)
            profit = round(revenue - cogs, 2)
            discount_amt = round(base_price * qty - revenue, 2) if discount_pct else 0

            sale_time = sale_times[idx % len(sale_times)] if sale_times else '12:00:00'

            order_types = ['dine_in', 'pickup', 'delivery', 'online']
            order_weights = [0.30, 0.30, 0.22, 0.18]
            order_type = random.choices(order_types, weights=order_weights, k=1)[0]

            rows.append((
                d.isoformat(), pid, pname, float(qty), revenue, cogs, profit,
                d.isoformat(), None, sale_time,
                base_price if discount_pct else None,
                sale_price if discount_pct else None,
                discount_amt if discount_pct else None,
                float(discount_pct) if discount_pct else None,
                order_type,
            ))

    cursor.executemany("""
        INSERT INTO sales_history
        (sale_date, product_id, product_name, quantity_sold, revenue, cost_of_goods,
         gross_profit, processed_date, notes, sale_time, original_price, sale_price,
         discount_amount, discount_percent, order_type)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)

    conn.commit()
    total_revenue = sum(r[4] for r in rows)
    print(f"  Inserted {len(rows)} sales records (${total_revenue:,.0f} revenue)")


def generate_invoices(conn, start, end, start_num):
    """Generate invoices for the given date range."""
    print(f"Generating invoices {start} → {end}...")
    cursor = conn.cursor()

    invoice_num = start_num
    rows_inv = []
    rows_items = []

    for d in daterange(start, end):
        for sup_name, freq, (lo, hi) in SUPPLIERS:
            should_deliver = False
            dow_idx = (d.weekday() + 1) % 7

            if freq == 'weekly':
                delivery_dow = hash(sup_name) % 5 + 1
                if dow_idx == delivery_dow:
                    should_deliver = True
                if random.random() < 0.08:
                    should_deliver = False
            elif freq == 'biweekly':
                delivery_dow = hash(sup_name) % 5 + 1
                week_num = d.isocalendar()[1]
                if dow_idx == delivery_dow and week_num % 2 == 0:
                    should_deliver = True
                if random.random() < 0.05:
                    should_deliver = False
            elif freq == 'monthly':
                if d.day >= 3 and d.day <= 8 and dow_idx >= 1 and dow_idx <= 5:
                    if hash(f"{sup_name}{d.month}{d.year}") % 5 == (d.day - 3):
                        should_deliver = True

            if not should_deliver:
                continue

            season = MONTHLY_SEASON[d.month]
            total = round(random.uniform(lo, hi) * season, 2)

            inv_number = f"INV-{invoice_num:05d}"
            invoice_num += 1

            # Recent invoices: mix of paid and pending
            days_ago = (date.today() - d).days
            if days_ago > 14:
                status = random.choice(['paid', 'paid', 'paid', 'pending'])
            else:
                status = random.choice(['paid', 'pending'])

            rows_inv.append((
                inv_number, sup_name, d.isoformat(), d.isoformat(),
                total, status, 1 if status == 'paid' else 0, None
            ))

            # Line items
            num_items = random.randint(1, 4)
            remaining = total
            for j in range(num_items):
                ing = random.choice(INGREDIENT_SAMPLES)
                ing_id, ing_name, unit, unit_price = ing

                if unit_price < 0.01:
                    unit_price = round(random.uniform(1.0, 8.0), 2)

                if j == num_items - 1:
                    item_total = round(remaining, 2)
                else:
                    item_total = round(remaining * random.uniform(0.15, 0.6), 2)
                    remaining -= item_total

                qty = max(1, round(item_total / unit_price)) if unit_price > 0 else 1
                item_total = round(qty * unit_price, 2)

                lot = f"LOT-{random.randint(10000, 99999)}"
                exp = (d + timedelta(days=random.randint(14, 180))).isoformat()
                desc = f"{ing_name} [Lot: {lot}] [Exp: {exp}]"

                rows_items.append((
                    inv_number, ing_id, None, desc, float(qty), unit_price, item_total
                ))

    # Insert invoices
    cursor.executemany("""
        INSERT INTO invoices
        (invoice_number, supplier_name, invoice_date, received_date,
         total_amount, payment_status, reconciled, notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, rows_inv)

    # Fetch IDs for line items
    placeholders = ','.join('?' for _ in rows_inv)
    inv_numbers = [r[0] for r in rows_inv]
    if inv_numbers:
        cursor.execute(
            f"SELECT id, invoice_number FROM invoices WHERE invoice_number IN ({placeholders})",
            inv_numbers
        )
        inv_id_map = {row[1]: row[0] for row in cursor.fetchall()}

        line_items_with_ids = []
        for inv_num, ing_id, prod_id, desc, qty, up, tp in rows_items:
            inv_id = inv_id_map.get(inv_num)
            if inv_id:
                line_items_with_ids.append((inv_id, ing_id, prod_id, desc, qty, up, tp))

        cursor.executemany("""
            INSERT INTO invoice_line_items
            (invoice_id, ingredient_id, product_id, description, quantity, unit_price, total_price)
            VALUES (?,?,?,?,?,?,?)
        """, line_items_with_ids)

    conn.commit()
    total_spent = sum(r[4] for r in rows_inv)
    print(f"  Inserted {len(rows_inv)} invoices, {len(rows_items)} line items (${total_spent:,.0f} total)")


def main():
    print("=" * 60)
    print("Firing Up — Fill Feb 2026 Sales & Invoice Gap")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Check current boundaries
        cursor = conn.cursor()

        cursor.execute("SELECT MAX(sale_date) FROM sales_history")
        last_sale = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(invoice_date) FROM invoices")
        last_invoice = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(CAST(REPLACE(invoice_number, 'INV-', '') AS INTEGER)) FROM invoices")
        last_inv_num = cursor.fetchone()[0] or 1058

        today = date.today()

        print(f"\nCurrent data boundaries:")
        print(f"  Last sale:    {last_sale}")
        print(f"  Last invoice: {last_invoice}")
        print(f"  Today:        {today}")

        # Sales: fill from day after last sale to today
        sales_start = date.fromisoformat(last_sale) + timedelta(days=1)
        if sales_start <= today:
            generate_sales(conn, sales_start, today)
        else:
            print(f"\nSales already up to date ({last_sale})")

        # Invoices: fill from day after last invoice to today
        inv_start = date.fromisoformat(last_invoice) + timedelta(days=1)
        if inv_start <= today:
            generate_invoices(conn, inv_start, today, last_inv_num + 1)
        else:
            print(f"\nInvoices already up to date ({last_invoice})")

        # Verify
        print("\n" + "=" * 60)
        print("Verification:")
        for table, col in [
            ('sales_history', 'sale_date'),
            ('invoices', 'invoice_date'),
            ('attendance', 'date(clock_in)'),
        ]:
            cursor.execute(f"SELECT MIN({col}), MAX({col}), COUNT(*) FROM {table}")
            r = cursor.fetchone()
            print(f"  {table}: {r[0]} → {r[1]} ({r[2]:,} rows)")

        # Feb-specific check
        print("\nFebruary 2026 coverage:")
        for table, col in [
            ('sales_history', 'sale_date'),
            ('invoices', 'invoice_date'),
            ('attendance', 'date(clock_in)'),
        ]:
            cursor.execute(f"""
                SELECT COUNT(*), COALESCE(MIN({col}), '-'), COALESCE(MAX({col}), '-')
                FROM {table}
                WHERE {col} >= '2026-02-01' AND {col} <= '2026-02-28'
            """)
            r = cursor.fetchone()
            print(f"  {table}: {r[1]} → {r[2]} ({r[0]:,} rows)")

        print("\nDone!")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
