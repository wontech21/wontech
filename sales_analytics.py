"""
Sales Analytics Endpoints
Provides detailed sales analytics and reporting
Multi-Tenant Support: Uses organization-specific databases
"""

from flask import request, jsonify
from datetime import datetime, timedelta

# Multi-tenant database manager
from db_manager import get_org_db


def register_analytics_routes(app, get_db_connection=None, INVENTORY_DB=None):
    """Register all sales analytics routes (multi-tenant enabled)"""

    @app.route('/api/analytics/sales-overview')
    def get_sales_overview():
        """Get sales overview with summary statistics"""
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        print(f"\n=== SALES OVERVIEW API CALLED ===")
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date}")

        try:
            conn = get_org_db()
            cursor = conn.cursor()

            # Build query with date filters
            where_clause = "WHERE 1=1"
            params = []

            if start_date:
                where_clause += " AND sale_date >= ?"
                params.append(start_date)

            if end_date:
                where_clause += " AND sale_date <= ?"
                params.append(end_date)

            print(f"Where clause: {where_clause}")
            print(f"Params: {params}")

            # Test query to see what dates exist
            cursor.execute("SELECT MIN(sale_date), MAX(sale_date), COUNT(*) FROM sales_history")
            date_range = cursor.fetchone()
            print(f"Date range in DB: {date_range}")

            # Get summary statistics
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_transactions,
                    SUM(quantity_sold) as total_items_sold,
                    SUM(revenue) as total_revenue,
                    SUM(cost_of_goods) as total_cost,
                    SUM(gross_profit) as total_profit,
                    AVG(revenue) as avg_transaction_value,
                    SUM(discount_amount) as total_discounts
                FROM sales_history
                {where_clause}
            """, params)

            summary = dict(cursor.fetchone())
            print(f"Summary results: {summary}")

            # Get top selling products
            cursor.execute(f"""
                SELECT
                    product_name,
                    SUM(quantity_sold) as total_sold,
                    SUM(revenue) as total_revenue,
                    COUNT(*) as num_transactions
                FROM sales_history
                {where_clause}
                GROUP BY product_name
                ORDER BY total_sold DESC
                LIMIT 10
            """, params)

            top_products = [dict(row) for row in cursor.fetchall()]

            # Get sales by hour
            cursor.execute(f"""
                SELECT
                    SUBSTR(sale_time, 1, 2) as hour,
                    COUNT(*) as num_sales,
                    SUM(revenue) as revenue,
                    SUM(quantity_sold) as items_sold
                FROM sales_history
                {where_clause}
                AND sale_time IS NOT NULL
                GROUP BY hour
                ORDER BY hour
            """, params)

            sales_by_hour = [dict(row) for row in cursor.fetchall()]

            # Get sales by date
            cursor.execute(f"""
                SELECT
                    sale_date,
                    COUNT(*) as num_sales,
                    SUM(revenue) as revenue,
                    SUM(gross_profit) as profit
                FROM sales_history
                {where_clause}
                GROUP BY sale_date
                ORDER BY sale_date DESC
            """, params)

            sales_by_date = [dict(row) for row in cursor.fetchall()]

            # Get highest revenue transaction
            cursor.execute(f"""
                SELECT
                    product_name,
                    quantity_sold,
                    revenue,
                    sale_date,
                    sale_time
                FROM sales_history
                {where_clause}
                ORDER BY revenue DESC
                LIMIT 1
            """, params)

            highest_transaction = cursor.fetchone()
            highest_transaction = dict(highest_transaction) if highest_transaction else None

            # Sales breakdown by order type
            cursor.execute(f"""
                SELECT
                    COALESCE(order_type, 'dine_in') as order_type,
                    COUNT(*) as num_sales,
                    SUM(revenue) as revenue,
                    SUM(gross_profit) as profit
                FROM sales_history
                {where_clause}
                GROUP BY COALESCE(order_type, 'dine_in')
                ORDER BY revenue DESC
            """, params)

            sales_by_order_type = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return jsonify({
                'success': True,
                'summary': summary,
                'top_products': top_products,
                'sales_by_hour': sales_by_hour,
                'sales_by_date': sales_by_date,
                'highest_transaction': highest_transaction,
                'sales_by_order_type': sales_by_order_type
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/analytics/sales-by-order-type')
    def get_sales_by_order_type():
        """Standalone order-type breakdown with date filters (used by voice AI)."""
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        try:
            conn = get_org_db()
            cursor = conn.cursor()

            where_clause = "WHERE 1=1"
            params = []
            if start_date:
                where_clause += " AND sale_date >= ?"
                params.append(start_date)
            if end_date:
                where_clause += " AND sale_date <= ?"
                params.append(end_date)

            cursor.execute(f"""
                SELECT
                    COALESCE(order_type, 'dine_in') as order_type,
                    COUNT(*) as num_sales,
                    SUM(revenue) as revenue,
                    SUM(gross_profit) as profit
                FROM sales_history
                {where_clause}
                GROUP BY COALESCE(order_type, 'dine_in')
                ORDER BY revenue DESC
            """, params)

            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()

            return jsonify({'success': True, 'sales_by_order_type': rows})

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/analytics/product-details')
    def get_product_details():
        """Get detailed analytics for a specific product"""
        product_name = request.args.get('product_name')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not product_name:
            return jsonify({'success': False, 'error': 'Product name required'}), 400

        try:
            conn = get_org_db()
            cursor = conn.cursor()

            # Build query — use LIKE for partial matching (e.g. "Pizza" matches all pizza variants)
            where_clause = "WHERE LOWER(product_name) LIKE LOWER(?)"
            params = [f'%{product_name}%']

            if start_date:
                where_clause += " AND sale_date >= ?"
                params.append(start_date)

            if end_date:
                where_clause += " AND sale_date <= ?"
                params.append(end_date)

            # Get product summary
            cursor.execute(f"""
                SELECT
                    product_name,
                    COUNT(*) as total_transactions,
                    SUM(quantity_sold) as total_sold,
                    SUM(revenue) as total_revenue,
                    SUM(cost_of_goods) as total_cost,
                    SUM(gross_profit) as total_profit,
                    AVG(sale_price) as avg_sale_price,
                    MIN(sale_price) as min_sale_price,
                    MAX(sale_price) as max_sale_price,
                    SUM(discount_amount) as total_discounts
                FROM sales_history
                {where_clause}
                GROUP BY product_name
            """, params)

            summary = cursor.fetchone()
            summary = dict(summary) if summary else None

            # Get sales by date
            cursor.execute(f"""
                SELECT
                    sale_date,
                    COUNT(*) as num_sales,
                    SUM(quantity_sold) as quantity_sold,
                    SUM(revenue) as revenue,
                    AVG(sale_price) as avg_price
                FROM sales_history
                {where_clause}
                GROUP BY sale_date
                ORDER BY sale_date
            """, params)

            sales_by_date = [dict(row) for row in cursor.fetchall()]

            # Get sales by hour
            cursor.execute(f"""
                SELECT
                    SUBSTR(sale_time, 1, 2) as hour,
                    COUNT(*) as num_sales,
                    SUM(quantity_sold) as quantity_sold,
                    SUM(revenue) as revenue
                FROM sales_history
                {where_clause}
                AND sale_time IS NOT NULL
                GROUP BY hour
                ORDER BY hour
            """, params)

            sales_by_hour = [dict(row) for row in cursor.fetchall()]

            # Get recent transactions
            cursor.execute(f"""
                SELECT
                    sale_date,
                    sale_time,
                    quantity_sold,
                    sale_price,
                    revenue,
                    discount_amount
                FROM sales_history
                {where_clause}
                ORDER BY sale_date DESC, sale_time DESC
                LIMIT 20
            """, params)

            recent_sales = [dict(row) for row in cursor.fetchall()]

            conn.close()

            return jsonify({
                'success': True,
                'summary': summary,
                'sales_by_date': sales_by_date,
                'sales_by_hour': sales_by_hour,
                'recent_sales': recent_sales
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/analytics/time-comparison')
    def get_time_comparison():
        """Compare sales across different time periods"""
        try:
            conn = get_org_db()
            cursor = conn.cursor()

            today = datetime.now().date()

            # Today
            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(revenue), 0) as revenue,
                    COALESCE(SUM(gross_profit), 0) as profit
                FROM sales_history
                WHERE sale_date = ?
            """, (str(today),))
            today_stats = dict(cursor.fetchone())

            # This week
            week_start = today - timedelta(days=today.weekday())
            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(revenue), 0) as revenue,
                    COALESCE(SUM(gross_profit), 0) as profit
                FROM sales_history
                WHERE sale_date >= ?
            """, (str(week_start),))
            week_stats = dict(cursor.fetchone())

            # This month
            month_start = today.replace(day=1)
            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(revenue), 0) as revenue,
                    COALESCE(SUM(gross_profit), 0) as profit
                FROM sales_history
                WHERE sale_date >= ?
            """, (str(month_start),))
            month_stats = dict(cursor.fetchone())

            # Last 30 days
            days_30_ago = today - timedelta(days=30)
            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(revenue), 0) as revenue,
                    COALESCE(SUM(gross_profit), 0) as profit
                FROM sales_history
                WHERE sale_date >= ?
            """, (str(days_30_ago),))
            month_30_stats = dict(cursor.fetchone())

            # All time
            cursor.execute("""
                SELECT
                    COUNT(*) as transactions,
                    COALESCE(SUM(revenue), 0) as revenue,
                    COALESCE(SUM(gross_profit), 0) as profit
                FROM sales_history
            """)
            all_time_stats = dict(cursor.fetchone())

            conn.close()

            return jsonify({
                'success': True,
                'today': today_stats,
                'this_week': week_stats,
                'this_month': month_stats,
                'last_30_days': month_30_stats,
                'all_time': all_time_stats
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
