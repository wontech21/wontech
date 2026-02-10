#!/usr/bin/env python3
"""
Simulate realistic historical data for Firing Up pizzeria.
Fills Jan 2025 → start of existing data for each category.

Existing data boundaries:
  - sales_history:  2025-10-25 → 2026-02-09
  - invoices:       2025-10-28 → 2026-01-21
  - attendance:     2026-01-25 → 2026-03-31
  - payroll_history: 2026-01-01 → 2026-01-31

This script fills:
  - sales_history:   2025-01-01 → 2025-10-24
  - invoices:        2025-01-02 → 2025-10-27
  - attendance:      2025-01-01 → 2026-01-24
  - payroll_history: 2025-01-01 → 2025-12-31
"""

import sqlite3
import random
import math
from datetime import datetime, timedelta, date

DB_PATH = '/Users/dell/WONTECH/databases/org_1.db'
ORG_ID = 1
random.seed(42)  # Reproducible

# ─── Product catalog (exclude test items) ───
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
# Normalize weights
_total_w = sum(p[4] for p in PRODUCTS)
for i in range(len(PRODUCTS)):
    PRODUCTS[i] = (*PRODUCTS[i][:4], PRODUCTS[i][4] / _total_w)

# ─── Employees (backdate hire dates to 2024 for realism) ───
EMPLOYEES = [
    (1,  'John',    'Smith',     'Line Cook',        'Kitchen',        18.50, 0.0,     'hourly'),
    (2,  'Gabriel', 'Silveira',  'Cashier',          'Front',          16.00, 0.0,     'hourly'),
    (3,  'Gabriel', 'Thompson',  'General Manager',  'Management',      0.00, 2884.62, 'salary'),
    (4,  'Sideir',  'Osman',     'Kitchen Staff',    'Kitchen',        17.00, 0.0,     'hourly'),
    (5,  'Emily',   'Rodriguez', 'Server',           'Front of House', 15.00, 0.0,     'hourly'),
    (6,  'Marcus',  'Johnson',   'Head Chef',        'Kitchen',        22.00, 0.0,     'hourly'),
    (7,  'Sarah',   'Williams',  'Bartender',        'Bar',            17.00, 0.0,     'hourly'),
    (8,  'David',   'Brown',     'Line Cook',        'Kitchen',        17.50, 0.0,     'hourly'),
    (9,  'Jessica', 'Davis',     'Host',             'Front of House', 14.00, 0.0,     'hourly'),
    (10, 'Michael', 'Chen',      'Dishwasher',       'Kitchen',        15.00, 0.0,     'hourly'),
]

# ─── Suppliers with realistic delivery patterns ───
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

# ─── Seasonality curve (1.0 = baseline) ───
# Pizzeria: slow Jan/Feb, builds spring, summer peak, slight fall dip, holiday bump Dec
MONTHLY_SEASON = {
    1: 0.80, 2: 0.78, 3: 0.88, 4: 0.95, 5: 1.02,  6: 1.10,
    7: 1.12, 8: 1.08, 9: 0.98, 10: 0.95, 11: 0.92, 12: 1.00,
}

# Day-of-week multipliers (from actual data patterns)
DOW_MULT = {
    0: 1.12,  # Sun
    1: 0.65,  # Mon (slowest)
    2: 0.80,  # Tue
    3: 0.88,  # Wed
    4: 0.95,  # Thu
    5: 1.27,  # Fri
    6: 1.48,  # Sat (busiest)
}

# ─── Shift templates by role ───
SHIFT_TEMPLATES = {
    'Kitchen':        [('07:00', '15:00'), ('10:00', '18:00'), ('14:00', '22:00')],
    'Front':          [('10:00', '18:00'), ('14:00', '22:00'), ('16:00', '23:00')],
    'Front of House': [('10:00', '18:00'), ('14:00', '22:00'), ('16:00', '23:00')],
    'Bar':            [('16:00', '00:00'), ('14:00', '22:00')],
    'Management':     [('09:00', '17:00'), ('10:00', '18:00')],
}

# ─── Ingredient samples for invoice line items ───
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


