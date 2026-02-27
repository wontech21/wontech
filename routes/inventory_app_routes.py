from flask import Blueprint, jsonify, request, g, make_response
import sqlite3, csv, io, json, os
from datetime import datetime
from db_manager import get_org_db
from utils.audit import log_audit
from middleware.tenant_context_separate_db import login_required, organization_required, organization_admin_required
from inventory_warnings import preview_quantity_change, preview_count_changes, check_inventory_warnings, format_warning_message

inventory_app_bp = Blueprint('inventory_app', __name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def update_ingredient_prices(ingredient_code, cursor_invoices, cursor_inventory):
    """Update last_unit_price and average_unit_price for an ingredient based on invoice history"""
    try:
        # Get all prices for this ingredient from invoice line items, ordered by invoice date (most recent first)
        cursor_invoices.execute("""
            SELECT ili.unit_price, i.invoice_date, ili.quantity
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_code = ?
            ORDER BY i.invoice_date DESC
        """, (ingredient_code,))

        price_records = cursor_invoices.fetchall()

        if price_records:
            # Last price is the most recent (first in the list)
            last_price = price_records[0]['unit_price']

            # Calculate weighted average price (weighted by quantity received)
            total_cost = sum(rec['unit_price'] * rec['quantity'] for rec in price_records)
            total_quantity = sum(rec['quantity'] for rec in price_records)
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

# ============================================================================
# INVENTORY VIEW ENDPOINTS
# ============================================================================

@inventory_app_bp.route('/api/inventory/aggregated')
def get_aggregated_inventory():
    """Get aggregated inventory (totals across all brands)"""
    conn = get_org_db()
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
    return jsonify({'success': True, 'items': items})

@inventory_app_bp.route('/api/inventory/detailed')
def get_detailed_inventory():
    """Get detailed inventory (individual brand/supplier lines)"""
    ingredient = request.args.get('ingredient', 'all')
    supplier = request.args.get('supplier', 'all')
    brand = request.args.get('brand', 'all')
    category = request.args.get('category', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    status = request.args.get('status', 'active')  # active, inactive, or all

    conn = get_org_db()
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
            active,
            barcode
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

@inventory_app_bp.route('/api/inventory/consolidated')
def get_consolidated_inventory():
    """
    Get consolidated inventory grouped by ingredient_name.
    Shows one row per ingredient with all brand/supplier variants.
    Aggregates quantities and provides variant details for dropdown selection.
    """
    category = request.args.get('category', 'all')
    status = request.args.get('status', 'active')
    search = request.args.get('search', '')

    conn = get_org_db()
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

# ============================================================================
# FILTER ENDPOINTS
# ============================================================================

@inventory_app_bp.route('/api/filters/suppliers')
def get_suppliers():
    """Get list of all suppliers from suppliers table"""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT supplier_name FROM suppliers ORDER BY supplier_name")
    suppliers = [row['supplier_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(suppliers)

@inventory_app_bp.route('/api/filters/brands')
def get_brands():
    """Get list of all brands from brands table"""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM brands ORDER BY brand_name")
    brands = [row['brand_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(brands)

@inventory_app_bp.route('/api/filters/categories')
def get_categories():
    """Get list of all categories from the categories table"""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT category_name FROM categories ORDER BY category_name")
    categories = [row['category_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(categories)

@inventory_app_bp.route('/api/filters/ingredients')
def get_ingredients():
    """Get list of all unique ingredient names"""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ingredient_name FROM ingredients ORDER BY ingredient_name")
    ingredients = [row['ingredient_name'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(ingredients)

# ============================================================================
# INVENTORY SUMMARY
# ============================================================================

@inventory_app_bp.route('/api/inventory/summary')
def get_inventory_summary():
    """Get inventory summary statistics"""
    conn = get_org_db()
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

# ============================================================================
# INVOICE ENDPOINTS
# ============================================================================

@inventory_app_bp.route('/api/invoices/unreconciled')
@login_required
@organization_required
def get_unreconciled_invoices():
    """Get list of unreconciled invoices"""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM unreconciled_invoices")
    invoices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(invoices)

@inventory_app_bp.route('/api/invoices/recent')
@login_required
@organization_required
def get_recent_invoices():
    """Get recent invoices with optional date filtering"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
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

    # Get total count (separate query, no LIMIT)
    count_query = "SELECT COUNT(*) as total_count FROM invoices WHERE 1=1"
    count_params = []
    if date_from:
        count_query += " AND invoice_date >= ?"
        count_params.append(date_from)
    if date_to:
        count_query += " AND invoice_date <= ?"
        count_params.append(date_to)
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()['total_count']

    query += " ORDER BY invoice_date DESC LIMIT 100"

    cursor.execute(query, params)
    invoices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'invoices': invoices, 'total_count': total_count})

@inventory_app_bp.route('/api/invoices/<invoice_number>')
@login_required
@organization_required
def get_invoice_details(invoice_number):
    """Get invoice details with line items"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/invoices/create', methods=['POST'])
@login_required
@organization_required
def create_invoice():
    """Create a new invoice with line items and add to inventory"""
    data = request.json

    conn_invoices = get_org_db()
    cursor_invoices = conn_invoices.cursor()

    conn_inventory = get_org_db()
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

@inventory_app_bp.route('/api/invoices/import', methods=['POST'])
@login_required
@organization_required
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
    conn_inv = get_org_db()
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
        conn_invoices = get_org_db()
        cursor_invoices = conn_invoices.cursor()

        conn_inventory = get_org_db()
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

@inventory_app_bp.route('/api/invoices/<invoice_number>/payment-status', methods=['PUT'])
@login_required
@organization_required
def update_invoice_payment_status(invoice_number):
    """Update the payment status of an invoice"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/invoices/delete/<invoice_number>', methods=['DELETE'])
@login_required
@organization_required
def delete_invoice(invoice_number):
    """Delete an invoice and reverse inventory changes"""
    conn_inv = get_org_db()
    cursor_inv = conn_inv.cursor()

    conn_inventory = get_org_db()
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
# PRODUCT / RECIPE ENDPOINTS
# ============================================================================

@inventory_app_bp.route('/api/products/all')
def get_products():
    """Get all products"""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY category, product_name")
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(products)

@inventory_app_bp.route('/api/products/costs')
def get_product_costs():
    """Get product costs and margins - includes products without recipes"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/recipes/all')
def get_all_recipes():
    """Get all recipes with ingredients including composite breakdown"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/recipes/by-product/<product_name>')
def get_recipe_by_product(product_name):
    """Get recipe for a specific product with composite ingredient breakdown"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/ingredients/composite/<int:ingredient_id>')
def get_composite_ingredient_recipe(ingredient_id):
    """Get recipe for a composite ingredient"""
    conn = get_org_db()
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

# ============================================================================
# INVENTORY ITEM OPERATIONS
# ============================================================================

@inventory_app_bp.route('/api/inventory/category-preview/<category>')
def get_category_preview(category):
    """Get 5 item preview for a category"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/inventory/item/<int:item_id>', methods=['GET'])
def get_inventory_item(item_id):
    """Get a single inventory item by ID"""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingredients WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if item:
        return jsonify(dict(item))
    return jsonify({'error': 'Item not found'}), 404

@inventory_app_bp.route('/api/inventory/item/<int:item_id>', methods=['PUT'])
def update_inventory_item(item_id):
    """Update an inventory item"""
    data = request.json
    conn = get_org_db()
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

@inventory_app_bp.route('/api/inventory/item/<int:item_id>/preview-update', methods=['POST'])
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

    conn = get_org_db()

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

@inventory_app_bp.route('/api/inventory/item/<int:item_id>/toggle-active', methods=['PUT'])
def toggle_item_active_status(item_id):
    """Toggle active/inactive status of an inventory item"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/inventory/bulk-update-brand', methods=['POST'])
def bulk_update_brand():
    """Update brand name across all databases"""
    data = request.json
    old_brand = data.get('old_brand')
    new_brand = data.get('new_brand')

    # Update inventory database
    conn_inv = get_org_db()
    cursor_inv = conn_inv.cursor()

    # Update invoices database
    conn_inv_db = get_org_db()
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

@inventory_app_bp.route('/api/inventory/update-category', methods=['POST'])
def update_category():
    """Update category for one or more items"""
    data = request.json
    item_ids = data.get('item_ids', [])
    new_category = data.get('new_category')

    if not item_ids or not new_category:
        return jsonify({'success': False, 'error': 'Missing item_ids or new_category'}), 400

    conn = get_org_db()
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

# ============================================================================
# CATEGORY MANAGEMENT ENDPOINTS
# ============================================================================

@inventory_app_bp.route('/api/categories/all', methods=['GET'])
def get_all_categories():
    """Get all categories with usage counts"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/categories/create', methods=['POST'])
def create_category():
    """Create a new category"""
    data = request.json
    category_name = data.get('category_name')

    if not category_name or not category_name.strip():
        return jsonify({'success': False, 'error': 'Category name is required'}), 400

    conn = get_org_db()
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

@inventory_app_bp.route('/api/categories/update/<int:category_id>', methods=['PUT'])
def update_category_name(category_id):
    """Update a category name and cascade to all items using it"""
    data = request.json
    new_name = data.get('category_name')

    if not new_name or not new_name.strip():
        return jsonify({'success': False, 'error': 'Category name is required'}), 400

    conn = get_org_db()
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

@inventory_app_bp.route('/api/categories/delete/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Delete a category"""
    conn = get_org_db()
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

# ============================================================================
# BULK OPERATIONS
# ============================================================================

@inventory_app_bp.route('/api/inventory/bulk-update-supplier', methods=['POST'])
def bulk_update_supplier():
    """Update supplier name across all databases"""
    data = request.json
    old_supplier = data.get('old_supplier')
    new_supplier = data.get('new_supplier')

    # Update inventory database
    conn_inv = get_org_db()
    cursor_inv = conn_inv.cursor()

    # Update invoices database
    conn_inv_db = get_org_db()
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

# ============================================================================
# SUPPLIER MANAGEMENT ENDPOINTS
# ============================================================================

@inventory_app_bp.route('/api/suppliers/all', methods=['GET'])
def get_all_suppliers():
    """Get all suppliers with full details"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/suppliers/create', methods=['POST'])
def create_supplier():
    """Create a new supplier"""
    data = request.json
    conn = get_org_db()
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

@inventory_app_bp.route('/api/suppliers/update/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    """Update a supplier and cascade changes globally"""
    data = request.json
    new_supplier_name = data['supplier_name']

    conn_inv = get_org_db()
    cursor_inv = conn_inv.cursor()

    conn_invoices = get_org_db()
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

@inventory_app_bp.route('/api/suppliers/delete/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    """Delete a supplier"""
    conn = get_org_db()
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

# ============================================================================
# INVENTORY COUNT ENDPOINTS
# ============================================================================

@inventory_app_bp.route('/api/counts/all', methods=['GET'])
def get_all_counts():
    """Get all inventory counts with optional date filtering"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
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

@inventory_app_bp.route('/api/counts/<int:count_id>', methods=['GET'])
def get_count_details(count_id):
    """Get detailed information for a specific count"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/counts/preview', methods=['POST'])
def preview_count():
    """
    Preview physical count changes and show warnings BEFORE applying.
    This prevents accidentally setting inventory to incorrect/negative values.
    """
    data = request.json
    count_items = data.get('line_items', [])

    if not count_items:
        return jsonify({'success': False, 'error': 'No count items provided'}), 400

    conn = get_org_db()

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

@inventory_app_bp.route('/api/counts/create', methods=['POST'])
def create_count():
    """Create a new inventory count and reconcile with inventory"""
    data = request.json

    conn = get_org_db()
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

@inventory_app_bp.route('/api/counts/delete/<int:count_id>', methods=['DELETE'])
def delete_count(count_id):
    """Delete an inventory count (does NOT reverse inventory changes)"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/audit/all', methods=['GET'])
def get_all_audit_logs():
    """Get all audit log entries with optional date filtering"""
    conn = get_org_db()
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

@inventory_app_bp.route('/api/audit/stats', methods=['GET'])
def get_audit_stats():
    """Get audit statistics"""
    conn = get_org_db()
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
