#!/usr/bin/env python3
"""
Simulate 2 months of payroll data (late January through end of March 2026)
Creates realistic time entries for all employees with varying patterns:
- Full-time (35-45 hours/week, some overtime)
- Part-time (15-25 hours/week)
- Management (salaried)
"""

import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "databases" / "org_1.db"

# Employee configurations with realistic restaurant roles
EMPLOYEE_CONFIGS = [
    # (id, position, job_classification, hourly_rate, salary, employment_type, work_pattern)
    # work_pattern: 'full-time', 'part-time', 'overtime-heavy', 'management'
    (1, "Line Cook", "Kitchen", 18.50, 0, "full-time", "overtime-heavy"),
    (2, "Cashier", "Front", 16.00, 0, "full-time", "full-time"),
    (3, "General Manager", "Management", 0, 2884.62, "full-time", "management"),  # Bi-weekly salary
    (4, "Kitchen Staff", "Kitchen", 17.00, 0, "full-time", "full-time"),
    (5, "Server", "Front", 15.00, 0, "part-time", "part-time"),
    (6, "Head Chef", "Kitchen", 22.00, 0, "full-time", "overtime-heavy"),
    (7, "Bartender", "Front", 17.00, 0, "full-time", "full-time"),
    (8, "Line Cook", "Kitchen", 17.50, 0, "full-time", "full-time"),
    (9, "Host", "Front", 14.00, 0, "part-time", "part-time"),
    (10, "Dishwasher", "Kitchen", 15.00, 0, "full-time", "full-time"),
]

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_payroll_columns():
    """Add columns needed for payroll export if they don't exist"""
    conn = get_connection()
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(employees)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    columns_to_add = [
        ("job_classification", "TEXT DEFAULT 'Front'"),
        ("bank_account_number", "TEXT"),
        ("bank_routing_number", "TEXT"),
        ("receives_tips", "INTEGER DEFAULT 0"),
    ]

    for col_name, col_def in columns_to_add:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name}")
            cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_def}")

    conn.commit()
    conn.close()
    print("Payroll columns added/verified.")

def update_employee_configs():
    """Update employees with proper pay rates and classifications"""
    conn = get_connection()
    cursor = conn.cursor()

    # Generate random but realistic bank info
    routing_numbers = ["211370545", "011000138", "231372691", "031176110", "121000358"]

    for emp_id, position, job_class, hourly, salary, emp_type, _ in EMPLOYEE_CONFIGS:
        # Generate bank account (random 10-12 digit number)
        account_num = ''.join([str(random.randint(0, 9)) for _ in range(random.randint(10, 12))])
        routing_num = random.choice(routing_numbers)

        # Determine if receives tips (Front and Driver positions)
        receives_tips = 1 if job_class in ["Front", "Driver"] else 0

        cursor.execute("""
            UPDATE employees SET
                position = ?,
                job_classification = ?,
                hourly_rate = ?,
                salary = ?,
                employment_type = ?,
                bank_account_number = ?,
                bank_routing_number = ?,
                receives_tips = ?
            WHERE id = ?
        """, (position, job_class, hourly, salary, emp_type, account_num, routing_num, receives_tips, emp_id))

        print(f"Updated employee {emp_id}: {position} ({job_class}) - ${hourly}/hr or ${salary} salary")

    conn.commit()
    conn.close()
    print("Employee configurations updated.")

