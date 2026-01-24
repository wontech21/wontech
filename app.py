#!/usr/bin/env python3
"""
Firing Up Inventory Dashboard
Flask web application for inventory management
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
import os
import csv
import io
from crud_operations import register_crud_routes
from sales_operations import register_sales_routes
from sales_analytics import register_analytics_routes
from barcode_routes import register_barcode_routes
from inventory_warnings import (
    preview_quantity_change,
    preview_count_changes,
    check_inventory_warnings,
    format_warning_message
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'firing-up-secret-key'

# Database paths
INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

def get_db_connection(db_name):
    """Create database connection"""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

def log_audit(action_type, entity_type, entity_id, entity_reference, details, user='System'):
    """Log an audit entry for tracking all system changes"""
    try:
        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # Get IP address from request if available
        ip_address = request.remote_addr if request else None

        cursor.execute("""
            INSERT INTO audit_log (
                action_type, entity_type, entity_id, entity_reference,
                details, user, ip_address
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (action_type, entity_type, entity_id, entity_reference, details, user, ip_address))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit logging error: {str(e)}")
        # Don't let audit logging failures break the main operation

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/test-scanner')
def test_scanner():
    """Barcode scanner diagnostic page"""
    return render_template('test_scanner.html')

@app.route('/api/inventory/aggregated')
def get_aggregated_inventory():
    """Get aggregated inventory (totals across all brands)"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ingredient_name,
            category,
            unit_of_measure,
            total_quantity,
            avg_unit_cost,
            total_value,
            brand_count,
            brands,
            suppliers
        FROM inventory_aggregated
        ORDER BY category, ingredient_name
    """)

    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(items)

@app.route('/api/inventory/detailed')
def get_detailed_inventory():
    """Get detailed inventory (individual brand/supplier lines)"""
    ingredient = request.args.get('ingredient', 'all')
    supplier = request.args.get('supplier', 'all')
    brand = request.args.get('brand', 'all')
    category = request.args.get('category', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    status = request.args.get('status', 'active')  # active, inactive, or all

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            ingredient_code,
            ingredient_name,
            brand,
            supplier_name,
            category,
            quantity_on_hand,
            unit_of_measure,
            CASE
                WHEN COALESCE(units_per_case, 1) > 0 THEN
                    COALESCE(last_unit_price, unit_cost, 0) / COALESCE(units_per_case, 1)
                ELSE
                    COALESCE(last_unit_price, unit_cost, 0)
            END as unit_cost,
            (quantity_on_hand * CASE
                WHEN COALESCE(units_per_case, 1) > 0 THEN
                    COALESCE(last_unit_price, unit_cost, 0) / COALESCE(units_per_case, 1)
                ELSE
                    COALESCE(last_unit_price, unit_cost, 0)
            END) as total_value,
            storage_location,
            date_received,
            lot_number,
            expiration_date,
            last_unit_price,
            average_unit_price,
            units_per_case,
            active
        FROM ingredients
        WHERE 1=1
    """

    params = []

    # Filter by active status (default to active only)
    if status == 'active':
        query += " AND active = 1"
    elif status == 'inactive':
        query += " AND active = 0"
    # If status == 'all', don't filter by active status

    if ingredient != 'all':
        query += " AND ingredient_name = ?"
        params.append(ingredient)
    if supplier != 'all':
        query += " AND supplier_name = ?"
        params.append(supplier)
    if brand != 'all':
        query += " AND brand = ?"
        params.append(brand)
    if category != 'all':
        query += " AND category = ?"
        params.append(category)
    if date_from:
        query += " AND date_received >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date_received <= ?"
        params.append(date_to)

    query += " ORDER BY ingredient_name, brand"

    cursor.execute(query, params)
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(items)

@app.route('/api/inventory/consolidated')
def get_consolidated_inventory():
    """
    Get consolidated inventory grouped by ingredient_name.
    Shows one row per ingredient with all brand/supplier variants.
    Aggregates quantities and provides variant details for dropdown selection.
    """
    category = request.args.get('category', 'all')
    status = request.args.get('status', 'active')
    search = request.args.get('search', '')

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Build WHERE clause
    where_clauses = []
    params = []

    if status == 'active':
        where_clauses.append("active = 1")
    elif status == 'inactive':
        where_clauses.append("active = 0")

    if category != 'all':
        where_clauses.append("category = ?")
        params.append(category)

    if search:
        where_clauses.append("(ingredient_name LIKE ? OR ingredient_code LIKE ?)")
        params.append(f'%{search}%')
        params.append(f'%{search}%')

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get all ingredients with calculated unit costs
    query = f"""
        SELECT
            id,
            ingredient_code,
            ingredient_name,
            brand,
            supplier_name,
            category,
            quantity_on_hand,
            unit_of_measure,
            CASE
                WHEN COALESCE(units_per_case, 1) > 0 THEN
                    COALESCE(last_unit_price, unit_cost, 0) / COALESCE(units_per_case, 1)
                ELSE
                    COALESCE(last_unit_price, unit_cost, 0)
            END as unit_cost,
            (quantity_on_hand * CASE
                WHEN COALESCE(units_per_case, 1) > 0 THEN
                    COALESCE(last_unit_price, unit_cost, 0) / COALESCE(units_per_case, 1)
                ELSE
                    COALESCE(last_unit_price, unit_cost, 0)
            END) as total_value,
            storage_location,
            date_received,
            lot_number,
            expiration_date,
            last_unit_price,
            average_unit_price,
            units_per_case
        FROM ingredients
        WHERE {where_sql}
        ORDER BY ingredient_name, brand, supplier_name
    """

    cursor.execute(query, params)
    all_items = [dict(row) for row in cursor.fetchall()]

    # Group by ingredient_name
    consolidated = {}

    for item in all_items:
        ing_name = item['ingredient_name']

        if ing_name not in consolidated:
            consolidated[ing_name] = {
                'ingredient_name': ing_name,
                'category': item['category'],
                'unit_of_measure': item['unit_of_measure'],
                'variants': [],
                'total_quantity': 0,
                'total_value': 0,
                'variant_count': 0,
                'brands': set(),
                'suppliers': set()
            }

        # Add to totals
        consolidated[ing_name]['total_quantity'] += item['quantity_on_hand']
        consolidated[ing_name]['total_value'] += item['total_value']
        consolidated[ing_name]['variant_count'] += 1
        consolidated[ing_name]['brands'].add(item['brand'] or 'Unknown')
        consolidated[ing_name]['suppliers'].add(item['supplier_name'] or 'Unknown')

        # Add variant details
        consolidated[ing_name]['variants'].append({
            'id': item['id'],
            'ingredient_code': item['ingredient_code'],
            'brand': item['brand'],
            'supplier_name': item['supplier_name'],
            'quantity_on_hand': item['quantity_on_hand'],
            'unit_cost': item['unit_cost'],
            'total_value': item['total_value'],
            'storage_location': item['storage_location'],
            'date_received': item['date_received'],
            'lot_number': item['lot_number'],
            'expiration_date': item['expiration_date'],
            'last_unit_price': item['last_unit_price'],
            'average_unit_price': item['average_unit_price'],
            'units_per_case': item['units_per_case']
        })

    # Convert to list and add calculated fields
    result = []
    for ing_name, data in consolidated.items():
        data['brands'] = sorted(list(data['brands']))
        data['suppliers'] = sorted(list(data['suppliers']))
        data['avg_unit_cost'] = data['total_value'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        result.append(data)

    # Sort by ingredient name
    result.sort(key=lambda x: x['ingredient_name'])

    conn.close()
    return jsonify(result)

@app.route('/api/filters/suppliers')
def get_suppliers():
    """Get list of all suppliers from suppliers table"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT supplier_name FROM suppliers ORDER BY supplier_name")
    suppliers = [row['supplier_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(suppliers)

@app.route('/api/filters/brands')
def get_brands():
    """Get list of all brands from brands table"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM brands ORDER BY brand_name")
    brands = [row['brand_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(brands)

@app.route('/api/filters/categories')
def get_categories():
    """Get list of all categories from the categories table"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT category_name FROM categories ORDER BY category_name")
    categories = [row['category_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route('/api/filters/ingredients')
def get_ingredients():
    """Get list of all unique ingredient names"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ingredient_name FROM ingredients ORDER BY ingredient_name")
    ingredients = [row['ingredient_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(ingredients)

@app.route('/api/inventory/summary')
def get_inventory_summary():
    """Get inventory summary statistics"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Total inventory value (using average_unit_price for consistency with analytics)
    cursor.execute("""
        SELECT SUM(quantity_on_hand * average_unit_price) as total
        FROM ingredients
        WHERE active = 1
    """)
    total_value = cursor.fetchone()['total']

    # Total items
    cursor.execute("SELECT COUNT(*) as count FROM ingredients")
    total_items = cursor.fetchone()['count']

    # Total unique ingredients
    cursor.execute("SELECT COUNT(DISTINCT ingredient_name) as count FROM ingredients")
    unique_ingredients = cursor.fetchone()['count']

    # By category (using average_unit_price for consistency)
    cursor.execute("""
        SELECT category,
               COUNT(*) as item_count,
               SUM(quantity_on_hand * average_unit_price) as category_value
        FROM ingredients
        WHERE active = 1
        GROUP BY category
        ORDER BY category_value DESC
    """)
    by_category = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'total_value': round(total_value, 2) if total_value else 0,
        'total_items': total_items,
        'unique_ingredients': unique_ingredients,
        'by_category': by_category
    })

@app.route('/api/invoices/unreconciled')
def get_unreconciled_invoices():
    """Get list of unreconciled invoices"""
    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM unreconciled_invoices")
    invoices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(invoices)

@app.route('/api/invoices/recent')
def get_recent_invoices():
    """Get recent invoices with optional date filtering"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    query = """
        SELECT invoice_number, supplier_name, invoice_date, received_date,
               total_amount, payment_status, reconciled
        FROM invoices
        WHERE 1=1
    """
    params = []

    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)

    query += " ORDER BY invoice_date DESC LIMIT 100"

    cursor.execute(query, params)
    invoices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(invoices)

@app.route('/api/products/all')
def get_products():
    """Get all products"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY category, product_name")
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(products)

