// Labor Analytics JavaScript

let laborCostChart = null;
let currentLaborPeriod = '8weeks';
let laborAnalyticsData = null;
let laborCustomStartDate = null;
let laborCustomEndDate = null;

// Initialize labor analytics when tab is shown
function initLaborAnalytics() {
    console.log('Initializing labor analytics...');
    loadLaborAnalytics();
}

// Change labor analytics time period
function changeLaborPeriod(period) {
    currentLaborPeriod = period;

    // Hide custom date range if not custom
    const customRange = document.getElementById('labor-custom-date-range');
    if (customRange) {
        customRange.style.display = period === 'custom' ? 'flex' : 'none';
    }

    // Update button states
    document.querySelectorAll('.labor-period-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.period === period) {
            btn.classList.add('active');
        }
    });

    // Update period display
    const periodLabels = {
        '4weeks': 'Last 4 Weeks',
        '8weeks': 'Last 8 Weeks',
        '12weeks': 'Last 12 Weeks',
        '6months': 'Last 6 Months',
        'year': 'Last Year',
        'all': 'All Time',
        'custom': 'Custom Range'
    };
    document.getElementById('labor-period-display').textContent = periodLabels[period] || period;

    if (period !== 'custom') {
        loadLaborAnalytics();
    }
}

// Show custom date range inputs
function showLaborCustomDateRange() {
    changeLaborPeriod('custom');
}

// Apply custom date range
function applyLaborCustomDateRange() {
    const startInput = document.getElementById('labor-start-date');
    const endInput = document.getElementById('labor-end-date');

    if (!startInput.value || !endInput.value) {
        alert('Please select both start and end dates');
        return;
    }

    laborCustomStartDate = startInput.value;
    laborCustomEndDate = endInput.value;

    document.getElementById('labor-period-display').textContent =
        `${new Date(laborCustomStartDate).toLocaleDateString()} - ${new Date(laborCustomEndDate).toLocaleDateString()}`;

    loadLaborAnalytics();
}

// Get date range based on current period
// latestDate parameter allows using actual data's latest date instead of system date
function getLaborDateRange(latestDate = null) {
    // Use the latest date from actual data, or far future to capture all records
    const endDate = latestDate ? new Date(latestDate) : new Date('2030-12-31');
    endDate.setHours(23, 59, 59, 999);

    let startDate = new Date(endDate);
    startDate.setHours(0, 0, 0, 0);

    if (currentLaborPeriod === 'custom' && laborCustomStartDate && laborCustomEndDate) {
        const customEnd = new Date(laborCustomEndDate);
        customEnd.setHours(23, 59, 59, 999);
        return {
            start: new Date(laborCustomStartDate),
            end: customEnd
        };
    }

    switch (currentLaborPeriod) {
        case '4weeks':
            startDate.setDate(startDate.getDate() - 28);
            break;
        case '8weeks':
            startDate.setDate(startDate.getDate() - 56);
            break;
        case '12weeks':
            startDate.setDate(startDate.getDate() - 84);
            break;
        case '6months':
            startDate.setMonth(startDate.getMonth() - 6);
            break;
        case 'year':
            startDate.setFullYear(startDate.getFullYear() - 1);
            break;
        case 'all':
            startDate = new Date('2020-01-01');
            break;
        default:
            startDate.setDate(startDate.getDate() - 56); // Default 8 weeks
    }

    console.log('Date range:', startDate.toISOString(), 'to', endDate.toISOString());
    return { start: startDate, end: endDate };
}

