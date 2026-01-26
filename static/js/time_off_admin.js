/**
 * Admin Time Off Request Management
 * Handles viewing, approving, and denying employee time off requests
 */

// Global state
let allTimeOffRequests = [];
let filteredTimeOffRequests = [];
let timeOffCurrentPage = 1;
let timeOffPageSize = 10;
let timeOffSort = { column: 2, order: 'desc', type: 'date' }; // Default sort by start date descending

// Initialize when tab is shown
async function initializeTimeOffTab() {
    console.log('Initializing Time Off Requests tab...');
    await loadTimeOffRequests();
    await populateTimeOffEmployeeFilter();
}

// Load all time off requests
async function loadTimeOffRequests() {
    try {
        const status = document.getElementById('timeOffStatusFilter')?.value || 'pending';

        const response = await fetch(`/api/schedules/time-off-requests?status=${status}`);

        if (!response.ok) {
            throw new Error('Failed to fetch time off requests');
        }

        const data = await response.json();
        console.log('Time off requests loaded:', data);

        allTimeOffRequests = data.requests || [];
        filterTimeOffRequests();
    } catch (error) {
        console.error('Error loading time off requests:', error);
        showNotification('Error loading time off requests', 'error');
        allTimeOffRequests = [];
        displayTimeOffRequests();
    }
}

// Populate employee filter dropdown
async function populateTimeOffEmployeeFilter() {
    const filter = document.getElementById('timeOffEmployeeFilter');
    if (!filter) return;

    // Get unique employees from requests
    const uniqueEmployees = new Map();
    allTimeOffRequests.forEach(request => {
        if (request.employee_id && request.employee_name) {
            uniqueEmployees.set(request.employee_id, request.employee_name);
        }
    });

    filter.innerHTML = '<option value="all">All Employees</option>';
    Array.from(uniqueEmployees.entries())
        .sort((a, b) => a[1].localeCompare(b[1]))
        .forEach(([id, name]) => {
            filter.innerHTML += `<option value="${id}">${name}</option>`;
        });
}

// Filter time off requests
function filterTimeOffRequests() {
    const employeeFilter = document.getElementById('timeOffEmployeeFilter')?.value || 'all';
    const statusFilter = document.getElementById('timeOffStatusFilter')?.value || 'all';
    const typeFilter = document.getElementById('timeOffTypeFilter')?.value || 'all';

    filteredTimeOffRequests = allTimeOffRequests.filter(request => {
        if (employeeFilter !== 'all' && request.employee_id != employeeFilter) return false;
        if (statusFilter !== 'all' && request.status !== statusFilter) return false;
        if (typeFilter !== 'all' && request.request_type !== typeFilter) return false;
        return true;
    });

    // Apply sorting
    sortTimeOffArray(filteredTimeOffRequests);

    timeOffCurrentPage = 1;
    displayTimeOffRequests();
}

// Display time off requests
function displayTimeOffRequests() {
    const tbody = document.getElementById('timeOffRequestsTableBody');
    if (!tbody) return;

    if (filteredTimeOffRequests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">No time off requests found</td></tr>';
        updateTimeOffPagination();
        return;
    }

    const startIdx = (timeOffCurrentPage - 1) * timeOffPageSize;
    const endIdx = timeOffPageSize === 'all' ? filteredTimeOffRequests.length : Math.min(startIdx + parseInt(timeOffPageSize), filteredTimeOffRequests.length);
    const pageRequests = filteredTimeOffRequests.slice(startIdx, endIdx);

    tbody.innerHTML = pageRequests.map(request => {
        const startDate = new Date(request.start_date).toLocaleDateString();
        const endDate = new Date(request.end_date).toLocaleDateString();

        const statusClass = request.status === 'approved' ? 'status-active' :
                          request.status === 'denied' ? 'status-inactive' :
                          'status-pending';

        const statusText = request.status.charAt(0).toUpperCase() + request.status.slice(1);

        const actions = request.status === 'pending' ?
            `<button onclick="approveTimeOffRequest(${request.id})" class="btn-approve" style="background: #10b981; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; margin-right: 5px;">Approve</button>
             <button onclick="denyTimeOffRequest(${request.id})" class="btn-deny" style="background: #ef4444; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer;">Deny</button>` :
            `<span style="color: #9ca3af;">—</span>`;

        const displayReason = request.status === 'denied' && request.reason
            ? request.reason
            : (request.admin_notes || request.reason || '—');

        return `
            <tr>
                <td>${request.employee_name || 'Unknown'}</td>
                <td>${request.position || '—'}</td>
                <td>${startDate}</td>
                <td>${endDate}</td>
                <td>${capitalizeFirst(request.request_type)}</td>
                <td>${request.total_hours} hrs</td>
                <td><span class="${statusClass}">${statusText}</span></td>
                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">${displayReason}</td>
                <td>${actions}</td>
            </tr>
        `;
    }).join('');

    updateTimeOffPagination();
}

