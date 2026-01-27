/**
 * Admin Schedule Management
 * Handles schedule creation, editing, deletion, and change request approval
 */

// Global state
let adminCurrentView = 'week';
let adminCurrentDate = luxon.DateTime.now();
let adminSchedules = [];
let adminEmployees = [];
let adminChangeRequests = [];
let adminFilters = {
    employee: '',
    position: '',
    status: ''
};
let expandedDayDate = null; // Track which day is expanded (null = week view)

// Color palette for employees
const employeeColors = [
    '#667eea', '#764ba2', '#f093fb', '#4facfe',
    '#43e97b', '#fa709a', '#fee140', '#30cfd0',
    '#a8edea', '#fed6e3', '#c471f5', '#12c2e9'
];

// Initialize admin schedules when tab is shown
function initAdminSchedules() {
    console.log('=== INITIALIZING ADMIN SCHEDULES ===');
    console.log('Initial filters:', adminFilters);

    // Ensure filters are reset on init
    adminFilters = {
        employee: '',
        position: '',
        status: ''
    };

    loadAdminData();
}

// ==========================================
// DATA LOADING
// ==========================================

async function loadAdminData() {
    try {
        showAdminLoading(true);

        const { startDate, endDate } = getAdminDateRange();

        await Promise.all([
            loadAdminSchedules(startDate, endDate),
            loadAdminEmployees(),
            loadChangeRequests()
        ]);

        renderAdminScheduleView();
        updateAdminDateDisplay();
        showAdminLoading(false);
    } catch (error) {
        console.error('Error loading admin data:', error);
        showAdminError('Failed to load schedule data');
        showAdminLoading(false);
    }
}

async function loadAdminSchedules(startDate, endDate) {
    try {
        const params = new URLSearchParams({
            start_date: startDate,
            end_date: endDate
        });

        if (adminFilters.employee) params.append('employee_id', adminFilters.employee);
        if (adminFilters.position) params.append('position', adminFilters.position);
        if (adminFilters.status) params.append('status', adminFilters.status);

        console.log('=== LOADING ADMIN SCHEDULES ===');
        console.log('Date range:', startDate, 'to', endDate);
        console.log('Filters:', adminFilters);
        console.log('API URL:', `/api/schedules?${params.toString()}`);

        const response = await fetch(`/api/schedules?${params.toString()}`);
        if (!response.ok) throw new Error('Failed to fetch schedules');

        const data = await response.json();
        adminSchedules = data.schedules || [];
        console.log(`Loaded ${adminSchedules.length} schedules`);
        console.log('Schedule IDs:', adminSchedules.map(s => `ID:${s.id} Date:${s.date} Emp:${s.employee_id}`));
        return data;
    } catch (error) {
        console.error('Error loading admin schedules:', error);
        adminSchedules = []; // Reset to empty on error
        throw error;
    }
}

async function loadAdminEmployees() {
    try {
        const response = await fetch('/api/employees');
        if (!response.ok) throw new Error('Failed to fetch employees');

        const data = await response.json();
        adminEmployees = data.employees || [];

        populateAdminFilters();
        return data;
    } catch (error) {
        console.error('Error loading employees:', error);
        throw error;
    }
}

async function loadChangeRequests() {
    try {
        const response = await fetch('/api/schedules?change_request_status=pending');
        if (!response.ok) throw new Error('Failed to fetch change requests');

        const data = await response.json();
        adminChangeRequests = data.schedules || [];

        renderChangeRequests();
        return data;
    } catch (error) {
        console.error('Error loading change requests:', error);
        adminChangeRequests = [];
    }
}

// ==========================================
// VIEW RENDERING
// ==========================================

function renderAdminScheduleView() {
    console.log(`Rendering admin ${adminCurrentView} view with ${adminSchedules.length} schedules`);
    if (adminCurrentView === 'week') {
        if (expandedDayDate) {
            renderExpandedDayView();
        } else {
            renderAdminWeekView();
        }
    } else if (adminCurrentView === 'month') {
        renderAdminMonthView();
    }
}

