/**
 * Employee Schedule Management
 * Handles week/day/list views, team schedule, filters, and change requests
 */

// Global state
let currentView = 'week';
let currentDate = luxon.DateTime.now();
let showTeamSchedule = false;
let schedules = [];
let teamSchedules = [];
let attendanceData = [];
let allEmployees = [];
let currentFilters = {
    position: '',
    department: '',
    name: ''
};
let currentShiftDetail = null;
let listViewPage = 1;
const listViewPerPage = 10;

// Color palette for employees
const employeeColors = [
    '#667eea', '#764ba2', '#f093fb', '#4facfe',
    '#43e97b', '#fa709a', '#fee140', '#30cfd0',
    '#a8edea', '#fed6e3', '#c471f5', '#12c2e9'
];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeSchedule();
});

async function initializeSchedule() {
    console.log('Initializing schedule page...');
    console.log('Employee data:', window.employeeData);
    console.log('Current view:', currentView);

    showLoading(true);

    try {
        await loadInitialData();
        console.log('Initial data loaded successfully');
        console.log('Schedules loaded:', schedules.length);

        renderCurrentView();
        console.log('View rendered');
    } catch (error) {
        console.error('Error during initialization:', error);
        showError('Failed to initialize schedule. Please refresh the page.');
    }

    showLoading(false);
}

// ==========================================
// DATA FETCHING
// ==========================================

async function loadInitialData() {
    try {
        const { startDate, endDate } = getCurrentDateRange();

        // Load schedules and attendance in parallel
        await Promise.all([
            loadSchedules(startDate, endDate),
            loadAttendanceOverlay(startDate, endDate),
            loadEmployeeList()
        ]);
    } catch (error) {
        console.error('Error loading initial data:', error);
        showError('Failed to load schedule data. Please try again.');
    }
}

async function loadSchedules(startDate, endDate) {
    try {
        const endpoint = showTeamSchedule
            ? `/api/schedules/employee/team?start_date=${startDate}&end_date=${endDate}`
            : `/api/schedules/employee/data?start_date=${startDate}&end_date=${endDate}`;

        console.log('Loading schedules from:', endpoint);

        const response = await fetch(endpoint);
        console.log('Response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response:', errorText);
            throw new Error('Failed to fetch schedules: ' + response.status);
        }

        const data = await response.json();
        console.log('Schedule data received:', data);

        if (showTeamSchedule) {
            teamSchedules = data.schedules || [];
            schedules = teamSchedules;
        } else {
            schedules = data.own_schedules || [];
            teamSchedules = data.team_schedules || [];
        }

        console.log('Schedules set:', schedules.length, 'items');

        return data;
    } catch (error) {
        console.error('Error loading schedules:', error);
        throw error;
    }
}

async function loadAttendanceOverlay(startDate, endDate) {
    try {
        const employeeId = showTeamSchedule ? '' : window.employeeData.id;
        const response = await fetch(
            `/api/schedules/attendance-overlay?employee_id=${employeeId}&start_date=${startDate}&end_date=${endDate}`
        );

        if (!response.ok) throw new Error('Failed to fetch attendance');

        const data = await response.json();
        attendanceData = data.attendance || [];
        return data;
    } catch (error) {
        console.error('Error loading attendance:', error);
        attendanceData = [];
    }
}

async function loadEmployeeList() {
    try {
        // Fetch all employees for filters
        const response = await fetch('/api/employees');
        if (!response.ok) throw new Error('Failed to fetch employees');

        const data = await response.json();
        allEmployees = data.employees || [];

        // Populate filter dropdowns
        populateFilters();
    } catch (error) {
        console.error('Error loading employees:', error);
    }
}

// ==========================================
// VIEW RENDERING
// ==========================================

function renderCurrentView() {
    console.log('Rendering view:', currentView);
    updateDateRangeDisplay();

    try {
        switch (currentView) {
            case 'week':
                renderWeekView();
                break;
            case 'month':
                renderMonthView();
                break;
            default:
                renderWeekView();
        }

        checkEmptyState();
        console.log('View rendered successfully');
    } catch (error) {
        console.error('Error rendering view:', error);
        showError('Failed to render schedule view');
    }
}

