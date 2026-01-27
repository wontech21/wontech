# Payroll Data Architecture

## Single Source of Truth: `attendance` Table

All time tracking and payroll data flows from a single source - the `attendance` table in the organization database.

```
┌─────────────────────────────────────────────────────────────────┐
│                      attendance table                            │
│  (databases/org_{id}.db)                                         │
├─────────────────────────────────────────────────────────────────┤
│  id                  - Primary key                               │
│  organization_id     - Multi-tenant isolation                    │
│  employee_id         - FK to employees table                     │
│  clock_in            - TIMESTAMP of shift start                  │
│  clock_out           - TIMESTAMP of shift end                    │
│  break_duration      - Minutes of break time                     │
│  total_hours         - Calculated: (clock_out - clock_in) - break│
│  cc_tips             - Credit card tips for this shift           │
│  status              - clocked_in, on_break, clocked_out         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌───────────────────┐                    ┌───────────────────┐
│   Admin Portal    │                    │  Employee Portal  │
├───────────────────┤                    ├───────────────────┤
│ • Attendance Tab  │                    │ • My Time Entries │
│ • Payroll Tab     │                    │ • My Schedule     │
│ • Schedules Tab   │                    │ • Paystubs        │
└───────────────────┘                    └───────────────────┘
```

## Hours Calculation Formula

All components use the same formula:

```sql
total_hours = (julianday(clock_out) - julianday(clock_in)) * 24 - (break_duration / 60.0)
```

This is calculated:
1. **On clock-out**: Automatically by the API when employee clocks out
2. **On edit**: Recalculated when admin edits an attendance record
3. **In simulation**: Using the same formula for consistency

## Data Flow by Component

### 1. Employee Clock In/Out
```
POST /api/attendance/clock-in  → Creates attendance record with clock_in
POST /api/attendance/clock-out → Updates with clock_out, calculates total_hours
```

### 2. Admin Attendance Tab
```
GET /api/attendance/history → Reads from attendance table
                            → Shows all employees' records
                            → Same total_hours displayed
```

### 3. Admin Payroll Tab
```
GET /api/payroll/weekly?week_start=YYYY-MM-DD
GET /api/payroll/monthly?month=M&year=YYYY
    → Reads from attendance table
    → Sums total_hours by employee
    → Calculates Regular (≤40) vs OT (>40) per week
    → Multiplies by hourly_rate from employees table
```

### 4. Employee Time Entries
```
GET /employee/time-entries/data
    → Reads from attendance table (WHERE employee_id = current)
    → Shows personal clock in/out history
    → Same total_hours values
```

## Payroll Calculations

### Weekly Payroll
```
Regular Hours = MIN(weekly_total_hours, 40)
OT Hours = MAX(weekly_total_hours - 40, 0)
Regular Wage = Regular Hours × Hourly Rate
OT Wage = OT Hours × Hourly Rate × 1.5
Tips = SUM(cc_tips) for the week
Gross Pay = Regular Wage + OT Wage + Tips (or Salary if salaried)
```

### Monthly Payroll
```
For each week in the month:
    Weekly Regular = MIN(week_hours, 40)
    Weekly OT = MAX(week_hours - 40, 0)

Total Regular Hours = SUM(Weekly Regular)
Total OT Hours = SUM(Weekly OT)
(This ensures OT is calculated per-week, not on monthly total)
```

## Employee Table Fields Used

| Field | Purpose |
|-------|---------|
| hourly_rate | Wage per hour for hourly employees |
| salary | Weekly salary for salaried employees |
| job_classification | Front, Kitchen, Driver, Management |
| receives_tips | 1 if employee gets CC tips, 0 if not |
| bank_account_number | For payroll export |
| bank_routing_number | For payroll export |

## Simulation Data

The `simulate_payroll_data.py` script:
1. Creates attendance records with realistic clock_in/clock_out timestamps
2. Calculates total_hours using the same formula as the app
3. Assigns CC tips to front-of-house staff
4. Covers Jan 27 - Mar 31, 2026 (~9 weeks of data)

To regenerate simulation data:
```bash
python simulate_payroll_data.py
```

## Verifying Data Consistency

All these should show the same hours for an employee:
1. Admin Attendance Tab → Employee's total hours
2. Admin Payroll Tab → Weekly/Monthly breakdown
3. Employee Portal → My Time Entries → Total hours
