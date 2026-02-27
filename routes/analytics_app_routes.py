from flask import Blueprint, jsonify, request, g, make_response
import sqlite3, csv, io, json
from datetime import datetime, timedelta
from db_manager import get_org_db
from middleware.tenant_context_separate_db import login_required, organization_required, log_audit

analytics_app_bp = Blueprint('analytics_app', __name__)

# ==================== WIDGET MANAGEMENT ====================

@analytics_app_bp.route('/api/analytics/widgets/available')
@login_required
@organization_required
def get_available_widgets():
    """Get all available analytics widgets"""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT widget_key, widget_name, widget_type, chart_type, category,
               description, icon, default_enabled, requires_recipe_data
        FROM analytics_widgets
        ORDER BY category, widget_name
    """)

    widgets = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'success': True, 'widgets': widgets})

@analytics_app_bp.route('/api/analytics/categories')
@login_required
@organization_required
def get_analytics_categories():
    """Get all available categories for filtering"""
    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/widgets/enabled')
@login_required
@organization_required
def get_enabled_widgets():
    """Get user's enabled widgets with preferences"""
    user_id = request.args.get('user_id', 'default')

    conn = get_org_db()
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

    return jsonify({'success': True, 'widgets': widgets})

@analytics_app_bp.route('/api/analytics/widgets/toggle', methods=['POST'])
def toggle_widget():
    """Enable/disable a widget"""
    data = request.json
    user_id = data.get('user_id', 'default')
    widget_key = data.get('widget_key')
    enabled = data.get('enabled', 1)

    conn = get_org_db()
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

# ==================== ANALYTICS SUMMARY ====================

@analytics_app_bp.route('/api/analytics/summary')
@login_required
@organization_required
def analytics_summary():
    """Get summary KPIs for dashboard header"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn_inv = get_org_db()
    conn_ing = get_org_db()
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

@analytics_app_bp.route('/api/analytics/vendor-spend')
@login_required
@organization_required
def analytics_vendor_spend():
    """Vendor spend distribution"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/price-trends')
