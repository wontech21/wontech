/**
 * Attendance Management JavaScript
 * Handles loading and displaying employee attendance records
 */

let allAttendance = [];
let allEmployeesForFilter = [];
let currentAttendancePage = 1;
let attendancePageSize = 10;
let attendanceSortColumn = null;
let attendanceSortDirection = 'desc';

// Load attendance records when attendance tab is shown
function loadAttendance() {
    // Get date filters
    const dateFrom = document.getElementById('attendanceDateFrom')?.value || '';
    const dateTo = document.getElementById('attendanceDateTo')?.value || '';

    // Build URL with optional date filters
    let url = '/api/attendance/history';
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (params.toString()) url += '?' + params.toString();

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                allAttendance = data.attendance || [];
                loadEmployeesForFilter();
                filterAndDisplayAttendance();
                updateAttendanceStats();
            } else {
                showError('Failed to load attendance records');
            }
        })
        .catch(error => {
            console.error('Error loading attendance:', error);
            showError('Error loading attendance records');
        });
}

// Load employees for filter dropdown
function loadEmployeesForFilter() {
    fetch('/api/employees')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                allEmployeesForFilter = data.employees || [];
                populateEmployeeFilter();
            }
        })
        .catch(error => {
            console.error('Error loading employees:', error);
        });
}

function populateEmployeeFilter() {
    const select = document.getElementById('attendanceEmployeeFilter');
    const currentValue = select.value;

    // Clear existing options except "All Employees"
    select.innerHTML = '<option value="all">All Employees</option>';

    // Add employee options
    allEmployeesForFilter.forEach(emp => {
        const option = document.createElement('option');
        option.value = emp.id;
        option.textContent = `${emp.first_name} ${emp.last_name} (${emp.employee_code})`;
        select.appendChild(option);
    });

    // Restore previous selection if valid
    if (currentValue) {
        select.value = currentValue;
    }
}

function filterAndDisplayAttendance() {
    const employeeFilter = document.getElementById('attendanceEmployeeFilter')?.value || 'all';
    const statusFilter = document.getElementById('attendanceStatusFilter')?.value || 'all';
    const dateFrom = document.getElementById('attendanceDateFrom')?.value || '';
    const dateTo = document.getElementById('attendanceDateTo')?.value || '';

    let filtered = allAttendance;

    // Filter by employee
    if (employeeFilter !== 'all') {
        filtered = filtered.filter(record => record.employee_id == employeeFilter);
    }

    // Filter by status
    if (statusFilter !== 'all') {
        filtered = filtered.filter(record => record.status === statusFilter);
    }

    // Filter by date range
    if (dateFrom) {
        filtered = filtered.filter(record => {
            if (!record.clock_in) return false;
            // Convert SQL format to ISO if needed
            const isoString = record.clock_in.replace(' ', 'T');
            const recordDate = new Date(isoString).toISOString().split('T')[0];
            return recordDate >= dateFrom;
        });
    }

    if (dateTo) {
        filtered = filtered.filter(record => {
            if (!record.clock_in) return false;
            // Convert SQL format to ISO if needed
            const isoString = record.clock_in.replace(' ', 'T');
            const recordDate = new Date(isoString).toISOString().split('T')[0];
            return recordDate <= dateTo;
        });
    }

    displayAttendance(filtered);
}