// Load labor analytics data
async function loadLaborAnalytics() {
    console.log('Loading labor analytics for period:', currentLaborPeriod);

    // Show loading state
    const chartContainer = document.getElementById('labor-hours-by-employee');
    if (chartContainer) {
        chartContainer.innerHTML = '<div class="loading">Loading...</div>';
    }

    try {
        // Fetch all employees
        const empRes = await fetch('/api/employees');
        const empData = await empRes.json();
        const employees = empData.employees || [];

        // Fetch attendance history
        const attRes = await fetch('/api/attendance/history');
        const attData = await attRes.json();
        const attendance = attData.attendance || [];

        console.log('Total attendance records:', attendance.length);

        // Find the latest date in the actual data to use as reference point
        let latestDataDate = null;
        if (attendance.length > 0) {
            const allDates = attendance
                .filter(r => r.clock_in)
                .map(r => new Date(r.clock_in.replace(' ', 'T')))
                .sort((a, b) => b - a); // Sort descending

            if (allDates.length > 0) {
                latestDataDate = allDates[0];
                const earliestDate = allDates[allDates.length - 1];
                console.log('Data date range:', earliestDate.toLocaleDateString(), 'to', latestDataDate.toLocaleDateString());
            }
        }

        // Get date range using the latest data date as reference
        const dateRange = getLaborDateRange(latestDataDate);
        console.log('Filter range:', dateRange.start.toLocaleDateString(), '-', dateRange.end.toLocaleDateString());

        // Filter attendance to date range
        const filteredAttendance = attendance.filter(record => {
            if (!record.clock_in) return false;
            // Parse the date - handle various formats
            let clockIn;
            if (typeof record.clock_in === 'string') {
                // Handle ISO format or YYYY-MM-DD HH:MM:SS format
                clockIn = new Date(record.clock_in.replace(' ', 'T'));
            } else {
                clockIn = new Date(record.clock_in);
            }

            // Compare using timestamps for reliability
            const clockInTime = clockIn.getTime();
            const startTime = dateRange.start.getTime();
            const endTime = dateRange.end.getTime();

            return clockInTime >= startTime && clockInTime <= endTime;
        });

        console.log('Filtered attendance records:', filteredAttendance.length);

        // Create employee lookup with wage info
        const employeeLookup = {};
        employees.forEach(emp => {
            employeeLookup[emp.id] = {
                name: `${emp.first_name} ${emp.last_name}`,
                hourly_rate: parseFloat(emp.hourly_rate) || 0,
                salary: parseFloat(emp.salary) || 0,
                color: emp.color || '#667eea'
            };
        });

        // Group attendance by week
        const weeklyData = {};

        filteredAttendance.forEach(record => {
            const clockIn = new Date(record.clock_in.replace(' ', 'T'));
            const weekStart = getWeekStart(clockIn);
            const weekKey = weekStart.toISOString().split('T')[0];

            if (!weeklyData[weekKey]) {
                weeklyData[weekKey] = {
                    weekStart: weekKey,
                    totalHours: 0,
                    regularHours: 0,
                    overtimeHours: 0,
                    regularWages: 0,
                    overtimeWages: 0,
                    tips: 0,
                    employees: new Set()
                };
            }

            const hours = parseFloat(record.total_hours) || 0;
            const emp = employeeLookup[record.employee_id];
            const hourlyRate = emp ? emp.hourly_rate : 0;

            weeklyData[weekKey].totalHours += hours;
            weeklyData[weekKey].employees.add(record.employee_id);

            // Calculate regular vs overtime (over 40 hrs/week simplified)
            weeklyData[weekKey].regularHours += Math.min(hours, 8);
            weeklyData[weekKey].overtimeHours += Math.max(0, hours - 8);

            weeklyData[weekKey].regularWages += Math.min(hours, 8) * hourlyRate;
            weeklyData[weekKey].overtimeWages += Math.max(0, hours - 8) * hourlyRate * 1.5;

            // Tips
            weeklyData[weekKey].tips += parseFloat(record.tips) || 0;
        });

        // Fill in all weeks in the date range (even ones with no data)
        const allWeeks = {};
        let currentWeek = getWeekStart(dateRange.start);
        const endWeek = getWeekStart(dateRange.end);

        while (currentWeek <= endWeek) {
            const weekKey = currentWeek.toISOString().split('T')[0];
            if (weeklyData[weekKey]) {
                allWeeks[weekKey] = weeklyData[weekKey];
            } else {
                // Create empty week
                allWeeks[weekKey] = {
                    weekStart: weekKey,
                    totalHours: 0,
                    regularHours: 0,
                    overtimeHours: 0,
                    regularWages: 0,
                    overtimeWages: 0,
                    tips: 0,
                    employees: new Set()
                };
            }
            // Move to next week
            currentWeek = new Date(currentWeek);
            currentWeek.setDate(currentWeek.getDate() + 7);
        }

        // Convert to array and sort
        const weeksArray = Object.values(allWeeks)
            .map(w => ({
                ...w,
                label: formatWeekLabel(w.weekStart),
                employeeCount: w.employees.size,
                totalCost: w.regularWages + w.overtimeWages + w.tips,
                salaries: 0 // Would need salary calculation logic
            }))
            .sort((a, b) => new Date(a.weekStart) - new Date(b.weekStart));

        laborAnalyticsData = weeksArray;

        console.log('Loaded', weeksArray.length, 'weeks of data');

        // Update displays
        updateLaborSummary(weeksArray, employees);
        updateLaborChart(weeksArray);
        updateLaborBreakdown(weeksArray);
        updateHoursByEmployee(filteredAttendance, employeeLookup);

    } catch (err) {
        console.error('Error loading labor analytics:', err);
        const chartContainer = document.getElementById('labor-hours-by-employee');
        if (chartContainer) {
            chartContainer.innerHTML = '<div style="text-align: center; color: #ef4444; padding: 20px;">Error loading data</div>';
        }
    }
}

// Get the Monday of the week for a date
function getWeekStart(date) {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setDate(diff);
    d.setHours(0, 0, 0, 0);
    return d;
}

