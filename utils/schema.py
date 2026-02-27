"""
Shared DB schema extraction — used by Voice AI and Ask-a-Question.
"""

from flask import g
from db_manager import get_org_db

_ESSENTIAL_TABLES = {
    'sales_history', 'employees', 'attendance', 'payroll_history',
    'invoices', 'invoice_line_items', 'products', 'ingredients',
    'recipes', 'ingredient_recipes', 'suppliers', 'schedules',
    'time_off_requests', 'orders', 'order_items', 'categories',
    'brands', 'customers', 'business_hours', 'menu_items',
    'menu_categories', 'inventory_counts',
}


def get_db_schema():
    """Extract compact schema from the org's SQLite database."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        lines = []
        for table in tables:
            if table not in _ESSENTIAL_TABLES:
                continue
            cursor.execute(f'PRAGMA table_info({table})')
            cols = ', '.join([f"{c[1]} {c[2]}" for c in cursor.fetchall()])
            lines.append(f"{table}({cols})")
        conn.close()
        return '\n'.join(lines)
    except Exception as e:
        print(f'[Schema] Error: {e}')
        return ''


def get_data_date_ranges():
    """Get the date range of data available across key tables."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        ranges = {}
        queries = [
            ('attendance', "SELECT MIN(date(clock_in)) as earliest, MAX(date(clock_in)) as latest FROM attendance WHERE organization_id = ?", True),
            ('payroll', "SELECT MIN(pay_period_start) as earliest, MAX(pay_period_end) as latest FROM payroll_history WHERE organization_id = ?", True),
            ('sales', "SELECT MIN(sale_date) as earliest, MAX(sale_date) as latest FROM sales_history", False),
            ('invoices', "SELECT MIN(invoice_date) as earliest, MAX(invoice_date) as latest FROM invoices", False),
        ]
        org_id = g.organization['id']
        for label, sql, has_org in queries:
            try:
                if has_org:
                    cursor.execute(sql, (org_id,))
                else:
                    cursor.execute(sql)
                row = cursor.fetchone()
                if row and row['earliest']:
                    ranges[label] = f"{row['earliest']} to {row['latest']}"
            except Exception:
                pass
        conn.close()
        return ranges
    except Exception:
        return {}
