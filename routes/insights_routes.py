"""
AI Insights routes — proactive business intelligence powered by GPT-4o-mini.
Aggregates cross-domain data (sales, inventory, labor, costs) and generates
actionable insights with rule-based fallback when OpenAI is unavailable.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, g
import requests as http_requests

from db_manager import get_org_db
from middleware import login_required, organization_admin_required

insights_bp = Blueprint('insights', __name__, url_prefix='/api/insights')


# ---------------------------------------------------------------------------
# Cache helpers — uses existing widget_data_cache table
# ---------------------------------------------------------------------------
def _get_cached_insights(cursor):
    """Return cached insights if generated today, else None."""
    cursor.execute("""
        SELECT data, generated_at FROM widget_data_cache
        WHERE widget_key = 'ai_insights' AND cache_key = 'daily_briefing'
        ORDER BY generated_at DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if not row:
        return None

    generated_at = row['generated_at'] if isinstance(row, sqlite3.Row) else row[0 + 1]
    data = row['data'] if isinstance(row, sqlite3.Row) else row[0]

    try:
        gen_time = datetime.fromisoformat(generated_at)
    except (ValueError, TypeError):
        return None

    # Cache expires at midnight — "Today's Intelligence" means today's data
    if gen_time.date() < datetime.now().date():
        return None

    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


def _cache_insights(cursor, data):
    """Store insights in widget_data_cache, replacing any previous entry."""
    now = datetime.now().isoformat()
    cursor.execute(
        "DELETE FROM widget_data_cache WHERE widget_key = 'ai_insights' AND cache_key = 'daily_briefing'"
    )
    cursor.execute("""
        INSERT INTO widget_data_cache (widget_key, cache_key, data, generated_at)
        VALUES ('ai_insights', 'daily_briefing', ?, ?)
    """, (json.dumps(data), now))


