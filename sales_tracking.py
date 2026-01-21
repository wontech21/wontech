"""
Sales Tracking Endpoints for Inventory Management
Handles uploading daily sales spreadsheets and automatically adjusting inventory
"""

from flask import request, jsonify
from datetime import datetime
import sqlite3
import csv
import io

INVENTORY_DB = 'inventory.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def log_audit(action_type, entity_type, entity_reference, details):
    """Log action to audit_log table"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log
        (timestamp, action_type, entity_type, entity_reference, details, user, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        action_type,
        entity_type,
        entity_reference,
        details,
        request.remote_addr or 'System',
        request.remote_addr or 'localhost'
    ))
    conn.commit()
    conn.close()

def register_sales_routes(app):
    """Register sales tracking routes with Flask app"""

    @app.route('/api/sales/upload', methods=['POST'])
    def upload_sales_data():
        """
        Upload sales data CSV and automatically adjust inventory

        Expected CSV format:
        product_code,product_name,quantity_sold,sale_date,sale_price
        """
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400

        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)

            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            processed_sales = []
            errors = []
            total_sold = 0
            total_revenue = 0

            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                try:
                    product_code = row.get('product_code', '').strip()
                    quantity_sold = float(row.get('quantity_sold', 0))
                    sale_date = row.get('sale_date', datetime.now().strftime('%Y-%m-%d')).strip()
                    sale_price = float(row.get('sale_price', 0))

                    if not product_code or quantity_sold <= 0:
                        errors.append(f"Row {row_num}: Invalid product_code or quantity")
                        continue

                    # Find product
                    cursor.execute("""
                        SELECT id, product_name, selling_price
                        FROM products
                        WHERE product_code = ?
                    """, (product_code,))

                    product = cursor.fetchone()
                    if not product:
                        errors.append(f"Row {row_num}: Product '{product_code}' not found")
                        continue

                    product_id = product['id']
                    product_name = product['product_name']

                    # Get recipe for this product
                    cursor.execute("""
                        SELECT r.ingredient_id, r.quantity_needed, i.ingredient_name,
                               i.quantity_on_hand, i.unit_of_measure,
                               COALESCE(i.is_composite, 0) as is_composite
                        FROM recipes r
                        JOIN ingredients i ON r.ingredient_id = i.id
                        WHERE r.product_id = ? AND i.active = 1
                    """, (product_id,))

                    recipe_items = cursor.fetchall()

                    if not recipe_items:
                        errors.append(f"Row {row_num}: No recipe found for '{product_name}'")
                        continue

                    # Build complete ingredient list (expanding composites)
                    all_ingredients_to_deduct = []

                    for item in recipe_items:
                        if item['is_composite']:
                            # For composite ingredients, we need to scale the base ingredients
                            # based on how much of the composite ingredient is needed

                            # Get the batch size for this composite ingredient
                            cursor.execute("""
                                SELECT batch_size FROM ingredients WHERE id = ?
                            """, (item['ingredient_id'],))
                            batch_result = cursor.fetchone()
                            batch_output_size = batch_result['batch_size'] if batch_result and batch_result['batch_size'] else 1

                            # Get base ingredients for this composite
                            cursor.execute("""
                                SELECT bi.id as ingredient_id,
                                       bi.ingredient_name,
                                       ir.quantity_needed,
                                       ir.unit_of_measure,
                                       bi.quantity_on_hand
                                FROM ingredient_recipes ir
                                JOIN ingredients bi ON ir.base_ingredient_id = bi.id
                                WHERE ir.composite_ingredient_id = ?
                            """, (item['ingredient_id'],))

                            base_ingredients = cursor.fetchall()

                            # Calculate scale factor: quantity needed / batch output size
                            # Example: Pizza needs 4 oz sauce, batch makes 128 oz, scale = 4/128 = 0.03125
                            scale_factor = item['quantity_needed'] / batch_output_size

                            # Scale each base ingredient
                            for base_ing in base_ingredients:
                                scaled_ingredient = dict(base_ing)
                                scaled_ingredient['quantity_needed'] = base_ing['quantity_needed'] * scale_factor
                                all_ingredients_to_deduct.append(scaled_ingredient)
                        else:
                            # Regular ingredient
                            all_ingredients_to_deduct.append(item)

                    # Check if we have enough inventory
                    insufficient_stock = []
                    for item in all_ingredients_to_deduct:
                        required_qty = item['quantity_needed'] * quantity_sold
                        if item['quantity_on_hand'] < required_qty:
                            insufficient_stock.append(
                                f"{item['ingredient_name']}: need {required_qty:.2f}, have {item['quantity_on_hand']:.2f}"
                            )

                    if insufficient_stock:
                        errors.append(f"Row {row_num}: Insufficient stock for '{product_name}': {'; '.join(insufficient_stock)}")
                        continue

                    # Deduct ingredients from inventory
                    deductions = []
                    for item in all_ingredients_to_deduct:
                        deduction_qty = item['quantity_needed'] * quantity_sold
                        new_qty = item['quantity_on_hand'] - deduction_qty

                        cursor.execute("""
                            UPDATE ingredients
                            SET quantity_on_hand = ?,
                                last_updated = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (new_qty, item['ingredient_id']))

                        deductions.append(f"{item['ingredient_name']}: -{deduction_qty:.2f} {item['unit_of_measure']}")

                    # Record successful sale
                    processed_sales.append({
                        'product_code': product_code,
                        'product_name': product_name,
                        'quantity_sold': quantity_sold,
                        'sale_date': sale_date,
                        'revenue': sale_price * quantity_sold,
                        'deductions': deductions
                    })

                    total_sold += quantity_sold
                    total_revenue += sale_price * quantity_sold

                    # Log to audit trail
                    details = f"Sold {quantity_sold} x {product_name}. Deductions: {'; '.join(deductions)}"
                    cursor.execute("""
                        INSERT INTO audit_log
                        (timestamp, action_type, entity_type, entity_reference, details, user, ip_address)
                        VALUES (?, 'SALE_RECORDED', 'product', ?, ?, ?, ?)
                    """, (
                        sale_date + ' 00:00:00',
                        product_name,
                        details,
                        request.remote_addr or 'System',
                        request.remote_addr or 'localhost'
                    ))

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue

            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'processed': len(processed_sales),
                'errors_count': len(errors),
                'errors': errors,
                'sales': processed_sales,
                'summary': {
                    'total_items_sold': total_sold,
                    'total_revenue': round(total_revenue, 2)
                }
            })

        except Exception as e:
            return jsonify({'error': f'Failed to process file: {str(e)}'}), 500

    @app.route('/api/sales/summary')
    def get_sales_summary():
        """Get sales summary statistics"""
        days = int(request.args.get('days', 30))

        conn = get_db_connection(INVENTORY_DB)
        cursor = conn.cursor()

        # Get sales from audit log
        cursor.execute("""
            SELECT
                COUNT(*) as total_sales,
                entity_reference as product_name
            FROM audit_log
            WHERE action_type = 'SALE_RECORDED'
              AND timestamp >= date('now', '-' || ? || ' days')
            GROUP BY entity_reference
            ORDER BY total_sales DESC
            LIMIT 10
        """, (days,))

        top_products = [dict(row) for row in cursor.fetchall()]

        # Get recent sales
        cursor.execute("""
            SELECT
                timestamp,
                entity_reference as product_name,
                details
            FROM audit_log
            WHERE action_type = 'SALE_RECORDED'
            ORDER BY timestamp DESC
            LIMIT 20
        """)

        recent_sales = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return jsonify({
            'top_products': top_products,
            'recent_sales': recent_sales
        })

    return app