function displayAttendance(records) {
    const tbody = document.getElementById('attendanceTableBody');

    if (!records || records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="color: #6b7280; padding: 40px;">No attendance records found</td></tr>';
        updateAttendancePagination(0);
        return;
    }

    // Apply pagination
    const totalRecords = records.length;
    const totalPages = attendancePageSize === 'all' ? 1 : Math.ceil(totalRecords / attendancePageSize);
    currentAttendancePage = Math.min(currentAttendancePage, totalPages || 1);

    const startIndex = attendancePageSize === 'all' ? 0 : (currentAttendancePage - 1) * attendancePageSize;
    const endIndex = attendancePageSize === 'all' ? totalRecords : startIndex + attendancePageSize;
    const paginatedRecords = records.slice(startIndex, endIndex);

    tbody.innerHTML = paginatedRecords.map(record => {
        const employeeName = record.employee_name || 'Unknown';
        const clockIn = record.clock_in ? formatDateTime(record.clock_in) : '—';
        const clockOut = record.clock_out ? formatDateTime(record.clock_out) : '—';
        const totalHours = record.total_hours ? record.total_hours.toFixed(2) : '0.00';
        const breakDuration = record.break_duration || 0;
        const status = record.status || 'clocked_out';
        const notes = record.notes || '';

        // Status badge styling
        let statusClass = 'badge-secondary';
        let statusIcon = '○';
        if (status === 'clocked_in') {
            statusClass = 'badge-success';
            statusIcon = '●';
        } else if (status === 'on_break') {
            statusClass = 'badge-warning';
            statusIcon = '☕';
        }

        return `
        <tr class="hoverable-row">
            <td><strong>${employeeName}</strong></td>
            <td>${clockIn}</td>
            <td>${clockOut}</td>
            <td><strong style="color: #667eea;">${totalHours} hrs</strong></td>
            <td>${breakDuration} min</td>
            <td>
                <span class="badge ${statusClass}">
                    ${statusIcon} ${status.replace('_', ' ').charAt(0).toUpperCase() + status.replace('_', ' ').slice(1)}
                </span>
            </td>
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;" title="${notes}">${notes}</td>
            <td class="actions-cell">
                <button class="btn-edit-dark"
                        onclick="editAttendance(${record.id})"
                        title="Edit Timesheet">
                    <span style="font-weight: 700;">✏️</span>
                </button>
            </td>
        </tr>
        `;
    }).join('');

    updateAttendancePagination(totalRecords);
}