# ---------------------------------------------------------------------------
# Data aggregation — one connection, ~10 targeted queries
# ---------------------------------------------------------------------------
def _aggregate_business_snapshot(cursor):
    """Build a comprehensive data snapshot for AI analysis."""
    snap = {}
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    # 1. Sales pulse
    try:
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN DATE(sale_date) = ? THEN revenue ELSE 0 END), 0) as today_revenue,
                COALESCE(SUM(CASE WHEN DATE(sale_date) = ? THEN 1 ELSE 0 END), 0) as today_transactions,
                COALESCE(SUM(CASE WHEN DATE(sale_date) >= ? THEN revenue ELSE 0 END), 0) as this_week_revenue,
                COALESCE(SUM(CASE WHEN DATE(sale_date) >= ? THEN 1 ELSE 0 END), 0) as this_week_transactions,
                COALESCE(SUM(CASE WHEN DATE(sale_date) >= ? AND DATE(sale_date) < ? THEN revenue ELSE 0 END), 0) as last_week_revenue,
                COALESCE(SUM(CASE WHEN DATE(sale_date) >= ? AND DATE(sale_date) < ? THEN 1 ELSE 0 END), 0) as last_week_transactions,
                COALESCE(SUM(CASE WHEN DATE(sale_date) >= ? THEN revenue ELSE 0 END), 0) as month_revenue
            FROM sales_history
        """, (today, today, week_ago, week_ago, two_weeks_ago, week_ago, two_weeks_ago, week_ago, month_start))
        row = cursor.fetchone()
        snap['sales'] = {
            'today_revenue': round(row[0], 2),
            'today_transactions': row[1],
            'this_week_revenue': round(row[2], 2),
            'this_week_transactions': row[3],
            'last_week_revenue': round(row[4], 2),
            'last_week_transactions': row[5],
            'month_revenue': round(row[6], 2),
            'avg_ticket_this_week': round(row[2] / row[3], 2) if row[3] > 0 else 0,
        }
    except Exception:
        snap['sales'] = {}

    # 2. Top & bottom products (this week)
    try:
        cursor.execute("""
            SELECT product_name, SUM(revenue) as rev, SUM(quantity_sold) as qty
            FROM sales_history WHERE DATE(sale_date) >= ?
            GROUP BY product_name ORDER BY rev DESC LIMIT 5
        """, (week_ago,))
        snap['top_products'] = [
            {'name': r[0], 'revenue': round(r[1], 2), 'qty': r[2]}
            for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT product_name, SUM(revenue) as rev, SUM(quantity_sold) as qty
            FROM sales_history WHERE DATE(sale_date) >= ?
            GROUP BY product_name ORDER BY rev ASC LIMIT 3
        """, (week_ago,))
        snap['bottom_products'] = [
            {'name': r[0], 'revenue': round(r[1], 2), 'qty': r[2]}
            for r in cursor.fetchall()
        ]
    except Exception:
        snap['top_products'] = []
        snap['bottom_products'] = []

    # 3. Inventory health
    try:
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN quantity_on_hand <= reorder_level AND reorder_level > 0 THEN 1 END) as below_reorder,
                COUNT(CASE WHEN quantity_on_hand = 0 THEN 1 END) as zero_stock,
                COALESCE(SUM(quantity_on_hand * COALESCE(last_unit_price, 0)), 0) as total_value,
                COUNT(*) as total_items
            FROM ingredients
        """)
        row = cursor.fetchone()
        snap['inventory'] = {
            'below_reorder': row[0],
            'zero_stock': row[1],
            'total_value': round(row[2], 2),
            'total_items': row[3],
        }
    except Exception:
        snap['inventory'] = {}

    # 4. Cost changes — ingredients with >15% price increase
    try:
        cursor.execute("""
            SELECT i.ingredient_name, i.last_unit_price, i.average_unit_price,
                   CASE WHEN i.average_unit_price > 0
                        THEN ROUND((i.last_unit_price - i.average_unit_price) / i.average_unit_price * 100, 1)
                        ELSE 0 END as pct_change
            FROM ingredients i
            WHERE i.last_unit_price IS NOT NULL AND i.average_unit_price IS NOT NULL
              AND i.average_unit_price > 0
              AND (i.last_unit_price - i.average_unit_price) / i.average_unit_price > 0.15
            ORDER BY pct_change DESC LIMIT 5
        """)
        snap['cost_increases'] = [
            {'name': r[0], 'last_price': round(r[1], 2), 'avg_price': round(r[2], 2), 'pct_change': r[3]}
            for r in cursor.fetchall()
        ]
    except Exception:
        snap['cost_increases'] = []

    # 5. Unreconciled invoices
    try:
        cursor.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as total
            FROM invoices WHERE reconciled = 0
        """)
        row = cursor.fetchone()
        snap['unreconciled'] = {'count': row[0], 'total': round(row[1], 2)}
    except Exception:
        snap['unreconciled'] = {'count': 0, 'total': 0}

    # 6. Labor snapshot
    try:
        cursor.execute("""
            SELECT
                COALESCE(SUM(total_hours), 0) as hours_this_week,
                COALESCE(SUM(CASE WHEN total_hours > 8 THEN total_hours - 8 ELSE 0 END), 0) as overtime_hours,
                COUNT(CASE WHEN clock_out IS NULL THEN 1 END) as currently_clocked_in
            FROM attendance
            WHERE DATE(clock_in) >= ?
        """, (week_ago,))
        row = cursor.fetchone()
        snap['labor'] = {
            'hours_this_week': round(row[0], 1),
            'overtime_hours': round(row[1], 1),
            'currently_clocked_in': row[2],
        }
    except Exception:
        snap['labor'] = {}

    # 7. Menu margins — products with negative/near-zero margin
    try:
        cursor.execute("""
            SELECT p.product_name, p.price,
                   COALESCE(SUM(ri.quantity * COALESCE(i.last_unit_price, i.average_unit_price, 0)), 0) as recipe_cost
            FROM products p
            LEFT JOIN recipe_ingredients ri ON ri.product_id = p.id
            LEFT JOIN ingredients i ON i.id = ri.ingredient_id
            WHERE p.price > 0
            GROUP BY p.id
            HAVING recipe_cost > 0 AND recipe_cost >= p.price * 0.8
            ORDER BY (recipe_cost / p.price) DESC
            LIMIT 5
        """)
        snap['tight_margins'] = [
            {'name': r[0], 'price': round(r[1], 2), 'cost': round(r[2], 2),
             'margin_pct': round((1 - r[2] / r[1]) * 100, 1) if r[1] > 0 else 0}
            for r in cursor.fetchall()
        ]
    except Exception:
        snap['tight_margins'] = []

    # 8. Stale products — zero sales in past 7 days (but have had sales before)
    try:
        cursor.execute("""
            SELECT p.product_name
            FROM products p
            WHERE p.id NOT IN (
                SELECT DISTINCT s.product_id FROM sales_history s
                WHERE DATE(s.sale_date) >= ?
                AND s.product_id IS NOT NULL
            )
            AND p.id IN (
                SELECT DISTINCT s.product_id FROM sales_history s
                WHERE s.product_id IS NOT NULL
            )
            LIMIT 10
        """, (week_ago,))
        snap['stale_products'] = [r[0] for r in cursor.fetchall()]
    except Exception:
        snap['stale_products'] = []

    # 9. Hourly sales patterns (today)
    try:
        cursor.execute("""
            SELECT
                CAST(SUBSTR(COALESCE(sale_time, '12:00'), 1, 2) AS INTEGER) as hour,
                COUNT(*) as transactions,
                COALESCE(SUM(revenue), 0) as rev
            FROM sales_history
            WHERE DATE(sale_date) = ?
            GROUP BY hour ORDER BY hour
        """, (today,))
        snap['hourly_sales'] = [
            {'hour': r[0], 'transactions': r[1], 'revenue': round(r[2], 2)}
            for r in cursor.fetchall()
        ]
    except Exception:
        snap['hourly_sales'] = []

    # 10. Labor cost vs revenue (most recent payroll period)
    try:
        cursor.execute("""
            SELECT SUM(gross_pay) as total
            FROM payroll_history
            GROUP BY pay_period_start, pay_period_end
            ORDER BY pay_period_end DESC LIMIT 1
        """)
        labor_row = cursor.fetchone()
        labor_cost = labor_row[0] if labor_row else 0
        week_rev = snap.get('sales', {}).get('this_week_revenue', 0)
        snap['labor_vs_revenue'] = {
            'labor_cost': round(labor_cost, 2),
            'revenue': round(week_rev, 2),
            'labor_pct': round(labor_cost / week_rev * 100, 1) if week_rev > 0 else 0,
        }
    except Exception:
        snap['labor_vs_revenue'] = {}

    # 11. Order type breakdown (this week)
    try:
        cursor.execute("""
            SELECT
                COALESCE(order_type, 'dine_in') as otype,
                COUNT(*) as cnt,
                COALESCE(SUM(revenue), 0) as rev
            FROM sales_history
            WHERE DATE(sale_date) >= ?
            GROUP BY otype ORDER BY rev DESC
        """, (week_ago,))
        snap['order_types'] = [
            {'type': r[0], 'count': r[1], 'revenue': round(r[2], 2)}
            for r in cursor.fetchall()
        ]
    except Exception:
        snap['order_types'] = []

    # 12. Food cost % (this week)
    try:
        cursor.execute("""
            SELECT
                COALESCE(SUM(cost_of_goods), 0) as cogs,
                COALESCE(SUM(revenue), 0) as rev,
                COALESCE(SUM(gross_profit), 0) as gp
            FROM sales_history
            WHERE DATE(sale_date) >= ?
        """, (week_ago,))
        row = cursor.fetchone()
        cogs, rev, gp = row[0], row[1], row[2]
        snap['food_cost'] = {
            'cogs': round(cogs, 2),
            'revenue': round(rev, 2),
            'gross_profit': round(gp, 2),
            'food_cost_pct': round(cogs / rev * 100, 1) if rev > 0 else 0,
            'gross_margin_pct': round(gp / rev * 100, 1) if rev > 0 else 0,
        }
    except Exception:
        snap['food_cost'] = {}

    return snap