@app.route('/api/products/costs')
def get_product_costs():
    """Get product costs and margins - includes products without recipes"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Helper function to calculate product ingredient cost recursively
    def calculate_cost(product_id, visited=None):
        if visited is None:
            visited = set()
        if product_id in visited:
            return 0  # Prevent infinite recursion
        visited.add(product_id)

        # Use a separate cursor for nested queries to avoid cursor conflicts
        cost_cursor = conn.cursor()
        cost_cursor.execute("""
            SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
            FROM recipes r
            WHERE r.product_id = ?
        """, (product_id,))

        # Fetch all rows first before processing to avoid cursor conflicts
        recipe_items = cost_cursor.fetchall()

        total_cost = 0
        for row in recipe_items:
            source_type = row['source_type']
            source_id = row['source_id']
            quantity = row['quantity_needed']

            if source_type == 'ingredient':
                ing_cursor = conn.cursor()
                ing_cursor.execute("""
                    SELECT COALESCE(unit_cost, 0) as unit_cost
                    FROM ingredients WHERE id = ?
                """, (source_id,))
                ing_result = ing_cursor.fetchone()
                if ing_result:
                    total_cost += quantity * ing_result['unit_cost']
            elif source_type == 'product':
                # Recursively calculate cost for nested product
                nested_cost = calculate_cost(source_id, visited)
                total_cost += quantity * nested_cost

        return total_cost

    # Get all products
    cursor.execute("""
        SELECT id, product_name, selling_price
        FROM products
    """)

    products = []
    for row in cursor.fetchall():
        product_id = row['id']
        product_name = row['product_name']
        selling_price = row['selling_price']

        # Calculate ingredient cost using recursive function
        ingredient_cost = calculate_cost(product_id)
        gross_profit = selling_price - ingredient_cost
        margin_pct = round((gross_profit / selling_price * 100) if selling_price > 0 else 0, 1)

        products.append({
            'product_id': product_id,
            'product_name': product_name,
            'selling_price': selling_price,
            'ingredient_cost': ingredient_cost,
            'gross_profit': gross_profit,
            'margin_pct': margin_pct
        })

    # Sort by gross profit descending
    products.sort(key=lambda x: x['gross_profit'], reverse=True)

    conn.close()
    return jsonify(products)

@app.route('/api/recipes/all')
def get_all_recipes():
    """Get all recipes with ingredients including composite breakdown"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    # Modified to handle both ingredients and products
    cursor.execute("""
        SELECT
            p.product_name,
            p.category,
            r.source_type,
            r.ingredient_id as source_id,
            CASE
                WHEN r.source_type = 'ingredient' THEN i.ingredient_name
                WHEN r.source_type = 'product' THEN prod.product_name
            END as ingredient_name,
            r.quantity_needed,
            r.unit_of_measure,
            CASE
                WHEN r.source_type = 'ingredient' THEN COALESCE(i.unit_cost, 0)
                WHEN r.source_type = 'product' THEN 0
            END as unit_cost,
            CASE
                WHEN r.source_type = 'ingredient' THEN (r.quantity_needed * COALESCE(i.unit_cost, 0))
                WHEN r.source_type = 'product' THEN 0
            END as line_cost,
            r.notes,
            CASE
                WHEN r.source_type = 'ingredient' THEN COALESCE(i.is_composite, 0)
                ELSE 0
            END as is_composite,
            CASE
                WHEN r.source_type = 'product' THEN 1
                ELSE 0
            END as is_product
        FROM recipes r
        JOIN products p ON r.product_id = p.id
        LEFT JOIN ingredients i ON r.ingredient_id = i.id AND r.source_type = 'ingredient'
        LEFT JOIN products prod ON r.ingredient_id = prod.id AND r.source_type = 'product'
        ORDER BY p.product_name, r.source_type, ingredient_name
    """)
    recipes = [dict(row) for row in cursor.fetchall()]

    # For each item, handle products and composites
    for recipe in recipes:
        if recipe.get('is_product'):
            # Calculate product cost using the same logic as before
            product_id = recipe['source_id']

            def calculate_cost(pid, visited=None):
                if visited is None:
                    visited = set()
                if pid in visited:
                    return 0
                visited.add(pid)

                cursor.execute("SELECT source_type, ingredient_id as source_id, quantity_needed FROM recipes WHERE product_id = ?", (pid,))
                total = 0
                for row in cursor.fetchall():
                    if row['source_type'] == 'ingredient':
                        cursor.execute("SELECT COALESCE(unit_cost, 0) as unit_cost FROM ingredients WHERE id = ?", (row['source_id'],))
                        result = cursor.fetchone()
                        if result:
                            total += row['quantity_needed'] * result['unit_cost']
                    elif row['source_type'] == 'product':
                        total += row['quantity_needed'] * calculate_cost(row['source_id'], visited.copy())
                return total

            product_cost = calculate_cost(product_id)
            recipe['unit_cost'] = product_cost
            recipe['line_cost'] = recipe['quantity_needed'] * product_cost

        elif recipe.get('is_composite'):
            cursor.execute("""
                SELECT
                    bi.ingredient_name,
                    ir.quantity_needed,
                    ir.unit_of_measure,
                    bi.unit_cost,
                    (ir.quantity_needed * bi.unit_cost) as line_cost,
                    ir.notes
                FROM ingredient_recipes ir
                JOIN ingredients bi ON ir.base_ingredient_id = bi.id
                WHERE ir.composite_ingredient_id = ?
                ORDER BY bi.ingredient_name
            """, (recipe['source_id'],))
            recipe['sub_recipe'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(recipes)

@app.route('/api/recipes/by-product/<product_name>')
def get_recipe_by_product(product_name):
    """Get recipe for a specific product with composite ingredient breakdown"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    # Modified query to handle both ingredients and products
    cursor.execute("""
        SELECT
            r.source_type,
            r.ingredient_id as source_id,
            CASE
                WHEN r.source_type = 'ingredient' THEN i.ingredient_name
                WHEN r.source_type = 'product' THEN prod.product_name
            END as ingredient_name,
            r.quantity_needed,
            r.unit_of_measure,
            CASE
                WHEN r.source_type = 'ingredient' THEN COALESCE(i.unit_cost, 0)
                WHEN r.source_type = 'product' THEN 0
            END as unit_cost,
            CASE
                WHEN r.source_type = 'ingredient' THEN (r.quantity_needed * COALESCE(i.unit_cost, 0))
                WHEN r.source_type = 'product' THEN 0
            END as line_cost,
            r.notes,
            CASE
                WHEN r.source_type = 'ingredient' THEN COALESCE(i.is_composite, 0)
                WHEN r.source_type = 'product' THEN 0
            END as is_composite,
            CASE
                WHEN r.source_type = 'product' THEN 1
                ELSE 0
            END as is_product
        FROM recipes r
        JOIN products p ON r.product_id = p.id
        LEFT JOIN ingredients i ON r.ingredient_id = i.id AND r.source_type = 'ingredient'
        LEFT JOIN products prod ON r.ingredient_id = prod.id AND r.source_type = 'product'
        WHERE p.product_name = ?
        ORDER BY r.source_type, ingredient_name
    """, (product_name,))
    recipe = [dict(row) for row in cursor.fetchall()]

    # For each item, calculate costs and fetch sub-recipes
    for item in recipe:
        if item.get('is_product'):
            # For products, calculate ingredient cost recursively
            product_id = item['source_id']

            def calculate_cost(pid, visited=None):
                if visited is None:
                    visited = set()
                if pid in visited:
                    return 0
                visited.add(pid)

                cursor.execute("""
                    SELECT source_type, ingredient_id as source_id, quantity_needed
                    FROM recipes WHERE product_id = ?
                """, (pid,))

                total = 0
                for row in cursor.fetchall():
                    if row['source_type'] == 'ingredient':
                        cursor.execute("""
                            SELECT COALESCE(unit_cost, 0) as unit_cost
                            FROM ingredients WHERE id = ?
                        """, (row['source_id'],))
                        result = cursor.fetchone()
                        if result:
                            total += row['quantity_needed'] * result['unit_cost']
                    elif row['source_type'] == 'product':
                        nested_cost = calculate_cost(row['source_id'], visited.copy())
                        total += row['quantity_needed'] * nested_cost
                return total

            product_unit_cost = calculate_cost(product_id)
            item['unit_cost'] = product_unit_cost
            item['line_cost'] = item['quantity_needed'] * product_unit_cost

        elif item.get('is_composite'):
            # For composite ingredients, fetch sub-recipe
            cursor.execute("""
                SELECT
                    bi.ingredient_name,
                    ir.quantity_needed,
                    ir.unit_of_measure,
                    bi.unit_cost,
                    (ir.quantity_needed * bi.unit_cost) as line_cost,
                    ir.notes
                FROM ingredient_recipes ir
                JOIN ingredients bi ON ir.base_ingredient_id = bi.id
                WHERE ir.composite_ingredient_id = ?
                ORDER BY bi.ingredient_name
            """, (item['source_id'],))
            item['sub_recipe'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(recipe)

@app.route('/api/ingredients/composite/<int:ingredient_id>')
def get_composite_ingredient_recipe(ingredient_id):
    """Get recipe for a composite ingredient"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            bi.ingredient_name,
            ir.quantity_needed,
            ir.unit_of_measure,
            bi.unit_cost,
            (ir.quantity_needed * bi.unit_cost) as line_cost,
            ir.notes
        FROM ingredient_recipes ir
        JOIN ingredients bi ON ir.base_ingredient_id = bi.id
        WHERE ir.composite_ingredient_id = ?
        ORDER BY bi.ingredient_name
    """, (ingredient_id,))
    recipe = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(recipe)

@app.route('/api/invoices/<invoice_number>')
def get_invoice_details(invoice_number):
    """Get invoice details with line items"""
    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    # Get invoice header
    cursor.execute("""
        SELECT *
        FROM invoices
        WHERE invoice_number = ?
    """, (invoice_number,))
    invoice = dict(cursor.fetchone())

    # Get line items
    cursor.execute("""
        SELECT *
        FROM invoice_line_items
        WHERE invoice_id = ?
        ORDER BY ingredient_code
    """, (invoice['id'],))
    line_items = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'invoice': invoice,
        'line_items': line_items
    })

@app.route('/api/inventory/category-preview/<category>')
def get_category_preview(category):
    """Get 5 item preview for a category"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            ingredient_name,
            brand,
            quantity_on_hand,
            unit_of_measure,
            CASE
                WHEN COALESCE(units_per_case, 1) > 0 THEN
                    COALESCE(last_unit_price, unit_cost, 0) / COALESCE(units_per_case, 1)
                ELSE
                    COALESCE(last_unit_price, unit_cost, 0)
            END as unit_cost
        FROM ingredients
        WHERE category = ?
        ORDER BY (quantity_on_hand *
            CASE
                WHEN COALESCE(units_per_case, 1) > 0 THEN
                    COALESCE(last_unit_price, unit_cost, 0) / COALESCE(units_per_case, 1)
                ELSE
                    COALESCE(last_unit_price, unit_cost, 0)
            END
        ) DESC
        LIMIT 5
    """, (category,))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(items)

@app.route('/api/inventory/item/<int:item_id>', methods=['GET'])
def get_inventory_item(item_id):
    """Get a single inventory item by ID"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingredients WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if item:
        return jsonify(dict(item))
    return jsonify({'error': 'Item not found'}), 404

@app.route('/api/inventory/item/<int:item_id>', methods=['PUT'])
def update_inventory_item(item_id):
    """Update an inventory item"""
    data = request.json
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE ingredients
            SET ingredient_code = ?,
                ingredient_name = ?,
                brand = ?,
                supplier_name = ?,
                category = ?,
                quantity_on_hand = ?,
                unit_of_measure = ?,
                last_unit_price = ?,
                average_unit_price = ?,
                storage_location = ?,
                date_received = ?,
                lot_number = ?,
                expiration_date = ?
            WHERE id = ?
        """, (
            data.get('ingredient_code'),
            data.get('ingredient_name'),
            data.get('brand'),
            data.get('supplier_name'),
            data.get('category'),
            data.get('quantity_on_hand'),
            data.get('unit_of_measure'),
            data.get('last_unit_price'),
            data.get('average_unit_price'),
            data.get('storage_location'),
            data.get('date_received'),
            data.get('lot_number'),
            data.get('expiration_date'),
            item_id
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Item updated successfully'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/item/<int:item_id>/preview-update', methods=['POST'])
def preview_inventory_update(item_id):
    """
    Preview inventory quantity change and show warnings BEFORE applying.
    This is critical for preventing negative inventory.
    """
    data = request.json
    new_quantity = data.get('quantity_on_hand')

    if new_quantity is None:
        return jsonify({'success': False, 'error': 'quantity_on_hand is required'}), 400

    try:
        new_quantity = float(new_quantity)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid quantity value'}), 400

    conn = get_db_connection(INVENTORY_DB)

    try:
        preview = preview_quantity_change(item_id, new_quantity, conn)
        conn.close()

        if not preview['success']:
            return jsonify(preview), 404

        return jsonify({
            'success': True,
            'preview': preview
        })

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/item/<int:item_id>/toggle-active', methods=['PUT'])
def toggle_item_active_status(item_id):
    """Toggle active/inactive status of an inventory item"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # Get current item details
        cursor.execute("""
            SELECT id, ingredient_code, ingredient_name, active
            FROM ingredients
            WHERE id = ?
        """, (item_id,))

        item = cursor.fetchone()
        if not item:
            conn.close()
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        current_status = item['active']
        new_status = 0 if current_status == 1 else 1

        # Update status
        cursor.execute("""
            UPDATE ingredients
            SET active = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, item_id))

        conn.commit()
        conn.close()

        # Log audit entry
        action_type = 'ITEM_DEACTIVATED' if new_status == 0 else 'ITEM_REACTIVATED'
        status_text = 'deactivated' if new_status == 0 else 'reactivated'

        log_audit(
            action_type=action_type,
            entity_type='item',
            entity_id=item_id,
            entity_reference=f"{item['ingredient_code']} - {item['ingredient_name']}",
            details=f"Item {status_text}"
        )

        return jsonify({
            'success': True,
            'message': f'Item {status_text} successfully',
            'active': new_status
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/bulk-update-brand', methods=['POST'])
def bulk_update_brand():
    """Update brand name across all databases"""
    data = request.json
    old_brand = data.get('old_brand')
    new_brand = data.get('new_brand')

    # Update inventory database
    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    # Update invoices database
    conn_inv_db = get_db_connection(INVOICES_DB)
    cursor_inv_db = conn_inv_db.cursor()

    try:
        # Update ingredients table
        cursor_inv.execute("UPDATE ingredients SET brand = ? WHERE brand = ?", (new_brand, old_brand))
        ingredients_affected = cursor_inv.rowcount

        # Update invoice_line_items table
        cursor_inv_db.execute("UPDATE invoice_line_items SET brand = ? WHERE brand = ?", (new_brand, old_brand))
        invoice_items_affected = cursor_inv_db.rowcount

        # Commit both databases
        conn_inv.commit()
        conn_inv_db.commit()

        # Log audit entry
        log_audit(
            action_type='BRAND_UPDATED',
            entity_type='brand',
            entity_id=0,
            entity_reference=f"{old_brand} → {new_brand}",
            details=f"Brand renamed. {ingredients_affected} inventory items and {invoice_items_affected} invoice line items updated"
        )

        conn_inv.close()
        conn_inv_db.close()

        message = f'Updated {ingredients_affected} items, {invoice_items_affected} invoice line item(s)'

        return jsonify({'success': True, 'message': message, 'count': ingredients_affected})
    except Exception as e:
        conn_inv.rollback()
        conn_inv_db.rollback()
        conn_inv.close()
        conn_inv_db.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/update-category', methods=['POST'])
def update_category():
    """Update category for one or more items"""
    data = request.json
    item_ids = data.get('item_ids', [])
    new_category = data.get('new_category')

    if not item_ids or not new_category:
        return jsonify({'success': False, 'error': 'Missing item_ids or new_category'}), 400

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # First, ensure the category exists in the categories table
        cursor.execute("""
            INSERT OR IGNORE INTO categories (category_name)
            VALUES (?)
        """, (new_category,))

        # Build placeholders for the IN clause
        placeholders = ','.join('?' * len(item_ids))

        # Update the items
        cursor.execute(f"""
            UPDATE ingredients
            SET category = ?
            WHERE id IN ({placeholders})
        """, [new_category] + item_ids)

        updated_count = cursor.rowcount
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Updated category for {updated_count} item(s)',
            'count': updated_count
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/all', methods=['GET'])
def get_all_categories():
    """Get all categories with usage counts"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            c.id,
            c.category_name,
            c.created_at,
            COUNT(i.id) as item_count
        FROM categories c
        LEFT JOIN ingredients i ON c.category_name = i.category
        GROUP BY c.id, c.category_name, c.created_at
        ORDER BY c.category_name
    """)
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route('/api/categories/create', methods=['POST'])
def create_category():
    """Create a new category"""
    data = request.json
    category_name = data.get('category_name')

    if not category_name or not category_name.strip():
        return jsonify({'success': False, 'error': 'Category name is required'}), 400

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # Insert the new category
        cursor.execute("""
            INSERT INTO categories (category_name)
            VALUES (?)
        """, (category_name.strip(),))

        category_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Category "{category_name}" created successfully',
            'category_id': category_id
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': f'Category "{category_name}" already exists'}), 400
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/update/<int:category_id>', methods=['PUT'])
def update_category_name(category_id):
    """Update a category name and cascade to all items using it"""
    data = request.json
    new_name = data.get('category_name')

    if not new_name or not new_name.strip():
        return jsonify({'success': False, 'error': 'Category name is required'}), 400

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # Get old category name
        cursor.execute("SELECT category_name FROM categories WHERE id = ?", (category_id,))
        category = cursor.fetchone()

        if not category:
            conn.close()
            return jsonify({'success': False, 'error': 'Category not found'}), 404

        old_name = category['category_name']

        # Prevent renaming "Uncategorized"
        if old_name == 'Uncategorized':
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Cannot rename the "Uncategorized" category'
            }), 400

        # Check if new name already exists
        cursor.execute("SELECT id FROM categories WHERE category_name = ? AND id != ?", (new_name.strip(), category_id))
        if cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Category "{new_name}" already exists'
            }), 400

        # Update the category name in categories table
        cursor.execute("UPDATE categories SET category_name = ? WHERE id = ?", (new_name.strip(), category_id))

        # CASCADE: Update all ingredients using this category
        cursor.execute("UPDATE ingredients SET category = ? WHERE category = ?", (new_name.strip(), old_name))
        items_updated = cursor.rowcount

        conn.commit()
        conn.close()

        message = f'Category renamed from "{old_name}" to "{new_name}"'
        if items_updated > 0:
            message += f' ({items_updated} item(s) updated)'

        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/delete/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Delete a category"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # Get category name
        cursor.execute("SELECT category_name FROM categories WHERE id = ?", (category_id,))
        category = cursor.fetchone()

        if not category:
            conn.close()
            return jsonify({'success': False, 'error': 'Category not found'}), 404

        category_name = category['category_name']

        # Check if category is in use
        cursor.execute("SELECT COUNT(*) as count FROM ingredients WHERE category = ?", (category_name,))
        count = cursor.fetchone()['count']

        if count > 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Cannot delete category - it is used by {count} item(s). Please reassign those items first.'
            }), 400

        # Prevent deletion of "Uncategorized"
        if category_name == 'Uncategorized':
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Cannot delete the "Uncategorized" category'
            }), 400

        # Delete the category
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Category "{category_name}" deleted successfully'
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/bulk-update-supplier', methods=['POST'])
def bulk_update_supplier():
    """Update supplier name across all databases"""
    data = request.json
    old_supplier = data.get('old_supplier')
    new_supplier = data.get('new_supplier')

    # Update inventory database
    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    # Update invoices database
    conn_inv_db = get_db_connection(INVOICES_DB)
    cursor_inv_db = conn_inv_db.cursor()

    try:
        # Update ingredients table
        cursor_inv.execute("UPDATE ingredients SET supplier_name = ? WHERE supplier_name = ?", (new_supplier, old_supplier))
        ingredients_affected = cursor_inv.rowcount

        # Update suppliers master table
        cursor_inv.execute("UPDATE suppliers SET supplier_name = ? WHERE supplier_name = ?", (new_supplier, old_supplier))
        suppliers_affected = cursor_inv.rowcount

        # Update invoices table
        cursor_inv_db.execute("UPDATE invoices SET supplier_name = ? WHERE supplier_name = ?", (new_supplier, old_supplier))
        invoices_affected = cursor_inv_db.rowcount

        # Commit both databases
        conn_inv.commit()
        conn_inv_db.commit()

        # Log audit entry
        log_audit(
            action_type='SUPPLIER_UPDATED',
            entity_type='supplier',
            entity_id=0,
            entity_reference=f"{old_supplier} → {new_supplier}",
            details=f"Supplier renamed. {ingredients_affected} inventory items, {suppliers_affected} supplier records, and {invoices_affected} invoices updated"
        )

        conn_inv.close()
        conn_inv_db.close()

        total_updates = ingredients_affected + suppliers_affected + invoices_affected
        message = f'Updated {ingredients_affected} items, {suppliers_affected} supplier record(s), {invoices_affected} invoice(s)'

        return jsonify({'success': True, 'message': message, 'count': ingredients_affected})
    except Exception as e:
        conn_inv.rollback()
        conn_inv_db.rollback()
        conn_inv.close()
        conn_inv_db.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/invoices/create', methods=['POST'])
def create_invoice():
    """Create a new invoice with line items and add to inventory"""
    data = request.json

    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    conn_inventory = get_db_connection(INVENTORY_DB)
    cursor_inventory = conn_inventory.cursor()

    try:
        # Insert invoice header
        cursor_invoices.execute("""
            INSERT INTO invoices (
                invoice_number, supplier_name, invoice_date, received_date,
                total_amount, payment_status, reconciled, reconciled_date, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, 'YES', CURRENT_TIMESTAMP, ?)
        """, (
            data['invoice_number'],
            data['supplier_name'],
            data['invoice_date'],
            data['received_date'],
            data['total_amount'],
            data['payment_status'],
            data.get('notes')
        ))

        invoice_id = cursor_invoices.lastrowid

        # Insert line items and add to inventory
        for item in data['line_items']:
            # Insert into invoice line items
            cursor_invoices.execute("""
                INSERT INTO invoice_line_items (
                    invoice_id, ingredient_code, ingredient_name, brand, size,
                    quantity_ordered, quantity_received_received, unit_of_measure,
                    unit_price, total_price, lot_number, reconciled_to_inventory
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'YES')
            """, (
                invoice_id,
                item['ingredient_code'],
                item['ingredient_name'],
                item.get('brand'),
                item.get('size'),
                item['quantity_ordered'],
                item['quantity_received'],
                item['unit_of_measure'],
                item['unit_price'],
                item['total_price'],
                item.get('lot_number')
            ))

            # Add to inventory - check if ingredient already exists (by code only)
            cursor_inventory.execute("""
                SELECT id, quantity_on_hand, unit_cost FROM ingredients
                WHERE ingredient_code = ?
                ORDER BY date_received DESC
                LIMIT 1
            """, (item['ingredient_code'],))

            existing = cursor_inventory.fetchone()

            # Get the inventory quantity (total units), default to quantity_received if not provided
            inventory_qty = item.get('inventory_quantity', item['quantity_received'])
            units_per_case = item.get('units_per_case', 1)

            # Calculate correct unit_cost: price per individual unit, not per case
            # unit_price from invoice is price per case/bag, so divide by units_per_case
            unit_cost = item['unit_price'] / units_per_case if units_per_case > 0 else item['unit_price']

            if existing:
                # Update existing inventory item - add to quantity, update lot/date to most recent
                new_quantity = existing['quantity_on_hand'] + inventory_qty
                cursor_inventory.execute("""
                    UPDATE ingredients
                    SET quantity_on_hand = ?,
                        units_per_case = ?,
                        unit_cost = ?,
                        lot_number = ?,
                        date_received = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_quantity, units_per_case, unit_cost, item.get('lot_number'), data['received_date'], existing['id']))
            else:
                # Insert new inventory item - use inventory_quantity (total expanded quantity)
                cursor_inventory.execute("""
                    INSERT INTO ingredients (
                        ingredient_code, ingredient_name, brand, supplier_name,
                        category, quantity_on_hand, unit_of_measure, unit_cost,
                        date_received, lot_number, storage_location, units_per_case
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item['ingredient_code'],
                    item['ingredient_name'],
                    item.get('brand'),
                    data['supplier_name'],
                    item.get('category', 'Uncategorized'),  # Use provided category or default
                    inventory_qty,  # Total quantity (e.g., 60 rolls, not 10 bags)
                    item['unit_of_measure'],
                    unit_cost,  # Cost per individual unit
                    data['received_date'],
                    item.get('lot_number'),
                    None,  # Storage location to be set later
                    units_per_case
                ))

                # Log item creation
                new_item_id = cursor_inventory.lastrowid
                log_audit(
                    action_type='ITEM_CREATED',
                    entity_type='item',
                    entity_id=new_item_id,
                    entity_reference=f"{item['ingredient_code']} - {item['ingredient_name']}",
                    details=f"New item added via invoice. Qty: {inventory_qty} {item['unit_of_measure']}, Supplier: {data['supplier_name']}"
                )

            # Update price tracking after adding to inventory
            update_ingredient_prices(item['ingredient_code'], cursor_invoices, cursor_inventory)

        conn_invoices.commit()
        conn_inventory.commit()
        conn_invoices.close()
        conn_inventory.close()

        # Log audit entry
        log_audit(
            action_type='INVOICE_CREATED',
            entity_type='invoice',
            entity_id=invoice_id,
            entity_reference=data['invoice_number'],
            details=f"Supplier: {data['supplier_name']}, Amount: ${data['total_amount']:.2f}, Items: {len(data['line_items'])}"
        )

        return jsonify({
            'success': True,
            'message': f'Invoice {data["invoice_number"]} created successfully and added to inventory',
            'invoice_id': invoice_id
        })
    except Exception as e:
        conn_invoices.rollback()
        conn_inventory.rollback()
        conn_invoices.close()
        conn_inventory.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/invoices/import', methods=['POST'])
def import_invoice():
    """Import invoice from CSV or Excel file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Get invoice metadata
    invoice_number = request.form.get('invoice_number')
    supplier_name = request.form.get('supplier_name')
    invoice_date = request.form.get('invoice_date')
    received_date = request.form.get('received_date')
    payment_status = request.form.get('payment_status')

    # Get inventory database to look up ingredient details
    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    # Parse file based on extension
    filename = file.filename.lower()
    line_items = []

    try:
        if filename.endswith('.csv'):
            # Parse CSV
            file_content = file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(file_content))
            rows = list(csv_reader)

        elif filename.endswith(('.xlsx', '.xls')):
            # Parse Excel - try with openpyxl
            try:
                import openpyxl
                workbook = openpyxl.load_workbook(file)
                sheet = workbook.active
                headers = [cell.value for cell in sheet[1]]
                rows = []
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    row_dict = {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
                    rows.append(row_dict)
            except ImportError:
                return jsonify({'success': False, 'error': 'openpyxl not installed. Please install it to import Excel files.'}), 500

        else:
            return jsonify({'success': False, 'error': 'Unsupported file format. Use CSV or Excel files.'}), 400

        # Process rows and build line items
        for row in rows:
            # Try to get ingredient code from various column names
            ingredient_code = row.get('ingredient_code', row.get('code', '')).strip()

            # Try to get ingredient name from various column names
            ingredient_name = row.get('ingredient_name', row.get('item', row.get('name', ''))).strip()

            # Skip if we have neither code nor name
            if not ingredient_code and not ingredient_name:
                continue

            # Try to get quantity received (cases/bags/boxes ordered)
            qty_received = float(row.get('quantity_received', row.get('received', row.get('qty_received', 0))) or 0)

            # Try to get total quantity (actual inventory count)
            # This is the expanded quantity (e.g., 10 bags x 6 rolls = 60 rolls)
            total_quantity = row.get('total_quantity', row.get('total_qty', row.get('quantity', '')))

            if total_quantity:
                # Use total_quantity as the inventory amount
                inventory_quantity = float(total_quantity or 0)
            else:
                # Fall back to received quantity if no total_quantity column
                inventory_quantity = qty_received

            if inventory_quantity == 0:
                continue  # Skip items with no quantity

            # Try to get unit of measure
            unit_of_measure = row.get('unit_of_measure', row.get('unit', row.get('uom', 'ea'))).strip()

            # If we have an ingredient code, try to look it up
            ingredient = None
            if ingredient_code:
                cursor_inv.execute("""
                    SELECT ingredient_name, unit_of_measure, brand
                    FROM ingredients
                    WHERE ingredient_code = ?
                    LIMIT 1
                """, (ingredient_code,))
                ingredient = cursor_inv.fetchone()

            # If ingredient was found, use its data
            if ingredient:
                ingredient_name = ingredient['ingredient_name']
                unit_of_measure = ingredient['unit_of_measure']
                brand = row.get('brand', ingredient['brand'] or '')
                category = ingredient.get('category', 'Uncategorized')
            else:
                # New ingredient - generate code if missing
                if not ingredient_code:
                    # Generate a simple code from the name
                    ingredient_code = ingredient_name[:3].upper() + '-' + str(hash(ingredient_name))[-6:]
                brand = row.get('brand', '')
                # Try to get category from CSV, default to Uncategorized
                category = row.get('category', 'Uncategorized')

            # Get quantity ordered (default to received if not specified)
            qty_ordered = float(row.get('quantity_ordered', row.get('ordered', row.get('qty_ordered', qty_received))) or qty_received)

            # Calculate units per case if we have both total_quantity and qty_received
            units_per_case = 1
            if total_quantity and qty_received > 0:
                units_per_case = inventory_quantity / qty_received
            else:
                # Try to read units_per_case from CSV if provided, or use size field
                units_per_case = float(row.get('units_per_case', row.get('units/case', row.get('size', 1))) or 1)

            # SMART PRICE CALCULATION:
            # If CSV has total_price, use it to calculate correct unit_price per case
            # Otherwise, assume unit_price from CSV is already per case
            total_price_from_csv = row.get('total_price', row.get('total', ''))
            if total_price_from_csv:
                # Parse total price from CSV
                total_price = float(str(total_price_from_csv).replace('$', '').replace(',', ''))
                # Calculate correct unit_price per case/bag
                unit_price = total_price / qty_received if qty_received > 0 else 0
            else:
                # No total_price in CSV, assume unit_price is per case
                unit_price = float(str(row.get('unit_price', row.get('price', 0)) or '0').replace('$', '').replace(',', ''))
                total_price = qty_received * unit_price

            line_items.append({
                'ingredient_code': ingredient_code,
                'ingredient_name': ingredient_name,
                'category': category,
                'brand': brand,
                'size': row.get('size', ''),
                'quantity_ordered': qty_ordered,
                'quantity_received': qty_received,
                'inventory_quantity': inventory_quantity,  # Total quantity for inventory
                'units_per_case': units_per_case,  # Units per case/bag/box
                'unit_of_measure': unit_of_measure,
                'unit_price': unit_price,  # Price per case/bag (calculated intelligently)
                'total_price': total_price,
                'lot_number': row.get('lot_number', row.get('lot', ''))
            })

        conn_inv.close()

        if not line_items:
            return jsonify({'success': False, 'error': 'No valid line items found in file'}), 400

        # Calculate total amount
        total_amount = sum(item['total_price'] for item in line_items)

        # Insert into databases
        conn_invoices = get_db_connection(INVOICES_DB)
        cursor_invoices = conn_invoices.cursor()

        conn_inventory = get_db_connection(INVENTORY_DB)
        cursor_inventory = conn_inventory.cursor()

        cursor_invoices.execute("""
            INSERT INTO invoices (
                invoice_number, supplier_name, invoice_date, received_date,
                total_amount, payment_status, reconciled, reconciled_date
            )
            VALUES (?, ?, ?, ?, ?, ?, 'YES', CURRENT_TIMESTAMP)
        """, (invoice_number, supplier_name, invoice_date, received_date, total_amount, payment_status))

        invoice_id = cursor_invoices.lastrowid

        # Insert line items and add to inventory
        for item in line_items:
            # Insert into invoice line items
            cursor_invoices.execute("""
                INSERT INTO invoice_line_items (
                    invoice_id, ingredient_code, ingredient_name, brand, size,
                    quantity_ordered, quantity_received_received, unit_of_measure,
                    unit_price, total_price, lot_number, reconciled_to_inventory
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'YES')
            """, (
                invoice_id,
                item['ingredient_code'],
                item['ingredient_name'],
                item['brand'],
                item['size'],
                item['quantity_ordered'],
                item['quantity_received'],
                item['unit_of_measure'],
                item['unit_price'],
                item['total_price'],
                item['lot_number']
            ))

            # Add to inventory - check if ingredient already exists (by code only)
            cursor_inventory.execute("""
                SELECT id, quantity_on_hand, unit_cost FROM ingredients
                WHERE ingredient_code = ?
                ORDER BY date_received DESC
                LIMIT 1
            """, (item['ingredient_code'],))

            existing = cursor_inventory.fetchone()

            units_per_case = item.get('units_per_case', 1)

            # Calculate correct unit_cost: price per individual unit, not per case
            # unit_price from invoice is price per case/bag, so divide by units_per_case
            unit_cost = item['unit_price'] / units_per_case if units_per_case > 0 else item['unit_price']

            if existing:
                # Update existing inventory item - add to quantity, update lot/date to most recent
                new_quantity = existing['quantity_on_hand'] + item['inventory_quantity']
                cursor_inventory.execute("""
                    UPDATE ingredients
                    SET quantity_on_hand = ?,
                        units_per_case = ?,
                        unit_cost = ?,
                        lot_number = ?,
                        date_received = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_quantity, units_per_case, unit_cost, item['lot_number'], received_date, existing['id']))
            else:
                # Insert new inventory item - use inventory_quantity (total expanded quantity)
                cursor_inventory.execute("""
                    INSERT INTO ingredients (
                        ingredient_code, ingredient_name, brand, supplier_name,
                        category, quantity_on_hand, unit_of_measure, unit_cost,
                        date_received, lot_number, storage_location, units_per_case
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item['ingredient_code'],
                    item['ingredient_name'],
                    item['brand'],
                    supplier_name,
                    item.get('category', 'Uncategorized'),  # Use provided category or default
                    item['inventory_quantity'],  # Total quantity (e.g., 60 rolls, not 10 bags)
                    item['unit_of_measure'],
                    unit_cost,  # Cost per individual unit
                    received_date,
                    item['lot_number'],
                    None,  # Storage location to be set later
                    units_per_case
                ))

                # Log item creation
                new_item_id = cursor_inventory.lastrowid
                log_audit(
                    action_type='ITEM_CREATED',
                    entity_type='item',
                    entity_id=new_item_id,
                    entity_reference=f"{item['ingredient_code']} - {item['ingredient_name']}",
                    details=f"New item added via imported invoice. Qty: {item['inventory_quantity']} {item['unit_of_measure']}, Supplier: {supplier_name}"
                )

            # Update price tracking after adding to inventory
            update_ingredient_prices(item['ingredient_code'], cursor_invoices, cursor_inventory)

        conn_invoices.commit()
        conn_inventory.commit()
        conn_invoices.close()
        conn_inventory.close()

        # Log audit entry
        log_audit(
            action_type='INVOICE_IMPORTED',
            entity_type='invoice',
            entity_id=invoice_id,
            entity_reference=invoice_number,
            details=f"Supplier: {supplier_name}, Amount: ${total_amount:.2f}, Items: {len(line_items)}, Source: File Upload"
        )

        return jsonify({
            'success': True,
            'message': f'Invoice {invoice_number} imported successfully and added to inventory',
            'items_count': len(line_items),
            'total_amount': total_amount
        })

    except Exception as e:
        if 'conn_invoices' in locals():
            conn_invoices.rollback()
            conn_invoices.close()
        if 'conn_inventory' in locals():
            conn_inventory.rollback()
            conn_inventory.close()
        return jsonify({'success': False, 'error': f'Error parsing file: {str(e)}'}), 500

@app.route('/api/suppliers/all', methods=['GET'])
def get_all_suppliers():
    """Get all suppliers with full details"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, supplier_name, contact_person, phone, email,
               address, payment_terms, notes
        FROM suppliers
        ORDER BY supplier_name
    """)
    suppliers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(suppliers)