function renderWeekView() {
    console.log('Rendering week view...');
    const weekGrid = document.getElementById('weekGrid');
    const startOfWeek = currentDate.startOf('week');
    const endOfWeek = currentDate.endOf('week');

    if (!weekGrid) {
        console.error('Week grid element not found!');
        return;
    }

    console.log('Week starting:', startOfWeek.toISODate());
    console.log('Schedules to render:', getFilteredSchedules().length);

    // Group all week schedules by day
    const weekSchedules = getFilteredSchedules().filter(shift => {
        const shiftDate = luxon.DateTime.fromISO(shift.date);
        return shiftDate >= startOfWeek && shiftDate <= endOfWeek;
    });

    // Build vertical day cards
    let html = '';

    for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
        const day = startOfWeek.plus({ days: dayOffset });
        const dateStr = day.toISODate();
        const isToday = day.hasSame(luxon.DateTime.now(), 'day');

        // Get shifts for this day
        const daySchedules = weekSchedules.filter(s => s.date === dateStr);
        daySchedules.sort((a, b) => a.start_time.localeCompare(b.start_time));

        html += `
            <div class="ep-week-day ${isToday ? 'today' : ''}">
                <div class="ep-week-day-header">
                    <span class="ep-week-day-name">${day.toFormat('EEE')}</span>
                    <span class="ep-week-day-date">${day.toFormat('d')}</span>
                    <span class="ep-week-day-month">${day.toFormat('MMM')}</span>
                </div>
                <div class="ep-week-shifts">
        `;

        if (daySchedules.length === 0) {
            html += '<div class="ep-no-shifts">No shifts</div>';
        } else {
            daySchedules.forEach(shift => {
                const isOwnShift = shift.employee_id === window.employeeData.id;
                const attendance = getAttendanceForShift(shift);
                const statusClass = getShiftStatusClass(shift, attendance);
                const duration = calculateDuration(shift.start_time, shift.end_time);

                html += `
                    <div class="ep-shift-card ${isOwnShift ? 'own-shift' : ''} ${statusClass}"
                         onclick="showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})">
                        <div class="ep-shift-time">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</div>
                        <div class="ep-shift-duration">${duration}h</div>
                        ${showTeamSchedule ? `<div class="ep-shift-employee">${shift.employee_name}</div>` : ''}
                        <div class="ep-shift-position">${shift.position || ''}</div>
                        ${shift.change_request_status === 'pending' ? '<div class="ep-shift-badge pending">Change Pending</div>' : ''}
                    </div>
                `;
            });
        }

        html += `
                </div>
            </div>
        `;
    }

    weekGrid.innerHTML = html;
    console.log('Week view rendered successfully');
}