@login_required
@organization_required
def analytics_price_trends():
    """Price trend for a single ingredient"""
    ingredient_code = request.args.get('ingredient_code', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not ingredient_code:
        return jsonify({'error': 'ingredient_code parameter required'}), 400

    conn_inv = get_org_db()
    cursor = conn_inv.cursor()

    query = """
        SELECT
            i.invoice_date as date,
            ili.unit_price as price,
            ing.ingredient_name
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        WHERE ing.ingredient_code = ?
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

@analytics_app_bp.route('/api/analytics/purchase-frequency')
@login_required
@organization_required
def analytics_purchase_frequency():
    """Calculate purchase frequency for ingredients"""
    conn_inv = get_org_db()
    cursor = conn_inv.cursor()

    # Get purchase dates for each ingredient
    cursor.execute("""
        SELECT
            ing.ingredient_code,
            ing.ingredient_name,
            i.invoice_date,
            COUNT(*) as purchase_count
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_code, ing.ingredient_name
        ORDER BY ing.ingredient_code
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
            ing.ingredient_code,
            i.invoice_date
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        ORDER BY ing.ingredient_code, i.invoice_date
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

@analytics_app_bp.route('/api/analytics/ingredients-with-price-history')
@login_required
@organization_required
def analytics_ingredients_with_price_history():
    """Get list of ingredient codes that have price history in invoices"""
    conn_inv = get_org_db()
    cursor = conn_inv.cursor()

    cursor.execute("""
        SELECT DISTINCT ing.ingredient_code
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        ORDER BY ing.ingredient_code
    """)

    codes = [row['ingredient_code'] for row in cursor.fetchall()]
    conn_inv.close()

    return jsonify({'ingredient_codes': codes})

@analytics_app_bp.route('/api/analytics/category-spending')
@login_required
@organization_required
def analytics_category_spending():
    """Category spending distribution (pie chart) - shows ALL categories"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn_inv = get_org_db()
    conn_ing = get_org_db()
    cursor_inv = conn_inv.cursor()
    cursor_ing = conn_ing.cursor()

    # Get category mapping from ingredients table
    cursor_ing.execute("SELECT ingredient_code, category FROM ingredients")
    category_map = {row['ingredient_code']: row['category'] for row in cursor_ing.fetchall()}

    # Get total spending by ingredient code from invoices
    query = """
        SELECT
            ing.ingredient_code,
            SUM(ili.total_price) as amount
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        WHERE 1=1
    """
    params = []

    if date_from:
        query += " AND i.invoice_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND i.invoice_date <= ?"
        params.append(date_to)

    query += " GROUP BY ing.ingredient_code"

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

@analytics_app_bp.route('/api/analytics/inventory-value')
@login_required
@organization_required
def analytics_inventory_value():
    """Inventory value by category"""
    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/supplier-performance')
@login_required
@organization_required
def analytics_supplier_performance():
    """Supplier performance metrics"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/price-volatility')
@login_required
@organization_required
def analytics_price_volatility():
    """Price volatility analysis"""
    conn_inv = get_org_db()
    cursor = conn_inv.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name,
               AVG(ili.unit_price) as avg_price,
               MAX(ili.unit_price) as max_price,
               MIN(ili.unit_price) as min_price,
               COUNT(*) as purchase_count
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
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

@analytics_app_bp.route('/api/analytics/invoice-activity')
@login_required
@organization_required
def analytics_invoice_activity():
    """Invoice activity over time"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/cost-variance')
@login_required
@organization_required
def analytics_cost_variance():
    """Cost variance alerts"""
    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/usage-forecast')
@login_required
@organization_required
def analytics_usage_forecast():
    """Ingredient usage forecast"""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name, SUM(ili.quantity) as total_qty
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
        ORDER BY total_qty DESC
        LIMIT 10
    """)

    top_ingredients = cursor.fetchall()

    datasets = []
    for ing in top_ingredients:
        cursor.execute("""
            SELECT DATE(i.invoice_date) as date, SUM(ili.quantity) as qty
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name = ?
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

@analytics_app_bp.route('/api/analytics/recipe-cost-trajectory')
@login_required
@organization_required
def analytics_recipe_cost_trajectory():
    """Recipe cost changes over time"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, p.product_name
        FROM products p
        WHERE 1=1 AND EXISTS (
            SELECT 1 FROM recipes WHERE product_id = p.id
        )
    """)

    products = cursor.fetchall()

    conn_inv = get_org_db()
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
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name = ?
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

@analytics_app_bp.route('/api/analytics/substitution-opportunities')
@login_required
@organization_required
def analytics_substitution_opportunities():
    """Ingredient substitution opportunities"""
    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/dead-stock')
@login_required
@organization_required
def analytics_dead_stock():
    """Dead stock analysis"""
    from datetime import datetime, timedelta

    conn_inv = get_org_db()
    cursor_inv = conn_inv.cursor()

    conn_invoices = get_org_db()
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
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name = ?
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

@analytics_app_bp.route('/api/analytics/eoq-optimizer')
@login_required
@organization_required
def analytics_eoq_optimizer():
    """Economic Order Quantity optimizer"""
    import math

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name,
               COUNT(*) as order_count,
               AVG(ili.quantity) as avg_order_qty,
               SUM(ili.quantity) as total_qty
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
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

        conn_inv = get_org_db()
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

@analytics_app_bp.route('/api/analytics/seasonal-patterns')
@login_required
@organization_required
def analytics_seasonal_patterns():
    """Seasonal purchasing patterns"""
    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/menu-engineering')
@login_required
@organization_required
def analytics_menu_engineering():
    """Menu engineering matrix (BCG analysis)"""
    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/waste-shrinkage')
@login_required
@organization_required
def analytics_waste_shrinkage():
    """Waste and shrinkage analysis"""
    conn_inv = get_org_db()
    cursor_inv = conn_inv.cursor()

    conn_invoices = get_org_db()
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
            SELECT SUM(ili.quantity) as total_purchased
            FROM invoice_line_items ili
            JOIN ingredients i ON ili.ingredient_id = i.id
            WHERE i.ingredient_name = ?
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

@analytics_app_bp.route('/api/analytics/price-correlation')
@login_required
@organization_required
def analytics_price_correlation():
    """Price correlation matrix"""
    import math

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name, COUNT(*) as count
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
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
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name = ?
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

@analytics_app_bp.route('/api/analytics/breakeven-analysis')
@login_required
@organization_required
def analytics_breakeven_analysis():
    """Product break-even analysis"""
    conn = get_org_db()
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

@analytics_app_bp.route('/api/analytics/cost-drivers')
@login_required
@organization_required
def analytics_cost_drivers():
    """Cost drivers regression analysis"""
    conn_inv = get_org_db()
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
    conn_invoices = get_org_db()
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
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name IN ({placeholders})
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

@analytics_app_bp.route('/api/analytics/vendor-spend/export')
@login_required
@organization_required
def export_vendor_spend():
    """Export vendor spend distribution as CSV"""

    # Get the data using the same logic as the regular endpoint
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'vendor-spend'})
    return response

@analytics_app_bp.route('/api/analytics/price-trends/export')
@login_required
@organization_required
def export_price_trends():
    """Export price trends as CSV"""

    ingredient_codes = request.args.get('ingredients', '').split(',')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not ingredient_codes or ingredient_codes == ['']:
        conn_inv = get_org_db()
        cursor = conn_inv.cursor()
        cursor.execute("""
            SELECT ing.ingredient_code, SUM(ili.quantity) as total_qty
            FROM invoice_line_items ili
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            GROUP BY ing.ingredient_code
            ORDER BY total_qty DESC
            LIMIT 5
        """)
        ingredient_codes = [row['ingredient_code'] for row in cursor.fetchall()]
        conn_inv.close()

    conn = get_org_db()
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
                   ing.ingredient_name,
                   AVG(ili.unit_price) as avg_price
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_code = ?
        """
        params = [code]

        if date_from:
            query += " AND i.invoice_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND i.invoice_date <= ?"
            params.append(date_to)

        query += " GROUP BY DATE(i.invoice_date), ing.ingredient_name ORDER BY date"

        cursor.execute(query, params)
        results = cursor.fetchall()

        for row in results:
            writer.writerow([row['date'], row['ingredient_name'], f"${float(row['avg_price']):.2f}"])

    conn.close()

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=price_trends.csv'
    log_audit('csv_exported', 'analytics', None, {'widget': 'price-trends'})
    return response

@analytics_app_bp.route('/api/analytics/category-spending/export')
@login_required
@organization_required
def export_category_spending():
    """Export category spending totals as CSV"""

    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    selected_categories = request.args.get('categories', '')

    conn_inv = get_org_db()
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
    conn_invoices = get_org_db()
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
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name IN ({placeholders})
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'category-spending'})
    return response