@app.route('/api/suppliers/create', methods=['POST'])
def create_supplier():
    """Create a new supplier"""
    data = request.json
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO suppliers (supplier_name, contact_person, phone, email,
                                   address, payment_terms, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data['supplier_name'],
            data.get('contact_person'),
            data.get('phone'),
            data.get('email'),
            data.get('address'),
            data.get('payment_terms'),
            data.get('notes')
        ))
        conn.commit()
        supplier_id = cursor.lastrowid

        # Log audit entry
        log_audit(
            action_type='SUPPLIER_CREATED',
            entity_type='supplier',
            entity_id=supplier_id,
            entity_reference=data['supplier_name'],
            details=f"New supplier created. Contact: {data.get('contact_person', 'N/A')}, Phone: {data.get('phone', 'N/A')}"
        )

        conn.close()
        return jsonify({
            'success': True,
            'message': f'Supplier {data["supplier_name"]} created successfully',
            'supplier_id': supplier_id
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Supplier name already exists'}), 400
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/suppliers/update/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    """Update a supplier and cascade changes globally"""
    data = request.json
    new_supplier_name = data['supplier_name']

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    try:
        # Get the old supplier name first
        cursor_inv.execute("SELECT supplier_name FROM suppliers WHERE id = ?", (supplier_id,))
        old_supplier_result = cursor_inv.fetchone()

        if not old_supplier_result:
            conn_inv.close()
            conn_invoices.close()
            return jsonify({'success': False, 'error': 'Supplier not found'}), 404

        old_supplier_name = old_supplier_result['supplier_name']

        # Update the suppliers table with all details
        cursor_inv.execute("""
            UPDATE suppliers
            SET supplier_name = ?,
                contact_person = ?,
                phone = ?,
                email = ?,
                address = ?,
                payment_terms = ?,
                notes = ?
            WHERE id = ?
        """, (
            new_supplier_name,
            data.get('contact_person'),
            data.get('phone'),
            data.get('email'),
            data.get('address'),
            data.get('payment_terms'),
            data.get('notes'),
            supplier_id
        ))

        # CASCADE: Update supplier name in ingredients table
        cursor_inv.execute("""
            UPDATE ingredients
            SET supplier_name = ?
            WHERE supplier_name = ?
        """, (new_supplier_name, old_supplier_name))
        ingredients_updated = cursor_inv.rowcount

        # CASCADE: Update supplier name in invoices table
        cursor_invoices.execute("""
            UPDATE invoices
            SET supplier_name = ?
            WHERE supplier_name = ?
        """, (new_supplier_name, old_supplier_name))
        invoices_updated = cursor_invoices.rowcount

        conn_inv.commit()
        conn_invoices.commit()
        conn_inv.close()
        conn_invoices.close()

        message = f'Supplier updated successfully'
        if ingredients_updated > 0 or invoices_updated > 0:
            message += f' (updated {ingredients_updated} inventory items, {invoices_updated} invoices)'

        return jsonify({
            'success': True,
            'message': message
        })
    except sqlite3.IntegrityError:
        conn_inv.close()
        conn_invoices.close()
        return jsonify({'success': False, 'error': 'Supplier name already exists'}), 400
    except Exception as e:
        conn_inv.rollback()
        conn_invoices.rollback()
        conn_inv.close()
        conn_invoices.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/suppliers/delete/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    """Delete a supplier"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # Check if supplier is in use
        cursor.execute("SELECT COUNT(*) as count FROM ingredients WHERE supplier_name = (SELECT supplier_name FROM suppliers WHERE id = ?)", (supplier_id,))
        count = cursor.fetchone()['count']

        if count > 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Cannot delete supplier - it is used by {count} inventory item(s)'
            }), 400

        cursor.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Supplier deleted successfully'
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/invoices/<invoice_number>/payment-status', methods=['PUT'])
def update_invoice_payment_status(invoice_number):
    """Update the payment status of an invoice"""
    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    try:
        data = request.json
        new_status = data.get('payment_status', 'UNPAID').upper()

        # Validate payment status
        if new_status not in ['UNPAID', 'PAID', 'PARTIAL']:
            return jsonify({'success': False, 'error': 'Invalid payment status'}), 400

        # Get current invoice details
        cursor.execute("SELECT id, payment_status, supplier_name, total_amount FROM invoices WHERE invoice_number = ?",
                      (invoice_number,))
        invoice = cursor.fetchone()

        if not invoice:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        old_status = invoice['payment_status']
        invoice_id = invoice['id']

        # Update payment status
        if new_status == 'PAID':
            cursor.execute("""
                UPDATE invoices
                SET payment_status = ?, payment_date = CURRENT_TIMESTAMP
                WHERE invoice_number = ?
            """, (new_status, invoice_number))
        else:
            cursor.execute("""
                UPDATE invoices
                SET payment_status = ?, payment_date = NULL
                WHERE invoice_number = ?
            """, (new_status, invoice_number))

        conn.commit()

        # Log audit entry
        log_audit(
            action_type=f'INVOICE_PAYMENT_{new_status}',
            entity_type='invoice',
            entity_id=invoice_id,
            entity_reference=invoice_number,
            details=f"Payment status changed from {old_status} to {new_status}. Supplier: {invoice['supplier_name']}, Amount: ${invoice['total_amount']:.2f}"
        )

        conn.close()

        return jsonify({
            'success': True,
            'message': f'Payment status updated to {new_status}',
            'payment_status': new_status
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/invoices/delete/<invoice_number>', methods=['DELETE'])
def delete_invoice(invoice_number):
    """Delete an invoice and reverse inventory changes"""
    conn_inv = get_db_connection(INVOICES_DB)
    cursor_inv = conn_inv.cursor()

    conn_inventory = get_db_connection(INVENTORY_DB)
    cursor_inventory = conn_inventory.cursor()

    try:
        # Get invoice details
        cursor_inv.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,))
        invoice = cursor_inv.fetchone()

        if not invoice:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        invoice_id = invoice['id']
        reconciled = invoice['reconciled']

        # Get all line items for this invoice
        cursor_inv.execute("""
            SELECT * FROM invoice_line_items
            WHERE invoice_id = ?
        """, (invoice_id,))
        line_items = cursor_inv.fetchall()

        items_deleted = 0
        inventory_reversed = 0

        # Reverse the inventory changes - inventory is created immediately when invoice is imported/created
        # We'll look for inventory records that match the invoice's received_date and line items
        for item in line_items:
            # Try to find matching inventory records
            # Match on: ingredient_code, date_received (from invoice), and lot_number if available
            cursor_inventory.execute("""
                SELECT id, quantity_on_hand
                FROM ingredients
                WHERE ingredient_code = ?
                AND date_received = ?
                AND (lot_number = ? OR (lot_number IS NULL AND ? IS NULL))
            """, (item['ingredient_code'], invoice['received_date'],
                  item['lot_number'], item['lot_number']))

            matching_records = cursor_inventory.fetchall()

            # Since these inventory records were created by this invoice,
            # we should delete them entirely (they only exist because of this invoice)
            for record in matching_records:
                cursor_inventory.execute("DELETE FROM ingredients WHERE id = ?", (record['id'],))
                inventory_reversed += 1

        # Delete line items
        cursor_inv.execute("DELETE FROM invoice_line_items WHERE invoice_id = ?", (invoice_id,))
        items_deleted = cursor_inv.rowcount

        # Delete invoice
        cursor_inv.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))

        # Commit both databases
        conn_inv.commit()
        conn_inventory.commit()

        conn_inv.close()
        conn_inventory.close()

        message = f'Invoice {invoice_number} deleted successfully'
        if inventory_reversed > 0:
            message += f'. Reversed {inventory_reversed} inventory record(s)'

        # Log audit entry
        log_audit(
            action_type='INVOICE_DELETED',
            entity_type='invoice',
            entity_id=invoice_id,
            entity_reference=invoice_number,
            details=f"Line items deleted: {items_deleted}, Inventory records reversed: {inventory_reversed}"
        )

        return jsonify({
            'success': True,
            'message': message,
            'line_items_deleted': items_deleted,
            'inventory_reversed': inventory_reversed
        })

    except Exception as e:
        conn_inv.rollback()
        conn_inventory.rollback()
        conn_inv.close()
        conn_inventory.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# INVENTORY COUNT ENDPOINTS
# ============================================================================

@app.route('/api/counts/all', methods=['GET'])
def get_all_counts():
    """Get all inventory counts with optional date filtering"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            count_number,
            count_date,
            counted_by,
            notes,
            reconciled,
            created_at
        FROM inventory_counts
        WHERE 1=1
    """
    params = []

    if date_from:
        query += " AND count_date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND count_date <= ?"
        params.append(date_to)

    query += " ORDER BY count_date DESC, created_at DESC"

    cursor.execute(query, params)
    counts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(counts)

@app.route('/api/counts/<int:count_id>', methods=['GET'])
def get_count_details(count_id):
    """Get detailed information for a specific count"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get count header
    cursor.execute("""
        SELECT * FROM inventory_counts WHERE id = ?
    """, (count_id,))

    count = cursor.fetchone()
    if not count:
        conn.close()
        return jsonify({'error': 'Count not found'}), 404

    count_dict = dict(count)

    # Get line items
    cursor.execute("""
        SELECT * FROM count_line_items WHERE count_id = ?
        ORDER BY ingredient_name
    """, (count_id,))

    count_dict['line_items'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(count_dict)

@app.route('/api/counts/preview', methods=['POST'])
def preview_count():
    """
    Preview physical count changes and show warnings BEFORE applying.
    This prevents accidentally setting inventory to incorrect/negative values.
    """
    data = request.json
    count_items = data.get('line_items', [])

    if not count_items:
        return jsonify({'success': False, 'error': 'No count items provided'}), 400

    conn = get_db_connection(INVENTORY_DB)

    try:
        preview = preview_count_changes(count_items, conn)
        conn.close()

        return jsonify({
            'success': True,
            'preview': preview
        })

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/counts/create', methods=['POST'])
def create_count():
    """Create a new inventory count and reconcile with inventory"""
    data = request.json

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # Insert count header
        cursor.execute("""
            INSERT INTO inventory_counts (
                count_number, count_date, counted_by, notes, reconciled
            )
            VALUES (?, ?, ?, ?, 'YES')
        """, (
            data['count_number'],
            data['count_date'],
            data.get('counted_by'),
            data.get('notes')
        ))

        count_id = cursor.lastrowid

        # Process each line item
        for item in data['line_items']:
            ingredient_code = item['ingredient_code']
            quantity_counted = item['quantity_counted']

            # Look up current inventory to get expected quantity
            cursor.execute("""
                SELECT id, quantity_on_hand, unit_of_measure, ingredient_name
                FROM ingredients
                WHERE ingredient_code = ?
                LIMIT 1
            """, (ingredient_code,))

            inventory_item = cursor.fetchone()

            if inventory_item:
                # Item exists in inventory
                quantity_expected = inventory_item['quantity_on_hand']
                variance = quantity_counted - quantity_expected
                ingredient_name = inventory_item['ingredient_name']
                unit_of_measure = inventory_item['unit_of_measure']

                # Update inventory quantity to counted amount (reconciliation)
                cursor.execute("""
                    UPDATE ingredients
                    SET quantity_on_hand = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (quantity_counted, inventory_item['id']))
            else:
                # Item not in inventory - this is a new discovery
                quantity_expected = 0
                variance = quantity_counted
                ingredient_name = item.get('ingredient_name', 'Unknown')
                unit_of_measure = item.get('unit_of_measure', 'ea')

                # Create new inventory record with counted quantity
                # Use minimal default values since we don't have pricing info from counts
                cursor.execute("""
                    INSERT INTO ingredients (
                        ingredient_code, ingredient_name, category, unit_of_measure,
                        quantity_on_hand, unit_cost, supplier_name, units_per_case
                    )
                    VALUES (?, ?, 'Uncategorized', ?, ?, 0, NULL, 1)
                """, (ingredient_code, ingredient_name, unit_of_measure, quantity_counted))

            # Insert count line item with variance tracking
            cursor.execute("""
                INSERT INTO count_line_items (
                    count_id, ingredient_code, ingredient_name,
                    quantity_counted, quantity_expected, variance,
                    unit_of_measure, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                count_id,
                ingredient_code,
                ingredient_name,
                quantity_counted,
                quantity_expected,
                variance,
                unit_of_measure,
                item.get('notes')
            ))

        conn.commit()

        # Log audit entry
        log_audit(
            action_type='COUNT_CREATED',
            entity_type='count',
            entity_id=count_id,
            entity_reference=data['count_number'],
            details=f"Counted by: {data.get('counted_by', 'N/A')}, Items: {len(data['line_items'])}"
        )

        conn.close()

        return jsonify({
            'success': True,
            'message': f'Count {data["count_number"]} created and inventory reconciled',
            'count_id': count_id
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/counts/delete/<int:count_id>', methods=['DELETE'])
def delete_count(count_id):
    """Delete an inventory count (does NOT reverse inventory changes)"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    try:
        # Get count details
        cursor.execute("SELECT count_number FROM inventory_counts WHERE id = ?", (count_id,))
        count = cursor.fetchone()

        if not count:
            conn.close()
            return jsonify({'success': False, 'error': 'Count not found'}), 404

        count_number = count['count_number']

        # Delete line items (CASCADE should handle this, but being explicit)
        cursor.execute("DELETE FROM count_line_items WHERE count_id = ?", (count_id,))

        # Delete count header
        cursor.execute("DELETE FROM inventory_counts WHERE id = ?", (count_id,))

        conn.commit()

        # Log audit entry
        log_audit(
            action_type='COUNT_DELETED',
            entity_type='count',
            entity_id=count_id,
            entity_reference=count_number,
            details="Count record deleted (inventory NOT reversed)"
        )

        conn.close()

        return jsonify({
            'success': True,
            'message': f'Count {count_number} deleted (inventory quantities were NOT reversed)'
        })

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# AUDIT LOG ENDPOINTS
# ============================================================================

@app.route('/api/audit/all', methods=['GET'])
def get_all_audit_logs():
    """Get all audit log entries with optional date filtering"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get optional filters
    action_type = request.args.get('action_type', 'all')
    entity_type = request.args.get('entity_type', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    limit = request.args.get('limit', 100)

    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []

    if action_type != 'all':
        query += " AND action_type = ?"
        params.append(action_type)

    if entity_type != 'all':
        query += " AND entity_type = ?"
        params.append(entity_type)

    if date_from:
        query += " AND DATE(timestamp) >= ?"
        params.append(date_from)

    if date_to:
        query += " AND DATE(timestamp) <= ?"
        params.append(date_to)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(logs)

@app.route('/api/audit/stats', methods=['GET'])
def get_audit_stats():
    """Get audit statistics"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get counts by action type
    cursor.execute("""
        SELECT action_type, COUNT(*) as count
        FROM audit_log
        GROUP BY action_type
    """)
    action_counts = [dict(row) for row in cursor.fetchall()]

    # Get recent activity count
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM audit_log
        WHERE timestamp >= datetime('now', '-7 days')
    """)
    recent_count = cursor.fetchone()['count']

    conn.close()

    return jsonify({
        'action_counts': action_counts,
        'recent_activity_count': recent_count
    })

def migrate_database():
    """Add price tracking columns to ingredients table and create categories table if they don't exist"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    columns_added = False

    try:
        # Create categories table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Populate categories table with existing categories from ingredients
        cursor.execute("""
            INSERT OR IGNORE INTO categories (category_name)
            SELECT DISTINCT category FROM ingredients WHERE category IS NOT NULL
        """)
        print("✓ Categories table ready")

        # Check if columns exist
        cursor.execute("PRAGMA table_info(ingredients)")
        columns = [col[1] for col in cursor.fetchall()]

        # Add last_unit_price column if it doesn't exist
        if 'last_unit_price' not in columns:
            cursor.execute("ALTER TABLE ingredients ADD COLUMN last_unit_price REAL")
            print("✓ Added last_unit_price column")
            columns_added = True

        # Add average_unit_price column if it doesn't exist
        if 'average_unit_price' not in columns:
            cursor.execute("ALTER TABLE ingredients ADD COLUMN average_unit_price REAL")
            print("✓ Added average_unit_price column")
            columns_added = True

        # Add units_per_case column if it doesn't exist
        if 'units_per_case' not in columns:
            cursor.execute("ALTER TABLE ingredients ADD COLUMN units_per_case REAL DEFAULT 1")
            print("✓ Added units_per_case column")
            columns_added = True

        conn.commit()
        conn.close()

        # If columns were added, recalculate prices for all existing ingredients
        if columns_added:
            print("🔄 Recalculating prices for existing ingredients...")
            recalculate_all_prices()

        print("✓ Database migration completed")
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"✗ Database migration failed: {str(e)}")

def recalculate_all_prices():
    """Recalculate price history for all ingredients from invoice data"""
    try:
        conn_inventory = get_db_connection(INVENTORY_DB)
        cursor_inventory = conn_inventory.cursor()

        conn_invoices = get_db_connection(INVOICES_DB)
        cursor_invoices = conn_invoices.cursor()

        # Get all unique ingredient codes
        cursor_inventory.execute("SELECT DISTINCT ingredient_code FROM ingredients")
        ingredient_codes = [row['ingredient_code'] for row in cursor_inventory.fetchall()]

        updated_from_invoices = 0
        updated_from_unit_cost = 0

        for ingredient_code in ingredient_codes:
            last_price, avg_price = update_ingredient_prices(ingredient_code, cursor_invoices, cursor_inventory)
            if last_price is not None:
                updated_from_invoices += 1
            else:
                # No invoice history - use unit_cost as fallback
                cursor_inventory.execute("""
                    SELECT unit_cost FROM ingredients
                    WHERE ingredient_code = ? AND unit_cost IS NOT NULL AND unit_cost > 0
                    LIMIT 1
                """, (ingredient_code,))
                result = cursor_inventory.fetchone()
                if result and result['unit_cost']:
                    unit_cost = result['unit_cost']
                    cursor_inventory.execute("""
                        UPDATE ingredients
                        SET last_unit_price = ?, average_unit_price = ?
                        WHERE ingredient_code = ?
                    """, (unit_cost, unit_cost, ingredient_code))
                    updated_from_unit_cost += 1

        conn_inventory.commit()
        conn_inventory.close()
        conn_invoices.close()

        print(f"✓ Updated prices: {updated_from_invoices} from invoices, {updated_from_unit_cost} from unit_cost")
    except Exception as e:
        print(f"✗ Error recalculating prices: {str(e)}")

def update_ingredient_prices(ingredient_code, cursor_invoices, cursor_inventory):
    """Update last_unit_price and average_unit_price for an ingredient based on invoice history"""
    try:
        # Get all prices for this ingredient from invoice line items, ordered by invoice date (most recent first)
        cursor_invoices.execute("""
            SELECT ili.unit_price, i.invoice_date, ili.quantity_received
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_code = ?
            ORDER BY i.invoice_date DESC
        """, (ingredient_code,))

        price_records = cursor_invoices.fetchall()

        if price_records:
            # Last price is the most recent (first in the list)
            last_price = price_records[0]['unit_price']

            # Calculate weighted average price (weighted by quantity received)
            total_cost = sum(rec['unit_price'] * rec['quantity_received'] for rec in price_records)
            total_quantity = sum(rec['quantity_received'] for rec in price_records)
            average_price = total_cost / total_quantity if total_quantity > 0 else last_price

            # Update all inventory records for this ingredient code
            cursor_inventory.execute("""
                UPDATE ingredients
                SET last_unit_price = ?, average_unit_price = ?
                WHERE ingredient_code = ?
            """, (last_price, average_price, ingredient_code))

            return last_price, average_price

        return None, None
    except Exception as e:
        print(f"Error updating prices for {ingredient_code}: {str(e)}")
        return None, None


# ==================== ANALYTICS API ENDPOINTS ====================

@app.route('/api/analytics/widgets/available')
def get_available_widgets():
    """Get all available analytics widgets"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT widget_key, widget_name, widget_type, chart_type, category,
               description, icon, default_enabled, requires_recipe_data
        FROM analytics_widgets
        ORDER BY category, widget_name
    """)

    widgets = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(widgets)

@app.route('/api/analytics/categories')
def get_analytics_categories():
    """Get all available categories for filtering"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT category
        FROM ingredients
        WHERE active = 1 AND category IS NOT NULL
        ORDER BY category
    """)

    categories = [row['category'] for row in cursor.fetchall()]
    conn.close()

    return jsonify({'categories': categories})

@app.route('/api/analytics/widgets/enabled')
def get_enabled_widgets():
    """Get user's enabled widgets with preferences"""
    user_id = request.args.get('user_id', 'default')

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT aw.widget_key, aw.widget_name, aw.widget_type, aw.chart_type,
               aw.category, aw.description, aw.icon,
               uwp.enabled, uwp.position, uwp.size, uwp.custom_settings
        FROM analytics_widgets aw
        JOIN user_widget_preferences uwp ON aw.widget_key = uwp.widget_key
        WHERE uwp.user_id = ? AND uwp.enabled = 1
        ORDER BY uwp.position
    """, (user_id,))

    widgets = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(widgets)

@app.route('/api/analytics/widgets/toggle', methods=['POST'])
def toggle_widget():
    """Enable/disable a widget"""
    data = request.json
    user_id = data.get('user_id', 'default')
    widget_key = data.get('widget_key')
    enabled = data.get('enabled', 1)

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM user_widget_preferences
        WHERE user_id = ? AND widget_key = ?
    """, (user_id, widget_key))

    if cursor.fetchone():
        cursor.execute("""
            UPDATE user_widget_preferences
            SET enabled = ?
            WHERE user_id = ? AND widget_key = ?
        """, (enabled, user_id, widget_key))
    else:
        cursor.execute("""
            SELECT MAX(position) FROM user_widget_preferences WHERE user_id = ?
        """, (user_id,))
        max_pos = cursor.fetchone()[0] or 0

        cursor.execute("""
            INSERT INTO user_widget_preferences (user_id, widget_key, enabled, position, size)
            VALUES (?, ?, ?, ?, 'medium')
        """, (user_id, widget_key, enabled, max_pos + 1))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/analytics/summary')
def analytics_summary():
    """Get summary KPIs for dashboard header"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn_inv = get_db_connection(INVOICES_DB)
    conn_ing = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()
    cursor_ing = conn_ing.cursor()

    query = "SELECT SUM(total_amount) as total FROM invoices WHERE 1=1"
    params = []
    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)

    cursor_inv.execute(query, params)
    total_spend = cursor_inv.fetchone()['total'] or 0

    cursor_inv.execute("SELECT COUNT(DISTINCT supplier_name) as count FROM invoices")
    supplier_count = cursor_inv.fetchone()['count']

    cursor_ing.execute("""
        SELECT COUNT(*) as count
        FROM ingredients
        WHERE active = 1 AND average_unit_price > 0 AND last_unit_price > 0
          AND ABS((last_unit_price - average_unit_price) / average_unit_price * 100) >= 15
    """)
    alert_count = cursor_ing.fetchone()['count']

    cursor_ing.execute("""
        SELECT SUM(quantity_on_hand * average_unit_price) as total
        FROM ingredients WHERE active = 1
    """)
    inventory_value = cursor_ing.fetchone()['total'] or 0

    conn_inv.close()
    conn_ing.close()

    return jsonify({
        'total_spend': round(total_spend, 2),
        'supplier_count': supplier_count,
        'alert_count': alert_count,
        'inventory_value': round(inventory_value, 2)
    })

# ==================== ANALYTICS WIDGET DATA ENDPOINTS ====================

@app.route('/api/analytics/vendor-spend')
def analytics_vendor_spend():
    """Vendor spend distribution"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    query = """
        SELECT supplier_name, SUM(total_amount) as total
        FROM invoices
        WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)

    query += " GROUP BY supplier_name ORDER BY total DESC LIMIT 10"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return jsonify({
        'labels': [row['supplier_name'] for row in results],
        'values': [float(row['total']) for row in results]
    })

@app.route('/api/analytics/price-trends')
def analytics_price_trends():
    """Price trend for a single ingredient"""
    ingredient_code = request.args.get('ingredient_code', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not ingredient_code:
        return jsonify({'error': 'ingredient_code parameter required'}), 400

    conn_inv = get_db_connection(INVOICES_DB)
    cursor = conn_inv.cursor()

    query = """
        SELECT
            i.invoice_date as date,
            ili.unit_price as price,
            ili.ingredient_name
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        WHERE ili.ingredient_code = ?
    """
    params = [ingredient_code]

    if date_from:
        query += " AND i.invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND i.invoice_date <= ?"
        params.append(date_to)

    query += " ORDER BY i.invoice_date"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn_inv.close()

    data = [dict(row) for row in rows]

    return jsonify({
        'name': data[0]['ingredient_name'] if data else 'Unknown',
        'data': data
    })

@app.route('/api/analytics/purchase-frequency')
def analytics_purchase_frequency():
    """Calculate purchase frequency for ingredients"""
    conn_inv = get_db_connection(INVOICES_DB)
    cursor = conn_inv.cursor()

    # Get purchase dates for each ingredient
    cursor.execute("""
        SELECT
            ili.ingredient_code,
            ili.ingredient_name,
            i.invoice_date,
            COUNT(*) as purchase_count
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        GROUP BY ili.ingredient_code, ili.ingredient_name
        ORDER BY ili.ingredient_code
    """)

    purchases = {}
    for row in cursor.fetchall():
        code = row['ingredient_code']
        if code not in purchases:
            purchases[code] = {
                'name': row['ingredient_name'],
                'count': row['purchase_count'],
                'dates': []
            }

    # Get all purchase dates for each ingredient
    cursor.execute("""
        SELECT
            ili.ingredient_code,
            i.invoice_date
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        ORDER BY ili.ingredient_code, i.invoice_date
    """)

    for row in cursor.fetchall():
        code = row['ingredient_code']
        if code in purchases:
            purchases[code]['dates'].append(row['invoice_date'])

    # Calculate average days between purchases
    from datetime import datetime
    results = []

    for code, data in purchases.items():
        if len(data['dates']) < 2:
            avg_days = 365  # Default to yearly if only one purchase
        else:
            dates = [datetime.strptime(d, '%Y-%m-%d') for d in data['dates']]
            dates.sort()
            total_days = 0
            for i in range(1, len(dates)):
                total_days += (dates[i] - dates[i-1]).days
            avg_days = total_days / (len(dates) - 1)

        # Categorize frequency
        if avg_days < 3:
            frequency = 'daily'
        elif avg_days <= 10:
            frequency = 'weekly'
        else:
            frequency = 'monthly'

        results.append({
            'code': code,
            'name': data['name'],
            'purchase_count': data['count'],
            'avg_days_between': round(avg_days, 1),
            'frequency': frequency
        })

    conn_inv.close()

    return jsonify({'ingredients': results})

@app.route('/api/analytics/ingredients-with-price-history')
def analytics_ingredients_with_price_history():
    """Get list of ingredient codes that have price history in invoices"""
    conn_inv = get_db_connection(INVOICES_DB)
    cursor = conn_inv.cursor()

    cursor.execute("""
        SELECT DISTINCT ingredient_code
        FROM invoice_line_items
        ORDER BY ingredient_code
    """)

    codes = [row['ingredient_code'] for row in cursor.fetchall()]
    conn_inv.close()

    return jsonify({'ingredient_codes': codes})

# Removed: Product Profitability widget deleted per user request
# @app.route('/api/analytics/product-profitability')
# def analytics_product_profitability():
#     """Product profitability analysis"""
#     conn = get_db_connection(INVENTORY_DB)
#     cursor = conn.cursor()
#
#     # Helper function to calculate product ingredient cost recursively
#     def calculate_cost(product_id, visited=None):
#         if visited is None:
#             visited = set()
#         if product_id in visited:
#             return 0
#         visited.add(product_id)
#
#         cost_cursor = conn.cursor()
#         cost_cursor.execute("""
#             SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
#             FROM recipes r
#             WHERE r.product_id = ?
#         """, (product_id,))
#
#         recipe_items = cost_cursor.fetchall()
#         total_cost = 0
#
#         for row in recipe_items:
#             source_type = row['source_type']
#             source_id = row['source_id']
#             quantity = row['quantity_needed']
#
#             if source_type == 'ingredient':
#                 ing_cursor = conn.cursor()
#                 ing_cursor.execute("""
#                     SELECT COALESCE(unit_cost, 0) as unit_cost
#                     FROM ingredients WHERE id = ?
#                 """, (source_id,))
#                 ing_result = ing_cursor.fetchone()
#                 if ing_result:
#                     total_cost += quantity * ing_result['unit_cost']
#             elif source_type == 'product':
#                 nested_cost = calculate_cost(source_id, visited)
#                 total_cost += quantity * nested_cost
#
#         return total_cost
#
#     # Get all products
#     cursor.execute("""
#         SELECT p.id, p.product_name, p.selling_price
#         FROM products p
#         WHERE EXISTS (SELECT 1 FROM recipes WHERE product_id = p.id)
#     """)
#
#     products = cursor.fetchall()
#
#     labels = []
#     margins = []
#
#     for product in products:
#         product_id = product['id']
#         sale_price = float(product['selling_price'] or 0)
#         cost = calculate_cost(product_id)
#
#         if sale_price > 0:
#             margin = ((sale_price - cost) / sale_price) * 100
#             labels.append(product['product_name'])
#             margins.append(round(margin, 1))
#
#     conn.close()
#
#     return jsonify({
#         'labels': labels,
#         'values': margins,
#         'dataset_label': 'Profit Margin %'
#     })

@app.route('/api/analytics/category-spending')
def analytics_category_spending():
    """Category spending distribution (pie chart) - shows ALL categories"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn_inv = get_db_connection(INVOICES_DB)
    conn_ing = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()
    cursor_ing = conn_ing.cursor()

    # Get category mapping from ingredients table
    cursor_ing.execute("SELECT ingredient_code, category FROM ingredients")
    category_map = {row['ingredient_code']: row['category'] for row in cursor_ing.fetchall()}

    # Get total spending by ingredient code from invoices
    query = """
        SELECT
            ili.ingredient_code,
            SUM(ili.total_price) as amount
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        WHERE 1=1
    """
    params = []

    if date_from:
        query += " AND i.invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND i.invoice_date <= ?"
        params.append(date_to)

    query += " GROUP BY ili.ingredient_code"

    cursor_inv.execute(query, params)
    data = [dict(row) for row in cursor_inv.fetchall()]

    # Aggregate by category
    category_totals = {}
    for row in data:
        category = category_map.get(row['ingredient_code'], 'Unknown')
        amount = row['amount']

        if category not in category_totals:
            category_totals[category] = 0

        category_totals[category] += amount

    conn_inv.close()
    conn_ing.close()

    # Sort by amount descending and return in pie chart format
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

    return jsonify({
        'labels': [category for category, _ in sorted_categories],
        'values': [round(amount, 2) for _, amount in sorted_categories]
    })

@app.route('/api/analytics/inventory-value')
def analytics_inventory_value():
    """Inventory value by category"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, SUM(quantity_on_hand * average_unit_price) as value
        FROM ingredients
        WHERE active = 1 AND category IS NOT NULL
        GROUP BY category
        ORDER BY value DESC
    """)

    results = cursor.fetchall()
    conn.close()

    return jsonify({
        'labels': [row['category'] for row in results],
        'values': [round(float(row['value'] or 0), 2) for row in results]
    })

@app.route('/api/analytics/supplier-performance')
def analytics_supplier_performance():
    """Supplier performance metrics"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    query = """
        SELECT supplier_name,
               COUNT(*) as invoice_count,
               SUM(total_amount) as total_spend,
               AVG(total_amount) as avg_invoice
        FROM invoices
        WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)

    query += " GROUP BY supplier_name ORDER BY total_spend DESC"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return jsonify({
        'columns': ['Supplier', 'Invoices', 'Total Spend', 'Avg Invoice'],
        'rows': [
            [
                row['supplier_name'],
                row['invoice_count'],
                f"${row['total_spend']:,.2f}",
                f"${row['avg_invoice']:,.2f}"
            ]
            for row in results
        ]
    })

@app.route('/api/analytics/price-volatility')
def analytics_price_volatility():
    """Price volatility analysis"""
    conn_inv = get_db_connection(INVOICES_DB)
    cursor = conn_inv.cursor()

    cursor.execute("""
        SELECT ili.ingredient_name,
               AVG(ili.unit_price) as avg_price,
               MAX(ili.unit_price) as max_price,
               MIN(ili.unit_price) as min_price,
               COUNT(*) as purchase_count
        FROM invoice_line_items ili
        GROUP BY ili.ingredient_name
        HAVING purchase_count >= 3
    """)

    results = cursor.fetchall()
    conn_inv.close()

    volatility_data = []
    for row in results:
        avg = float(row['avg_price'])
        max_price = float(row['max_price'])
        min_price = float(row['min_price'])
        if avg > 0:
            cv = ((max_price - min_price) / avg) * 100
            volatility_data.append({
                'ingredient': row['ingredient_name'],
                'cv': round(cv, 1),
                'avg': round(avg, 2)
            })

    volatility_data.sort(key=lambda x: x['cv'], reverse=True)
    volatility_data = volatility_data[:15]

    return jsonify({
        'labels': [item['ingredient'] for item in volatility_data],
        'values': [item['cv'] for item in volatility_data],
        'dataset_label': 'Price Volatility %'
    })

@app.route('/api/analytics/invoice-activity')
def analytics_invoice_activity():
    """Invoice activity over time"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    query = """
        SELECT DATE(invoice_date) as date,
               COUNT(*) as count,
               SUM(total_amount) as total
        FROM invoices
        WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)

    query += " GROUP BY DATE(invoice_date) ORDER BY date"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return jsonify({
        'labels': [row['date'] for row in results],
        'datasets': [
            {
                'label': 'Invoice Count',
                'data': [row['count'] for row in results]
            },
            {
                'label': 'Total Amount ($)',
                'data': [float(row['total']) for row in results]
            }
        ]
    })

@app.route('/api/analytics/cost-variance')
def analytics_cost_variance():
    """Cost variance alerts"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, category,
               average_unit_price,
               last_unit_price,
               ((last_unit_price - average_unit_price) / average_unit_price * 100) as variance_pct
        FROM ingredients
        WHERE active = 1
          AND average_unit_price > 0
          AND last_unit_price > 0
          AND ABS((last_unit_price - average_unit_price) / average_unit_price * 100) >= 15
        ORDER BY ABS(variance_pct) DESC
        LIMIT 20
    """)

    results = cursor.fetchall()
    conn.close()

    return jsonify({
        'columns': ['Ingredient', 'Category', 'Avg Price', 'Last Price', 'Variance'],
        'rows': [
            [
                row['ingredient_name'],
                row['category'],
                f"${row['average_unit_price']:,.2f}",
                f"${row['last_unit_price']:,.2f}",
                f"{row['variance_pct']:+.1f}%"
            ]
            for row in results
        ],
        'row_classes': ['variance-high' if abs(row['variance_pct']) >= 25 else 'variance-medium' for row in results]
    })

@app.route('/api/analytics/usage-forecast')
def analytics_usage_forecast():
    """Ingredient usage forecast"""
    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, SUM(quantity_received) as total_qty
        FROM invoice_line_items
        GROUP BY ingredient_name
        ORDER BY total_qty DESC
        LIMIT 10
    """)

    top_ingredients = cursor.fetchall()

    datasets = []
    for ing in top_ingredients:
        cursor.execute("""
            SELECT DATE(i.invoice_date) as date, SUM(ili.quantity_received) as qty
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name = ?
            GROUP BY DATE(i.invoice_date)
            ORDER BY date
        """, (ing['ingredient_name'],))

        results = cursor.fetchall()
        if results:
            datasets.append({
                'label': ing['ingredient_name'],
                'data': [float(row['qty']) for row in results]
            })

    cursor.execute("""
        SELECT DISTINCT DATE(invoice_date) as date
        FROM invoices
        ORDER BY date
    """)
    labels = [row['date'] for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'labels': labels,
        'datasets': datasets
    })

@app.route('/api/analytics/recipe-cost-trajectory')
def analytics_recipe_cost_trajectory():
    """Recipe cost changes over time"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, p.product_name
        FROM products p
        WHERE 1=1 AND EXISTS (
            SELECT 1 FROM recipes WHERE product_id = p.id
        )
    """)

    products = cursor.fetchall()

    conn_inv = get_db_connection(INVOICES_DB)
    cursor_inv = conn_inv.cursor()

    datasets = []
    for product in products[:5]:
        cursor.execute("""
            SELECT r.ingredient_id, r.quantity_needed, i.ingredient_name
            FROM recipes r
            JOIN ingredients i ON r.ingredient_id = i.id
            WHERE r.product_id = ?
        """, (product['id'],))

        recipe_items = cursor.fetchall()

        query = """
            SELECT DATE(inv.invoice_date) as date,
                   AVG(ili.unit_price) as avg_price
            FROM invoice_line_items ili
            JOIN invoices inv ON ili.invoice_id = inv.id
            WHERE ili.ingredient_name = ?
        """
        params_base = []
        if date_from:
            query += " AND inv.invoice_date >= ?"
            params_base.append(date_from)
        if date_to:
            query += " AND inv.invoice_date <= ?"
            params_base.append(date_to)

        query += " GROUP BY DATE(inv.invoice_date) ORDER BY date"

        cost_by_date = {}
        for item in recipe_items:
            cursor_inv.execute(query, [item['ingredient_name']] + params_base)
            results = cursor_inv.fetchall()

            for row in results:
                date = row['date']
                if date not in cost_by_date:
                    cost_by_date[date] = 0
                cost_by_date[date] += float(row['avg_price']) * float(item['quantity_needed'])

        if cost_by_date:
            sorted_dates = sorted(cost_by_date.keys())
            datasets.append({
                'label': product['product_name'],
                'data': [cost_by_date[date] for date in sorted_dates]
            })

    query = "SELECT DISTINCT DATE(invoice_date) as date FROM invoices WHERE 1=1"
    params = []
    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)
    query += " ORDER BY date"

    cursor_inv.execute(query, params)
    labels = [row['date'] for row in cursor_inv.fetchall()]

    conn.close()
    conn_inv.close()

    return jsonify({
        'labels': labels,
        'datasets': datasets
    })

@app.route('/api/analytics/substitution-opportunities')
def analytics_substitution_opportunities():
    """Ingredient substitution opportunities"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT i1.ingredient_name as ingredient1,
               i1.average_unit_price as price1,
               i2.ingredient_name as ingredient2,
               i2.average_unit_price as price2,
               i1.category,
               ((i1.average_unit_price - i2.average_unit_price) / i1.average_unit_price * 100) as savings_pct
        FROM ingredients i1
        JOIN ingredients i2 ON i1.category = i2.category
            AND i1.id != i2.id
            AND i1.average_unit_price > i2.average_unit_price
        WHERE i1.active = 1
          AND i2.active = 1
          AND i1.average_unit_price > 0
          AND i2.average_unit_price > 0
          AND ((i1.average_unit_price - i2.average_unit_price) / i1.average_unit_price * 100) >= 20
        ORDER BY savings_pct DESC
        LIMIT 15
    """)

    results = cursor.fetchall()
    conn.close()

    return jsonify({
        'columns': ['Current', 'Price', 'Alternative', 'Price', 'Category', 'Savings'],
        'rows': [
            [
                row['ingredient1'],
                f"${row['price1']:,.2f}",
                row['ingredient2'],
                f"${row['price2']:,.2f}",
                row['category'],
                f"{row['savings_pct']:.1f}%"
            ]
            for row in results
        ]
    })

@app.route('/api/analytics/dead-stock')
def analytics_dead_stock():
    """Dead stock analysis"""
    from datetime import datetime, timedelta

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    cursor_inv.execute("""
        SELECT ingredient_name, quantity_on_hand, average_unit_price, category
        FROM ingredients
        WHERE active = 1 AND quantity_on_hand > 0
    """)

    ingredients = cursor_inv.fetchall()

    dead_stock = []
    for ing in ingredients:
        cursor_invoices.execute("""
            SELECT MAX(i.invoice_date) as last_purchase
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name = ?
        """, (ing['ingredient_name'],))

        result = cursor_invoices.fetchone()
        last_purchase = result['last_purchase'] if result else None

        if last_purchase:
            last_date = datetime.strptime(last_purchase, '%Y-%m-%d')
            days_since = (datetime.now() - last_date).days

            if days_since > 30:
                value = float(ing['quantity_on_hand']) * float(ing['average_unit_price'])
                dead_stock.append({
                    'ingredient': ing['ingredient_name'],
                    'category': ing['category'],
                    'quantity': ing['quantity_on_hand'],
                    'value': value,
                    'days': days_since
                })

    dead_stock.sort(key=lambda x: x['value'], reverse=True)
    dead_stock = dead_stock[:20]

    conn_inv.close()
    conn_invoices.close()

    return jsonify({
        'columns': ['Ingredient', 'Category', 'Qty', 'Value', 'Days Since Purchase'],
        'rows': [
            [
                item['ingredient'],
                item['category'],
                f"{item['quantity']:.1f}",
                f"${item['value']:,.2f}",
                item['days']
            ]
            for item in dead_stock
        ]
    })

@app.route('/api/analytics/eoq-optimizer')
def analytics_eoq_optimizer():
    """Economic Order Quantity optimizer"""
    import math

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name,
               COUNT(*) as order_count,
               AVG(quantity_received) as avg_order_qty,
               SUM(quantity_received) as total_qty
        FROM invoice_line_items
        GROUP BY ingredient_name
        HAVING order_count >= 3
        ORDER BY total_qty DESC
        LIMIT 15
    """)

    results = cursor.fetchall()
    conn.close()

    eoq_data = []
    for row in results:
        annual_demand = float(row['total_qty'])
        order_cost = 50

        conn_inv = get_db_connection(INVENTORY_DB)
        cursor_inv = conn_inv.cursor()
        cursor_inv.execute("""
            SELECT average_unit_price
            FROM ingredients
            WHERE ingredient_name = ?
        """, (row['ingredient_name'],))

        ing_result = cursor_inv.fetchone()
        conn_inv.close()

        if ing_result and ing_result['average_unit_price']:
            unit_cost = float(ing_result['average_unit_price'])
            holding_cost = unit_cost * 0.20

            if holding_cost > 0:
                eoq = math.sqrt((2 * annual_demand * order_cost) / holding_cost)

                eoq_data.append({
                    'ingredient': row['ingredient_name'],
                    'current_avg': float(row['avg_order_qty']),
                    'eoq': round(eoq, 1)
                })

    return jsonify({
        'columns': ['Ingredient', 'Current Avg Order', 'Optimal EOQ', 'Difference'],
        'rows': [
            [
                item['ingredient'],
                f"{item['current_avg']:.1f}",
                f"{item['eoq']:.1f}",
                f"{((item['eoq'] - item['current_avg']) / item['current_avg'] * 100):+.1f}%"
            ]
            for item in eoq_data
        ]
    })