function renderAdminWeekView() {
    const weekGrid = document.getElementById('adminWeekGrid');
    if (!weekGrid) {
        console.error('adminWeekGrid element not found!');
        return;
    }

    const startOfWeek = adminCurrentDate.startOf('week');
    const endOfWeek = adminCurrentDate.endOf('week');
    console.log('=== RENDERING ADMIN WEEK VIEW ===');
    console.log('Week range:', startOfWeek.toISODate(), 'to', endOfWeek.toISODate());
    console.log('Total adminSchedules:', adminSchedules.length);
    console.log('Current filters:', adminFilters);

    // Filter schedules for this week
    const weekSchedules = adminSchedules.filter(shift => {
        const shiftDate = luxon.DateTime.fromISO(shift.date);
        return shiftDate >= startOfWeek && shiftDate <= endOfWeek;
    });

    // Determine time range to display based on shifts
    let earliestHour = 24, latestHour = 0;
    weekSchedules.forEach(shift => {
        const startHour = parseTime(shift.start_time).hour;
        const endTime = parseTime(shift.end_time);
        const endHour = endTime.hour + (endTime.minute > 0 ? 1 : 0);
        earliestHour = Math.min(earliestHour, startHour);
        latestHour = Math.max(latestHour, endHour);
    });

    // Default to 6am-10pm if no shifts
    if (earliestHour > latestHour) {
        earliestHour = 6;
        latestHour = 22;
    }
    // Add padding and ensure reasonable bounds
    earliestHour = Math.max(0, earliestHour - 1);
    latestHour = Math.min(24, latestHour + 1);

    // Header showing week range and active filter
    let filterText = '';
    if (adminFilters.employee) {
        const emp = adminEmployees.find(e => e.id === parseInt(adminFilters.employee));
        const empName = emp ? (emp.employee_name || `${emp.first_name} ${emp.last_name}`) : 'Unknown';
        filterText = ` - ${empName}`;
    } else if (adminFilters.position) {
        filterText = ` - ${adminFilters.position}`;
    } else if (adminFilters.status) {
        filterText = ` - ${adminFilters.status}`;
    }

    let html = '<div class="time-grid-week-view">';

    // Header with week range and add button
    html += `
        <div class="time-grid-header">
            <div class="time-grid-header-left">
                <h3>${startOfWeek.toFormat('MMM d')} - ${endOfWeek.toFormat('MMM d, yyyy')}${filterText}</h3>
                <span class="time-grid-hint">Double-click a day to expand</span>
            </div>
            <button class="btn-primary" onclick="openCreateScheduleModal()">+ Add Shift</button>
        </div>
    `;

    // Check if there are any schedules to display
    if (weekSchedules.length === 0) {
        html += `
            <div class="schedule-empty-state">
                <div class="empty-icon">📭</div>
                <h3>No Schedules Found</h3>
                <p>There are no schedules for this week${filterText ? ' with the selected filters' : ''}.</p>
                <button class="btn-primary" onclick="openCreateScheduleModal()">Create First Shift</button>
            </div>
        `;
        html += '</div>';
        weekGrid.innerHTML = html;
        return;
    }

    // Day headers row
    html += '<div class="time-grid-day-headers">';
    html += '<div class="time-grid-time-label-header"></div>'; // Empty corner cell
    for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
        const day = startOfWeek.plus({ days: dayOffset });
        const dateStr = day.toISODate();
        const isToday = day.hasSame(luxon.DateTime.now(), 'day');
        html += `
            <div class="time-grid-day-header ${isToday ? 'today' : ''}" ondblclick="expandDay('${dateStr}')" style="cursor: pointer;">
                <span class="day-name">${day.toFormat('EEE')}</span>
                <span class="day-number ${isToday ? 'today-number' : ''}">${day.day}</span>
            </div>
        `;
    }
    html += '</div>';

    // Time grid body
    html += '<div class="time-grid-body">';

    // Time labels column
    html += '<div class="time-grid-time-labels">';
    for (let hour = earliestHour; hour <= latestHour; hour++) {
        html += `<div class="time-grid-time-label">${formatHour(hour)}</div>`;
    }
    html += '</div>';

    // Days columns container
    html += '<div class="time-grid-days-container">';

    const hourHeight = 60; // pixels per hour
    const totalHours = latestHour - earliestHour;

    for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
        const day = startOfWeek.plus({ days: dayOffset });
        const dateStr = day.toISODate();
        const isToday = day.hasSame(luxon.DateTime.now(), 'day');
        const daySchedules = weekSchedules.filter(s => s.date === dateStr);

        const formattedDayLabel = day.toFormat('EEE, MMM d');
        html += `<div class="time-grid-day-column ${isToday ? 'today' : ''}" data-date="${dateStr}" data-label="${formattedDayLabel}" ondblclick="expandDay('${dateStr}')">`;

        // Hour lines
        for (let hour = earliestHour; hour <= latestHour; hour++) {
            html += `<div class="time-grid-hour-line" style="top: ${(hour - earliestHour) * hourHeight}px;" onclick="openCreateScheduleForDateTime('${dateStr}', ${hour})" ondblclick="event.stopPropagation(); expandDay('${dateStr}')"></div>`;
        }

        // Render shifts as full-height blocks
        // Group overlapping shifts for side-by-side display
        const shiftGroups = groupOverlappingShifts(daySchedules);

        shiftGroups.forEach(group => {
            const groupWidth = 100 / group.length;
            group.forEach((shift, idx) => {
                const startTime = parseTime(shift.start_time);
                const endTime = parseTime(shift.end_time);
                const startMinutes = startTime.hour * 60 + startTime.minute;
                const endMinutes = endTime.hour * 60 + endTime.minute;
                const durationMinutes = endMinutes - startMinutes;

                const top = ((startTime.hour - earliestHour) * 60 + startTime.minute) / 60 * hourHeight;
                const height = (durationMinutes / 60) * hourHeight - 2; // -2 for margin
                const left = idx * groupWidth;
                const width = groupWidth - 1; // Small gap between overlapping shifts

                const color = getEmployeeColor(shift.employee_id);
                const hasChangeRequest = shift.change_request_status === 'pending';

                html += `
                    <div class="time-grid-shift-block ${hasChangeRequest ? 'has-change-request' : ''}"
                         style="top: ${top}px; height: ${height}px; left: ${left}%; width: ${width}%; background: ${color};"
                         onclick="event.stopPropagation(); editSchedule(${shift.id})"
                         ondblclick="event.stopPropagation(); expandDay('${dateStr}')"
                         title="${shift.employee_name}: ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}">
                        <div class="shift-block-content">
                            <span class="shift-block-name">${shift.employee_name}</span>
                            <span class="shift-block-time">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</span>
                        </div>
                        ${hasChangeRequest ? '<div class="change-request-badge">!</div>' : ''}
                    </div>
                `;
            });
        });

        html += '</div>';
    }

    html += '</div>'; // days container
    html += '</div>'; // body
    html += '</div>'; // time-grid-week-view

    weekGrid.innerHTML = html;
    console.log('Admin week view rendered successfully');
}