function formatDateTime(dateString) {
    if (!dateString) return '—';

    // Convert SQL datetime format to ISO format if needed
    // "2026-01-25 13:53:00" -> "2026-01-25T13:53:00"
    const isoString = dateString.replace(' ', 'T');

    const date = new Date(isoString);

    // Check if date is valid
    if (isNaN(date.getTime())) {
        console.error('Invalid date string:', dateString);
        return 'Invalid Date';
    }

    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

function updateAttendanceStats() {
    const totalRecords = allAttendance.length;
    const totalHours = allAttendance.reduce((sum, record) => sum + (record.total_hours || 0), 0);
    const clockedIn = allAttendance.filter(record => record.status === 'clocked_in').length;
    const onBreak = allAttendance.filter(record => record.status === 'on_break').length;

    document.getElementById('statTotalRecords').textContent = totalRecords;
    document.getElementById('statTotalHours').textContent = totalHours.toFixed(1);
    document.getElementById('statClockedIn').textContent = clockedIn;
    document.getElementById('statOnBreak').textContent = onBreak;
}

// Pagination functions
function updateAttendancePagination(totalRecords) {
    const totalPages = attendancePageSize === 'all' ? 1 : Math.ceil(totalRecords / attendancePageSize);
    const startIndex = attendancePageSize === 'all' ? 1 : (currentAttendancePage - 1) * attendancePageSize + 1;
    const endIndex = attendancePageSize === 'all' ? totalRecords : Math.min(currentAttendancePage * attendancePageSize, totalRecords);

    // Update pagination info
    document.getElementById('attendancePaginationInfo').textContent =
        `Showing ${startIndex}-${endIndex} of ${totalRecords} records`;

    // Update page numbers
    const pageNumbersDiv = document.getElementById('attendancePageNumbers');
    let pageNumbersHTML = '';

    if (totalPages <= 7) {
        for (let i = 1; i <= totalPages; i++) {
            pageNumbersHTML += `<button class="${i === currentAttendancePage ? 'active' : ''}"
                onclick="goToAttendancePage(${i})">${i}</button>`;
        }
    } else {
        if (currentAttendancePage <= 4) {
            for (let i = 1; i <= 5; i++) {
                pageNumbersHTML += `<button class="${i === currentAttendancePage ? 'active' : ''}"
                    onclick="goToAttendancePage(${i})">${i}</button>`;
            }
            pageNumbersHTML += `<span>...</span>`;
            pageNumbersHTML += `<button onclick="goToAttendancePage(${totalPages})">${totalPages}</button>`;
        } else if (currentAttendancePage >= totalPages - 3) {
            pageNumbersHTML += `<button onclick="goToAttendancePage(1)">1</button>`;
            pageNumbersHTML += `<span>...</span>`;
            for (let i = totalPages - 4; i <= totalPages; i++) {
                pageNumbersHTML += `<button class="${i === currentAttendancePage ? 'active' : ''}"
                    onclick="goToAttendancePage(${i})">${i}</button>`;
            }
        } else {
            pageNumbersHTML += `<button onclick="goToAttendancePage(1)">1</button>`;
            pageNumbersHTML += `<span>...</span>`;
            for (let i = currentAttendancePage - 1; i <= currentAttendancePage + 1; i++) {
                pageNumbersHTML += `<button class="${i === currentAttendancePage ? 'active' : ''}"
                    onclick="goToAttendancePage(${i})">${i}</button>`;
            }
            pageNumbersHTML += `<span>...</span>`;
            pageNumbersHTML += `<button onclick="goToAttendancePage(${totalPages})">${totalPages}</button>`;
        }
    }

    pageNumbersDiv.innerHTML = pageNumbersHTML;

    // Enable/disable navigation buttons
    document.getElementById('attendanceFirstPage').disabled = currentAttendancePage === 1;
    document.getElementById('attendancePrevPage').disabled = currentAttendancePage === 1;
    document.getElementById('attendanceNextPage').disabled = currentAttendancePage === totalPages || totalPages === 0;
    document.getElementById('attendanceLastPage').disabled = currentAttendancePage === totalPages || totalPages === 0;
}

function changeAttendancePage(direction) {
    const totalPages = Math.ceil(allAttendance.length / attendancePageSize);

    switch (direction) {
        case 'first':
            currentAttendancePage = 1;
            break;
        case 'prev':
            currentAttendancePage = Math.max(1, currentAttendancePage - 1);
            break;
        case 'next':
            currentAttendancePage = Math.min(totalPages, currentAttendancePage + 1);
            break;
        case 'last':
            currentAttendancePage = totalPages;
            break;
    }

    filterAndDisplayAttendance();
}

function goToAttendancePage(pageNum) {
    currentAttendancePage = pageNum;
    filterAndDisplayAttendance();
}

function changeAttendancePageSize() {
    const pageSize = document.getElementById('attendancePageSize').value;
    attendancePageSize = pageSize === 'all' ? 'all' : parseInt(pageSize);
    currentAttendancePage = 1;
    filterAndDisplayAttendance();
}

// Sorting function
function sortAttendanceTable(columnIndex, dataType) {
    // Store column being sorted
    const wasAscending = attendanceSortColumn === columnIndex && attendanceSortDirection === 'asc';
    attendanceSortColumn = columnIndex;
    attendanceSortDirection = wasAscending ? 'desc' : 'asc';

    // Update sort arrows
    document.querySelectorAll('#attendanceTable .sort-arrow').forEach(arrow => {
        arrow.textContent = '';
    });

    const arrow = document.querySelectorAll('#attendanceTable .sort-arrow')[columnIndex];
    arrow.textContent = attendanceSortDirection === 'asc' ? '▲' : '▼';

    // Sort the data
    const columnMap = ['employee_name', 'clock_in', 'clock_out', 'total_hours', 'break_duration', 'status'];
    const sortKey = columnMap[columnIndex];

    allAttendance.sort((a, b) => {
        let aVal, bVal;

        if (dataType === 'date') {
            aVal = a[sortKey] ? new Date(a[sortKey]).getTime() : 0;
            bVal = b[sortKey] ? new Date(b[sortKey]).getTime() : 0;
        } else if (dataType === 'number') {
            aVal = parseFloat(a[sortKey]) || 0;
            bVal = parseFloat(b[sortKey]) || 0;
        } else {
            aVal = (a[sortKey] || '').toString().toLowerCase();
            bVal = (b[sortKey] || '').toString().toLowerCase();
        }

        if (attendanceSortDirection === 'asc') {
            return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
            return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
        }
    });

    filterAndDisplayAttendance();
}

// Helper functions
function showSuccess(message) {
    if (typeof showNotification === 'function') {
        showNotification(message, 'success');
    } else {
        alert(message);
    }
}

function showError(message) {
    if (typeof showNotification === 'function') {
        showNotification(message, 'error');
    } else {
        alert(message);
    }
}

// Edit attendance functions
function editAttendance(attendanceId) {
    fetch(`/api/attendance/${attendanceId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const record = data.attendance;

                document.getElementById('attendanceId').value = record.id;
                document.getElementById('attendanceEmployeeName').value = record.employee_name;

                // Format datetime for datetime-local input
                if (record.clock_in) {
                    const clockIn = new Date(record.clock_in);
                    document.getElementById('attendanceClockIn').value = formatDateTimeLocal(clockIn);
                }

                if (record.clock_out) {
                    const clockOut = new Date(record.clock_out);
                    document.getElementById('attendanceClockOut').value = formatDateTimeLocal(clockOut);
                } else {
                    document.getElementById('attendanceClockOut').value = '';
                }

                document.getElementById('attendanceBreakDuration').value = record.break_duration || 0;
                document.getElementById('attendanceStatus').value = record.status || 'clocked_out';
                document.getElementById('attendanceNotes').value = record.notes || '';

                document.getElementById('attendanceFormError').style.display = 'none';
                document.getElementById('editAttendanceModal').classList.add('active');
            } else {
                showError('Failed to load attendance record');
            }
        })
        .catch(error => {
            console.error('Error loading attendance record:', error);
            showError('Error loading attendance record');
        });
}

function formatDateTimeLocal(date) {
    // Format: YYYY-MM-DDTHH:mm
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function closeEditAttendanceModal() {
    document.getElementById('editAttendanceModal').classList.remove('active');
    document.getElementById('editAttendanceForm').reset();
}

function saveAttendanceEdit(event) {
    event.preventDefault();

    const attendanceId = document.getElementById('attendanceId').value;
    const formData = {
        clock_in: document.getElementById('attendanceClockIn').value,
        clock_out: document.getElementById('attendanceClockOut').value,
        break_duration: parseInt(document.getElementById('attendanceBreakDuration').value) || 0,
        status: document.getElementById('attendanceStatus').value,
        notes: document.getElementById('attendanceNotes').value
    };

    // Disable submit button
    const submitBtn = document.getElementById('saveAttendanceBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';

    fetch(`/api/attendance/${attendanceId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
            closeEditAttendanceModal();
            loadAttendance();
        } else {
            document.getElementById('attendanceFormError').textContent = data.error;
            document.getElementById('attendanceFormError').style.display = 'block';
        }
    })
    .catch(error => {
        console.error('Error saving attendance:', error);
        document.getElementById('attendanceFormError').textContent = 'Error saving attendance record';
        document.getElementById('attendanceFormError').style.display = 'block';
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.textContent = '💾 Save Changes';
    });
}

// Load attendance when the attendance tab becomes active
document.addEventListener('DOMContentLoaded', function() {
    // Hook into tab switching to load attendance when tab is shown
    const originalShowTab = window.showTab;
    window.showTab = function(tabName) {
        if (originalShowTab) {
            originalShowTab(tabName);
        }
        if (tabName === 'attendance') {
            loadAttendance();
        }
    };
});