def daterange(start, end):
    """Yield dates from start to end (inclusive)."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def pick_product():
    """Weighted random product selection."""
    r = random.random()
    cumulative = 0
    for pid, name, cat, price, weight in PRODUCTS:
        cumulative += weight
        if r <= cumulative:
            return pid, name, cat, price
    return PRODUCTS[-1][:4]


def generate_sales(conn):
    """Generate sales_history from 2025-01-01 to 2025-10-24."""
    print("Generating sales data...")
    cursor = conn.cursor()

    start = date(2025, 1, 1)
    end = date(2025, 10, 24)  # Day before existing data starts

    # Baseline: ~320 items/day average (from existing data ~550 avg but that's after 10 months of growth)
    # Start lower in Jan 2025, grow ~3% per month (new restaurant ramp-up)
    base_items_per_day = 280
    growth_per_month = 1.03  # 3% monthly growth

    rows = []
    for d in daterange(start, end):
        months_elapsed = (d.year - 2025) * 12 + d.month - 1  # 0 for Jan 2025
        growth = growth_per_month ** months_elapsed
        season = MONTHLY_SEASON[d.month]
        dow = DOW_MULT[d.weekday()]  # weekday(): Mon=0, Sun=6
        # Python weekday: Mon=0..Sun=6. Our DOW_MULT: 0=Sun..6=Sat
        dow_idx = (d.weekday() + 1) % 7  # Convert to Sun=0..Sat=6
        dow = DOW_MULT[dow_idx]

        daily_items = int(base_items_per_day * growth * season * dow * random.uniform(0.85, 1.15))
        daily_items = max(daily_items, 50)

        # Generate individual product sales
        sale_times = sorted([
            f"{random.randint(10, 22):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
            for _ in range(min(daily_items, 600))
        ])

        item_idx = 0
        for _ in range(daily_items):
            pid, pname, cat, base_price = pick_product()
            qty = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]

            # Slight price variation (occasional discount)
            discount_pct = 0
            if random.random() < 0.05:  # 5% chance of discount
                discount_pct = random.choice([5, 10, 15])

            sale_price = round(base_price * (1 - discount_pct / 100), 2)
            revenue = round(sale_price * qty, 2)
            cogs = round(revenue * random.uniform(0.28, 0.38), 2)
            profit = round(revenue - cogs, 2)
            discount_amt = round(base_price * qty - revenue, 2) if discount_pct else 0

            sale_time = sale_times[item_idx % len(sale_times)] if sale_times else '12:00:00'
            item_idx += 1

            rows.append((
                d.isoformat(), pid, pname, float(qty), revenue, cogs, profit,
                d.isoformat(), None, sale_time,
                base_price if discount_pct else None,
                sale_price if discount_pct else None,
                discount_amt if discount_pct else None,
                float(discount_pct) if discount_pct else None,
            ))

    cursor.executemany("""
        INSERT INTO sales_history
        (sale_date, product_id, product_name, quantity_sold, revenue, cost_of_goods,
         gross_profit, processed_date, notes, sale_time, original_price, sale_price,
         discount_amount, discount_percent)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)

    conn.commit()
    print(f"  Inserted {len(rows)} sales records ({start} → {end})")


