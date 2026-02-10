#!/usr/bin/env python3
"""
Generate test data for Firing Up Inventory System
- 50 invoices spanning last 2 weeks
- Mix of new and existing ingredients
- Multiple suppliers and brands
- 3 recipes using the ingredients
"""

import sqlite3
import random
from datetime import datetime, timedelta

# Database paths
INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

# Test data pools
SUPPLIERS = [
    'Sysco Foods', 'US Foods', 'Gordon Food Service', 'Performance Foodservice',
    'Restaurant Depot', 'Ben E. Keith', 'Cheney Brothers', 'Reinhart Foodservice',
    'Shamrock Foods', 'Vistar', 'Fresh Express', 'Kings Produce',
    'Baldor Specialty Foods', 'Chefs Warehouse', 'LA Specialty Produce'
]

BRANDS = [
    'Heinz', 'Kraft', 'Tyson', 'ConAgra', 'General Mills', 'Kelloggs',
    'Hormel', 'Smithfield', 'Perdue', 'Butterball', 'Land O Lakes',
    'Crystal Farms', 'Boars Head', 'Oscar Mayer', 'French\'s', 'McCormick',
    'Hidden Valley', 'Hellmanns', 'Best Foods', 'Dole', 'Fresh Express',
    'Taylor Farms', 'Ore-Ida', 'Birds Eye', 'Stouffers', 'Nestle',
    'Unilever', 'Barilla', 'De Cecco', 'Bumble Bee', 'StarKist'
]

CATEGORIES = [
    'Meat', 'Poultry', 'Seafood', 'Dairy', 'Produce', 'Bread',
    'Dry Foods', 'Frozen Foods', 'Condiments', 'Beverages',
    'Spices & Seasonings', 'Oils & Vinegars', 'Canned Goods', 'Baking Supplies'
]

# Ingredient pools by category
INGREDIENTS = {
    'Meat': ['Ground Beef', 'Beef Brisket', 'Ribeye Steak', 'Pork Chops', 'Bacon', 'Sausage Links', 'Italian Sausage'],
    'Poultry': ['Chicken Breast', 'Chicken Thighs', 'Chicken Wings', 'Turkey Breast', 'Ground Turkey'],
    'Seafood': ['Salmon Fillets', 'Shrimp 16/20', 'Cod Fillets', 'Tuna Steaks', 'Tilapia'],
    'Dairy': ['Whole Milk', 'Heavy Cream', 'Butter', 'Cheddar Cheese', 'Mozzarella Cheese', 'Parmesan Cheese', 'Eggs', 'Sour Cream', 'Cream Cheese'],
    'Produce': ['Romaine Lettuce', 'Iceberg Lettuce', 'Tomatoes', 'Onions', 'Bell Peppers', 'Mushrooms', 'Potatoes', 'Carrots', 'Celery', 'Garlic', 'Avocados', 'Lemons', 'Limes'],
    'Bread': ['Hamburger Buns', 'Hot Dog Buns', 'Sliced Bread', 'Tortillas', 'Pita Bread', 'French Bread'],
    'Dry Foods': ['Pasta Penne', 'Pasta Spaghetti', 'Rice Long Grain', 'Flour All Purpose', 'Sugar Granulated', 'Salt', 'Black Pepper', 'Panko Breadcrumbs'],
    'Frozen Foods': ['French Fries', 'Onion Rings', 'Chicken Tenders', 'Fish Sticks', 'Mixed Vegetables', 'Corn', 'Peas'],
    'Condiments': ['Ketchup', 'Mustard', 'Mayonnaise', 'Ranch Dressing', 'BBQ Sauce', 'Hot Sauce', 'Soy Sauce', 'Worcestershire Sauce', 'Pickles'],
    'Beverages': ['Coca Cola', 'Pepsi', 'Sprite', 'Orange Juice', 'Apple Juice', 'Coffee Grounds', 'Tea Bags'],
    'Spices & Seasonings': ['Garlic Powder', 'Onion Powder', 'Paprika', 'Cumin', 'Oregano', 'Basil', 'Thyme', 'Chili Powder'],
    'Oils & Vinegars': ['Vegetable Oil', 'Olive Oil', 'Canola Oil', 'Balsamic Vinegar', 'Red Wine Vinegar'],
    'Canned Goods': ['Diced Tomatoes', 'Tomato Sauce', 'Black Beans', 'Kidney Beans', 'Corn', 'Green Beans', 'Chicken Broth', 'Beef Broth'],
    'Baking Supplies': ['Baking Powder', 'Baking Soda', 'Vanilla Extract', 'Chocolate Chips', 'Brown Sugar']
}

UNITS = ['lb', 'oz', 'gal', 'qt', 'each', 'case', 'bag', 'box', 'can']