# ---------------------------------------------------------------------------
# OpenAI integration
# ---------------------------------------------------------------------------
def _build_insights_prompt(snapshot, org_name):
    """Build system + user messages for GPT-4o-mini."""
    # Rotate focus areas by day of week so insights vary daily even with similar data
    day_focuses = {
        0: "labor efficiency and scheduling optimization",
        1: "ingredient costs and supplier pricing trends",
        2: "menu performance — which items earn their spot, which don't",
        3: "inventory management and waste reduction",
        4: "weekend prep — what to stock up on based on recent weekend trends",
        5: "peak performance — real-time sales momentum and staffing",
        6: "weekly wrap-up — compare this week vs last, highlight wins and misses",
    }
    today_focus = day_focuses.get(datetime.now().weekday(), "overall business health")

    system_msg = f"""You are a sharp business analyst for a restaurant/food service operation.
You receive a data snapshot and must produce exactly 5 insights as a JSON object.

TODAY'S FOCUS: {today_focus}
At least 2 of your 5 insights should relate to today's focus area. The rest should cover whatever is most urgent or notable in the data.

Data includes cross-domain metrics:
- Sales: daily/weekly/monthly revenue, transactions, product rankings
- Costs: food cost %, gross margin %, ingredient price changes
- Labor: labor cost as % of revenue, hours, overtime
- Operations: order type mix (dine-in/delivery/pickup), hourly patterns, inventory health

Rules:
- Use plain business language, no jargon
- Name specific products, ingredients, and dollar amounts — never be vague
- Focus on money: revenue, costs, profit, waste
- Compare to prior periods when data allows (e.g., "up 12% vs last week")
- Look for cross-domain connections (e.g., labor cost vs revenue, food cost vs margins)
- Restaurant industry benchmarks: labor cost 25-35% of revenue is NORMAL, food cost 28-35% is NORMAL. Only flag as warning if ABOVE these ranges.
- Include at least one positive insight (what's going well)
- Each insight must have a concrete, specific action recommendation
- Be specific to TODAY — what should they do right now, this shift, today
- Severity levels: "critical" (needs immediate action), "warning" (should address soon), "positive" (good news), "info" (FYI)
- Domain tags: "sales", "inventory", "labor", "costs", "operations"

Respond with ONLY valid JSON in this exact format:
{{
  "insights": [
    {{
      "title": "Short headline (under 60 chars)",
      "detail": "2-3 sentence explanation with specific numbers",
      "action": "One specific action to take today",
      "severity": "warning",
      "domain": "costs"
    }}
  ]
}}"""

    now = datetime.now()
    user_msg = (
        f"Business: {org_name}\n"
        f"Date: {now.strftime('%A, %B %d, %Y')} (day of week focus: {today_focus})\n"
        f"Time: {now.strftime('%I:%M %p')}\n\n"
        f"Data snapshot:\n{json.dumps(snapshot, indent=2)}"
    )

    return system_msg, user_msg


