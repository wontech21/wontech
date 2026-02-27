"""
Ask-a-Question routes — natural language query engine for business data.
"""

import os
import re
import json
import hashlib
import sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, g
import requests as http_requests

from db_manager import get_org_db
from middleware import login_required
from utils.schema import get_db_schema, get_data_date_ranges

ask_bp = Blueprint('ask', __name__, url_prefix='/api/ask')

# Safety: same forbidden pattern as voice_routes.py
_FORBIDDEN_PATTERN = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX)\b',
    re.IGNORECASE
)
_MAX_ROWS = 50
_QUERY_TIMEOUT_MS = 5000

# ---------------------------------------------------------------------------
# Keyword-based fallback queries (when OpenAI is unavailable)
# ---------------------------------------------------------------------------
_FALLBACK_QUERIES = [
    {
        'keywords': ['best sell', 'top product', 'top sell', 'best item', 'popular'],
        'sql': """
            SELECT product_name, SUM(revenue) as total_revenue,
                   SUM(quantity_sold) as total_qty
            FROM sales_history WHERE DATE(sale_date) >= date('now', '-7 days')
            GROUP BY product_name ORDER BY total_revenue DESC LIMIT 10
        """,
        'title': 'Top 10 products by revenue (last 7 days)',
    },
    {
        'keywords': ['revenue', 'sales today'],
        'sql': """
            SELECT DATE(sale_date) as day, SUM(revenue) as revenue,
                   COUNT(*) as transactions
            FROM sales_history WHERE DATE(sale_date) >= date('now', '-7 days')
            GROUP BY day ORDER BY day
        """,
        'title': 'Daily revenue (last 7 days)',
    },
    {
        'keywords': ['labor cost', 'payroll', 'wage'],
        'sql': """
            SELECT pay_period_start, pay_period_end,
                   SUM(gross_pay) as total_pay, SUM(total_hours) as hours
            FROM payroll_history
            GROUP BY pay_period_start, pay_period_end
            ORDER BY pay_period_end DESC LIMIT 8
        """,
        'title': 'Recent payroll summary',
    },
    {
        'keywords': ['food cost', 'cogs', 'cost of goods'],
        'sql': """
            SELECT
                ROUND(SUM(cost_of_goods), 2) as total_cogs,
                ROUND(SUM(revenue), 2) as total_revenue,
                ROUND(SUM(cost_of_goods) * 100.0 / SUM(revenue), 1) as food_cost_pct
            FROM sales_history WHERE DATE(sale_date) >= date('now', '-7 days')
        """,
        'title': 'Food cost percentage (last 7 days)',
    },
    {
        'keywords': ['who work', 'hours', 'attendance', 'clock'],
        'sql': """
            SELECT e.first_name || ' ' || e.last_name as employee,
                   ROUND(SUM(a.total_hours), 1) as total_hours,
                   COUNT(*) as shifts
            FROM attendance a
            JOIN employees e ON e.id = a.employee_id
            WHERE DATE(a.clock_in) >= date('now', '-7 days')
            GROUP BY a.employee_id ORDER BY total_hours DESC LIMIT 15
        """,
        'title': 'Employee hours (last 7 days)',
    },
    {
        'keywords': ['inventory', 'stock', 'ingredient', 'low stock'],
        'sql': """
            SELECT ingredient_name, quantity_on_hand, unit_of_measure,
                   reorder_level, last_unit_price
            FROM ingredients
            WHERE quantity_on_hand <= reorder_level AND reorder_level > 0
            ORDER BY quantity_on_hand ASC LIMIT 15
        """,
        'title': 'Low stock ingredients',
    },
    {
        'keywords': ['invoice', 'supplier', 'bill'],
        'sql': """
            SELECT invoice_number, supplier_name, invoice_date,
                   total_amount, payment_status, reconciled
            FROM invoices ORDER BY invoice_date DESC LIMIT 10
        """,
        'title': 'Recent invoices',
    },
    {
        'keywords': ['overtime', 'ot hour'],
        'sql': """
            SELECT e.first_name || ' ' || e.last_name as employee,
                   ROUND(SUM(a.total_hours), 1) as total_hours,
                   ROUND(SUM(CASE WHEN a.total_hours > 8 THEN a.total_hours - 8 ELSE 0 END), 1) as ot_hours
            FROM attendance a
            JOIN employees e ON e.id = a.employee_id
            WHERE DATE(a.clock_in) >= date('now', '-7 days')
            GROUP BY a.employee_id
            HAVING ot_hours > 0
            ORDER BY ot_hours DESC LIMIT 15
        """,
        'title': 'Overtime hours (last 7 days)',
    },
]