# Recipes to create
RECIPES = [
    {
        'name': 'Classic Burger',
        'selling_price': 12.99,
        'ingredients': [
            ('Ground Beef', 0.33),  # 1/3 lb
            ('Cheddar Cheese', 0.08),  # 1 slice
            ('Hamburger Buns', 1),
            ('Romaine Lettuce', 0.05),
            ('Tomatoes', 0.1),
            ('Onions', 0.05),
            ('Pickles', 0.02),
            ('Ketchup', 0.02),
            ('Mustard', 0.02)
        ]
    },
    {
        'name': 'Chicken Pasta Alfredo',
        'selling_price': 16.99,
        'ingredients': [
            ('Chicken Breast', 0.5),
            ('Pasta Penne', 0.25),
            ('Heavy Cream', 0.5),
            ('Parmesan Cheese', 0.15),
            ('Butter', 0.1),
            ('Garlic', 0.05),
            ('Black Pepper', 0.01),
            ('Salt', 0.01)
        ]
    },
    {
        'name': 'Fish and Chips',
        'selling_price': 14.99,
        'ingredients': [
            ('Cod Fillets', 0.5),
            ('French Fries', 0.5),
            ('Flour All Purpose', 0.1),
            ('Eggs', 1),
            ('Panko Breadcrumbs', 0.15),
            ('Vegetable Oil', 0.25),
            ('Lemons', 0.5),
            ('Salt', 0.01)
        ]
    }
]

def generate_ingredient_code(name):
    """Generate ingredient code from name"""
    words = name.upper().split()
    if len(words) >= 2:
        return f"{words[0][:3]}{words[1][:3]}"
    else:
        return words[0][:6]

def log_audit(conn, action_type, entity_type, entity_id, entity_reference, details):
    """Log to audit table"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (action_type, entity_type, entity_id, entity_reference, details, user, ip_address)
        VALUES (?, ?, ?, ?, ?, 'test_data_generator', '127.0.0.1')
    """, (action_type, entity_type, entity_id, entity_reference, details))
    conn.commit()

def create_supplier_if_not_exists(conn, supplier_name):
    """Create supplier if it doesn't exist"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM suppliers WHERE supplier_name = ?", (supplier_name,))
    result = cursor.fetchone()

    if not result:
        cursor.execute("""
            INSERT INTO suppliers (supplier_name, contact_person, phone, email, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            supplier_name,
            f"Contact-{supplier_name[:10]}",
            f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            f"orders@{supplier_name.lower().replace(' ', '')}.com",
            f"Test supplier created by generator"
        ))
        supplier_id = cursor.lastrowid
        conn.commit()

        # Log supplier creation
        log_audit(conn, 'SUPPLIER_CREATED', 'supplier', supplier_id, supplier_name,
                  f"New supplier created. Contact: Contact-{supplier_name[:10]}")
        return supplier_id
    return result[0]

def get_or_create_ingredient(inv_conn, inv_db, name, brand, supplier, category, unit):
    """Get existing ingredient or create new one"""
    cursor = inv_conn.cursor()

    # Try to find existing
    cursor.execute("""
        SELECT id, ingredient_code, quantity_on_hand, average_unit_price
        FROM ingredients
        WHERE ingredient_name = ? AND brand = ? AND supplier_name = ?
    """, (name, brand, supplier))

    result = cursor.fetchone()

    if result:
        return {
            'id': result[0],
            'code': result[1],
            'existing_qty': result[2],
            'avg_cost': result[3] or 0,
            'is_new': False
        }

    # Create new ingredient
    code = generate_ingredient_code(name)

    # Make sure code is unique
    base_code = code
    counter = 1
    while True:
        cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?", (code,))
        if not cursor.fetchone():
            break
        code = f"{base_code}{counter}"
        counter += 1

    cursor.execute("""
        INSERT INTO ingredients (
            ingredient_code, ingredient_name, brand, supplier_name, category,
            unit_of_measure, quantity_on_hand, unit_cost, average_unit_price, last_unit_price,
            storage_location, active
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 'Storage', 1)
    """, (code, name, brand, supplier, category, unit))

    ingredient_id = cursor.lastrowid
    inv_conn.commit()

    return {
        'id': ingredient_id,
        'code': code,
        'existing_qty': 0,
        'avg_cost': 0,
        'is_new': True
    }