def generate_attendance(conn):
    """Generate attendance from 2025-01-01 to 2026-01-24."""
    print("Generating attendance data...")
    cursor = conn.cursor()

    start = date(2025, 1, 1)
    end = date(2026, 1, 24)  # Day before existing attendance starts

    rows = []
    for d in daterange(start, end):
        dow_idx = (d.weekday() + 1) % 7  # Sun=0..Sat=6

        for emp_id, fn, ln, position, dept, rate, salary, pay_type in EMPLOYEES:
            # Scheduling logic: not everyone works every day
            # Kitchen staff: 5-6 days/week, FOH: 4-5 days, Management: 5 days, Bar: 4-5 days
            if dept == 'Management':
                # Works Mon-Fri mostly, occasional Sat
                if dow_idx == 0:  # Sunday off
                    continue
                if dow_idx == 6 and random.random() < 0.6:  # Sat 40% chance
                    continue
                if random.random() < 0.08:  # 8% call-out
                    continue
            elif dept == 'Kitchen':
                # 5-6 days, random day off
                if random.random() < 0.20:  # ~1.4 days off/week
                    continue
            elif dept in ('Front', 'Front of House'):
                if random.random() < 0.28:  # ~2 days off/week
                    continue
            elif dept == 'Bar':
                # Bar works more evenings, Thu-Sun heavy
                if dow_idx in (1, 2) and random.random() < 0.65:  # Mon/Tue often off
                    continue
                if random.random() < 0.25:
                    continue

            # Pick a shift template
            templates = SHIFT_TEMPLATES.get(dept, [('10:00', '18:00')])
            shift_start_str, shift_end_str = random.choice(templates)

            # Add some time variance (±30 min)
            sh, sm = map(int, shift_start_str.split(':'))
            eh, em = map(int, shift_end_str.split(':'))

            clock_in_h = sh + random.randint(-1, 0)
            clock_in_m = random.randint(0, 59) if random.random() < 0.3 else sm + random.randint(-5, 10)
            clock_in_m = max(0, min(59, clock_in_m))
            clock_in_h = max(6, min(23, clock_in_h))

            clock_out_h = eh + random.randint(0, 1)
            clock_out_m = random.randint(0, 59) if random.random() < 0.3 else em + random.randint(-10, 15)
            clock_out_m = max(0, min(59, clock_out_m))
            clock_out_h = max(clock_in_h + 3, min(23, clock_out_h))

            clock_in = f"{d.isoformat()} {clock_in_h:02d}:{clock_in_m:02d}:00"
            clock_out = f"{d.isoformat()} {clock_out_h:02d}:{clock_out_m:02d}:00"

            total_hours = round((clock_out_h * 60 + clock_out_m - clock_in_h * 60 - clock_in_m) / 60, 2)
            # Subtract break (~30 min for shifts > 5 hours)
            if total_hours > 5:
                total_hours = round(total_hours - 0.5, 2)

            total_hours = max(total_hours, 2.0)

            # Tips for front-of-house roles
            tips = 0
            if dept in ('Front', 'Front of House', 'Bar'):
                tips = round(random.uniform(15, 80) * DOW_MULT.get((d.weekday() + 1) % 7, 1.0), 2)

            rows.append((
                ORG_ID, emp_id, clock_in, clock_out, total_hours, 0, 'clocked_out', None, tips
            ))

    cursor.executemany("""
        INSERT INTO attendance
        (organization_id, employee_id, clock_in, clock_out, total_hours,
         break_duration, status, notes, cc_tips)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)

    conn.commit()
    print(f"  Inserted {len(rows)} attendance records ({start} → {end})")


def generate_payroll(conn):
    """Generate monthly payroll from Jan 2025 to Dec 2025."""
    print("Generating payroll data...")
    cursor = conn.cursor()

    for month in range(1, 13):
        year = 2025
        import calendar
        first_day = f"{year}-{month:02d}-01"
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = f"{year}-{month:02d}-{last_day_num:02d}"

        for emp_id, fn, ln, position, dept, rate, salary, pay_type in EMPLOYEES:
            if pay_type == 'salary':
                cursor.execute("""
                    INSERT INTO payroll_history
                    (organization_id, employee_id, pay_period_start, pay_period_end,
                     pay_period_type, hourly_rate_used, salary_used, total_hours,
                     regular_hours, ot_hours, regular_wage, ot_wage, tips, gross_pay,
                     job_classification, position, processed_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    ORG_ID, emp_id, first_day, last_day, 'monthly',
                    0, salary, 0, 0, 0, 0, 0, 0, salary, dept, position,
                    f"{year}-{month:02d}-{last_day_num:02d} 23:59:00"
                ))
            else:
                # Sum attendance hours for this employee in this month
                cursor.execute("""
                    SELECT COALESCE(SUM(total_hours), 0), COALESCE(SUM(cc_tips), 0)
                    FROM attendance
                    WHERE organization_id = ? AND employee_id = ?
                      AND date(clock_in) >= ? AND date(clock_in) <= ?
                """, (ORG_ID, emp_id, first_day, last_day))

                row = cursor.fetchone()
                total_hrs = round(row[0], 2)
                tips = round(row[1], 2)

                # Weekly OT threshold ~40hrs/week, monthly ~173 hrs
                monthly_ot_threshold = 173
                regular = min(total_hrs, monthly_ot_threshold)
                ot = max(0, total_hrs - monthly_ot_threshold)

                regular_wage = round(regular * rate, 2)
                ot_wage = round(ot * rate * 1.5, 2)
                gross = round(regular_wage + ot_wage + tips, 2)

                cursor.execute("""
                    INSERT INTO payroll_history
                    (organization_id, employee_id, pay_period_start, pay_period_end,
                     pay_period_type, hourly_rate_used, salary_used, total_hours,
                     regular_hours, ot_hours, regular_wage, ot_wage, tips, gross_pay,
                     job_classification, position, processed_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    ORG_ID, emp_id, first_day, last_day, 'monthly',
                    rate, 0, total_hrs, regular, ot,
                    regular_wage, ot_wage, tips, gross,
                    dept, position,
                    f"{year}-{month:02d}-{last_day_num:02d} 23:59:00"
                ))

    conn.commit()
    print(f"  Inserted payroll for Jan-Dec 2025 (10 employees × 12 months)")


def generate_invoices(conn):
    """Generate invoices from 2025-01-02 to 2025-10-27."""
    print("Generating invoice/receiving data...")
    cursor = conn.cursor()

    start = date(2025, 1, 2)
    end = date(2025, 10, 27)  # Day before existing invoices

    invoice_num = 500  # Start numbering from INV-00500
    rows_inv = []
    rows_items = []

    for d in daterange(start, end):
        for sup_name, freq, (lo, hi) in SUPPLIERS:
            should_deliver = False
            dow_idx = (d.weekday() + 1) % 7

            if freq == 'weekly':
                # Each weekly supplier has a set delivery day
                delivery_dow = hash(sup_name) % 5 + 1  # Mon-Fri (1-5)
                if dow_idx == delivery_dow:
                    should_deliver = True
                # Occasional skip
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
                # First or second week of month
                if d.day >= 3 and d.day <= 8 and dow_idx >= 1 and dow_idx <= 5:
                    # Pick one day in that window
                    if hash(f"{sup_name}{d.month}{d.year}") % 5 == (d.day - 3):
                        should_deliver = True

            if not should_deliver:
                continue

            # Generate invoice
            season = MONTHLY_SEASON[d.month]
            total = round(random.uniform(lo, hi) * season, 2)

            inv_number = f"INV-{invoice_num:05d}"
            invoice_num += 1

            # Payment status: older = more likely paid
            days_ago = (date(2026, 2, 9) - d).days
            if days_ago > 60:
                status = 'paid'
            elif days_ago > 30:
                status = random.choice(['paid', 'paid', 'paid', 'pending'])
            else:
                status = random.choice(['paid', 'pending'])

            rows_inv.append((
                inv_number, sup_name, d.isoformat(), d.isoformat(),
                total, status, 1 if status == 'paid' else 0, None
            ))

            # Generate 1-4 line items per invoice
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

    # Insert line items — need invoice IDs
    # Fetch mapping
    cursor.execute("SELECT id, invoice_number FROM invoices WHERE invoice_number LIKE 'INV-00%'")
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
    print(f"  Inserted {len(rows_inv)} invoices, {len(line_items_with_ids)} line items ({start} → {end})")


def backdate_employees(conn):
    """Update employee hire_dates to 2024 for realism (they didn't all start Jan 2026)."""
    print("Backdating employee hire dates...")
    cursor = conn.cursor()
    hire_dates = {
        1: '2024-03-15',   # John - Line Cook
        2: '2024-06-01',   # Gabriel S - Cashier
        3: '2024-01-10',   # Gabriel T - GM (founding)
        4: '2024-04-20',   # Sideir - Kitchen
        5: '2024-07-15',   # Emily - Server
        6: '2024-02-01',   # Marcus - Head Chef (early hire)
        7: '2024-08-01',   # Sarah - Bartender
        8: '2024-05-10',   # David - Line Cook
        9: '2024-09-01',   # Jessica - Host
        10: '2024-06-15',  # Michael - Dishwasher
    }
    for emp_id, hd in hire_dates.items():
        cursor.execute("UPDATE employees SET hire_date = ? WHERE id = ?", (hd, emp_id))
    conn.commit()
    print(f"  Updated {len(hire_dates)} employee hire dates")


def main():
    print("=" * 60)
    print("Firing Up — Historical Data Simulation")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Order matters: attendance before payroll (payroll reads attendance)
        backdate_employees(conn)
        generate_sales(conn)
        generate_invoices(conn)
        generate_attendance(conn)
        generate_payroll(conn)

        # Verify
        cursor = conn.cursor()
        print("\n" + "=" * 60)
        print("Verification:")
        for table, col in [
            ('sales_history', 'sale_date'),
            ('attendance', 'date(clock_in)'),
            ('payroll_history', 'pay_period_start'),
            ('invoices', 'invoice_date'),
        ]:
            cursor.execute(f"SELECT MIN({col}), MAX({col}), COUNT(*) FROM {table}")
            r = cursor.fetchone()
            print(f"  {table}: {r[0]} → {r[1]} ({r[2]:,} rows)")

        print("\nDone!")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
