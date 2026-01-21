import sqlite3
from datetime import datetime, timedelta
import random

INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def add_packaging_materials():
    """Add bags and pizza boxes to inventory via invoices"""
    print("\n" + "="*70)
    print("STEP 1: Adding Packaging Materials")
    print("="*70 + "\n")

    conn_inv = get_db_connection(INVENTORY_DB)
    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_inv = conn_inv.cursor()
    cursor_invoices = conn_invoices.cursor()

    # Packaging items to add
    packaging_items = [
        # Bags
        {'code': 'BAG-S', 'name': 'Small Paper Bag', 'category': 'Packaging', 'uom': 'each',
         'supplier': 'Restaurant Depot', 'qty': 500, 'unit_price': 0.08, 'case_qty': 500},
        {'code': 'BAG-M', 'name': 'Medium Paper Bag', 'category': 'Packaging', 'uom': 'each',
         'supplier': 'Restaurant Depot', 'qty': 400, 'unit_price': 0.12, 'case_qty': 400},
        {'code': 'BAG-L', 'name': 'Large Paper Bag', 'category': 'Packaging', 'uom': 'each',
         'supplier': 'Restaurant Depot', 'qty': 300, 'unit_price': 0.15, 'case_qty': 300},

        # Pizza Boxes
        {'code': 'BOX-PIZZA-S', 'name': '10" Pizza Box', 'category': 'Packaging', 'uom': 'each',
         'supplier': 'Restaurant Depot', 'qty': 200, 'unit_price': 0.35, 'case_qty': 100},
        {'code': 'BOX-PIZZA-M', 'name': '14" Pizza Box', 'category': 'Packaging', 'uom': 'each',
         'supplier': 'Restaurant Depot', 'qty': 200, 'unit_price': 0.45, 'case_qty': 100},
        {'code': 'BOX-PIZZA-L', 'name': '16" Pizza Box', 'category': 'Packaging', 'uom': 'each',
         'supplier': 'Restaurant Depot', 'qty': 150, 'unit_price': 0.55, 'case_qty': 50},
    ]

    invoice_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')

    for item in packaging_items:
        # Check if already exists
        cursor_inv.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", (item['code'],))
        existing = cursor_inv.fetchone()

        if existing:
            print(f"  ⊕ {item['name']} already exists, skipping")
            continue

        # Add to inventory
        cursor_inv.execute("""
            INSERT INTO ingredients (
                ingredient_code, ingredient_name, category, unit_of_measure,
                quantity_on_hand, unit_cost, supplier_name, date_received,
                last_unit_price, average_unit_price, active, units_per_case
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            item['code'], item['name'], item['category'], item['uom'],
            item['qty'], item['unit_price'], item['supplier'], invoice_date,
            item['unit_price'], item['unit_price'], item['case_qty']
        ))

        # Create invoice
        invoice_total = item['qty'] * item['unit_price']
        invoice_num = f"PKG-{item['code']}-001"

        cursor_invoices.execute("""
            INSERT INTO invoices (
                invoice_number, invoice_date, supplier_name, total_amount
            ) VALUES (?, ?, ?, ?)
        """, (invoice_num, invoice_date, item['supplier'], invoice_total))

        invoice_id = cursor_invoices.lastrowid

        # Create invoice line item
        cursor_invoices.execute("""
            INSERT INTO invoice_line_items (
                invoice_id, ingredient_code, ingredient_name, quantity_received,
                unit_price, total_price, unit_of_measure
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_id, item['code'], item['name'], item['qty'],
            item['unit_price'], invoice_total, item['uom']
        ))

        print(f"  ✓ Added {item['name']}: {item['qty']} @ ${item['unit_price']}")

    conn_inv.commit()
    conn_invoices.commit()
    conn_inv.close()
    conn_invoices.close()
    print(f"\n✓ Packaging materials added successfully")