@app.route('/api/analytics/seasonal-patterns')
def analytics_seasonal_patterns():
    """Seasonal purchasing patterns"""
    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT strftime('%m', invoice_date) as month,
               SUM(total_amount) as total
        FROM invoices
        GROUP BY month
        ORDER BY month
    """)

    results = cursor.fetchall()
    conn.close()

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    spending_by_month = {str(i+1).zfill(2): 0 for i in range(12)}
    for row in results:
        spending_by_month[row['month']] = float(row['total'])

    return jsonify({
        'labels': month_names,
        'values': [spending_by_month[str(i+1).zfill(2)] for i in range(12)],
        'dataset_label': 'Total Spending'
    })

@app.route('/api/analytics/menu-engineering')
def analytics_menu_engineering():
    """Menu engineering matrix (BCG analysis)"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Helper function to calculate product ingredient cost recursively
    def calculate_cost(product_id, visited=None):
        if visited is None:
            visited = set()
        if product_id in visited:
            return 0  # Prevent infinite recursion
        visited.add(product_id)

        cost_cursor = conn.cursor()
        cost_cursor.execute("""
            SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
            FROM recipes r
            WHERE r.product_id = ?
        """, (product_id,))

        recipe_items = cost_cursor.fetchall()
        total_cost = 0

        for row in recipe_items:
            source_type = row['source_type']
            source_id = row['source_id']
            quantity = row['quantity_needed']

            if source_type == 'ingredient':
                ing_cursor = conn.cursor()
                ing_cursor.execute("""
                    SELECT COALESCE(unit_cost, 0) as unit_cost
                    FROM ingredients WHERE id = ?
                """, (source_id,))
                ing_result = ing_cursor.fetchone()
                if ing_result:
                    total_cost += quantity * ing_result['unit_cost']
            elif source_type == 'product':
                nested_cost = calculate_cost(source_id, visited)
                total_cost += quantity * nested_cost

        return total_cost

    # Get all products
    cursor.execute("""
        SELECT p.id, p.product_name, p.selling_price, p.quantity_on_hand as volume
        FROM products p
        WHERE EXISTS (SELECT 1 FROM recipes WHERE product_id = p.id)
    """)

    products = cursor.fetchall()

    # Calculate cost for each product using recursive function
    results = []
    for product in products:
        product_id = product['id']
        cost = calculate_cost(product_id)
        results.append({
            'product_name': product['product_name'],
            'selling_price': product['selling_price'],
            'cost': cost,
            'volume': product['volume']
        })

    conn.close()

    quadrants = {
        'stars': {'label': 'Stars (High Margin, High Volume)', 'data': []},
        'plowhorses': {'label': 'Plow Horses (Low Margin, High Volume)', 'data': []},
        'puzzles': {'label': 'Puzzles (High Margin, Low Volume)', 'data': []},
        'dogs': {'label': 'Dogs (Low Margin, Low Volume)', 'data': []}
    }

    if results:
        avg_margin = sum((float(r['selling_price'] or 0) - float(r['cost'] or 0)) / float(r['selling_price'] or 1) * 100 for r in results) / len(results)
        avg_volume = sum(float(r['volume'] or 0) for r in results) / len(results)

        for row in results:
            sale_price = float(row['selling_price'] or 0)
            cost = float(row['cost'] or 0)
            volume = float(row['volume'] or 0)

            if sale_price > 0:
                margin = ((sale_price - cost) / sale_price) * 100

                point = {
                    'x': round(margin, 1),
                    'y': round(volume, 1),
                    'name': row['product_name']
                }

                if margin >= avg_margin and volume >= avg_volume:
                    quadrants['stars']['data'].append(point)
                elif margin < avg_margin and volume >= avg_volume:
                    quadrants['plowhorses']['data'].append(point)
                elif margin >= avg_margin and volume < avg_volume:
                    quadrants['puzzles']['data'].append(point)
                else:
                    quadrants['dogs']['data'].append(point)

    return jsonify({
        'quadrants': list(quadrants.values()),
        'x_label': 'Profit Margin %',
        'y_label': 'Sales Volume'
    })

