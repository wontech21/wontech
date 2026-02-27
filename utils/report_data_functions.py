"""Report Data Functions — standalone data extractors for all analytics reports.

Each function queries the org database and returns a (headers, rows) tuple
where headers is a list of column name strings and rows is a list of lists.
All values are raw (no dollar signs, no formatting).
"""

from db_manager import get_org_db
from utils.report_registry import register_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_filter_invoices(query, params, date_from, date_to, date_col="invoice_date"):
    """Append date range WHERE clauses for invoice queries."""
    if date_from:
        query += f" AND {date_col} >= ?"
        params.append(date_from)
    if date_to:
        query += f" AND {date_col} <= ?"
        params.append(date_to)
    return query, params


def _calculate_product_cost(conn, product_id, visited=None):
    """Recursively calculate a product's ingredient cost from its recipe."""
    if visited is None:
        visited = set()
    if product_id in visited:
        return 0
    visited.add(product_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.source_type, r.ingredient_id as source_id, r.quantity_needed
        FROM recipes r
        WHERE r.product_id = ?
    """, (product_id,))

    recipe_items = cursor.fetchall()
    total_cost = 0

    for row in recipe_items:
        source_type = row['source_type']
        source_id = row['source_id']
        quantity = row['quantity_needed']

        if source_type == 'ingredient':
            cursor.execute("""
                SELECT COALESCE(unit_cost, 0) as unit_cost
                FROM ingredients WHERE id = ?
            """, (source_id,))
            ing_result = cursor.fetchone()
            if ing_result:
                total_cost += quantity * ing_result['unit_cost']
        elif source_type == 'product':
            nested_cost = _calculate_product_cost(conn, source_id, visited)
            total_cost += quantity * nested_cost

    return total_cost


# ---------------------------------------------------------------------------
# 1. Vendor Spend Distribution
# ---------------------------------------------------------------------------

def get_vendor_spend(date_from=None, date_to=None, **kwargs):
    """Top vendors by total spend."""
    conn = get_org_db()
    cursor = conn.cursor()

    query = """
        SELECT supplier_name, SUM(total_amount) as total
        FROM invoices
        WHERE 1=1
    """
    params = []
    query, params = _date_filter_invoices(query, params, date_from, date_to)
    query += " GROUP BY supplier_name ORDER BY total DESC LIMIT 10"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    headers = ['Supplier Name', 'Total Spend']
    rows = [[row['supplier_name'], float(row['total'])] for row in results]
    return headers, rows


# ---------------------------------------------------------------------------
# 2. Price Trends
# ---------------------------------------------------------------------------

def get_price_trends(date_from=None, date_to=None, **kwargs):
    """Unit price changes over time for top ingredients."""
    ingredient_codes = kwargs.get('ingredients', [])

    conn = get_org_db()
    cursor = conn.cursor()

    # If no ingredients specified, pick top 5 by purchase volume
    if not ingredient_codes:
        cursor.execute("""
            SELECT ing.ingredient_code, SUM(ili.quantity) as total_qty
            FROM invoice_line_items ili
            JOIN ingredients ing ON ili.ingredient_id = ing.id
            GROUP BY ing.ingredient_code
            ORDER BY total_qty DESC
            LIMIT 5
        """)
        ingredient_codes = [row['ingredient_code'] for row in cursor.fetchall()]

    headers = ['Date', 'Ingredient', 'Average Price']
    rows = []

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
            rows.append([row['date'], row['ingredient_name'], float(row['avg_price'])])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 3. Category Spending
# ---------------------------------------------------------------------------

def get_category_spending(date_from=None, date_to=None, **kwargs):
    """Spending breakdown by ingredient category."""
    selected_categories = kwargs.get('categories', [])

    conn = get_org_db()
    cursor = conn.cursor()

    # Get all categories
    cursor.execute("SELECT DISTINCT category FROM ingredients WHERE active = 1 ORDER BY category")
    all_categories = [row['category'] for row in cursor.fetchall() if row['category']]

    # Determine which categories to show
    if selected_categories:
        categories = [cat for cat in selected_categories if cat in all_categories]
    else:
        categories = all_categories[:5]

    # Get ingredient-to-category mapping
    category_map = {}
    for category in categories:
        cursor.execute(
            "SELECT ingredient_name FROM ingredients WHERE category = ? AND active = 1",
            (category,),
        )
        category_map[category] = [row['ingredient_name'] for row in cursor.fetchall()]

    headers = ['Category', 'Total Spending']
    rows = []

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

        cursor.execute(query, params)
        result = cursor.fetchone()
        total = float(result['total'] or 0)
        if total > 0:
            rows.append([category, total])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 4. Inventory Value
# ---------------------------------------------------------------------------

def get_inventory_value(date_from=None, date_to=None, **kwargs):
    """Current inventory valuation."""
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

    headers = ['Ingredient', 'Quantity On Hand', 'Unit Cost', 'Total Value']
    rows = [
        [
            row['ingredient_name'],
            float(row['quantity_on_hand']),
            float(row['unit_cost']),
            float(row['total_value']),
        ]
        for row in results
    ]
    return headers, rows


# ---------------------------------------------------------------------------
# 5. Supplier Performance
# ---------------------------------------------------------------------------

def get_supplier_performance(date_from=None, date_to=None, **kwargs):
    """Supplier delivery and pricing metrics."""
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

    headers = ['Supplier', 'Invoice Count', 'Avg Invoice', 'Total Spend', 'Avg Days Since Last']
    rows = [
        [
            row['supplier_name'],
            row['invoice_count'],
            float(row['avg_invoice']),
            float(row['total_spend']),
            int(row['avg_days_ago']),
        ]
        for row in results
    ]
    return headers, rows


# ---------------------------------------------------------------------------
# 6. Price Volatility
# ---------------------------------------------------------------------------

def get_price_volatility(date_from=None, date_to=None, **kwargs):
    """Price stability analysis by ingredient."""
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
            'std_dev': std_dev,
        })

    conn.close()

    volatility_data.sort(key=lambda x: x['cv'], reverse=True)

    headers = ['Ingredient', 'Volatility Index (CV%)', 'Avg Price', 'Std Deviation']
    rows = [
        [item['name'], round(item['cv'], 1), round(item['avg_price'], 4), round(item['std_dev'], 4)]
        for item in volatility_data[:15]
    ]
    return headers, rows


# ---------------------------------------------------------------------------
# 7. Invoice Activity
# ---------------------------------------------------------------------------

def get_invoice_activity(date_from=None, date_to=None, **kwargs):
    """Invoice volume and amounts over time."""
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
    query, params = _date_filter_invoices(query, params, date_from, date_to)
    query += " GROUP BY DATE(invoice_date) ORDER BY date"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    headers = ['Date', 'Invoice Count', 'Total Value']
    rows = [
        [row['date'], row['invoice_count'], float(row['total_value'])]
        for row in results
    ]
    return headers, rows


# ---------------------------------------------------------------------------
# 8. Cost Variance
# ---------------------------------------------------------------------------

def get_cost_variance(date_from=None, date_to=None, **kwargs):
    """Actual vs expected cost analysis."""
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
                    'variance_pct': variance_pct,
                })

    conn.close()

    variances.sort(key=lambda x: abs(x['variance_pct']), reverse=True)

    headers = ['Ingredient', 'Avg Price', 'Latest Price', 'Variance %']
    rows = [
        [item['name'], round(item['avg_price'], 4), round(item['latest_price'], 4), round(item['variance_pct'], 1)]
        for item in variances[:15]
    ]
    return headers, rows


# ---------------------------------------------------------------------------
# 9. Menu Engineering Matrix
# ---------------------------------------------------------------------------

def get_menu_engineering(date_from=None, date_to=None, **kwargs):
    """Menu items by popularity and profitability."""
    conn = get_org_db()
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
        cost = _calculate_product_cost(conn, product_id)
        selling_price = float(product['selling_price'] or 0)
        margin_pct = ((selling_price - cost) / selling_price * 100) if selling_price > 0 else 0

        results.append({
            'product_name': product['product_name'],
            'selling_price': selling_price,
            'cost': cost,
            'margin_pct': margin_pct,
            'volume': float(product['volume'] or 0),
        })

    conn.close()

    if not results:
        avg_margin = 0
        avg_volume = 0
    else:
        avg_margin = sum(r['margin_pct'] for r in results) / len(results)
        avg_volume = sum(r['volume'] for r in results) / len(results)

    headers = ['Product', 'Margin %', 'Volume', 'Classification']
    rows = []
    for r in results:
        margin = r['margin_pct']
        volume = r['volume']

        if margin >= avg_margin and volume >= avg_volume:
            classification = 'Star'
        elif margin >= avg_margin and volume < avg_volume:
            classification = 'Puzzle'
        elif margin < avg_margin and volume >= avg_volume:
            classification = 'Plow Horse'
        else:
            classification = 'Dog'

        rows.append([r['product_name'], round(margin, 1), round(volume, 0), classification])

    return headers, rows


# ---------------------------------------------------------------------------
# 10. Dead Stock Analysis
# ---------------------------------------------------------------------------

def get_dead_stock(date_from=None, date_to=None, **kwargs):
    """Items with no recent movement."""
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

    headers = ['Ingredient', 'Quantity On Hand', 'Unit Price', 'Total Value', 'Category']
    rows = []
    for row in results:
        qty = float(row['quantity_on_hand'])
        price = float(row['average_unit_price'] or 0)
        total_value = qty * price
        rows.append([
            row['ingredient_name'],
            qty,
            price,
            total_value,
            row['category'] or 'N/A',
        ])

    return headers, rows


# ---------------------------------------------------------------------------
# 11. Break-Even Analysis
# ---------------------------------------------------------------------------

def get_breakeven_analysis(date_from=None, date_to=None, **kwargs):
    """Revenue needed to cover costs."""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, p.product_name, p.selling_price
        FROM products p
        WHERE EXISTS (SELECT 1 FROM recipes WHERE product_id = p.id)
        ORDER BY p.product_name
    """)

    products = cursor.fetchall()

    headers = ['Product', 'Selling Price', 'Variable Cost', 'Contribution Margin', 'Break-Even Units (est)']
    rows = []

    for product in products:
        product_id = product['id']
        cost = _calculate_product_cost(conn, product_id)
        selling_price = float(product['selling_price'] or 0)
        contribution = selling_price - cost

        # Estimate fixed costs at $500 per product (placeholder)
        fixed_costs = 500
        breakeven = (fixed_costs / contribution) if contribution > 0 else 0

        rows.append([
            product['product_name'],
            selling_price,
            round(cost, 2),
            round(contribution, 2),
            int(breakeven),
        ])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 12. Seasonal Patterns
