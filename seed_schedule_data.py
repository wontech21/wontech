"""
Seed Schedule Data Script
Creates sample schedules, employees, and attendance data for testing the schedule system
"""

import sqlite3
import os
from datetime import datetime, timedelta
import random

def seed_schedule_data():
    """Seed the database with sample schedule data"""

    # Get database paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    databases_dir = os.path.join(base_dir, 'databases')

    # Process each organization database
    for db_file in os.listdir(databases_dir):
        if db_file.startswith('org_') and db_file.endswith('.db'):
            db_path = os.path.join(databases_dir, db_file)
            org_id = int(db_file.split('_')[1].split('.')[0])

            print(f"\n{'='*60}")
            print(f"Seeding schedule data for {db_file} (org_id: {org_id})")
            print('='*60)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            try:
                # Get existing employees
                cursor.execute("SELECT id, first_name || ' ' || last_name as name, position, department FROM employees WHERE status = 'active' LIMIT 10")
                employees = cursor.fetchall()

                if not employees or len(employees) < 3:
                    print("⚠️  Not enough employees found. Creating sample employees...")
                    create_sample_employees(cursor, org_id)
                    conn.commit()

                    # Re-fetch employees
                    cursor.execute("SELECT id, first_name || ' ' || last_name as name, position, department FROM employees WHERE status = 'active' LIMIT 10")
                    employees = cursor.fetchall()

                print(f"✅ Found {len(employees)} employees to schedule")

                # Use default admin_id (users table is in master.db, not org db)
                admin_id = 1

                # Clear existing test schedules (optional - uncomment to reset)
                # cursor.execute("DELETE FROM schedules WHERE organization_id = ?", (org_id,))
                # print("🗑️  Cleared existing schedules")

                # Generate schedules for the next 3 weeks
                schedules_created = 0
                today = datetime.now().date()

                # Create schedules for each employee
                for emp_id, emp_name, emp_position, emp_dept in employees:
                    print(f"\n📅 Creating schedules for {emp_name} ({emp_position})")

                    # Create 3 weeks of schedules
                    for week in range(3):
                        # Each employee works 4-5 days per week
                        work_days = random.sample(range(7), random.randint(4, 5))

                        for day_offset in work_days:
                            schedule_date = today + timedelta(weeks=week, days=day_offset)

                            # Random shift times
                            shift_type = random.choice(['regular', 'regular', 'regular', 'overtime'])

                            if shift_type == 'regular':
                                start_hour = random.choice([7, 8, 9, 10])
                                end_hour = min(start_hour + 8, 23)  # Cap at 11pm
                            else:  # overtime
                                start_hour = random.choice([6, 7, 8, 14])
                                end_hour = min(start_hour + 10, 23)  # Cap at 11pm

                            start_time = f"{start_hour:02d}:00"
                            end_time = f"{end_hour:02d}:00"

                            # Insert schedule
                            cursor.execute("""
                                INSERT INTO schedules (
                                    organization_id, employee_id, date, start_time, end_time,
                                    shift_type, position, break_duration, status, created_by
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                org_id, emp_id, schedule_date, start_time, end_time,
                                shift_type, emp_position, 30, 'scheduled', admin_id
                            ))

                            schedules_created += 1

                conn.commit()
                print(f"\n✅ Created {schedules_created} schedules")

                # Create some confirmed schedules
                cursor.execute("""
                    UPDATE schedules
                    SET status = 'confirmed'
                    WHERE organization_id = ? AND date >= date('now')
                    AND id IN (SELECT id FROM schedules WHERE organization_id = ? ORDER BY RANDOM() LIMIT ?)
                """, (org_id, org_id, schedules_created // 3))
                conn.commit()
                print(f"✅ Confirmed {schedules_created // 3} schedules")

                # Create attendance records for past schedules
                cursor.execute("""
                    SELECT id, employee_id, date, start_time, end_time
                    FROM schedules
                    WHERE organization_id = ? AND date < date('now')
                    LIMIT 20
                """, (org_id,))

                past_schedules = cursor.fetchall()
                attendance_created = 0

                for schedule_id, emp_id, date, start_time, end_time in past_schedules:
                    # 80% chance of creating attendance
                    if random.random() < 0.8:
                        # Parse times
                        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
                        end_dt = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")

                        # Add some variance (early/late)
                        clock_in = start_dt + timedelta(minutes=random.randint(-10, 10))
                        clock_out = end_dt + timedelta(minutes=random.randint(-15, 15))

                        # Calculate hours
                        total_hours = (clock_out - clock_in).total_seconds() / 3600

                        cursor.execute("""
                            INSERT OR IGNORE INTO attendance (
                                organization_id, employee_id, clock_in, clock_out,
                                total_hours, status, break_duration
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            org_id, emp_id,
                            clock_in.strftime("%Y-%m-%d %H:%M:%S"),
                            clock_out.strftime("%Y-%m-%d %H:%M:%S"),
                            total_hours, 'clocked_out', 30
                        ))

                        attendance_created += 1

                conn.commit()
                print(f"✅ Created {attendance_created} attendance records")

                # Create some change requests
                cursor.execute("""
                    SELECT id, employee_id, date, start_time, end_time
                    FROM schedules
                    WHERE organization_id = ? AND date >= date('now')
                    ORDER BY RANDOM()
                    LIMIT 5
                """, (org_id,))

                future_schedules = cursor.fetchall()
                change_requests_created = 0

                reasons = [
                    "Need to pick up kids from school",
                    "Doctor's appointment",
                    "Family emergency",
                    "Prefer to work different shift",
                    "Personal commitment"
                ]

                for schedule_id, emp_id, date, start_time, end_time in future_schedules:
                    cursor.execute("""
                        UPDATE schedules
                        SET change_requested_by = ?,
                            change_request_reason = ?,
                            change_request_status = 'pending',
                            change_request_date = datetime('now')
                        WHERE id = ?
                    """, (emp_id, random.choice(reasons), schedule_id))

                    change_requests_created += 1

                conn.commit()
                print(f"✅ Created {change_requests_created} pending change requests")

                # Summary
                cursor.execute("SELECT COUNT(*) FROM schedules WHERE organization_id = ?", (org_id,))
                total_schedules = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM attendance WHERE organization_id = ?", (org_id,))
                total_attendance = cursor.fetchone()[0]

                print(f"\n{'='*60}")
                print(f"SUMMARY for {db_file}")
                print('='*60)
                print(f"Total Schedules: {total_schedules}")
                print(f"Total Attendance Records: {total_attendance}")
                print(f"Pending Change Requests: {change_requests_created}")
                print('='*60)

            except Exception as e:
                print(f"❌ Error seeding data: {e}")
                conn.rollback()
            finally:
                conn.close()

    print(f"\n✨ Schedule data seeding completed!\n")


