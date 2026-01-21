"""
Sales Processing Operations
Handles sales CSV import, inventory deductions, and sales tracking
"""

from flask import request, jsonify
import csv
import io
from datetime import datetime


def register_sales_routes(app, get_db_connection, INVENTORY_DB):
    """Register all sales processing routes"""

    @app.route('/api/sales/preview', methods=['POST'])
    def preview_sales():
        """Preview what inventory deductions will happen (doesn't modify data)"""
        data = request.json
        sales_data = data.get('sales_data', [])
        sale_date = data.get('sale_date', datetime.now().strftime('%Y-%m-%d'))

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            results = {
                'matched': [],
                'unmatched': [],
                'deductions': [],
                'warnings': [],
                'totals': {
                    'revenue': 0,
                    'cost': 0,
                    'profit': 0
                }
            }

            for sale in sales_data:
                product_name = sale.get('product_name', '').strip()
                quantity_sold = float(sale.get('quantity', 0))
                retail_price = sale.get('retail_price')

                if not product_name or quantity_sold <= 0:
                    continue

                # Find product by name (case-insensitive)
                cursor.execute("""
                    SELECT id, product_name, selling_price
                    FROM products
                    WHERE LOWER(product_name) = LOWER(?)
                """, (product_name,))
                product = cursor.fetchone()

                if not product:
                    results['unmatched'].append({
                        'product_name': product_name,
                        'quantity': quantity_sold,
                        'reason': 'Product not found in database'
                    })
                    continue

                product_id = product['id']
                product_name = product['product_name']
                original_price = float(product['selling_price'])

                # Use retail_price if provided, otherwise use database price
                actual_retail_price = retail_price if retail_price is not None else original_price

                # Revenue = retail_price × quantity
                actual_revenue = actual_retail_price * quantity_sold

                # Sale price is the retail price
                sale_price = actual_retail_price

                # Calculate discount info (if sale price differs from database price)
                discount_amount = (original_price - sale_price) * quantity_sold
                discount_percent = ((original_price - sale_price) / original_price * 100) if original_price > 0 else 0

                # Get recipe
                cursor.execute("""
                    SELECT
                        r.ingredient_id,
                        r.quantity_needed,
                        r.unit_of_measure,
                        i.ingredient_name,
                        i.unit_cost,
                        i.quantity_on_hand,
                        i.reorder_level
                    FROM recipes r
                    JOIN ingredients i ON r.ingredient_id = i.id
                    WHERE r.product_id = ?
                """, (product_id,))
                recipe = cursor.fetchall()

                if not recipe:
                    results['warnings'].append(f"⚠️ {product_name} has no recipe - no inventory will be deducted")

                # Calculate deductions and costs
                product_cost = 0
                ingredient_deductions = []

                for ingredient in recipe:
                    quantity_needed = ingredient['quantity_needed'] * quantity_sold
                    ingredient_cost = ingredient['unit_cost'] * quantity_needed
                    product_cost += ingredient_cost

                    new_quantity = ingredient['quantity_on_hand'] - quantity_needed

                    ingredient_deductions.append({
                        'ingredient_id': ingredient['ingredient_id'],
                        'ingredient_name': ingredient['ingredient_name'],
                        'current_qty': ingredient['quantity_on_hand'],
                        'deduction': quantity_needed,
                        'new_qty': new_quantity,
                        'unit': ingredient['unit_of_measure'],
                        'cost': ingredient_cost
                    })

                    # Check for low stock warning
                    if new_quantity < 0:
                        results['warnings'].append(
                            f"❌ {ingredient['ingredient_name']} will go NEGATIVE "
                            f"({new_quantity:.2f} {ingredient['unit_of_measure']})"
                        )
                    elif ingredient['reorder_level'] and new_quantity < ingredient['reorder_level']:
                        results['warnings'].append(
                            f"⚠️ {ingredient['ingredient_name']} will drop below reorder level "
                            f"({new_quantity:.2f} < {ingredient['reorder_level']} {ingredient['unit_of_measure']})"
                        )

                # Calculate gross profit
                gross_profit = actual_revenue - product_cost

                results['matched'].append({
                    'product_id': product_id,
                    'product_name': product_name,
                    'quantity_sold': quantity_sold,
                    'original_price': original_price,
                    'retail_price': actual_retail_price,
                    'sale_price': sale_price,
                    'discount_amount': discount_amount,
                    'discount_percent': discount_percent,
                    'revenue': actual_revenue,
                    'cost': product_cost,
                    'profit': gross_profit,
                    'ingredients': ingredient_deductions
                })

                # Update totals
                results['totals']['revenue'] += actual_revenue
                results['totals']['cost'] += product_cost
                results['totals']['profit'] += gross_profit

            conn.close()

            return jsonify({
                'success': True,
                'preview': results
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/sales/apply', methods=['POST'])
    def apply_sales():
        """Apply sales and deduct inventory (MODIFIES DATA)"""
        data = request.json
        sales_data = data.get('sales_data', [])
        sale_date = data.get('sale_date', datetime.now().strftime('%Y-%m-%d'))
        sale_time = data.get('sale_time', '')

        conn = None
        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            applied_count = 0
            total_revenue = 0
            total_cost = 0

            for sale in sales_data:
                product_name = sale.get('product_name', '').strip()
                quantity_sold = float(sale.get('quantity', 0))
                # Use individual sale time if provided, otherwise use global time
                item_sale_time = sale.get('sale_time', sale_time)
                retail_price = sale.get('retail_price')

                if not product_name or quantity_sold <= 0:
                    continue

                # Find product
                cursor.execute("""
                    SELECT id, product_name, selling_price
                    FROM products
                    WHERE LOWER(product_name) = LOWER(?)
                """, (product_name,))
                product = cursor.fetchone()

                if not product:
                    continue  # Skip unmatched products

                product_id = product['id']
                original_price = float(product['selling_price'])

                # Use retail_price if provided, otherwise use database price
                actual_retail_price = retail_price if retail_price is not None else original_price

                # Revenue = retail_price × quantity
                actual_revenue = actual_retail_price * quantity_sold

                # Sale price is the retail price
                sale_price = actual_retail_price

                # Calculate discount info (if sale price differs from database price)
                discount_amount = (original_price - sale_price) * quantity_sold
                discount_percent = ((original_price - sale_price) / original_price * 100) if original_price > 0 else 0

                # Get recipe
                cursor.execute("""
                    SELECT
                        r.ingredient_id,
                        r.quantity_needed,
                        i.unit_cost
                    FROM recipes r
                    JOIN ingredients i ON r.ingredient_id = i.id
                    WHERE r.product_id = ?
                """, (product_id,))
                recipe = cursor.fetchall()

                # Deduct ingredients from inventory
                product_cost = 0
                for ingredient in recipe:
                    quantity_needed = ingredient['quantity_needed'] * quantity_sold
                    ingredient_cost = ingredient['unit_cost'] * quantity_needed
                    product_cost += ingredient_cost

                    # UPDATE inventory
                    cursor.execute("""
                        UPDATE ingredients
                        SET quantity_on_hand = quantity_on_hand - ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (quantity_needed, ingredient['ingredient_id']))

                # Record sale in history
                # Revenue = retail_price × quantity
                gross_profit = actual_revenue - product_cost

                cursor.execute("""
                    INSERT INTO sales_history (
                        sale_date, sale_time, product_id, product_name, quantity_sold,
                        revenue, cost_of_goods, gross_profit,
                        original_price, sale_price, discount_amount, discount_percent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sale_date,
                    item_sale_time,
                    product_id,
                    product['product_name'],
                    quantity_sold,
                    actual_revenue,
                    product_cost,
                    gross_profit,
                    original_price,
                    sale_price,
                    discount_amount,
                    discount_percent
                ))

                applied_count += 1
                total_revenue += actual_revenue
                total_cost += product_cost

            conn.commit()

            return jsonify({
                'success': True,
                'message': f'Successfully processed {applied_count} sales',
                'summary': {
                    'sales_processed': applied_count,
                    'total_revenue': round(total_revenue, 2),
                    'total_cost': round(total_cost, 2),
                    'total_profit': round(total_revenue - total_cost, 2)
                }
            })

        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()

    @app.route('/api/sales/parse-csv', methods=['POST'])
    def parse_csv():
        """Parse CSV data into sales format"""
        data = request.json
        csv_text = data.get('csv_text', '')

        try:
            # Parse CSV
            lines = csv_text.strip().split('\n')
            if not lines:
                return jsonify({
                    'success': True,
                    'sales_data': [],
                    'count': 0
                })

            sales_data = []

            # Check if first line looks like a header
            first_line = lines[0].lower()
            has_header = any(word in first_line for word in ['product', 'item', 'name', 'quantity', 'qty'])

            if has_header:
                # Use DictReader for CSV with headers
                csv_reader = csv.DictReader(io.StringIO(csv_text))

                for row in csv_reader:
                    # Look for product name column
                    product_name = None
                    for key in row.keys():
                        key_lower = key.lower()
                        if any(word in key_lower for word in ['product', 'item', 'name']):
                            product_name = row[key]
                            break

                    # Look for quantity column
                    quantity = None
                    for key in row.keys():
                        key_lower = key.lower()
                        if any(word in key_lower for word in ['quantity', 'qty', 'sold', 'count']):
                            try:
                                quantity = float(row[key])
                            except:
                                continue
                            break

                    # Look for retail_price column
                    retail_price = None
                    for key in row.keys():
                        key_lower = key.lower()
                        if any(word in key_lower for word in ['retail_price', 'retail price', 'unit_price', 'price']):
                            try:
                                retail_price = float(row[key])
                            except:
                                pass
                            break

                    # Look for time column
                    sale_time = None
                    for key in row.keys():
                        key_lower = key.lower()
                        if 'time' in key_lower:
                            sale_time = row[key].strip()
                            break

                    if product_name and quantity:
                        sale_entry = {
                            'product_name': product_name.strip(),
                            'quantity': quantity
                        }
                        if retail_price is not None:
                            sale_entry['retail_price'] = retail_price
                        if sale_time:
                            sale_entry['sale_time'] = sale_time
                        sales_data.append(sale_entry)
            else:
                # Parse as: Product, Quantity, Retail_Price, Time
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        product_name = parts[0]
                        try:
                            quantity = float(parts[1])
                            sale_entry = {
                                'product_name': product_name,
                                'quantity': quantity
                            }
                            # Retail price (index 2)
                            if len(parts) >= 3 and parts[2]:
                                try:
                                    sale_entry['retail_price'] = float(parts[2])
                                except:
                                    pass
                            # Time (index 3)
                            if len(parts) >= 4 and parts[3]:
                                sale_entry['sale_time'] = parts[3]

                            sales_data.append(sale_entry)
                        except ValueError:
                            # Skip lines where quantity isn't a number
                            continue

            return jsonify({
                'success': True,
                'sales_data': sales_data,
                'count': len(sales_data)
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/sales/history')
    def get_sales_history():
        """Get sales history with optional filters and pagination"""
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        product_id = request.args.get('product_id')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            # Count total records
            count_query = "SELECT COUNT(*) as total FROM sales_history WHERE 1=1"
            count_params = []

            if start_date:
                count_query += " AND sale_date >= ?"
                count_params.append(start_date)

            if end_date:
                count_query += " AND sale_date <= ?"
                count_params.append(end_date)

            if product_id:
                count_query += " AND product_id = ?"
                count_params.append(product_id)

            cursor.execute(count_query, count_params)
            total_records = cursor.fetchone()['total']

            # Get paginated data
            query = """
                SELECT
                    id,
                    sale_date,
                    sale_time,
                    product_name,
                    quantity_sold,
                    revenue,
                    cost_of_goods,
                    gross_profit,
                    original_price,
                    sale_price,
                    discount_amount,
                    discount_percent,
                    processed_date
                FROM sales_history
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND sale_date >= ?"
                params.append(start_date)

            if end_date:
                query += " AND sale_date <= ?"
                params.append(end_date)

            if product_id:
                query += " AND product_id = ?"
                params.append(product_id)

            query += " ORDER BY sale_date DESC, processed_date DESC"
            query += f" LIMIT {per_page} OFFSET {(page - 1) * per_page}"

            cursor.execute(query, params)
            history = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return jsonify({
                'data': history,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_records': total_records,
                    'total_pages': (total_records + per_page - 1) // per_page
                }
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/sales/summary')
    def get_sales_summary():
        """Get sales summary statistics"""
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        try:
            conn = get_db_connection(INVENTORY_DB)
            cursor = conn.cursor()

            query = """
                SELECT
                    COUNT(*) as total_transactions,
                    SUM(quantity_sold) as total_units,
                    SUM(revenue) as total_revenue,
                    SUM(cost_of_goods) as total_cost,
                    SUM(gross_profit) as total_profit,
                    AVG(gross_profit / revenue * 100) as avg_margin_pct
                FROM sales_history
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND sale_date >= ?"
                params.append(start_date)

            if end_date:
                query += " AND sale_date <= ?"
                params.append(end_date)

            cursor.execute(query, params)
            summary = dict(cursor.fetchone())

            # Get top products
            cursor.execute("""
                SELECT
                    product_name,
                    SUM(quantity_sold) as total_sold,
                    SUM(revenue) as total_revenue,
                    SUM(gross_profit) as total_profit
                FROM sales_history
                GROUP BY product_name
                ORDER BY total_revenue DESC
                LIMIT 10
            """)
            top_products = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return jsonify({
                'summary': summary,
                'top_products': top_products
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