// Helper function to group overlapping shifts for side-by-side display
function groupOverlappingShifts(shifts) {
    if (shifts.length === 0) return [];

    // Sort by start time
    const sorted = [...shifts].sort((a, b) => {
        const aStart = parseTime(a.start_time);
        const bStart = parseTime(b.start_time);
        return (aStart.hour * 60 + aStart.minute) - (bStart.hour * 60 + bStart.minute);
    });

    const groups = [];
    let currentGroup = [sorted[0]];
    let currentGroupEnd = parseTime(sorted[0].end_time);

    for (let i = 1; i < sorted.length; i++) {
        const shift = sorted[i];
        const shiftStart = parseTime(shift.start_time);
        const shiftEnd = parseTime(shift.end_time);

        // Check if this shift overlaps with current group
        if (shiftStart.hour * 60 + shiftStart.minute < currentGroupEnd.hour * 60 + currentGroupEnd.minute) {
            currentGroup.push(shift);
            // Extend group end if needed
            if (shiftEnd.hour * 60 + shiftEnd.minute > currentGroupEnd.hour * 60 + currentGroupEnd.minute) {
                currentGroupEnd = shiftEnd;
            }
        } else {
            // No overlap, start new group
            groups.push(currentGroup);
            currentGroup = [shift];
            currentGroupEnd = shiftEnd;
        }
    }
    groups.push(currentGroup);

    return groups;
}

// ==========================================
// EXPANDED DAY VIEW
// ==========================================

function expandDay(dateStr) {
    console.log('Expanding day:', dateStr);
    expandedDayDate = dateStr;
    renderAdminScheduleView();
}

function collapseToWeekView() {
    console.log('Collapsing to week view');
    expandedDayDate = null;
    renderAdminScheduleView();
}

function navigateExpandedDay(direction) {
    if (!expandedDayDate) return;

    const currentDay = luxon.DateTime.fromISO(expandedDayDate);
    const newDay = direction === 'prev'
        ? currentDay.minus({ days: 1 })
        : currentDay.plus({ days: 1 });

    expandedDayDate = newDay.toISODate();

    // Update adminCurrentDate to keep week in sync
    adminCurrentDate = newDay;

    // Reload data if we moved to a different week
    const startOfWeek = newDay.startOf('week');
    const endOfWeek = newDay.endOf('week');
    const needsReload = !adminSchedules.some(s => {
        const shiftDate = luxon.DateTime.fromISO(s.date);
        return shiftDate >= startOfWeek && shiftDate <= endOfWeek;
    });

    if (needsReload) {
        loadAdminData();
    } else {
        renderAdminScheduleView();
    }
}

function renderExpandedDayView() {
    const weekGrid = document.getElementById('adminWeekGrid');
    if (!weekGrid || !expandedDayDate) {
        return;
    }

    const day = luxon.DateTime.fromISO(expandedDayDate);
    const isToday = day.hasSame(luxon.DateTime.now(), 'day');
    const dateStr = expandedDayDate;

    // Get schedules for this day
    const daySchedules = adminSchedules.filter(s => s.date === dateStr);

    // Determine time range
    let earliestHour = 24, latestHour = 0;
    daySchedules.forEach(shift => {
        const startHour = parseTime(shift.start_time).hour;
        const endTime = parseTime(shift.end_time);
        const endHour = endTime.hour + (endTime.minute > 0 ? 1 : 0);
        earliestHour = Math.min(earliestHour, startHour);
        latestHour = Math.max(latestHour, endHour);
    });

    if (earliestHour > latestHour) {
        earliestHour = 6;
        latestHour = 22;
    }
    earliestHour = Math.max(0, earliestHour - 1);
    latestHour = Math.min(24, latestHour + 1);

    const hourHeight = 60;

    let html = '<div class="expanded-day-view" ondblclick="collapseToWeekView()">';

    // Header with navigation
    html += `
        <div class="expanded-day-header">
            <button class="btn-nav" onclick="event.stopPropagation(); navigateExpandedDay('prev')">
                <span class="nav-arrow">←</span>
                <span class="nav-text">${day.minus({ days: 1 }).toFormat('EEE')}</span>
            </button>
            <div class="expanded-day-title">
                <h2>${day.toFormat('EEEE, MMMM d, yyyy')}</h2>
                <span class="expanded-day-hint">Double-click anywhere to return to week view</span>
            </div>
            <button class="btn-nav" onclick="event.stopPropagation(); navigateExpandedDay('next')">
                <span class="nav-text">${day.plus({ days: 1 }).toFormat('EEE')}</span>
                <span class="nav-arrow">→</span>
            </button>
        </div>
    `;

    // Action bar
    html += `
        <div class="expanded-day-actions">
            <button class="btn-primary" onclick="event.stopPropagation(); openCreateScheduleForDate('${dateStr}')">+ Add Shift</button>
            <span class="shift-count">${daySchedules.length} shift${daySchedules.length !== 1 ? 's' : ''} scheduled</span>
        </div>
    `;

    if (daySchedules.length === 0) {
        html += `
            <div class="expanded-day-empty">
                <div class="empty-icon">📅</div>
                <h3>No Shifts Scheduled</h3>
                <p>Click the button above to add a shift for this day.</p>
            </div>
        `;
    } else {
        // Time grid for the expanded day
        html += '<div class="expanded-day-grid">';

        // Time labels
        html += '<div class="expanded-day-time-labels">';
        for (let hour = earliestHour; hour <= latestHour; hour++) {
            html += `<div class="expanded-day-time-label">${formatHour(hour)}</div>`;
        }
        html += '</div>';

        // Shifts column (takes full remaining width)
        html += `<div class="expanded-day-shifts-column" style="min-height: ${(latestHour - earliestHour + 1) * hourHeight}px;">`;

        // Hour lines
        for (let hour = earliestHour; hour <= latestHour; hour++) {
            html += `<div class="expanded-day-hour-line" style="top: ${(hour - earliestHour) * hourHeight}px;" onclick="event.stopPropagation(); openCreateScheduleForDateTime('${dateStr}', ${hour})"></div>`;
        }

        // Render shifts - in expanded view, show them with more details
        const shiftGroups = groupOverlappingShifts(daySchedules);

        shiftGroups.forEach(group => {
            const groupWidth = 100 / group.length;
            group.forEach((shift, idx) => {
                const startTime = parseTime(shift.start_time);
                const endTime = parseTime(shift.end_time);
                const durationMinutes = (endTime.hour * 60 + endTime.minute) - (startTime.hour * 60 + startTime.minute);

                const top = ((startTime.hour - earliestHour) * 60 + startTime.minute) / 60 * hourHeight;
                const height = Math.max((durationMinutes / 60) * hourHeight - 4, 40); // Min height for readability
                const left = idx * groupWidth;
                const width = groupWidth - 0.5;

                const color = getEmployeeColor(shift.employee_id);
                const hasChangeRequest = shift.change_request_status === 'pending';
                const duration = (durationMinutes / 60).toFixed(1);

                html += `
                    <div class="expanded-shift-block ${hasChangeRequest ? 'has-change-request' : ''}"
                         style="top: ${top}px; height: ${height}px; left: ${left}%; width: ${width}%; background: ${color};"
                         onclick="event.stopPropagation(); editSchedule(${shift.id})">
                        <div class="expanded-shift-content">
                            <div class="expanded-shift-name">${shift.employee_name}</div>
                            <div class="expanded-shift-time">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</div>
                            <div class="expanded-shift-details">
                                <span class="shift-duration">${duration} hrs</span>
                                ${shift.position ? `<span class="shift-position">${shift.position}</span>` : ''}
                                ${shift.shift_type && shift.shift_type !== 'regular' ? `<span class="shift-type">${shift.shift_type}</span>` : ''}
                            </div>
                        </div>
                        ${hasChangeRequest ? '<div class="expanded-change-badge">Change Requested</div>' : ''}
                    </div>
                `;
            });
        });

        html += '</div>'; // shifts column
        html += '</div>'; // grid
    }

    html += '</div>'; // expanded-day-view

    weekGrid.innerHTML = html;
    console.log('Expanded day view rendered for:', dateStr);
}

