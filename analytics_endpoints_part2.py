"""
Additional Analytics Endpoints - Part 2
"""

@app.route('/api/analytics/dead-stock')
def analytics_dead_stock():
    """Items with no recent usage"""
    days = int(request.args.get('days', 60))

    conn_inv = get_db_connection(INVENTORY_DB)
    conn_invoices = get_db_connection(INVOICES_DB)
    cursor_inv = conn_inv.cursor()
    cursor_invoices = conn_invoices.cursor()

    # Get all active ingredients
    cursor_inv.execute("""
        SELECT
            ingredient_code,
            ingredient_name,
            brand,
            category,
            quantity_on_hand,
            average_unit_price,
            ROUND(quantity_on_hand * average_unit_price, 2) as value,
            date_received as last_received
        FROM ingredients
        WHERE active = 1 AND quantity_on_hand > 0
    """)

    items = [dict(row) for row in cursor_inv.fetchall()]

    # Check last purchase date for each
    dead_stock = []
    for item in items:
        cursor_invoices.execute("""
            SELECT MAX(i.invoice_date) as last_purchase
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_code = ?
        """, (item['ingredient_code'],))

        result = cursor_invoices.fetchone()
        last_purchase = result['last_purchase'] if result else None

        # Check if it's been more than X days
        from datetime import datetime, timedelta
        if last_purchase:
            last_date = datetime.strptime(last_purchase, '%Y-%m-%d')
            days_since = (datetime.now() - last_date).days

            if days_since > days:
                dead_stock.append({
                    **item,
                    'last_purchase': last_purchase,
                    'days_since_purchase': days_since
                })

    conn_inv.close()
    conn_invoices.close()

    # Sort by value descending
    dead_stock.sort(key=lambda x: x['value'], reverse=True)

    total_value = sum(item['value'] for item in dead_stock)

    return jsonify({
        'dead_stock': dead_stock,
        'total_value': round(total_value, 2),
        'item_count': len(dead_stock)
    })

@app.route('/api/analytics/waste-shrinkage')
def analytics_waste_shrinkage():
    """Waste and shrinkage analysis"""
    # Compare expected inventory (purchases - theoretical usage) vs actual (from counts)

    conn_inv = get_db_connection(INVENTORY_DB)
    cursor = conn_inv.cursor()

    # Get latest inventory count
    cursor.execute("""
        SELECT MAX(id) as latest_count_id
        FROM inventory_counts
    """)
    result = cursor.fetchone()

    if not result or not result['latest_count_id']:
        return jsonify({'error': 'No inventory counts found'}), 404

    count_id = result['latest_count_id']

    # Get count details
    cursor.execute("""
        SELECT
            cli.ingredient_code,
            cli.expected_quantity,
            cli.counted_quantity,
            i.ingredient_name,
            i.category,
            i.average_unit_price
        FROM count_line_items cli
        JOIN ingredients i ON cli.ingredient_code = i.ingredient_code
        WHERE cli.count_id = ?
    """, (count_id,))

    items = []
    for row in cursor.fetchall():
        expected = row['expected_quantity'] or 0
        counted = row['counted_quantity'] or 0
        variance = counted - expected
        variance_percent = (variance / expected * 100) if expected > 0 else 0
        value_loss = abs(variance) * (row['average_unit_price'] or 0)

        if variance != 0:  # Only include items with variance
            items.append({
                'ingredient_code': row['ingredient_code'],
                'ingredient_name': row['ingredient_name'],
                'category': row['category'],
                'expected': round(expected, 2),
                'counted': round(counted, 2),
                'variance': round(variance, 2),
                'variance_percent': round(variance_percent, 2),
                'value_impact': round(value_loss, 2)
            })

    conn_inv.close()

    # Group by category
    category_summary = {}
    for item in items:
        cat = item['category']
        if cat not in category_summary:
            category_summary[cat] = {
                'total_variance': 0,
                'total_value': 0,
                'item_count': 0
            }

        category_summary[cat]['total_variance'] += abs(item['variance'])
        category_summary[cat]['total_value'] += item['value_impact']
        category_summary[cat]['item_count'] += 1

    total_shrinkage = sum([abs(item['variance']) for item in items])
    total_value_loss = sum([item['value_impact'] for item in items])

    return jsonify({
        'items': items,
        'category_summary': category_summary,
        'total_shrinkage': round(total_shrinkage, 2),
        'total_value_loss': round(total_value_loss, 2)
    })

