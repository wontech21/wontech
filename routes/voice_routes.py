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
from utils.schema import get_db_schema, get_data_date_ranges

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
            "Query menu/product data. 'items' returns the products sold through POS "
            "(the actual sellable items with prices). Also: business hours, categories."
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

# ---------------------------------------------------------------------------
# Action tool definitions — write operations via voice commands.
# Each tool requires verbal confirmation before execution.
# ---------------------------------------------------------------------------
VOICE_ACTION_TOOLS = [
    {
        "type": "function",
        "name": "manage_attendance",
        "description": (
            "Manage employee attendance: clock in, clock out, start break, end break. "
            "IMPORTANT: Always describe the action and ask 'Shall I go ahead?' before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "The attendance action to perform.",
                    "enum": ["clock_in", "clock_out", "break_start", "break_end"]
                },
                "employee_name": {"type": "string", "description": "Employee name (fuzzy matched)."},
                "employee_id": {"type": "integer", "description": "Employee ID if known."}
            },
            "required": ["action_type"]
        }
    },
    {
        "type": "function",
        "name": "manage_schedule",
        "description": (
            "Manage employee scheduling: create shifts, cancel shifts, approve or deny time-off requests. "
            "IMPORTANT: Always describe the action and ask 'Shall I go ahead?' before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "The schedule action to perform.",
                    "enum": ["create_shift", "cancel_shift", "approve_time_off", "deny_time_off"]
                },
                "employee_name": {"type": "string", "description": "Employee name (fuzzy matched)."},
                "employee_id": {"type": "integer", "description": "Employee ID if known."},
                "date": {"type": "string", "description": "Shift date YYYY-MM-DD."},
                "start_time": {"type": "string", "description": "Shift start time HH:MM."},
                "end_time": {"type": "string", "description": "Shift end time HH:MM."},
                "position": {"type": "string", "description": "Position/role for the shift."},
                "request_id": {"type": "integer", "description": "Time-off request ID."},
                "reason": {"type": "string", "description": "Reason for denial."}
            },
            "required": ["action_type"]
        }
    },
    {
        "type": "function",
        "name": "manage_orders",
        "description": (
            "Manage POS orders: update order status or void an order (reverses inventory). "
            "IMPORTANT: Always describe the action and ask 'Shall I go ahead?' before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "The order action to perform.",
                    "enum": ["update_status", "void_order"]
                },
                "order_id": {"type": "integer", "description": "Order ID."},
                "status": {
                    "type": "string",
                    "description": "New order status.",
                    "enum": ["confirmed", "preparing", "ready", "picked_up", "delivered", "served", "closed"]
                },
                "reason": {"type": "string", "description": "Reason for voiding."}
            },
            "required": ["action_type", "order_id"]
        }
    },
    {
        "type": "function",
        "name": "manage_86",
        "description": (
            "Mark menu items as 86'd (unavailable) or un-86 them (available again). "
            "IMPORTANT: Always describe the action and ask 'Shall I go ahead?' before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "86 to mark unavailable, un-86 to mark available again.",
                    "enum": ["eighty_six", "un_eighty_six"]
                },
                "product_name": {"type": "string", "description": "Product/menu item name (fuzzy matched)."},
                "product_id": {"type": "integer", "description": "Product ID if known."},
                "reason": {"type": "string", "description": "Reason for 86'ing."}
            },
            "required": ["action_type"]
        }
    },
    {
        "type": "function",
        "name": "manage_inventory",
        "description": (
            "Manage inventory: adjust stock quantities, toggle items active/inactive, "
            "update invoice payment status (PAID/UNPAID/PARTIAL). "
            "IMPORTANT: Always describe the action and ask 'Shall I go ahead?' before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "The inventory action to perform.",
                    "enum": ["adjust_quantity", "toggle_active", "update_invoice_status"]
                },
                "item_name": {"type": "string", "description": "Ingredient name (fuzzy matched)."},
                "item_id": {"type": "integer", "description": "Ingredient ID if known."},
                "new_quantity": {"type": "number", "description": "New stock quantity."},
                "unit": {"type": "string", "description": "Unit of measure."},
                "invoice_number": {"type": "string", "description": "Invoice number for payment status update."},
                "payment_status": {"type": "string", "description": "New payment status.", "enum": ["PAID", "UNPAID", "PARTIAL"]}
            },
            "required": ["action_type"]
        }
    },
    {
        "type": "function",
        "name": "manage_payroll",
        "description": (
            "Process or unprocess payroll for a pay period. "
            "WARNING: Processing locks the pay period — this is hard to undo. "
            "IMPORTANT: Always describe the action with EXTRA emphasis and ask 'Are you sure?' before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "Process or unprocess payroll.",
                    "enum": ["process", "unprocess"]
                },
                "period_start": {"type": "string", "description": "Pay period start YYYY-MM-DD."},
                "period_end": {"type": "string", "description": "Pay period end YYYY-MM-DD."},
                "period_type": {"type": "string", "description": "Period type.", "enum": ["weekly", "biweekly", "monthly"]}
            },
            "required": ["action_type", "period_start", "period_end"]
        }
    },
    {
        "type": "function",
        "name": "manage_menu",
        "description": (
            "Manage menu/product configuration: update product prices, toggle availability, "
            "change business hours for a day. Products are the items sold through POS. "
            "IMPORTANT: Always describe the action and ask 'Shall I go ahead?' before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "The menu action to perform.",
                    "enum": ["update_price", "toggle_item", "update_hours"]
                },
                "item_name": {"type": "string", "description": "Product name (fuzzy matched)."},
                "item_id": {"type": "integer", "description": "Product ID if known."},
                "new_price": {"type": "number", "description": "New price in dollars."},
                "active": {"type": "boolean", "description": "True to make available, false to 86."},
                "day": {"type": "string", "description": "Day of week for hours.", "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
                "open_time": {"type": "string", "description": "Opening time HH:MM (24h)."},
                "close_time": {"type": "string", "description": "Closing time HH:MM (24h)."},
                "is_closed": {"type": "boolean", "description": "True if closed for the day."}
            },
            "required": ["action_type"]
        }
    },
]


