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
            case 'day':
                renderDayView();
                break;
            case 'list':
                renderListView();
                break;
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

    // Build proper calendar grid
    let html = '';

    // Header row with day names
    html += '<div class="week-header-row">';
    html += '<div class="week-time-label"></div>'; // Empty corner cell

    for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
        const day = startOfWeek.plus({ days: dayOffset });
        const isToday = day.hasSame(luxon.DateTime.now(), 'day');

        html += `
            <div class="week-day-header ${isToday ? 'today' : ''}">
                <div>${day.toFormat('EEE')}</div>
                <div class="day-number">${day.toFormat('d')}</div>
            </div>
        `;
    }
    html += '</div>';

    // Time slots (6am to 11pm in 1-hour increments)
    for (let hour = 6; hour <= 23; hour++) {
        html += `<div class="week-time-label">${formatHour(hour)}</div>`;

        // For each day of the week
        for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
            const day = startOfWeek.plus({ days: dayOffset });
            const dateStr = day.toISODate();
            const isToday = day.hasSame(luxon.DateTime.now(), 'day');

            // Get shifts for this day that overlap with this hour
            const daySchedules = weekSchedules.filter(s => {
                if (s.date !== dateStr) return false;
                const startHour = parseTime(s.start_time).hour;
                const endHour = parseTime(s.end_time).hour;
                return startHour <= hour && (endHour > hour || (endHour === hour && parseTime(s.end_time).minute > 0));
            });

            html += `<div class="week-day-cell ${isToday ? 'today' : ''}">`;

            // Render shifts in this time slot
            daySchedules.forEach(shift => {
                const startHour = parseTime(shift.start_time).hour;
                // Only render at the start hour to avoid duplicates
                if (startHour === hour) {
                    const color = getEmployeeColor(shift.employee_id);
                    const isOwnShift = shift.employee_id === window.employeeData.id;
                    const attendance = getAttendanceForShift(shift);
                    const statusClass = getShiftStatusClass(shift, attendance);

                    html += `
                        <div class="week-shift-block ${isOwnShift ? 'own-shift' : ''} ${statusClass}"
                             style="background: ${color};"
                             onclick="showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})"
                             title="${shift.employee_name}: ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}">
                            <div class="shift-employee">${shift.employee_name}</div>
                            <div class="shift-time">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</div>
                            <div class="shift-position">${shift.position || ''}</div>
                        </div>
                    `;
                }
            });

            html += '</div>';
        }
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
    console.log('Date range:', startOfCalendar.toISODate(), 'to', endOfCalendar.toISODate());

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

        html += `
            <div class="month-day-cell ${!isCurrentMonth ? 'other-month' : ''} ${isToday ? 'today' : ''}"
                 data-date="${dateStr}"
                 onclick="handleEmployeeMonthDayClick('${dateStr}', event)">
                <div class="month-day-number">${currentDay.day}</div>
                <div class="month-day-shifts">
        `;

        // Find shifts for this day
        const daySchedules = getFilteredSchedules().filter(s => s.date === dateStr);

        // Show shift indicators
        daySchedules.slice(0, 3).forEach(shift => {
            const color = getEmployeeColor(shift.employee_id);
            const isOwnShift = shift.employee_id === window.employeeData.id;

            html += `
                <div class="month-shift-indicator ${isOwnShift ? 'own-shift' : ''}"
                     style="background: ${color};"
                     onclick="event.stopPropagation(); showShiftDetail(${JSON.stringify(shift).replace(/"/g, '&quot;')})"
                     title="${shift.employee_name}: ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}">
                    <span class="shift-employee-initials">${getInitials(shift.employee_name)}</span>
                    <span class="shift-time-compact">${formatTime(shift.start_time)}</span>
                </div>
            `;
        });

        // Show "more" indicator if there are additional shifts
        if (daySchedules.length > 3) {
            html += `<div class="month-shift-more">+${daySchedules.length - 3} more</div>`;
        }

        html += `
                </div>
            </div>
        `;

        currentDay = currentDay.plus({ days: 1 });
    }

    html += '</div></div>';
    monthGrid.innerHTML = html;
    console.log('Month view rendered successfully with', getFilteredSchedules().length, 'total schedules');
}

function handleEmployeeMonthDayClick(dateStr, event) {
    // Check if we already have an expanded view open
    const existingExpanded = document.querySelector('.month-day-expanded');
    if (existingExpanded) {
        existingExpanded.remove();
    }

    const daySchedules = getFilteredSchedules().filter(s => s.date === dateStr);
    const clickedCell = event.currentTarget;
    const rect = clickedCell.getBoundingClientRect();

    if (daySchedules.length === 0) {
        // Show message that no shifts are scheduled
        showNoShiftsMessage(dateStr, rect);
    } else {
        // Expand to show all schedules for this day
        showEmployeeDaySchedulesExpanded(dateStr, daySchedules, clickedCell);
    }
}