@analytics_app_bp.route('/api/analytics/inventory-value/export')
@login_required
@organization_required
def export_inventory_value():
    """Export inventory value distribution as CSV"""

    conn = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'inventory-value'})
    return response

@analytics_app_bp.route('/api/analytics/supplier-performance/export')
@login_required
@organization_required
def export_supplier_performance():
    """Export supplier performance as CSV"""

    conn = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'supplier-performance'})
    return response

@analytics_app_bp.route('/api/analytics/price-volatility/export')
@login_required
@organization_required
def export_price_volatility():
    """Export price volatility index as CSV"""

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name,
               AVG(ili.unit_price) as avg_price,
               COUNT(*) as price_count
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
        HAVING price_count >= 3
    """)

    ingredients = cursor.fetchall()
    volatility_data = []

    for ing in ingredients:
        cursor.execute("""
            SELECT ili.unit_price
            FROM invoice_line_items ili
            JOIN ingredients i ON ili.ingredient_id = i.id
            WHERE i.ingredient_name = ?
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'price-volatility'})
    return response

@analytics_app_bp.route('/api/analytics/invoice-activity/export')
@login_required
@organization_required
def export_invoice_activity():
    """Export invoice activity timeline as CSV"""

    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'invoice-activity'})
    return response

@analytics_app_bp.route('/api/analytics/cost-variance/export')
@login_required
@organization_required
def export_cost_variance():
    """Export cost variance alerts as CSV"""

    conn = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'cost-variance'})
    return response

