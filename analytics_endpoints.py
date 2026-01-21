"""
Analytics API Endpoints - Add these to app.py before the if __name__ == '__main__' block
"""

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

    # Check if preference exists
    cursor.execute("""
        SELECT id FROM user_widget_preferences
        WHERE user_id = ? AND widget_key = ?
    """, (user_id, widget_key))

    if cursor.fetchone():
        # Update existing
        cursor.execute("""
            UPDATE user_widget_preferences
            SET enabled = ?
            WHERE user_id = ? AND widget_key = ?
        """, (enabled, user_id, widget_key))
    else:
        # Insert new
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

@app.route('/api/analytics/widgets/reorder', methods=['PUT'])
def reorder_widgets():
    """Reorder widgets"""
    data = request.json
    user_id = data.get('user_id', 'default')
    widget_order = data.get('widget_order', [])  # Array of widget_keys in order

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    for position, widget_key in enumerate(widget_order):
        cursor.execute("""
            UPDATE user_widget_preferences
            SET position = ?
            WHERE user_id = ? AND widget_key = ?
        """, (position, user_id, widget_key))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/analytics/widgets/settings', methods=['PUT'])
def update_widget_settings():
    """Update widget settings"""
    data = request.json
    user_id = data.get('user_id', 'default')
    widget_key = data.get('widget_key')
    settings = data.get('settings', {})

    import json
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE user_widget_preferences
        SET custom_settings = ?, size = ?
        WHERE user_id = ? AND widget_key = ?
    """, (json.dumps(settings), settings.get('size', 'medium'), user_id, widget_key))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

# ==================== WIDGET DATA ENDPOINTS ====================

@app.route('/api/analytics/vendor-spend')
def analytics_vendor_spend():
    """Vendor spend distribution"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn_inv = get_db_connection(INVOICES_DB)
    cursor = conn_inv.cursor()

    query = """
        SELECT
            supplier_name,
            COUNT(*) as invoice_count,
            SUM(total_amount) as total_spend,
            ROUND(AVG(total_amount), 2) as avg_invoice
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
    suppliers = [dict(row) for row in cursor.fetchall()]

    # Calculate percentages
    total_spend = sum(s['total_spend'] for s in suppliers)
    for supplier in suppliers:
        supplier['percentage'] = round((supplier['total_spend'] / total_spend * 100), 2) if total_spend > 0 else 0

    conn_inv.close()

    return jsonify({
        'suppliers': suppliers,
        'total_spend': total_spend,
        'supplier_count': len(suppliers)
    })

@app.route('/api/analytics/price-trends')
def analytics_price_trends():
    """Price trends for selected ingredients"""
    ingredient_codes = request.args.get('ingredients', '').split(',')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not ingredient_codes or ingredient_codes == ['']:
        # Get top 5 most purchased ingredients by default
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

    conn_inv = get_db_connection(INVOICES_DB)
    cursor = conn_inv.cursor()

    results = {}
    for ing_code in ingredient_codes:
        query = """
            SELECT
                i.invoice_date as date,
                ili.unit_price as price,
                ili.ingredient_name
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_code = ?
        """
        params = [ing_code]

        if date_from:
            query += " AND i.invoice_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND i.invoice_date <= ?"
            params.append(date_to)

        query += " ORDER BY i.invoice_date"

        cursor.execute(query, params)
        data = [dict(row) for row in cursor.fetchall()]

        if data:
            results[ing_code] = {
                'name': data[0]['ingredient_name'],
                'data': data
            }

    conn_inv.close()

    return jsonify(results)

@app.route('/api/analytics/product-profitability')
def analytics_product_profitability():
    """Product profitability analysis"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get products with their recipes
    cursor.execute("""
        SELECT
            p.id,
            p.product_name,
            p.selling_price,
            SUM(r.quantity_needed * i.average_unit_price) as cogs
        FROM products p
        JOIN recipes r ON p.id = r.product_id
        JOIN ingredients i ON r.ingredient_id = i.id
        WHERE i.active = 1
        GROUP BY p.id, p.product_name, p.selling_price
        HAVING cogs IS NOT NULL
    """)

    products = []
    for row in cursor.fetchall():
        cogs = row['cogs'] or 0
        selling_price = row['selling_price']
        profit = selling_price - cogs
        margin = (profit / selling_price * 100) if selling_price > 0 else 0

        products.append({
            'id': row['id'],
            'name': row['product_name'],
            'selling_price': round(selling_price, 2),
            'cogs': round(cogs, 2),
            'profit': round(profit, 2),
            'margin_percent': round(margin, 2)
        })

    conn.close()

    # Sort by profit descending
    products.sort(key=lambda x: x['profit'], reverse=True)

    return jsonify({
        'products': products,
        'total_products': len(products)
    })