function renderAdminMonthView() {
    console.log('Rendering admin month view...');
    const monthGrid = document.getElementById('adminMonthGrid');

    if (!monthGrid) {
        console.error('adminMonthGrid element not found!');
        return;
    }

    const startOfMonth = adminCurrentDate.startOf('month');
    const endOfMonth = adminCurrentDate.endOf('month');
    const startOfCalendar = startOfMonth.startOf('week');
    const endOfCalendar = endOfMonth.endOf('week');

    console.log('Month:', adminCurrentDate.toFormat('MMMM yyyy'));
    console.log('Date range:', startOfCalendar.toISODate(), 'to', endOfCalendar.toISODate());

    // Get active filter text
    let filterText = '';
    if (adminFilters.employee) {
        const emp = adminEmployees.find(e => e.id === parseInt(adminFilters.employee));
        const empName = emp ? (emp.employee_name || `${emp.first_name} ${emp.last_name}`) : 'Unknown';
        filterText = ` - ${empName}`;
    } else if (adminFilters.position) {
        filterText = ` - ${adminFilters.position}`;
    } else if (adminFilters.status) {
        filterText = ` - ${adminFilters.status}`;
    }

    let html = '<div class="month-calendar-grid">';

    // Month header
    html += `
        <div class="compact-week-header" style="margin-bottom: 20px;">
            <h3>${adminCurrentDate.toFormat('MMMM yyyy')}${filterText}</h3>
            <button class="btn-primary" onclick="openCreateScheduleModal()">+ Add Shift</button>
        </div>
    `;

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
        const isCurrentMonth = currentDay.month === adminCurrentDate.month;
        const isToday = currentDay.hasSame(luxon.DateTime.now(), 'day');
        const dateStr = currentDay.toISODate();

        html += `
            <div class="month-day-cell ${!isCurrentMonth ? 'other-month' : ''} ${isToday ? 'today' : ''}"
                 data-date="${dateStr}"
                 onclick="handleMonthDayClick('${dateStr}', event)">
                <div class="month-day-number">${currentDay.day}</div>
                <div class="month-day-shifts">
        `;

        // Find shifts for this day
        const daySchedules = adminSchedules.filter(s => s.date === dateStr);

        // Show shift indicators (max 3)
        daySchedules.slice(0, 3).forEach(shift => {
            const color = getEmployeeColor(shift.employee_id);

            html += `
                <div class="month-shift-indicator"
                     style="background: ${color};"
                     onclick="event.stopPropagation(); editSchedule(${shift.id})"
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
    console.log('Admin month view rendered successfully');
}

function handleMonthDayClick(dateStr, event) {
    // Check if we already have an expanded view open
    const existingExpanded = document.querySelector('.month-day-expanded');
    if (existingExpanded) {
        existingExpanded.remove();
    }

    const daySchedules = adminSchedules.filter(s => s.date === dateStr);
    const clickedCell = event.currentTarget;
    const rect = clickedCell.getBoundingClientRect();

    if (daySchedules.length === 0) {
        // Show "Create Event" popup with animation
        showCreateEventPopup(dateStr, rect);
    } else {
        // Expand to show all schedules for this day
        showDaySchedulesExpanded(dateStr, daySchedules, clickedCell);
    }
}

function showCreateEventPopup(dateStr, rect) {
    // Create popup element
    const popup = document.createElement('div');
    popup.className = 'create-event-popup';
    popup.style.position = 'fixed';
    popup.style.left = rect.left + 'px';
    popup.style.top = rect.top + 'px';
    // Make popup twice the width of a calendar cell
    popup.style.width = (rect.width * 2) + 'px';
    popup.style.minHeight = rect.height + 'px';

    const formattedDate = luxon.DateTime.fromISO(dateStr).toFormat('EEEE, MMM d');

    popup.innerHTML = `
        <div class="popup-content">
            <div class="popup-title">No shifts scheduled</div>
            <div class="popup-subtitle">${formattedDate}</div>
            <button class="popup-btn" onclick="closeCreateEventPopup(); openCreateScheduleForDate('${dateStr}')">
                + Create Shift
            </button>
        </div>
    `;

    document.body.appendChild(popup);

    // Close when mouse leaves the popup
    popup.addEventListener('mouseleave', () => {
        closeCreateEventPopup();
    });

    // Trigger animation
    setTimeout(() => {
        popup.classList.add('show');
    }, 10);
}

function closeCreateEventPopup() {
    const popup = document.querySelector('.create-event-popup');
    if (popup) {
        popup.classList.remove('show');
        setTimeout(() => popup.remove(), 300);
    }
}

function showDaySchedulesExpanded(dateStr, schedules, clickedCell) {
    const formattedDate = luxon.DateTime.fromISO(dateStr).toFormat('EEEE, MMMM d, yyyy');

    // Create expanded view
    const expanded = document.createElement('div');
    expanded.className = 'month-day-expanded';

    let shiftsHTML = '';
    schedules.forEach(shift => {
        const color = getEmployeeColor(shift.employee_id);
        shiftsHTML += `
            <div class="expanded-shift-item" style="border-left: 4px solid ${color};" onclick="editSchedule(${shift.id})">
                <div class="shift-item-employee">${shift.employee_name}</div>
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
            <button class="btn-primary" onclick="openCreateScheduleForDate('${dateStr}')">+ Add Shift</button>
        </div>
    `;

    // Insert after the clicked cell's parent row
    const dayCell = clickedCell.closest('.month-day-cell');
    const daysGrid = dayCell.closest('.month-days-grid');
    daysGrid.appendChild(expanded);

    // Trigger animation
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

function renderAdminShiftBlock(shift) {
    const shiftStart = parseTime(shift.start_time);
    const shiftEnd = parseTime(shift.end_time);
    const duration = shiftEnd.diff(shiftStart, 'hours').hours;

    const color = getEmployeeColor(shift.employee_id);
    const hasChangeRequest = shift.change_request_status === 'pending';

    const top = (shiftStart.minute / 60) * 100;
    const height = (duration * 60 - 2) + '%';

    return `
        <div class="admin-shift-block ${hasChangeRequest ? 'has-change-request' : ''}"
             style="top: ${top}%; height: ${height}; background: ${color};"
             onclick="event.stopPropagation(); showAdminShiftDetail(${shift.id})"
             title="Click to edit">
            <div class="shift-employee-name">${shift.employee_name}</div>
            <div class="shift-time-text">${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</div>
            ${hasChangeRequest ? '<div class="change-request-indicator">⚠️</div>' : ''}
        </div>
    `;
}

function renderChangeRequests() {
    const tbody = document.getElementById('changeRequestsTableBody');

    if (adminChangeRequests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="list-empty">No pending change requests</td></tr>';
        return;
    }

    let html = '';
    adminChangeRequests.forEach(shift => {
        html += `
            <tr>
                <td>${shift.employee_name}</td>
                <td>${formatDate(shift.date)}: ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</td>
                <td>${shift.change_requested_by_name || 'Unknown'}</td>
                <td>${shift.change_request_reason || '-'}</td>
                <td>${formatDateTime(shift.change_request_date)}</td>
                <td>
                    <button class="btn btn-success btn-sm" onclick="approveChangeRequest(${shift.id})">
                        ✓ Approve
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="denyChangeRequest(${shift.id})">
                        ✗ Deny
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// ==========================================
// VIEW SWITCHING & NAVIGATION
// ==========================================

async function switchAdminScheduleView(view) {
    adminCurrentView = view;
    expandedDayDate = null; // Reset expanded day when switching views

    // Update buttons
    document.querySelectorAll('.schedule-view-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.view === view) {
            btn.classList.add('active');
        }
    });

    // Toggle views
    document.getElementById('adminWeekView').style.display = view === 'week' ? 'block' : 'none';
    document.getElementById('adminMonthView').style.display = view === 'month' ? 'block' : 'none';

    // Reload data with the correct date range for the new view
    await loadAdminData();
}

async function navigateAdminSchedule(direction) {
    if (direction === 'prev') {
        if (adminCurrentView === 'month') {
            adminCurrentDate = adminCurrentDate.minus({ months: 1 });
        } else {
            adminCurrentDate = adminCurrentDate.minus({ weeks: 1 });
        }
    } else if (direction === 'next') {
        if (adminCurrentView === 'month') {
            adminCurrentDate = adminCurrentDate.plus({ months: 1 });
        } else {
            adminCurrentDate = adminCurrentDate.plus({ weeks: 1 });
        }
    } else if (direction === 'today') {
        adminCurrentDate = luxon.DateTime.now();
    }

    await loadAdminData();
}

// ==========================================
// FILTERS
// ==========================================

function populateAdminFilters() {
    const employeeFilter = document.getElementById('scheduleEmployeeFilter');
    const positionFilter = document.getElementById('schedulePositionFilter');

    if (!employeeFilter || !positionFilter) {
        console.error('Filter elements not found');
        return;
    }

    // Save currently selected values
    const selectedEmployee = employeeFilter.value;
    const selectedPosition = positionFilter.value;

    console.log('Populating filters. Current selections:', {
        employee: selectedEmployee,
        position: selectedPosition,
        adminFilters: adminFilters
    });

    // Clear and reset employee filter
    employeeFilter.innerHTML = '<option value="">All Employees</option>';

    // Populate employees (sorted alphabetically)
    const sortedEmployees = [...adminEmployees].sort((a, b) => {
        const nameA = a.employee_name || `${a.first_name || ''} ${a.last_name || ''}`.trim();
        const nameB = b.employee_name || `${b.first_name || ''} ${b.last_name || ''}`.trim();
        return nameA.localeCompare(nameB);
    });
    sortedEmployees.forEach(emp => {
        const empName = emp.employee_name || `${emp.first_name || ''} ${emp.last_name || ''}`.trim();
        employeeFilter.innerHTML += `<option value="${emp.id}">${empName}</option>`;
    });

    // Clear and reset position filter
    positionFilter.innerHTML = '<option value="">All Positions</option>';

    // Populate positions (unique)
    const positions = [...new Set(adminEmployees.map(e => e.position).filter(Boolean))].sort();
    positions.forEach(pos => {
        positionFilter.innerHTML += `<option value="${pos}">${pos}</option>`;
    });

    // Restore previously selected values only if they exist in adminFilters
    if (adminFilters.employee) {
        employeeFilter.value = adminFilters.employee;
    } else {
        employeeFilter.value = '';
    }

    if (adminFilters.position) {
        positionFilter.value = adminFilters.position;
    } else {
        positionFilter.value = '';
    }

    console.log('Filters populated. Dropdown values:', {
        employee: employeeFilter.value,
        position: positionFilter.value
    });
}

async function filterAdminSchedules() {
    const employeeFilter = document.getElementById('scheduleEmployeeFilter');
    const positionFilter = document.getElementById('schedulePositionFilter');
    const statusFilter = document.getElementById('scheduleStatusFilter');

    adminFilters.employee = employeeFilter.value;
    adminFilters.position = positionFilter.value;
    adminFilters.status = statusFilter.value;

    console.log('=== FILTER CHANGED ===');
    console.log('Selected employee:', adminFilters.employee);
    console.log('Selected position:', adminFilters.position);
    console.log('Selected status:', adminFilters.status);
    console.log('Employee dropdown text:', employeeFilter.options[employeeFilter.selectedIndex].text);

    await loadAdminData();
}

// ==========================================
// SCHEDULE CRUD OPERATIONS
// ==========================================

function openCreateScheduleModal(prefilledDate = null, prefilledStartTime = null, prefilledEndTime = null) {
    const modal = document.getElementById('createScheduleModal');
    const employeeSelect = document.getElementById('scheduleEmployee');
    const dateInput = document.getElementById('scheduleDate');
    const startTimeInput = document.getElementById('scheduleStartTime');
    const endTimeInput = document.getElementById('scheduleEndTime');

    // Clear and populate employee dropdown
    employeeSelect.innerHTML = '<option value="">Select Employee</option>';
    const sortedEmployees = [...adminEmployees].sort((a, b) => {
        const nameA = a.employee_name || `${a.first_name || ''} ${a.last_name || ''}`.trim();
        const nameB = b.employee_name || `${b.first_name || ''} ${b.last_name || ''}`.trim();
        return nameA.localeCompare(nameB);
    });
    sortedEmployees.forEach(emp => {
        const empName = emp.employee_name || `${emp.first_name || ''} ${emp.last_name || ''}`.trim();
        employeeSelect.innerHTML += `<option value="${emp.id}">${empName} (${emp.employee_code || emp.id})</option>`;
    });

    // Set default values
    if (prefilledDate) {
        dateInput.value = prefilledDate;
    } else {
        dateInput.value = luxon.DateTime.now().toISODate();
    }

    startTimeInput.value = prefilledStartTime || '09:00';
    endTimeInput.value = prefilledEndTime || '17:00';
    document.getElementById('scheduleShiftType').value = 'regular';
    document.getElementById('schedulePosition').value = '';
    document.getElementById('scheduleBreak').value = '30';
    document.getElementById('scheduleNotes').value = '';

    modal.style.display = 'flex';
}

function openCreateScheduleForDate(date) {
    openCreateScheduleModal(date);
}

function openCreateScheduleForDateTime(date, hour) {
    const startTime = `${String(hour).padStart(2, '0')}:00`;
    const endTime = `${String(hour + 4).padStart(2, '0')}:00`;
    openCreateScheduleModal(date, startTime, endTime);
}

function closeScheduleModal() {
    document.getElementById('createScheduleModal').style.display = 'none';
    document.getElementById('editScheduleModal').style.display = 'none';
    document.getElementById('approveChangeModal').style.display = 'none';
    document.getElementById('denyChangeModal').style.display = 'none';
    document.getElementById('replaceShiftModal').style.display = 'none';
}

async function saveSchedule() {
    const employeeId = document.getElementById('scheduleEmployee').value;
    const date = document.getElementById('scheduleDate').value;
    const startTime = document.getElementById('scheduleStartTime').value;
    const endTime = document.getElementById('scheduleEndTime').value;
    const shiftType = document.getElementById('scheduleShiftType').value;
    const position = document.getElementById('schedulePosition').value;
    const breakDuration = document.getElementById('scheduleBreak').value;
    const notes = document.getElementById('scheduleNotes').value;

    if (!employeeId || !date || !startTime || !endTime) {
        showAdminError('Please fill in all required fields');
        return;
    }

    const scheduleData = {
        employee_id: parseInt(employeeId),
        date: date,
        start_time: startTime,
        end_time: endTime,
        shift_type: shiftType,
        position: position || null,
        break_duration: parseInt(breakDuration) || 30,
        notes: notes || null
    };

    await createSchedule(scheduleData);
    closeScheduleModal();
}

async function createSchedule(scheduleData) {
    try {
        const response = await fetch('/api/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(scheduleData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create schedule');
        }

        showAdminSuccess('Schedule created successfully');
        await loadAdminData();
    } catch (error) {
        console.error('Error creating schedule:', error);
        showAdminError(error.message || 'Failed to create schedule');
    }
}

function editSchedule(scheduleId) {
    const shift = adminSchedules.find(s => s.id === scheduleId);
    if (!shift) {
        showAdminError('Schedule not found');
        return;
    }

    const modal = document.getElementById('editScheduleModal');

    // Populate the form with existing data
    document.getElementById('editScheduleId').value = shift.id;
    document.getElementById('editScheduleEmployeeName').textContent = shift.employee_name;
    document.getElementById('editScheduleDate').value = shift.date;
    document.getElementById('editScheduleStartTime').value = shift.start_time;
    document.getElementById('editScheduleEndTime').value = shift.end_time;
    document.getElementById('editScheduleShiftType').value = shift.shift_type || 'regular';
    document.getElementById('editSchedulePosition').value = shift.position || '';
    document.getElementById('editScheduleBreak').value = shift.break_duration || 30;
    document.getElementById('editScheduleNotes').value = shift.notes || '';
    document.getElementById('editScheduleStatus').value = shift.status || 'scheduled';

    modal.style.display = 'flex';
}

// Alias for backwards compatibility
const showAdminShiftDetail = editSchedule;

async function updateSchedule() {
    const scheduleId = document.getElementById('editScheduleId').value;
    const date = document.getElementById('editScheduleDate').value;
    const startTime = document.getElementById('editScheduleStartTime').value;
    const endTime = document.getElementById('editScheduleEndTime').value;
    const shiftType = document.getElementById('editScheduleShiftType').value;
    const position = document.getElementById('editSchedulePosition').value;
    const breakDuration = document.getElementById('editScheduleBreak').value;
    const notes = document.getElementById('editScheduleNotes').value;
    const status = document.getElementById('editScheduleStatus').value;

    if (!date || !startTime || !endTime) {
        showAdminError('Please fill in all required fields');
        return;
    }

    const updates = {
        date: date,
        start_time: startTime,
        end_time: endTime,
        shift_type: shiftType,
        position: position || null,
        break_duration: parseInt(breakDuration) || 30,
        notes: notes || null,
        status: status
    };

    try {
        const response = await fetch(`/api/schedules/${scheduleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (!response.ok) throw new Error('Failed to update schedule');

        showAdminSuccess('Schedule updated successfully');
        closeScheduleModal();
        await loadAdminData();
    } catch (error) {
        console.error('Error updating schedule:', error);
        showAdminError('Failed to update schedule');
    }
}

async function deleteScheduleConfirm() {
    try {
        const response = await fetch(`/api/schedules/${scheduleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (!response.ok) throw new Error('Failed to update schedule');

        showAdminSuccess('Schedule updated successfully');
        await loadAdminData();
    } catch (error) {
        console.error('Error updating schedule:', error);
        showAdminError('Failed to update schedule');
    }
}

async function deleteScheduleConfirm() {
    const scheduleId = document.getElementById('editScheduleId').value;
    const shift = adminSchedules.find(s => s.id == scheduleId);

    if (!shift || !confirm(`Are you sure you want to delete this schedule for ${shift.employee_name} on ${formatDate(shift.date)}?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/schedules/${scheduleId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete schedule');

        showAdminSuccess('Schedule deleted successfully');
        closeScheduleModal();
        await loadAdminData();
    } catch (error) {
        console.error('Error deleting schedule:', error);
        showAdminError('Failed to delete schedule');
    }
}

// ==========================================
// CHANGE REQUESTS
// ==========================================

function showChangeRequestDetail(scheduleId) {
    // Can be used to show details - for now just open approval modal
    approveChangeRequest(scheduleId);
}

function approveChangeRequest(scheduleId) {
    const shift = adminChangeRequests.find(s => s.id === scheduleId);
    if (!shift) {
        showAdminError('Change request not found');
        return;
    }

    const modal = document.getElementById('approveChangeModal');
    document.getElementById('approveScheduleId').value = scheduleId;

    const detailsHTML = `
        <div class="change-request-details">
            <p><strong>Employee:</strong> ${shift.employee_name}</p>
            <p><strong>Current Schedule:</strong> ${formatDate(shift.date)} at ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</p>
            <p><strong>Requested By:</strong> ${shift.employee_name}</p>
            <p><strong>Request Date:</strong> ${formatDateTime(shift.change_request_date)}</p>
            <p><strong>Reason:</strong></p>
            <p style="background: #f3f4f6; padding: 10px; border-radius: 6px; margin-top: 5px;">${shift.change_request_reason || 'No reason provided'}</p>
        </div>
    `;

    document.getElementById('approveChangeDetails').innerHTML = detailsHTML;
    modal.style.display = 'flex';
}

async function confirmApproveChange() {
    const scheduleId = document.getElementById('approveScheduleId').value;

    try {
        const response = await fetch(`/api/schedules/${scheduleId}/approve-change`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved: true })
        });

        if (!response.ok) throw new Error('Failed to approve change request');

        const data = await response.json();

        showAdminSuccess('Change request approved and shift cancelled');
        closeScheduleModal();

        // Show replacement prompt if shift details are returned
        if (data.cancelled_shift) {
            showReplaceShiftModal(data.cancelled_shift);
        } else {
            await loadAdminData();
        }
    } catch (error) {
        console.error('Error approving change request:', error);
        showAdminError('Failed to approve change request');
    }
}

function showReplaceShiftModal(cancelledShift) {
    const modal = document.getElementById('replaceShiftModal');

    // Store the cancelled shift details
    document.getElementById('replacementDate').value = cancelledShift.date;
    document.getElementById('replacementStartTime').value = cancelledShift.start_time;
    document.getElementById('replacementEndTime').value = cancelledShift.end_time;
    document.getElementById('replacementPosition').value = cancelledShift.position || '';

    // Display the shift details
    const detailsHTML = `
        <p><strong>Date:</strong> ${formatDate(cancelledShift.date)}</p>
        <p><strong>Time:</strong> ${formatTime(cancelledShift.start_time)} - ${formatTime(cancelledShift.end_time)}</p>
        ${cancelledShift.position ? `<p><strong>Position:</strong> ${cancelledShift.position}</p>` : ''}
    `;

    document.getElementById('replaceShiftDetails').innerHTML = detailsHTML;
    modal.style.display = 'flex';
}

function closeReplaceShiftModal() {
    document.getElementById('replaceShiftModal').style.display = 'none';
    // Reload data to show updated calendar
    loadAdminData();
}

function openReplacementScheduleModal() {
    // Get the stored shift details
    const date = document.getElementById('replacementDate').value;
    const startTime = document.getElementById('replacementStartTime').value;
    const endTime = document.getElementById('replacementEndTime').value;
    const position = document.getElementById('replacementPosition').value;

    // Close the replacement prompt
    document.getElementById('replaceShiftModal').style.display = 'none';

    // Open the create schedule modal with pre-filled data
    openCreateScheduleModal(date, startTime, endTime);

    // Pre-fill the position if available
    if (position) {
        setTimeout(() => {
            document.getElementById('schedulePosition').value = position;
        }, 100);
    }
}

function denyChangeRequest(scheduleId) {
    const shift = adminChangeRequests.find(s => s.id === scheduleId);
    if (!shift) {
        showAdminError('Change request not found');
        return;
    }

    const modal = document.getElementById('denyChangeModal');
    document.getElementById('denyScheduleId').value = scheduleId;

    const detailsHTML = `
        <div class="change-request-details">
            <p><strong>Employee:</strong> ${shift.employee_name}</p>
            <p><strong>Current Schedule:</strong> ${formatDate(shift.date)} at ${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}</p>
            <p><strong>Reason:</strong></p>
            <p style="background: #f3f4f6; padding: 10px; border-radius: 6px; margin-top: 5px;">${shift.change_request_reason || 'No reason provided'}</p>
        </div>
    `;

    document.getElementById('denyChangeDetails').innerHTML = detailsHTML;
    document.getElementById('denyReason').value = '';
    modal.style.display = 'flex';
}

async function confirmDenyChange() {
    const scheduleId = document.getElementById('denyScheduleId').value;
    const reason = document.getElementById('denyReason').value;

    if (!reason || !reason.trim()) {
        showAdminError('Please provide a reason for denying this request');
        return;
    }

    try {
        const response = await fetch(`/api/schedules/${scheduleId}/approve-change`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                approved: false,
                admin_notes: reason
            })
        });

        if (!response.ok) throw new Error('Failed to deny change request');

        showAdminSuccess('Change request denied');
        closeScheduleModal();
        await loadAdminData();
    } catch (error) {
        console.error('Error denying change request:', error);
        showAdminError('Failed to deny change request');
    }
}

// ==========================================
// PAGINATION
// ==========================================

// ==========================================
// HELPER FUNCTIONS
// ==========================================

function getAdminDateRange() {
    if (adminCurrentView === 'month') {
        const startDate = adminCurrentDate.startOf('month').startOf('week').toISODate();
        const endDate = adminCurrentDate.endOf('month').endOf('week').toISODate();
        return { startDate, endDate };
    } else {
        const startDate = adminCurrentDate.startOf('week').toISODate();
        const endDate = adminCurrentDate.endOf('week').toISODate();
        return { startDate, endDate };
    }
}

function updateAdminDateDisplay() {
    const display = document.getElementById('adminScheduleDateRange');

    // Element removed - date display now shown in view headers
    if (!display) return;

    if (adminCurrentView === 'month') {
        display.textContent = adminCurrentDate.toFormat('MMMM yyyy');
    } else {
        const start = adminCurrentDate.startOf('week');
        const end = adminCurrentDate.endOf('week');
        display.textContent = `${start.toFormat('MMM d')} - ${end.toFormat('MMM d, yyyy')}`;
    }
}

function getEmployeeColor(employeeId) {
    const index = employeeId % employeeColors.length;
    return employeeColors[index];
}

function getInitials(name) {
    if (!name) return '?';
    const parts = name.split(' ');
    if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
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

function showAdminLoading(show) {
    // Toggle loading state
    const weekGrid = document.getElementById('adminWeekGrid');
    if (show) {
        weekGrid.innerHTML = '<div class="schedule-loading"><div class="loader"></div><p>Loading...</p></div>';
    }
}

function showAdminError(message) {
    console.error('Admin Schedule Error:', message);
    // Don't show alert - just log to console to avoid disrupting UX
}

function showAdminSuccess(message) {
    console.log('Admin Schedule Success:', message);
    // Show a subtle notification instead of alert
    const headerStats = document.getElementById('headerStats');
    if (headerStats) {
        const originalHTML = headerStats.innerHTML;
        headerStats.innerHTML = `✅ ${message}`;
        headerStats.style.color = '#10b981';
        setTimeout(() => {
            headerStats.innerHTML = originalHTML;
            headerStats.style.color = '';
        }, 3000);
    }
}

// Auto-initialize when schedules tab is shown
document.addEventListener('DOMContentLoaded', function() {
    // Listen for tab changes
    const schedulesTab = document.getElementById('schedules-tab');
    if (schedulesTab) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName === 'class') {
                    if (schedulesTab.classList.contains('active')) {
                        initAdminSchedules();
                    }
                }
            });
        });
        observer.observe(schedulesTab, { attributes: true });
    }
});

// Close modals when clicking outside
window.addEventListener('click', function(event) {
    const modals = ['createScheduleModal', 'editScheduleModal', 'approveChangeModal', 'denyChangeModal', 'replaceShiftModal'];

    modals.forEach(modalId => {
        const modal = document.getElementById(modalId);
        if (modal && event.target === modal) {
            closeScheduleModal();
        }
    });
});