// Approve time off request
async function approveTimeOffRequest(requestId) {
    const notes = prompt('Admin notes (optional):');
    if (notes === null) return; // User cancelled

    try {
        const response = await fetch(`/api/schedules/time-off-requests/${requestId}/approve`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ admin_notes: notes })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Time off request approved successfully', 'success');
            await loadTimeOffRequests();
        } else {
            showNotification(data.error || 'Error approving request', 'error');
        }
    } catch (error) {
        console.error('Error approving time off request:', error);
        showNotification('Error approving request', 'error');
    }
}

// Deny time off request
async function denyTimeOffRequest(requestId) {
    const reason = prompt('Reason for denial (required):');
    if (!reason || reason.trim() === '') {
        showNotification('Reason for denial is required', 'error');
        return;
    }

    const notes = prompt('Admin notes (optional):');

    try {
        const response = await fetch(`/api/schedules/time-off-requests/${requestId}/deny`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reason: reason.trim(),
                admin_notes: notes || ''
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Time off request denied', 'success');
            await loadTimeOffRequests();
        } else {
            showNotification(data.error || 'Error denying request', 'error');
        }
    } catch (error) {
        console.error('Error denying time off request:', error);
        showNotification('Error denying request', 'error');
    }
}

// Sort time off table
function sortTimeOffTable(columnIndex, type) {
    if (timeOffSort.column === columnIndex) {
        timeOffSort.order = timeOffSort.order === 'asc' ? 'desc' : 'asc';
    } else {
        timeOffSort.column = columnIndex;
        timeOffSort.type = type;
        timeOffSort.order = 'asc';
    }

    sortTimeOffArray(filteredTimeOffRequests);
    displayTimeOffRequests();
    updateSortArrows('timeOffRequestsTable', columnIndex, timeOffSort.order);
}

// Sort array based on current sort settings
function sortTimeOffArray(array) {
    array.sort((a, b) => {
        let aVal, bVal;

        switch (timeOffSort.column) {
            case 0: // Employee
                aVal = a.employee_name || '';
                bVal = b.employee_name || '';
                break;
            case 1: // Position
                aVal = a.position || '';
                bVal = b.position || '';
                break;
            case 2: // Start Date
                aVal = new Date(a.start_date);
                bVal = new Date(b.start_date);
                break;
            case 3: // End Date
                aVal = new Date(a.end_date);
                bVal = new Date(b.end_date);
                break;
            case 4: // Type
                aVal = a.request_type || '';
                bVal = b.request_type || '';
                break;
            case 5: // Hours
                aVal = a.total_hours || 0;
                bVal = b.total_hours || 0;
                break;
            case 6: // Status
                aVal = a.status || '';
                bVal = b.status || '';
                break;
            default:
                return 0;
        }

        if (timeOffSort.type === 'number') {
            return timeOffSort.order === 'asc' ? aVal - bVal : bVal - aVal;
        } else if (timeOffSort.type === 'date') {
            return timeOffSort.order === 'asc' ? aVal - bVal : bVal - aVal;
        } else {
            const comparison = String(aVal).localeCompare(String(bVal));
            return timeOffSort.order === 'asc' ? comparison : -comparison;
        }
    });
}