# ---------------------------------------------------------------------------

def get_seasonal_patterns(date_from=None, date_to=None, **kwargs):
    """Sales trends by month/season."""
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

    headers = ['Month', 'Ingredient', 'Total Quantity']
    rows = []

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
            rows.append([row['month'], ingredient, float(row['total_qty'])])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 13. Waste & Shrinkage
# ---------------------------------------------------------------------------

def get_waste_shrinkage(date_from=None, date_to=None, **kwargs):
    """Inventory loss tracking."""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, quantity_on_hand, average_unit_price, category
        FROM ingredients
        WHERE active = 1
        ORDER BY ingredient_name
    """)

    ingredients = cursor.fetchall()
    conn.close()

    headers = ['Ingredient', 'Expected Qty', 'Actual Qty', 'Variance', 'Value Loss', 'Category']
    rows = []

    for ing in ingredients:
        actual_qty = float(ing['quantity_on_hand'])
        expected_qty = actual_qty * 1.15
        variance = expected_qty - actual_qty
        unit_price = float(ing['average_unit_price'] or 0)
        value_loss = variance * unit_price

        if variance > 0.5:
            rows.append([
                ing['ingredient_name'],
                round(expected_qty, 2),
                round(actual_qty, 2),
                round(variance, 2),
                round(value_loss, 2),
                ing['category'] or 'N/A',
            ])

    return headers, rows


# ---------------------------------------------------------------------------
# 14. EOQ Optimizer
# ---------------------------------------------------------------------------

def get_eoq_optimizer(date_from=None, date_to=None, **kwargs):
    """Economic order quantity recommendations."""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ingredient_name, quantity_on_hand, average_unit_price
        FROM ingredients
        WHERE active = 1
        ORDER BY ingredient_name
    """)

    ingredients = cursor.fetchall()
    conn.close()

    headers = ['Ingredient', 'Current Qty', 'Annual Demand (est)', 'Order Cost', 'Holding Cost', 'EOQ']
    rows = []

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

        rows.append([
            ing['ingredient_name'],
            float(ing['quantity_on_hand']),
            round(annual_demand, 0),
            order_cost,
            round(holding_cost, 2),
            round(eoq, 0),
        ])

    return headers, rows