@app.route('/api/analytics/waste-shrinkage')
def analytics_waste_shrinkage():
    """Waste and shrinkage analysis"""
    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    cursor_inv.execute("""
        SELECT ingredient_name, quantity_on_hand, average_unit_price, category
        FROM ingredients
        WHERE active = 1 AND average_unit_price > 5
        ORDER BY (quantity_on_hand * average_unit_price) DESC
        LIMIT 20
    """)

    ingredients = cursor_inv.fetchall()

    shrinkage_data = []
    for ing in ingredients:
        cursor_invoices.execute("""
            SELECT SUM(quantity_received) as total_purchased
            FROM invoice_line_items
            WHERE ingredient_name = ?
        """, (ing['ingredient_name'],))

        result = cursor_invoices.fetchone()
        total_purchased = float(result['total_purchased'] or 0)
        on_hand = float(ing['quantity_on_hand'])

        if total_purchased > 0:
            expected_ratio = 0.3
            expected_on_hand = total_purchased * expected_ratio
            variance = on_hand - expected_on_hand
            variance_pct = (variance / expected_on_hand) * 100 if expected_on_hand > 0 else 0

            if abs(variance_pct) > 20:
                shrinkage_data.append({
                    'ingredient': ing['ingredient_name'],
                    'category': ing['category'],
                    'purchased': total_purchased,
                    'on_hand': on_hand,
                    'variance': variance_pct
                })

    conn_inv.close()
    conn_invoices.close()

    shrinkage_data.sort(key=lambda x: abs(x['variance']), reverse=True)

    return jsonify({
        'columns': ['Ingredient', 'Category', 'Purchased', 'On Hand', 'Variance'],
        'rows': [
            [
                item['ingredient'],
                item['category'],
                f"{item['purchased']:.1f}",
                f"{item['on_hand']:.1f}",
                f"{item['variance']:+.1f}%"
            ]
            for item in shrinkage_data
        ]
    })