def _find_fallback(question):
    """Match a question to a pre-built query by keywords."""
    q_lower = question.lower()
    for fb in _FALLBACK_QUERIES:
        if any(kw in q_lower for kw in fb['keywords']):
            return fb
    return None


def _build_sql_prompt(question, schema, date_ranges):
    """Build system prompt for SQL generation."""
    today = datetime.now().strftime('%A, %B %d, %Y')
    ranges_text = '\n'.join(f"- {k}: {v}" for k, v in date_ranges.items()) if date_ranges else 'No date range info available.'

    system_msg = f"""You are a SQL analyst for a restaurant business. Today is {today}.
You receive a natural language question and must return a JSON object with:
- "sql": a valid SQLite SELECT query to answer the question
- "explanation": a brief explanation of what the query does
- "chart_spec": optional chart specification (null if not applicable)

DATABASE SCHEMA:
{schema}

DATA AVAILABILITY:
{ranges_text}

FINANCIAL DEFINITIONS:
- sales_history has ONE ROW PER PRODUCT SOLD (not per transaction).
- Columns: revenue, cost_of_goods, gross_profit, quantity_sold.
- Revenue = SUM(revenue). COGS = SUM(cost_of_goods). Gross Profit = SUM(gross_profit).
- Labor Cost = SUM(gross_pay) from payroll_history.
- NEVER report revenue AS profit.
- NEVER join sales_history to other tables unless necessary — joins multiply rows.

SQLite RULES:
- Use date('now'), date('now','-7 days'), strftime('%Y-%m', col)
- NO: DATEADD, DATEDIFF, NOW(), GETDATE(), DATE_FORMAT, EXTRACT, INTERVAL
- Use || for concat, ROUND(x,2) for rounding
- Dates are TEXT 'YYYY-MM-DD'. Use >= and < for ranges.
- Product names have variants — use LIKE '%keyword%', never exact match.
- ALWAYS include LIMIT (max 50).
- ONLY SELECT statements. No INSERT, UPDATE, DELETE, DROP, etc.

CHART SPEC FORMAT (when a chart would help visualize the answer):
{{"type": "bar|horizontal_bar|line|doughnut", "title": "...", "label_column": "column_name", "data_column": "column_name"}}
Use horizontal_bar for rankings, line for trends over time, doughnut for breakdowns, bar for comparisons.

Respond with ONLY valid JSON:
{{"sql": "SELECT ...", "explanation": "...", "chart_spec": null}}"""

    return system_msg


def _build_summary_prompt(question, columns, rows):
    """Build prompt for natural language summary of query results."""
    return f"""You are a business analyst. A restaurant owner asked: "{question}"

Here are the query results:
Columns: {json.dumps(columns)}
Data: {json.dumps(rows[:20])}

Provide a concise, natural language answer (2-4 sentences) with specific numbers and product names. Be direct and actionable. Do not mention SQL or databases."""