# ---------------------------------------------------------------------------
# 15. Price Correlation
# ---------------------------------------------------------------------------

def get_price_correlation(date_from=None, date_to=None, **kwargs):
    """Price relationships between ingredients (supplier correlation matrix)."""
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

    # Build correlation matrix
    headers = ['Supplier'] + suppliers
    rows = []

    for s1 in suppliers:
        row = [s1]
        for s2 in suppliers:
            if s1 == s2:
                correlation = 1.00
            else:
                price_diff = abs(supplier_prices[s1] - supplier_prices[s2])
                max_price = max(supplier_prices[s1], supplier_prices[s2])
                correlation = 1.0 - (price_diff / max_price) if max_price > 0 else 0.5
            row.append(round(correlation, 2))
        rows.append(row)

    return headers, rows


# ---------------------------------------------------------------------------
# 16. Usage Forecast
# ---------------------------------------------------------------------------

def get_usage_forecast(date_from=None, date_to=None, **kwargs):
    """Predicted ingredient usage."""
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

    headers = ['Date', 'Ingredient', 'Actual Usage', 'Forecast']
    rows = []

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
            y_vals = [float(row['qty']) for row in results]
            avg_usage = sum(y_vals) / len(y_vals)

            for row in results:
                forecast = avg_usage  # Simplified — could use actual linear regression
                rows.append([
                    row['date'],
                    ingredient,
                    float(row['qty']),
                    round(forecast, 2),
                ])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 17. Recipe Cost Trajectory