@app.route('/api/analytics/price-correlation')
def analytics_price_correlation():
    """Price correlation matrix"""
    import math

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, COUNT(*) as count
        FROM invoice_line_items
        GROUP BY ingredient_name
        ORDER BY count DESC
        LIMIT 8
    """)

    top_ingredients = [row['ingredient_name'] for row in cursor.fetchall()]

    price_series = {}
    for ing in top_ingredients:
        cursor.execute("""
            SELECT DATE(i.invoice_date) as date, AVG(ili.unit_price) as price
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name = ?
            GROUP BY DATE(i.invoice_date)
            ORDER BY date
        """, (ing,))

        prices = [float(row['price']) for row in cursor.fetchall()]
        if len(prices) >= 3:
            price_series[ing] = prices

    conn.close()

    def correlation(x, y):
        n = min(len(x), len(y))
        if n < 2:
            return 0
        x, y = x[:n], y[:n]

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator = math.sqrt(sum((xi - mean_x) ** 2 for xi in x)) * math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        return numerator / denominator if denominator != 0 else 0

    ingredients = list(price_series.keys())
    matrix = []

    for ing1 in ingredients:
        row = []
        for ing2 in ingredients:
            corr = correlation(price_series[ing1], price_series[ing2])
            row.append(round(corr, 2))
        matrix.append(row)

    return jsonify({
        'rows': ingredients,
        'columns': ingredients,
        'values': matrix
    })

@app.route('/api/analytics/breakeven-analysis')
def analytics_breakeven_analysis():
    """Product break-even analysis"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Helper function to calculate product ingredient cost recursively
    def calculate_cost(product_id, visited=None):
        if visited is None:
            visited = set()
        if product_id in visited:
            return 0
        visited.add(product_id)

        cost_cursor = conn.cursor()
        cost_cursor.execute("""
            SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
            FROM recipes r
            WHERE r.product_id = ?
        """, (product_id,))

        recipe_items = cost_cursor.fetchall()
        total_cost = 0

        for row in recipe_items:
            source_type = row['source_type']
            source_id = row['source_id']
            quantity = row['quantity_needed']

            if source_type == 'ingredient':
                ing_cursor = conn.cursor()
                ing_cursor.execute("""
                    SELECT COALESCE(unit_cost, 0) as unit_cost
                    FROM ingredients WHERE id = ?
                """, (source_id,))
                ing_result = ing_cursor.fetchone()
                if ing_result:
                    total_cost += quantity * ing_result['unit_cost']
            elif source_type == 'product':
                nested_cost = calculate_cost(source_id, visited)
                total_cost += quantity * nested_cost

        return total_cost

    # Get all products
    cursor.execute("""
        SELECT p.id, p.product_name, p.selling_price
        FROM products p
        WHERE EXISTS (SELECT 1 FROM recipes WHERE product_id = p.id)
    """)

    products = cursor.fetchall()

    fixed_cost_per_product = 500

    breakeven_data = []
    for product in products:
        product_id = product['id']
        sale_price = float(product['selling_price'] or 0)
        variable_cost = calculate_cost(product_id)

        if sale_price > variable_cost:
            contribution_margin = sale_price - variable_cost
            breakeven_units = fixed_cost_per_product / contribution_margin

            breakeven_data.append({
                'product': product['product_name'],
                'sale_price': sale_price,
                'variable_cost': variable_cost,
                'contribution': contribution_margin,
                'breakeven': round(breakeven_units, 1)
            })

    conn.close()

    return jsonify({
        'columns': ['Product', 'Sale Price', 'Variable Cost', 'Contribution', 'Breakeven Units'],
        'rows': [
            [
                item['product'],
                f"${item['sale_price']:.2f}",
                f"${item['variable_cost']:.2f}",
                f"${item['contribution']:.2f}",
                f"{item['breakeven']:.1f}"
            ]
            for item in breakeven_data
        ]
    })

