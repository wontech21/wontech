"""
Payroll Management Routes
Handles payroll calculations, reports, and exports
"""

from flask import Blueprint, jsonify, request, g, make_response
import sqlite3
from datetime import datetime, timedelta
from db_manager import get_org_db
from middleware import (
    login_required,
    organization_required,
    permission_required,
    log_audit
)

payroll_bp = Blueprint('payroll', __name__, url_prefix='/api/payroll')

# ========================================
# PAYROLL DATA & CALCULATIONS
# ========================================

def get_week_boundaries(date_str):
    """Get Monday and Sunday of the week containing the given date"""
    date = datetime.strptime(date_str, '%Y-%m-%d')
    # Monday is weekday 0
    monday = date - timedelta(days=date.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')

def calculate_weekly_hours(cursor, employee_id, week_start, week_end):
    """Calculate hours worked in a week, split into regular and overtime"""
    cursor.execute("""
        SELECT
            COALESCE(SUM(total_hours), 0) as total_hours,
            COALESCE(SUM(cc_tips), 0) as total_tips
        FROM attendance
        WHERE employee_id = ?
          AND DATE(clock_in) >= ?
          AND DATE(clock_in) <= ?
          AND status = 'clocked_out'
    """, (employee_id, week_start, week_end))

    result = cursor.fetchone()
    total_hours = result['total_hours'] or 0
    total_tips = result['total_tips'] or 0

    # Calculate regular vs overtime (over 40 hours = OT)
    regular_hours = min(total_hours, 40)
    ot_hours = max(total_hours - 40, 0)

    return {
        'total_hours': round(total_hours, 2),
        'regular_hours': round(regular_hours, 2),
        'ot_hours': round(ot_hours, 2),
        'tips': round(total_tips, 2)
    }


@payroll_bp.route('/weekly', methods=['GET'])
@login_required
@organization_required
@permission_required('employees.read')
def get_weekly_payroll():
    """
    Get payroll data for a specific week (Monday-Sunday)
    Query params:
      - week_start: Date string (YYYY-MM-DD) - any date in the desired week
    """
    week_date = request.args.get('week_start', datetime.now().strftime('%Y-%m-%d'))

    # Get the Monday-Sunday boundaries for this week
    week_start, week_end = get_week_boundaries(week_date)

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get all active employees
        cursor.execute("""
            SELECT
                id, first_name, last_name, position,
                job_classification, hourly_rate, salary,
                employment_type, email,
                bank_account_number, bank_routing_number,
                receives_tips
            FROM employees
            WHERE organization_id = ? AND status = 'active'
            ORDER BY job_classification, last_name
        """, (g.organization['id'],))

        employees = cursor.fetchall()

        payroll_data = []
        totals = {
            'total_hours': 0,
            'regular_hours': 0,
            'ot_hours': 0,
            'regular_wages': 0,
            'ot_wages': 0,
            'tips': 0,
            'salary': 0,
            'gross_pay': 0
        }

        for emp in employees:
            emp_dict = dict(emp)
            hourly_rate = emp_dict['hourly_rate'] or 0
            salary = emp_dict['salary'] or 0

            # Get hours worked this week
            hours_data = calculate_weekly_hours(cursor, emp_dict['id'], week_start, week_end)

            # Calculate wages
            regular_wage = round(hours_data['regular_hours'] * hourly_rate, 2)
            ot_wage = round(hours_data['ot_hours'] * hourly_rate * 1.5, 2)
            tips = hours_data['tips'] if emp_dict['receives_tips'] else 0

            # Gross pay (hourly wages + tips OR salary)
            if salary > 0:
                # Salaried employee - salary is per pay period (weekly in this case)
                gross_pay = salary
            else:
                gross_pay = regular_wage + ot_wage + tips

            employee_payroll = {
                'employee_id': emp_dict['id'],
                'employee_name': f"{emp_dict['first_name']} {emp_dict['last_name']}",
                'position': emp_dict['position'],
                'job_classification': emp_dict['job_classification'] or 'Other',
                'hourly_rate': hourly_rate,
                'total_hours': hours_data['total_hours'],
                'regular_hours': hours_data['regular_hours'],
                'regular_wage': regular_wage,
                'ot_hours': hours_data['ot_hours'],
                'ot_wage': ot_wage,
                'tips': tips,
                'salary': salary,
                'gross_pay': round(gross_pay, 2),
                'email': emp_dict['email'],
                'bank_account': emp_dict['bank_account_number'],
                'bank_routing': emp_dict['bank_routing_number'],
                'employment_type': emp_dict['employment_type']
            }

            payroll_data.append(employee_payroll)

            # Update totals
            totals['total_hours'] += hours_data['total_hours']
            totals['regular_hours'] += hours_data['regular_hours']
            totals['ot_hours'] += hours_data['ot_hours']
            totals['regular_wages'] += regular_wage
            totals['ot_wages'] += ot_wage
            totals['tips'] += tips
            totals['salary'] += salary if salary > 0 else 0
            totals['gross_pay'] += gross_pay

        # Round totals
        for key in totals:
            totals[key] = round(totals[key], 2)

        conn.close()

        return jsonify({
            'success': True,
            'pay_period': {
                'start': week_start,
                'end': week_end,
                'type': 'weekly'
            },
            'employees': payroll_data,
            'totals': totals
        })

    except Exception as e:
        conn.close()
        print(f"Error getting payroll data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@payroll_bp.route('/summary', methods=['GET'])
@login_required
@organization_required
@permission_required('employees.read')
def get_payroll_summary():
    """
    Get payroll summary for multiple weeks
    Query params:
      - start_date: Start of period (YYYY-MM-DD)
      - end_date: End of period (YYYY-MM-DD)
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        # Default to last 4 weeks
        end = datetime.now()
        start = end - timedelta(weeks=4)
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get employee hours and pay for the period
        cursor.execute("""
            SELECT
                e.id,
                e.first_name || ' ' || e.last_name as employee_name,
                e.position,
                e.job_classification,
                e.hourly_rate,
                e.salary,
                COALESCE(SUM(a.total_hours), 0) as total_hours,
                COALESCE(SUM(a.cc_tips), 0) as total_tips,
                COUNT(a.id) as shifts_worked
            FROM employees e
            LEFT JOIN attendance a ON e.id = a.employee_id
                AND DATE(a.clock_in) >= ?
                AND DATE(a.clock_in) <= ?
                AND a.status = 'clocked_out'
            WHERE e.organization_id = ? AND e.status = 'active'
            GROUP BY e.id
            ORDER BY e.job_classification, e.last_name
        """, (start_date, end_date, g.organization['id']))

        employees = cursor.fetchall()
        conn.close()

        summary = []
        for emp in employees:
            emp_dict = dict(emp)
            hourly_rate = emp_dict['hourly_rate'] or 0
            total_hours = emp_dict['total_hours'] or 0

            # Estimate regular vs OT (simplified for summary)
            estimated_pay = total_hours * hourly_rate + (emp_dict['total_tips'] or 0)
            if emp_dict['salary'] > 0:
                # Calculate weeks in period
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                weeks = max(1, (end - start).days / 7)
                estimated_pay = emp_dict['salary'] * weeks

            summary.append({
                'employee_id': emp_dict['id'],
                'employee_name': emp_dict['employee_name'],
                'position': emp_dict['position'],
                'job_classification': emp_dict['job_classification'],
                'total_hours': round(total_hours, 2),
                'shifts_worked': emp_dict['shifts_worked'],
                'tips': round(emp_dict['total_tips'] or 0, 2),
                'estimated_pay': round(estimated_pay, 2)
            })

        return jsonify({
            'success': True,
            'period': {
                'start': start_date,
                'end': end_date
            },
            'summary': summary
        })

    except Exception as e:
        conn.close()
        print(f"Error getting payroll summary: {str(e)}")
        return jsonify({'error': str(e)}), 500


@payroll_bp.route('/available-weeks', methods=['GET'])
@login_required
@organization_required
def get_available_weeks():
    """Get list of weeks that have attendance data"""
    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get date range of attendance records
        cursor.execute("""
            SELECT
                MIN(DATE(clock_in)) as earliest,
                MAX(DATE(clock_in)) as latest
            FROM attendance
            WHERE organization_id = ?
        """, (g.organization['id'],))

        result = cursor.fetchone()
        conn.close()

        if not result['earliest']:
            return jsonify({
                'success': True,
                'weeks': []
            })

        # Generate list of weeks
        earliest = datetime.strptime(result['earliest'], '%Y-%m-%d')
        latest = datetime.strptime(result['latest'], '%Y-%m-%d')

        # Adjust to Monday of earliest week
        earliest_monday = earliest - timedelta(days=earliest.weekday())

        weeks = []
        current = earliest_monday
        while current <= latest:
            week_end = current + timedelta(days=6)
            weeks.append({
                'start': current.strftime('%Y-%m-%d'),
                'end': week_end.strftime('%Y-%m-%d'),
                'label': f"{current.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
            })
            current += timedelta(weeks=1)

        # Reverse so most recent is first
        weeks.reverse()

        return jsonify({
            'success': True,
            'weeks': weeks
        })

    except Exception as e:
        conn.close()
        print(f"Error getting available weeks: {str(e)}")
        return jsonify({'error': str(e)}), 500


@payroll_bp.route('/available-years', methods=['GET'])
@login_required
@organization_required
def get_available_years():
    """Get list of years that have attendance data"""
    conn = get_org_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT strftime('%Y', clock_in) as year
            FROM attendance
            WHERE organization_id = ?
            ORDER BY year DESC
        """, (g.organization['id'],))

        years = [row['year'] for row in cursor.fetchall() if row['year']]
        conn.close()

        return jsonify({
            'success': True,
            'years': years
        })

    except Exception as e:
        conn.close()
        print(f"Error getting available years: {str(e)}")
        return jsonify({'error': str(e)}), 500


@payroll_bp.route('/monthly', methods=['GET'])
@login_required
@organization_required
@permission_required('employees.read')
def get_monthly_payroll():
    """
    Get payroll data for a specific month
    Query params:
      - month: Month number (1-12)
      - year: Year (YYYY)
    """
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    if not month or not year:
        return jsonify({'error': 'Month and year are required'}), 400

    # Calculate month boundaries
    import calendar
    first_day = f"{year}-{month:02d}-01"
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = f"{year}-{month:02d}-{last_day_num:02d}"

    month_name = calendar.month_name[month]

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get all active employees
        cursor.execute("""
            SELECT
                id, first_name, last_name, position,
                job_classification, hourly_rate, salary,
                employment_type, email,
                bank_account_number, bank_routing_number,
                receives_tips
            FROM employees
            WHERE organization_id = ? AND status = 'active'
            ORDER BY job_classification, last_name
        """, (g.organization['id'],))

        employees = cursor.fetchall()

        payroll_data = []
        totals = {
            'total_hours': 0,
            'regular_hours': 0,
            'ot_hours': 0,
            'regular_wages': 0,
            'ot_wages': 0,
            'tips': 0,
            'salary': 0,
            'gross_pay': 0
        }

        for emp in employees:
            emp_dict = dict(emp)
            hourly_rate = emp_dict['hourly_rate'] or 0
            salary = emp_dict['salary'] or 0

            # Get all attendance for this employee in the month
            cursor.execute("""
                SELECT
                    DATE(clock_in) as work_date,
                    strftime('%W', clock_in) as week_num,
                    COALESCE(SUM(total_hours), 0) as daily_hours,
                    COALESCE(SUM(cc_tips), 0) as daily_tips
                FROM attendance
                WHERE employee_id = ?
                  AND DATE(clock_in) >= ?
                  AND DATE(clock_in) <= ?
                  AND status = 'clocked_out'
                GROUP BY DATE(clock_in)
                ORDER BY work_date
            """, (emp_dict['id'], first_day, last_day))

            daily_records = cursor.fetchall()

            # Calculate weekly overtime properly
            # Group by week and calculate OT per week
            weekly_hours = {}
            total_tips = 0

            for record in daily_records:
                week = record['week_num']
                if week not in weekly_hours:
                    weekly_hours[week] = 0
                weekly_hours[week] += record['daily_hours']
                total_tips += record['daily_tips']

            # Calculate regular and OT hours across all weeks
            total_hours = 0
            regular_hours = 0
            ot_hours = 0

            for week, hours in weekly_hours.items():
                total_hours += hours
                week_regular = min(hours, 40)
                week_ot = max(hours - 40, 0)
                regular_hours += week_regular
                ot_hours += week_ot

            # Calculate wages
            regular_wage = round(regular_hours * hourly_rate, 2)
            ot_wage = round(ot_hours * hourly_rate * 1.5, 2)
            tips = total_tips if emp_dict['receives_tips'] else 0

            # For salaried employees, calculate monthly salary
            # Assuming salary field is bi-weekly, multiply by ~2.17 for monthly
            monthly_salary = 0
            if salary > 0:
                # Count weeks in this month (for salary calculation)
                weeks_in_month = len(weekly_hours) if weekly_hours else 4
                monthly_salary = salary * (weeks_in_month / 1)  # salary is already weekly equivalent

            # Gross pay
            if salary > 0:
                gross_pay = monthly_salary
            else:
                gross_pay = regular_wage + ot_wage + tips

            employee_payroll = {
                'employee_id': emp_dict['id'],
                'employee_name': f"{emp_dict['first_name']} {emp_dict['last_name']}",
                'position': emp_dict['position'],
                'job_classification': emp_dict['job_classification'] or 'Other',
                'hourly_rate': hourly_rate,
                'total_hours': round(total_hours, 2),
                'regular_hours': round(regular_hours, 2),
                'regular_wage': regular_wage,
                'ot_hours': round(ot_hours, 2),
                'ot_wage': ot_wage,
                'tips': round(tips, 2),
                'salary': round(monthly_salary, 2),
                'gross_pay': round(gross_pay, 2),
                'email': emp_dict['email'],
                'bank_account': emp_dict['bank_account_number'],
                'bank_routing': emp_dict['bank_routing_number'],
                'employment_type': emp_dict['employment_type']
            }

            payroll_data.append(employee_payroll)

            # Update totals
            totals['total_hours'] += total_hours
            totals['regular_hours'] += regular_hours
            totals['ot_hours'] += ot_hours
            totals['regular_wages'] += regular_wage
            totals['ot_wages'] += ot_wage
            totals['tips'] += tips
            totals['salary'] += monthly_salary
            totals['gross_pay'] += gross_pay

        # Round totals
        for key in totals:
            totals[key] = round(totals[key], 2)

        conn.close()

        return jsonify({
            'success': True,
            'pay_period': {
                'start': first_day,
                'end': last_day,
                'type': 'monthly',
                'month': month,
                'year': year,
                'month_name': month_name
            },
            'employees': payroll_data,
            'totals': totals
        })

    except Exception as e:
        conn.close()
        print(f"Error getting monthly payroll data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@payroll_bp.route('/export/csv', methods=['GET'])
@login_required
@organization_required
@permission_required('employees.read')
def export_payroll_csv():
    """Export payroll data as CSV (weekly or monthly)"""
    import calendar

    # Check if monthly or weekly export
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    if month and year:
        # Monthly export
        first_day = f"{year}-{month:02d}-01"
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = f"{year}-{month:02d}-{last_day_num:02d}"
        filename = f"payroll_{calendar.month_name[month]}_{year}.csv"
        is_monthly = True
    else:
        # Weekly export
        week_date = request.args.get('week_start', datetime.now().strftime('%Y-%m-%d'))
        first_day, last_day = get_week_boundaries(week_date)
        filename = f"payroll_{first_day}_to_{last_day}.csv"
        is_monthly = False

    conn = get_org_db()
    cursor = conn.cursor()

    try:
        # Get all employees with payroll data
        cursor.execute("""
            SELECT
                e.id, e.first_name, e.last_name, e.position,
                e.job_classification, e.hourly_rate, e.salary,
                e.email, e.bank_account_number, e.bank_routing_number,
                e.receives_tips
            FROM employees e
            WHERE e.organization_id = ? AND e.status = 'active'
            ORDER BY e.job_classification, e.last_name
        """, (g.organization['id'],))

        employees = cursor.fetchall()

        # Build CSV
        csv_lines = []
        headers = [
            'Employee Name', 'Hourly', 'Total Hours', 'Regular Hours',
            'Regular Wage', 'OT Hours', 'OT Wage', 'CC Tips', 'Salary',
            'Job Classification', 'Account #', 'Routing #', 'Email'
        ]
        csv_lines.append(','.join(headers))

        for emp in employees:
            emp_dict = dict(emp)
            hourly_rate = emp_dict['hourly_rate'] or 0
            salary_rate = emp_dict['salary'] or 0

            if is_monthly:
                # Calculate monthly hours with proper OT per week
                cursor.execute("""
                    SELECT
                        strftime('%W', clock_in) as week_num,
                        COALESCE(SUM(total_hours), 0) as weekly_hours,
                        COALESCE(SUM(cc_tips), 0) as weekly_tips
                    FROM attendance
                    WHERE employee_id = ?
                      AND DATE(clock_in) >= ?
                      AND DATE(clock_in) <= ?
                      AND status = 'clocked_out'
                    GROUP BY week_num
                """, (emp_dict['id'], first_day, last_day))

                weekly_data = cursor.fetchall()
                total_hours = 0
                regular_hours = 0
                ot_hours = 0
                total_tips = 0

                for week in weekly_data:
                    wh = week['weekly_hours'] or 0
                    total_hours += wh
                    regular_hours += min(wh, 40)
                    ot_hours += max(wh - 40, 0)
                    total_tips += week['weekly_tips'] or 0

                hours_data = {
                    'total_hours': round(total_hours, 2),
                    'regular_hours': round(regular_hours, 2),
                    'ot_hours': round(ot_hours, 2),
                    'tips': round(total_tips, 2)
                }

                # Monthly salary calculation
                weeks_worked = len(weekly_data) if weekly_data else 0
                salary = salary_rate * weeks_worked if salary_rate > 0 else 0
            else:
                hours_data = calculate_weekly_hours(cursor, emp_dict['id'], first_day, last_day)
                salary = salary_rate

            regular_wage = round(hours_data['regular_hours'] * hourly_rate, 2)
            ot_wage = round(hours_data['ot_hours'] * hourly_rate * 1.5, 2)
            tips = hours_data['tips'] if emp_dict['receives_tips'] else 0

            row = [
                f"{emp_dict['first_name']} {emp_dict['last_name']}",
                f"${hourly_rate:.2f}" if hourly_rate > 0 else '-',
                str(hours_data['total_hours']) if hours_data['total_hours'] > 0 else '-',
                str(hours_data['regular_hours']) if hours_data['regular_hours'] > 0 else '-',
                f"${regular_wage:.2f}" if regular_wage > 0 else '-',
                str(hours_data['ot_hours']) if hours_data['ot_hours'] > 0 else '-',
                f"${ot_wage:.2f}" if ot_wage > 0 else '-',
                f"${tips:.2f}" if tips > 0 else '-',
                f"${salary:.2f}" if salary > 0 else '-',
                emp_dict['job_classification'] or '-',
                emp_dict['bank_account_number'] or '-',
                emp_dict['bank_routing_number'] or '-',
                emp_dict['email'] or '-'
            ]
            csv_lines.append(','.join(row))

        conn.close()

        # Create response
        csv_content = '\n'.join(csv_lines)
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'

        return response

    except Exception as e:
        conn.close()
        print(f"Error exporting payroll: {str(e)}")
        return jsonify({'error': str(e)}), 500