def _execute_safe_query(cursor, sql):
    """Execute a read-only SQL query with safety checks. Returns (columns, rows) or raises."""
    if _FORBIDDEN_PATTERN.search(sql):
        raise ValueError('Only SELECT queries are allowed')
    if not sql.strip().upper().startswith('SELECT'):
        raise ValueError('Query must start with SELECT')
    if 'LIMIT' not in sql.upper():
        sql += f' LIMIT {_MAX_ROWS}'

    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = [list(r) for r in cursor.fetchmany(_MAX_ROWS)]
    return columns, rows


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@ask_bp.route('/question', methods=['POST'])
@login_required
def ask_question():
    """Answer a natural language question about business data."""
    data = request.get_json()
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({'success': False, 'error': 'No question provided'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Check cache
        cache_key = hashlib.sha256(question.lower().encode()).hexdigest()[:32]
        cursor.execute("""
            SELECT data, generated_at FROM widget_data_cache
            WHERE widget_key = 'ask_question' AND cache_key = ?
            ORDER BY generated_at DESC LIMIT 1
        """, (cache_key,))
        cached = cursor.fetchone()
        if cached:
            gen_at = cached['generated_at'] if hasattr(cached, 'keys') else cached[1]
            try:
                age = datetime.now() - datetime.fromisoformat(gen_at)
                if age < timedelta(hours=1):
                    data_str = cached['data'] if hasattr(cached, 'keys') else cached[0]
                    return jsonify(json.loads(data_str))
            except (ValueError, TypeError):
                pass

        # Try OpenAI first
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            result = _ask_with_ai(question, cursor, api_key)
        else:
            result = _ask_with_fallback(question, cursor)

        if result and result.get('success'):
            # Cache the result
            now = datetime.now().isoformat()
            expires = (datetime.now() + timedelta(hours=1)).isoformat()
            cursor.execute(
                "DELETE FROM widget_data_cache WHERE widget_key = 'ask_question' AND cache_key = ?",
                (cache_key,)
            )
            cursor.execute("""
                INSERT INTO widget_data_cache (widget_key, cache_key, data, generated_at, expires_at)
                VALUES ('ask_question', ?, ?, ?, ?)
            """, (cache_key, json.dumps(result), now, expires))
            conn.commit()

        return jsonify(result)

    except Exception as e:
        print(f"[Ask] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        conn.close()


def _ask_with_ai(question, cursor, api_key):
    """Use GPT-4o-mini to generate SQL, execute, and summarize."""
    schema = get_db_schema()
    date_ranges = get_data_date_ranges()

    # Step 1: Generate SQL
    system_msg = _build_sql_prompt(question, schema, date_ranges)
    try:
        resp = http_requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'gpt-4o-mini',
                'temperature': 0.1,
                'max_tokens': 800,
                'response_format': {'type': 'json_object'},
                'messages': [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': question},
                ],
            },
            timeout=15,
        )

        if resp.status_code != 200:
            print(f"[Ask] OpenAI SQL error: {resp.status_code}")
            return _ask_with_fallback(question, cursor)

        sql_result = json.loads(resp.json()['choices'][0]['message']['content'])
        sql = sql_result.get('sql', '')
        chart_spec = sql_result.get('chart_spec')

    except Exception as e:
        print(f"[Ask] OpenAI SQL gen failed: {e}")
        return _ask_with_fallback(question, cursor)

    # Step 2: Execute SQL
    try:
        columns, rows = _execute_safe_query(cursor, sql)
    except Exception as e:
        print(f"[Ask] SQL execution failed: {e} | SQL: {sql}")
        return _ask_with_fallback(question, cursor)

    # Step 3: Summarize results
    try:
        summary_prompt = _build_summary_prompt(question, columns, rows)
        resp2 = http_requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_tokens': 400,
                'messages': [
                    {'role': 'user', 'content': summary_prompt},
                ],
            },
            timeout=15,
        )
        if resp2.status_code == 200:
            answer = resp2.json()['choices'][0]['message']['content']
        else:
            answer = _format_basic_answer(columns, rows)
    except Exception:
        answer = _format_basic_answer(columns, rows)

    # Build chart if spec provided
    chart = None
    if chart_spec and rows:
        chart = _build_chart(chart_spec, columns, rows)

    return {
        'success': True,
        'answer': answer,
        'data': {'columns': columns, 'rows': rows},
        'chart': chart,
        'source': 'ai',
    }


