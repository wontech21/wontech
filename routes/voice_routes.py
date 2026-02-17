"""
Voice AI routes — ephemeral session creation for OpenAI Realtime API.
"""

import os
import re
import sqlite3
from datetime import datetime
from flask import Blueprint, jsonify, request, g
import requests as http_requests

from db_manager import get_org_db
from middleware import login_required, organization_required

voice_bp = Blueprint('voice', __name__, url_prefix='/api/voice')

# ---------------------------------------------------------------------------
# Tool definitions — grouped by business domain.
# Each tool has a query_type param that maps to specific API endpoints.
# The browser JS handles the routing via a lookup table.
# ---------------------------------------------------------------------------
VOICE_TOOLS = [
    {
        "type": "function",
        "name": "query_sales",
        "description": (
            "Query sales and order data. Use for: today's sales, revenue, order history, "
            "sales overview, product-level sales details, time period comparisons. "
            "Covers everything related to money coming in."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What sales data to fetch.",
                    "enum": [
                        "orders_by_date",
                        "sales_history",
                        "sales_summary",
                        "sales_overview",
                        "product_sales_details",
                        "time_comparison",
                        "sales_by_order_type"
                    ]
                },
                "date": {"type": "string", "description": "Single date YYYY-MM-DD (for orders_by_date)."},
                "status": {"type": "string", "description": "Order status filter.", "enum": ["new", "confirmed", "preparing", "ready", "picked_up", "delivered", "served", "closed", "voided"]},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD."},
                "product_name": {"type": "string", "description": "Product name for product_sales_details."},
                "order_type": {"type": "string", "description": "Filter by order type.", "enum": ["dine_in", "pickup", "delivery", "online"]}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_inventory",
        "description": (
            "Query inventory data. Use for: stock levels, inventory value, detailed item info, "
            "aggregated totals, consolidated view, product list, product costs, recipes, "
            "ingredient costs, composite ingredients. Covers everything in the stockroom."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What inventory data to fetch.",
                    "enum": [
                        "summary",
                        "detailed",
                        "aggregated",
                        "consolidated",
                        "products",
                        "product_costs",
                        "recipes",
                        "recipe_for_product",
                        "ingredients_list",
                        "categories",
                        "brands"
                    ]
                },
                "category": {"type": "string", "description": "Filter by category."},
                "supplier": {"type": "string", "description": "Filter by supplier."},
                "brand": {"type": "string", "description": "Filter by brand."},
                "product_name": {"type": "string", "description": "Product name for recipe_for_product."},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_suppliers",
        "description": (
            "Query supplier and vendor data. Use for: supplier directory, vendor spending breakdown, "
            "supplier performance metrics, category-level spending. "
            "Use when asking about specific vendors, who you're spending the most with, supplier contacts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What supplier data to fetch.",
                    "enum": [
                        "supplier_list",
                        "vendor_spend",
                        "supplier_performance",
                        "category_spending"
                    ]
                },
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_invoices",
        "description": (
            "Query invoice and purchasing data. Use for: unpaid/unreconciled invoices, "
            "recent invoices, specific invoice details, invoice activity trends. "
            "Covers accounts payable and purchasing history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What invoice data to fetch.",
                    "enum": [
                        "unreconciled",
                        "recent",
                        "invoice_details",
                        "invoice_activity"
                    ]
                },
                "invoice_number": {"type": "string", "description": "Specific invoice number for invoice_details."},
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_employees",
        "description": (
            "Query employee/HR data. Use for: employee roster, individual employee details, "
            "contact info, positions, departments, employment status."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What employee data to fetch.",
                    "enum": ["list", "details"]
                },
                "employee_id": {"type": "integer", "description": "Employee ID for details."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_schedule",
        "description": (
            "Query scheduling data. Use for: who's working today/tomorrow, shift schedules, "
            "time-off requests, employee availability. Covers staffing and coverage questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What schedule data to fetch.",
                    "enum": [
                        "schedules",
                        "time_off_requests"
                    ]
                },
                "date": {"type": "string", "description": "Single date YYYY-MM-DD."},
                "start_date": {"type": "string", "description": "Range start YYYY-MM-DD."},
                "end_date": {"type": "string", "description": "Range end YYYY-MM-DD."},
                "employee_id": {"type": "integer", "description": "Filter to specific employee."},
                "department": {"type": "string", "description": "Filter by department."},
                "position": {"type": "string", "description": "Filter by position."},
                "status": {"type": "string", "description": "Filter by status (for time_off: pending, approved, denied)."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_attendance",
        "description": (
            "Query attendance and time tracking data. Use for: who's clocked in right now, "
            "attendance history, hours worked, break times, punctuality."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What attendance data to fetch.",
                    "enum": ["current_status", "history"]
                },
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_payroll",
        "description": (
            "Query payroll and labor cost data. Use for: weekly/monthly payroll, labor costs, "
            "wages, overtime, tips, payroll summary over a period."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What payroll data to fetch.",
                    "enum": ["weekly", "monthly", "summary"]
                },
                "week_start": {"type": "string", "description": "Week start date YYYY-MM-DD for weekly."},
                "month": {"type": "integer", "description": "Month 1-12 for monthly."},
                "year": {"type": "integer", "description": "Year for monthly."},
                "start_date": {"type": "string", "description": "Range start for summary."},
                "end_date": {"type": "string", "description": "Range end for summary."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_analytics",
        "description": (
            "Query advanced business analytics. Use for: KPI summary, price trends, purchase frequency, "
            "price volatility, cost variance, usage forecasts, recipe cost trends, ingredient substitutions, "
            "dead/slow stock, economic order quantity, seasonal patterns, menu engineering/profitability, "
            "waste and shrinkage analysis, inventory value tracking."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "Which analytics report to fetch.",
                    "enum": [
                        "summary",
                        "price_trends",
                        "purchase_frequency",
                        "price_volatility",
                        "cost_variance",
                        "usage_forecast",
                        "recipe_cost_trajectory",
                        "substitution_opportunities",
                        "dead_stock",
                        "eoq_optimizer",
                        "seasonal_patterns",
                        "menu_engineering",
                        "waste_shrinkage",
                        "inventory_value"
                    ]
                },
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD."},
                "days": {"type": "integer", "description": "Number of days for dead_stock (default 90)."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_pos",
        "description": (
            "Query point-of-sale operational data. Use for: kitchen display orders, "
            "register status, product availability, 86'd (unavailable) items, "
            "specific order details, order receipts, customer lookup."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What POS data to fetch.",
                    "enum": [
                        "kitchen",
                        "register",
                        "product_availability",
                        "eighty_sixed",
                        "order_details",
                        "customer_lookup"
                    ]
                },
                "order_id": {"type": "integer", "description": "Order ID for order_details."},
                "phone": {"type": "string", "description": "Phone for customer_lookup."},
                "name": {"type": "string", "description": "Name for customer_lookup."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "query_menu",
        "description": (
            "Query menu configuration. Use for: business hours, storefront settings, "
            "menu categories, menu items, modifier groups."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "What menu data to fetch.",
                    "enum": [
                        "hours",
                        "settings",
                        "categories",
                        "items",
                        "modifier_groups"
                    ]
                },
                "item_id": {"type": "integer", "description": "Item ID for item-specific modifiers."}
            },
            "required": ["query_type"]
        }
    },
    {
        "type": "function",
        "name": "run_sql_query",
        "description": (
            "Run a read-only SQL query against the business database. Use this for ad-hoc "
            "analytical questions that the other tools can't answer — cross-domain analysis, "
            "custom filters, aggregations, comparisons across time periods, ranking, etc. "
            "The database schema is provided in the system instructions. "
            "ONLY use SELECT statements. Limit results to 50 rows max. "
            "Always include a LIMIT clause."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A read-only SQL SELECT query. Must include LIMIT clause (max 50)."
                },
                "explanation": {
                    "type": "string",
                    "description": "Brief explanation of what this query does (for transparency)."
                }
            },
            "required": ["sql"]
        }
    },
    {
        "type": "function",
        "name": "create_visualization",
        "description": (
            "Render a chart/graph in the user's dashboard. Call this AFTER fetching data "
            "to visualize insights. You must compute the values yourself from the data you received. "
            "Use this for: trends over time (line), comparisons (bar), breakdowns (doughnut), "
            "or any analytical insight that benefits from visual representation. "
            "ALWAYS prefer this over letting raw data display as a table."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "horizontal_bar", "doughnut"],
                    "description": "line=trends over time, bar=comparisons, horizontal_bar=rankings, doughnut=proportional breakdown"
                },
                "title": {
                    "type": "string",
                    "description": "Chart title describing the insight (e.g. 'Labor Cost % by Month')"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "X-axis labels (dates, categories, names)"
                },
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["label", "values"]
                    },
                    "description": "One or more data series. Each has a label and values array matching labels length."
                },
                "format": {
                    "type": "string",
                    "enum": ["currency", "percent", "number"],
                    "description": "How to format values in tooltips/axis. currency=$X, percent=X%, number=X"
                }
            },
            "required": ["chart_type", "title", "labels", "datasets"]
        }
    },
]