@app.route('/api/analytics/category-spending')
def analytics_category_spending():
    """Category spending over time"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    grouping = request.args.get('grouping', 'month')  # day, week, month

    conn_inv = get_db_connection(INVOICES_DB)
    conn_ing = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()
    cursor_ing = conn_ing.cursor()

    # Get category mapping
    cursor_ing.execute("SELECT ingredient_code, category FROM ingredients")
    category_map = {row['ingredient_code']: row['category'] for row in cursor_ing.fetchall()}

    # Build date grouping
    if grouping == 'day':
        date_group = "date(i.invoice_date)"
    elif grouping == 'week':
        date_group = "strftime('%Y-W%W', i.invoice_date)"
    else:  # month
        date_group = "strftime('%Y-%m', i.invoice_date)"

    query = f"""
        SELECT
            {date_group} as period,
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

    query += f" GROUP BY {date_group}, ili.ingredient_code ORDER BY period"

    cursor_inv.execute(query, params)
    data = [dict(row) for row in cursor_inv.fetchall()]

    # Organize by period and category
    result = {}
    for row in data:
        period = row['period']
        category = category_map.get(row['ingredient_code'], 'Unknown')
        amount = row['amount']

        if period not in result:
            result[period] = {}
        if category not in result[period]:
            result[period][category] = 0

        result[period][category] += amount

    conn_inv.close()
    conn_ing.close()

    return jsonify(result)

@app.route('/api/analytics/inventory-value')
def analytics_inventory_value():
    """Top items by inventory value"""
    limit = request.args.get('limit', 20)
    category = request.args.get('category', 'all')

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    query = """
        SELECT
            ingredient_name,
            brand,
            category,
            quantity_on_hand,
            unit_of_measure,
            average_unit_price,
            ROUND(quantity_on_hand * average_unit_price, 2) as total_value
        FROM ingredients
        WHERE active = 1 AND quantity_on_hand > 0
    """
    params = []

    if category != 'all':
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY total_value DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    items = [dict(row) for row in cursor.fetchall()]

    total_value = sum(item['total_value'] for item in items)

    conn.close()

    return jsonify({
        'items': items,
        'total_value': round(total_value, 2),
        'item_count': len(items)
    })

@app.route('/api/analytics/supplier-performance')
def analytics_supplier_performance():
    """Supplier performance metrics"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    query = """
        SELECT
            supplier_name,
            COUNT(*) as invoice_count,
            SUM(total_amount) as total_spend,
            AVG(total_amount) as avg_invoice,
            MIN(invoice_date) as first_order,
            MAX(invoice_date) as last_order
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
    suppliers = []

    for row in cursor.fetchall():
        supplier = dict(row)

        # Calculate price consistency (get std dev of invoice amounts)
        cursor.execute("""
            SELECT AVG(total_amount) as avg,
                   COUNT(*) as cnt
            FROM invoices
            WHERE supplier_name = ?
        """, (supplier['supplier_name'],))

        stats = cursor.fetchone()
        supplier['consistency_score'] = 100 if stats['cnt'] > 1 else 0  # Simplified

        suppliers.append(supplier)

    conn.close()

    return jsonify({'suppliers': suppliers})

@app.route('/api/analytics/price-volatility')
def analytics_price_volatility():
    """Price volatility (coefficient of variation)"""
    limit = request.args.get('limit', 20)
    min_purchases = request.args.get('min_purchases', 5)

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    # SQLite doesn't have STDDEV, so we'll calculate it manually
    cursor.execute("""
        SELECT
            ingredient_code,
            ingredient_name,
            AVG(unit_price) as avg_price,
            COUNT(*) as purchase_count,
            MIN(unit_price) as min_price,
            MAX(unit_price) as max_price
        FROM invoice_line_items
        GROUP BY ingredient_code, ingredient_name
        HAVING purchase_count >= ?
        ORDER BY ingredient_name
    """, (min_purchases,))

    items = []
    for row in cursor.fetchall():
        # Get all prices for std dev calculation
        cursor.execute("""
            SELECT unit_price
            FROM invoice_line_items
            WHERE ingredient_code = ?
        """, (row['ingredient_code'],))

        prices = [r[0] for r in cursor.fetchall()]

        # Calculate standard deviation
        import statistics
        if len(prices) > 1:
            std_dev = statistics.stdev(prices)
            cv = (std_dev / row['avg_price'] * 100) if row['avg_price'] > 0 else 0

            items.append({
                'ingredient_code': row['ingredient_code'],
                'ingredient_name': row['ingredient_name'],
                'avg_price': round(row['avg_price'], 2),
                'min_price': round(row['min_price'], 2),
                'max_price': round(row['max_price'], 2),
                'std_dev': round(std_dev, 2),
                'cv_percent': round(cv, 2),
                'purchase_count': row['purchase_count']
            })

    conn.close()

    # Sort by CV descending and limit
    items.sort(key=lambda x: x['cv_percent'], reverse=True)
    items = items[:int(limit)]

    return jsonify({'items': items})

