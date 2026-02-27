// WONTECH Dashboard Core
// Tab switching, header stats, history/audit, format guide, dropdown toggle
// Domain modules: inventory.js, products.js, invoices.js, settings.js, counts.js, analytics.js
// Shared utilities: utils.js

// ========== SALES CSV HELPER FUNCTIONS ==========

/**
 * Toggle the CSV format guide visibility
 */
function toggleFormatGuide() {
    const guide = document.getElementById('format-guide');
    if (!guide) return;

    if (guide.style.display === 'none' || guide.style.display === '') {
        guide.style.display = 'block';
        event.target.textContent = '📋 Hide Format Guide';
    } else {
        guide.style.display = 'none';
        event.target.textContent = '📋 Show Format Guide';
    }
}

// ========== HISTORY PAGINATION FUNCTIONS ==========

function changeHistoryPageSize() {
    const select = document.getElementById('historyPageSize');
    paginationState.history.pageSize = select.value;
    paginationState.history.currentPage = 1;
    renderHistoryTable();
}

function changeHistoryPage(direction) {
    const state = paginationState.history;
    const totalPages = getTotalPages('history');

    switch(direction) {
        case 'first':
            state.currentPage = 1;
            break;
        case 'prev':
            state.currentPage = Math.max(1, state.currentPage - 1);
            break;
        case 'next':
            state.currentPage = Math.min(totalPages, state.currentPage + 1);
            break;
        case 'last':
            state.currentPage = totalPages;
            break;
    }

    renderHistoryTable();
}

// ========== INITIALIZATION ==========

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Determine which tab is active and load appropriate data
    const activeTab = document.querySelector('.tab-content.active');
    const tabId = activeTab ? activeTab.id : null;

    // Check if we're in the employee/attendance section
    const isEmployeeSection = tabId === 'employees-tab' ||
                              tabId === 'attendance-tab' ||
                              tabId === 'schedules-tab' ||
                              tabId === 'time-off-requests-tab' ||
                              tabId === 'payroll-tab';

    // Load header stats based on section
    if (isEmployeeSection) {
        loadEmployeeHeaderStats();
    } else {
        loadInventoryHeaderStats();
    }

    // Load tab-specific data
    if (activeTab) {
        if (tabId === 'inventory-tab') {
            loadInventory();
            loadFilters();
            loadCategoriesList();
        } else if (tabId === 'schedules-tab') {
            if (typeof initAdminSchedules === 'function') {
                initAdminSchedules();
            }
        } else if (tabId === 'employees-tab') {
            if (typeof loadEmployees === 'function') {
                loadEmployees();
            }
        } else if (tabId === 'attendance-tab') {
            if (typeof loadAttendance === 'function') {
                loadAttendance();
            }
        } else if (tabId === 'time-off-requests-tab') {
            if (typeof initializeTimeOffTab === 'function') {
                initializeTimeOffTab();
            }
        } else if (tabId === 'payroll-tab') {
            if (typeof initializePayrollTab === 'function') {
                initializePayrollTab();
            }
        }
    } else {
        // Default to inventory if no active tab found
        loadInventory();
        loadFilters();
        loadCategoriesList();
    }
});

// ========== TAB SWITCHING ==========

// Tab switching
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active class from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName + '-tab').classList.add('active');

    // Add active class to clicked button
    event.target.classList.add('active');

    // Refresh header stats based on new active tab
    loadHeaderStats();

    // Load data for the tab
    switch(tabName) {
        case 'inventory':
            loadInventory();
            break;
        case 'products':
            loadProducts();
            break;
        case 'invoices':
            loadInvoices();
            break;
        case 'counts':
            loadCounts();
            break;
        case 'history':
            loadHistory();
            break;
        case 'analytics':
            loadAnalytics();
            break;
        case 'sales':
            // Initialize sales analytics dashboard
            if (typeof initSalesAnalytics === 'function') {
                initSalesAnalytics();
            }
            break;
        case 'settings':
            loadSettings();
            break;
        case 'employees':
            if (typeof loadEmployees === 'function') {
                loadEmployees();
            }
            break;
        case 'attendance':
            if (typeof loadAttendance === 'function') {
                loadAttendance();
            }
            break;
        case 'schedules':
            if (typeof initAdminSchedules === 'function') {
                initAdminSchedules();
            }
            break;
        case 'time-off-requests':
            if (typeof initializeTimeOffTab === 'function') {
                initializeTimeOffTab();
            }
            break;
        case 'payroll':
            if (typeof initializePayrollTab === 'function') {
                initializePayrollTab();
            }
            break;
        case 'labor-analytics':
            if (typeof initLaborAnalytics === 'function') {
                initLaborAnalytics();
            }
            break;
    }

    // Update header stats to reflect current section - pass tab name directly
    updateHeaderStatsForTab(tabName);
}