def _call_openai(system_msg, user_msg):
    """Call OpenAI Chat Completions API. Returns parsed insights list or None."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    try:
        resp = http_requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_tokens': 1500,
                'response_format': {'type': 'json_object'},
                'messages': [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': user_msg},
                ],
            },
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"[Insights] OpenAI API error: {resp.status_code} — {resp.text[:200]}")
            return None

        data = resp.json()
        content = data['choices'][0]['message']['content']
        parsed = json.loads(content)
        return parsed.get('insights', [])

    except Exception as e:
        print(f"[Insights] OpenAI call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Rule-based fallback — when OpenAI is unavailable
# ---------------------------------------------------------------------------
def _generate_fallback_insights(snapshot):
    """Generate basic rule-based insights from raw snapshot data."""
    insights = []

    # Sales comparison
    sales = snapshot.get('sales', {})
    if sales.get('this_week_revenue') and sales.get('last_week_revenue'):
        this_wk = sales['this_week_revenue']
        last_wk = sales['last_week_revenue']
        if last_wk > 0:
            pct = round((this_wk - last_wk) / last_wk * 100, 1)
            if pct > 0:
                insights.append({
                    'title': f'Revenue up {pct}% vs last week',
                    'detail': f'This week: ${this_wk:,.2f} vs last week: ${last_wk:,.2f}. '
                              f'{sales.get("this_week_transactions", 0)} transactions so far.',
                    'action': 'Keep the momentum — review what drove the increase.',
                    'severity': 'positive',
                    'domain': 'sales',
                })
            else:
                insights.append({
                    'title': f'Revenue down {abs(pct)}% vs last week',
                    'detail': f'This week: ${this_wk:,.2f} vs last week: ${last_wk:,.2f}.',
                    'action': 'Check if there were fewer transactions or lower average ticket.',
                    'severity': 'warning',
                    'domain': 'sales',
                })

    # Inventory alerts
    inv = snapshot.get('inventory', {})
    below = inv.get('below_reorder', 0)
    zero = inv.get('zero_stock', 0)
    if below > 0 or zero > 0:
        parts = []
        if below > 0:
            parts.append(f'{below} item{"s" if below != 1 else ""} below reorder level')
        if zero > 0:
            parts.append(f'{zero} item{"s" if zero != 1 else ""} at zero stock')
        insights.append({
            'title': f'{below + zero} inventory items need attention',
            'detail': ' and '.join(parts) + '.',
            'action': 'Review inventory levels and place orders for critical items.',
            'severity': 'critical' if zero > 0 else 'warning',
            'domain': 'inventory',
        })

    # Cost increases
    cost_increases = snapshot.get('cost_increases', [])
    if cost_increases:
        top = cost_increases[0]
        insights.append({
            'title': f'{top["name"]} price up {top["pct_change"]}%',
            'detail': f'Last price: ${top["last_price"]:.2f} vs average: ${top["avg_price"]:.2f}. '
                      f'{len(cost_increases)} ingredient{"s" if len(cost_increases) != 1 else ""} with >15% price increase.',
            'action': 'Compare pricing with alternative suppliers.',
            'severity': 'warning',
            'domain': 'costs',
        })

    # Unreconciled invoices
    unrec = snapshot.get('unreconciled', {})
    if unrec.get('count', 0) > 0:
        insights.append({
            'title': f'{unrec["count"]} unreconciled invoices (${unrec["total"]:,.2f})',
            'detail': f'You have {unrec["count"]} invoice{"s" if unrec["count"] != 1 else ""} '
                      f'totaling ${unrec["total"]:,.2f} that haven\'t been reconciled.',
            'action': 'Reconcile invoices to keep your cost tracking accurate.',
            'severity': 'warning' if unrec['count'] > 5 else 'info',
            'domain': 'costs',
        })

    # Top product
    top_products = snapshot.get('top_products', [])
    if top_products:
        top = top_products[0]
        insights.append({
            'title': f'{top["name"]} leading sales this week',
            'detail': f'${top["revenue"]:,.2f} in revenue from {top["qty"]} units sold.',
            'action': 'Ensure you have sufficient stock for this top seller.',
            'severity': 'positive',
            'domain': 'sales',
        })

    # Tight margins
    tight = snapshot.get('tight_margins', [])
    if tight:
        item = tight[0]
        insights.append({
            'title': f'{item["name"]} has only {item["margin_pct"]}% margin',
            'detail': f'Sells for ${item["price"]:.2f} but costs ${item["cost"]:.2f} to make.',
            'action': 'Consider a price increase or recipe adjustment.',
            'severity': 'critical' if item['margin_pct'] < 5 else 'warning',
            'domain': 'costs',
        })

    # Labor cost %
    labor = snapshot.get('labor_vs_revenue', {})
    labor_pct = labor.get('labor_pct', 0)
    if labor_pct > 0:
        if labor_pct > 35:
            insights.append({
                'title': f'Labor cost at {labor_pct}% of revenue',
                'detail': f'${labor.get("labor_cost", 0):,.2f} in labor against ${labor.get("revenue", 0):,.2f} revenue this week. '
                          f'Industry target is 25-35%.',
                'action': 'Review scheduling — reduce overlapping shifts or cut slow-period hours.',
                'severity': 'critical' if labor_pct > 40 else 'warning',
                'domain': 'labor',
            })
        elif labor_pct < 20:
            insights.append({
                'title': f'Labor cost very lean at {labor_pct}%',
                'detail': f'${labor.get("labor_cost", 0):,.2f} labor vs ${labor.get("revenue", 0):,.2f} revenue. '
                          f'May be understaffed during peak hours.',
                'action': 'Check if service quality or speed is being impacted.',
                'severity': 'info',
                'domain': 'labor',
            })

    # Food cost %
    fc = snapshot.get('food_cost', {})
    food_pct = fc.get('food_cost_pct', 0)
    if food_pct > 0:
        if food_pct > 35:
            insights.append({
                'title': f'Food cost at {food_pct}% — above target',
                'detail': f'COGS: ${fc.get("cogs", 0):,.2f} on ${fc.get("revenue", 0):,.2f} revenue. '
                          f'Industry target is 28-35%. Gross margin: {fc.get("gross_margin_pct", 0)}%.',
                'action': 'Review portion sizes and supplier pricing. Consider menu price adjustments.',
                'severity': 'warning',
                'domain': 'costs',
            })
        elif food_pct < 25:
            insights.append({
                'title': f'Food cost healthy at {food_pct}%',
                'detail': f'Gross margin at {fc.get("gross_margin_pct", 0)}%. '
                          f'${fc.get("gross_profit", 0):,.2f} gross profit this week.',
                'action': 'Strong margins — maintain current recipes and pricing.',
                'severity': 'positive',
                'domain': 'costs',
            })

    # Order type mix
    order_types = snapshot.get('order_types', [])
    if len(order_types) > 1:
        total_rev = sum(ot['revenue'] for ot in order_types)
        if total_rev > 0:
            parts = ', '.join(
                f'{ot["type"].replace("_", " ").title()}: ${ot["revenue"]:,.0f} ({round(ot["revenue"]/total_rev*100)}%)'
                for ot in order_types[:3]
            )
            insights.append({
                'title': 'Order mix: ' + ' / '.join(
                    f'{round(ot["revenue"]/total_rev*100)}% {ot["type"].replace("_"," ")}'
                    for ot in order_types[:2]
                ),
                'detail': parts + '.',
                'action': 'Focus marketing on your strongest channel, or push the underperforming one.',
                'severity': 'info',
                'domain': 'sales',
            })

    return insights[:5] if insights else [{
        'title': 'Welcome to Today\'s Intelligence',
        'detail': 'Your AI-powered business insights will appear here as data accumulates.',
        'action': 'Keep recording sales and invoices for richer analysis.',
        'severity': 'info',
        'domain': 'operations',
    }]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@insights_bp.route('/today')
@login_required
def today():
    """Return today's AI-generated insights (cached or fresh)."""
    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Check cache first
        cached = _get_cached_insights(cursor)
        if cached:
            return jsonify(cached)

        # Generate fresh insights
        snapshot = _aggregate_business_snapshot(cursor)
        org_name = g.organization.get('organization_name', 'your business') if g.organization else 'your business'

        # Try OpenAI first, fall back to rules
        system_msg, user_msg = _build_insights_prompt(snapshot, org_name)
        ai_insights = _call_openai(system_msg, user_msg)

        if ai_insights:
            source = 'ai'
            insights_list = ai_insights[:5]
        else:
            source = 'rules'
            insights_list = _generate_fallback_insights(snapshot)

        now = datetime.now().isoformat()
        result = {
            'success': True,
            'generated_at': now,
            'source': source,
            'insights': insights_list,
        }

        _cache_insights(cursor, result)
        conn.commit()

        return jsonify(result)

    except Exception as e:
        print(f"[Insights] Error generating insights: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate insights',
            'insights': [],
        }), 500

    finally:
        conn.close()


@insights_bp.route('/refresh', methods=['POST'])
@login_required
@organization_admin_required
def refresh():
    """Force regeneration of insights (admin only)."""
    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Clear cache
        cursor.execute(
            "DELETE FROM widget_data_cache WHERE widget_key = 'ai_insights' AND cache_key = 'daily_briefing'"
        )
        conn.commit()

        # Generate fresh
        snapshot = _aggregate_business_snapshot(cursor)
        org_name = g.organization.get('organization_name', 'your business') if g.organization else 'your business'

        system_msg, user_msg = _build_insights_prompt(snapshot, org_name)
        ai_insights = _call_openai(system_msg, user_msg)

        if ai_insights:
            source = 'ai'
            insights_list = ai_insights[:5]
        else:
            source = 'rules'
            insights_list = _generate_fallback_insights(snapshot)

        now = datetime.now().isoformat()
        result = {
            'success': True,
            'generated_at': now,
            'source': source,
            'insights': insights_list,
        }

        _cache_insights(cursor, result)
        conn.commit()

        return jsonify(result)

    except Exception as e:
        print(f"[Insights] Error refreshing insights: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh insights',
        }), 500

    finally:
        conn.close()