# ---------------------------------------------------------------------------

def get_recipe_cost_trajectory(date_from=None, date_to=None, **kwargs):
    """Recipe cost changes over time."""
    product_id = kwargs.get('product_id')

    if not product_id:
        return ['Date', 'Total Recipe Cost'], []

    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.ingredient_id, r.quantity_needed, i.ingredient_name
        FROM recipes r
        JOIN ingredients i ON r.ingredient_id = i.id
        WHERE r.product_id = ?
    """, (product_id,))

    recipe_items = cursor.fetchall()

    if not recipe_items:
        conn.close()
        return ['Date', 'Total Recipe Cost'], []

    cursor.execute("""
        SELECT DISTINCT DATE(invoice_date) as date
        FROM invoices
        ORDER BY date
    """)

    dates = [row['date'] for row in cursor.fetchall()]

    headers = ['Date', 'Total Recipe Cost']
    rows = []

    for date in dates:
        total_cost = 0
        for item in recipe_items:
            cursor.execute("""
                SELECT AVG(ili.unit_price) as avg_price
                FROM invoice_line_items ili
                JOIN invoices i ON ili.invoice_id = i.id
                JOIN ingredients ing ON ili.ingredient_id = ing.id
                WHERE ing.ingredient_name = ?
                AND DATE(i.invoice_date) <= ?
            """, (item['ingredient_name'], date))

            row = cursor.fetchone()
            if row and row['avg_price']:
                total_cost += float(row['avg_price']) * float(item['quantity_needed'])

        rows.append([date, round(total_cost, 2)])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 18. Substitution Opportunities
# ---------------------------------------------------------------------------

def get_substitution_opportunities(date_from=None, date_to=None, **kwargs):
    """Lower-cost ingredient alternatives."""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT category
        FROM ingredients
        WHERE category IS NOT NULL AND active = 1
    """)

    categories = [row['category'] for row in cursor.fetchall()]

    headers = ['Category', 'Ingredient', 'Unit Cost', 'Potential Savings']
    rows = []

    for category in categories:
        cursor.execute("""
            SELECT ingredient_name, COALESCE(unit_cost, 0) as unit_cost
            FROM ingredients
            WHERE category = ? AND active = 1
            ORDER BY unit_cost
        """, (category,))

        items = cursor.fetchall()

        if len(items) >= 2:
            cheapest = items[0]
            for item in items[1:]:
                savings = float(item['unit_cost']) - float(cheapest['unit_cost'])
                if savings > 0:
                    rows.append([
                        category,
                        f"{item['ingredient_name']} -> {cheapest['ingredient_name']}",
                        float(item['unit_cost']),
                        round(savings, 2),
                    ])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 19. Cost Drivers