function renderMonthView() {
    console.log('Rendering month view for:', currentDate.toFormat('MMMM yyyy'));

    const monthGrid = document.getElementById('monthGrid');
    const monthTitle = document.getElementById('monthViewTitle');

    if (!monthGrid || !monthTitle) {
        console.error('Month view elements not found');
        return;
    }

    const startOfMonth = currentDate.startOf('month');
    const endOfMonth = currentDate.endOf('month');
    const startOfCalendar = startOfMonth.startOf('week');
    const endOfCalendar = endOfMonth.endOf('week');

    monthTitle.textContent = currentDate.toFormat('MMMM yyyy');

    // Get all schedules for this month
    const monthSchedules = getFilteredSchedules().filter(s => {
        const shiftDate = luxon.DateTime.fromISO(s.date);
        return shiftDate >= startOfMonth && shiftDate <= endOfMonth;
    });

    // Build a map of dates to shifts for quick lookup
    const shiftsByDate = {};
    monthSchedules.forEach(shift => {
        if (!shiftsByDate[shift.date]) {
            shiftsByDate[shift.date] = [];
        }
        shiftsByDate[shift.date].push(shift);
    });

    let html = '<div class="month-calendar-grid">';

    // Header row with day names
    html += '<div class="month-day-names">';
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    dayNames.forEach(day => {
        html += `<div class="month-day-name">${day}</div>`;
    });
    html += '</div>';

    // Calendar days
    html += '<div class="month-days-grid">';

    let currentDay = startOfCalendar;
    while (currentDay <= endOfCalendar) {
        const isCurrentMonth = currentDay.month === currentDate.month;
        const isToday = currentDay.hasSame(luxon.DateTime.now(), 'day');
        const dateStr = currentDay.toISODate();
        const dayShifts = shiftsByDate[dateStr] || [];
        const hasShift = dayShifts.length > 0;

        // Get color for the day
        let dayColor = '';
        let isOwnShift = false;
        let multipleEmployees = false;
        if (hasShift) {
            // Check if multiple employees have shifts
            const uniqueEmployees = [...new Set(dayShifts.map(s => s.employee_id))];
            multipleEmployees = uniqueEmployees.length > 1;

            // Prioritize own shifts for coloring
            const ownShift = dayShifts.find(s => s.employee_id === window.employeeData.id);
            if (ownShift) {
                dayColor = getEmployeeColor(ownShift.employee_id);
                isOwnShift = true;
            } else if (multipleEmployees) {
                // Use gradient for multiple employees
                const color1 = getEmployeeColor(dayShifts[0].employee_id);
                const color2 = getEmployeeColor(dayShifts[1].employee_id);
                dayColor = `linear-gradient(135deg, ${color1} 0%, ${color2} 100%)`;
            } else {
                dayColor = getEmployeeColor(dayShifts[0].employee_id);
            }
        }

        const cellStyle = hasShift && isCurrentMonth
            ? (multipleEmployees && !isOwnShift
                ? `background: ${dayColor}; color: white;`
                : `background: ${dayColor}; color: white;`)
            : '';

        html += `
            <div class="month-day-cell ${!isCurrentMonth ? 'other-month' : ''} ${isToday ? 'today' : ''} ${hasShift ? 'has-shift' : ''}"
                 data-date="${dateStr}"
                 style="${cellStyle}"
                 onclick="handleEmployeeMonthDayClick('${dateStr}', event)">
                <div class="month-day-number">${currentDay.day}</div>
            </div>
        `;

        currentDay = currentDay.plus({ days: 1 });
    }

    html += '</div></div>';

    // Add shifts list below calendar
    html += '<div class="month-shifts-list">';
    html += '<h3 class="shifts-list-title">Scheduled Shifts</h3>';

    if (monthSchedules.length === 0) {
        html += '<div class="no-shifts-message">No shifts scheduled this month</div>';
    } else {
        // Sort shifts by date
        const sortedShifts = [...monthSchedules].sort((a, b) => {
            if (a.date !== b.date) return a.date.localeCompare(b.date);
            return a.start_time.localeCompare(b.start_time);
        });

        sortedShifts.forEach(shift => {
            const shiftDate = luxon.DateTime.fromISO(shift.date);
            const color = getEmployeeColor(shift.employee_id);
            const isOwn = shift.employee_id === window.employeeData.id;
            const duration = calculateDuration(shift.start_time, shift.end_time);

            html += `
                <div class="month-shift-row ${isOwn ? 'own-shift' : ''}"
                     style="border-left-color: ${color}; ${showTeamSchedule ? 'background: ' + color + '10;' : ''}"
                     onclick="showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})">
                    <div class="shift-row-date" style="${showTeamSchedule ? 'border-right-color: ' + color + '30;' : ''}">
                        <span class="shift-row-day">${shiftDate.toFormat('EEE')}</span>
                        <span class="shift-row-date-num">${shiftDate.toFormat('d')}</span>
                    </div>
                    <div class="shift-row-details">
                        ${showTeamSchedule ? `<div class="shift-row-employee" style="color: ${color};">${shift.employee_name}</div>` : ''}
                        <div class="shift-row-time">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</div>
                        <div class="shift-row-meta">
                            <span class="shift-row-duration">${duration}h</span>
                            ${shift.position ? `<span class="shift-row-position">${shift.position}</span>` : ''}
                        </div>
                    </div>
                    <div class="shift-row-arrow">›</div>
                </div>
            `;
        });
    }

    html += '</div>';

    monthGrid.innerHTML = html;
    console.log('Month view rendered successfully with', monthSchedules.length, 'shifts');
}

function handleEmployeeMonthDayClick(dateStr, event) {
    // Check if we already have an expanded view open
    const existingExpanded = document.querySelector('.month-day-expanded');
    if (existingExpanded) {
        existingExpanded.remove();
    }

    const daySchedules = getFilteredSchedules().filter(s => s.date === dateStr);
    const clickedCell = event.currentTarget;

    // Only show expanded view if there are shifts
    if (daySchedules.length > 0) {
        showEmployeeDaySchedulesExpanded(dateStr, daySchedules, clickedCell);
    }
}

