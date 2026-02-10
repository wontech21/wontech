/**
 * Payroll Management JavaScript
 * Handles payroll data display, calculations, and exports
 */

// Global state
let payrollData = null;
let currentPayPeriod = null;
let currentViewType = 'weekly';

/**
 * Initialize the Payroll tab
 */
async function initializePayrollTab() {
    console.log('Initializing Payroll tab...');
    await loadAvailableWeeks();
    await loadAvailableYears();
}

/**
 * Toggle between weekly and monthly view
 */
function togglePayrollView() {
    const viewType = document.getElementById('payrollViewType').value;
    currentViewType = viewType;

    const weeklySelector = document.getElementById('weeklySelector');
    const monthlySelector = document.getElementById('monthlySelector');

    if (viewType === 'weekly') {
        weeklySelector.style.display = 'block';
        monthlySelector.style.display = 'none';
        loadPayrollData();
    } else {
        weeklySelector.style.display = 'none';
        monthlySelector.style.display = 'flex';
        loadMonthlyPayroll();
    }
}

/**
 * Load available weeks from the API
 */
async function loadAvailableWeeks() {
    const select = document.getElementById('payrollWeekSelect');
    if (!select) return;

    try {
        const response = await fetch('/api/payroll/available-weeks');
        const data = await response.json();

        if (data.success && data.weeks.length > 0) {
            select.innerHTML = data.weeks.map((week, index) =>
                `<option value="${week.start}" ${index === 0 ? 'selected' : ''}>${week.label}</option>`
            ).join('');

            // Load the most recent week
            loadPayrollData();
        } else {
            select.innerHTML = '<option value="">No payroll data available</option>';
        }
    } catch (error) {
        console.error('Error loading available weeks:', error);
        select.innerHTML = '<option value="">Error loading weeks</option>';
    }
}

/**
 * Load available years from the API
 */
async function loadAvailableYears() {
    const yearSelect = document.getElementById('payrollYearSelect');
    if (!yearSelect) return;

    try {
        const response = await fetch('/api/payroll/available-years');
        const data = await response.json();

        if (data.success && data.years.length > 0) {
            yearSelect.innerHTML = data.years.map((year, index) =>
                `<option value="${year}" ${index === 0 ? 'selected' : ''}>${year}</option>`
            ).join('');

            // Set current month as default
            const monthSelect = document.getElementById('payrollMonthSelect');
            const currentMonth = new Date().getMonth() + 1;
            if (monthSelect) {
                monthSelect.value = currentMonth;
            }
        } else {
            yearSelect.innerHTML = '<option value="">No data</option>';
        }
    } catch (error) {
        console.error('Error loading available years:', error);
        yearSelect.innerHTML = '<option value="">Error</option>';
    }
}

/**
 * Load monthly payroll data
 */
async function loadMonthlyPayroll() {
    const monthSelect = document.getElementById('payrollMonthSelect');
    const yearSelect = document.getElementById('payrollYearSelect');

    const month = monthSelect ? monthSelect.value : null;
    const year = yearSelect ? yearSelect.value : null;

    if (!month || !year) {
        return;
    }

    const tbody = document.getElementById('payrollTableBody');
    tbody.innerHTML = '<tr><td colspan="10" class="loading">Loading monthly payroll data...</td></tr>';

    try {
        const response = await fetch(`/api/payroll/monthly?month=${month}&year=${year}`);
        const data = await response.json();

        if (data.success) {
            payrollData = data;
            currentPayPeriod = data.pay_period;
            displayPayrollData(data);
            updateSummaryCards(data.totals);
        } else {
            tbody.innerHTML = `<tr><td colspan="10" class="loading" style="color: #ef4444;">Error: ${data.error}</td></tr>`;
        }
    } catch (error) {
        console.error('Error loading monthly payroll data:', error);
        tbody.innerHTML = '<tr><td colspan="10" class="loading" style="color: #ef4444;">Error loading payroll data</td></tr>';
    }
}

/**
 * Load payroll data for the selected week
 */
async function loadPayrollData() {
    const select = document.getElementById('payrollWeekSelect');
    const weekStart = select ? select.value : null;

    if (!weekStart) {
        return;
    }

    const tbody = document.getElementById('payrollTableBody');
    tbody.innerHTML = '<tr><td colspan="10" class="loading">Loading payroll data...</td></tr>';

    try {
        const response = await fetch(`/api/payroll/weekly?week_start=${weekStart}`);
        const data = await response.json();

        if (data.success) {
            payrollData = data;
            currentPayPeriod = data.pay_period;
            displayPayrollData(data);
            updateSummaryCards(data.totals);
        } else {
            tbody.innerHTML = `<tr><td colspan="10" class="loading" style="color: #ef4444;">Error: ${data.error}</td></tr>`;
        }
    } catch (error) {
        console.error('Error loading payroll data:', error);
        tbody.innerHTML = '<tr><td colspan="10" class="loading" style="color: #ef4444;">Error loading payroll data</td></tr>';
    }
}

/**
 * Display payroll data in the table
 */