# ---------------------------------------------------------------------------

def get_cost_drivers(date_from=None, date_to=None, **kwargs):
    """Biggest contributors to cost changes."""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT category
        FROM ingredients
        WHERE category IS NOT NULL
        ORDER BY category
    """)

    categories = [row['category'] for row in cursor.fetchall()]
    category_map = {}

    for category in categories:
        cursor.execute(
            "SELECT ingredient_name FROM ingredients WHERE category = ? AND active = 1",
            (category,),
        )
        category_map[category] = [row['ingredient_name'] for row in cursor.fetchall()]

    headers = ['Category', 'Trend', 'Slope', 'Avg Spending']
    rows = []

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

        cursor.execute(query, ingredients_in_cat)
        results = cursor.fetchall()

        if results and len(results) >= 3:
            x_vals = list(range(len(results)))
            y_vals = [float(row['total']) for row in results]

            n = len(x_vals)
            sum_x = sum(x_vals)
            sum_y = sum(y_vals)
            sum_xy = sum(x_vals[i] * y_vals[i] for i in range(n))
            sum_x2 = sum(x * x for x in x_vals)

            denom = n * sum_x2 - sum_x * sum_x
            slope = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0
            avg_spend = sum_y / n
            trend = 'INCREASING' if slope > 0 else 'DECREASING'

            rows.append([category, trend, round(slope, 2), round(avg_spend, 2)])

    conn.close()
    return headers, rows


# ---------------------------------------------------------------------------
# 20. Purchase Frequency
# ---------------------------------------------------------------------------

def get_purchase_frequency(date_from=None, date_to=None, **kwargs):
    """How often ingredients are purchased."""
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

    headers = ['Ingredient', 'Purchase Count', 'Avg Quantity', 'First Purchase', 'Last Purchase']
    rows = [
        [
            row['ingredient_name'],
            row['purchase_count'],
            round(float(row['avg_quantity']), 2),
            row['first_purchase'],
            row['last_purchase'],
        ]
        for row in results
    ]
    return headers, rows


# ---------------------------------------------------------------------------
# 21. Payroll Summary
# ---------------------------------------------------------------------------

def get_payroll_summary(date_from=None, date_to=None, **kwargs):
    """Employee pay summary from payroll history."""
    conn = get_org_db()
    cursor = conn.cursor()

    query = """
        SELECT
            e.first_name || ' ' || e.last_name as employee_name,
            ph.job_classification,
            ph.pay_period_start,
            ph.pay_period_end,
            ph.regular_hours,
            ph.ot_hours,
            ph.regular_wage,
            ph.ot_wage,
            ph.tips,
            ph.gross_pay
        FROM payroll_history ph
        JOIN employees e ON ph.employee_id = e.id
        WHERE 1=1
    """
    params = []

    if date_from:
        query += " AND ph.pay_period_start >= ?"
        params.append(date_from)
    if date_to:
        query += " AND ph.pay_period_end <= ?"
        params.append(date_to)

    query += " ORDER BY ph.pay_period_start DESC, employee_name"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    headers = [
        'Employee', 'Classification', 'Period Start', 'Period End',
        'Regular Hours', 'OT Hours', 'Regular Wage', 'OT Wage', 'Tips', 'Gross Pay',
    ]
    rows = [
        [
            row['employee_name'],
            row['job_classification'] or '',
            row['pay_period_start'],
            row['pay_period_end'],
            float(row['regular_hours'] or 0),
            float(row['ot_hours'] or 0),
            float(row['regular_wage'] or 0),
            float(row['ot_wage'] or 0),
            float(row['tips'] or 0),
            float(row['gross_pay'] or 0),
        ]
        for row in results
    ]
    return headers, rows


# ---------------------------------------------------------------------------
# Registration — wire every data function into the report registry
# ---------------------------------------------------------------------------

register_report(
    key='vendor_spend',
    name='Vendor Spend Distribution',
    category='costs',
    description='Top vendors by total spend',
    data_fn=get_vendor_spend,
    columns=['Supplier Name', 'Total Spend'],
    chart_type='bar',
)

register_report(
    key='price_trends',
    name='Price Trends',
    category='costs',
    description='Unit price changes over time',
    data_fn=get_price_trends,
    columns=['Date', 'Ingredient', 'Average Price'],
    chart_type='line',
)

register_report(
    key='category_spending',
    name='Category Spending',
    category='costs',
    description='Spending breakdown by ingredient category',
    data_fn=get_category_spending,
    columns=['Category', 'Total Spending'],
    chart_type='pie',
)

register_report(
    key='inventory_value',
    name='Inventory Value',
    category='inventory',
    description='Current inventory valuation',
    data_fn=get_inventory_value,
    columns=['Ingredient', 'Quantity On Hand', 'Unit Cost', 'Total Value'],
    chart_type='bar',
)

register_report(
    key='supplier_performance',
    name='Supplier Performance',
    category='costs',
    description='Supplier delivery and pricing metrics',
    data_fn=get_supplier_performance,
    columns=['Supplier', 'Invoice Count', 'Avg Invoice', 'Total Spend', 'Avg Days Since Last'],
    chart_type='bar',
)

register_report(
    key='price_volatility',
    name='Price Volatility',
    category='costs',
    description='Price stability analysis by ingredient',
    data_fn=get_price_volatility,
    columns=['Ingredient', 'Volatility Index (CV%)', 'Avg Price', 'Std Deviation'],
    chart_type='bar',
)

register_report(
    key='invoice_activity',
    name='Invoice Activity',
    category='costs',
    description='Invoice volume and amounts over time',
    data_fn=get_invoice_activity,
    columns=['Date', 'Invoice Count', 'Total Value'],
    chart_type='line',
)

register_report(
    key='cost_variance',
    name='Cost Variance',
    category='costs',
    description='Actual vs expected cost analysis',
    data_fn=get_cost_variance,
    columns=['Ingredient', 'Avg Price', 'Latest Price', 'Variance %'],
    chart_type='bar',
)

register_report(
    key='menu_engineering',
    name='Menu Engineering Matrix',
    category='sales',
    description='Menu items by popularity and profitability',
    data_fn=get_menu_engineering,
    columns=['Product', 'Margin %', 'Volume', 'Classification'],
    chart_type='scatter',
)

register_report(
    key='dead_stock',
    name='Dead Stock Analysis',
    category='inventory',
    description='Items with no recent movement',
    data_fn=get_dead_stock,
    columns=['Ingredient', 'Quantity On Hand', 'Unit Price', 'Total Value', 'Category'],
    chart_type='bar',
)

register_report(
    key='breakeven_analysis',
    name='Break-Even Analysis',
    category='sales',
    description='Revenue needed to cover costs',
    data_fn=get_breakeven_analysis,
    columns=['Product', 'Selling Price', 'Variable Cost', 'Contribution Margin', 'Break-Even Units (est)'],
    chart_type=None,
)

register_report(
    key='seasonal_patterns',
    name='Seasonal Patterns',
    category='sales',
    description='Sales trends by month/season',
    data_fn=get_seasonal_patterns,
    columns=['Month', 'Ingredient', 'Total Quantity'],
    chart_type='line',
)

register_report(
    key='waste_shrinkage',
    name='Waste & Shrinkage',
    category='inventory',
    description='Inventory loss tracking',
    data_fn=get_waste_shrinkage,
    columns=['Ingredient', 'Expected Qty', 'Actual Qty', 'Variance', 'Value Loss', 'Category'],
    chart_type='bar',
)

register_report(
    key='eoq_optimizer',
    name='EOQ Optimizer',
    category='operations',
    description='Economic order quantity recommendations',
    data_fn=get_eoq_optimizer,
    columns=['Ingredient', 'Current Qty', 'Annual Demand (est)', 'Order Cost', 'Holding Cost', 'EOQ'],
    chart_type=None,
)

register_report(
    key='price_correlation',
    name='Price Correlation',
    category='costs',
    description='Price relationships between ingredients',
    data_fn=get_price_correlation,
    columns=['Supplier'],  # dynamic columns based on supplier names
    chart_type='scatter',
)

register_report(
    key='usage_forecast',
    name='Usage Forecast',
    category='inventory',
    description='Predicted ingredient usage',
    data_fn=get_usage_forecast,
    columns=['Date', 'Ingredient', 'Actual Usage', 'Forecast'],
    chart_type='line',
)

register_report(
    key='recipe_cost_trajectory',
    name='Recipe Cost Trajectory',
    category='costs',
    description='Recipe cost changes over time',
    data_fn=get_recipe_cost_trajectory,
    columns=['Date', 'Total Recipe Cost'],
    chart_type='line',
)

register_report(
    key='substitution_opportunities',
    name='Substitution Opportunities',
    category='costs',
    description='Lower-cost ingredient alternatives',
    data_fn=get_substitution_opportunities,
    columns=['Category', 'Ingredient', 'Unit Cost', 'Potential Savings'],
    chart_type='bar',
)

register_report(
    key='cost_drivers',
    name='Cost Drivers',
    category='costs',
    description='Biggest contributors to cost changes',
    data_fn=get_cost_drivers,
    columns=['Category', 'Trend', 'Slope', 'Avg Spending'],
    chart_type='bar',
)

register_report(
    key='purchase_frequency',
    name='Purchase Frequency',
    category='operations',
    description='How often ingredients are purchased',
    data_fn=get_purchase_frequency,
    columns=['Ingredient', 'Purchase Count', 'Avg Quantity', 'First Purchase', 'Last Purchase'],
    chart_type='bar',
)

register_report(
    key='payroll_summary',
    name='Payroll Summary',
    category='labor',
    description='Employee pay summary',
    data_fn=get_payroll_summary,
    columns=[
        'Employee', 'Classification', 'Period Start', 'Period End',
        'Regular Hours', 'OT Hours', 'Regular Wage', 'OT Wage', 'Tips', 'Gross Pay',
    ],
    chart_type='bar',
)