function showNoShiftsMessage(dateStr, rect) {
    const popup = document.createElement('div');
    popup.className = 'create-event-popup';

    const formattedDate = luxon.DateTime.fromISO(dateStr).toFormat('EEEE, MMM d');

    popup.innerHTML = `
        <div class="popup-content">
            <div class="popup-title">No shifts scheduled</div>
            <div class="popup-subtitle">${formattedDate}</div>
        </div>
    `;

    document.body.appendChild(popup);

    // Close when clicking outside
    popup.addEventListener('click', (e) => {
        if (e.target === popup || e.target.closest('.popup-content')) {
            popup.classList.remove('show');
            setTimeout(() => popup.remove(), 200);
        }
    });

    setTimeout(() => {
        popup.classList.add('show');
    }, 10);

    // Auto-close after 2 seconds
    setTimeout(() => {
        popup.classList.remove('show');
        setTimeout(() => popup.remove(), 200);
    }, 2000);
}

function showEmployeeDaySchedulesExpanded(dateStr, schedules, clickedCell) {
    const formattedDate = luxon.DateTime.fromISO(dateStr).toFormat('EEEE, MMMM d, yyyy');

    const expanded = document.createElement('div');
    expanded.className = 'month-day-expanded';

    let shiftsHTML = '';
    schedules.forEach(shift => {
        const color = getEmployeeColor(shift.employee_id);
        const isOwnShift = shift.employee_id === window.employeeData.id;
        const attendance = getAttendanceForShift(shift);
        const statusClass = getShiftStatusClass(shift, attendance);

        shiftsHTML += `
            <div class="expanded-shift-item ${isOwnShift ? 'own-shift' : ''} ${statusClass}"
                 style="border-left: 4px solid ${color};"
                 onclick="showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})">
                <div class="shift-item-employee">${shift.employee_name} ${isOwnShift ? '(You)' : ''}</div>
                <div class="shift-item-time">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</div>
                <div class="shift-item-type">${shift.shift_type || 'regular'}</div>
            </div>
        `;
    });

    expanded.innerHTML = `
        <div class="expanded-header">
            <strong>${formattedDate}</strong>
            <button class="btn-close-expanded" onclick="closeExpandedDay()">×</button>
        </div>
        <div class="expanded-shifts">
            ${shiftsHTML}
        </div>
        <div class="expanded-footer">
            <button class="btn-secondary" onclick="closeExpandedDay()">Close</button>
            <button class="btn-primary" onclick="navigateToDate('${dateStr}')">View Day Details</button>
        </div>
    `;

    const dayCell = clickedCell.closest('.month-day-cell');
    const daysGrid = dayCell.closest('.month-days-grid');
    daysGrid.appendChild(expanded);

    setTimeout(() => {
        expanded.classList.add('show');
    }, 10);
}

function closeExpandedDay() {
    const expanded = document.querySelector('.month-day-expanded');
    if (expanded) {
        expanded.classList.remove('show');
        setTimeout(() => expanded.remove(), 300);
    }
}