def _get_db_schema():
    """Extract compact schema from the org's SQLite database.

    Only includes business-relevant tables — caches, widget configs,
    and internal bookkeeping are excluded to keep the system prompt
    small enough for the Realtime API to handle effectively.
    """
    ESSENTIAL_TABLES = {
        'sales_history', 'employees', 'attendance', 'payroll_history',
        'invoices', 'invoice_line_items', 'products', 'ingredients',
        'recipes', 'ingredient_recipes', 'suppliers', 'schedules',
        'time_off_requests', 'orders', 'order_items', 'categories',
        'brands', 'customers', 'business_hours', 'menu_items',
        'menu_categories', 'inventory_counts',
    }
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        lines = []
        for table in tables:
            if table not in ESSENTIAL_TABLES:
                continue
            cursor.execute(f'PRAGMA table_info({table})')
            cols = ', '.join([f"{c[1]} {c[2]}" for c in cursor.fetchall()])
            lines.append(f"{table}({cols})")
        conn.close()
        return '\n'.join(lines)
    except Exception as e:
        print(f'[Voice] Schema error: {e}')
        return ''


def _get_data_date_ranges():
    """Get the date range of data available across key tables."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()
        ranges = {}
        # Some tables have organization_id, some don't (per-tenant DB)
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


def _build_system_instructions(org_name, business_type='restaurant'):
    """Build the system prompt for the realtime session, including DB schema."""
    today = datetime.now().strftime('%A, %B %d, %Y')
    schema = _get_db_schema()
    date_ranges = _get_data_date_ranges()

    base = (
        f"You are a concise business assistant for {org_name} ({business_type}). "
        f"Today is {today}. "
        "Fetch real data with tools, summarize in 2-3 sentences. "
        "For analytics, use run_sql_query (SQLite). Always include LIMIT. "
        "Read-only access. Call tools immediately — never narrate before calling. "
        "Only speak AFTER you have the final result."

        "\n\nBUSINESS CONTEXT: "
        "This is a local restaurant. Typical monthly revenue is thousands to low tens of thousands of dollars, NOT hundreds of thousands or millions. "
        "If your query returns revenue/profit above $100,000 for a single month, something is wrong — recheck your SQL. "
        "Common mistakes: counting the same sale multiple times via bad JOINs, summing line-item prices instead of order totals, forgetting GROUP BY."

        "\n\nFINANCIAL DEFINITIONS: "
        "sales_history has ONE ROW PER PRODUCT SOLD (not per transaction). Columns: revenue, cost_of_goods, gross_profit, quantity_sold. "
        "Revenue = SUM(revenue) from sales_history. COGS = SUM(cost_of_goods). Gross Profit = SUM(gross_profit). "
        "These columns already exist — do NOT try to compute profit from other tables. "
        "Labor Cost = SUM(gross_pay) from payroll_history. "
        "NEVER report revenue AS profit. They are different columns. "
        "CRITICAL: When aggregating sales_history, do NOT join it to other tables unless absolutely necessary — "
        "joins multiply rows and inflate totals. Aggregate sales_history alone first, then join summaries if needed."

        "\n\nTABLE RELATIONSHIPS: "
        "sales_history: one row per product per sale. revenue/cost_of_goods/gross_profit are per-line amounts. SUM them directly. "
        "orders + order_items: POS orders. order_items has item-level detail. Do NOT double-count by joining orders to sales_history — they are separate systems. "
        "invoices + invoice_line_items: purchase invoices from suppliers. JOIN on invoice_line_items.invoice_id = invoices.id. "
        "products: product catalog with prices. NOT a sales record — don't sum product prices to get revenue. "
        "payroll_history: one row per employee per pay period. gross_pay is total compensation. "

        "\n\nSQLite rules: "
        "date('now'), date('now','-6 months'), strftime('%Y-%m', col). "
        "NO: DATEADD, DATEDIFF, NOW(), GETDATE(), DATE_FORMAT, EXTRACT, INTERVAL. "
        "Use || for concat, 1/0 for booleans, ROUND(x,2). "
        "Dates are TEXT 'YYYY-MM-DD'. Use >= and < for ranges. "
        "Product names have variants (e.g. 'Cheese Pizza - Large (16\")') — "
        "ALWAYS use LIKE '%keyword%', never exact match. "
        "Cross-table: NEVER join payroll_history to sales_history directly. "
        "Aggregate each table separately into subqueries, then join results. "
        "\nFor visualizations, call create_visualization after computing values. "
        "Chart types: line=trends, bar=comparisons, horizontal_bar=rankings, doughnut=breakdowns."
    )

    if date_ranges:
        base += "\n\nDATA AVAILABILITY:\n"
        for label, rng in date_ranges.items():
            base += f"- {label}: {rng}\n"

    if schema:
        base += f"\n\nDATABASE SCHEMA:\n{schema}"

    return base


@voice_bp.route('/session', methods=['POST'])
@login_required
@organization_required
def create_voice_session():
    """Create an ephemeral OpenAI Realtime session and return the client_secret."""

    # Only admins can use voice assistant
    if not (g.get('is_super_admin') or g.get('is_organization_admin')):
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({
            'success': False,
            'error': 'OpenAI API key not configured. Set the OPENAI_API_KEY environment variable.'
        }), 500

    org_name = g.organization.get('organization_name', 'your business')

    try:
        instructions = _build_system_instructions(org_name)
        import logging
        logging.basicConfig(filename='/tmp/voice_debug.log', level=logging.INFO, force=True)
        logging.info(f'Session instructions length: {len(instructions)} chars')
        logging.info(f'Schema included: {"DATABASE SCHEMA" in instructions}')
        logging.info(f'Instructions:\n{instructions[:500]}...')
        resp = http_requests.post(
            'https://api.openai.com/v1/realtime/sessions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'gpt-realtime',
                'voice': 'verse',
                'modalities': ['audio', 'text'],
                'instructions': instructions,
                'tools': VOICE_TOOLS,
                'turn_detection': {
                    'type': 'server_vad',
                    'threshold': 0.7,
                    'prefix_padding_ms': 300,
                    'silence_duration_ms': 1000,
                },
            },
            timeout=10,
        )

        if resp.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'OpenAI API error: {resp.status_code}',
                'detail': resp.text
            }), 502

        data = resp.json()
        return jsonify({
            'success': True,
            'client_secret': data.get('client_secret', {}).get('value'),
            'expires_at': data.get('client_secret', {}).get('expires_at'),
        })

    except http_requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'OpenAI API request timed out'}), 504
    except http_requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'Could not connect to OpenAI API'}), 502
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# SQL query execution — read-only, row-limited, timeout-protected
# ---------------------------------------------------------------------------
_FORBIDDEN_PATTERN = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX)\b',
    re.IGNORECASE
)
_MAX_ROWS = 50
_QUERY_TIMEOUT_MS = 5000


@voice_bp.route('/query', methods=['POST'])
@login_required
@organization_required
def run_voice_query():
    """Execute a read-only SQL query against the org database."""

    if not (g.get('is_super_admin') or g.get('is_organization_admin')):
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    import logging
    data = request.get_json()
    sql = (data.get('sql') or '').strip()
    logging.info(f'Voice SQL: {sql}')

    if not sql:
        return jsonify({'success': False, 'error': 'No SQL query provided'}), 400

    # Safety: block anything that isn't a SELECT
    if _FORBIDDEN_PATTERN.search(sql):
        return jsonify({'success': False, 'error': 'Only SELECT queries are allowed'}), 403

    if not sql.upper().lstrip().startswith('SELECT'):
        return jsonify({'success': False, 'error': 'Query must start with SELECT'}), 403

    # Enforce row limit
    if 'LIMIT' not in sql.upper():
        sql += f' LIMIT {_MAX_ROWS}'

    conn = None
    try:
        conn = get_org_db()
        conn.execute(f'PRAGMA busy_timeout = {_QUERY_TIMEOUT_MS}')
        cursor = conn.cursor()
        cursor.execute(sql)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(_MAX_ROWS)

        # Convert to list of dicts for readability
        results = [dict(zip(columns, row)) for row in rows]

        return jsonify({
            'success': True,
            'columns': columns,
            'rows': results,
            'row_count': len(results),
        })

    except sqlite3.OperationalError as e:
        logging.error(f'Voice SQL error: {e} | SQL: {sql}')
        return jsonify({'success': False, 'error': f'SQL error: {str(e)}', 'sql': sql}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