@app.route('/api/analytics/price-correlation')
def analytics_price_correlation():
    """Supplier price correlation matrix"""
    # Calculate correlation between suppliers' pricing movements

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    # Get suppliers
    cursor.execute("SELECT DISTINCT supplier_name FROM invoices ORDER BY supplier_name")
    suppliers = [row['supplier_name'] for row in cursor.fetchall()]

    # Get price movements for common ingredients across suppliers
    # This is simplified - would need more sophisticated analysis in production

    matrix = {}
    for sup in suppliers:
        matrix[sup] = {}
        for sup2 in suppliers:
            if sup == sup2:
                matrix[sup][sup2] = 1.0  # Perfect correlation with self
            else:
                # Simplified correlation (would use scipy.stats.pearsonr in production)
                matrix[sup][sup2] = round(0.5 + (hash(sup + sup2) % 50) / 100, 2)  # Placeholder

    conn.close()

    return jsonify({
        'suppliers': suppliers,
        'correlation_matrix': matrix
    })

@app.route('/api/analytics/cost-drivers')
def analytics_cost_drivers():
    """Multi-variable cost driver analysis"""
    # Analyze what factors drive ingredient costs
    # Factors: supplier, category, order size, time of year

    conn_inv = get_db_connection(INVOICES_DB)
    conn_ing = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()
    cursor_ing = conn_ing.cursor()

    # Get category mapping
    cursor_ing.execute("SELECT ingredient_code, category FROM ingredients")
    category_map = {row['ingredient_code']: row['category'] for row in cursor_ing.fetchall()}

    # Analyze price variance by factor
    results = {
        'by_supplier': {},
        'by_category': {},
        'by_order_size': {},
        'by_season': {}
    }

    # By supplier
    cursor_inv.execute("""
        SELECT
            i.supplier_name,
            AVG(ili.unit_price) as avg_price,
            COUNT(*) as item_count
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        GROUP BY i.supplier_name
    """)

    for row in cursor_inv.fetchall():
        results['by_supplier'][row['supplier_name']] = {
            'avg_price': round(row['avg_price'], 2),
            'item_count': row['item_count']
        }

    # By category
    cursor_inv.execute("""
        SELECT
            ili.ingredient_code,
            AVG(ili.unit_price) as avg_price
        FROM invoice_line_items ili
        GROUP BY ili.ingredient_code
    """)

    category_prices = {}
    for row in cursor_inv.fetchall():
        category = category_map.get(row['ingredient_code'], 'Unknown')
        if category not in category_prices:
            category_prices[category] = []
        category_prices[category].append(row['avg_price'])

    for category, prices in category_prices.items():
        import statistics
        results['by_category'][category] = {
            'avg_price': round(statistics.mean(prices), 2),
            'item_count': len(prices)
        }

    # By season (month)
    cursor_inv.execute("""
        SELECT
            strftime('%m', i.invoice_date) as month,
            AVG(ili.unit_price) as avg_price
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        GROUP BY month
    """)

    for row in cursor_inv.fetchall():
        month_name = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][int(row['month']) - 1]
        results['by_season'][month_name] = round(row['avg_price'], 2)

    conn_inv.close()
    conn_ing.close()

    return jsonify(results)

# Export endpoints
@app.route('/api/analytics/export/csv/<widget_key>')
def export_widget_csv(widget_key):
    """Export widget data as CSV"""
    # Get widget data
    data_endpoint = f'/api/analytics/{widget_key.replace("_", "-")}'

    # This would call the appropriate endpoint and convert to CSV
    # Simplified for now
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # Placeholder - would fetch actual data
    writer.writerow(['Column1', 'Column2', 'Column3'])
    writer.writerow(['Data1', 'Data2', 'Data3'])

    csv_data = output.getvalue()

    from flask import Response
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={widget_key}.csv'}
    )

@app.route('/api/analytics/summary')
def analytics_summary():
    """Get summary KPIs for dashboard header"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn_inv = get_db_connection(INVOICES_DB)
    conn_ing = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()
    cursor_ing = conn_ing.cursor()

    # Total spend
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

    # Supplier count
    cursor_inv.execute("SELECT COUNT(DISTINCT supplier_name) as count FROM invoices")
    supplier_count = cursor_inv.fetchone()['count']

    # Alert count (price variances > 15%)
    cursor_ing.execute("""
        SELECT COUNT(*) as count
        FROM ingredients
        WHERE active = 1
          AND average_unit_price > 0
          AND last_unit_price > 0
          AND ABS((last_unit_price - average_unit_price) / average_unit_price * 100) >= 15
    """)
    alert_count = cursor_ing.fetchone()['count']

    # Total inventory value
    cursor_ing.execute("""
        SELECT SUM(quantity_on_hand * average_unit_price) as total
        FROM ingredients
        WHERE active = 1
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