function displayPayrollData(data) {
    const tbody = document.getElementById('payrollTableBody');
    const tfoot = document.getElementById('payrollTableFoot');

    if (!data.employees || data.employees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="loading">No payroll data for this period</td></tr>';
        tfoot.style.display = 'none';
        return;
    }

    // Group employees by classification
    const grouped = {};
    data.employees.forEach(emp => {
        const classification = emp.job_classification || 'Other';
        if (!grouped[classification]) {
            grouped[classification] = [];
        }
        grouped[classification].push(emp);
    });

    // Sort classifications: Management first, then alphabetical
    const classOrder = ['Management', 'Front', 'Kitchen', 'Driver', 'Other'];
    const sortedClasses = Object.keys(grouped).sort((a, b) => {
        const aIndex = classOrder.indexOf(a);
        const bIndex = classOrder.indexOf(b);
        if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
        if (aIndex === -1) return 1;
        if (bIndex === -1) return -1;
        return aIndex - bIndex;
    });

    let html = '';
    sortedClasses.forEach(classification => {
        grouped[classification].forEach(emp => {
            const hasHours = emp.total_hours > 0;
            const isSalaried = emp.salary > 0;
            const rowClass = !hasHours && !isSalaried ? 'inactive-row' : '';

            html += `
                <tr class="${rowClass}" style="${!hasHours && !isSalaried ? 'background: #fef3c7; text-decoration: line-through; opacity: 0.7;' : ''}">
                    <td><strong>${emp.employee_name}</strong></td>
                    <td>${emp.hourly_rate > 0 ? '$' + emp.hourly_rate.toFixed(2) : '-'}</td>
                    <td>${emp.total_hours > 0 ? emp.total_hours.toFixed(1) : '-'}</td>
                    <td>${emp.regular_hours > 0 ? emp.regular_hours.toFixed(1) : '-'}</td>
                    <td>${emp.regular_wage > 0 ? '$' + emp.regular_wage.toFixed(2) : '-'}</td>
                    <td>${emp.ot_hours > 0 ? emp.ot_hours.toFixed(1) : '-'}</td>
                    <td>${emp.ot_wage > 0 ? '$' + emp.ot_wage.toFixed(2) : '-'}</td>
                    <td>${emp.tips > 0 ? '$' + emp.tips.toFixed(2) : '-'}</td>
                    <td>${emp.salary > 0 ? '$' + emp.salary.toFixed(2) : '-'}</td>
                    <td><span class="classification-badge classification-${classification.toLowerCase()}">${classification}</span></td>
                </tr>
            `;
        });
    });

    tbody.innerHTML = html;

    // Update footer
    const totals = data.totals;
    document.getElementById('footTotalHours').textContent = totals.total_hours.toFixed(1);
    document.getElementById('footRegHours').textContent = totals.regular_hours.toFixed(1);
    document.getElementById('footRegWages').textContent = '$' + totals.regular_wages.toFixed(2);
    document.getElementById('footOTHours').textContent = totals.ot_hours.toFixed(1);
    document.getElementById('footOTWages').textContent = '$' + totals.ot_wages.toFixed(2);
    document.getElementById('footTips').textContent = '$' + totals.tips.toFixed(2);
    document.getElementById('footSalary').textContent = '$' + totals.salary.toFixed(2);

    tfoot.style.display = 'table-footer-group';

    // Add classification badge styles
    addPayrollStyles();
}

/**
 * Update summary cards with totals
 */
function updateSummaryCards(totals) {
    document.getElementById('payrollTotalHours').textContent = totals.total_hours.toFixed(1);
    document.getElementById('payrollRegularWages').textContent = '$' + totals.regular_wages.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('payrollOTWages').textContent = '$' + totals.ot_wages.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('payrollTips').textContent = '$' + totals.tips.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('payrollSalaries').textContent = '$' + totals.salary.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('payrollGrossPay').textContent = '$' + totals.gross_pay.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

/**
 * Export payroll as CSV
 */
async function exportPayrollCSV() {
    let url, fileName;

    if (currentViewType === 'weekly') {
        const select = document.getElementById('payrollWeekSelect');
        const weekStart = select ? select.value : null;

        if (!weekStart) {
            alert('Please select a pay period first');
            return;
        }

        url = `/api/payroll/export/csv?week_start=${weekStart}`;
        fileName = `payroll_${weekStart}.csv`;
    } else {
        const monthSelect = document.getElementById('payrollMonthSelect');
        const yearSelect = document.getElementById('payrollYearSelect');
        const month = monthSelect ? monthSelect.value : null;
        const year = yearSelect ? yearSelect.value : null;

        if (!month || !year) {
            alert('Please select a month and year first');
            return;
        }

        url = `/api/payroll/export/csv?month=${month}&year=${year}`;
        fileName = `payroll_${year}_${month}.csv`;
    }

    // Fetch CSV content and use share modal
    if (typeof shareCSV === 'function') {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch payroll data');
            const csvContent = await response.text();
            shareCSV(csvContent, fileName);
        } catch (error) {
            console.error('Error fetching payroll CSV:', error);
            // Fallback to direct download
            window.location.href = url;
        }
    } else {
        // Fallback to direct download if share.js not loaded
        window.location.href = url;
    }
}