// Format week label
function formatWeekLabel(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Update summary KPIs
function updateLaborSummary(data, employees) {
    const totalCost = data.reduce((sum, w) => sum + w.totalCost, 0);
    const totalHours = data.reduce((sum, w) => sum + w.totalHours, 0);
    const avgWeekly = data.length > 0 ? totalCost / data.length : 0;
    const activeEmployees = employees ? employees.filter(e => e.status === 'active').length : 0;

    document.getElementById('labor-total-cost').textContent = '$' + totalCost.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    document.getElementById('labor-total-hours').textContent = totalHours.toFixed(1);
    document.getElementById('labor-avg-weekly').textContent = '$' + avgWeekly.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    document.getElementById('labor-active-employees').textContent = activeEmployees;
}

// Update the labor cost chart
function updateLaborChart(data) {
    const ctx = document.getElementById('laborCostCanvas');
    if (!ctx) {
        console.error('Labor cost canvas not found');
        return;
    }

    // Destroy existing chart
    if (laborCostChart) {
        laborCostChart.destroy();
    }

    if (data.length === 0) {
        ctx.parentElement.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 300px; color: #9ca3af;">No data available for this period</div>';
        return;
    }

    const labels = data.map(w => w.label);
    const costs = data.map(w => w.totalCost);
    const hours = data.map(w => w.totalHours);

    // Adjust bar thickness and styling based on number of data points
    const numWeeks = data.length;
    const barThickness = numWeeks > 20 ? 'flex' : (numWeeks > 12 ? 20 : 40);
    const barPercentage = numWeeks > 20 ? 0.9 : (numWeeks > 12 ? 0.8 : 0.7);
    const borderRadius = numWeeks > 20 ? 3 : 6;
    const pointRadius = numWeeks > 20 ? 2 : (numWeeks > 12 ? 3 : 4);
    const lineWidth = numWeeks > 20 ? 2 : 3;

    laborCostChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Labor Cost ($)',
                    data: costs,
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1,
                    borderRadius: borderRadius,
                    barThickness: barThickness,
                    barPercentage: barPercentage,
                    yAxisID: 'y'
                },
                {
                    label: 'Hours Worked',
                    data: hours,
                    type: 'line',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: lineWidth,
                    pointRadius: pointRadius,
                    pointBackgroundColor: 'rgba(16, 185, 129, 1)',
                    fill: true,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.dataset.label.includes('$')) {
                                return context.dataset.label + ': $' + context.raw.toLocaleString();
                            }
                            return context.dataset.label + ': ' + context.raw.toFixed(1);
                        }
                    }
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Labor Cost ($)'
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Hours'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

// Update cost breakdown
function updateLaborBreakdown(data) {
    const regular = data.reduce((sum, w) => sum + w.regularWages, 0);
    const overtime = data.reduce((sum, w) => sum + w.overtimeWages, 0);
    const tips = data.reduce((sum, w) => sum + w.tips, 0);
    const salaries = data.reduce((sum, w) => sum + w.salaries, 0);
    const total = regular + overtime + tips + salaries;

    document.getElementById('labor-breakdown-regular').textContent = '$' + regular.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    document.getElementById('labor-breakdown-overtime').textContent = '$' + overtime.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    document.getElementById('labor-breakdown-tips').textContent = '$' + tips.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    document.getElementById('labor-breakdown-salaries').textContent = '$' + salaries.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    document.getElementById('labor-breakdown-total').textContent = '$' + total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Update hours by employee
function updateHoursByEmployee(attendance, employeeLookup) {
    const container = document.getElementById('labor-hours-by-employee');
    if (!container) return;

    // Calculate hours per employee
    const employeeHours = {};

    attendance.forEach(record => {
        const empId = record.employee_id;
        if (!employeeHours[empId]) {
            employeeHours[empId] = 0;
        }
        employeeHours[empId] += parseFloat(record.total_hours) || 0;
    });

    // Build employee list with hours
    const employeeList = Object.entries(employeeHours)
        .map(([empId, hours]) => {
            const emp = employeeLookup[empId] || { name: 'Unknown', color: '#667eea' };
            return {
                name: emp.name,
                hours: hours,
                color: emp.color
            };
        })
        .filter(emp => emp.hours > 0)
        .sort((a, b) => b.hours - a.hours);

    if (employeeList.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: #9ca3af; padding: 20px;">No hours recorded in this period</div>';
        return;
    }

    const maxHours = Math.max(...employeeList.map(e => e.hours));

    container.innerHTML = employeeList.map(emp => {
        const percentage = (emp.hours / maxHours) * 100;
        return `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="font-weight: 600;">${emp.name}</span>
                    <span style="color: #667eea; font-weight: 600;">${emp.hours.toFixed(1)} hrs</span>
                </div>
                <div style="background: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden;">
                    <div style="background: ${emp.color}; height: 100%; width: ${percentage}%; border-radius: 4px; transition: width 0.3s;"></div>
                </div>
            </div>
        `;
    }).join('');
}

// Export labor analytics
function exportLaborAnalytics() {
    if (!laborAnalyticsData || laborAnalyticsData.length === 0) {
        alert('No data to export');
        return;
    }

    const headers = ['Week Starting', 'Total Cost', 'Total Hours', 'Regular Wages', 'Overtime Wages', 'Tips', 'Salaries', 'Employees'];
    const rows = laborAnalyticsData.map(w => [
        w.weekStart,
        w.totalCost.toFixed(2),
        w.totalHours.toFixed(2),
        w.regularWages.toFixed(2),
        w.overtimeWages.toFixed(2),
        w.tips.toFixed(2),
        w.salaries.toFixed(2),
        w.employeeCount
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `labor_analytics_${currentLaborPeriod}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