// Pagination functions
function updateTimeOffPagination() {
    const totalItems = filteredTimeOffRequests.length;
    const pageSize = timeOffPageSize === 'all' ? totalItems : parseInt(timeOffPageSize);
    const totalPages = Math.ceil(totalItems / pageSize);

    const startIdx = (timeOffCurrentPage - 1) * pageSize + 1;
    const endIdx = Math.min(timeOffCurrentPage * pageSize, totalItems);

    const infoElement = document.getElementById('timeOffPaginationInfo');
    if (infoElement) {
        infoElement.textContent = `Showing ${startIdx}-${endIdx} of ${totalItems} items`;
    }

    // Update button states
    const firstBtn = document.getElementById('timeOffFirstPage');
    const prevBtn = document.getElementById('timeOffPrevPage');
    const nextBtn = document.getElementById('timeOffNextPage');
    const lastBtn = document.getElementById('timeOffLastPage');

    if (firstBtn) firstBtn.disabled = timeOffCurrentPage === 1;
    if (prevBtn) prevBtn.disabled = timeOffCurrentPage === 1;
    if (nextBtn) nextBtn.disabled = timeOffCurrentPage === totalPages || timeOffPageSize === 'all';
    if (lastBtn) lastBtn.disabled = timeOffCurrentPage === totalPages || timeOffPageSize === 'all';

    // Update page numbers
    const pageNumbersElement = document.getElementById('timeOffPageNumbers');
    if (pageNumbersElement && timeOffPageSize !== 'all') {
        let pageNumbersHTML = '';
        const maxButtons = 5;
        let startPage = Math.max(1, timeOffCurrentPage - Math.floor(maxButtons / 2));
        let endPage = Math.min(totalPages, startPage + maxButtons - 1);

        if (endPage - startPage + 1 < maxButtons) {
            startPage = Math.max(1, endPage - maxButtons + 1);
        }

        for (let i = startPage; i <= endPage; i++) {
            pageNumbersHTML += `<button class="${i === timeOffCurrentPage ? 'active' : ''}" onclick="goToTimeOffPage(${i})">${i}</button>`;
        }

        pageNumbersElement.innerHTML = pageNumbersHTML;
    }
}

function changeTimeOffPage(direction) {
    const totalPages = Math.ceil(filteredTimeOffRequests.length / (timeOffPageSize === 'all' ? filteredTimeOffRequests.length : parseInt(timeOffPageSize)));

    switch (direction) {
        case 'first':
            timeOffCurrentPage = 1;
            break;
        case 'prev':
            timeOffCurrentPage = Math.max(1, timeOffCurrentPage - 1);
            break;
        case 'next':
            timeOffCurrentPage = Math.min(totalPages, timeOffCurrentPage + 1);
            break;
        case 'last':
            timeOffCurrentPage = totalPages;
            break;
    }

    displayTimeOffRequests();
}

function goToTimeOffPage(page) {
    timeOffCurrentPage = page;
    displayTimeOffRequests();
}

function changeTimeOffPageSize() {
    const select = document.getElementById('timeOffPageSize');
    timeOffPageSize = select.value === 'all' ? 'all' : parseInt(select.value);
    timeOffCurrentPage = 1;
    displayTimeOffRequests();
}

// Helper function
function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Update sort arrows (reuse from existing dashboard code if available)
function updateSortArrows(tableId, columnIndex, order) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const arrows = table.querySelectorAll('.sort-arrow');
    arrows.forEach((arrow, index) => {
        if (index === columnIndex) {
            arrow.textContent = order === 'asc' ? '▲' : '▼';
        } else {
            arrow.textContent = '';
        }
    });
}