/**
 * Print payroll report
 */
function printPayroll() {
    if (!payrollData) {
        alert('Please load payroll data first');
        return;
    }

    // Create print window
    const printWindow = window.open('', '_blank');
    const period = currentPayPeriod;

    // Build HTML for print
    let tableRows = '';
    payrollData.employees.forEach(emp => {
        tableRows += `
            <tr>
                <td>${emp.employee_name}</td>
                <td>${emp.hourly_rate > 0 ? '$' + emp.hourly_rate.toFixed(2) : '-'}</td>
                <td>${emp.total_hours > 0 ? emp.total_hours.toFixed(1) : '-'}</td>
                <td>${emp.regular_hours > 0 ? emp.regular_hours.toFixed(1) : '-'}</td>
                <td>${emp.regular_wage > 0 ? '$' + emp.regular_wage.toFixed(2) : '-'}</td>
                <td>${emp.ot_hours > 0 ? emp.ot_hours.toFixed(1) : '-'}</td>
                <td>${emp.ot_wage > 0 ? '$' + emp.ot_wage.toFixed(2) : '-'}</td>
                <td>${emp.tips > 0 ? '$' + emp.tips.toFixed(2) : '-'}</td>
                <td>${emp.salary > 0 ? '$' + emp.salary.toFixed(2) : '-'}</td>
                <td>${emp.job_classification}</td>
            </tr>
        `;
    });

    const totals = payrollData.totals;
    const printContent = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Payroll Report - ${period.start} to ${period.end}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .period { color: #666; margin-bottom: 20px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 12px; }
                th { background: #667eea; color: white; }
                tr:nth-child(even) { background: #f9f9f9; }
                tfoot td { font-weight: bold; background: #f3f4f6; }
                .summary { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
                .summary-item { background: #f3f4f6; padding: 10px 15px; border-radius: 5px; }
                .summary-label { font-size: 12px; color: #666; }
                .summary-value { font-size: 18px; font-weight: bold; }
                @media print {
                    body { margin: 0; }
                    table { font-size: 10px; }
                }
            </style>
        </head>
        <body>
            <h1>Payroll Report</h1>
            <div class="period">Pay Period: ${period.start} to ${period.end}</div>

            <div class="summary">
                <div class="summary-item">
                    <div class="summary-label">Total Hours</div>
                    <div class="summary-value">${totals.total_hours.toFixed(1)}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Regular Wages</div>
                    <div class="summary-value">$${totals.regular_wages.toFixed(2)}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">OT Wages</div>
                    <div class="summary-value">$${totals.ot_wages.toFixed(2)}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Tips</div>
                    <div class="summary-value">$${totals.tips.toFixed(2)}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Salaries</div>
                    <div class="summary-value">$${totals.salary.toFixed(2)}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Total Gross Pay</div>
                    <div class="summary-value">$${totals.gross_pay.toFixed(2)}</div>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Employee</th>
                        <th>Hourly</th>
                        <th>Total Hrs</th>
                        <th>Reg Hrs</th>
                        <th>Reg Wage</th>
                        <th>OT Hrs</th>
                        <th>OT Wage</th>
                        <th>Tips</th>
                        <th>Salary</th>
                        <th>Classification</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRows}
                </tbody>
                <tfoot>
                    <tr>
                        <td>TOTAL</td>
                        <td></td>
                        <td>${totals.total_hours.toFixed(1)}</td>
                        <td>${totals.regular_hours.toFixed(1)}</td>
                        <td>$${totals.regular_wages.toFixed(2)}</td>
                        <td>${totals.ot_hours.toFixed(1)}</td>
                        <td>$${totals.ot_wages.toFixed(2)}</td>
                        <td>$${totals.tips.toFixed(2)}</td>
                        <td>$${totals.salary.toFixed(2)}</td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>

            <script>
                window.onload = function() { window.print(); }
            </script>
        </body>
        </html>
    `;

    printWindow.document.write(printContent);
    printWindow.document.close();
}

/**
 * Add payroll-specific styles
 */
function addPayrollStyles() {
    if (document.getElementById('payroll-styles')) return;

    const styles = document.createElement('style');
    styles.id = 'payroll-styles';
    styles.textContent = `
        .classification-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .classification-management {
            background: #dbeafe;
            color: #1e40af;
        }
        .classification-front {
            background: #d1fae5;
            color: #065f46;
        }
        .classification-kitchen {
            background: #fef3c7;
            color: #92400e;
        }
        .classification-driver {
            background: #e0e7ff;
            color: #3730a3;
        }
        .classification-other {
            background: #f3f4f6;
            color: #374151;
        }
        #payrollTable {
            width: 100%;
            border-collapse: collapse;
        }
        #payrollTable th,
        #payrollTable td {
            padding: 10px 8px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        #payrollTable tbody tr:hover {
            background: #f9fafb;
        }
        #payrollTable tfoot td {
            border-top: 2px solid #667eea;
        }
    `;
    document.head.appendChild(styles);
}