def create_sample_employees(cursor, org_id):
    """Create sample employees for testing"""
    sample_employees = [
        ("Gabriel", "Thompson", "gabriel.t@test.com", "555-0101", "Manager", "Management", "EMP001"),
        ("Sideir", "Osman", "s.o@test.com", "555-0102", "Kitchen Staff", "Kitchen", "EMP002"),
        ("Emily", "Rodriguez", "emily.r@test.com", "555-0103", "Server", "Front of House", "EMP003"),
        ("Marcus", "Johnson", "marcus.j@test.com", "555-0104", "Chef", "Kitchen", "EMP004"),
        ("Sarah", "Williams", "sarah.w@test.com", "555-0105", "Bartender", "Bar", "EMP005"),
        ("David", "Brown", "david.b@test.com", "555-0106", "Line Cook", "Kitchen", "EMP006"),
        ("Jessica", "Davis", "jessica.d@test.com", "555-0107", "Host", "Front of House", "EMP007"),
        ("Michael", "Chen", "michael.c@test.com", "555-0108", "Dishwasher", "Kitchen", "EMP008")
    ]

    for first_name, last_name, email, phone, position, department, emp_code in sample_employees:
        try:
            cursor.execute("""
                INSERT INTO employees (
                    organization_id, first_name, last_name, email, phone, position, department,
                    employee_code, status, hire_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', date('now'))
            """, (org_id, first_name, last_name, email, phone, position, department, emp_code))
            print(f"  ✅ Created employee: {first_name} {last_name}")
        except sqlite3.IntegrityError:
            # Employee already exists
            print(f"  ⏭️  Employee already exists: {first_name} {last_name}")
            pass


if __name__ == '__main__':
    seed_schedule_data()