function renderDayView() {
    const dayGrid = document.getElementById('dayGrid');
    const dayTitle = document.getElementById('dayViewTitle');

    dayTitle.textContent = currentDate.toFormat('EEEE, MMMM d, yyyy');

    const dateStr = currentDate.toISODate();
    const daySchedules = getFilteredSchedules().filter(s => s.date === dateStr);

    if (daySchedules.length === 0) {
        dayGrid.innerHTML = '<div class="day-empty">No shifts scheduled for this day</div>';
        return;
    }

    // Group by employee
    const byEmployee = {};
    daySchedules.forEach(shift => {
        const empId = shift.employee_id;
        if (!byEmployee[empId]) {
            byEmployee[empId] = {
                employee: shift.employee_name,
                position: shift.position,
                shifts: []
            };
        }
        byEmployee[empId].shifts.push(shift);
    });

    let html = '<div class="day-employee-list">';

    Object.values(byEmployee).forEach(empData => {
        html += `
            <div class="day-employee-card">
                <div class="day-employee-header">
                    <h3>${empData.employee}</h3>
                    <span class="day-employee-position">${empData.position || ''}</span>
                </div>
                <div class="day-employee-shifts">
        `;

        empData.shifts.forEach(shift => {
            const attendance = getAttendanceForShift(shift);
            const statusClass = getShiftStatusClass(shift, attendance);

            html += `
                <div class="day-shift-card ${statusClass}" onclick="showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})">
                    <div class="shift-time">
                        ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}
                    </div>
                    <div class="shift-duration">
                        ${calculateDuration(shift.start_time, shift.end_time)} hours
                    </div>
                    ${shift.notes ? `<div class="shift-notes">${shift.notes}</div>` : ''}
                    ${shift.change_request_status === 'pending' ? '<div class="change-badge">⚠️ Change Requested</div>' : ''}
                    ${renderAttendanceBadge(attendance)}
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    html += '</div>';

    dayGrid.innerHTML = html;
}

function renderListView() {
    const listBody = document.getElementById('listViewBody');
    const filteredSchedules = getFilteredSchedules();

    if (filteredSchedules.length === 0) {
        listBody.innerHTML = '<tr><td colspan="9" class="list-empty">No schedules found</td></tr>';
        return;
    }

    // Sort by date and time
    const sortedSchedules = [...filteredSchedules].sort((a, b) => {
        if (a.date !== b.date) return a.date.localeCompare(b.date);
        return a.start_time.localeCompare(b.start_time);
    });

    // Paginate
    const start = (listViewPage - 1) * listViewPerPage;
    const end = start + listViewPerPage;
    const pageSchedules = sortedSchedules.slice(start, end);

    let html = '';
    pageSchedules.forEach(shift => {
        const attendance = getAttendanceForShift(shift);
        const statusClass = getShiftStatusClass(shift, attendance);
        const duration = calculateDuration(shift.start_time, shift.end_time);

        html += `
            <tr class="list-row ${statusClass}" onclick="showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})">
                <td>${formatDate(shift.date)}</td>
                <td>${shift.employee_name}</td>
                <td>${formatTime(shift.start_time)}</td>
                <td>${formatTime(shift.end_time)}</td>
                <td>${duration}h</td>
                <td>${shift.position || '-'}</td>
                <td><span class="status-badge status-${shift.status}">${shift.status}</span></td>
                <td>${renderAttendanceBadge(attendance)}</td>
                <td>
                    <button class="btn-icon" onclick="event.stopPropagation(); showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})">
                        👁️ View
                    </button>
                </td>
            </tr>
        `;
    });

    listBody.innerHTML = html;

    // Render pagination
    renderListPagination(sortedSchedules.length);
}

function renderListPagination(totalItems) {
    const pagination = document.getElementById('listPagination');
    const totalPages = Math.ceil(totalItems / listViewPerPage);

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '<div class="pagination-controls">';

    // Previous button
    html += `<button class="page-btn" ${listViewPage === 1 ? 'disabled' : ''} onclick="changePage(${listViewPage - 1})">← Previous</button>`;

    // Page numbers
    html += `<span class="page-info">Page ${listViewPage} of ${totalPages}</span>`;

    // Next button
    html += `<button class="page-btn" ${listViewPage === totalPages ? 'disabled' : ''} onclick="changePage(${listViewPage + 1})">Next →</button>`;

    html += '</div>';
    pagination.innerHTML = html;
}

function renderShiftBlock(shift, day) {
    const shiftStart = parseTime(shift.start_time);
    const shiftEnd = parseTime(shift.end_time);
    const duration = shiftEnd.diff(shiftStart, 'hours').hours;

    const attendance = getAttendanceForShift(shift);
    const statusClass = getShiftStatusClass(shift, attendance);

    const color = getEmployeeColor(shift.employee_id);
    const isOwnShift = shift.employee_id === window.employeeData.id;

    const top = (shiftStart.minute / 60) * 100;
    const height = (duration * 60 - 2) + '%'; // Slight padding

    return `
        <div class="shift-block ${statusClass} ${isOwnShift ? 'own-shift' : ''}"
             style="top: ${top}%; height: ${height}; background: ${color};"
             onclick="showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})"
             title="${shift.employee_name}: ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}">
            <div class="shift-employee">${shift.employee_name}</div>
            <div class="shift-time-range">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</div>
            ${shift.change_request_status === 'pending' ? '<div class="change-indicator">⚠️</div>' : ''}
        </div>
    `;
}

function renderAttendanceBadge(attendance) {
    if (!attendance) return '<span class="attendance-badge no-attendance">No Record</span>';

    const status = attendance.status || 'present';
    return `<span class="attendance-badge attendance-${status}">${status}</span>`;
}

// ==========================================
// VIEW SWITCHING
// ==========================================

function switchView(view) {
    // Only allow week and month views
    if (view !== 'week' && view !== 'month') {
        view = 'week';
    }

    currentView = view;

    // Update active button
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.view === view) {
            btn.classList.add('active');
        }
    });

    // Hide all views
    document.querySelectorAll('.schedule-view').forEach(v => v.style.display = 'none');

    // Show selected view with appropriate display type
    const viewElement = document.getElementById(`${view}View`);
    if (viewElement) {
        viewElement.style.display = view === 'week' ? 'flex' : 'block';
    }

    renderCurrentView();
}

async function toggleTeamView() {
    showTeamSchedule = !showTeamSchedule;

    const btn = document.getElementById('teamToggleBtn');
    const filters = document.getElementById('scheduleFilters');

    if (showTeamSchedule) {
        btn.textContent = '👤 Show My Schedule';
        btn.classList.add('active');
        filters.style.display = 'flex';
    } else {
        btn.textContent = '👥 Show Team Schedule';
        btn.classList.remove('active');
        filters.style.display = 'none';
    }

    showLoading(true);
    await loadInitialData();
    renderCurrentView();
    showLoading(false);
}

// ==========================================
// FILTERS
// ==========================================

function populateFilters() {
    const positionFilter = document.getElementById('positionFilter');
    const departmentFilter = document.getElementById('departmentFilter');
    const nameFilter = document.getElementById('nameFilter');

    // Get unique positions and departments
    const positions = [...new Set(allEmployees.map(e => e.position).filter(Boolean))].sort();
    const departments = [...new Set(allEmployees.map(e => e.department).filter(Boolean))].sort();
    const names = allEmployees.map(e => ({ id: e.id, name: e.name })).sort((a, b) => a.name.localeCompare(b.name));

    // Populate positions
    positions.forEach(position => {
        positionFilter.innerHTML += `<option value="${position}">${position}</option>`;
    });

    // Populate departments
    departments.forEach(dept => {
        departmentFilter.innerHTML += `<option value="${dept}">${dept}</option>`;
    });

    // Populate names
    names.forEach(emp => {
        nameFilter.innerHTML += `<option value="${emp.id}">${emp.name}</option>`;
    });
}

function applyFilters() {
    currentFilters.position = document.getElementById('positionFilter').value;
    currentFilters.department = document.getElementById('departmentFilter').value;
    currentFilters.name = document.getElementById('nameFilter').value;

    renderCurrentView();
}

function resetFilters() {
    currentFilters = { position: '', department: '', name: '' };
    document.getElementById('positionFilter').value = '';
    document.getElementById('departmentFilter').value = '';
    document.getElementById('nameFilter').value = '';
    renderCurrentView();
}

function getFilteredSchedules() {
    let filtered = showTeamSchedule ? teamSchedules : schedules;

    if (currentFilters.position) {
        filtered = filtered.filter(s => s.position === currentFilters.position);
    }

    if (currentFilters.department) {
        filtered = filtered.filter(s => s.department === currentFilters.department);
    }

    if (currentFilters.name) {
        filtered = filtered.filter(s => s.employee_id == currentFilters.name);
    }

    return filtered;
}

// ==========================================
// NAVIGATION
// ==========================================

async function navigatePrevious() {
    if (currentView === 'month') {
        currentDate = currentDate.minus({ months: 1 });
    } else {
        // Week view (default)
        currentDate = currentDate.minus({ weeks: 1 });
    }

    showLoading(true);
    await loadInitialData();
    renderCurrentView();
    showLoading(false);
}

async function navigateNext() {
    if (currentView === 'month') {
        currentDate = currentDate.plus({ months: 1 });
    } else {
        // Week view (default)
        currentDate = currentDate.plus({ weeks: 1 });
    }

    showLoading(true);
    await loadInitialData();
    renderCurrentView();
    showLoading(false);
}

async function navigateToday() {
    currentDate = luxon.DateTime.now();

    showLoading(true);
    await loadInitialData();
    renderCurrentView();
    showLoading(false);
}

function changePage(page) {
    listViewPage = page;
    renderListView();
}

// ==========================================
// SHIFT DETAILS & CHANGE REQUESTS
// ==========================================

function showShiftDetail(shift) {
    currentShiftDetail = shift;
    const modal = document.getElementById('shiftDetailModal');
    const body = document.getElementById('shiftDetailBody');

    const attendance = getAttendanceForShift(shift);
    const duration = calculateDuration(shift.start_time, shift.end_time);

    let html = `
        <div class="shift-detail-content">
            <div class="detail-row">
                <strong>Employee:</strong>
                <span>${shift.employee_name}</span>
            </div>
            <div class="detail-row">
                <strong>Date:</strong>
                <span>${formatDate(shift.date)}</span>
            </div>
            <div class="detail-row">
                <strong>Time:</strong>
                <span>${formatTime(shift.start_time)} - ${formatTime(shift.end_time)} (${duration}h)</span>
            </div>
            <div class="detail-row">
                <strong>Position:</strong>
                <span>${shift.position || '-'}</span>
            </div>
            <div class="detail-row">
                <strong>Shift Type:</strong>
                <span>${shift.shift_type || 'regular'}</span>
            </div>
            <div class="detail-row">
                <strong>Break Duration:</strong>
                <span>${shift.break_duration || 30} minutes</span>
            </div>
            <div class="detail-row">
                <strong>Status:</strong>
                <span class="status-badge status-${shift.status}">${shift.status}</span>
            </div>
    `;

    if (shift.notes) {
        html += `
            <div class="detail-row">
                <strong>Notes:</strong>
                <span>${shift.notes}</span>
            </div>
        `;
    }

    // Attendance overlay
    if (attendance) {
        html += `
            <div class="detail-section">
                <h4>Actual Attendance</h4>
                <div class="detail-row">
                    <strong>Clock In:</strong>
                    <span>${formatDateTime(attendance.clock_in)}</span>
                </div>
                <div class="detail-row">
                    <strong>Clock Out:</strong>
                    <span>${attendance.clock_out ? formatDateTime(attendance.clock_out) : 'Not clocked out'}</span>
                </div>
                <div class="detail-row">
                    <strong>Total Hours:</strong>
                    <span>${attendance.total_hours || 0}h</span>
                </div>
            </div>
        `;
    }

    // Change request info
    if (shift.change_request_status) {
        html += `
            <div class="detail-section change-request-section">
                <h4>Change Request</h4>
                <div class="detail-row">
                    <strong>Status:</strong>
                    <span class="status-badge status-${shift.change_request_status}">${shift.change_request_status}</span>
                </div>
                <div class="detail-row">
                    <strong>Reason:</strong>
                    <span>${shift.change_request_reason || '-'}</span>
                </div>
            </div>
        `;
    }

    html += '</div>';
    body.innerHTML = html;

    modal.style.display = 'flex';
}

function closeShiftDetailModal() {
    document.getElementById('shiftDetailModal').style.display = 'none';
    currentShiftDetail = null;
}

// ==========================================
// HELPER FUNCTIONS
// ==========================================

function getCurrentDateRange() {
    let startDate, endDate;

    if (currentView === 'month') {
        startDate = currentDate.startOf('month').startOf('week').toISODate();
        endDate = currentDate.endOf('month').endOf('week').toISODate();
    } else {
        // Week view (default)
        startDate = currentDate.startOf('week').toISODate();
        endDate = currentDate.endOf('week').toISODate();
    }

    return { startDate, endDate };
}

function updateDateRangeDisplay() {
    const display = document.getElementById('currentDateRange');

    if (currentView === 'month') {
        display.textContent = currentDate.toFormat('MMMM yyyy');
    } else {
        // Week view (default)
        const start = currentDate.startOf('week');
        const end = currentDate.endOf('week');
        display.textContent = `${start.toFormat('MMM d')} - ${end.toFormat('MMM d, yyyy')}`;
    }
}

function getAttendanceForShift(shift) {
    return attendanceData.find(a =>
        a.employee_id === shift.employee_id &&
        a.clock_in && a.clock_in.startsWith(shift.date)
    );
}

function getShiftStatusClass(shift, attendance) {
    if (shift.change_request_status === 'pending') {
        return 'change-requested';
    }

    if (!attendance) {
        return 'missed';
    }

    // Compare scheduled vs actual times
    const scheduledStart = parseTime(shift.start_time);

    // Convert SQL datetime format to ISO format
    const clockInISO = attendance.clock_in.replace(' ', 'T');
    const actualStart = luxon.DateTime.fromISO(clockInISO);

    const diffMinutes = Math.abs(actualStart.diff(scheduledStart, 'minutes').minutes);

    if (diffMinutes <= 5) {
        return 'on-time';
    } else {
        return 'late';
    }
}

function getEmployeeColor(employeeId) {
    const index = employeeId % employeeColors.length;
    return employeeColors[index];
}

function parseTime(timeStr) {
    if (!timeStr) {
        console.error('parseTime received null/undefined timeStr');
        return luxon.DateTime.now();
    }

    // Handle both HH:MM and HH:MM:SS formats
    const parts = timeStr.split(':').map(Number);
    const hours = parts[0] || 0;
    const minutes = parts[1] || 0;
    const seconds = parts[2] || 0;

    return luxon.DateTime.now().set({ hour: hours, minute: minutes, second: seconds });
}

function formatTime(timeStr) {
    const time = parseTime(timeStr);
    return time.toFormat('h:mm a');
}

function formatDate(dateStr) {
    if (!dateStr) return '—';

    // Handle both date-only and datetime strings
    const isoString = dateStr.replace(' ', 'T');
    const dt = luxon.DateTime.fromISO(isoString);

    if (!dt.isValid) {
        console.error('Invalid date string:', dateStr);
        return 'Invalid Date';
    }

    return dt.toFormat('MMM d, yyyy');
}

function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return '—';

    // Convert SQL datetime format to ISO format
    // "2026-01-25 13:53:00" -> "2026-01-25T13:53:00"
    const isoString = dateTimeStr.replace(' ', 'T');
    const dt = luxon.DateTime.fromISO(isoString);

    // Check if date is valid
    if (!dt.isValid) {
        console.error('Invalid datetime string:', dateTimeStr, 'Error:', dt.invalidReason);
        return 'Invalid Date';
    }

    return dt.toFormat('MMM d, yyyy h:mm a');
}

function formatHour(hour) {
    const time = luxon.DateTime.now().set({ hour: hour });
    return time.toFormat('h a');
}

function calculateDuration(startTime, endTime) {
    const start = parseTime(startTime);
    const end = parseTime(endTime);
    return end.diff(start, 'hours').hours;
}

function checkEmptyState() {
    const isEmpty = getFilteredSchedules().length === 0;
    document.getElementById('scheduleEmpty').style.display = isEmpty ? 'block' : 'none';

    // Handle view display based on empty state
    const weekView = document.getElementById('weekView');
    const monthView = document.getElementById('monthView');

    if (isEmpty) {
        if (weekView) weekView.style.display = 'none';
        if (monthView) monthView.style.display = 'none';
    } else {
        // Show the active view with appropriate display type
        if (weekView) {
            weekView.style.display = currentView === 'week' ? 'flex' : 'none';
        }
        if (monthView) {
            monthView.style.display = currentView === 'month' ? 'block' : 'none';
        }
    }
}

function showLoading(show) {
    document.getElementById('scheduleLoading').style.display = show ? 'flex' : 'none';
}

function getInitials(name) {
    if (!name) return '?';
    const parts = name.split(' ');
    if (parts.length >= 2) {
        return parts[0][0] + parts[parts.length - 1][0];
    }
    return name.substring(0, 2).toUpperCase();
}

async function navigateToDate(dateStr) {
    // Navigate to week view containing this date
    currentDate = luxon.DateTime.fromISO(dateStr);
    currentView = 'week';

    // Update active button
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.view === 'week') {
            btn.classList.add('active');
        }
    });

    // Hide all views
    document.querySelectorAll('.schedule-view').forEach(v => v.style.display = 'none');
    document.getElementById('weekView').style.display = 'flex';

    // Close the expanded day popup
    closeExpandedDay();

    showLoading(true);
    await loadInitialData();
    renderCurrentView();
    showLoading(false);
}

function showError(message) {
    alert('Error: ' + message);
}

function showSuccess(message) {
    alert(message);
}