// ========== HEADER STATS ==========

// Update stats based on tab name
function updateHeaderStatsForTab(tabName) {
    const employeeTabs = ['employees', 'attendance', 'schedules', 'time-off-requests', 'payroll', 'labor-analytics'];
    if (employeeTabs.includes(tabName)) {
        loadEmployeeHeaderStats();
    } else {
        loadInventoryHeaderStats();
    }
}

// Load header statistics
async function loadHeaderStats() {
    // Find the currently active tab
    const activeTab = document.querySelector('.tab-content.active');
    const tabId = activeTab ? activeTab.id : null;

    // Employee section tabs
    const employeeTabs = ['employees-tab', 'attendance-tab', 'schedules-tab', 'time-off-requests-tab', 'payroll-tab', 'labor-analytics-tab'];

    if (employeeTabs.includes(tabId)) {
        await loadEmployeeHeaderStats();
    } else {
        await loadInventoryHeaderStats();
    }
}

async function loadInventoryHeaderStats() {
    try {
        const response = await fetch('/api/inventory/summary');
        const data = await response.json();

        // Check if there's any inventory data
        if (!data || data.total_items === 0 || data.total_items === null || data.total_items === undefined) {
            document.getElementById('headerStats').innerHTML = '📦 No inventory data available yet';
            return;
        }

        const statsHTML = `
            💰 Total Value: ${formatCurrency(data.total_value)} |
            📦 ${data.total_items} Items |
            🏷️ ${data.unique_ingredients} Unique Ingredients
        `;

        document.getElementById('headerStats').innerHTML = statsHTML;
    } catch (error) {
        console.error('Error loading inventory stats:', error);
        document.getElementById('headerStats').innerHTML = '📦 No inventory data available yet';
    }
}

async function loadEmployeeHeaderStats() {
    try {
        // Get employee count
        const employeesResponse = await fetch('/api/employees');
        const employeesData = await employeesResponse.json();
        const employees = employeesData.employees || [];
        const activeEmployees = employees.filter(e => e.status === 'active').length;

        // Get currently working count from attendance
        let clockedInCount = 0;
        const attendanceResponse = await fetch('/api/attendance/history');
        if (attendanceResponse.ok) {
            const attendanceData = await attendanceResponse.json();
            if (attendanceData.success) {
                const attendance = attendanceData.attendance || [];
                clockedInCount = attendance.filter(a =>
                    a.status === 'clocked_in' || a.status === 'on_break'
                ).length;
            }
        }

        // Get today's schedule count
        let todaySchedules = 0;
        const today = new Date().toISOString().split('T')[0];
        const scheduleResponse = await fetch(`/api/schedules?start_date=${today}&end_date=${today}`);
        if (scheduleResponse.ok) {
            const scheduleData = await scheduleResponse.json();
            if (scheduleData.success) {
                todaySchedules = (scheduleData.schedules || []).length;
            }
        }

        const statsHTML = `
            👥 ${activeEmployees} Active Employees |
            ⏰ ${clockedInCount} Currently Working |
            📅 ${todaySchedules} Shifts Today
        `;

        document.getElementById('headerStats').innerHTML = statsHTML;
    } catch (error) {
        console.error('Error loading employee stats:', error);
        document.getElementById('headerStats').innerHTML = '👥 Employee Management';
    }
}

// ========== DROPDOWN TOGGLE ==========

// Toggle dropdown for brands/suppliers
function toggleDropdown(event, dropdownId) {
    event.stopPropagation();

    // Close all other dropdowns
    document.querySelectorAll('.dropdown-content.active').forEach(dropdown => {
        if (dropdown.id !== dropdownId) {
            dropdown.classList.remove('active');
        }
    });

    // Toggle current dropdown
    const dropdown = document.getElementById(dropdownId);
    dropdown.classList.toggle('active');
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.matches('.dropdown-toggle')) {
        document.querySelectorAll('.dropdown-content.active').forEach(dropdown => {
            dropdown.classList.remove('active');
        });
    }
});

// ============================================================================
// HISTORY / AUDIT LOG FUNCTIONS
// ============================================================================