@app.route('/api/analytics/cost-drivers')
def analytics_cost_drivers():
    """Cost drivers regression analysis"""
    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    cursor_inv.execute("""
        SELECT DISTINCT category
        FROM ingredients
        WHERE category IS NOT NULL
        ORDER BY category
    """)

    categories = [row['category'] for row in cursor_inv.fetchall()]

    # Get ingredient-to-category mapping
    category_map = {}
    for category in categories:
        cursor_inv.execute("SELECT ingredient_name FROM ingredients WHERE category = ? AND active = 1", (category,))
        ingredients = [row['ingredient_name'] for row in cursor_inv.fetchall()]
        category_map[category] = ingredients

    conn_inv.close()

    # Now query invoices
    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    datasets = []
    for category in categories[:6]:
        ingredients_in_cat = category_map.get(category, [])
        if not ingredients_in_cat:
            continue

        placeholders = ','.join('?' * len(ingredients_in_cat))
        query = f"""
            SELECT DATE(i.invoice_date) as date, SUM(ili.total_price) as total
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name IN ({placeholders})
            GROUP BY DATE(i.invoice_date)
            ORDER BY date
        """

        cursor_invoices.execute(query, ingredients_in_cat)
        results = cursor_invoices.fetchall()

        if results and len(results) >= 3:
            x_vals = list(range(len(results)))
            y_vals = [float(row['total']) for row in results]

            n = len(x_vals)
            sum_x = sum(x_vals)
            sum_y = sum(y_vals)
            sum_xy = sum(x_vals[i] * y_vals[i] for i in range(n))
            sum_x2 = sum(x * x for x in x_vals)

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0

            datasets.append({
                'category': category,
                'trend': 'increasing' if slope > 0 else 'decreasing',
                'slope': round(slope, 2),
                'avg_spend': round(sum_y / n, 2)
            })

    datasets.sort(key=lambda x: x['avg_spend'], reverse=True)

    conn_invoices.close()

    return jsonify({
        'columns': ['Category', 'Trend', 'Slope', 'Avg Spending'],
        'rows': [
            [
                item['category'],
                item['trend'].upper(),
                f"{item['slope']:+.2f}",
                f"${item['avg_spend']:,.2f}"
            ]
            for item in datasets
        ]
    })

# ========== ANALYTICS EXPORT ENDPOINTS ==========

@app.route('/api/analytics/vendor-spend/export')
def export_vendor_spend():
    """Export vendor spend distribution as CSV"""
    from flask import make_response

    # Get the data using the same logic as the regular endpoint
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    query = """
        SELECT supplier_name, SUM(total_amount) as total
        FROM invoices
        WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)

    query += " GROUP BY supplier_name ORDER BY total DESC LIMIT 10"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Supplier Name', 'Total Spend'])
    for row in results:
        writer.writerow([row['supplier_name'], f"${float(row['total']):.2f}"])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=vendor_spend.csv'
    return response

@app.route('/api/analytics/price-trends/export')
def export_price_trends():
    """Export price trends as CSV"""
    from flask import make_response

    ingredient_codes = request.args.get('ingredients', '').split(',')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not ingredient_codes or ingredient_codes == ['']:
        conn_inv = get_db_connection(INVOICES_DB)
        cursor = conn_inv.cursor()
        cursor.execute("""
            SELECT ingredient_code, SUM(quantity_received) as total_qty
            FROM invoice_line_items
            GROUP BY ingredient_code
            ORDER BY total_qty DESC
            LIMIT 5
        """)
        ingredient_codes = [row['ingredient_code'] for row in cursor.fetchall()]
        conn_inv.close()

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Date', 'Ingredient', 'Average Price'])

    for code in ingredient_codes:
        if not code:
            continue

        query = """
            SELECT DATE(i.invoice_date) as date,
                   ili.ingredient_name,
                   AVG(ili.unit_price) as avg_price
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_code = ?
        """
        params = [code]

        if date_from:
            query += " AND i.invoice_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND i.invoice_date <= ?"
            params.append(date_to)

        query += " GROUP BY DATE(i.invoice_date), ili.ingredient_name ORDER BY date"

        cursor.execute(query, params)
        results = cursor.fetchall()

        for row in results:
            writer.writerow([row['date'], row['ingredient_name'], f"${float(row['avg_price']):.2f}"])

    conn.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=price_trends.csv'
    return response

# Removed: Product Profitability export endpoint
# @app.route('/api/analytics/product-profitability/export')
# def export_product_profitability():
#     """Export product profitability as CSV"""
#     from flask import make_response
#
#     conn = get_db_connection(INVENTORY_DB)
#
#     # Helper function to calculate product ingredient cost recursively
#     def calculate_cost(product_id, visited=None):
#         if visited is None:
#             visited = set()
#         if product_id in visited:
#             return 0
#         visited.add(product_id)
#
#         cost_cursor = conn.cursor()
#         cost_cursor.execute("""
#             SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
#             FROM recipes r
#             WHERE r.product_id = ?
#         """, (product_id,))
#
#         recipe_items = cost_cursor.fetchall()
#         total_cost = 0
#
#         for row in recipe_items:
#             source_type = row['source_type']
#             source_id = row['source_id']
#             quantity = row['quantity_needed']
#
#             if source_type == 'ingredient':
#                 ing_cursor = conn.cursor()
#                 ing_cursor.execute("""
#                     SELECT COALESCE(unit_cost, 0) as unit_cost
#                     FROM ingredients WHERE id = ?
#                 """, (source_id,))
#                 ing_result = ing_cursor.fetchone()
#                 if ing_result:
#                     total_cost += quantity * ing_result['unit_cost']
#             elif source_type == 'product':
#                 nested_cost = calculate_cost(source_id, visited)
#                 total_cost += quantity * nested_cost
#
#         return total_cost
#
#     cursor = conn.cursor()
#     cursor.execute("""
#         SELECT p.id, p.product_name, p.selling_price
#         FROM products p
#         WHERE EXISTS (SELECT 1 FROM recipes WHERE product_id = p.id)
#         ORDER BY p.product_name
#     """)
#
#     products = cursor.fetchall()
#
#     output = io.StringIO()
#     writer = csv.writer(output)
#     writer.writerow(['Product Name', 'Selling Price', 'Ingredient Cost', 'Profit', 'Margin %'])
#
#     for product in products:
#         product_id = product['id']
#         cost = calculate_cost(product_id)
#         selling_price = float(product['selling_price'] or 0)
#         profit = selling_price - cost
#         margin = (profit / selling_price * 100) if selling_price > 0 else 0
#
#         writer.writerow([
#             product['product_name'],
#             f"${selling_price:.2f}",
#             f"${cost:.2f}",
#             f"${profit:.2f}",
#             f"{margin:.1f}%"
#         ])
#
#     conn.close()
#
#     response = make_response(output.getvalue())
#     response.headers['Content-Type'] = 'text/csv'
#     response.headers['Content-Disposition'] = 'attachment; filename=product_profitability.csv'
#     return response

@app.route('/api/analytics/category-spending/export')
def export_category_spending():
    """Export category spending totals as CSV"""
    from flask import make_response

    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    selected_categories = request.args.get('categories', '')

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    # Get all categories
    cursor_inv.execute("SELECT DISTINCT category FROM ingredients WHERE active = 1 ORDER BY category")
    all_categories = [row['category'] for row in cursor_inv.fetchall() if row['category']]

    # Determine which categories to show
    if selected_categories:
        categories = [cat.strip() for cat in selected_categories.split(',') if cat.strip() in all_categories]
    else:
        categories = all_categories[:5]

    # Get ingredient-to-category mapping
    category_map = {}
    for category in categories:
        cursor_inv.execute("SELECT ingredient_name FROM ingredients WHERE category = ? AND active = 1", (category,))
        ingredients = [row['ingredient_name'] for row in cursor_inv.fetchall()]
        category_map[category] = ingredients

    conn_inv.close()

    # Query invoices for total spending per category
    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Category', 'Total Spending'])

    for category in categories:
        ingredients_in_cat = category_map.get(category, [])
        if not ingredients_in_cat:
            continue

        placeholders = ','.join('?' * len(ingredients_in_cat))
        query = f"""
            SELECT SUM(ili.total_price) as total
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name IN ({placeholders})
        """
        params = ingredients_in_cat[:]

        if date_from:
            query += " AND i.invoice_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND i.invoice_date <= ?"
            params.append(date_to)

        cursor_invoices.execute(query, params)
        result = cursor_invoices.fetchone()

        total = float(result['total'] or 0)
        if total > 0:
            writer.writerow([category, f"${total:.2f}"])

    conn_invoices.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=category_spending.csv'
    return response