def _get_db_schema():
    """Delegate to shared utility."""
    return get_db_schema()


def _get_data_date_ranges():
    """Delegate to shared utility."""
    return get_data_date_ranges()


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
        "products: the MENU — sellable items with prices, category, pos_86d flag. This is what POS sells and what manage_menu modifies. NOT a sales record — don't sum product prices to get revenue. "
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

        "\n\nACTION CAPABILITIES: "
        "You can execute write actions using manage_* tools: clock employees in/out, "
        "manage breaks, create/cancel shifts, approve/deny time off, update order status, "
        "void orders, 86/un-86 items, adjust inventory quantities, update invoice payment status, "
        "process/unprocess payroll, update menu prices, toggle menu items, change business hours. "
        "The manage_* tools have smart fuzzy name matching built in — just pass the name "
        "the user said (e.g. 'supreme pizza', 'john') and the system will resolve it. "
        "Do NOT look up names yourself before calling manage_* tools. Just call them directly. "
        "If the name is ambiguous, the tool will return suggestions — relay those to the user. "
        "MANDATORY: Before calling ANY manage_* tool, describe exactly what you will do "
        "and ask 'Shall I go ahead?' — wait for explicit confirmation before proceeding. "
        "For payroll processing, add extra warning: 'This will lock the pay period and is hard to undo.' "
        "NEVER execute a write action without user confirmation."
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
                'tools': VOICE_TOOLS + VOICE_ACTION_TOOLS,
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


# ---------------------------------------------------------------------------
# Voice Action: Name resolution helpers
# ---------------------------------------------------------------------------

def _resolve_employee(params, cursor, org_id):
    """Resolve employee by name or ID. Returns (id, full_name) or raises ValueError."""
    emp_id = params.get('employee_id')
    if emp_id:
        cursor.execute(
            "SELECT id, first_name || ' ' || last_name as full_name FROM employees "
            "WHERE id = ? AND organization_id = ?",
            (emp_id, org_id)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Employee #{emp_id} not found")
        return row['id'], row['full_name']

    name = params.get('employee_name', '').strip()
    if not name:
        raise ValueError("No employee name or ID provided")

    # Priority 1: exact first name match (case-insensitive) — "John" → John Smith, not Marcus Johnson
    cursor.execute(
        "SELECT id, first_name || ' ' || last_name as full_name FROM employees "
        "WHERE organization_id = ? AND LOWER(first_name) = LOWER(?)",
        (org_id, name)
    )
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]['id'], rows[0]['full_name']
    if len(rows) > 1:
        names = ', '.join(r['full_name'] for r in rows[:5])
        raise ValueError(f"Multiple employees named '{name}': {names}. Please use their full name.")

    # Priority 2: exact full name match
    cursor.execute(
        "SELECT id, first_name || ' ' || last_name as full_name FROM employees "
        "WHERE organization_id = ? AND LOWER(first_name || ' ' || last_name) = LOWER(?)",
        (org_id, name)
    )
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]['id'], rows[0]['full_name']

    # Priority 3: substring match on full name
    cursor.execute(
        "SELECT id, first_name || ' ' || last_name as full_name FROM employees "
        "WHERE organization_id = ? AND (first_name || ' ' || last_name) LIKE ?",
        (org_id, f'%{name}%')
    )
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]['id'], rows[0]['full_name']
    if len(rows) > 1:
        names = ', '.join(r['full_name'] for r in rows[:5])
        raise ValueError(f"Multiple employees match '{name}': {names}. Please be more specific.")

    raise ValueError(f"No employee matching '{name}'")