async function loadHistory() {
    try {
        // Load statistics
        const statsResponse = await fetch('/api/audit/stats');
        const stats = await statsResponse.json();

        document.getElementById('totalEvents').textContent = stats.action_counts.reduce((sum, item) => sum + item.count, 0);
        document.getElementById('recentEvents').textContent = stats.recent_activity_count;

        // Load audit logs
        const actionFilter = document.getElementById('historyActionFilter')?.value || 'all';
        const entityFilter = document.getElementById('historyEntityFilter')?.value || 'all';
        const dateFrom = document.getElementById('historyDateFrom')?.value || '';
        const dateTo = document.getElementById('historyDateTo')?.value || '';

        let url = '/api/audit/all?limit=500';
        if (actionFilter !== 'all') {
            url += `&action_type=${actionFilter}`;
        }
        if (entityFilter !== 'all') {
            url += `&entity_type=${entityFilter}`;
        }
        if (dateFrom) {
            url += `&date_from=${dateFrom}`;
        }
        if (dateTo) {
            url += `&date_to=${dateTo}`;
        }

        const response = await fetch(url);
        const logs = await response.json();

        // Store data in pagination state
        paginationState.history.allData = logs;
        paginationState.history.totalItems = logs.length;
        paginationState.history.currentPage = 1;

        // Render the table with pagination
        renderHistoryTable();

    } catch (error) {
        console.error('Error loading history:', error);
        const tbody = document.getElementById('historyTableBody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" class="error">Error loading history</td></tr>';
        }
    }
}

// Render history table with pagination
function renderHistoryTable() {
    const tbody = document.getElementById('historyTableBody');
    if (!tbody) return;

    const logs = getPaginatedData('history');

    if (paginationState.history.totalItems === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">No history found</td></tr>';
        updatePaginationInfo('history', 'historyPaginationInfo');
        return;
    }

    tbody.innerHTML = logs.map(log => {
        const formattedTime = formatDateTime(log.timestamp);
        const actionBadge = getActionBadge(log.action_type);

        return `
            <tr>
                <td>${formattedTime}</td>
                <td>${actionBadge}</td>
                <td><span class="badge badge-secondary">${log.entity_type}</span></td>
                <td><strong>${log.entity_reference || '-'}</strong></td>
                <td>${log.details || '-'}</td>
                <td>${log.user || 'System'}</td>
                <td>${log.ip_address || '-'}</td>
            </tr>
        `;
    }).join('');

    // Update pagination controls
    updatePaginationInfo('history', 'historyPaginationInfo');
    renderPageNumbers('history', 'historyPageNumbers');
    updatePaginationButtons('history', 'history');
}

function getActionBadge(actionType) {
    const badges = {
        'INVOICE_CREATED': '<span class="badge badge-success">Invoice Created</span>',
        'INVOICE_IMPORTED': '<span class="badge badge-info">Invoice Imported</span>',
        'INVOICE_DELETED': '<span class="badge badge-danger">Invoice Deleted</span>',
        'INVOICE_PAYMENT_PAID': '<span class="badge badge-success">Invoice Paid</span>',
        'INVOICE_PAYMENT_UNPAID': '<span class="badge badge-warning">Invoice Unpaid</span>',
        'INVOICE_PAYMENT_PARTIAL': '<span class="badge badge-info">Invoice Partial Payment</span>',
        'COUNT_CREATED': '<span class="badge badge-success">Count Created</span>',
        'COUNT_DELETED': '<span class="badge badge-warning">Count Deleted</span>',
        'ITEM_CREATED': '<span class="badge badge-success">Item Created</span>',
        'ITEM_DEACTIVATED': '<span class="badge badge-danger">Item Deactivated</span>',
        'ITEM_REACTIVATED': '<span class="badge badge-success">Item Reactivated</span>',
        'BRAND_UPDATED': '<span class="badge badge-info">Brand Updated</span>',
        'SUPPLIER_UPDATED': '<span class="badge badge-info">Supplier Updated</span>',
        'SUPPLIER_CREATED': '<span class="badge badge-success">Supplier Created</span>'
    };
    return badges[actionType] || `<span class="badge badge-secondary">${actionType}</span>`;
}

function sortHistoryTable(columnIndex) {
    // Simple table sorting implementation
    const table = document.getElementById('historyTable');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    const isAscending = table.dataset.sortOrder === 'asc';
    table.dataset.sortOrder = isAscending ? 'desc' : 'asc';

    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex]?.textContent.trim() || '';
        const bValue = b.cells[columnIndex]?.textContent.trim() || '';

        if (isAscending) {
            return aValue.localeCompare(bValue);
        } else {
            return bValue.localeCompare(aValue);
        }
    });

    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

// ========== HISTORY DATE FILTERS ==========

function clearHistoryDateFilters() {
    document.getElementById('historyDateFrom').value = '';
    document.getElementById('historyDateTo').value = '';
    loadHistory();
}

function applyHistoryDateFilter() {
    const dateFrom = document.getElementById('historyDateFrom').value;
    const dateTo = document.getElementById('historyDateTo').value;
    const btn = event.target;

    // Validate dates if both are provided
    if (dateFrom && dateTo && new Date(dateTo) < new Date(dateFrom)) {
        showMessage('End date must be after or equal to start date', 'error');
        return;
    }

    // Show loading state
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Loading...';
    btn.disabled = true;

    loadHistory().then(() => {
        btn.innerHTML = '✓ Applied!';
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 1500);
    }).catch(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}