@analytics_app_bp.route('/api/analytics/menu-engineering/export')
@login_required
@organization_required
def export_menu_engineering():
    """Export menu engineering matrix as CSV"""

    conn = get_org_db()

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
    log_audit('csv_exported', 'analytics', None, {'widget': 'menu-engineering'})
    return response

@analytics_app_bp.route('/api/analytics/dead-stock/export')
@login_required
@organization_required
def export_dead_stock():
    """Export dead stock analysis as CSV"""

    conn = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'dead-stock'})
    return response

@analytics_app_bp.route('/api/analytics/breakeven-analysis/export')
@login_required
@organization_required
def export_breakeven_analysis():
    """Export break-even analysis as CSV"""

    conn = get_org_db()

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
    log_audit('csv_exported', 'analytics', None, {'widget': 'breakeven-analysis'})
    return response

@analytics_app_bp.route('/api/analytics/seasonal-patterns/export')
@login_required
@organization_required
def export_seasonal_patterns():
    """Export seasonal demand patterns as CSV"""

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name, SUM(ili.quantity) as total_qty
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
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
                   SUM(ili.quantity) as total_qty
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name = ?
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'seasonal-patterns'})
    return response

@analytics_app_bp.route('/api/analytics/waste-shrinkage/export')
@login_required
@organization_required
def export_waste_shrinkage():
    """Export waste and shrinkage analysis as CSV"""

    conn_inv = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'waste-shrinkage'})
    return response

@analytics_app_bp.route('/api/analytics/eoq-optimizer/export')
@login_required
@organization_required
def export_eoq_optimizer():
    """Export EOQ optimizer as CSV"""

    conn_inv = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'eoq-optimizer'})
    return response

@analytics_app_bp.route('/api/analytics/price-correlation/export')
@login_required
@organization_required
def export_price_correlation():
    """Export supplier price correlation as CSV"""

    conn = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'price-correlation'})
    return response

@analytics_app_bp.route('/api/analytics/usage-forecast/export')
@login_required
@organization_required
def export_usage_forecast():
    """Export usage & forecast as CSV"""

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name, SUM(ili.quantity) as total_qty
        FROM invoice_line_items ili
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
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
                   SUM(ili.quantity) as qty
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name = ?
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'usage-forecast'})
    return response

@analytics_app_bp.route('/api/analytics/recipe-cost-trajectory/export')
@login_required
@organization_required
def export_recipe_cost_trajectory():
    """Export recipe cost trajectory as CSV"""

    product_id = request.args.get('product_id', type=int)

    if not product_id:
        response = make_response("Product ID required")
        response.status_code = 400
        return response

    conn_inv = get_org_db()
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

    conn_invoices = get_org_db()
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
                JOIN ingredients ing ON ili.ingredient_id = ing.id
                WHERE ing.ingredient_name = ?
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'recipe-cost-trajectory'})
    return response

@analytics_app_bp.route('/api/analytics/substitution-opportunities/export')
@login_required
@organization_required
def export_substitution_opportunities():
    """Export ingredient substitution opportunities as CSV"""

    conn_inv = get_org_db()
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'substitution-opportunities'})
    return response

@analytics_app_bp.route('/api/analytics/cost-drivers/export')
@login_required
@organization_required
def export_cost_drivers():
    """Export cost drivers analysis as CSV"""

    conn_inv = get_org_db()
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

    conn_invoices = get_org_db()
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
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            WHERE ing.ingredient_name IN ({placeholders})
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'cost-drivers'})
    return response

@analytics_app_bp.route('/api/analytics/purchase-frequency/export')
@login_required
@organization_required
def export_purchase_frequency():
    """Export purchase frequency as CSV"""

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ing.ingredient_name,
               COUNT(*) as purchase_count,
               AVG(ili.quantity) as avg_quantity,
               MIN(DATE(i.invoice_date)) as first_purchase,
               MAX(DATE(i.invoice_date)) as last_purchase
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        JOIN ingredients ing ON ili.ingredient_id = ing.id
        GROUP BY ing.ingredient_name
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
    log_audit('csv_exported', 'analytics', None, {'widget': 'purchase-frequency'})
    return response
