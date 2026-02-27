"""
Business KPI routes — computed metrics for the dashboard KPI strip.
"""

import json
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, g

from db_manager import get_org_db
from middleware import login_required

kpi_bp = Blueprint('kpi', __name__, url_prefix='/api/kpi')

# Industry benchmarks for restaurants
_TARGETS = {
    'food_cost_pct': 30.0,
    'gross_margin_pct': 70.0,
    'labor_cost_pct': 30.0,
    'prime_cost_pct': 60.0,
    'avg_ticket': None,  # no universal target
    'revenue_per_labor_hour': 40.0,
    'inventory_turnover': 4.0,  # per month
    'invoice_payment_days': 30.0,
}


def _status(value, target, lower_is_better=True):
    """Return good/warning/critical based on how far value is from target."""
    if target is None or value is None:
        return 'info'
    diff_pct = (value - target) / target * 100 if target != 0 else 0
    if lower_is_better:
        if diff_pct <= 0:
            return 'good'
        elif diff_pct <= 15:
            return 'warning'
        return 'critical'
    else:
        if diff_pct >= 0:
            return 'good'
        elif diff_pct >= -15:
            return 'warning'
        return 'critical'


@kpi_bp.route('/dashboard')
@login_required
def dashboard():
    """Return 8 business KPIs with trend and status."""
    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Check cache
        cursor.execute("""
            SELECT data, generated_at FROM widget_data_cache
            WHERE widget_key = 'business_kpis' AND cache_key = 'dashboard'
            ORDER BY generated_at DESC LIMIT 1
        """)
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

        now = datetime.now()
        week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        two_weeks_ago = (now - timedelta(days=14)).strftime('%Y-%m-%d')
        month_start = now.replace(day=1).strftime('%Y-%m-%d')

        kpis = {}

        # --- This week sales aggregates ---
        cursor.execute("""
            SELECT
                COALESCE(SUM(cost_of_goods), 0),
                COALESCE(SUM(revenue), 0),
                COALESCE(SUM(gross_profit), 0),
                COUNT(*)
            FROM sales_history WHERE DATE(sale_date) >= ?
        """, (week_ago,))
        row = cursor.fetchone()
        wk_cogs, wk_rev, wk_gp, wk_txn = row[0], row[1], row[2], row[3]

        # --- Last week sales aggregates ---
        cursor.execute("""
            SELECT
                COALESCE(SUM(cost_of_goods), 0),
                COALESCE(SUM(revenue), 0),
                COALESCE(SUM(gross_profit), 0),
                COUNT(*)
            FROM sales_history WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ?
        """, (two_weeks_ago, week_ago))
        row = cursor.fetchone()
        lw_cogs, lw_rev, lw_gp, lw_txn = row[0], row[1], row[2], row[3]

        # 1. Food Cost %
        fc_pct = round(wk_cogs / wk_rev * 100, 1) if wk_rev > 0 else 0
        lw_fc_pct = round(lw_cogs / lw_rev * 100, 1) if lw_rev > 0 else 0
        kpis['food_cost_pct'] = {
            'label': 'Food Cost',
            'value': fc_pct,
            'unit': '%',
            'trend': round(fc_pct - lw_fc_pct, 1),
            'target': _TARGETS['food_cost_pct'],
            'status': _status(fc_pct, _TARGETS['food_cost_pct'], lower_is_better=True),
        }

        # 2. Gross Profit Margin
        gm_pct = round(wk_gp / wk_rev * 100, 1) if wk_rev > 0 else 0
        lw_gm_pct = round(lw_gp / lw_rev * 100, 1) if lw_rev > 0 else 0
        kpis['gross_margin_pct'] = {
            'label': 'Gross Margin',
            'value': gm_pct,
            'unit': '%',
            'trend': round(gm_pct - lw_gm_pct, 1),
            'target': _TARGETS['gross_margin_pct'],
            'status': _status(gm_pct, _TARGETS['gross_margin_pct'], lower_is_better=False),
        }

        # --- Labor data: compare two most recent payroll periods ---
        # Rolling date windows don't align with fixed pay period boundaries,
        # so we compare the two most recent completed payroll periods directly.
        cursor.execute("""
            SELECT pay_period_start, pay_period_end, SUM(gross_pay) as total
            FROM payroll_history
            GROUP BY pay_period_start, pay_period_end
            ORDER BY pay_period_end DESC LIMIT 2
        """)
        payroll_periods = cursor.fetchall()
        wk_labor = payroll_periods[0][2] if len(payroll_periods) >= 1 else 0
        lw_labor = payroll_periods[1][2] if len(payroll_periods) >= 2 else 0

        # 3. Labor Cost %
        lc_pct = round(wk_labor / wk_rev * 100, 1) if wk_rev > 0 else 0
        lw_lc_pct = round(lw_labor / lw_rev * 100, 1) if lw_rev > 0 else 0
        kpis['labor_cost_pct'] = {
            'label': 'Labor Cost',
            'value': lc_pct,
            'unit': '%',
            'trend': round(lc_pct - lw_lc_pct, 1),
            'target': _TARGETS['labor_cost_pct'],
            'status': _status(lc_pct, _TARGETS['labor_cost_pct'], lower_is_better=True),
        }

        # 4. Prime Cost %
        pc_pct = round((wk_cogs + wk_labor) / wk_rev * 100, 1) if wk_rev > 0 else 0
        lw_pc_pct = round((lw_cogs + lw_labor) / lw_rev * 100, 1) if lw_rev > 0 else 0
        kpis['prime_cost_pct'] = {
            'label': 'Prime Cost',
            'value': pc_pct,
            'unit': '%',
            'trend': round(pc_pct - lw_pc_pct, 1),
            'target': _TARGETS['prime_cost_pct'],
            'status': _status(pc_pct, _TARGETS['prime_cost_pct'], lower_is_better=True),
        }

        # 5. Average Ticket
        avg_tkt = round(wk_rev / wk_txn, 2) if wk_txn > 0 else 0
        lw_avg_tkt = round(lw_rev / lw_txn, 2) if lw_txn > 0 else 0
        kpis['avg_ticket'] = {
            'label': 'Avg Ticket',
            'value': avg_tkt,
            'unit': '$',
            'trend': round(avg_tkt - lw_avg_tkt, 2),
            'target': None,
            'status': 'good' if avg_tkt >= lw_avg_tkt else 'warning',
        }

        # 6. Revenue per Labor Hour
        cursor.execute("""
            SELECT COALESCE(SUM(total_hours), 0) FROM attendance
            WHERE DATE(clock_in) >= ?
        """, (week_ago,))
        wk_hours = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COALESCE(SUM(total_hours), 0) FROM attendance
            WHERE DATE(clock_in) >= ? AND DATE(clock_in) < ?
        """, (two_weeks_ago, week_ago))
        lw_hours = cursor.fetchone()[0]

        rplh = round(wk_rev / wk_hours, 2) if wk_hours > 0 else 0
        lw_rplh = round(lw_rev / lw_hours, 2) if lw_hours > 0 else 0
        kpis['revenue_per_labor_hour'] = {
            'label': 'Rev/Labor Hr',
            'value': rplh,
            'unit': '$',
            'trend': round(rplh - lw_rplh, 2),
            'target': _TARGETS['revenue_per_labor_hour'],
            'status': _status(rplh, _TARGETS['revenue_per_labor_hour'], lower_is_better=False),
        }

        # 7. Inventory Turnover (monthly basis)
        cursor.execute("""
            SELECT COALESCE(SUM(cost_of_goods), 0) FROM sales_history
            WHERE DATE(sale_date) >= ?
        """, (month_start,))
        month_cogs = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COALESCE(SUM(quantity_on_hand * COALESCE(last_unit_price, unit_cost, 0)), 0)
            FROM ingredients
        """)
        inv_value = cursor.fetchone()[0]

        inv_turn = round(month_cogs / inv_value, 1) if inv_value > 0 else 0
        kpis['inventory_turnover'] = {
            'label': 'Inv Turnover',
            'value': inv_turn,
            'unit': 'x',
            'trend': None,
            'target': _TARGETS['inventory_turnover'],
            'status': _status(inv_turn, _TARGETS['inventory_turnover'], lower_is_better=False),
        }

        # 8. Invoice Payment Cycle
        cursor.execute("""
            SELECT AVG(
                JULIANDAY(COALESCE(received_date, date('now'))) - JULIANDAY(invoice_date)
            )
            FROM invoices
            WHERE invoice_date >= ?
        """, (month_start,))
        avg_days_row = cursor.fetchone()
        avg_days = round(avg_days_row[0], 0) if avg_days_row[0] else 0
        kpis['invoice_payment_days'] = {
            'label': 'Invoice Cycle',
            'value': avg_days,
            'unit': 'days',
            'trend': None,
            'target': _TARGETS['invoice_payment_days'],
            'status': _status(avg_days, _TARGETS['invoice_payment_days'], lower_is_better=True),
        }

        result = {
            'success': True,
            'generated_at': now.isoformat(),
            'kpis': kpis,
        }

        # Cache for 1 hour
        expires = (now + timedelta(hours=1)).isoformat()
        cursor.execute(
            "DELETE FROM widget_data_cache WHERE widget_key = 'business_kpis' AND cache_key = 'dashboard'"
        )
        cursor.execute("""
            INSERT INTO widget_data_cache (widget_key, cache_key, data, generated_at, expires_at)
            VALUES ('business_kpis', 'dashboard', ?, ?, ?)
        """, (json.dumps(result), now.isoformat(), expires))
        conn.commit()

        return jsonify(result)

    except Exception as e:
        print(f"[KPI] Error: {e}")
        return jsonify({'success': False, 'error': 'Failed to compute KPIs'}), 500

    finally:
        conn.close()