def _ask_with_fallback(question, cursor):
    """Use keyword matching to answer without AI."""
    fb = _find_fallback(question)
    if not fb:
        return {
            'success': True,
            'answer': "I couldn't find a matching query for your question. Try asking about sales, revenue, top products, labor costs, food cost, inventory, or invoices.",
            'data': {'columns': [], 'rows': []},
            'chart': None,
            'source': 'fallback',
        }

    try:
        columns, rows = _execute_safe_query(cursor, fb['sql'])
        answer = _format_basic_answer(columns, rows, fb['title'])

        # Auto-detect chart type
        chart = None
        if rows and len(columns) >= 2:
            if any(kw in fb['title'].lower() for kw in ['top', 'ranking']):
                chart = _build_chart(
                    {'type': 'horizontal_bar', 'title': fb['title'],
                     'label_column': columns[0], 'data_column': columns[1]},
                    columns, rows
                )
            elif 'daily' in fb['title'].lower() or 'day' in fb['title'].lower():
                chart = _build_chart(
                    {'type': 'line', 'title': fb['title'],
                     'label_column': columns[0], 'data_column': columns[1]},
                    columns, rows
                )

        return {
            'success': True,
            'answer': answer,
            'data': {'columns': columns, 'rows': rows},
            'chart': chart,
            'source': 'fallback',
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Query failed: {str(e)}',
            'data': {'columns': [], 'rows': []},
            'chart': None,
            'source': 'fallback',
        }


def _format_basic_answer(columns, rows, title=None):
    """Format query results as a simple text answer."""
    if not rows:
        return 'No data found for this query.'

    prefix = f'{title}: ' if title else ''

    if len(rows) == 1 and len(columns) <= 4:
        # Single row — list key-value pairs
        parts = []
        for col, val in zip(columns, rows[0]):
            if isinstance(val, float):
                if 'pct' in col.lower() or 'percent' in col.lower():
                    parts.append(f'{col.replace("_", " ").title()}: {val:.1f}%')
                else:
                    parts.append(f'{col.replace("_", " ").title()}: ${val:,.2f}')
            else:
                parts.append(f'{col.replace("_", " ").title()}: {val}')
        return prefix + ' | '.join(parts)

    # Multiple rows — describe top entries
    lines = [prefix + f'Found {len(rows)} results:']
    for i, row in enumerate(rows[:5]):
        vals = []
        for col, val in zip(columns, row):
            if isinstance(val, float):
                if 'hour' in col.lower():
                    vals.append(f'{val:.1f}h')
                elif 'pct' in col.lower():
                    vals.append(f'{val:.1f}%')
                else:
                    vals.append(f'${val:,.2f}')
            else:
                vals.append(str(val))
        lines.append(f'{i+1}. ' + ' — '.join(vals))

    if len(rows) > 5:
        lines.append(f'...and {len(rows) - 5} more.')
    return '\n'.join(lines)


def _build_chart(spec, columns, rows):
    """Build a Chart.js-compatible chart object from query results."""
    if not spec or not rows:
        return None

    label_col = spec.get('label_column', columns[0])
    data_col = spec.get('data_column', columns[1] if len(columns) > 1 else columns[0])

    try:
        label_idx = columns.index(label_col)
        data_idx = columns.index(data_col)
    except ValueError:
        label_idx, data_idx = 0, min(1, len(columns) - 1)

    labels = [str(r[label_idx]) for r in rows]
    data_vals = [float(r[data_idx]) if r[data_idx] is not None else 0 for r in rows]

    colors = [
        'rgba(102, 126, 234, 0.8)', 'rgba(16, 185, 129, 0.8)',
        'rgba(245, 158, 11, 0.8)', 'rgba(239, 68, 68, 0.8)',
        'rgba(139, 92, 246, 0.8)', 'rgba(59, 130, 246, 0.8)',
        'rgba(236, 72, 153, 0.8)', 'rgba(20, 184, 166, 0.8)',
        'rgba(251, 146, 60, 0.8)', 'rgba(168, 85, 247, 0.8)',
    ]

    return {
        'type': spec.get('type', 'bar'),
        'title': spec.get('title', ''),
        'labels': labels,
        'datasets': [{
            'label': data_col.replace('_', ' ').title(),
            'data': data_vals,
            'backgroundColor': colors[:len(data_vals)],
            'borderColor': [c.replace('0.8', '1') for c in colors[:len(data_vals)]],
            'borderWidth': 1,
        }],
    }


@ask_bp.route('/suggestions')
@login_required
def suggestions():
    """Return suggested questions based on available data."""
    return jsonify({
        'success': True,
        'suggestions': [
            'How are sales today?',
            "What's my food cost?",
            'Top products this week?',
            'Overtime hours?',
            'Revenue by day this month?',
            'Low stock items?',
        ]
    })