def create_invoice(inv_conn, inv_db_conn, invoice_number, supplier, date_str, line_items):
    """Create an invoice with line items"""
    inv_cursor = inv_db_conn.cursor()

    # Calculate total
    total_amount = sum(item['total_price'] for item in line_items)

    # Create invoice
    inv_cursor.execute("""
        INSERT INTO invoices (
            invoice_number, supplier_name, invoice_date, received_date,
            total_amount, payment_status, reconciled, reconciled_date, notes
        ) VALUES (?, ?, ?, ?, ?, 'UNPAID', 'YES', CURRENT_TIMESTAMP, ?)
    """, (
        invoice_number,
        supplier,
        date_str,
        date_str,
        total_amount,
        f"Test invoice generated for {supplier}"
    ))

    invoice_id = inv_cursor.lastrowid
    inv_db_conn.commit()

    # Log invoice creation
    log_audit(inv_conn, 'INVOICE_CREATED', 'invoice', invoice_id, invoice_number,
              f"Invoice created for {supplier}. Total: ${total_amount:.2f}")

    # Create line items and update inventory
    for item in line_items:
        # Insert invoice line item
        inv_cursor.execute("""
            INSERT INTO invoice_line_items (
                invoice_id, ingredient_code, ingredient_name, brand,
                quantity_received, unit_of_measure, unit_price, total_price,
                reconciled_to_inventory
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'YES')
        """, (
            invoice_id,
            item['code'],
            item['name'],
            item['brand'],
            item['quantity'],
            item['unit'],
            item['unit_price'],
            item['total_price']
        ))
        inv_db_conn.commit()

        # Update inventory
        inventory_cursor = inv_conn.cursor()
        ingredient_info = item['ingredient_info']

        if ingredient_info['is_new']:
            # New item - just log creation
            log_audit(inv_conn, 'ITEM_CREATED', 'item', ingredient_info['id'],
                     f"{item['code']} - {item['name']}",
                     f"New item added via invoice. Qty: {item['quantity']} {item['unit']}, Supplier: {supplier}")

        # Calculate new average cost
        old_qty = ingredient_info['existing_qty']
        old_avg = ingredient_info['avg_cost']
        new_qty = item['quantity']
        new_cost = item['unit_price']

        total_qty = old_qty + new_qty
        if total_qty > 0:
            new_avg_cost = ((old_qty * old_avg) + (new_qty * new_cost)) / total_qty
        else:
            new_avg_cost = new_cost

        # Update ingredient
        inventory_cursor.execute("""
            UPDATE ingredients
            SET quantity_on_hand = quantity_on_hand + ?,
                average_unit_price = ?,
                last_unit_price = ?,
                unit_cost = ?,
                date_received = ?
            WHERE id = ?
        """, (new_qty, new_avg_cost, new_cost, new_avg_cost, date_str, ingredient_info['id']))
        inv_conn.commit()

    return invoice_id

def create_recipe(conn, recipe_data, ingredient_map):
    """Create a recipe (product with ingredient links)"""
    cursor = conn.cursor()

    # Generate product code
    product_code = 'PROD-' + ''.join([word[0] for word in recipe_data['name'].split()]).upper()

    # Check if product already exists
    cursor.execute("SELECT id FROM products WHERE product_code = ?", (product_code,))
    existing = cursor.fetchone()

    if existing:
        # Product already exists, delete old recipe links and recreate
        product_id = existing[0]
        cursor.execute("DELETE FROM recipes WHERE product_id = ?", (product_id,))
        conn.commit()
    else:
        # Create product
        cursor.execute("""
            INSERT INTO products (
                product_code, product_name, category, unit_of_measure,
                quantity_on_hand, selling_price
            ) VALUES (?, ?, 'Prepared Foods', 'each', 0, ?)
        """, (product_code, recipe_data['name'], recipe_data['selling_price']))

        product_id = cursor.lastrowid
        conn.commit()

    # Add ingredients to recipe
    for ing_name, quantity in recipe_data['ingredients']:
        # Find ingredient
        ingredient_id = None
        for key, ing_info in ingredient_map.items():
            if ing_name.lower() in key.lower():
                ingredient_id = ing_info['id']
                break

        if ingredient_id:
            cursor.execute("""
                INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure)
                VALUES (?, ?, ?, 'lb')
            """, (product_id, ingredient_id, quantity))

    conn.commit()
    return product_id