def generate_shift_times(work_pattern, day_of_week):
    """Generate realistic shift start/end times based on work pattern"""

    if work_pattern == "management":
        # Management works regular hours, no clock tracking
        return None, None

    # Restaurant typical shifts
    shifts = {
        "morning": (6, 14),    # 6am - 2pm
        "day": (10, 18),       # 10am - 6pm
        "evening": (14, 22),   # 2pm - 10pm
        "night": (16, 24),     # 4pm - midnight
    }

    # Weekend vs weekday patterns
    is_weekend = day_of_week in [5, 6]  # Saturday, Sunday

    if work_pattern == "full-time":
        # Full-time: 5 days, ~8 hours
        if random.random() < 0.15:  # 15% chance of day off
            return None, None
        shift_type = random.choice(["morning", "day", "evening"])
        base_start, base_end = shifts[shift_type]
        # Add some variation
        start_hour = base_start + random.uniform(-0.5, 0.5)
        hours = random.uniform(7.5, 9.0)

    elif work_pattern == "overtime-heavy":
        # Overtime workers: longer shifts, more days
        if random.random() < 0.08:  # 8% chance of day off
            return None, None
        shift_type = random.choice(["morning", "day", "evening"])
        base_start, _ = shifts[shift_type]
        start_hour = base_start + random.uniform(-0.5, 0.5)
        hours = random.uniform(9.0, 12.0)  # Longer shifts

    elif work_pattern == "part-time":
        # Part-time: 3-4 days, shorter shifts
        if random.random() < 0.45:  # 45% chance of no shift
            return None, None
        shift_type = random.choice(["day", "evening"])
        base_start, _ = shifts[shift_type]
        start_hour = base_start + random.uniform(-0.5, 1.0)
        hours = random.uniform(4.0, 6.5)

    else:
        return None, None

    # Cap end time at reasonable hour
    end_hour = min(start_hour + hours, 24.0)
    actual_hours = end_hour - start_hour

    return start_hour, actual_hours

def simulate_time_entries():
    """Generate time entries from Jan 27, 2026 through March 31, 2026"""
    conn = get_connection()
    cursor = conn.cursor()

    # Clear existing attendance data for clean simulation
    cursor.execute("DELETE FROM attendance WHERE DATE(clock_in) >= '2026-01-27'")
    print("Cleared existing attendance data from Jan 27 onwards.")

    # Date range: Jan 27 (Monday) through March 31, 2026
    start_date = datetime(2026, 1, 27)
    end_date = datetime(2026, 3, 31)

    entries_created = 0

    current_date = start_date
    while current_date <= end_date:
        day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday

        for emp_id, _, job_class, _, _, _, work_pattern in EMPLOYEE_CONFIGS:
            # Skip management (salaried, no time tracking)
            if work_pattern == "management":
                continue

            start_hour, hours_worked = generate_shift_times(work_pattern, day_of_week)

            if start_hour is None:
                continue  # Day off

            # Create clock in/out times
            clock_in = current_date.replace(hour=int(start_hour), minute=int((start_hour % 1) * 60))
            # Add some minute variation
            clock_in += timedelta(minutes=random.randint(-5, 10))

            clock_out = clock_in + timedelta(hours=hours_worked)
            # Add some minute variation to clock out
            clock_out += timedelta(minutes=random.randint(-5, 15))

            # Calculate break (30 min for shifts > 6 hours)
            break_duration = 30 if hours_worked > 6 else 0

            # Insert record - total_hours will be calculated by SQL using same formula as app
            cursor.execute("""
                INSERT INTO attendance (
                    organization_id, employee_id, clock_in, clock_out,
                    total_hours, status, break_duration, created_at
                ) VALUES (
                    ?, ?, ?, ?,
                    ROUND((julianday(?) - julianday(?)) * 24 - (? / 60.0), 2),
                    'clocked_out', ?, ?
                )
            """, (
                1,
                emp_id,
                clock_in.strftime("%Y-%m-%d %H:%M:%S"),
                clock_out.strftime("%Y-%m-%d %H:%M:%S"),
                clock_out.strftime("%Y-%m-%d %H:%M:%S"),  # For total_hours calc
                clock_in.strftime("%Y-%m-%d %H:%M:%S"),   # For total_hours calc
                break_duration,                           # For total_hours calc
                break_duration,
                clock_in.strftime("%Y-%m-%d %H:%M:%S")
            ))
            entries_created += 1

        current_date += timedelta(days=1)

    conn.commit()
    conn.close()
    print(f"Created {entries_created} time entries from {start_date.date()} to {end_date.date()}")