function showNoShiftsMessage(dateStr, rect) {
    const popup = document.createElement('div');
    popup.className = 'create-event-popup';
    popup.style.position = 'fixed';
    popup.style.left = rect.left + 'px';
    popup.style.top = rect.top + 'px';
    popup.style.width = rect.width + 'px';
    popup.style.height = rect.height + 'px';

    const formattedDate = luxon.DateTime.fromISO(dateStr).toFormat('EEEE, MMM d');

    popup.innerHTML = `
        <div class="popup-content">
            <div class="popup-title">No shifts scheduled</div>
            <div class="popup-subtitle">${formattedDate}</div>
        </div>
    `;

    document.body.appendChild(popup);

    setTimeout(() => {
        popup.classList.add('show');
    }, 10);

    setTimeout(() => {
        popup.classList.remove('show');
        setTimeout(() => popup.remove(), 300);
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

    // Show selected view
    document.getElementById(`${view}View`).style.display = 'block';

    // Reset pagination for list view
    if (view === 'list') {
        listViewPage = 1;
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
    if (currentView === 'week') {
        currentDate = currentDate.minus({ weeks: 1 });
    } else if (currentView === 'month') {
        currentDate = currentDate.minus({ months: 1 });
    } else if (currentView === 'day') {
        currentDate = currentDate.minus({ days: 1 });
    }

    showLoading(true);
    await loadInitialData();
    renderCurrentView();
    showLoading(false);
}

async function navigateNext() {
    if (currentView === 'week') {
        currentDate = currentDate.plus({ weeks: 1 });
    } else if (currentView === 'month') {
        currentDate = currentDate.plus({ months: 1 });
    } else if (currentView === 'day') {
        currentDate = currentDate.plus({ days: 1 });
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

    // Show/hide request change button
    const isOwnShift = shift.employee_id === window.employeeData.id;
    const canRequest = isOwnShift && !shift.change_request_status;
    document.getElementById('requestChangeBtn').style.display = canRequest ? 'block' : 'none';

    modal.style.display = 'flex';
}

function closeShiftDetailModal() {
    document.getElementById('shiftDetailModal').style.display = 'none';
    currentShiftDetail = null;
}

function openChangeRequestModal() {
    if (!currentShiftDetail) return;

    closeShiftDetailModal();

    const modal = document.getElementById('changeRequestModal');
    document.getElementById('changeScheduleId').value = currentShiftDetail.id;

    const currentInfo = document.getElementById('currentScheduleInfo');
    currentInfo.innerHTML = `
        <strong>${formatDate(currentShiftDetail.date)}</strong> -
        ${formatTime(currentShiftDetail.start_time)} to ${formatTime(currentShiftDetail.end_time)}
    `;

    modal.style.display = 'flex';
}

function closeChangeRequestModal() {
    document.getElementById('changeRequestModal').style.display = 'none';
    document.getElementById('changeRequestForm').reset();
}

function toggleSuggestedChanges() {
    const checkbox = document.getElementById('suggestChanges');
    const section = document.getElementById('suggestedChangesSection');
    section.style.display = checkbox.checked ? 'block' : 'none';
}

async function submitChangeRequest(event) {
    event.preventDefault();

    const scheduleId = document.getElementById('changeScheduleId').value;
    const reason = document.getElementById('changeReason').value;

    const requestData = {
        reason: reason,
        requested_changes: {}
    };

    // Add suggested changes if provided
    if (document.getElementById('suggestChanges').checked) {
        const newDate = document.getElementById('newDate').value;
        const newStartTime = document.getElementById('newStartTime').value;
        const newEndTime = document.getElementById('newEndTime').value;

        if (newDate) requestData.requested_changes.new_date = newDate;
        if (newStartTime) requestData.requested_changes.new_start_time = newStartTime;
        if (newEndTime) requestData.requested_changes.new_end_time = newEndTime;
    }

    try {
        const response = await fetch(`/api/schedules/${scheduleId}/request-change`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) throw new Error('Failed to submit change request');

        showSuccess('Change request submitted successfully! You will be notified when it is reviewed.');
        closeChangeRequestModal();

        // Reload data
        await loadInitialData();
        renderCurrentView();
    } catch (error) {
        console.error('Error submitting change request:', error);
        showError('Failed to submit change request. Please try again.');
    }
}

// ==========================================
// HELPER FUNCTIONS
// ==========================================

function getCurrentDateRange() {
    let startDate, endDate;

    if (currentView === 'week') {
        startDate = currentDate.startOf('week').toISODate();
        endDate = currentDate.endOf('week').toISODate();
    } else if (currentView === 'month') {
        startDate = currentDate.startOf('month').startOf('week').toISODate();
        endDate = currentDate.endOf('month').endOf('week').toISODate();
    } else if (currentView === 'day') {
        startDate = currentDate.toISODate();
        endDate = currentDate.toISODate();
    } else {
        // List view - get current week
        startDate = currentDate.startOf('week').toISODate();
        endDate = currentDate.endOf('week').toISODate();
    }

    return { startDate, endDate };
}

function updateDateRangeDisplay() {
    const display = document.getElementById('currentDateRange');

    if (currentView === 'week') {
        const start = currentDate.startOf('week');
        const end = currentDate.endOf('week');
        display.textContent = `${start.toFormat('MMM d')} - ${end.toFormat('MMM d, yyyy')}`;
    } else if (currentView === 'month') {
        display.textContent = currentDate.toFormat('MMMM yyyy');
    } else if (currentView === 'day') {
        display.textContent = currentDate.toFormat('EEEE, MMMM d, yyyy');
    } else {
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
    document.querySelectorAll('.schedule-view').forEach(view => {
        view.style.display = isEmpty ? 'none' : (view.classList.contains('active') ? 'block' : 'none');
    });
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
    currentDate = luxon.DateTime.fromISO(dateStr);
    currentView = 'day';

    // Update active button
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.view === 'day') {
            btn.classList.add('active');
        }
    });

    // Hide all views
    document.querySelectorAll('.schedule-view').forEach(v => v.style.display = 'none');
    document.getElementById('dayView').style.display = 'block';

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