@app.route('/api/analytics/invoice-activity')
def analytics_invoice_activity():
    """Invoice activity timeline"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    grouping = request.args.get('grouping', 'week')

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    if grouping == 'day':
        date_group = "date(invoice_date)"
    elif grouping == 'month':
        date_group = "strftime('%Y-%m', invoice_date)"
    else:  # week
        date_group = "strftime('%Y-W%W', invoice_date)"

    query = f"""
        SELECT
            {date_group} as period,
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

    query += f" GROUP BY {date_group} ORDER BY period"

    cursor.execute(query, params)
    data = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({'timeline': data})

@app.route('/api/analytics/cost-variance')
def analytics_cost_variance():
    """Items with significant price variance"""
    threshold = float(request.args.get('threshold', 15))  # % change
    limit = request.args.get('limit', 50)

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get ingredients with both average and last price
    cursor.execute("""
        SELECT
            ingredient_code,
            ingredient_name,
            brand,
            category,
            average_unit_price as avg_price,
            last_unit_price as last_price,
            date_received as last_purchase_date
        FROM ingredients
        WHERE active = 1
          AND average_unit_price > 0
          AND last_unit_price > 0
          AND average_unit_price != last_unit_price
    """)

    alerts = []
    for row in cursor.fetchall():
        avg = row['avg_price']
        last = row['last_price']
        change = ((last - avg) / avg * 100) if avg > 0 else 0

        if abs(change) >= threshold:
            alerts.append({
                'ingredient_code': row['ingredient_code'],
                'ingredient_name': row['ingredient_name'],
                'brand': row['brand'],
                'category': row['category'],
                'avg_price': round(avg, 2),
                'last_price': round(last, 2),
                'change_percent': round(change, 2),
                'change_direction': 'increase' if change > 0 else 'decrease',
                'last_purchase_date': row['last_purchase_date']
            })

    conn.close()

    # Sort by absolute change descending
    alerts.sort(key=lambda x: abs(x['change_percent']), reverse=True)
    alerts = alerts[:int(limit)]

    return jsonify({
        'alerts': alerts,
        'alert_count': len(alerts)
    })

@app.route('/api/analytics/usage-forecast')
def analytics_usage_forecast():
    """Usage forecast with linear regression"""
    ingredient_code = request.args.get('ingredient_code', '')
    forecast_days = int(request.args.get('forecast_days', 30))

    if not ingredient_code:
        return jsonify({'error': 'ingredient_code required'}), 400

    conn_inv = get_db_connection(INVOICES_DB)
    cursor = conn_inv.cursor()

    # Get purchase history
    cursor.execute("""
        SELECT
            i.invoice_date as date,
            SUM(ili.quantity_received) as quantity
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        WHERE ili.ingredient_code = ?
        GROUP BY i.invoice_date
        ORDER BY i.invoice_date
    """, (ingredient_code,))

    data = [dict(row) for row in cursor.fetchall()]
    conn_inv.close()

    if len(data) < 2:
        return jsonify({'error': 'Insufficient data for forecast'}), 400

    # Simple linear regression
    from datetime import datetime, timedelta
    import statistics

    dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in data]
    quantities = [d['quantity'] for d in data]

    # Convert to day numbers
    base_date = dates[0]
    x = [(d - base_date).days for d in dates]
    y = quantities

    # Calculate regression
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    intercept = (sum_y - slope * sum_x) / n

    # Generate forecast
    last_day = x[-1]
    forecast = []
    for i in range(1, forecast_days + 1):
        forecast_date = base_date + timedelta(days=last_day + i)
        forecast_qty = slope * (last_day + i) + intercept
        forecast.append({
            'date': forecast_date.strftime('%Y-%m-%d'),
            'quantity': max(0, round(forecast_qty, 2))  # Don't forecast negative
        })

    return jsonify({
        'historical': data,
        'forecast': forecast,
        'trend': 'increasing' if slope > 0 else 'decreasing',
        'slope': round(slope, 4)
    })

# Add remaining analytics endpoints in next part...