def _resolve_product(params, cursor):
    """Resolve product by name or ID. Returns (id, product_name) or raises ValueError."""
    pid = params.get('product_id')
    if pid:
        cursor.execute("SELECT id, product_name FROM products WHERE id = ?", (pid,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Product #{pid} not found")
        return row['id'], row['product_name']

    name = params.get('product_name', '').strip()
    if not name:
        raise ValueError("No product name or ID provided")

    def _pick_best(rows, search):
        """From multiple matches, pick exact match or error with suggestions."""
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]['id'], rows[0]['product_name']
        exact = [r for r in rows if r['product_name'].lower() == search.lower()]
        if len(exact) == 1:
            return exact[0]['id'], exact[0]['product_name']
        names = ', '.join(r['product_name'] for r in rows[:5])
        raise ValueError(f"Multiple products match '{search}': {names}. Please specify which one.")

    # Priority 1: base name match — "Supreme Pizza" → "Supreme Pizza - Large (16\")"
    cursor.execute("SELECT id, product_name FROM products")
    all_products = cursor.fetchall()
    search_lower = name.lower()

    base_exact = [p for p in all_products if _product_base_name(p['product_name']).lower() == search_lower]
    if len(base_exact) == 1:
        return base_exact[0]['id'], base_exact[0]['product_name']
    if base_exact:
        names = ', '.join(p['product_name'] for p in base_exact[:5])
        raise ValueError(f"Multiple sizes match '{name}': {names}. Please specify which size.")

    # Priority 2: search is substring of base name
    base_partial = [p for p in all_products if search_lower in _product_base_name(p['product_name']).lower()]
    if len(base_partial) == 1:
        return base_partial[0]['id'], base_partial[0]['product_name']
    if base_partial:
        result = _pick_best(base_partial, name)
        if result:
            return result

    # Priority 3: substring of full product name
    full_matches = [p for p in all_products if search_lower in p['product_name'].lower()]
    result = _pick_best(full_matches, name)
    if result:
        return result

    # Priority 4: all significant words match (filtering stop words)
    words = [w for w in name.lower().split() if len(w) > 1 and w not in _STOP_WORDS]
    if len(words) > 1:
        where = ' AND '.join(['product_name LIKE ?' for _ in words])
        params_list = [f'%{w}%' for w in words]
        cursor.execute(f"SELECT id, product_name FROM products WHERE {where}", params_list)
        result = _pick_best(cursor.fetchall(), name)
        if result:
            return result

    # Priority 5: any significant word → suggest similar items
    if words:
        where = ' OR '.join(['product_name LIKE ?' for _ in words])
        params_list = [f'%{w}%' for w in words]
        cursor.execute(f"SELECT id, product_name FROM products WHERE {where} LIMIT 8", params_list)
        rows = cursor.fetchall()
        if rows:
            suggestions = ', '.join(r['product_name'] for r in rows)
            raise ValueError(
                f"No exact match for '{name}'. Did you mean one of these: {suggestions}?"
            )

    raise ValueError(f"No product matching '{name}'")


def _resolve_ingredient(params, cursor):
    """Resolve ingredient by name or ID. Returns (id, ingredient_name) or raises ValueError."""
    iid = params.get('item_id')
    if iid:
        cursor.execute("SELECT id, ingredient_name FROM ingredients WHERE id = ?", (iid,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Ingredient #{iid} not found")
        return row['id'], row['ingredient_name']

    name = params.get('item_name', '').strip()
    if not name:
        raise ValueError("No item name or ID provided")

    def _pick_best(rows, search):
        """From multiple matches, pick exact match or error with suggestions."""
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]['id'], rows[0]['ingredient_name']
        exact = [r for r in rows if r['ingredient_name'].lower() == search.lower()]
        if len(exact) == 1:
            return exact[0]['id'], exact[0]['ingredient_name']
        names = ', '.join(r['ingredient_name'] for r in rows[:5])
        raise ValueError(f"Multiple ingredients match '{search}': {names}. Please be more specific.")

    # Priority 1: substring match
    cursor.execute(
        "SELECT id, ingredient_name FROM ingredients WHERE ingredient_name LIKE ?",
        (f'%{name}%',)
    )
    result = _pick_best(cursor.fetchall(), name)
    if result:
        return result

    # Priority 2: all words must appear — "hot dog buns" → "Hot Dog Buns"
    words = [w for w in name.split() if len(w) > 2]
    if len(words) > 1:
        where = ' AND '.join(['ingredient_name LIKE ?' for _ in words])
        params_list = [f'%{w}%' for w in words]
        cursor.execute(f"SELECT id, ingredient_name FROM ingredients WHERE {where}", params_list)
        result = _pick_best(cursor.fetchall(), name)
        if result:
            return result

    # Priority 3: any word matches — suggest similar items so AI can ask user
    if words:
        where = ' OR '.join(['ingredient_name LIKE ?' for _ in words])
        params_list = [f'%{w}%' for w in words]
        cursor.execute(f"SELECT id, ingredient_name FROM ingredients WHERE {where} LIMIT 8", params_list)
        rows = cursor.fetchall()
        if rows:
            suggestions = ', '.join(r['ingredient_name'] for r in rows)
            raise ValueError(
                f"No exact match for '{name}'. Similar ingredients: {suggestions}. "
                f"Ask the user which one they mean."
            )

    raise ValueError(f"No ingredient matching '{name}'")


def _product_base_name(full_name):
    """Extract base product name: 'Supreme Pizza - Large (16\")' → 'Supreme Pizza'."""
    import re
    base = full_name.split(' - ')[0].strip()
    base = re.sub(r'\s*\(.*\)$', '', base).strip()
    return base


_STOP_WORDS = {'the', 'a', 'an', 'of', 'for', 'and', 'or', 'to', 'in', 'on', 'at', 'by', 'with', 'from',
               'its', 'our', 'my', 'inch', 'size', 'please', 'change', 'update', 'set', 'make'}


def _resolve_menu_item(params, cursor):
    """Resolve menu item from PRODUCTS table by name or ID. Returns (id, product_name) or raises ValueError."""
    mid = params.get('item_id')
    if mid:
        cursor.execute("SELECT id, product_name FROM products WHERE id = ?", (mid,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Product #{mid} not found")
        return row['id'], row['product_name']

    name = params.get('item_name', '').strip()
    if not name:
        raise ValueError("No item name or ID provided")

    def _pick_best(rows, search):
        """From multiple matches, pick exact match or error with suggestions."""
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]['id'], rows[0]['product_name']
        exact = [r for r in rows if r['product_name'].lower() == search.lower()]
        if len(exact) == 1:
            return exact[0]['id'], exact[0]['product_name']
        names = ', '.join(r['product_name'] for r in rows[:5])
        raise ValueError(f"Multiple products match '{search}': {names}. Please specify which one.")

    # Priority 1: exact base name match — "Supreme Pizza" → "Supreme Pizza - Large (16\")"
    # Like employee first-name matching: match the core identity, ignore size/variant
    cursor.execute("SELECT id, product_name FROM products")
    all_products = cursor.fetchall()
    search_lower = name.lower()

    base_exact = [p for p in all_products if _product_base_name(p['product_name']).lower() == search_lower]
    if len(base_exact) == 1:
        return base_exact[0]['id'], base_exact[0]['product_name']
    if base_exact:
        names = ', '.join(p['product_name'] for p in base_exact[:5])
        raise ValueError(f"Multiple sizes match '{name}': {names}. Please specify which size.")

    # Priority 2: search is substring of base name — "Supreme" → base "Supreme Pizza"
    base_partial = [p for p in all_products if search_lower in _product_base_name(p['product_name']).lower()]
    if len(base_partial) == 1:
        return base_partial[0]['id'], base_partial[0]['product_name']
    if base_partial:
        result = _pick_best(base_partial, name)
        if result:
            return result

    # Priority 3: substring of full product name
    cursor.execute("SELECT id, product_name FROM products WHERE product_name LIKE ?", (f'%{name}%',))
    result = _pick_best(cursor.fetchall(), name)
    if result:
        return result

    # Priority 4: all significant words match (filtering stop words)
    words = [w for w in name.lower().split() if len(w) > 1 and w not in _STOP_WORDS]
    if len(words) > 1:
        where = ' AND '.join(['product_name LIKE ?' for _ in words])
        params_list = [f'%{w}%' for w in words]
        cursor.execute(f"SELECT id, product_name FROM products WHERE {where}", params_list)
        result = _pick_best(cursor.fetchall(), name)
        if result:
            return result

    # Priority 5: any significant word → suggest similar items
    if words:
        where = ' OR '.join(['product_name LIKE ?' for _ in words])
        params_list = [f'%{w}%' for w in words]
        cursor.execute(f"SELECT id, product_name FROM products WHERE {where} LIMIT 8", params_list)
        rows = cursor.fetchall()
        if rows:
            suggestions = ', '.join(r['product_name'] for r in rows)
            raise ValueError(
                f"No exact match for '{name}'. Did you mean one of these: {suggestions}?"
            )

    raise ValueError(f"No product matching '{name}'")


# ---------------------------------------------------------------------------
# Voice Action: Handler functions
# ---------------------------------------------------------------------------

def _handle_attendance(params, conn, user_id):
    action_type = params.get('action_type')
    org_id = g.organization['id']
    cursor = conn.cursor()
    emp_id, emp_name = _resolve_employee(params, cursor, org_id)
    now = datetime.now().strftime('%I:%M %p')

    if action_type == 'clock_in':
        cursor.execute(
            "SELECT id FROM attendance WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL",
            (emp_id, org_id)
        )
        if cursor.fetchone():
            return {'success': False, 'error': f'{emp_name} is already clocked in'}
        cursor.execute(
            "INSERT INTO attendance (organization_id, employee_id, clock_in, status) "
            "VALUES (?, ?, datetime('now', 'localtime'), 'clocked_in')",
            (org_id, emp_id)
        )
        conn.commit()
        return {'success': True, 'message': f'{emp_name} clocked in at {now}', 'entity_id': emp_id}

    elif action_type == 'clock_out':
        cursor.execute(
            "SELECT id FROM attendance WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL",
            (emp_id, org_id)
        )
        record = cursor.fetchone()
        if not record:
            return {'success': False, 'error': f'{emp_name} is not clocked in'}
        cursor.execute(
            "UPDATE attendance SET clock_out = datetime('now', 'localtime'), status = 'clocked_out', "
            "total_hours = ROUND((julianday(datetime('now', 'localtime')) - julianday(clock_in)) * 24, 2), "
            "updated_at = datetime('now', 'localtime') WHERE id = ?",
            (record['id'],)
        )
        conn.commit()
        return {'success': True, 'message': f'{emp_name} clocked out at {now}', 'entity_id': emp_id}

    elif action_type == 'break_start':
        cursor.execute(
            "SELECT id, break_start, break_end FROM attendance "
            "WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL",
            (emp_id, org_id)
        )
        record = cursor.fetchone()
        if not record:
            return {'success': False, 'error': f'{emp_name} is not clocked in'}
        if record['break_start'] and not record['break_end']:
            return {'success': False, 'error': f'{emp_name} is already on break'}
        cursor.execute(
            "UPDATE attendance SET break_start = datetime('now', 'localtime'), "
            "status = 'on_break', updated_at = datetime('now', 'localtime') WHERE id = ?",
            (record['id'],)
        )
        conn.commit()
        return {'success': True, 'message': f'{emp_name} started break at {now}', 'entity_id': emp_id}

    elif action_type == 'break_end':
        cursor.execute(
            "SELECT id, break_start, break_end FROM attendance "
            "WHERE employee_id = ? AND organization_id = ? AND clock_out IS NULL",
            (emp_id, org_id)
        )
        record = cursor.fetchone()
        if not record:
            return {'success': False, 'error': f'{emp_name} is not clocked in'}
        if not record['break_start'] or record['break_end']:
            return {'success': False, 'error': f'{emp_name} is not on break'}
        cursor.execute(
            "UPDATE attendance SET break_end = datetime('now', 'localtime'), status = 'clocked_in', "
            "break_duration = CAST((julianday(datetime('now', 'localtime')) - julianday(break_start)) * 1440 AS INTEGER), "
            "updated_at = datetime('now', 'localtime') WHERE id = ?",
            (record['id'],)
        )
        conn.commit()
        return {'success': True, 'message': f'{emp_name} ended break at {now}', 'entity_id': emp_id}

    return {'success': False, 'error': f'Unknown attendance action: {action_type}'}


def _handle_schedule(params, conn, user_id):
    action_type = params.get('action_type')
    org_id = g.organization['id']
    cursor = conn.cursor()

    if action_type == 'create_shift':
        emp_id, emp_name = _resolve_employee(params, cursor, org_id)
        date = params.get('date')
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        if not all([date, start_time, end_time]):
            return {'success': False, 'error': 'date, start_time, and end_time are required'}

        # Conflict check
        cursor.execute(
            "SELECT id FROM schedules WHERE employee_id = ? AND date = ? AND status != 'cancelled' "
            "AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?) "
            "OR (start_time >= ? AND end_time <= ?))",
            (emp_id, date, start_time, start_time, end_time, end_time, start_time, end_time)
        )
        if cursor.fetchone():
            return {'success': False, 'error': f'{emp_name} already has a conflicting shift on {date}'}

        position = params.get('position', '')
        cursor.execute(
            "INSERT INTO schedules (organization_id, employee_id, date, start_time, end_time, position, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (org_id, emp_id, date, start_time, end_time, position, user_id)
        )
        conn.commit()
        return {
            'success': True,
            'message': f'Shift created for {emp_name} on {date} ({start_time} - {end_time})',
            'entity_id': cursor.lastrowid
        }

    elif action_type == 'cancel_shift':
        schedule_id = params.get('schedule_id')
        if not schedule_id:
            emp_id, emp_name = _resolve_employee(params, cursor, org_id)
            date = params.get('date')
            if not date:
                return {'success': False, 'error': 'Either schedule_id or employee name + date required'}
            cursor.execute(
                "SELECT id FROM schedules WHERE employee_id = ? AND date = ? "
                "AND organization_id = ? AND status != 'cancelled'",
                (emp_id, date, org_id)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': f'No active shift found for {emp_name} on {date}'}
            schedule_id = row['id']

        cursor.execute(
            "UPDATE schedules SET status = 'cancelled', updated_by = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND organization_id = ?",
            (user_id, schedule_id, org_id)
        )
        if cursor.rowcount == 0:
            return {'success': False, 'error': f'Shift #{schedule_id} not found'}
        conn.commit()
        return {'success': True, 'message': f'Shift #{schedule_id} cancelled', 'entity_id': schedule_id}

    elif action_type == 'approve_time_off':
        request_id = params.get('request_id')
        if not request_id:
            emp_id, emp_name = _resolve_employee(params, cursor, org_id)
            cursor.execute(
                "SELECT id FROM time_off_requests WHERE employee_id = ? AND organization_id = ? "
                "AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
                (emp_id, org_id)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': f'No pending time-off request for {emp_name}'}
            request_id = row['id']

        cursor.execute(
            "SELECT id, employee_id, status, request_type, total_hours "
            "FROM time_off_requests WHERE id = ? AND organization_id = ?",
            (request_id, org_id)
        )
        req = cursor.fetchone()
        if not req:
            return {'success': False, 'error': f'Time-off request #{request_id} not found'}
        if req['status'] != 'pending':
            return {'success': False, 'error': f'Request #{request_id} is already {req["status"]}'}

        cursor.execute(
            "UPDATE time_off_requests SET status = 'approved', reviewed_by = ?, "
            "reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id, request_id)
        )
        # Deduct PTO balance if applicable
        if req['request_type'] == 'pto':
            cursor.execute(
                "UPDATE employees SET pto_hours_available = pto_hours_available - ?, "
                "pto_hours_used = pto_hours_used + ? WHERE id = ? AND organization_id = ?",
                (req['total_hours'], req['total_hours'], req['employee_id'], org_id)
            )
        conn.commit()
        cursor.execute(
            "SELECT first_name || ' ' || last_name as name FROM employees WHERE id = ?",
            (req['employee_id'],)
        )
        emp = cursor.fetchone()
        return {
            'success': True,
            'message': f"Time-off approved for {emp['name'] if emp else 'employee'} (request #{request_id})",
            'entity_id': request_id
        }

    elif action_type == 'deny_time_off':
        request_id = params.get('request_id')
        if not request_id:
            emp_id, emp_name = _resolve_employee(params, cursor, org_id)
            cursor.execute(
                "SELECT id FROM time_off_requests WHERE employee_id = ? AND organization_id = ? "
                "AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
                (emp_id, org_id)
            )
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': f'No pending time-off request for {emp_name}'}
            request_id = row['id']

        reason = params.get('reason', '')
        cursor.execute(
            "SELECT id, employee_id, status FROM time_off_requests WHERE id = ? AND organization_id = ?",
            (request_id, org_id)
        )
        req = cursor.fetchone()
        if not req:
            return {'success': False, 'error': f'Time-off request #{request_id} not found'}
        if req['status'] != 'pending':
            return {'success': False, 'error': f'Request #{request_id} is already {req["status"]}'}

        cursor.execute(
            "UPDATE time_off_requests SET status = 'denied', reason = ?, reviewed_by = ?, "
            "reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (reason, user_id, request_id)
        )
        conn.commit()
        cursor.execute(
            "SELECT first_name || ' ' || last_name as name FROM employees WHERE id = ?",
            (req['employee_id'],)
        )
        emp = cursor.fetchone()
        return {
            'success': True,
            'message': f"Time-off denied for {emp['name'] if emp else 'employee'} (request #{request_id})",
            'entity_id': request_id
        }

    return {'success': False, 'error': f'Unknown schedule action: {action_type}'}


def _handle_orders(params, conn, user_id):
    action_type = params.get('action_type')
    cursor = conn.cursor()
    order_id = params.get('order_id')
    if not order_id:
        return {'success': False, 'error': 'order_id is required'}

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        return {'success': False, 'error': f'Order #{order_id} not found'}

    if action_type == 'update_status':
        new_status = params.get('status')
        valid = ['confirmed', 'preparing', 'ready', 'picked_up', 'delivered', 'served', 'closed']
        if new_status not in valid:
            return {'success': False, 'error': f'Invalid status. Valid: {", ".join(valid)}'}

        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        values = [new_status]
        if new_status == 'ready':
            updates.append("actual_ready_time = CURRENT_TIMESTAMP")

        values.append(order_id)
        cursor.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        return {'success': True, 'message': f'Order #{order_id} updated to {new_status}', 'entity_id': order_id}

    elif action_type == 'void_order':
        if order['status'] == 'voided':
            return {'success': False, 'error': f'Order #{order_id} is already voided'}

        reason = params.get('reason', 'Voided via voice assistant')
        cursor.execute(
            "UPDATE orders SET status = 'voided', voided_at = CURRENT_TIMESTAMP, "
            "void_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (reason, order_id)
        )

        # Reverse inventory deductions
        cursor.execute(
            "SELECT product_id, product_name, quantity FROM order_items WHERE order_id = ?",
            (order_id,)
        )
        items = cursor.fetchall()
        for item in items:
            cursor.execute(
                "SELECT ingredient_id, quantity_needed FROM recipes WHERE product_id = ?",
                (item['product_id'],)
            )
            recipe = cursor.fetchall()
            for ing in recipe:
                restore_qty = ing['quantity_needed'] * item['quantity']
                cursor.execute(
                    "UPDATE ingredients SET quantity_on_hand = quantity_on_hand + ?, "
                    "last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                    (restore_qty, ing['ingredient_id'])
                )

            # Mark sales_history as voided
            order_date = (order['created_at'] or '').split('T')[0].split(' ')[0]
            if order_date:
                cursor.execute(
                    "UPDATE sales_history SET notes = 'VOIDED' "
                    "WHERE product_id = ? AND sale_date = ? "
                    "AND id IN ("
                    "  SELECT id FROM sales_history WHERE product_id = ? AND sale_date = ? "
                    "  AND (notes IS NULL OR notes != 'VOIDED') ORDER BY id DESC LIMIT ?"
                    ")",
                    (item['product_id'], order_date,
                     item['product_id'], order_date, item['quantity'])
                )

        conn.commit()
        return {'success': True, 'message': f'Order #{order_id} voided. Inventory restored.', 'entity_id': order_id}

    return {'success': False, 'error': f'Unknown order action: {action_type}'}


def _handle_86(params, conn, user_id):
    action_type = params.get('action_type')
    cursor = conn.cursor()

    # Ensure pos_86d column exists
    try:
        cursor.execute("SELECT pos_86d FROM products LIMIT 1")
    except Exception:
        cursor.execute("ALTER TABLE products ADD COLUMN pos_86d INTEGER DEFAULT 0")

    pid, pname = _resolve_product(params, cursor)
    new_val = 1 if action_type == 'eighty_six' else 0
    action_word = "86'd (unavailable)" if new_val else "un-86'd (available)"

    cursor.execute("UPDATE products SET pos_86d = ? WHERE id = ?", (new_val, pid))
    conn.commit()
    return {'success': True, 'message': f'{pname} has been {action_word}', 'entity_id': pid}


def _handle_inventory(params, conn, user_id):
    action_type = params.get('action_type')
    cursor = conn.cursor()

    if action_type == 'adjust_quantity':
        iid, iname = _resolve_ingredient(params, cursor)
        new_qty = params.get('new_quantity')
        if new_qty is None:
            return {'success': False, 'error': 'new_quantity is required'}
        cursor.execute(
            "UPDATE ingredients SET quantity_on_hand = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
            (new_qty, iid)
        )
        conn.commit()
        unit = params.get('unit', '')
        return {'success': True, 'message': f'{iname} updated to {new_qty} {unit}'.strip(), 'entity_id': iid}

    elif action_type == 'toggle_active':
        iid, iname = _resolve_ingredient(params, cursor)
        cursor.execute("SELECT active FROM ingredients WHERE id = ?", (iid,))
        current = cursor.fetchone()
        new_active = 0 if current['active'] else 1
        cursor.execute(
            "UPDATE ingredients SET active = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
            (new_active, iid)
        )
        conn.commit()
        status_word = 'activated' if new_active else 'deactivated'
        return {'success': True, 'message': f'{iname} {status_word}', 'entity_id': iid}

    elif action_type == 'update_invoice_status':
        inv_num = params.get('invoice_number')
        if not inv_num:
            return {'success': False, 'error': 'invoice_number is required'}
        new_status = params.get('payment_status', 'PAID')

        cursor.execute(
            "SELECT id, invoice_number, supplier_name FROM invoices WHERE invoice_number = ?",
            (inv_num,)
        )
        inv = cursor.fetchone()
        if not inv:
            return {'success': False, 'error': f'Invoice {inv_num} not found'}

        cursor.execute(
            "UPDATE invoices SET payment_status = ? WHERE invoice_number = ?",
            (new_status, inv_num)
        )
        conn.commit()
        return {
            'success': True,
            'message': f'Invoice {inv_num} ({inv["supplier_name"]}) marked as {new_status}',
            'entity_id': inv['id']
        }

    return {'success': False, 'error': f'Unknown inventory action: {action_type}'}


def _handle_payroll(params, conn, user_id):
    action_type = params.get('action_type')
    org_id = g.organization['id']
    cursor = conn.cursor()
    period_start = params.get('period_start')
    period_end = params.get('period_end')
    period_type = params.get('period_type', 'weekly')

    if not period_start or not period_end:
        return {'success': False, 'error': 'period_start and period_end are required'}

    if action_type == 'unprocess':
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM payroll_history "
            "WHERE organization_id = ? AND pay_period_start = ? AND pay_period_end = ?",
            (org_id, period_start, period_end)
        )
        count = cursor.fetchone()['cnt']
        if count == 0:
            return {'success': False, 'error': f'No payroll found for {period_start} to {period_end}'}
        cursor.execute(
            "DELETE FROM payroll_history "
            "WHERE organization_id = ? AND pay_period_start = ? AND pay_period_end = ?",
            (org_id, period_start, period_end)
        )
        conn.commit()
        return {
            'success': True,
            'message': f'Payroll unprocessed for {period_start} to {period_end} ({count} records removed)',
            'entity_id': 0
        }

    elif action_type == 'process':
        # Check if already processed
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM payroll_history "
            "WHERE organization_id = ? AND pay_period_start = ? AND pay_period_end = ?",
            (org_id, period_start, period_end)
        )
        if cursor.fetchone()['cnt'] > 0:
            return {
                'success': False,
                'error': f'Payroll already processed for {period_start} to {period_end}. Unprocess first to rerun.'
            }

        # Get all active employees
        cursor.execute(
            "SELECT * FROM employees WHERE organization_id = ? AND status = 'active'",
            (org_id,)
        )
        employees = cursor.fetchall()
        if not employees:
            return {'success': False, 'error': 'No active employees found'}

        processed = 0
        for emp in employees:
            emp_dict = dict(emp)

            # Calculate hours from attendance
            cursor.execute(
                "SELECT COALESCE(SUM(total_hours), 0) as total_hours FROM attendance "
                "WHERE employee_id = ? AND organization_id = ? "
                "AND date(clock_in) >= ? AND date(clock_in) <= ? AND clock_out IS NOT NULL",
                (emp_dict['id'], org_id, period_start, period_end)
            )
            total_hours = cursor.fetchone()['total_hours'] or 0

            hourly_rate = emp_dict.get('hourly_rate') or emp_dict.get('pay_rate') or 0
            salary = emp_dict.get('salary_amount') or 0

            if total_hours == 0 and not salary:
                continue  # Skip employees with no hours and no salary

            regular_hours = min(total_hours, 40)
            ot_hours = max(total_hours - 40, 0)
            regular_wage = round(regular_hours * hourly_rate, 2)
            ot_wage = round(ot_hours * hourly_rate * 1.5, 2)

            # Tips
            tips = 0
            if emp_dict.get('receives_tips'):
                cursor.execute(
                    "SELECT COALESCE(SUM(cc_tips), 0) as tips FROM attendance "
                    "WHERE employee_id = ? AND organization_id = ? "
                    "AND date(clock_in) >= ? AND date(clock_in) <= ?",
                    (emp_dict['id'], org_id, period_start, period_end)
                )
                tips = cursor.fetchone()['tips'] or 0

            gross_pay = salary if salary else round(regular_wage + ot_wage + tips, 2)

            try:
                cursor.execute(
                    "INSERT INTO payroll_history ("
                    "  organization_id, employee_id, pay_period_start, pay_period_end, "
                    "  pay_period_type, hourly_rate_used, salary_used, "
                    "  total_hours, regular_hours, ot_hours, "
                    "  regular_wage, ot_wage, tips, gross_pay, "
                    "  job_classification, position, processed_by"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        org_id, emp_dict['id'], period_start, period_end,
                        period_type, hourly_rate, salary,
                        round(total_hours, 2), round(regular_hours, 2), round(ot_hours, 2),
                        regular_wage, ot_wage, round(tips, 2), round(gross_pay, 2),
                        emp_dict.get('job_classification', ''), emp_dict.get('position', ''),
                        user_id
                    )
                )
                processed += 1
            except sqlite3.IntegrityError:
                continue  # Skip duplicates (UNIQUE constraint)

        conn.commit()
        return {
            'success': True,
            'message': f'Payroll processed for {period_start} to {period_end}: {processed} employees',
            'entity_id': 0
        }

    return {'success': False, 'error': f'Unknown payroll action: {action_type}'}


def _handle_menu(params, conn, user_id):
    action_type = params.get('action_type')
    cursor = conn.cursor()

    if action_type == 'update_price':
        mid, mname = _resolve_menu_item(params, cursor)
        new_price = params.get('new_price')
        if new_price is None:
            return {'success': False, 'error': 'new_price is required'}

        cursor.execute(
            "UPDATE products SET selling_price = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
            (new_price, mid)
        )
        conn.commit()
        return {'success': True, 'message': f'{mname} price updated to ${new_price:.2f}', 'entity_id': mid}

    elif action_type == 'toggle_item':
        mid, mname = _resolve_menu_item(params, cursor)
        active = params.get('active')
        if active is None:
            cursor.execute("SELECT pos_86d FROM products WHERE id = ?", (mid,))
            current = cursor.fetchone()
            # pos_86d=1 means unavailable, so flip: active means NOT 86'd
            active = bool(current['pos_86d'])  # if currently 86'd, make active
        new_86d = 0 if active else 1
        cursor.execute(
            "UPDATE products SET pos_86d = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
            (new_86d, mid)
        )
        conn.commit()
        status_word = 'available' if not new_86d else 'unavailable (86\'d)'
        return {'success': True, 'message': f'{mname} marked as {status_word}', 'entity_id': mid}

    elif action_type == 'update_hours':
        day_name = params.get('day', '').lower()
        DAY_MAP = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        day_num = DAY_MAP.get(day_name)
        if day_num is None:
            return {'success': False, 'error': f'Invalid day: {day_name}. Use monday through sunday.'}

        is_closed = params.get('is_closed', False)
        open_time = params.get('open_time', '09:00')
        close_time = params.get('close_time', '21:00')

        cursor.execute("SELECT id FROM business_hours WHERE day_of_week = ?", (day_num,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE business_hours SET open_time = ?, close_time = ?, is_closed = ? "
                "WHERE day_of_week = ?",
                (open_time, close_time, 1 if is_closed else 0, day_num)
            )
        else:
            cursor.execute(
                "INSERT INTO business_hours (day_of_week, open_time, close_time, is_closed) "
                "VALUES (?, ?, ?, ?)",
                (day_num, open_time, close_time, 1 if is_closed else 0)
            )
        conn.commit()
        if is_closed:
            return {'success': True, 'message': f'{day_name.capitalize()} set to closed', 'entity_id': day_num}
        return {
            'success': True,
            'message': f'{day_name.capitalize()} hours updated: {open_time} - {close_time}',
            'entity_id': day_num
        }

    return {'success': False, 'error': f'Unknown menu action: {action_type}'}


# ---------------------------------------------------------------------------
# Voice Action: Main endpoint
# ---------------------------------------------------------------------------

_ACTION_HANDLERS = {
    'manage_attendance': _handle_attendance,
    'manage_schedule': _handle_schedule,
    'manage_orders': _handle_orders,
    'manage_86': _handle_86,
    'manage_inventory': _handle_inventory,
    'manage_payroll': _handle_payroll,
    'manage_menu': _handle_menu,
}


@voice_bp.route('/action', methods=['POST'])
@login_required
@organization_required
def execute_voice_action():
    """Execute a write action via voice command. Admin-only."""
    import logging

    if not (g.get('is_super_admin') or g.get('is_organization_admin')):
        return jsonify({'success': False, 'error': 'Admin access required'}), 403

    data = request.get_json()
    action_name = data.get('action', '')
    params = data.get('params', {})

    handler = _ACTION_HANDLERS.get(action_name)
    if not handler:
        return jsonify({'success': False, 'error': f'Unknown action: {action_name}'}), 400

    conn = None
    try:
        conn = get_org_db()
        result = handler(params, conn, g.user['id'])

        # Audit trail
        logging.info(
            '[Voice Action] user=%s action=%s:%s result=%s',
            g.user['id'], action_name, params.get('action_type', ''),
            result.get('success')
        )
        try:
            conn.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
                (
                    g.user['id'],
                    f"voice:{action_name}:{params.get('action_type', '')}",
                    action_name.replace('manage_', ''),
                    str(result.get('entity_id', '')),
                    str(params)[:500]
                )
            )
            conn.commit()
        except Exception:
            pass  # Don't fail the action if audit logging fails

        return jsonify(result)

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        logging.exception('[Voice Action] Error in %s', action_name)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