def main():
    print("=" * 60)
    print("🔥 GENERATING TEST DATA FOR FIRING UP INVENTORY")
    print("=" * 60)
    print()

    # Connect to databases
    inv_conn = sqlite3.connect(INVENTORY_DB)
    inv_db_conn = sqlite3.connect(INVOICES_DB)

    # Track created items
    ingredient_map = {}
    created_suppliers = []

    # Generate invoices over last 2 weeks
    today = datetime.now()
    start_date = today - timedelta(days=14)

    print(f"📅 Generating 50 invoices from {start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    print()

    for i in range(50):
        # Random date in the range
        days_offset = random.randint(0, 14)
        invoice_date = start_date + timedelta(days=days_offset)
        date_str = invoice_date.strftime('%Y-%m-%d')

        # Random supplier
        supplier = random.choice(SUPPLIERS)
        if supplier not in created_suppliers:
            create_supplier_if_not_exists(inv_conn, supplier)  # Use inv_conn not inv_db_conn
            created_suppliers.append(supplier)

        # Generate invoice number (add counter to make unique across runs)
        invoice_number = f"INV-{invoice_date.strftime('%Y%m%d')}-{random.randint(1000, 9999)}-{i+1}"

        # Generate 3-8 line items
        num_items = random.randint(3, 8)
        line_items = []

        for j in range(num_items):
            # Pick random category and ingredient
            category = random.choice(list(INGREDIENTS.keys()))
            ing_name = random.choice(INGREDIENTS[category])
            brand = random.choice(BRANDS)
            unit = random.choice(['lb', 'oz', 'each', 'case', 'gal'])

            # 70% chance to use existing ingredient, 30% new
            key = f"{ing_name}_{brand}_{supplier}"
            if key in ingredient_map and random.random() < 0.7:
                ingredient_info = ingredient_map[key]
            else:
                ingredient_info = get_or_create_ingredient(
                    inv_conn, inv_db_conn, ing_name, brand, supplier, category, unit
                )
                ingredient_map[key] = ingredient_info

                # Log brand creation if new
                if ingredient_info['is_new']:
                    cursor = inv_conn.cursor()
                    cursor.execute("""
                        SELECT COUNT(*) FROM ingredients WHERE brand = ?
                    """, (brand,))
                    brand_count = cursor.fetchone()[0]
                    if brand_count == 1:  # First item with this brand
                        log_audit(inv_conn, 'BRAND_UPDATED', 'brand', 0, brand,
                                 f"New brand introduced: {brand}")

            # Generate quantities and prices
            quantity = round(random.uniform(5, 100), 2)
            unit_price = round(random.uniform(2, 50), 2)
            total_price = round(quantity * unit_price, 2)

            line_items.append({
                'code': ingredient_info['code'],
                'name': ing_name,
                'brand': brand,
                'unit': unit,
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price,
                'ingredient_info': ingredient_info
            })

        # Create invoice
        create_invoice(inv_conn, inv_db_conn, invoice_number, supplier, date_str, line_items)

        print(f"✅ Invoice {i+1}/50: {invoice_number} - {supplier} - {date_str} - ${sum(item['total_price'] for item in line_items):.2f}")

    print()
    print("=" * 60)
    print("📝 CREATING RECIPES")
    print("=" * 60)
    print()

    # Create recipes
    for recipe_data in RECIPES:
        recipe_id = create_recipe(inv_conn, recipe_data, ingredient_map)
        print(f"✅ Recipe created: {recipe_data['name']} (${recipe_data['selling_price']}) - ID: {recipe_id}")

    print()
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    # Get counts
    inv_cursor = inv_conn.cursor()
    inv_cursor.execute("SELECT COUNT(*) FROM ingredients WHERE active = 1")
    total_ingredients = inv_cursor.fetchone()[0]

    inv_cursor.execute("SELECT COUNT(DISTINCT brand) FROM ingredients")
    total_brands = inv_cursor.fetchone()[0]

    inv_cursor.execute("SELECT COUNT(DISTINCT supplier_name) FROM ingredients")
    total_suppliers_inv = inv_cursor.fetchone()[0]

    inv_db_cursor = inv_db_conn.cursor()
    inv_db_cursor.execute("SELECT COUNT(*) FROM invoices")
    total_invoices = inv_db_cursor.fetchone()[0]

    inv_db_cursor.execute("SELECT COUNT(*) FROM invoice_line_items")
    total_line_items = inv_db_cursor.fetchone()[0]

    inv_db_cursor.execute("SELECT SUM(total_amount) FROM invoices")
    total_value = inv_db_cursor.fetchone()[0]

    inv_cursor.execute("SELECT COUNT(*) FROM products")
    total_products = inv_cursor.fetchone()[0]

    inv_cursor.execute("SELECT COUNT(*) FROM recipes")
    total_recipe_links = inv_cursor.fetchone()[0]

    inv_cursor.execute("SELECT COUNT(*) FROM audit_log")
    total_audit_entries = inv_cursor.fetchone()[0]

    print(f"📦 Total Ingredients: {total_ingredients}")
    print(f"🏷️  Total Brands: {total_brands}")
    print(f"🚚 Total Suppliers: {total_suppliers_inv}")
    print(f"📄 Total Invoices: {total_invoices}")
    print(f"📋 Total Invoice Line Items: {total_line_items}")
    print(f"💰 Total Invoice Value: ${total_value:,.2f}")
    print(f"🍔 Total Products: {total_products}")
    print(f"📝 Total Recipe Links: {total_recipe_links}")
    print(f"📜 Total Audit Log Entries: {total_audit_entries}")

    print()
    print("=" * 60)
    print("✅ TEST DATA GENERATION COMPLETE!")
    print("=" * 60)

    # Close connections
    inv_conn.close()
    inv_db_conn.close()

if __name__ == '__main__':
    main()