@app.route('/api/analytics/inventory-value/export')
def export_inventory_value():
    """Export inventory value distribution as CSV"""
    from flask import make_response

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name,
               quantity_on_hand,
               COALESCE(unit_cost, 0) as unit_cost,
               (quantity_on_hand * COALESCE(unit_cost, 0)) as total_value
        FROM ingredients
        WHERE active = 1
        ORDER BY total_value DESC
        LIMIT 10
    """)

    results = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Quantity On Hand', 'Unit Cost', 'Total Value'])

    for row in results:
        writer.writerow([
            row['ingredient_name'],
            f"{float(row['quantity_on_hand']):.2f}",
            f"${float(row['unit_cost']):.2f}",
            f"${float(row['total_value']):.2f}"
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=inventory_value.csv'
    return response

@app.route('/api/analytics/supplier-performance/export')
def export_supplier_performance():
    """Export supplier performance as CSV"""
    from flask import make_response

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT supplier_name,
               COUNT(DISTINCT id) as invoice_count,
               AVG(total_amount) as avg_invoice,
               SUM(total_amount) as total_spend,
               AVG(JULIANDAY('now') - JULIANDAY(invoice_date)) as avg_days_ago
        FROM invoices
        GROUP BY supplier_name
        HAVING invoice_count >= 2
        ORDER BY total_spend DESC
        LIMIT 15
    """)

    results = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Supplier', 'Invoice Count', 'Avg Invoice', 'Total Spend', 'Avg Days Since Last'])

    for row in results:
        writer.writerow([
            row['supplier_name'],
            row['invoice_count'],
            f"${float(row['avg_invoice']):.2f}",
            f"${float(row['total_spend']):.2f}",
            f"{int(row['avg_days_ago'])} days"
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=supplier_performance.csv'
    return response

@app.route('/api/analytics/price-volatility/export')
def export_price_volatility():
    """Export price volatility index as CSV"""
    from flask import make_response

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ili.ingredient_name,
               AVG(ili.unit_price) as avg_price,
               COUNT(*) as price_count
        FROM invoice_line_items ili
        GROUP BY ili.ingredient_name
        HAVING price_count >= 3
    """)

    ingredients = cursor.fetchall()
    volatility_data = []

    for ing in ingredients:
        cursor.execute("""
            SELECT unit_price
            FROM invoice_line_items
            WHERE ingredient_name = ?
        """, (ing['ingredient_name'],))

        prices = [float(row['unit_price']) for row in cursor.fetchall()]
        avg = sum(prices) / len(prices)
        variance = sum((p - avg) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        cv = (std_dev / avg * 100) if avg > 0 else 0

        volatility_data.append({
            'name': ing['ingredient_name'],
            'cv': cv,
            'avg_price': avg,
            'std_dev': std_dev
        })

    conn.close()

    volatility_data.sort(key=lambda x: x['cv'], reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Volatility Index (CV%)', 'Avg Price', 'Std Deviation'])

    for item in volatility_data[:15]:
        writer.writerow([
            item['name'],
            f"{item['cv']:.1f}%",
            f"${item['avg_price']:.2f}",
            f"${item['std_dev']:.2f}"
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=price_volatility.csv'
    return response

@app.route('/api/analytics/invoice-activity/export')
def export_invoice_activity():
    """Export invoice activity timeline as CSV"""
    from flask import make_response

    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    query = """
        SELECT DATE(invoice_date) as date,
               COUNT(*) as invoice_count,
               SUM(total_amount) as total_value
        FROM invoices
        WHERE 1=1
    """
    params = []

    if date_from:
        query += " AND invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND invoice_date <= ?"
        params.append(date_to)

    query += " GROUP BY DATE(invoice_date) ORDER BY date"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Invoice Count', 'Total Value'])

    for row in results:
        writer.writerow([
            row['date'],
            row['invoice_count'],
            f"${float(row['total_value']):.2f}"
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=invoice_activity.csv'
    return response

@app.route('/api/analytics/cost-variance/export')
def export_cost_variance():
    """Export cost variance alerts as CSV"""
    from flask import make_response

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name,
               AVG(unit_price) as avg_price,
               COUNT(*) as purchase_count
        FROM invoice_line_items
        GROUP BY ingredient_name
        HAVING purchase_count >= 2
    """)

    ingredients = cursor.fetchall()
    variances = []

    for ing in ingredients:
        cursor.execute("""
            SELECT unit_price, invoice_id
            FROM invoice_line_items
            WHERE ingredient_name = ?
            ORDER BY invoice_id DESC
            LIMIT 1
        """, (ing['ingredient_name'],))

        latest = cursor.fetchone()

        if latest:
            avg_price = float(ing['avg_price'])
            latest_price = float(latest['unit_price'])
            variance_pct = ((latest_price - avg_price) / avg_price * 100) if avg_price > 0 else 0

            if abs(variance_pct) >= 10:
                variances.append({
                    'name': ing['ingredient_name'],
                    'avg_price': avg_price,
                    'latest_price': latest_price,
                    'variance_pct': variance_pct
                })

    conn.close()

    variances.sort(key=lambda x: abs(x['variance_pct']), reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Avg Price', 'Latest Price', 'Variance %'])

    for item in variances[:15]:
        writer.writerow([
            item['name'],
            f"${item['avg_price']:.2f}",
            f"${item['latest_price']:.2f}",
            f"{item['variance_pct']:+.1f}%"
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=cost_variance.csv'
    return response

@app.route('/api/analytics/menu-engineering/export')
def export_menu_engineering():
    """Export menu engineering matrix as CSV"""
    from flask import make_response

    conn = get_db_connection(INVENTORY_DB)

    # Helper function to calculate product ingredient cost recursively
    def calculate_cost(product_id, visited=None):
        if visited is None:
            visited = set()
        if product_id in visited:
            return 0
        visited.add(product_id)

        cost_cursor = conn.cursor()
        cost_cursor.execute("""
            SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
            FROM recipes r
            WHERE r.product_id = ?
        """, (product_id,))

        recipe_items = cost_cursor.fetchall()
        total_cost = 0

        for row in recipe_items:
            source_type = row['source_type']
            source_id = row['source_id']
            quantity = row['quantity_needed']

            if source_type == 'ingredient':
                ing_cursor = conn.cursor()
                ing_cursor.execute("""
                    SELECT COALESCE(unit_cost, 0) as unit_cost
                    FROM ingredients WHERE id = ?
                """, (source_id,))
                ing_result = ing_cursor.fetchone()
                if ing_result:
                    total_cost += quantity * ing_result['unit_cost']
            elif source_type == 'product':
                nested_cost = calculate_cost(source_id, visited)
                total_cost += quantity * nested_cost

        return total_cost

    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.product_name, p.selling_price, p.quantity_on_hand as volume
        FROM products p
        WHERE EXISTS (SELECT 1 FROM recipes WHERE product_id = p.id)
    """)

    products = cursor.fetchall()
    results = []

    for product in products:
        product_id = product['id']
        cost = calculate_cost(product_id)
        selling_price = float(product['selling_price'] or 0)
        margin_pct = ((selling_price - cost) / selling_price * 100) if selling_price > 0 else 0

        results.append({
            'product_name': product['product_name'],
            'selling_price': selling_price,
            'cost': cost,
            'margin_pct': margin_pct,
            'volume': product['volume']
        })

    conn.close()

    if not results:
        avg_margin = 0
        avg_volume = 0
    else:
        avg_margin = sum(r['margin_pct'] for r in results) / len(results)
        avg_volume = sum(float(r['volume'] or 0) for r in results) / len(results)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Product', 'Margin %', 'Volume', 'Classification'])

    for r in results:
        margin = r['margin_pct']
        volume = float(r['volume'] or 0)

        if margin >= avg_margin and volume >= avg_volume:
            classification = 'Star'
        elif margin >= avg_margin and volume < avg_volume:
            classification = 'Puzzle'
        elif margin < avg_margin and volume >= avg_volume:
            classification = 'Plow Horse'
        else:
            classification = 'Dog'

        writer.writerow([
            r['product_name'],
            f"{margin:.1f}%",
            f"{volume:.0f}",
            classification
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=menu_engineering.csv'
    return response

@app.route('/api/analytics/dead-stock/export')
def export_dead_stock():
    """Export dead stock analysis as CSV"""
    from flask import make_response

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, quantity_on_hand, average_unit_price, category
        FROM ingredients
        WHERE active = 1 AND quantity_on_hand > 0
        ORDER BY (quantity_on_hand * average_unit_price) DESC
    """)

    results = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Quantity On Hand', 'Unit Price', 'Total Value', 'Category'])

    for row in results:
        qty = float(row['quantity_on_hand'])
        price = float(row['average_unit_price'] or 0)
        total_value = qty * price

        writer.writerow([
            row['ingredient_name'],
            f"{qty:.2f}",
            f"${price:.2f}",
            f"${total_value:.2f}",
            row['category'] or 'N/A'
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=dead_stock.csv'
    return response

@app.route('/api/analytics/breakeven-analysis/export')
def export_breakeven_analysis():
    """Export break-even analysis as CSV"""
    from flask import make_response

    conn = get_db_connection(INVENTORY_DB)

    # Helper function to calculate product ingredient cost recursively
    def calculate_cost(product_id, visited=None):
        if visited is None:
            visited = set()
        if product_id in visited:
            return 0
        visited.add(product_id)

        cost_cursor = conn.cursor()
        cost_cursor.execute("""
            SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
            FROM recipes r
            WHERE r.product_id = ?
        """, (product_id,))

        recipe_items = cost_cursor.fetchall()
        total_cost = 0

        for row in recipe_items:
            source_type = row['source_type']
            source_id = row['source_id']
            quantity = row['quantity_needed']

            if source_type == 'ingredient':
                ing_cursor = conn.cursor()
                ing_cursor.execute("""
                    SELECT COALESCE(unit_cost, 0) as unit_cost
                    FROM ingredients WHERE id = ?
                """, (source_id,))
                ing_result = ing_cursor.fetchone()
                if ing_result:
                    total_cost += quantity * ing_result['unit_cost']
            elif source_type == 'product':
                nested_cost = calculate_cost(source_id, visited)
                total_cost += quantity * nested_cost

        return total_cost

    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.product_name, p.selling_price
        FROM products p
        WHERE EXISTS (SELECT 1 FROM recipes WHERE product_id = p.id)
        ORDER BY p.product_name
    """)

    products = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Product', 'Selling Price', 'Variable Cost', 'Contribution Margin', 'Break-Even Units (est)'])

    for product in products:
        product_id = product['id']
        cost = calculate_cost(product_id)
        selling_price = float(product['selling_price'] or 0)
        contribution = selling_price - cost

        # Estimate fixed costs at $500 per product (placeholder)
        fixed_costs = 500
        breakeven = (fixed_costs / contribution) if contribution > 0 else 0

        writer.writerow([
            product['product_name'],
            f"${selling_price:.2f}",
            f"${cost:.2f}",
            f"${contribution:.2f}",
            f"{int(breakeven)} units"
        ])

    conn.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=breakeven_analysis.csv'
    return response

@app.route('/api/analytics/seasonal-patterns/export')
def export_seasonal_patterns():
    """Export seasonal demand patterns as CSV"""
    from flask import make_response

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, SUM(quantity_received) as total_qty
        FROM invoice_line_items
        GROUP BY ingredient_name
        ORDER BY total_qty DESC
        LIMIT 5
    """)

    top_ingredients = [row['ingredient_name'] for row in cursor.fetchall()]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Month', 'Ingredient', 'Total Quantity'])

    for ingredient in top_ingredients:
        cursor.execute("""
            SELECT strftime('%Y-%m', i.invoice_date) as month,
                   SUM(ili.quantity_received) as total_qty
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name = ?
            GROUP BY month
            ORDER BY month
        """, (ingredient,))

        results = cursor.fetchall()

        for row in results:
            writer.writerow([
                row['month'],
                ingredient,
                f"{float(row['total_qty']):.2f}"
            ])

    conn.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=seasonal_patterns.csv'
    return response

@app.route('/api/analytics/waste-shrinkage/export')
def export_waste_shrinkage():
    """Export waste and shrinkage analysis as CSV"""
    from flask import make_response

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    cursor_inv.execute("""
        SELECT ingredient_name, quantity_on_hand, average_unit_price, category
        FROM ingredients
        WHERE active = 1
        ORDER BY ingredient_name
    """)

    ingredients = cursor_inv.fetchall()
    conn_inv.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Expected Qty', 'Actual Qty', 'Variance', 'Value Loss', 'Category'])

    for ing in ingredients:
        actual_qty = float(ing['quantity_on_hand'])
        expected_qty = actual_qty * 1.15
        variance = expected_qty - actual_qty
        unit_price = float(ing['average_unit_price'] or 0)
        value_loss = variance * unit_price

        if variance > 0.5:
            writer.writerow([
                ing['ingredient_name'],
                f"{expected_qty:.2f}",
                f"{actual_qty:.2f}",
                f"{variance:.2f}",
                f"${value_loss:.2f}",
                ing['category'] or 'N/A'
            ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=waste_shrinkage.csv'
    return response

@app.route('/api/analytics/eoq-optimizer/export')
def export_eoq_optimizer():
    """Export EOQ optimizer as CSV"""
    from flask import make_response

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    cursor_inv.execute("""
        SELECT ingredient_name, quantity_on_hand, average_unit_price
        FROM ingredients
        WHERE active = 1
        ORDER BY ingredient_name
    """)

    ingredients = cursor_inv.fetchall()
    conn_inv.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Current Qty', 'Annual Demand (est)', 'Order Cost', 'Holding Cost', 'EOQ'])

    for ing in ingredients:
        annual_demand = float(ing['quantity_on_hand']) * 12
        order_cost = 50
        unit_price = float(ing['average_unit_price'] or 0)
        holding_cost_pct = 0.25
        holding_cost = unit_price * holding_cost_pct

        if holding_cost > 0 and annual_demand > 0:
            eoq = ((2 * annual_demand * order_cost) / holding_cost) ** 0.5
        else:
            eoq = 0

        writer.writerow([
            ing['ingredient_name'],
            f"{float(ing['quantity_on_hand']):.2f}",
            f"{annual_demand:.0f}",
            f"${order_cost:.2f}",
            f"${holding_cost:.2f}",
            f"{eoq:.0f} units"
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=eoq_optimizer.csv'
    return response

@app.route('/api/analytics/price-correlation/export')
def export_price_correlation():
    """Export supplier price correlation as CSV"""
    from flask import make_response

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT supplier_name
        FROM invoices
        ORDER BY supplier_name
        LIMIT 8
    """)

    suppliers = [row['supplier_name'] for row in cursor.fetchall()]

    # Get average prices per supplier
    supplier_prices = {}
    for supplier in suppliers:
        cursor.execute("""
            SELECT AVG(total_amount) as avg_price
            FROM invoices
            WHERE supplier_name = ?
        """, (supplier,))
        result = cursor.fetchone()
        supplier_prices[supplier] = float(result['avg_price'] or 0)

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write correlation matrix
    header = ['Supplier'] + suppliers
    writer.writerow(header)

    for s1 in suppliers:
        row = [s1]
        for s2 in suppliers:
            if s1 == s2:
                correlation = 1.00
            else:
                # Simplified correlation (in real analysis, this would calculate actual correlation)
                price_diff = abs(supplier_prices[s1] - supplier_prices[s2])
                max_price = max(supplier_prices[s1], supplier_prices[s2])
                correlation = 1.0 - (price_diff / max_price) if max_price > 0 else 0.5
            row.append(f"{correlation:.2f}")
        writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=price_correlation.csv'
    return response

@app.route('/api/analytics/usage-forecast/export')
def export_usage_forecast():
    """Export usage & forecast as CSV"""
    from flask import make_response

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, SUM(quantity_received) as total_qty
        FROM invoice_line_items
        GROUP BY ingredient_name
        ORDER BY total_qty DESC
        LIMIT 5
    """)

    top_ingredients = [row['ingredient_name'] for row in cursor.fetchall()]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Ingredient', 'Actual Usage', 'Forecast'])

    for ingredient in top_ingredients:
        cursor.execute("""
            SELECT DATE(i.invoice_date) as date,
                   SUM(ili.quantity_received) as qty
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name = ?
            GROUP BY DATE(i.invoice_date)
            ORDER BY date
        """, (ingredient,))

        results = cursor.fetchall()

        if len(results) >= 2:
            # Simple linear forecast
            y_vals = [float(row['qty']) for row in results]
            avg_usage = sum(y_vals) / len(y_vals)

            for i, row in enumerate(results):
                forecast = avg_usage  # Simplified - could use actual linear regression
                writer.writerow([
                    row['date'],
                    ingredient,
                    f"{float(row['qty']):.2f}",
                    f"{forecast:.2f}"
                ])

    conn.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=usage_forecast.csv'
    return response

@app.route('/api/analytics/recipe-cost-trajectory/export')
def export_recipe_cost_trajectory():
    """Export recipe cost trajectory as CSV"""
    from flask import make_response

    product_id = request.args.get('product_id', type=int)

    if not product_id:
        response = make_response("Product ID required")
        response.status_code = 400
        return response

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    cursor_inv.execute("""
        SELECT r.ingredient_id, r.quantity_needed, i.ingredient_name
        FROM recipes r
        JOIN ingredients i ON r.ingredient_id = i.id
        WHERE r.product_id = ?
    """, (product_id,))

    recipe_items = cursor_inv.fetchall()
    conn_inv.close()

    if not recipe_items:
        response = make_response("No recipe found")
        response.status_code = 404
        return response

    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Total Recipe Cost'])

    cursor_invoices.execute("""
        SELECT DISTINCT DATE(invoice_date) as date
        FROM invoices
        ORDER BY date
    """)

    dates = [row['date'] for row in cursor_invoices.fetchall()]

    for date in dates:
        total_cost = 0
        for item in recipe_items:
            cursor_invoices.execute("""
                SELECT AVG(ili.unit_price) as avg_price
                FROM invoice_line_items ili
                JOIN invoices i ON ili.invoice_id = i.id
                WHERE ili.ingredient_name = ?
                AND DATE(i.invoice_date) <= ?
            """, (item['ingredient_name'], date))

            row = cursor_invoices.fetchone()
            if row and row['avg_price']:
                total_cost += float(row['avg_price']) * float(item['quantity_needed'])

        writer.writerow([date, f"${total_cost:.2f}"])

    conn_invoices.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=recipe_cost_trajectory.csv'
    return response

@app.route('/api/analytics/substitution-opportunities/export')
def export_substitution_opportunities():
    """Export ingredient substitution opportunities as CSV"""
    from flask import make_response

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    cursor_inv.execute("""
        SELECT DISTINCT category
        FROM ingredients
        WHERE category IS NOT NULL AND active = 1
    """)

    categories = [row['category'] for row in cursor_inv.fetchall()]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Category', 'Ingredient', 'Unit Cost', 'Potential Savings'])

    for category in categories:
        cursor_inv.execute("""
            SELECT ingredient_name, COALESCE(unit_cost, 0) as unit_cost
            FROM ingredients
            WHERE category = ? AND active = 1
            ORDER BY unit_cost
        """, (category,))

        items = cursor_inv.fetchall()

        if len(items) >= 2:
            cheapest = items[0]
            for item in items[1:]:
                savings = float(item['unit_cost']) - float(cheapest['unit_cost'])
                if savings > 0:
                    writer.writerow([
                        category,
                        f"{item['ingredient_name']} → {cheapest['ingredient_name']}",
                        f"${float(item['unit_cost']):.2f}",
                        f"${savings:.2f} per unit"
                    ])

    conn_inv.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=substitution_opportunities.csv'
    return response

@app.route('/api/analytics/cost-drivers/export')
def export_cost_drivers():
    """Export cost drivers analysis as CSV"""
    from flask import make_response

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    cursor_inv.execute("""
        SELECT DISTINCT category
        FROM ingredients
        WHERE category IS NOT NULL
        ORDER BY category
    """)

    categories = [row['category'] for row in cursor_inv.fetchall()]
    category_map = {}

    for category in categories:
        cursor_inv.execute("SELECT ingredient_name FROM ingredients WHERE category = ? AND active = 1", (category,))
        ingredients = [row['ingredient_name'] for row in cursor_inv.fetchall()]
        category_map[category] = ingredients

    conn_inv.close()

    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_invoices = conn_invoices.cursor()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Category', 'Trend', 'Slope', 'Avg Spending'])

    for category in categories[:6]:
        ingredients_in_cat = category_map.get(category, [])
        if not ingredients_in_cat:
            continue

        placeholders = ','.join('?' * len(ingredients_in_cat))
        query = f"""
            SELECT DATE(i.invoice_date) as date, SUM(ili.total_price) as total
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_name IN ({placeholders})
            GROUP BY DATE(i.invoice_date)
            ORDER BY date
        """

        cursor_invoices.execute(query, ingredients_in_cat)
        results = cursor_invoices.fetchall()

        if results and len(results) >= 3:
            x_vals = list(range(len(results)))
            y_vals = [float(row['total']) for row in results]

            n = len(x_vals)
            sum_x = sum(x_vals)
            sum_y = sum(y_vals)
            sum_xy = sum(x_vals[i] * y_vals[i] for i in range(n))
            sum_x2 = sum(x * x for x in x_vals)

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
            avg_spend = sum_y / n
            trend = 'INCREASING' if slope > 0 else 'DECREASING'

            writer.writerow([
                category,
                trend,
                f"{slope:+.2f}",
                f"${avg_spend:,.2f}"
            ])

    conn_invoices.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=cost_drivers.csv'
    return response

@app.route('/api/analytics/purchase-frequency/export')
def export_purchase_frequency():
    """Export purchase frequency as CSV"""
    from flask import make_response

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name,
               COUNT(*) as purchase_count,
               AVG(quantity_received) as avg_quantity,
               MIN(DATE(invoice_date)) as first_purchase,
               MAX(DATE(invoice_date)) as last_purchase
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        GROUP BY ingredient_name
        ORDER BY purchase_count DESC
        LIMIT 20
    """)

    results = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Purchase Count', 'Avg Quantity', 'First Purchase', 'Last Purchase'])

    for row in results:
        writer.writerow([
            row['ingredient_name'],
            row['purchase_count'],
            f"{float(row['avg_quantity']):.2f}",
            row['first_purchase'],
            row['last_purchase']
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=purchase_frequency.csv'
    return response

# Register CRUD routes
register_crud_routes(app)

# Register Sales Processing routes (Layer 4)
register_sales_routes(app, get_db_connection, INVENTORY_DB)

# Register Sales Analytics routes
register_analytics_routes(app, get_db_connection, INVENTORY_DB)

# Register Barcode Scanner routes
register_barcode_routes(app, get_db_connection, INVENTORY_DB)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🔥 FIRING UP INVENTORY DASHBOARD")
    print("="*60)

    # Run database migrations
    print("\n🔧 Checking database schema...")
    migrate_database()

    print("\n📊 Dashboard starting at: http://localhost:5001")
    print("📦 Inventory Database: Connected")
    print("📄 Invoices Database: Connected")
    print("\n⌨️  Press CTRL+C to stop the server\n")
    print("="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5001)