def generate_tip_data():
    """Generate CC tips for front-of-house staff based on hours worked"""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if tips column exists in attendance
    cursor.execute("PRAGMA table_info(attendance)")
    columns = {row[1] for row in cursor.fetchall()}

    if "cc_tips" not in columns:
        cursor.execute("ALTER TABLE attendance ADD COLUMN cc_tips REAL DEFAULT 0")
        print("Added cc_tips column to attendance table")

    # Get employees who receive tips
    cursor.execute("""
        SELECT id, job_classification FROM employees
        WHERE receives_tips = 1 AND status = 'active'
    """)
    tip_employees = {row[0]: row[1] for row in cursor.fetchall()}

    # Update attendance records with tips
    cursor.execute("""
        SELECT id, employee_id, total_hours, DATE(clock_in) as work_date
        FROM attendance
        WHERE DATE(clock_in) >= '2026-01-27'
    """)

    for row in cursor.fetchall():
        att_id, emp_id, hours, work_date = row
        if emp_id in tip_employees:
            # Tips roughly $5-15 per hour for front staff
            tip_rate = random.uniform(5, 15)
            tips = round(hours * tip_rate, 2)
            cursor.execute("UPDATE attendance SET cc_tips = ? WHERE id = ?", (tips, att_id))

    conn.commit()
    conn.close()
    print("Generated tip data for front-of-house staff")

def print_summary():
    """Print summary of simulated data"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("SIMULATION SUMMARY")
    print("="*60)

    # Employee summary
    cursor.execute("""
        SELECT e.id, e.first_name, e.last_name, e.position, e.job_classification,
               e.hourly_rate, e.salary, e.employment_type,
               COUNT(a.id) as shifts,
               COALESCE(SUM(a.total_hours), 0) as total_hours
        FROM employees e
        LEFT JOIN attendance a ON e.id = a.employee_id AND DATE(a.clock_in) >= '2026-01-27'
        WHERE e.status = 'active'
        GROUP BY e.id
        ORDER BY e.job_classification, e.last_name
    """)

    print(f"\n{'Name':<25} {'Position':<20} {'Class':<12} {'Rate':<10} {'Shifts':<8} {'Hours':<10}")
    print("-" * 90)

    for row in cursor.fetchall():
        name = f"{row[1]} {row[2]}"
        rate = f"${row[5]}/hr" if row[5] > 0 else f"${row[6]} sal"
        print(f"{name:<25} {row[3]:<20} {row[4]:<12} {rate:<10} {row[8]:<8} {row[9]:<10.1f}")

    # Weekly breakdown for one sample week
    print("\n" + "-"*60)
    print("SAMPLE WEEK: March 2-8, 2026")
    print("-"*60)

    cursor.execute("""
        SELECT e.first_name || ' ' || e.last_name as name,
               e.hourly_rate,
               SUM(a.total_hours) as hours,
               SUM(CASE WHEN a.total_hours > 0 THEN
                   CASE WHEN SUM(a.total_hours) OVER (PARTITION BY e.id) > 40
                        THEN a.total_hours ELSE 0 END
                   ELSE 0 END) as ot_hours,
               COALESCE(SUM(a.cc_tips), 0) as tips
        FROM employees e
        LEFT JOIN attendance a ON e.id = a.employee_id
            AND DATE(a.clock_in) BETWEEN '2026-03-02' AND '2026-03-08'
        WHERE e.status = 'active' AND e.hourly_rate > 0
        GROUP BY e.id
        ORDER BY hours DESC
    """)

    print(f"\n{'Name':<25} {'Rate':<10} {'Hours':<10} {'Tips':<10} {'Est Pay':<12}")
    print("-" * 70)

    for row in cursor.fetchall():
        hours = row[2] or 0
        tips = row[4] or 0
        rate = row[1]
        reg_hours = min(hours, 40)
        ot_hours = max(hours - 40, 0)
        est_pay = (reg_hours * rate) + (ot_hours * rate * 1.5) + tips
        print(f"{row[0]:<25} ${rate:<9.2f} {hours:<10.1f} ${tips:<9.2f} ${est_pay:<11.2f}")

    conn.close()

def main():
    print("="*60)
    print("PAYROLL DATA SIMULATION")
    print("Generating 2 months of time entries (Jan 27 - Mar 31, 2026)")
    print("="*60 + "\n")

    # Step 1: Add necessary columns
    print("Step 1: Adding payroll columns...")
    add_payroll_columns()

    # Step 2: Update employee configurations
    print("\nStep 2: Updating employee configurations...")
    update_employee_configs()

    # Step 3: Generate time entries
    print("\nStep 3: Generating time entries...")
    simulate_time_entries()

    # Step 4: Generate tip data
    print("\nStep 4: Generating tip data...")
    generate_tip_data()

    # Step 5: Print summary
    print_summary()

    print("\n" + "="*60)
    print("SIMULATION COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