def add_pizza_ingredients():
    """Add pizza-specific ingredients"""
    print("\n" + "="*70)
    print("STEP 2: Adding Pizza Ingredients")
    print("="*70 + "\n")

    conn_inv = get_db_connection(INVENTORY_DB)
    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_inv = conn_inv.cursor()
    cursor_invoices = conn_invoices.cursor()

    pizza_ingredients = [
        {'code': 'DOUGH-PIZ', 'name': 'Pizza Dough Ball', 'category': 'Dough', 'uom': 'each',
         'supplier': 'Eddy\'s', 'qty': 50, 'unit_price': 1.25, 'case_qty': 50},
        {'code': 'SAUCE-PIZ', 'name': 'Pizza Sauce', 'category': 'Sauces', 'uom': 'oz',
         'supplier': 'Reinhart Foodservice', 'qty': 128, 'unit_price': 0.08, 'case_qty': 128},
        {'code': 'CHEESE-MOZ', 'name': 'Mozzarella Cheese Shredded', 'category': 'Dairy', 'uom': 'lb',
         'supplier': 'Reinhart Foodservice', 'qty': 20, 'unit_price': 3.50, 'case_qty': 20},
        {'code': 'PEPP-SLICE', 'name': 'Pepperoni Sliced', 'category': 'Proteins', 'uom': 'lb',
         'supplier': 'Reinhart Foodservice', 'qty': 10, 'unit_price': 4.25, 'case_qty': 10},
        {'code': 'SAUS-ITAL', 'name': 'Italian Sausage', 'category': 'Proteins', 'uom': 'lb',
         'supplier': 'Reinhart Foodservice', 'qty': 10, 'unit_price': 3.75, 'case_qty': 10},
        {'code': 'MUSH-SLICE', 'name': 'Mushrooms Sliced', 'category': 'Produce', 'uom': 'lb',
         'supplier': 'LA Specialty Produce', 'qty': 5, 'unit_price': 2.50, 'case_qty': 5},
        {'code': 'ONION-DICE', 'name': 'Onions Diced', 'category': 'Produce', 'uom': 'lb',
         'supplier': 'LA Specialty Produce', 'qty': 5, 'unit_price': 1.50, 'case_qty': 5},
        {'code': 'PEPPER-DICE', 'name': 'Bell Peppers Diced', 'category': 'Produce', 'uom': 'lb',
         'supplier': 'LA Specialty Produce', 'qty': 5, 'unit_price': 2.00, 'case_qty': 5},
    ]

    invoice_date = (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d')

    for item in pizza_ingredients:
        # Check if already exists
        cursor_inv.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", (item['code'],))
        existing = cursor_inv.fetchone()

        if existing:
            print(f"  ⊕ {item['name']} already exists, skipping")
            continue

        # Add to inventory
        cursor_inv.execute("""
            INSERT INTO ingredients (
                ingredient_code, ingredient_name, category, unit_of_measure,
                quantity_on_hand, unit_cost, supplier_name, date_received,
                last_unit_price, average_unit_price, active, units_per_case
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            item['code'], item['name'], item['category'], item['uom'],
            item['qty'], item['unit_price'], item['supplier'], invoice_date,
            item['unit_price'], item['unit_price'], item['case_qty']
        ))

        # Create invoice
        invoice_total = item['qty'] * item['unit_price']
        invoice_num = f"PIZZA-{item['code']}-001"

        cursor_invoices.execute("""
            INSERT INTO invoices (
                invoice_number, invoice_date, supplier_name, total_amount
            ) VALUES (?, ?, ?, ?)
        """, (invoice_num, invoice_date, item['supplier'], invoice_total))

        invoice_id = cursor_invoices.lastrowid

        # Create invoice line item
        cursor_invoices.execute("""
            INSERT INTO invoice_line_items (
                invoice_id, ingredient_code, ingredient_name, quantity_received,
                unit_price, total_price, unit_of_measure
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_id, item['code'], item['name'], item['qty'],
            item['unit_price'], invoice_total, item['uom']
        ))

        print(f"  ✓ Added {item['name']}: {item['qty']} {item['uom']} @ ${item['unit_price']}")

    conn_inv.commit()
    conn_invoices.commit()
    conn_inv.close()
    conn_invoices.close()
    print(f"\n✓ Pizza ingredients added successfully")

def create_pizza_products():
    """Create pizza products with recipes"""
    print("\n" + "="*70)
    print("STEP 3: Creating Pizza Products with Recipes")
    print("="*70 + "\n")

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get ingredient IDs
    def get_ingredient_id(code):
        cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", (code,))
        result = cursor.fetchone()
        return result['id'] if result else None

    pizzas = [
        {
            'code': 'PIZZA-CHZ-S',
            'name': 'Cheese Pizza - Small (10")',
            'category': 'Pizza',
            'price': 9.99,
            'recipe': [
                ('DOUGH-PIZ', 1),
                ('SAUCE-PIZ', 4),
                ('CHEESE-MOZ', 0.25),
                ('BOX-PIZZA-S', 1),
            ]
        },
        {
            'code': 'PIZZA-CHZ-M',
            'name': 'Cheese Pizza - Medium (14")',
            'category': 'Pizza',
            'price': 13.99,
            'recipe': [
                ('DOUGH-PIZ', 1.5),
                ('SAUCE-PIZ', 6),
                ('CHEESE-MOZ', 0.4),
                ('BOX-PIZZA-M', 1),
            ]
        },
        {
            'code': 'PIZZA-CHZ-L',
            'name': 'Cheese Pizza - Large (16")',
            'category': 'Pizza',
            'price': 16.99,
            'recipe': [
                ('DOUGH-PIZ', 2),
                ('SAUCE-PIZ', 8),
                ('CHEESE-MOZ', 0.5),
                ('BOX-PIZZA-L', 1),
            ]
        },
        {
            'code': 'PIZZA-PEP-M',
            'name': 'Pepperoni Pizza - Medium (14")',
            'category': 'Pizza',
            'price': 15.99,
            'recipe': [
                ('DOUGH-PIZ', 1.5),
                ('SAUCE-PIZ', 6),
                ('CHEESE-MOZ', 0.4),
                ('PEPP-SLICE', 0.2),
                ('BOX-PIZZA-M', 1),
            ]
        },
        {
            'code': 'PIZZA-SUP-L',
            'name': 'Supreme Pizza - Large (16")',
            'category': 'Pizza',
            'price': 20.99,
            'recipe': [
                ('DOUGH-PIZ', 2),
                ('SAUCE-PIZ', 8),
                ('CHEESE-MOZ', 0.5),
                ('PEPP-SLICE', 0.15),
                ('SAUS-ITAL', 0.15),
                ('MUSH-SLICE', 0.1),
                ('ONION-DICE', 0.08),
                ('PEPPER-DICE', 0.08),
                ('BOX-PIZZA-L', 1),
            ]
        },
    ]

    for pizza in pizzas:
        # Check if product exists
        cursor.execute("SELECT id FROM products WHERE product_name = ?", (pizza['name'],))
        existing = cursor.fetchone()

        if existing:
            print(f"  ⊕ {pizza['name']} already exists, skipping")
            continue

        # Create product
        cursor.execute("""
            INSERT INTO products (product_code, product_name, category, unit_of_measure, selling_price)
            VALUES (?, ?, ?, 'each', ?)
        """, (pizza['code'], pizza['name'], pizza['category'], pizza['price']))

        product_id = cursor.lastrowid

        # Add recipe items
        total_cost = 0
        for ing_code, qty in pizza['recipe']:
            ing_id = get_ingredient_id(ing_code)
            if ing_id:
                cursor.execute("SELECT average_unit_price, unit_of_measure FROM ingredients WHERE id = ?", (ing_id,))
                ing_info = cursor.fetchone()
                unit_price = ing_info['average_unit_price']
                uom = ing_info['unit_of_measure']
                total_cost += unit_price * qty

                cursor.execute("""
                    INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure)
                    VALUES (?, ?, ?, ?)
                """, (product_id, ing_id, qty, uom))

        margin = ((pizza['price'] - total_cost) / pizza['price'] * 100) if pizza['price'] > 0 else 0
        print(f"  ✓ Created {pizza['name']}: ${pizza['price']} (cost: ${total_cost:.2f}, margin: {margin:.1f}%)")

    conn.commit()
    conn.close()
    print(f"\n✓ Pizza products created successfully")

def link_bags_to_products():
    """Link bags to existing products"""
    print("\n" + "="*70)
    print("STEP 4: Linking Bags to Existing Products")
    print("="*70 + "\n")

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get bag IDs
    def get_ingredient_id(code):
        cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", (code,))
        result = cursor.fetchone()
        return result['id'] if result else None

    bag_small_id = get_ingredient_id('BAG-S')
    bag_medium_id = get_ingredient_id('BAG-M')
    bag_large_id = get_ingredient_id('BAG-L')

    if not all([bag_small_id, bag_medium_id, bag_large_id]):
        print("  ⚠ Bags not found in inventory")
        conn.close()
        return

    # Get products without "Pizza" (pizzas already have boxes)
    cursor.execute("""
        SELECT id, product_name, category
        FROM products
        WHERE product_name NOT LIKE '%Pizza%'
        ORDER BY product_name
        LIMIT 10
    """)

    products = cursor.fetchall()
    added_count = 0

    for product in products:
        product_id = product['id']
        product_name = product['product_name']

        # Check if already has a bag
        cursor.execute("""
            SELECT r.id
            FROM recipes r
            JOIN ingredients i ON r.ingredient_id = i.id
            WHERE r.product_id = ? AND i.ingredient_code LIKE 'BAG-%'
        """, (product_id,))

        if cursor.fetchone():
            print(f"  ⊕ {product_name} already has bag, skipping")
            continue

        # Assign bag based on product name/category
        if 'Sandwich' in product_name or 'Burger' in product_name:
            bag_id = bag_medium_id
            bag_type = 'Medium'
        elif 'Side' in product_name or 'Fries' in product_name:
            bag_id = bag_small_id
            bag_type = 'Small'
        else:
            # Random for variety
            bag_id = random.choice([bag_small_id, bag_medium_id, bag_large_id])
            bag_type = ['Small', 'Medium', 'Large'][bag_id - bag_small_id]

        # Get bag unit of measure
        cursor.execute("SELECT unit_of_measure FROM ingredients WHERE id = ?", (bag_id,))
        bag_uom = cursor.fetchone()['unit_of_measure']

        cursor.execute("""
            INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure)
            VALUES (?, ?, 1, ?)
        """, (product_id, bag_id, bag_uom))

        added_count += 1
        print(f"  ✓ Linked {bag_type} bag to {product_name}")

    conn.commit()
    conn.close()
    print(f"\n✓ Linked bags to {added_count} products")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("SALES TRACKING SYSTEM SETUP")
    print("="*70)

    add_packaging_materials()
    add_pizza_ingredients()
    create_pizza_products()
    link_bags_to_products()

    print("\n" + "="*70)
    print("✓ SETUP COMPLETE")
    print("="*70 + "\n")
