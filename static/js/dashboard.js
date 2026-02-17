// Firing Up Inventory Dashboard JavaScript

// ========== PAGINATION STATE ==========
const paginationState = {
    inventory: {
        currentPage: 1,
        pageSize: 25,
        totalItems: 0,
        allData: []
    },
    products: {
        currentPage: 1,
        pageSize: 10,
        totalItems: 0,
        allData: []
    },
    invoices: {
        currentPage: 1,
        pageSize: 25,
        totalItems: 0,
        allData: []
    },
    unreconciled: {
        currentPage: 1,
        pageSize: 10,
        totalItems: 0,
        allData: []
    },
    history: {
        currentPage: 1,
        pageSize: 25,
        totalItems: 0,
        allData: []
    }
};

// Helper function to format timestamps
function formatDateTime(dateString) {
    if (!dateString) return '-';

    try {
        const date = new Date(dateString.replace(' ', 'T'));
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    } catch (error) {
        console.error('Error formatting datetime:', dateString, error);
        return dateString;
    }
}

// Helper function to format date only (no time)
function formatDateOnly(dateString) {
    if (!dateString) return '-';

    try {
        // Parse date as local time to avoid timezone shift for date-only values
        const parts = dateString.split(/[- :T]/);
        const year = parseInt(parts[0]);
        const month = parseInt(parts[1]) - 1; // Month is 0-indexed
        const day = parseInt(parts[2]);

        const date = new Date(year, month, day);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    } catch (error) {
        console.error('Error formatting date:', dateString, error);
        return dateString;
    }
}

// ========== CATEGORY STYLING ==========

/**
 * Get category styling (icon and color class) for visual distinction
 */
function getCategoryStyle(category) {
    const categoryStyles = {
        'Proteins': { icon: '🥩', colorClass: 'category-proteins' },
        'Seafood': { icon: '🦞', colorClass: 'category-seafood' },
        'Dairy': { icon: '🧀', colorClass: 'category-dairy' },
        'Produce': { icon: '🥬', colorClass: 'category-produce' },
        'Vegetables': { icon: '🥕', colorClass: 'category-vegetables' },
        'Fruits': { icon: '🍎', colorClass: 'category-fruits' },
        'Grains & Pasta': { icon: '🌾', colorClass: 'category-grains' },
        'Bread & Bakery': { icon: '🍞', colorClass: 'category-bread' },
        'Baking': { icon: '🧁', colorClass: 'category-baking' },
        'Spices & Seasonings': { icon: '🌶️', colorClass: 'category-spices' },
        'Herbs': { icon: '🌿', colorClass: 'category-herbs' },
        'Oils & Fats': { icon: '🫒', colorClass: 'category-oils' },
        'Sauces & Condiments': { icon: '🍯', colorClass: 'category-sauces' },
        'Beverages': { icon: '☕', colorClass: 'category-beverages' },
        'Canned Goods': { icon: '🥫', colorClass: 'category-canned' },
        'Frozen Foods': { icon: '❄️', colorClass: 'category-frozen' },
        'Prepared Foods': { icon: '🍱', colorClass: 'category-prepared' },
        'Snacks': { icon: '🍿', colorClass: 'category-snacks' },
        'Desserts': { icon: '🍰', colorClass: 'category-desserts' },
        'Specialty': { icon: '⭐', colorClass: 'category-specialty' },
        'Cleaning Supplies': { icon: '🧼', colorClass: 'category-cleaning' },
        'Paper Products': { icon: '🧻', colorClass: 'category-paper' },
        'Disposables': { icon: '🥤', colorClass: 'category-disposables' },
        'Uncategorized': { icon: '📦', colorClass: 'category-uncategorized' }
    };

    return categoryStyles[category] || { icon: '📦', colorClass: 'category-default' };
}

/**
 * Format category badge with icon and color
 */
function formatCategoryBadge(category, itemId) {
    const style = getCategoryStyle(category);
    const escapedCategory = category.replace(/'/g, "\\'");

    // Add size class based on category name length
    const sizeClass = category.length > 18 ? 'category-long' : category.length > 12 ? 'category-medium' : '';

    return `<span class="badge category-badge ${style.colorClass} ${sizeClass} category-editable"
                  onclick="showCategoryDropdown(${itemId}, '${escapedCategory}')"
                  title="Click to change category">
                ${style.icon} ${category}
            </span>`;
}

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

// ========== PAGINATION HELPER FUNCTIONS ==========

/**
 * Get paginated slice of data
 */
function getPaginatedData(tableName) {
    const state = paginationState[tableName];
    const pageSize = state.pageSize === 'all' ? state.totalItems : parseInt(state.pageSize);
    const startIndex = (state.currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;

    return state.allData.slice(startIndex, endIndex);
}

/**
 * Calculate total pages
 */
function getTotalPages(tableName) {
    const state = paginationState[tableName];
    if (state.pageSize === 'all') return 1;
    return Math.ceil(state.totalItems / parseInt(state.pageSize));
}

/**
 * Update pagination info text
 */
function updatePaginationInfo(tableName, elementId) {
    const state = paginationState[tableName];
    const element = document.getElementById(elementId);

    if (!element || state.totalItems === 0) {
        if (element) element.textContent = 'Showing 0-0 of 0 items';
        return;
    }

    const pageSize = state.pageSize === 'all' ? state.totalItems : parseInt(state.pageSize);
    const startIndex = (state.currentPage - 1) * pageSize + 1;
    const endIndex = Math.min(startIndex + pageSize - 1, state.totalItems);

    element.textContent = `Showing ${startIndex}-${endIndex} of ${state.totalItems} items`;
}

/**
 * Render page number buttons
 */
function renderPageNumbers(tableName, elementId) {
    const state = paginationState[tableName];
    const element = document.getElementById(elementId);

    if (!element) return;

    const totalPages = getTotalPages(tableName);

    if (totalPages <= 1) {
        element.innerHTML = '';
        return;
    }

    let html = '';
    const maxButtons = 5;
    let startPage = Math.max(1, state.currentPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);

    // Adjust startPage if we're near the end
    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === state.currentPage ? 'active' : '';
        html += `<button class="page-number ${activeClass}" onclick="goToPage('${tableName}', ${i})">${i}</button>`;
    }

    element.innerHTML = html;
}

/**
 * Update pagination button states
 */
function updatePaginationButtons(tableName, prefix) {
    const state = paginationState[tableName];
    const totalPages = getTotalPages(tableName);

    const firstBtn = document.getElementById(`${prefix}FirstPage`);
    const prevBtn = document.getElementById(`${prefix}PrevPage`);
    const nextBtn = document.getElementById(`${prefix}NextPage`);
    const lastBtn = document.getElementById(`${prefix}LastPage`);

    if (firstBtn) firstBtn.disabled = state.currentPage === 1;
    if (prevBtn) prevBtn.disabled = state.currentPage === 1;
    if (nextBtn) nextBtn.disabled = state.currentPage >= totalPages;
    if (lastBtn) lastBtn.disabled = state.currentPage >= totalPages;
}

/**
 * Go to specific page
 */
function goToPage(tableName, pageNumber) {
    const state = paginationState[tableName];
    const totalPages = getTotalPages(tableName);

    state.currentPage = Math.max(1, Math.min(pageNumber, totalPages));

    // Call the appropriate render function
    const renderFunctions = {
        'inventory': renderInventoryTable,
        'products': renderProductsTable,
        'invoices': renderInvoicesTable,
        'unreconciled': renderUnreconciledInvoicesTable,
        'history': renderHistoryTable
    };

    if (renderFunctions[tableName]) {
        renderFunctions[tableName]();
    }
}

// ========== INVENTORY PAGINATION FUNCTIONS ==========

function changeInventoryPageSize() {
    const select = document.getElementById('inventoryPageSize');
    paginationState.inventory.pageSize = select.value;
    paginationState.inventory.currentPage = 1;
    renderInventoryTable();
}

function changeInventoryPage(direction) {
    const state = paginationState.inventory;
    const totalPages = getTotalPages('inventory');

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

    renderInventoryTable();
}

// ========== PRODUCTS PAGINATION FUNCTIONS ==========

function changeProductsPageSize() {
    const select = document.getElementById('productsPageSize');
    paginationState.products.pageSize = select.value;
    paginationState.products.currentPage = 1;
    renderProductsTable();
}

function changeProductsPage(direction) {
    const state = paginationState.products;
    const totalPages = getTotalPages('products');

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

    renderProductsTable();
}

// ========== INVOICES PAGINATION FUNCTIONS ==========

function changeInvoicesPageSize() {
    const select = document.getElementById('invoicesPageSize');
    paginationState.invoices.pageSize = select.value;
    paginationState.invoices.currentPage = 1;
    renderInvoicesTable();
}

function changeInvoicesPage(direction) {
    const state = paginationState.invoices;
    const totalPages = getTotalPages('invoices');

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

    renderInvoicesTable();
}

// ========== UNRECONCILED INVOICES PAGINATION FUNCTIONS ==========

function changeUnreconciledPageSize() {
    const select = document.getElementById('unreconciledPageSize');
    paginationState.unreconciled.pageSize = select.value;
    paginationState.unreconciled.currentPage = 1;
    renderUnreconciledInvoicesTable();
}

function changeUnreconciledPage(direction) {
    const state = paginationState.unreconciled;
    const totalPages = getTotalPages('unreconciled');

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

    renderUnreconciledInvoicesTable();
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

// Load inventory (consolidated view - groups by ingredient name)
async function loadInventory() {
    try {
        const status = document.getElementById('statusFilter')?.value || 'active';
        const category = document.getElementById('categoryFilter').value;
        const ingredient = document.getElementById('ingredientFilter')?.value || 'all';
        const supplier = document.getElementById('supplierFilter')?.value || 'all';
        const brand = document.getElementById('brandFilter')?.value || 'all';
        const dateFrom = document.getElementById('dateFrom')?.value || '';
        const dateTo = document.getElementById('dateTo')?.value || '';

        const params = new URLSearchParams({
            status: status,
            category: category
        });

        const response = await fetch(`/api/inventory/consolidated?${params}`);
        let items = await response.json();

        // Apply client-side filters for ingredient/supplier/brand
        if (ingredient !== 'all') {
            items = items.filter(item => item.ingredient_name === ingredient);
        }

        if (supplier !== 'all') {
            items = items.filter(item => item.suppliers.includes(supplier));
        }

        if (brand !== 'all') {
            items = items.filter(item => item.brands.includes(brand));
        }

        // Apply date range filter
        if (dateFrom || dateTo) {
            items = items.filter(item => {
                // Get all dates from variants
                const allDates = item.variants.map(v => v.date_received).filter(d => d);
                if (allDates.length === 0) return false;

                // Check if any variant's date falls within the range
                return allDates.some(date => {
                    if (dateFrom && date < dateFrom) return false;
                    if (dateTo && date > dateTo) return false;
                    return true;
                });
            });
        }

        // Store data in pagination state
        paginationState.inventory.allData = items;
        paginationState.inventory.totalItems = items.length;
        paginationState.inventory.currentPage = 1;

        // Render the table with pagination
        renderInventoryTable();
    } catch (error) {
        console.error('Error loading inventory:', error);
        document.getElementById('inventoryTableBody').innerHTML =
            '<tr><td colspan="10" class="text-danger">Error loading inventory</td></tr>';
    }
}

// Global map to store item data for easy lookup
window.inventoryItemsMap = window.inventoryItemsMap || new Map();

// Render inventory table with pagination (CONSOLIDATED VIEW)
function renderInventoryTable() {
    const tbody = document.getElementById('inventoryTableBody');
    const items = getPaginatedData('inventory');

    if (paginationState.inventory.totalItems === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center">No items match the selected filters</td></tr>';
        updatePaginationInfo('inventory', 'inventoryPaginationInfo');
        return;
    }

    // Clear the map and rebuild it
    window.inventoryItemsMap.clear();

    tbody.innerHTML = items.map((item, index) => {
        // Generate a safe unique key using index
        const itemKey = `item_${index}`;
        window.inventoryItemsMap.set(itemKey, item);

        const escapedName = item.ingredient_name.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
        const variantCount = item.variant_count;
        const hasMultipleVariants = variantCount > 1;

        // Create brand dropdown
        const brandOptions = item.brands.map(brand =>
            `<option value="${brand}">${brand}</option>`
        ).join('');
        const brandDropdown = hasMultipleVariants
            ? `<select class="variant-dropdown" onchange="updateVariantData(this, 'brand')" data-row-index="${index}">
                <option value="all">All (${variantCount})</option>
                ${brandOptions}
              </select>`
            : (item.brands[0] || '-');

        // Create supplier dropdown
        const supplierOptions = item.suppliers.map(supplier =>
            `<option value="${supplier}">${supplier}</option>`
        ).join('');
        const supplierDropdown = hasMultipleVariants
            ? `<select class="variant-dropdown" onchange="updateVariantData(this, 'supplier')" data-row-index="${index}">
                <option value="all">All (${item.suppliers.length})</option>
                ${supplierOptions}
              </select>`
            : (item.suppliers[0] || '-');

        return `
        <tr data-ingredient="${escapedName}" data-row-index="${index}" data-all-variants='${JSON.stringify(item.variants)}' data-current-brand="all" data-current-supplier="all">
            <td><strong>${item.ingredient_name}</strong></td>
            <td>${brandDropdown}</td>
            <td>${supplierDropdown}</td>
            <td>${formatCategoryBadge(item.category)}</td>
            <td class="text-right quantity-cell"><strong>${item.total_quantity.toFixed(2)}</strong></td>
            <td>${item.unit_of_measure}</td>
            <td class="text-right cost-cell">${formatCurrency(item.avg_unit_cost)}</td>
            <td class="text-right value-cell"><strong>${formatCurrency(item.total_value)}</strong></td>
            <td class="actions-cell">
                ${hasMultipleVariants
                    ? `<button class="btn-expand" onclick="expandVariantsFromMap('item_${index}')" title="View All ${variantCount} Variants">
                         <span style="font-weight: 700;">📋 ${variantCount}</span>
                       </button>`
                    : `<button class="btn-edit-dark" onclick="openEditIngredientModal(${item.variants[0].id})" title="Edit">
                         <span style="font-weight: 700;">✏️</span>
                       </button>
                       <button class="btn-delete-dark" onclick="confirmDeleteIngredient(${item.variants[0].id}, '${escapedName}')" title="Delete">
                         <span style="font-weight: 700;">🗑️</span>
                       </button>`
                }
            </td>
        </tr>
        `;
    }).join('');

    // Update pagination controls
    updatePaginationInfo('inventory', 'inventoryPaginationInfo');
    renderPageNumbers('inventory', 'inventoryPageNumbers');
    updatePaginationButtons('inventory', 'inventory');
}

// Update row data when brand/supplier dropdown changes
function updateVariantData(selectElement, filterType) {
    const row = selectElement.closest('tr');
    const rowIndex = parseInt(row.dataset.rowIndex);
    const allVariants = JSON.parse(row.dataset.allVariants);

    // Get current selections
    const brandSelect = row.querySelector('select[onchange*="brand"]');
    const supplierSelect = row.querySelector('select[onchange*="supplier"]');

    const selectedBrand = brandSelect ? brandSelect.value : 'all';
    const selectedSupplier = supplierSelect ? supplierSelect.value : 'all';

    // Update row data attributes
    row.dataset.currentBrand = selectedBrand;
    row.dataset.currentSupplier = selectedSupplier;

    // Filter variants based on selections
    let matchingVariants = allVariants;

    if (selectedBrand !== 'all') {
        matchingVariants = matchingVariants.filter(v => v.brand === selectedBrand);
    }

    if (selectedSupplier !== 'all') {
        matchingVariants = matchingVariants.filter(v => v.supplier_name === selectedSupplier);
    }

    // Calculate aggregated values
    if (matchingVariants.length === 0) {
        // No matches
        row.querySelector('.quantity-cell').innerHTML = '<strong>0.00</strong>';
        row.querySelector('.cost-cell').textContent = formatCurrency(0);
        row.querySelector('.value-cell').innerHTML = '<strong>' + formatCurrency(0) + '</strong>';
        row.style.background = '#fff3cd';
    } else {
        const totalQty = matchingVariants.reduce((sum, v) => sum + v.quantity_on_hand, 0);
        const totalValue = matchingVariants.reduce((sum, v) => sum + v.total_value, 0);
        const avgCost = totalValue / totalQty;

        row.querySelector('.quantity-cell').innerHTML = `<strong>${totalQty.toFixed(2)}</strong>`;
        row.querySelector('.cost-cell').textContent = formatCurrency(avgCost);
        row.querySelector('.value-cell').innerHTML = '<strong>' + formatCurrency(totalValue) + '</strong>';

        // Highlight filtered rows
        if (selectedBrand !== 'all' || selectedSupplier !== 'all') {
            row.style.background = 'rgba(102, 126, 234, 0.05)';
            row.style.borderLeft = '3px solid #667eea';
        } else {
            row.style.background = '';
            row.style.borderLeft = '';
        }
    }

    console.log(`Filtered to ${matchingVariants.length} variant(s): Brand=${selectedBrand}, Supplier=${selectedSupplier}`);
}

// Look up item from global map and expand variants
function expandVariantsFromMap(itemKey) {
    if (!window.inventoryItemsMap) {
        alert('Error: Inventory data not available. Please reload the page.');
        return;
    }

    const item = window.inventoryItemsMap.get(itemKey);

    if (!item) {
        alert(`Error: Could not find item with key "${itemKey}"`);
        return;
    }

    if (!item.variants || item.variants.length === 0) {
        alert(`Error: Item "${item.ingredient_name}" has no variants data`);
        return;
    }

    expandVariantsWithData(item);
}

// Wrapper function called from button - gets data from DOM
function expandVariantsFromButton(button) {
    const row = button.closest('tr');
    const itemDataJson = row.getAttribute('data-item-data');

    try {
        const item = JSON.parse(itemDataJson.replace(/&quot;/g, '"'));
        expandVariantsWithData(item);
    } catch (e) {
        console.error('Error parsing item data:', e);
        // Fallback to index-based lookup
        const rowIndex = parseInt(button.getAttribute('data-row-index'));
        expandVariants(rowIndex);
    }
}

// Expand to show all variants in a proper modal (index-based)
function expandVariants(rowIndex) {
    const items = paginationState.inventory.allData;

    if (!items || items.length === 0) {
        alert('Error: No inventory data available. Please reload the page.');
        return;
    }

    const item = items[rowIndex];

    if (!item) {
        alert(`Error: Could not find item at index ${rowIndex}. Total items: ${items.length}`);
        return;
    }

    if (!item.variants) {
        alert(`Error: Item "${item.ingredient_name}" has no variants data`);
        return;
    }

    expandVariantsWithData(item);
}

// Actual modal display logic
function expandVariantsWithData(item) {

    // Calculate totals
    const totalQty = item.variants.reduce((sum, v) => sum + v.quantity_on_hand, 0);
    const totalValue = item.variants.reduce((sum, v) => sum + v.total_value, 0);

    // Build variant table HTML
    let html = `
        <div style="margin-bottom: 20px;">
            <p><strong>Category:</strong> ${item.category}</p>
            <p><strong>Total Quantity:</strong> ${totalQty.toFixed(2)} ${item.unit_of_measure}</p>
            <p><strong>Total Value:</strong> ${formatCurrency(totalValue)}</p>
            <p><strong>Average Cost:</strong> ${formatCurrency(item.avg_unit_cost)} per ${item.unit_of_measure}</p>
        </div>

        <div style="max-height: 500px; overflow-y: auto;">
            <table class="variants-table" style="width: 100%; border-collapse: collapse;">
                <thead style="position: sticky; top: 0; background: #667eea; color: white; z-index: 1;">
                    <tr>
                        <th style="padding: 10px; text-align: left;">Code</th>
                        <th style="padding: 10px; text-align: left;">Brand</th>
                        <th style="padding: 10px; text-align: left;">Supplier</th>
                        <th style="padding: 10px; text-align: right;">Qty</th>
                        <th style="padding: 10px; text-align: right;">Unit Cost</th>
                        <th style="padding: 10px; text-align: right;">Total Value</th>
                        <th style="padding: 10px; text-align: left;">Location</th>
                        <th style="padding: 10px; text-align: left;">Date</th>
                        <th style="padding: 10px; text-align: left;">Lot #</th>
                        <th style="padding: 10px; text-align: center;">Actions</th>
                    </tr>
                </thead>
                <tbody>
    `;

    // Sort variants by brand, then supplier
    const sortedVariants = [...item.variants].sort((a, b) => {
        const brandCompare = (a.brand || '').localeCompare(b.brand || '');
        if (brandCompare !== 0) return brandCompare;
        return (a.supplier_name || '').localeCompare(b.supplier_name || '');
    });

    sortedVariants.forEach((v, idx) => {
        const rowStyle = idx % 2 === 0 ? 'background: #f8f9fa;' : 'background: white;';
        const escapedName = (v.brand || 'Unknown') + ' ' + item.ingredient_name;
        html += `
            <tr style="${rowStyle}">
                <td style="padding: 8px; border-bottom: 1px solid #ddd;"><code style="background: #e9ecef; padding: 2px 6px; border-radius: 4px;">${v.ingredient_code}</code></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">${v.brand || '-'}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">${v.supplier_name || '-'}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;"><strong>${v.quantity_on_hand.toFixed(2)}</strong> ${item.unit_of_measure}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">${formatCurrency(v.unit_cost)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;"><strong>${formatCurrency(v.total_value)}</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">${v.storage_location || '-'}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;"><small>${v.date_received || '-'}</small></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;"><small>${v.lot_number || '-'}</small></td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">
                    <button class="btn-edit-dark" onclick="openEditIngredientModal(${v.id})" title="Edit" style="margin-right: 5px;"><span style="font-weight: 700;">✏️</span></button>
                    <button class="btn-delete-dark" onclick="confirmDeleteIngredient(${v.id}, '${escapedName.replace(/'/g, "\\'")}')" title="Delete"><span style="font-weight: 700;">🗑️</span></button>
                </td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    // Open modal with proper title and close button
    openModal(
        `${item.ingredient_name} (${item.variant_count})`,
        html,
        [
            {
                text: 'Close',
                className: 'btn-secondary',
                onclick: () => closeModal()
            }
        ],
        true  // wide modal
    );
}

// Load filter dropdowns
async function loadFilters() {
    try {
        // Load ingredients
        const ingredientsResponse = await fetch('/api/filters/ingredients');
        const ingredients = await ingredientsResponse.json();

        const ingredientFilter = document.getElementById('ingredientFilter');
        ingredients.forEach(ingredient => {
            const option = document.createElement('option');
            option.value = ingredient;
            option.textContent = ingredient;
            ingredientFilter.appendChild(option);
        });

        // Load categories
        await loadCategoriesFilter();

        // Load suppliers
        await loadSuppliersFilter();

        // Load brands
        await loadBrandsFilter();
    } catch (error) {
        console.error('Error loading filters:', error);
    }
}

// Load suppliers filter dropdown
async function loadSuppliersFilter() {
    try {
        const suppliersResponse = await fetch('/api/filters/suppliers');
        const suppliers = await suppliersResponse.json();

        const supplierFilter = document.getElementById('supplierFilter');
        const currentValue = supplierFilter.value;

        // Clear existing options except the first one
        supplierFilter.innerHTML = '<option value="all">All Suppliers</option>';

        suppliers.forEach(supplier => {
            const option = document.createElement('option');
            option.value = supplier;
            option.textContent = supplier;
            supplierFilter.appendChild(option);
        });

        // Restore previous selection if it still exists
        if (currentValue && suppliers.includes(currentValue)) {
            supplierFilter.value = currentValue;
        }
    } catch (error) {
        console.error('Error loading suppliers filter:', error);
    }
}

// Load brands filter dropdown
async function loadBrandsFilter() {
    try {
        const brandsResponse = await fetch('/api/filters/brands');
        const brands = await brandsResponse.json();

        const brandFilter = document.getElementById('brandFilter');
        const currentValue = brandFilter.value;

        // Clear existing options except the first one
        brandFilter.innerHTML = '<option value="all">All Brands</option>';

        brands.forEach(brand => {
            const option = document.createElement('option');
            option.value = brand;
            option.textContent = brand;
            brandFilter.appendChild(option);
        });

        // Restore previous selection if it still exists
        if (currentValue && brands.includes(currentValue)) {
            brandFilter.value = currentValue;
        }
    } catch (error) {
        console.error('Error loading brands filter:', error);
    }
}

// Load categories filter dropdown
async function loadCategoriesFilter() {
    try {
        const categoriesResponse = await fetch('/api/filters/categories');
        const categories = await categoriesResponse.json();

        const categoryFilter = document.getElementById('categoryFilter');
        const currentValue = categoryFilter.value;

        // Clear existing options except the first one
        categoryFilter.innerHTML = '<option value="all">All Categories</option>';

        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            categoryFilter.appendChild(option);
        });

        // Restore previous selection if it still exists
        if (currentValue && categories.includes(currentValue)) {
            categoryFilter.value = currentValue;
        }
    } catch (error) {
        console.error('Error loading categories filter:', error);
    }
}

// Load products and costs
async function loadProducts() {
    try {
        const response = await fetch('/api/products/costs');
        const products = await response.json();

        // Store data in pagination state
        paginationState.products.allData = products;
        paginationState.products.totalItems = products.length;
        paginationState.products.currentPage = 1;

        // Render the table with pagination
        renderProductsTable();
    } catch (error) {
        console.error('Error loading products:', error);
        document.getElementById('productsTableBody').innerHTML =
            '<tr><td colspan="5" class="text-danger">Error loading products</td></tr>';
    }
}

// Render products table with pagination
function renderProductsTable() {
    const tbody = document.getElementById('productsTableBody');
    const products = getPaginatedData('products');

    if (paginationState.products.totalItems === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No products found</td></tr>';
        updatePaginationInfo('products', 'productsPaginationInfo');
        return;
    }

    tbody.innerHTML = products.map((product, index) => {
        const marginClass = product.margin_pct < 0 ? 'text-danger' : 'text-success';
        const rowId = `product-row-${index}`;
        const detailsId = `product-details-${index}`;
        return `
            <tr class="hoverable-row product-row" id="${rowId}"
                data-product-index="${index}"
                data-details-id="${detailsId}"
                data-row-id="${rowId}"
                data-product-id="${product.product_id}">
                <td class="product-name-cell">
                    <span class="expand-icon" id="${rowId}-icon">▶</span>
                    <strong>${product.product_name}</strong>
                </td>
                <td class="text-right">${formatCurrency(product.ingredient_cost)}</td>
                <td class="text-right"><strong>${formatCurrency(product.selling_price)}</strong></td>
                <td class="text-right ${marginClass}"><strong>${formatCurrency(product.gross_profit)}</strong></td>
                <td class="text-right ${marginClass}"><strong>${product.margin_pct}%</strong></td>
                <td class="actions-cell">
                    <button class="btn-edit-dark"
                            onclick="event.stopPropagation(); openEditProductModal(${product.product_id})"
                            title="Edit Product">
                        <span style="font-weight: 700;">✏️</span>
                    </button>
                    <button class="btn-delete-dark"
                            onclick="event.stopPropagation(); deleteProduct(${product.product_id}, '${product.product_name.replace(/'/g, "\\'")}')"
                            title="Delete Product">
                        <span style="font-weight: 700;">🗑️</span>
                    </button>
                </td>
            </tr>
            <tr class="product-details-row" id="${detailsId}" style="display: none;">
                <td colspan="6">
                    <div class="product-ingredients-container">
                        <div class="loading-spinner">Loading ingredients...</div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    // Add click event listeners to product rows (for expand/collapse)
    tbody.querySelectorAll('.product-row').forEach(row => {
        row.addEventListener('click', function(event) {
            // Don't expand if clicking on action buttons
            if (event.target.closest('.actions-cell')) {
                return;
            }
            const productIndex = parseInt(this.getAttribute('data-product-index'));
            const product = products[productIndex];
            const detailsId = this.getAttribute('data-details-id');
            const rowId = this.getAttribute('data-row-id');
            toggleProductDetails(product.product_name, detailsId, rowId);
        });
    });

    // Update pagination controls
    updatePaginationInfo('products', 'productsPaginationInfo');
    renderPageNumbers('products', 'productsPageNumbers');
    updatePaginationButtons('products', 'products');
}

// Toggle product ingredient details
async function toggleProductDetails(productName, detailsId, rowId) {
    const detailsRow = document.getElementById(detailsId);
    const icon = document.getElementById(`${rowId}-icon`);

    if (detailsRow.style.display === 'none') {
        // Expand - load ingredient details
        detailsRow.style.display = 'table-row';
        icon.textContent = '▼';

        // Check if already loaded
        const container = detailsRow.querySelector('.product-ingredients-container');
        if (container.querySelector('.loading-spinner')) {
            try {
                console.log('Fetching recipe for:', productName);
                const url = `/api/recipes/by-product/${encodeURIComponent(productName)}`;
                console.log('API URL:', url);
                const response = await fetch(url);
                const ingredients = await response.json();
                console.log('Received ingredients:', ingredients);

                if (ingredients.length === 0) {
                    container.innerHTML = '<p style="padding: 15px; color: #6c757d;">No recipe found for this product</p>';
                    return;
                }

                const totalCost = ingredients.reduce((sum, ing) => sum + ing.line_cost, 0);

                container.innerHTML = `
                    <div class="product-recipe-details">
                        <h4>Recipe Ingredients</h4>
                        <table class="ingredients-table">
                            <thead>
                                <tr>
                                    <th>Ingredient</th>
                                    <th>Quantity Needed</th>
                                    <th>Unit Cost</th>
                                    <th>Line Cost</th>
                                    <th>Notes</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${ingredients.map(ing => {
                                    let rows = `
                                        <tr class="${ing.is_composite ? 'composite-ingredient' : ''} ${ing.is_product ? 'product-ingredient' : ''}">
                                            <td>
                                                <strong>${ing.ingredient_name}</strong>
                                                ${ing.is_composite ? '<span class="composite-badge">🔧 Composite</span>' : ''}
                                                ${ing.is_product ? '<span class="badge badge-product">🍔 Product</span>' : ''}
                                            </td>
                                            <td class="text-right">${ing.quantity_needed} ${ing.unit_of_measure}</td>
                                            <td class="text-right">${formatCurrency(ing.unit_cost)}</td>
                                            <td class="text-right"><strong>${formatCurrency(ing.line_cost)}</strong></td>
                                            <td><small style="color: #6c757d;">${ing.notes || '-'}</small></td>
                                        </tr>
                                    `;

                                    // If composite, show sub-recipe
                                    if (ing.is_composite && ing.sub_recipe && ing.sub_recipe.length > 0) {
                                        rows += `
                                            <tr class="sub-recipe-row">
                                                <td colspan="5">
                                                    <div class="sub-recipe-container">
                                                        <div class="sub-recipe-header">↳ Made from:</div>
                                                        <table class="sub-recipe-table">
                                                            ${ing.sub_recipe.map(sub => `
                                                                <tr>
                                                                    <td>${sub.ingredient_name}</td>
                                                                    <td class="text-right">${sub.quantity_needed} ${sub.unit_of_measure}</td>
                                                                    <td class="text-right">${formatCurrency(sub.unit_cost)}</td>
                                                                    <td class="text-right">${formatCurrency(sub.line_cost)}</td>
                                                                    <td><small style="color: #6c757d;">${sub.notes || '-'}</small></td>
                                                                </tr>
                                                            `).join('')}
                                                        </table>
                                                    </div>
                                                </td>
                                            </tr>
                                        `;
                                    }

                                    return rows;
                                }).join('')}
                            </tbody>
                            <tfoot>
                                <tr>
                                    <td colspan="3" class="text-right"><strong>Total Ingredient Cost:</strong></td>
                                    <td class="text-right"><strong>${formatCurrency(totalCost)}</strong></td>
                                    <td></td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                `;
            } catch (error) {
                console.error('Error loading recipe details:', error);
                container.innerHTML = '<p style="padding: 15px; color: #dc3545;">Error loading recipe details</p>';
            }
        }
    } else {
        // Collapse
        detailsRow.style.display = 'none';
        icon.textContent = '▶';
    }
}

// Load invoices
async function loadInvoices() {
    try {
        // Load unreconciled invoices
        const unreconciledResponse = await fetch('/api/invoices/unreconciled');
        const unreconciled = await unreconciledResponse.json();

        // Store data in pagination state
        paginationState.unreconciled.allData = unreconciled;
        paginationState.unreconciled.totalItems = unreconciled.length;
        paginationState.unreconciled.currentPage = 1;

        // Render unreconciled invoices table
        renderUnreconciledInvoicesTable();

        // Load recent invoices with date filtering
        const dateFrom = document.getElementById('invoiceDateFrom')?.value || '';
        const dateTo = document.getElementById('invoiceDateTo')?.value || '';

        let url = '/api/invoices/recent';
        const params = new URLSearchParams();
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        if (params.toString()) url += '?' + params.toString();

        const recentResponse = await fetch(url);
        const recentData = await recentResponse.json();
        const recent = recentData.invoices || recentData;

        // Store data in pagination state
        paginationState.invoices.allData = recent;
        paginationState.invoices.totalItems = recentData.total_count || recent.length;
        paginationState.invoices.currentPage = 1;

        // Render recent invoices table
        renderInvoicesTable();
    } catch (error) {
        console.error('Error loading invoices:', error);
    }
}

// Render unreconciled invoices table with pagination
function renderUnreconciledInvoicesTable() {
    const unreconciledBody = document.getElementById('unreconciledTableBody');
    const unreconciled = getPaginatedData('unreconciled');

    if (paginationState.unreconciled.totalItems === 0) {
        unreconciledBody.innerHTML = '<tr><td colspan="7" class="text-center text-success">✓ All invoices reconciled</td></tr>';
        updatePaginationInfo('unreconciled', 'unreconciledPaginationInfo');
        return;
    }

    unreconciledBody.innerHTML = unreconciled.map(inv => {
        const escapedSupplier = inv.supplier_name.replace(/'/g, "\\'");
        const escapedInvoiceNum = inv.invoice_number.replace(/'/g, "\\'");
        return `
        <tr>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><strong>${inv.invoice_number}</strong></td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')">${inv.supplier_name}</td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')">${inv.invoice_date}</td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')">${inv.received_date}</td>
            <td class="text-right invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><strong>${formatCurrency(inv.total_amount)}</strong></td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><span class="badge badge-warning">${inv.payment_status}</span></td>
            <td class="actions-cell">
                <button class="btn-delete-dark" onclick="event.stopPropagation(); openDeleteInvoiceModal('${escapedInvoiceNum}', '${escapedSupplier}', ${inv.total_amount})" title="Delete"><span style="font-weight: 700;">🗑️</span></button>
            </td>
        </tr>
        `;
    }).join('');

    // Update pagination controls
    updatePaginationInfo('unreconciled', 'unreconciledPaginationInfo');
    renderPageNumbers('unreconciled', 'unreconciledPageNumbers');
    updatePaginationButtons('unreconciled', 'unreconciled');
}

// Render recent invoices table with pagination
function renderInvoicesTable() {
    const recentBody = document.getElementById('recentInvoicesTableBody');
    const recent = getPaginatedData('invoices');

    if (paginationState.invoices.totalItems === 0) {
        recentBody.innerHTML = '<tr><td colspan="7" class="text-center">No recent invoices</td></tr>';
        updatePaginationInfo('invoices', 'invoicesPaginationInfo');
        return;
    }

    recentBody.innerHTML = recent.map(inv => {
        const escapedSupplier = inv.supplier_name.replace(/'/g, "\\'");
        const escapedInvoiceNum = inv.invoice_number.replace(/'/g, "\\'");
        return `
        <tr>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><strong>${inv.invoice_number}</strong></td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')">${inv.supplier_name}</td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')">${inv.invoice_date}</td>
            <td class="text-right invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><strong>${formatCurrency(inv.total_amount)}</strong></td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><span class="badge ${inv.payment_status === 'PAID' ? 'badge-success' : 'badge-warning'}">${inv.payment_status}</span></td>
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><span class="badge ${inv.reconciled === 'YES' ? 'badge-success' : 'badge-danger'}">${inv.reconciled}</span></td>
            <td class="actions-cell">
                <button class="btn-delete-dark" onclick="event.stopPropagation(); openDeleteInvoiceModal('${escapedInvoiceNum}', '${escapedSupplier}', ${inv.total_amount})" title="Delete"><span style="font-weight: 700;">🗑️</span></button>
            </td>
        </tr>
        `;
    }).join('');

    // Update pagination controls
    updatePaginationInfo('invoices', 'invoicesPaginationInfo');
    renderPageNumbers('invoices', 'invoicesPageNumbers');
    updatePaginationButtons('invoices', 'invoices');
}

// Tooltip functionality
const tooltip = document.getElementById('tooltip');
const tooltipContent = document.getElementById('tooltipContent');

function showTooltip(content, event) {
    tooltipContent.innerHTML = content;
    tooltip.classList.add('active');
    positionTooltip(event);
}

function hideTooltip() {
    tooltip.classList.remove('active');
    tooltip.style.display = 'none';
}

function positionTooltip(event) {
    // Force a reflow to get accurate dimensions
    tooltip.style.left = '-9999px';
    tooltip.style.top = '-9999px';
    tooltip.style.display = 'block';

    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width;
    const tooltipHeight = tooltipRect.height;

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
    const scrollY = window.pageYOffset || document.documentElement.scrollTop;

    const offset = 15; // Distance from cursor

    // Start with default position (right and below cursor)
    let x = event.clientX + offset;
    let y = event.clientY + offset;

    // Check right boundary - if tooltip goes off right edge, show it on left of cursor
    if (x + tooltipWidth > viewportWidth - 10) {
        x = event.clientX - tooltipWidth - offset;
    }

    // Check bottom boundary - if tooltip goes off bottom, show it above cursor
    if (y + tooltipHeight > viewportHeight - 10) {
        y = event.clientY - tooltipHeight - offset;
    }

    // Ensure tooltip doesn't go off left edge
    if (x < 10) {
        x = 10;
    }

    // Ensure tooltip doesn't go off top edge
    if (y < 10) {
        y = 10;
    }

    // If tooltip is still too wide for viewport, center it
    if (tooltipWidth > viewportWidth - 20) {
        x = 10;
    }

    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
}

// Show product row tooltip with ingredient breakdown
async function showProductRowTooltip(productName, ingredientCost, event) {
    try {
        const response = await fetch(`/api/recipes/by-product/${encodeURIComponent(productName)}`);
        const recipe = await response.json();

        if (recipe.length === 0) {
            showTooltip(`<h4>${productName}</h4><p>No recipe found</p>`, event);
            return;
        }

        const content = `
            <h4>${productName} - Ingredient Breakdown</h4>
            <table>
                ${recipe.map(item => `
                    <tr>
                        <td>${item.ingredient_name}</td>
                        <td class="text-right">${item.quantity_needed} ${item.unit_of_measure} × ${formatCurrency(item.unit_cost)}</td>
                        <td class="text-right"><strong>${formatCurrency(item.line_cost)}</strong></td>
                    </tr>
                `).join('')}
            </table>
            <div class="tooltip-total">Total Ingredient Cost: ${formatCurrency(ingredientCost)}</div>
        `;

        showTooltip(content, event);
    } catch (error) {
        console.error('Error loading product row tooltip:', error);
    }
}

// Show recipe on product name hover
async function showRecipeTooltip(productName, event) {
    try {
        const response = await fetch(`/api/recipes/by-product/${encodeURIComponent(productName)}`);
        const recipe = await response.json();

        if (recipe.length === 0) {
            showTooltip(`<h4>${productName}</h4><p>No recipe found</p>`, event);
            return;
        }

        const totalCost = recipe.reduce((sum, item) => sum + item.line_cost, 0);

        const content = `
            <h4>${productName} - Recipe</h4>
            <table>
                ${recipe.map(item => `
                    <tr>
                        <td>${item.ingredient_name}</td>
                        <td class="text-right">${item.quantity_needed} ${item.unit_of_measure}</td>
                        <td class="text-right">${formatCurrency(item.line_cost)}</td>
                    </tr>
                `).join('')}
            </table>
            <div class="tooltip-total">Total Cost: ${formatCurrency(totalCost)}</div>
        `;

        showTooltip(content, event);
    } catch (error) {
        console.error('Error loading recipe tooltip:', error);
    }
}

// Show cost breakdown on ingredient cost hover
async function showCostBreakdownTooltip(productName, event) {
    try {
        const response = await fetch(`/api/recipes/by-product/${encodeURIComponent(productName)}`);
        const recipe = await response.json();

        if (recipe.length === 0) {
            return;
        }

        const content = `
            <h4>${productName} - Cost Breakdown</h4>
            <table>
                ${recipe.map(item => `
                    <tr>
                        <td>${item.ingredient_name}</td>
                        <td class="text-right">${item.quantity_needed} ${item.unit_of_measure} × ${formatCurrency(item.unit_cost)}</td>
                        <td class="text-right"><strong>${formatCurrency(item.line_cost)}</strong></td>
                    </tr>
                `).join('')}
            </table>
        `;

        showTooltip(content, event);
    } catch (error) {
        console.error('Error loading cost breakdown:', error);
    }
}

// Show invoice details in modal
async function showInvoiceDetails(invoiceNumber) {
    try {
        const response = await fetch(`/api/invoices/${encodeURIComponent(invoiceNumber)}`);
        const data = await response.json();

        const invoice = data.invoice;
        const lineItems = data.line_items;

        // Update modal title
        document.getElementById('modalInvoiceTitle').textContent = `Invoice ${invoiceNumber}`;

        // Display invoice info
        const invoiceInfo = document.getElementById('invoiceInfo');
        invoiceInfo.innerHTML = `
            <div class="invoice-info-item">
                <span class="invoice-info-label">Supplier</span>
                <span class="invoice-info-value">${invoice.supplier_name}</span>
            </div>
            <div class="invoice-info-item">
                <span class="invoice-info-label">Invoice Date</span>
                <span class="invoice-info-value">${formatDate(invoice.invoice_date)}</span>
            </div>
            <div class="invoice-info-item">
                <span class="invoice-info-label">Received Date</span>
                <span class="invoice-info-value">${formatDate(invoice.received_date)}</span>
            </div>
            <div class="invoice-info-item">
                <span class="invoice-info-label">Total Amount</span>
                <span class="invoice-info-value">${formatCurrency(invoice.total_amount)}</span>
            </div>
            <div class="invoice-info-item">
                <span class="invoice-info-label">Payment Status</span>
                <div class="invoice-info-value">
                    <select id="invoicePaymentStatus" onchange="updateInvoicePaymentStatus('${invoice.invoice_number}', this.value)">
                        <option value="UNPAID" ${invoice.payment_status === 'UNPAID' ? 'selected' : ''}>UNPAID</option>
                        <option value="PARTIAL" ${invoice.payment_status === 'PARTIAL' ? 'selected' : ''}>PARTIAL</option>
                        <option value="PAID" ${invoice.payment_status === 'PAID' ? 'selected' : ''}>PAID</option>
                    </select>
                    ${invoice.payment_status !== 'PAID' ? `<button class="btn-mark-paid" onclick="markInvoiceAsPaid('${invoice.invoice_number}')">💰 Mark as Paid</button>` : ''}
                </div>
            </div>
            ${invoice.payment_date ? `
            <div class="invoice-info-item">
                <span class="invoice-info-label">Payment Date</span>
                <span class="invoice-info-value">${formatDateTime(invoice.payment_date)}</span>
            </div>
            ` : ''}
            <div class="invoice-info-item">
                <span class="invoice-info-label">Reconciled</span>
                <span class="invoice-info-value">${invoice.reconciled}</span>
            </div>
        `;

        // Render line items as table
        renderInvoiceLineItemsTable(lineItems);

        // Show modal
        document.getElementById('invoiceModal').classList.add('active');
    } catch (error) {
        console.error('Error loading invoice details:', error);
        alert('Error loading invoice details. Please try again.');
    }
}

// Render invoice line items as table
function renderInvoiceLineItemsTable(lineItems) {
    const tbody = document.getElementById('invoiceItemsTableBody');

    if (lineItems.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center">No line items found for this invoice.</td></tr>';
        return;
    }

    tbody.innerHTML = lineItems.map(item => {
        // Combine size_modifier and size for display
        const sizeDisplay = [item.size_modifier, item.size, item.unit_of_measure]
            .filter(Boolean)
            .join(' ');

        // Highlight discrepancies between ordered and received quantities
        const qtyClass = item.quantity_ordered !== item.quantity_received ? 'text-warning' : '';

        return `
            <tr>
                <td><code>${item.ingredient_code || '-'}</code></td>
                <td><strong>${item.ingredient_name || '-'}</strong></td>
                <td>${item.brand || '-'}</td>
                <td>${sizeDisplay || '-'}</td>
                <td class="text-right">${item.quantity_ordered || '-'}</td>
                <td class="text-right ${qtyClass}"><strong>${item.quantity_received || '-'}</strong></td>
                <td class="text-right">${item.unit_price ? formatCurrency(parseFloat(item.unit_price)) : '-'}</td>
                <td class="text-right"><strong>${item.total_price ? formatCurrency(parseFloat(item.total_price)) : '-'}</strong></td>
                <td><small>${item.lot_number || '-'}</small></td>
            </tr>
        `;
    }).join('');
}

// Close invoice modal
function closeInvoiceModal() {
    document.getElementById('invoiceModal').classList.remove('active');
}

// Update invoice payment status
async function updateInvoicePaymentStatus(invoiceNumber, newStatus) {
    try {
        const response = await fetch(`/api/invoices/${encodeURIComponent(invoiceNumber)}/payment-status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                payment_status: newStatus
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ Payment status updated to ${newStatus}`);
            // Reload invoice details and invoice list
            await Promise.all([
                showInvoiceDetails(invoiceNumber),
                loadInvoices()
            ]);
        } else {
            alert(`❌ Error: ${result.error}`);
            // Reload to reset the dropdown
            showInvoiceDetails(invoiceNumber);
        }
    } catch (error) {
        console.error('Error updating payment status:', error);
        alert('❌ Error updating payment status. Please try again.');
        // Reload to reset the dropdown
        showInvoiceDetails(invoiceNumber);
    }
}

// Mark invoice as paid (quick action)
async function markInvoiceAsPaid(invoiceNumber) {
    if (!confirm(`Mark invoice ${invoiceNumber} as PAID?`)) {
        return;
    }

    await updateInvoicePaymentStatus(invoiceNumber, 'PAID');
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const modal = document.getElementById('invoiceModal');
    if (event.target === modal) {
        closeInvoiceModal();
    }
});

// Close modal with Escape key
window.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeInvoiceModal();
    }
});

// Format date helper (legacy, redirects to formatDateOnly)
function formatDate(dateString) {
    return formatDateOnly(dateString);
}

function formatCurrency(value) {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

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

// Table sorting functionality
let sortState = {};

function sortTable(tableName, columnIndex, type) {
    const tableId = tableName + 'Table';
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');

    // Initialize sort state for this table/column if needed
    const key = `${tableName}-${columnIndex}`;
    if (!sortState[key]) {
        sortState[key] = { direction: 'none' };
    }

    // Cycle through sort directions: none -> asc -> desc -> none
    if (sortState[key].direction === 'none') {
        sortState[key].direction = 'asc';
    } else if (sortState[key].direction === 'asc') {
        sortState[key].direction = 'desc';
    } else {
        sortState[key].direction = 'none';
    }

    // Handle paginated tables specially (suppliers and categories)
    if (tableName === 'suppliers' || tableName === 'categories') {
        return sortPaginatedTable(tableName, columnIndex, type, key, table);
    }

    const rows = Array.from(tbody.querySelectorAll('tr'));

    // Clear all sort arrows in this table
    table.querySelectorAll('.sort-arrow').forEach(arrow => {
        arrow.className = 'sort-arrow';
    });

    // Update the clicked column's arrow
    const header = table.querySelectorAll('th')[columnIndex];
    const arrow = header.querySelector('.sort-arrow');
    if (sortState[key].direction === 'asc') {
        arrow.className = 'sort-arrow sort-asc';
    } else if (sortState[key].direction === 'desc') {
        arrow.className = 'sort-arrow sort-desc';
    }

    // If direction is 'none', reload the original data
    if (sortState[key].direction === 'none') {
        // Reload the data for the table
        switch(tableName) {
            case 'inventory':
                loadInventory();
                break;
            case 'products':
                loadProducts();
                break;
            case 'unreconciled':
            case 'recentInvoices':
                loadInvoices();
                break;
            case 'counts':
                loadCounts();
                break;
            case 'suppliers':
                renderSuppliersTable();
                break;
            case 'categories':
                renderCategoriesTable();
                break;
        }
        return;
    }

    // Sort rows
    rows.sort((rowA, rowB) => {
        const cellA = rowA.cells[columnIndex];
        const cellB = rowB.cells[columnIndex];

        let aValue = cellA.textContent.trim();
        let bValue = cellB.textContent.trim();

        // Extract numeric values from cells that may contain formatted text
        if (type === 'number') {
            // Remove $ and commas, extract just the number
            aValue = parseFloat(aValue.replace(/[$,]/g, '').split(' ')[0]) || 0;
            bValue = parseFloat(bValue.replace(/[$,]/g, '').split(' ')[0]) || 0;

            if (sortState[key].direction === 'asc') {
                return aValue - bValue;
            } else {
                return bValue - aValue;
            }
        } else if (type === 'date') {
            // Handle date sorting
            aValue = aValue === '-' ? new Date(0) : new Date(aValue);
            bValue = bValue === '-' ? new Date(0) : new Date(bValue);

            if (sortState[key].direction === 'asc') {
                return aValue - bValue;
            } else {
                return bValue - aValue;
            }
        } else {
            // String sorting
            if (sortState[key].direction === 'asc') {
                return aValue.localeCompare(bValue);
            } else {
                return bValue.localeCompare(aValue);
            }
        }
    });

    // Clear and re-append sorted rows
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

// Sort paginated tables (suppliers, categories)
function sortPaginatedTable(tableName, columnIndex, type, key, table) {
    const tableState = tableName === 'suppliers' ? suppliersTableState : categoriesTableState;

    // Clear all sort arrows
    table.querySelectorAll('.sort-arrow').forEach(arrow => {
        arrow.className = 'sort-arrow';
    });

    // Update the clicked column's arrow
    const header = table.querySelectorAll('th')[columnIndex];
    const arrow = header.querySelector('.sort-arrow');
    if (sortState[key].direction === 'asc') {
        arrow.className = 'sort-arrow sort-asc';
    } else if (sortState[key].direction === 'desc') {
        arrow.className = 'sort-arrow sort-desc';
    }

    // If direction is 'none', reload original data
    if (sortState[key].direction === 'none') {
        if (tableName === 'suppliers') {
            loadSuppliersTable();
        } else {
            loadCategoriesTable();
        }
        return;
    }

    // Sort the state data
    tableState.allData.sort((a, b) => {
        let aValue, bValue;

        // Get values based on column index
        if (tableName === 'suppliers') {
            const keys = ['supplier_name', 'contact_person', 'phone', 'email', 'address', 'payment_terms'];
            aValue = a[keys[columnIndex]] || '';
            bValue = b[keys[columnIndex]] || '';
        } else { // categories
            const keys = ['category_name', 'item_count', 'created_at'];
            aValue = a[keys[columnIndex]] || '';
            bValue = b[keys[columnIndex]] || '';
        }

        // Convert to appropriate type for comparison
        if (type === 'number') {
            aValue = parseFloat(aValue) || 0;
            bValue = parseFloat(bValue) || 0;
            return sortState[key].direction === 'asc' ? aValue - bValue : bValue - aValue;
        } else if (type === 'date') {
            aValue = new Date(aValue || 0);
            bValue = new Date(bValue || 0);
            return sortState[key].direction === 'asc' ? aValue - bValue : bValue - aValue;
        } else {
            // String comparison
            return sortState[key].direction === 'asc'
                ? String(aValue).localeCompare(String(bValue))
                : String(bValue).localeCompare(String(aValue));
        }
    });

    // Re-render the table with sorted data
    if (tableName === 'suppliers') {
        renderSuppliersTable();
    } else {
        renderCategoriesTable();
    }
}

// Edit item functionality
async function editItem(itemId) {
    try {
        // Load suppliers first
        const suppliersResponse = await fetch('/api/suppliers/all');
        const suppliers = await suppliersResponse.json();

        const supplierSelect = document.getElementById('editSupplier');
        supplierSelect.innerHTML = '<option value="">-- Select Supplier --</option>';
        suppliers.forEach(supplier => {
            const option = document.createElement('option');
            option.value = supplier.supplier_name;
            option.textContent = supplier.supplier_name;
            supplierSelect.appendChild(option);
        });

        // Load item data
        const response = await fetch(`/api/inventory/item/${itemId}`);
        const item = await response.json();

        // Populate form
        document.getElementById('editItemId').value = item.id;
        document.getElementById('editCode').value = item.ingredient_code;
        document.getElementById('editName').value = item.ingredient_name;
        document.getElementById('editBrand').value = item.brand || '';
        document.getElementById('editSupplier').value = item.supplier_name || '';
        document.getElementById('editCategory').value = item.category;
        document.getElementById('editLocation').value = item.storage_location || '';
        document.getElementById('editQuantity').value = item.quantity_on_hand;
        document.getElementById('editUnit').value = item.unit_of_measure;
        document.getElementById('editCost').value = item.last_unit_price || item.unit_cost || 0;
        document.getElementById('editDateReceived').value = item.date_received || '';
        document.getElementById('editLotNumber').value = item.lot_number || '';
        document.getElementById('editExpirationDate').value = item.expiration_date || '';

        // Show modal
        document.getElementById('editItemModal').classList.add('active');
    } catch (error) {
        console.error('Error loading item:', error);
        alert('Error loading item details');
    }
}

function closeEditModal() {
    document.getElementById('editItemModal').classList.remove('active');
}

async function saveItemChanges(event) {
    event.preventDefault();

    const itemId = document.getElementById('editItemId').value;
    const lastPrice = parseFloat(document.getElementById('editCost').value);
    const data = {
        ingredient_code: document.getElementById('editCode').value,
        ingredient_name: document.getElementById('editName').value,
        brand: document.getElementById('editBrand').value,
        supplier_name: document.getElementById('editSupplier').value,
        category: document.getElementById('editCategory').value,
        storage_location: document.getElementById('editLocation').value,
        quantity_on_hand: parseFloat(document.getElementById('editQuantity').value),
        unit_of_measure: document.getElementById('editUnit').value,
        last_unit_price: lastPrice,
        average_unit_price: lastPrice, // Update average to match when manually edited
        date_received: document.getElementById('editDateReceived').value || null,
        lot_number: document.getElementById('editLotNumber').value || null,
        expiration_date: document.getElementById('editExpirationDate').value || null
    };

    try {
        const response = await fetch(`/api/inventory/item/${itemId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ Item updated successfully!');
            closeEditModal();

            // Reload inventory and header stats
            await Promise.all([
                loadInventory(),
                loadHeaderStats()
            ]);
        } else {
            alert('Error updating item: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating item:', error);
        alert('Error updating item');
    }
}

async function toggleItemActiveStatus(itemId, itemName, isCurrentlyActive) {
    // Decode HTML entities in item name for display
    const decodedName = itemName.replace(/&#39;/g, "'").replace(/&quot;/g, '"');
    const action = isCurrentlyActive ? 'deactivate' : 'reactivate';
    const actionPastTense = isCurrentlyActive ? 'deactivated' : 'reactivated';

    if (!confirm(`Are you sure you want to ${action} "${decodedName}"?\n\n${isCurrentlyActive ? 'This will hide the item from active inventory view.' : 'This will restore the item to active inventory.'}`)) {
        return;
    }

    try {
        const response = await fetch(`/api/inventory/item/${itemId}/toggle-active`, {
            method: 'PUT'
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ Item ${actionPastTense} successfully!`);

            // Reload inventory and header stats
            await Promise.all([
                loadInventory(),
                loadHeaderStats()
            ]);
        } else {
            alert(`Error ${action}ing item: ` + result.error);
        }
    } catch (error) {
        console.error(`Error ${action}ing item:`, error);
        alert(`Error ${action}ing item`);
    }
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const editModal = document.getElementById('editItemModal');
    if (event.target === editModal) {
        closeEditModal();
    }
});

// ============================================================
// Settings Tab Functions
// ============================================================

async function loadSettings() {
    // Load brands, suppliers, and categories
    await Promise.all([
        loadBrandsList(),
        loadSuppliersList(),
        loadSuppliersTable(),
        loadCategoriesTable()
    ]);
}

async function loadBrandsList() {
    try {
        const response = await fetch('/api/filters/brands');
        const brands = await response.json();

        const select = document.getElementById('brandSelect');
        select.innerHTML = '<option value="">-- Select a brand --</option>';

        brands.forEach(brand => {
            const option = document.createElement('option');
            option.value = brand;
            option.textContent = brand;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading brands:', error);
    }
}

async function loadSuppliersList() {
    try {
        const response = await fetch('/api/filters/suppliers');
        const suppliers = await response.json();

        const select = document.getElementById('supplierSelect');
        select.innerHTML = '<option value="">-- Select a supplier --</option>';

        suppliers.forEach(supplier => {
            const option = document.createElement('option');
            option.value = supplier;
            option.textContent = supplier;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading suppliers:', error);
    }
}

async function updateBrandPreview() {
    const brandSelect = document.getElementById('brandSelect');
    const selectedBrand = brandSelect.value;
    const preview = document.getElementById('brandPreview');

    if (!selectedBrand) {
        preview.innerHTML = '';
        preview.classList.remove('show');
        return;
    }

    try {
        // Get count of items with this brand
        const response = await fetch(`/api/inventory/detailed?brand=${encodeURIComponent(selectedBrand)}`);
        const items = await response.json();

        preview.innerHTML = `<strong>${items.length}</strong> item(s) will be updated`;
        preview.classList.add('show');
    } catch (error) {
        console.error('Error getting brand preview:', error);
        preview.innerHTML = 'Error loading preview';
    }
}

async function updateSupplierPreview() {
    const supplierSelect = document.getElementById('supplierSelect');
    const selectedSupplier = supplierSelect.value;
    const preview = document.getElementById('supplierPreview');

    if (!selectedSupplier) {
        preview.innerHTML = '';
        preview.classList.remove('show');
        return;
    }

    try {
        // Get count of items with this supplier
        const response = await fetch(`/api/inventory/detailed?supplier=${encodeURIComponent(selectedSupplier)}`);
        const items = await response.json();

        preview.innerHTML = `<strong>${items.length}</strong> item(s) will be updated`;
        preview.classList.add('show');
    } catch (error) {
        console.error('Error getting supplier preview:', error);
        preview.innerHTML = 'Error loading preview';
    }
}

async function bulkUpdateBrand() {
    const oldBrand = document.getElementById('brandSelect').value;
    const newBrand = document.getElementById('newBrandName').value.trim();

    if (!oldBrand) {
        alert('Please select a brand to update');
        return;
    }

    if (!newBrand) {
        alert('Please enter a new brand name');
        return;
    }

    if (oldBrand === newBrand) {
        alert('New brand name must be different from the current name');
        return;
    }

    if (!confirm(`Are you sure you want to rename all items from "${oldBrand}" to "${newBrand}"?`)) {
        return;
    }

    try {
        const response = await fetch('/api/inventory/bulk-update-brand', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                old_brand: oldBrand,
                new_brand: newBrand
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            // Reset form
            document.getElementById('brandSelect').value = '';
            document.getElementById('newBrandName').value = '';
            document.getElementById('brandPreview').innerHTML = '';

            // Reset brand filter to "all" if it was set to the old brand
            const brandFilter = document.getElementById('brandFilter');
            if (brandFilter && brandFilter.value === oldBrand) {
                brandFilter.value = 'all';
            }

            // Reload all affected data across the dashboard
            await Promise.all([
                loadBrandsList(),
                loadBrandsFilter(),
                loadHeaderStats(),
                loadInventory(),
                loadProducts(),
                loadInvoices()
            ]);
        } else {
            alert('Error updating brand: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating brand:', error);
        alert('Error updating brand');
    }
}

async function bulkUpdateSupplier() {
    const oldSupplier = document.getElementById('supplierSelect').value;
    const newSupplier = document.getElementById('newSupplierName').value.trim();

    if (!oldSupplier) {
        alert('Please select a supplier to update');
        return;
    }

    if (!newSupplier) {
        alert('Please enter a new supplier name');
        return;
    }

    if (oldSupplier === newSupplier) {
        alert('New supplier name must be different from the current name');
        return;
    }

    if (!confirm(`Are you sure you want to rename all items from "${oldSupplier}" to "${newSupplier}"?`)) {
        return;
    }

    try {
        const response = await fetch('/api/inventory/bulk-update-supplier', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                old_supplier: oldSupplier,
                new_supplier: newSupplier
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            // Reset form
            document.getElementById('supplierSelect').value = '';
            document.getElementById('newSupplierName').value = '';
            document.getElementById('supplierPreview').innerHTML = '';

            // Reset supplier filter to "all" if it was set to the old supplier
            const supplierFilter = document.getElementById('supplierFilter');
            if (supplierFilter && supplierFilter.value === oldSupplier) {
                supplierFilter.value = 'all';
            }

            // Reload all affected data across the dashboard
            await Promise.all([
                loadSuppliersList(),
                loadSuppliersFilter(),
                loadHeaderStats(),
                loadInventory(),
                loadProducts(),
                loadInvoices()
            ]);
        } else {
            alert('Error updating supplier: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating supplier:', error);
        alert('Error updating supplier');
    }
}

// ============================================================
// Date Range Filter Functions
// ============================================================

function clearDateFilter() {
    document.getElementById('dateFrom').value = '';
    document.getElementById('dateTo').value = '';
    loadInventory();
}

function applyInventoryDateFilter() {
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;
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

    loadInventory().then(() => {
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

// ============================================================
// Create Invoice Functions
// ============================================================

let invoiceLineItemCounter = 0;
let ingredientsList = [];

async function openCreateInvoiceModal() {
    document.getElementById('createInvoiceModal').classList.add('active');

    // Load suppliers from full supplier profiles database
    const suppliersResponse = await fetch('/api/suppliers/all');
    const suppliers = await suppliersResponse.json();

    const supplierSelect = document.getElementById('newInvoiceSupplier');
    supplierSelect.innerHTML = '<option value="">-- Select Supplier --</option>';
    suppliers.forEach(supplier => {
        const option = document.createElement('option');
        option.value = supplier.supplier_name;
        option.textContent = supplier.supplier_name;
        supplierSelect.appendChild(option);
    });

    // Load ingredients for dropdowns
    const ingredientsResponse = await fetch('/api/inventory/detailed?ingredient=all&supplier=all&brand=all&category=all');
    ingredientsList = await ingredientsResponse.json();

    // Set default dates to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('newInvoiceDate').value = today;
    document.getElementById('newReceivedDate').value = today;

    // Clear and add initial line item
    invoiceLineItemCounter = 0;
    document.getElementById('newInvoiceItemsBody').innerHTML = '';
    addInvoiceLineItem();
}

function closeCreateInvoiceModal() {
    document.getElementById('createInvoiceModal').classList.remove('active');
    document.getElementById('createInvoiceForm').reset();
}

function addInvoiceLineItem() {
    const tbody = document.getElementById('newInvoiceItemsBody');
    const rowId = invoiceLineItemCounter++;

    // Create ingredient datalist options
    const ingredientOptions = ingredientsList.map(ing =>
        `<option value="${ing.ingredient_code}">${ing.ingredient_name}</option>`
    ).join('');

    const row = document.createElement('tr');
    row.id = `lineItem-${rowId}`;
    row.innerHTML = `
        <td>
            <input list="ingredients-${rowId}" class="ingredient-input form-control" placeholder="Type or select code"
                   oninput="handleIngredientInput(${rowId}, this.value)" required>
            <datalist id="ingredients-${rowId}">
                ${ingredientOptions}
            </datalist>
            <input type="text" class="ingredient-name-input" placeholder="Ingredient name" style="display:none; margin-top:4px;">
            <select class="ingredient-category-input" style="display:none; margin-top:4px;">
                <option value="">-- Category --</option>
                <option value="Meat">Meat</option>
                <option value="Produce">Produce</option>
                <option value="Dairy">Dairy</option>
                <option value="Dry Goods">Dry Goods</option>
                <option value="Packaging">Packaging</option>
                <option value="Beverages">Beverages</option>
                <option value="Condiments">Condiments</option>
                <option value="Bakery">Bakery</option>
                <option value="Seafood">Seafood</option>
                <option value="Frozen">Frozen</option>
                <option value="Spices">Spices</option>
                <option value="Uncategorized">Uncategorized</option>
            </select>
            <input type="text" class="ingredient-uom-input" placeholder="Unit (lb, ea, etc)" style="display:none; margin-top:4px; width:100px;">
        </td>
        <td><input type="text" class="brand-input" placeholder="Brand"></td>
        <td><input type="text" class="size-input" placeholder="Size"></td>
        <td><input type="number" step="0.01" class="qty-ordered-input" placeholder="0" required oninput="calculateLineTotal(${rowId})"></td>
        <td><input type="number" step="0.01" class="qty-received-input" placeholder="0" required oninput="calculateLineTotal(${rowId})"></td>
        <td><input type="number" step="1" class="units-per-case-input" placeholder="1" value="1" oninput="calculateLineTotal(${rowId})" title="Units per case/bag (e.g., 6 rolls per bag)"></td>
        <td><input type="number" step="0.01" class="unit-price-input" placeholder="0.00" required oninput="calculateLineTotal(${rowId})"></td>
        <td><input type="text" class="line-total-input" value="$0.00" readonly></td>
        <td><input type="text" class="lot-number-input" placeholder="Lot #"></td>
        <td><button type="button" class="btn-remove-row" onclick="removeInvoiceLineItem(${rowId})">✖</button></td>
    `;

    tbody.appendChild(row);
}

function handleIngredientInput(rowId, ingredientCode) {
    if (!ingredientCode) return;

    const row = document.getElementById(`lineItem-${rowId}`);
    const nameInput = row.querySelector('.ingredient-name-input');
    const categoryInput = row.querySelector('.ingredient-category-input');
    const uomInput = row.querySelector('.ingredient-uom-input');

    // Check if this is an existing ingredient
    const ingredient = ingredientsList.find(ing => ing.ingredient_code === ingredientCode);

    if (ingredient) {
        // Existing ingredient - auto-fill all appropriate fields
        row.querySelector('.brand-input').value = ingredient.brand || '';

        // Auto-fill units per case
        if (ingredient.units_per_case) {
            row.querySelector('.units-per-case-input').value = ingredient.units_per_case;
        }

        // Auto-fill last price (price per case/bag)
        if (ingredient.last_unit_price) {
            row.querySelector('.unit-price-input').value = ingredient.last_unit_price;
        }

        // Store unit of measure for reference (will be used when saving)
        row.dataset.unitOfMeasure = ingredient.unit_of_measure || 'ea';

        // Recalculate line total with auto-filled values
        calculateLineTotal(rowId);

        // Hide extra fields for new ingredients
        nameInput.style.display = 'none';
        categoryInput.style.display = 'none';
        uomInput.style.display = 'none';
        nameInput.removeAttribute('required');
        categoryInput.removeAttribute('required');
        uomInput.removeAttribute('required');
    } else {
        // New ingredient - show fields for name, category, and unit of measure
        nameInput.style.display = 'block';
        categoryInput.style.display = 'block';
        uomInput.style.display = 'block';
        nameInput.setAttribute('required', 'required');
        categoryInput.setAttribute('required', 'required');
        uomInput.setAttribute('required', 'required');
        row.querySelector('.brand-input').value = '';

        // Clear auto-filled values for new ingredients
        row.querySelector('.units-per-case-input').value = '1';
        row.querySelector('.unit-price-input').value = '';
        row.dataset.unitOfMeasure = '';
    }
}

function removeInvoiceLineItem(rowId) {
    const row = document.getElementById(`lineItem-${rowId}`);
    if (row) {
        row.remove();
        calculateInvoiceTotal();
    }
}

function calculateLineTotal(rowId) {
    const row = document.getElementById(`lineItem-${rowId}`);
    const qtyReceived = parseFloat(row.querySelector('.qty-received-input').value) || 0;
    const unitPrice = parseFloat(row.querySelector('.unit-price-input').value) || 0;
    const lineTotal = qtyReceived * unitPrice;

    row.querySelector('.line-total-input').value = formatCurrency(lineTotal);
    calculateInvoiceTotal();
}

function calculateInvoiceTotal() {
    const rows = document.querySelectorAll('#newInvoiceItemsBody tr');
    let total = 0;

    rows.forEach(row => {
        const qtyReceived = parseFloat(row.querySelector('.qty-received-input').value) || 0;
        const unitPrice = parseFloat(row.querySelector('.unit-price-input').value) || 0;
        total += qtyReceived * unitPrice;
    });

    document.getElementById('newInvoiceTotal').textContent = formatCurrency(total);
}

async function saveNewInvoice(event) {
    event.preventDefault();

    // Collect invoice header data
    const invoiceData = {
        invoice_number: document.getElementById('newInvoiceNumber').value,
        supplier_name: document.getElementById('newInvoiceSupplier').value,
        invoice_date: document.getElementById('newInvoiceDate').value,
        received_date: document.getElementById('newReceivedDate').value,
        payment_status: document.getElementById('newPaymentStatus').value,
        notes: document.getElementById('newInvoiceNotes').value || null,
        line_items: []
    };

    // Collect line items
    const rows = document.querySelectorAll('#newInvoiceItemsBody tr');
    rows.forEach(row => {
        const ingredientCode = row.querySelector('.ingredient-input').value;
        if (!ingredientCode) return;

        // Check if this is an existing ingredient or a new one
        const ingredient = ingredientsList.find(ing => ing.ingredient_code === ingredientCode);

        let ingredientName, unitOfMeasure, category;

        if (ingredient) {
            // Existing ingredient
            ingredientName = ingredient.ingredient_name;
            unitOfMeasure = ingredient.unit_of_measure;
            category = ingredient.category;
        } else {
            // New ingredient - get from the extra fields
            ingredientName = row.querySelector('.ingredient-name-input').value;
            category = row.querySelector('.ingredient-category-input').value || 'Uncategorized';
            unitOfMeasure = row.querySelector('.ingredient-uom-input').value;
        }

        const qtyReceived = parseFloat(row.querySelector('.qty-received-input').value) || 0;
        const unitsPerCase = parseFloat(row.querySelector('.units-per-case-input').value) || 1;
        const unitPrice = parseFloat(row.querySelector('.unit-price-input').value) || 0;

        // Calculate total inventory quantity (cases * units per case)
        const inventoryQuantity = qtyReceived * unitsPerCase;

        invoiceData.line_items.push({
            ingredient_code: ingredientCode,
            ingredient_name: ingredientName,
            category: category,
            brand: row.querySelector('.brand-input').value || null,
            size: row.querySelector('.size-input').value || null,
            quantity_ordered: parseFloat(row.querySelector('.qty-ordered-input').value) || 0,
            quantity_received: qtyReceived,
            inventory_quantity: inventoryQuantity,  // Total units for inventory
            units_per_case: unitsPerCase,  // Units per case/bag for proper unit cost calculation
            unit_of_measure: unitOfMeasure,
            unit_price: unitPrice,
            total_price: qtyReceived * unitPrice,
            lot_number: row.querySelector('.lot-number-input').value || null
        });
    });

    if (invoiceData.line_items.length === 0) {
        alert('Please add at least one line item');
        return;
    }

    // Calculate total amount
    invoiceData.total_amount = invoiceData.line_items.reduce((sum, item) => sum + item.total_price, 0);

    try {
        const response = await fetch('/api/invoices/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(invoiceData)
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            closeCreateInvoiceModal();

            // Reload all affected data
            await Promise.all([
                loadInvoices(),
                loadInventory(),
                loadHeaderStats()
            ]);
        } else {
            alert('Error creating invoice: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving invoice:', error);
        alert('Error saving invoice');
    }
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const modal = document.getElementById('createInvoiceModal');
    if (event.target === modal) {
        closeCreateInvoiceModal();
    }

    const importModal = document.getElementById('importInvoiceModal');
    if (event.target === importModal) {
        closeImportInvoiceModal();
    }
});

// ============================================================
// Import Invoice Functions
// ============================================================

async function openImportInvoiceModal() {
    document.getElementById('importInvoiceModal').classList.add('active');

    // Load suppliers from full supplier profiles database
    const suppliersResponse = await fetch('/api/suppliers/all');
    const suppliers = await suppliersResponse.json();

    const supplierSelect = document.getElementById('importSupplier');
    supplierSelect.innerHTML = '<option value="">-- Select Supplier --</option>';
    suppliers.forEach(supplier => {
        const option = document.createElement('option');
        option.value = supplier.supplier_name;
        option.textContent = supplier.supplier_name;
        supplierSelect.appendChild(option);
    });

    // Set default dates to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('importInvoiceDate').value = today;
    document.getElementById('importReceivedDate').value = today;
}

function closeImportInvoiceModal() {
    document.getElementById('importInvoiceModal').classList.remove('active');
    document.getElementById('importInvoiceForm').reset();
    document.getElementById('importProgress').style.display = 'none';
}

async function uploadInvoiceFile(event) {
    event.preventDefault();

    const form = document.getElementById('importInvoiceForm');
    const fileInput = document.getElementById('invoiceFile');
    const file = fileInput.files[0];

    if (!file) {
        alert('Please select a file');
        return;
    }

    // Show progress
    document.getElementById('importProgress').style.display = 'block';
    form.style.display = 'none';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('invoice_number', document.getElementById('importInvoiceNumber').value);
    formData.append('supplier_name', document.getElementById('importSupplier').value);
    formData.append('invoice_date', document.getElementById('importInvoiceDate').value);
    formData.append('received_date', document.getElementById('importReceivedDate').value);
    formData.append('payment_status', document.getElementById('importPaymentStatus').value);

    try {
        const response = await fetch('/api/invoices/import', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        document.getElementById('importProgress').style.display = 'none';
        form.style.display = 'block';

        if (result.success) {
            alert(`✅ ${result.message}\n${result.items_count} line items imported`);
            closeImportInvoiceModal();

            // Reload all affected data
            await Promise.all([
                loadInvoices(),
                loadInventory(),
                loadHeaderStats()
            ]);
        } else {
            alert('Error importing invoice: ' + result.error);
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        document.getElementById('importProgress').style.display = 'none';
        form.style.display = 'block';
        alert('Error uploading file');
    }
}

// ============================================================
// Delete Invoice Functions
// ============================================================

let invoiceToDelete = null;

function openDeleteInvoiceModal(invoiceNumber, supplierName, totalAmount) {
    invoiceToDelete = invoiceNumber;

    const infoText = `Are you sure you want to delete invoice <strong>${invoiceNumber}</strong> from <strong>${supplierName}</strong> (${formatCurrency(totalAmount)})?`;
    document.getElementById('deleteInvoiceInfo').innerHTML = infoText;

    document.getElementById('deleteInvoiceModal').classList.add('active');
}

function closeDeleteInvoiceModal() {
    document.getElementById('deleteInvoiceModal').classList.remove('active');
    invoiceToDelete = null;
}

async function confirmDeleteInvoice() {
    if (!invoiceToDelete) {
        return;
    }

    try {
        const response = await fetch(`/api/invoices/delete/${encodeURIComponent(invoiceToDelete)}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            closeDeleteInvoiceModal();

            // Reload all affected data
            await Promise.all([
                loadInvoices(),
                loadHeaderStats(),
                loadInventory()
            ]);
        } else {
            alert('Error deleting invoice: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting invoice:', error);
        alert('Error deleting invoice');
    }
}

// Close delete modal when clicking outside
window.addEventListener('click', function(event) {
    const deleteModal = document.getElementById('deleteInvoiceModal');
    if (event.target === deleteModal) {
        closeDeleteInvoiceModal();
    }
});

// ============================================================
// Supplier Management Functions
// ============================================================

// Suppliers table pagination state
const suppliersTableState = {
    allData: [],
    currentPage: 1,
    pageSize: 10
};

async function loadSuppliersTable() {
    try {
        const response = await fetch('/api/suppliers/all');
        const suppliers = await response.json();

        suppliersTableState.allData = suppliers;
        suppliersTableState.currentPage = 1;

        renderSuppliersTable();
    } catch (error) {
        console.error('Error loading suppliers:', error);
        document.getElementById('suppliersTableBody').innerHTML =
            '<tr><td colspan="7" class="text-center text-danger">Error loading suppliers</td></tr>';
    }
}

function renderSuppliersTable() {
    const tbody = document.getElementById('suppliersTableBody');
    const { allData, currentPage, pageSize } = suppliersTableState;

    if (allData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No suppliers found. Create your first supplier!</td></tr>';
        updateSuppliersPagination();
        return;
    }

    // Calculate pagination
    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = allData.slice(startIdx, endIdx);

    // Render table rows
    tbody.innerHTML = pageData.map(supplier => {
        const escapedName = (supplier.supplier_name || '').replace(/'/g, "\\'");
        return `
            <tr>
                <td><strong>${supplier.supplier_name || '-'}</strong></td>
                <td>${supplier.contact_person || '-'}</td>
                <td>${supplier.phone || '-'}</td>
                <td>${supplier.email || '-'}</td>
                <td>${supplier.address || '-'}</td>
                <td>${supplier.payment_terms || '-'}</td>
                <td class="actions-cell">
                    <button class="btn-edit-dark" onclick="editSupplierProfile(${supplier.id})" title="Edit"><span style="font-weight: 700;">✏️</span></button>
                    <button class="btn-delete-dark" onclick="deleteSupplierProfile(${supplier.id}, '${escapedName}')" title="Delete"><span style="font-weight: 700;">🗑️</span></button>
                </td>
            </tr>
        `;
    }).join('');

    updateSuppliersPagination();
}

function updateSuppliersPagination() {
    const { allData, currentPage, pageSize } = suppliersTableState;
    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, allData.length);

    const paginationDiv = document.getElementById('suppliersPagination');
    if (!paginationDiv) return;

    if (allData.length === 0) {
        paginationDiv.innerHTML = '';
        return;
    }

    paginationDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: white; border-radius: 8px;">
            <div>Showing ${startIdx + 1}-${endIdx} of ${allData.length} suppliers</div>
            <div style="display: flex; gap: 10px; align-items: center;">
                <button class="btn btn-secondary" onclick="changeSuppliersPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                    ← Previous
                </button>
                <span>Page ${currentPage} of ${totalPages}</span>
                <button class="btn btn-secondary" onclick="changeSuppliersPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                    Next →
                </button>
            </div>
        </div>
    `;
}

function changeSuppliersPage(newPage) {
    const totalPages = Math.ceil(suppliersTableState.allData.length / suppliersTableState.pageSize);
    if (newPage < 1 || newPage > totalPages) return;

    suppliersTableState.currentPage = newPage;
    renderSuppliersTable();
}

function openCreateSupplierModal() {
    document.getElementById('supplierModalTitle').textContent = 'Create New Supplier';
    document.getElementById('supplierEditId').value = '';
    document.getElementById('supplierForm').reset();
    document.getElementById('supplierModal').classList.add('active');
}

async function editSupplierProfile(supplierId) {
    try {
        const response = await fetch('/api/suppliers/all');
        const suppliers = await response.json();
        const supplier = suppliers.find(s => s.id === supplierId);

        if (!supplier) {
            alert('Supplier not found');
            return;
        }

        // Populate form
        document.getElementById('supplierModalTitle').textContent = 'Edit Supplier';
        document.getElementById('supplierEditId').value = supplier.id;
        document.getElementById('supplierName').value = supplier.supplier_name || '';
        document.getElementById('supplierContact').value = supplier.contact_person || '';
        document.getElementById('supplierPhone').value = supplier.phone || '';
        document.getElementById('supplierEmail').value = supplier.email || '';
        document.getElementById('supplierAddress').value = supplier.address || '';
        document.getElementById('supplierPaymentTerms').value = supplier.payment_terms || '';
        document.getElementById('supplierNotes').value = supplier.notes || '';

        document.getElementById('supplierModal').classList.add('active');
    } catch (error) {
        console.error('Error loading supplier:', error);
        alert('Error loading supplier details');
    }
}

function closeSupplierModal() {
    document.getElementById('supplierModal').classList.remove('active');
    document.getElementById('supplierForm').reset();
}

async function saveSupplier(event) {
    event.preventDefault();

    const supplierId = document.getElementById('supplierEditId').value;
    const isEdit = supplierId !== '';

    const data = {
        supplier_name: document.getElementById('supplierName').value,
        contact_person: document.getElementById('supplierContact').value || null,
        phone: document.getElementById('supplierPhone').value || null,
        email: document.getElementById('supplierEmail').value || null,
        address: document.getElementById('supplierAddress').value || null,
        payment_terms: document.getElementById('supplierPaymentTerms').value || null,
        notes: document.getElementById('supplierNotes').value || null
    };

    try {
        const url = isEdit ? `/api/suppliers/update/${supplierId}` : '/api/suppliers/create';
        const method = isEdit ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            closeSupplierModal();

            // Reload suppliers table and dropdowns
            await Promise.all([
                loadSuppliersTable(),
                loadSuppliersList(),
                loadSuppliersFilter()  // Also update the inventory filter
            ]);
        } else {
            alert('Error saving supplier: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving supplier:', error);
        alert('Error saving supplier');
    }
}

async function deleteSupplierProfile(supplierId, supplierName) {
    if (!confirm(`Are you sure you want to delete supplier "${supplierName}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/suppliers/delete/${supplierId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);

            // Reload suppliers table and dropdowns
            await Promise.all([
                loadSuppliersTable(),
                loadSuppliersList(),
                loadSuppliersFilter()  // Also update the inventory filter
            ]);
        } else {
            alert('Error deleting supplier: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting supplier:', error);
        alert('Error deleting supplier');
    }
}

// Close supplier modal when clicking outside
window.addEventListener('click', function(event) {
    const supplierModal = document.getElementById('supplierModal');
    if (event.target === supplierModal) {
        closeSupplierModal();
    }
});

// ============================================================
// Category Management and Selection Functions
// ============================================================

let availableCategories = [];

async function loadCategoriesList() {
    try {
        const response = await fetch('/api/filters/categories');
        availableCategories = await response.json();
        console.log('Available categories loaded:', availableCategories);
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const headerCheckbox = document.getElementById('selectAllHeaderCheckbox');
    const checkboxes = document.querySelectorAll('.item-checkbox');

    // Sync both checkboxes
    if (event.target.id === 'selectAllCheckbox') {
        headerCheckbox.checked = selectAllCheckbox.checked;
    } else {
        selectAllCheckbox.checked = headerCheckbox.checked;
    }

    const isChecked = selectAllCheckbox.checked;
    checkboxes.forEach(cb => cb.checked = isChecked);
    updateSelectionCount();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.item-checkbox');
    checkboxes.forEach(cb => cb.checked = false);
    document.getElementById('selectAllCheckbox').checked = false;
    document.getElementById('selectAllHeaderCheckbox').checked = false;
    updateSelectionCount();
}

function updateSelectionCount() {
    const selectedCheckboxes = document.querySelectorAll('.item-checkbox:checked');
    const count = selectedCheckboxes.length;

    document.getElementById('selectionCount').textContent = `${count} selected`;

    const editSelectedBtn = document.getElementById('editSelectedBtn');
    if (count > 0) {
        editSelectedBtn.style.display = 'inline-block';
    } else {
        editSelectedBtn.style.display = 'none';
    }
}

function getSelectedItemIds() {
    const selectedCheckboxes = document.querySelectorAll('.item-checkbox:checked');
    return Array.from(selectedCheckboxes).map(cb => parseInt(cb.dataset.itemId));
}

function showCategoryDropdown(itemId, currentCategory) {
    // Remove any existing dropdown
    const existingDropdown = document.querySelector('.category-dropdown');
    if (existingDropdown) {
        existingDropdown.remove();
    }

    // Create dropdown
    const dropdown = document.createElement('div');
    dropdown.className = 'category-dropdown';
    dropdown.innerHTML = `
        <div class="category-dropdown-header">Change Category</div>
        <div class="category-dropdown-options">
            ${availableCategories.map(cat => `
                <div class="category-option ${cat === currentCategory ? 'selected' : ''}"
                     onclick="updateItemCategory(${itemId}, '${cat.replace(/'/g, '\\\'')}')">${cat}</div>
            `).join('')}
            <div class="category-option-divider"></div>
            <div class="category-option-new" onclick="createNewCategory(${itemId})">+ Create New Category</div>
        </div>
    `;

    // Position dropdown near the badge
    const badge = event.target;
    const rect = badge.getBoundingClientRect();
    dropdown.style.position = 'fixed';
    dropdown.style.top = `${rect.bottom + 5}px`;
    dropdown.style.left = `${rect.left}px`;
    dropdown.style.zIndex = '1000';

    document.body.appendChild(dropdown);

    // Close dropdown when clicking outside
    setTimeout(() => {
        document.addEventListener('click', function closeDropdown(e) {
            if (!dropdown.contains(e.target)) {
                dropdown.remove();
                document.removeEventListener('click', closeDropdown);
            }
        });
    }, 100);
}

async function updateItemCategory(itemId, newCategory) {
    console.log('Updating item', itemId, 'to category:', newCategory);

    try {
        const response = await fetch(`/api/inventory/update-category`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                item_ids: [itemId],
                new_category: newCategory
            })
        });

        const result = await response.json();
        console.log('Update result:', result);

        if (result.success) {
            // Remove dropdown
            const dropdown = document.querySelector('.category-dropdown');
            if (dropdown) dropdown.remove();

            // Reload inventory and refresh categories list
            console.log('Reloading inventory and filters...');
            await Promise.all([
                loadInventory(),
                loadCategoriesFilter(),
                loadCategoriesList()  // IMPORTANT: Refresh the available categories list
            ]);
            console.log('✓ Category updated successfully');
        } else {
            console.error('Category update failed:', result);
            alert('❌ Error updating category: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error updating category:', error);
        alert('❌ Error updating category: ' + error.message);
    }
}

function createNewCategory(itemId) {
    const newCategory = prompt('Enter new category name:');
    if (newCategory && newCategory.trim()) {
        updateItemCategory(itemId, newCategory.trim());
    }
}

function editSelectedCategories() {
    const selectedIds = getSelectedItemIds();
    if (selectedIds.length === 0) {
        alert('No items selected');
        return;
    }

    showMassEditModal(selectedIds);
}

function editAllCategories() {
    // Get all item IDs from the current table
    const allCheckboxes = document.querySelectorAll('.item-checkbox');
    const allIds = Array.from(allCheckboxes).map(cb => parseInt(cb.dataset.itemId));

    if (allIds.length === 0) {
        alert('No items to edit');
        return;
    }

    showMassEditModal(allIds);
}

function showMassEditModal(itemIds) {
    // Remove existing modal if any
    const existingModal = document.getElementById('massEditCategoryModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create modal
    const modal = document.createElement('div');
    modal.id = 'massEditCategoryModal';
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-content modal-small">
            <div class="modal-header">
                <h2>Update Categories for ${itemIds.length} Item(s)</h2>
                <button class="modal-close" onclick="closeMassEditModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="massEditCategoryForm" onsubmit="saveMassEditCategory(event, ${JSON.stringify(itemIds)})">
                    <div class="form-group">
                        <label for="massEditCategory">Select Category *</label>
                        <select id="massEditCategory" required class="form-control">
                            <option value="">-- Select Category --</option>
                            ${availableCategories.map(cat => `<option value="${cat}">${cat}</option>`).join('')}
                            <option value="_new_">+ Create New Category</option>
                        </select>
                    </div>
                    <div class="form-group" id="newCategoryGroup" style="display: none;">
                        <label for="newCategoryName">New Category Name *</label>
                        <input type="text" id="newCategoryName" class="form-control" placeholder="Enter category name">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn-secondary" onclick="closeMassEditModal()">Cancel</button>
                        <button type="submit" class="btn-primary">Update Categories</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Add event listener for category select
    document.getElementById('massEditCategory').addEventListener('change', function() {
        const newCategoryGroup = document.getElementById('newCategoryGroup');
        if (this.value === '_new_') {
            newCategoryGroup.style.display = 'block';
            document.getElementById('newCategoryName').required = true;
        } else {
            newCategoryGroup.style.display = 'none';
            document.getElementById('newCategoryName').required = false;
        }
    });
}

function closeMassEditModal() {
    const modal = document.getElementById('massEditCategoryModal');
    if (modal) {
        modal.remove();
    }
}

async function saveMassEditCategory(event, itemIds) {
    event.preventDefault();

    let categorySelect = document.getElementById('massEditCategory');
    let newCategory;

    if (categorySelect.value === '_new_') {
        newCategory = document.getElementById('newCategoryName').value.trim();
        if (!newCategory) {
            alert('Please enter a category name');
            return;
        }
    } else {
        newCategory = categorySelect.value;
    }

    try {
        const response = await fetch('/api/inventory/update-category', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                item_ids: itemIds,
                new_category: newCategory
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ Updated ${result.count} item(s)`);
            closeMassEditModal();
            clearSelection();

            // Reload inventory to show changes
            await Promise.all([
                loadInventory(),
                loadCategoriesFilter(),
                loadCategoriesList()
            ]);
        } else {
            alert('Error updating categories: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating categories:', error);
        alert('Error updating categories');
    }
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const modal = document.getElementById('massEditCategoryModal');
    if (event.target === modal) {
        closeMassEditModal();
    }
});

// ============================================================
// Category Management Functions (Settings Tab)
// ============================================================

// Categories table pagination state
const categoriesTableState = {
    allData: [],
    currentPage: 1,
    pageSize: 10
};

async function loadCategoriesTable() {
    try {
        const response = await fetch('/api/categories/all');
        const categories = await response.json();

        categoriesTableState.allData = categories;
        categoriesTableState.currentPage = 1;

        renderCategoriesTable();
    } catch (error) {
        console.error('Error loading categories:', error);
        document.getElementById('categoriesTableBody').innerHTML =
            '<tr><td colspan="4" class="text-center text-danger">Error loading categories</td></tr>';
    }
}

function renderCategoriesTable() {
    const tbody = document.getElementById('categoriesTableBody');
    const { allData, currentPage, pageSize } = categoriesTableState;

    if (allData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">No categories found</td></tr>';
        updateCategoriesPagination();
        return;
    }

    // Calculate pagination
    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = allData.slice(startIdx, endIdx);

    // Render table rows
    tbody.innerHTML = pageData.map(category => {
        const escapedName = (category.category_name || '').replace(/'/g, "\\'");
        const isUncategorized = category.category_name === 'Uncategorized';
        const canDelete = category.item_count === 0 && !isUncategorized;
        const canEdit = !isUncategorized;

        // Edit button
        const editButton = canEdit
            ? `<button class="btn-edit-dark" onclick="editCategoryFromSettings(${category.id}, '${escapedName}')" title="Edit"><span style="font-weight: 700;">✏️</span></button>`
            : `<button class="btn-edit-dark btn-disabled" title="Cannot edit Uncategorized"><span style="font-weight: 700;">✏️</span></button>`;

        // Delete button
        let deleteButton;
        if (isUncategorized) {
            deleteButton = `<button class="btn-delete-dark btn-disabled" title="Cannot delete Uncategorized"><span style="font-weight: 700;">🗑️</span></button>`;
        } else if (category.item_count > 0) {
            deleteButton = `<button class="btn-delete-dark btn-disabled" title="Category in use by ${category.item_count} item(s) - reassign them first"><span style="font-weight: 700;">🗑️</span></button>`;
        } else {
            deleteButton = `<button class="btn-delete-dark" onclick="deleteCategoryFromSettings(${category.id}, '${escapedName}')" title="Delete"><span style="font-weight: 700;">🗑️</span></button>`;
        }

        return `
            <tr>
                <td><strong>${category.category_name}</strong></td>
                <td class="text-center">${category.item_count}</td>
                <td><small>${formatDateTime(category.created_at)}</small></td>
                <td class="actions-cell">
                    ${editButton}
                    ${deleteButton}
                </td>
            </tr>
        `;
    }).join('');

    updateCategoriesPagination();
}

function updateCategoriesPagination() {
    const { allData, currentPage, pageSize } = categoriesTableState;
    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, allData.length);

    const paginationDiv = document.getElementById('categoriesPagination');
    if (!paginationDiv) return;

    if (allData.length === 0) {
        paginationDiv.innerHTML = '';
        return;
    }

    paginationDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: white; border-radius: 8px;">
            <div>Showing ${startIdx + 1}-${endIdx} of ${allData.length} categories</div>
            <div style="display: flex; gap: 10px; align-items: center;">
                <button class="btn btn-secondary" onclick="changeCategoriesPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                    ← Previous
                </button>
                <span>Page ${currentPage} of ${totalPages}</span>
                <button class="btn btn-secondary" onclick="changeCategoriesPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                    Next →
                </button>
            </div>
        </div>
    `;
}

function changeCategoriesPage(newPage) {
    const totalPages = Math.ceil(categoriesTableState.allData.length / categoriesTableState.pageSize);
    if (newPage < 1 || newPage > totalPages) return;

    categoriesTableState.currentPage = newPage;
    renderCategoriesTable();
}

function openCreateCategoryModal() {
    // Clear the form
    document.getElementById('categoryForm').reset();
    document.getElementById('categoryEditId').value = '';
    document.getElementById('categoryOldName').value = '';

    // Update modal title and button text
    document.getElementById('categoryModalTitle').textContent = 'Create New Category';
    document.getElementById('categorySaveBtn').textContent = 'Create Category';
    document.getElementById('categoryHelpText').style.display = 'none';

    // Open the modal
    document.getElementById('categoryModal').classList.add('active');
}

function editCategoryFromSettings(categoryId, categoryName) {
    // Populate the modal
    document.getElementById('categoryEditId').value = categoryId;
    document.getElementById('categoryOldName').value = categoryName;
    document.getElementById('categoryName').value = categoryName;

    // Update modal title and button text
    document.getElementById('categoryModalTitle').textContent = 'Edit Category';
    document.getElementById('categorySaveBtn').textContent = 'Save Changes';
    document.getElementById('categoryHelpText').style.display = 'block';

    // Open the modal
    document.getElementById('categoryModal').classList.add('active');
}

function closeCategoryModal() {
    document.getElementById('categoryModal').classList.remove('active');
    document.getElementById('categoryForm').reset();
}

async function saveCategory(event) {
    event.preventDefault();

    const categoryId = document.getElementById('categoryEditId').value;
    const newName = document.getElementById('categoryName').value.trim();
    const oldName = document.getElementById('categoryOldName').value;

    // Check if this is create or update
    const isCreate = !categoryId;

    if (!isCreate && newName === oldName) {
        alert('Category name is unchanged');
        return;
    }

    try {
        let response;

        if (isCreate) {
            // Create new category
            response = await fetch('/api/categories/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    category_name: newName
                })
            });
        } else {
            // Update existing category
            response = await fetch(`/api/categories/update/${categoryId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    category_name: newName
                })
            });
        }

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            closeCategoryModal();

            // Reload categories table and refresh available categories
            await Promise.all([
                loadCategoriesTable(),
                loadCategoriesList(),
                loadCategoriesFilter(),
                loadInventory()  // Refresh inventory to show updated category names
            ]);
        } else {
            alert('❌ Error saving category: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving category:', error);
        alert('❌ Error saving category');
    }
}

async function deleteCategoryFromSettings(categoryId, categoryName) {
    if (!confirm(`Are you sure you want to delete the category "${categoryName}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/categories/delete/${categoryId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);

            // Reload categories table and refresh available categories
            await Promise.all([
                loadCategoriesTable(),
                loadCategoriesList(),
                loadCategoriesFilter()
            ]);
        } else {
            alert('❌ Error deleting category: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting category:', error);
        alert('❌ Error deleting category');
    }
}

// ============================================================================
// INVENTORY COUNT FUNCTIONS
// ============================================================================

let countRowId = 0;

async function loadCounts() {
    try {
        // Build URL with date filtering
        const dateFrom = document.getElementById('countDateFrom')?.value || '';
        const dateTo = document.getElementById('countDateTo')?.value || '';

        let url = '/api/counts/all';
        const params = new URLSearchParams();
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        if (params.toString()) url += '?' + params.toString();

        const response = await fetch(url);
        const counts = await response.json();

        const tbody = document.getElementById('countsTableBody');
        if (!tbody) return;

        if (counts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="no-data">No counts found</td></tr>';
            return;
        }

        tbody.innerHTML = counts.map(count => {
            return `
                <tr>
                    <td><strong>${count.count_number}</strong></td>
                    <td>${formatDate(count.count_date)}</td>
                    <td>${count.counted_by || '-'}</td>
                    <td id="count-items-${count.id}">Loading...</td>
                    <td id="count-variance-${count.id}">Loading...</td>
                    <td><span class="badge ${count.reconciled === 'YES' ? 'badge-success' : 'badge-warning'}">${count.reconciled}</span></td>
                    <td>
                        <button class="btn-view" onclick="viewCountDetails(${count.id})" title="View Details">👁️</button>
                        <button class="btn-delete-dark" onclick="deleteCount(${count.id}, '${count.count_number}')" title="Delete"><span style="font-weight: 700;">🗑️</span></button>
                    </td>
                </tr>
            `;
        }).join('');

        // Load line items count and variance for each count
        counts.forEach(async count => {
            const detailsResponse = await fetch(`/api/counts/${count.id}`);
            const details = await detailsResponse.json();
            const itemsCell = document.getElementById(`count-items-${count.id}`);
            const varianceCell = document.getElementById(`count-variance-${count.id}`);

            if (itemsCell && details.line_items) {
                itemsCell.textContent = details.line_items.length;
            }

            if (varianceCell && details.line_items) {
                const totalVariance = details.line_items.reduce((sum, item) => sum + (item.variance || 0), 0);
                const varianceClass = totalVariance === 0 ? '' : totalVariance > 0 ? 'variance-positive' : 'variance-negative';
                varianceCell.innerHTML = `<span class="${varianceClass}">${totalVariance > 0 ? '+' : ''}${totalVariance.toFixed(2)}</span>`;
            }
        });

    } catch (error) {
        console.error('Error loading counts:', error);
        const tbody = document.getElementById('countsTableBody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" class="error">Error loading counts</td></tr>';
        }
    }
}

async function openCreateCountModal() {
    document.getElementById('countForm').reset();
    document.getElementById('countItemsTableBody').innerHTML = '';
    countRowId = 0;

    // Set default count date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('countDate').value = today;

    // Populate ingredient codes datalist for autocomplete
    await populateIngredientCodesList();

    // Add initial row
    addCountRow();

    document.getElementById('createCountModal').classList.add('active');
}

async function populateIngredientCodesList() {
    try {
        const response = await fetch('/api/inventory/detailed');
        const items = await response.json();

        const datalist = document.getElementById('ingredientCodesList');
        datalist.innerHTML = '';

        // Create options for each unique ingredient code
        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item.ingredient_code;
            option.textContent = `${item.ingredient_code} - ${item.ingredient_name}`;
            datalist.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading ingredient codes:', error);
    }
}

function closeCreateCountModal() {
    document.getElementById('createCountModal').classList.remove('active');
}

function addCountRow() {
    countRowId++;
    const tbody = document.getElementById('countItemsTableBody');
    const row = document.createElement('tr');
    row.id = `count-row-${countRowId}`;
    row.dataset.rowId = countRowId;

    row.innerHTML = `
        <td>
            <input type="text" class="count-ingredient-code-input" placeholder="Code" required
                   oninput="lookupIngredientForCount(${countRowId})" list="ingredientCodesList">
        </td>
        <td><input type="text" class="count-ingredient-name-input" readonly placeholder="Auto-filled"></td>
        <td><input type="number" step="0.01" class="count-expected-input" readonly placeholder="0"></td>
        <td><input type="number" step="0.01" class="count-counted-input" required placeholder="0"
                   oninput="calculateCountVariance(${countRowId})"></td>
        <td><input type="text" class="count-variance-input" readonly placeholder="0"></td>
        <td><input type="text" class="count-uom-input" readonly placeholder="Unit"></td>
        <td><input type="text" class="count-notes-input" placeholder="Notes"></td>
        <td><button type="button" class="btn-delete-dark" onclick="removeCountRow(${countRowId})" title="Remove"><span style="font-weight: 700;">✖</span></button></td>
    `;

    tbody.appendChild(row);
    updateCountSummary();
}

function removeCountRow(rowId) {
    const row = document.getElementById(`count-row-${rowId}`);
    if (row) {
        row.remove();
        updateCountSummary();
    }
}

async function lookupIngredientForCount(rowId) {
    const row = document.getElementById(`count-row-${rowId}`);
    if (!row) return;

    const code = row.querySelector('.count-ingredient-code-input').value.trim();
    if (!code) {
        // Clear fields if code is empty
        row.querySelector('.count-ingredient-name-input').value = '';
        row.querySelector('.count-expected-input').value = '';
        row.querySelector('.count-uom-input').value = '';
        row.dataset.ingredientName = '';
        row.dataset.unitOfMeasure = '';
        row.querySelector('.count-variance-input').value = '';
        return;
    }

    try {
        const response = await fetch('/api/inventory/detailed');
        const items = await response.json();

        // Find ingredient by code (case-insensitive match)
        const ingredient = items.find(item =>
            item.ingredient_code.toLowerCase() === code.toLowerCase()
        );

        if (ingredient) {
            // Item found in inventory - autofill all fields from inventory
            row.querySelector('.count-ingredient-name-input').value = ingredient.ingredient_name || '';
            row.querySelector('.count-expected-input').value = ingredient.quantity_on_hand || 0;
            row.querySelector('.count-uom-input').value = ingredient.unit_of_measure || 'ea';

            // Store complete ingredient data in dataset for later use
            row.dataset.ingredientName = ingredient.ingredient_name || '';
            row.dataset.unitOfMeasure = ingredient.unit_of_measure || 'ea';
            row.dataset.ingredientCode = ingredient.ingredient_code; // Store exact code from inventory
            row.dataset.brand = ingredient.brand || '';
            row.dataset.category = ingredient.category || 'Uncategorized';

            // Update the ingredient code input to match exact case from inventory
            row.querySelector('.count-ingredient-code-input').value = ingredient.ingredient_code;

            // Recalculate variance if counted value exists
            calculateCountVariance(rowId);
        } else {
            // Item NOT found in inventory - this is a new item being discovered during count
            row.querySelector('.count-ingredient-name-input').value = '(New Item - Not in Inventory)';
            row.querySelector('.count-expected-input').value = '0';
            row.querySelector('.count-uom-input').value = 'ea';
            row.dataset.ingredientName = '';
            row.dataset.unitOfMeasure = 'ea';
            row.dataset.ingredientCode = code;
            row.dataset.brand = '';
            row.dataset.category = 'Uncategorized';

            // Clear variance since there's no expected value
            calculateCountVariance(rowId);
        }
    } catch (error) {
        console.error('Error looking up ingredient:', error);
        alert('Error looking up ingredient. Please check your connection and try again.');
    }
}

function calculateCountVariance(rowId) {
    const row = document.getElementById(`count-row-${rowId}`);
    if (!row) return;

    const expected = parseFloat(row.querySelector('.count-expected-input').value) || 0;
    const counted = parseFloat(row.querySelector('.count-counted-input').value) || 0;
    const variance = counted - expected;

    const varianceInput = row.querySelector('.count-variance-input');
    varianceInput.value = variance.toFixed(2);

    // Apply color coding
    if (variance > 0) {
        varianceInput.style.color = '#28a745'; // Green for positive
    } else if (variance < 0) {
        varianceInput.style.color = '#dc3545'; // Red for negative
    } else {
        varianceInput.style.color = '#6c757d'; // Gray for zero
    }

    updateCountSummary();
}

function updateCountSummary() {
    const rows = document.querySelectorAll('#countItemsTableBody tr');
    const totalItems = rows.length;
    let totalVariance = 0;

    rows.forEach(row => {
        const varianceValue = parseFloat(row.querySelector('.count-variance-input').value) || 0;
        totalVariance += varianceValue;
    });

    document.getElementById('countTotalItems').textContent = totalItems;
    document.getElementById('countTotalVariance').textContent = totalVariance.toFixed(2);
}

async function submitCount(event) {
    event.preventDefault();

    const countData = {
        count_number: document.getElementById('countNumber').value,
        count_date: document.getElementById('countDate').value,
        counted_by: document.getElementById('countedBy').value || null,
        notes: document.getElementById('countNotes').value || null,
        line_items: []
    };

    // Collect line items
    const rows = document.querySelectorAll('#countItemsTableBody tr');
    rows.forEach(row => {
        const code = row.querySelector('.count-ingredient-code-input').value.trim();
        const counted = parseFloat(row.querySelector('.count-counted-input').value);

        if (code && !isNaN(counted)) {
            // Use exact ingredient_code from dataset (preserves case from inventory)
            // Fall back to input value if dataset not populated (new items)
            const exactCode = row.dataset.ingredientCode || code;
            const ingredientName = row.dataset.ingredientName || row.querySelector('.count-ingredient-name-input').value.replace('(New Item - Not in Inventory)', '').trim() || 'Unknown Item';
            const unitOfMeasure = row.dataset.unitOfMeasure || row.querySelector('.count-uom-input').value || 'ea';

            countData.line_items.push({
                ingredient_code: exactCode,
                ingredient_name: ingredientName,
                quantity_counted: counted,
                unit_of_measure: unitOfMeasure,
                notes: row.querySelector('.count-notes-input').value || null
            });
        }
    });

    if (countData.line_items.length === 0) {
        alert('Please add at least one item to count');
        return;
    }

    try {
        const response = await fetch('/api/counts/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(countData)
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            closeCreateCountModal();
            loadCounts();
            loadInventory(); // Refresh inventory to show updated quantities
        } else {
            alert('❌ Error creating count: ' + result.error);
        }
    } catch (error) {
        console.error('Error creating count:', error);
        alert('❌ Error creating count');
    }
}

async function viewCountDetails(countId) {
    try {
        const response = await fetch(`/api/counts/${countId}`);
        const count = await response.json();

        document.getElementById('countDetailsTitle').textContent = `Count ${count.count_number}`;

        let html = `
            <div class="details-section">
                <p><strong>Count Date:</strong> ${formatDate(count.count_date)}</p>
                <p><strong>Counted By:</strong> ${count.counted_by || 'N/A'}</p>
                <p><strong>Status:</strong> <span class="badge ${count.reconciled === 'YES' ? 'badge-success' : 'badge-warning'}">${count.reconciled}</span></p>
                ${count.notes ? `<p><strong>Notes:</strong> ${count.notes}</p>` : ''}
            </div>

            <h3 style="margin-top: 20px;">Count Items</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Code</th>
                            <th>Ingredient</th>
                            <th>Expected</th>
                            <th>Counted</th>
                            <th>Variance</th>
                            <th>Unit</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        let totalVariance = 0;
        count.line_items.forEach(item => {
            const variance = item.variance || 0;
            totalVariance += variance;
            const varianceClass = variance === 0 ? '' : variance > 0 ? 'variance-positive' : 'variance-negative';

            html += `
                <tr>
                    <td><code>${item.ingredient_code}</code></td>
                    <td>${item.ingredient_name}</td>
                    <td>${item.quantity_expected || 0}</td>
                    <td><strong>${item.quantity_counted}</strong></td>
                    <td class="${varianceClass}"><strong>${variance > 0 ? '+' : ''}${variance.toFixed(2)}</strong></td>
                    <td>${item.unit_of_measure}</td>
                    <td>${item.notes || '-'}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
            <div class="count-summary" style="margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <strong>Total Items: ${count.line_items.length}</strong> |
                <strong>Total Variance: <span class="${totalVariance === 0 ? '' : totalVariance > 0 ? 'variance-positive' : 'variance-negative'}">${totalVariance > 0 ? '+' : ''}${totalVariance.toFixed(2)}</span></strong>
            </div>
        `;

        document.getElementById('countDetailsContent').innerHTML = html;
        document.getElementById('countDetailsModal').classList.add('active');

    } catch (error) {
        console.error('Error loading count details:', error);
        alert('❌ Error loading count details');
    }
}

function closeCountDetailsModal() {
    document.getElementById('countDetailsModal').classList.remove('active');
}

async function deleteCount(countId, countNumber) {
    if (!confirm(`Are you sure you want to delete count ${countNumber}?\n\nNote: This will NOT reverse the inventory changes made by this count.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/counts/delete/${countId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            loadCounts();
        } else {
            alert('❌ Error deleting count: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting count:', error);
        alert('❌ Error deleting count');
    }
}

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

// Close modals when clicking outside (but NOT count modals)
window.addEventListener('click', function(event) {
    const categoryModal = document.getElementById('categoryModal');
    if (event.target === categoryModal) {
        closeCategoryModal();
    }

    // Count modals do NOT close on outside click to prevent accidental data loss
});

// ========== DATE FILTER CLEAR FUNCTIONS ==========

function clearInvoiceDateFilters() {
    document.getElementById('invoiceDateFrom').value = '';
    document.getElementById('invoiceDateTo').value = '';
    loadInvoices();
}

function applyInvoiceDateFilter() {
    const dateFrom = document.getElementById('invoiceDateFrom').value;
    const dateTo = document.getElementById('invoiceDateTo').value;
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

    loadInvoices().then(() => {
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

function clearCountDateFilters() {
    document.getElementById('countDateFrom').value = '';
    document.getElementById('countDateTo').value = '';
    loadCounts();
}

function applyCountDateFilter() {
    const dateFrom = document.getElementById('countDateFrom').value;
    const dateTo = document.getElementById('countDateTo').value;
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

    loadCounts().then(() => {
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


// ==================== ANALYTICS FUNCTIONS ====================

let analyticsCharts = {};
let analyticsRefreshInterval = null;
let currentAnalyticsPeriod = '30days';
let currentAnalyticsStartDate = null;
let currentAnalyticsEndDate = null;

/**
 * Change time period for analytics dashboard
 */
function changeAnalyticsPeriod(period) {
    // Update active button
    document.querySelectorAll('#analytics-tab .btn-time-filter').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.period === period) {
            btn.classList.add('active');
        }
    });

    // Hide custom date range
    document.getElementById('analytics-custom-date-range').style.display = 'none';

    currentAnalyticsPeriod = period;

    // Helper to convert Date to YYYY-MM-DD string
    const toDateString = (date) => date.toISOString().split('T')[0];

    // Calculate date range
    const today = new Date();
    let startDate, endDate, displayText;

    switch (period) {
        case 'today':
            startDate = endDate = toDateString(today);
            displayText = "Today's Analytics";
            break;

        case '7days':
            const days7Ago = new Date(today);
            days7Ago.setDate(today.getDate() - 7);
            startDate = toDateString(days7Ago);
            endDate = toDateString(today);
            displayText = "Last 7 Days";
            break;

        case 'week':
            const weekStart = new Date(today);
            weekStart.setDate(today.getDate() - today.getDay());
            startDate = toDateString(weekStart);
            endDate = toDateString(today);
            displayText = "This Week";
            break;

        case 'month':
            const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
            startDate = toDateString(monthStart);
            endDate = toDateString(today);
            displayText = "This Month";
            break;

        case '30days':
            const days30Ago = new Date(today);
            days30Ago.setDate(today.getDate() - 30);
            startDate = toDateString(days30Ago);
            endDate = toDateString(today);
            displayText = "Last 30 Days";
            break;

        case '90days':
            const days90Ago = new Date(today);
            days90Ago.setDate(today.getDate() - 90);
            startDate = toDateString(days90Ago);
            endDate = toDateString(today);
            displayText = "Last Quarter";
            break;

        case '365days':
            const days365Ago = new Date(today);
            days365Ago.setDate(today.getDate() - 365);
            startDate = toDateString(days365Ago);
            endDate = toDateString(today);
            displayText = "Last Year";
            break;

        case 'all':
            startDate = null;
            endDate = null;
            displayText = "All Time";
            break;
    }

    currentAnalyticsStartDate = startDate;
    currentAnalyticsEndDate = endDate;

    document.getElementById('analytics-period-display').textContent = displayText;

    // Reload analytics data
    refreshAnalytics();
}

/**
 * Show custom date range inputs for analytics
 */
function showAnalyticsCustomDateRange() {
    document.getElementById('analytics-custom-date-range').style.display = 'flex';

    // Set default values
    const today = new Date();
    const monthAgo = new Date(today);
    monthAgo.setDate(today.getDate() - 30);

    document.getElementById('analytics-start-date').value = formatDate(monthAgo);
    document.getElementById('analytics-end-date').value = formatDate(today);
}

/**
 * Apply custom date range for analytics
 */
function applyAnalyticsCustomDateRange() {
    const startDate = document.getElementById('analytics-start-date').value;
    const endDate = document.getElementById('analytics-end-date').value;
    const applyBtn = event.target;

    if (!startDate || !endDate) {
        showMessage('Please select both start and end dates', 'error');
        return;
    }

    // Validate date range
    if (new Date(endDate) < new Date(startDate)) {
        showMessage('End date must be after or equal to start date', 'error');
        return;
    }

    // Show loading state
    const originalText = applyBtn.innerHTML;
    applyBtn.innerHTML = '⏳ Loading...';
    applyBtn.disabled = true;

    currentAnalyticsStartDate = startDate;
    currentAnalyticsEndDate = endDate;

    document.querySelectorAll('#analytics-tab .btn-time-filter').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.period === 'custom') {
            btn.classList.add('active');
        }
    });

    // Format dates for display
    const startFormatted = new Date(startDate).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
    });
    const endFormatted = new Date(endDate).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
    });

    document.getElementById('analytics-period-display').textContent =
        `${startFormatted} - ${endFormatted}`;

    // Hide custom date range section after applying
    document.getElementById('analytics-custom-date-range').style.display = 'none';

    refreshAnalytics().then(() => {
        // Restore button state
        applyBtn.innerHTML = '✓ Applied!';
        setTimeout(() => {
            applyBtn.innerHTML = originalText;
            applyBtn.disabled = false;
        }, 1500);
    }).catch(() => {
        applyBtn.innerHTML = originalText;
        applyBtn.disabled = false;
    });
}

async function loadAnalytics() {
    console.log('loadAnalytics() called');
    try {
        await loadAnalyticsKPIs();
        await loadAnalyticsWidgets();

        console.log('Analytics loaded successfully');
    } catch (error) {
        console.error('Error loading analytics:', error);
        showMessage('Failed to load analytics', 'error');
    }
}

async function loadAnalyticsKPIs() {
    let dateFrom = currentAnalyticsStartDate || '';
    let dateTo = currentAnalyticsEndDate || '';

    const response = await fetch(`/api/analytics/summary?date_from=${dateFrom}&date_to=${dateTo}`);
    const data = await response.json();

    document.getElementById('kpiSpending').textContent = `$${data.total_spend.toLocaleString()}`;
    document.getElementById('kpiSuppliers').textContent = data.supplier_count;
    document.getElementById('kpiAlerts').textContent = data.alert_count;
    document.getElementById('kpiInventoryValue').textContent = `$${data.inventory_value.toLocaleString()}`;
}

async function loadAnalyticsWidgets() {
    console.log('loadAnalyticsWidgets() called');
    const response = await fetch('/api/analytics/widgets/enabled?user_id=default');
    const widgets = await response.json();
    console.log('Loaded widgets:', widgets.length);

    const container = document.getElementById('analyticsWidgetsContainer');
    container.innerHTML = '';

    if (widgets.length === 0) {
        container.innerHTML = '<div class="widget-placeholder"><p>No widgets enabled. Click "Customize" to add widgets.</p></div>';
        return;
    }

    for (const widget of widgets) {
        console.log('Creating widget:', widget.widget_key);
        const widgetElement = createWidgetElement(widget);
        container.appendChild(widgetElement);
        await renderWidget(widget);
    }
    console.log('All widgets rendered');

    // Show default "Spending" page after widgets are loaded
    setTimeout(() => {
        const spendingBtn = document.querySelector('.analytics-subtab-btn');
        if (spendingBtn) {
            spendingBtn.click();
        }
    }, 100);
}

function createWidgetElement(widget) {
    const div = document.createElement('div');
    div.className = `analytics-widget widget-${widget.size || 'medium'}`;
    div.id = `widget-${widget.widget_key}`;

    // Add widget-specific controls
    let controlsHTML = '';
    if (widget.widget_key === 'price_trends') {
        controlsHTML = '';
    } else if (widget.widget_key === 'supplier_performance') {
        controlsHTML = `
            <div class="widget-controls" id="controls-${widget.widget_key}">
                <label>Items per page:</label>
                <select id="supplier-page-size" onchange="updateSupplierPerformance()">
                    <option value="5">5</option>
                    <option value="10" selected>10</option>
                    <option value="20">20</option>
                </select>
            </div>
        `;
    }

    // Add reset zoom button for chart widgets
    const resetZoomButton = widget.widget_type === 'chart' && widget.chart_type !== 'doughnut' && widget.chart_type !== 'pie'
        ? `<button onclick="resetChartZoom('${widget.widget_key}'); refreshWidget('${widget.widget_key}');" title="Reset Zoom">🔍↺</button>`
        : '';

    div.innerHTML = `
        <div class="widget-header">
            <div class="widget-title">
                <span class="widget-icon">${widget.icon || '📊'}</span>
                <span class="widget-title-text" title="${widget.description || ''}">${widget.widget_name}</span>
            </div>
            <div class="widget-actions">
                ${resetZoomButton}
                <button onclick="refreshWidget('${widget.widget_key}')" title="Refresh">🔄</button>
                <button onclick="exportWidget('${widget.widget_key}')" title="Export CSV">📥</button>
            </div>
        </div>
        ${controlsHTML}
        <div class="widget-body" id="widget-body-${widget.widget_key}">
            <div class="widget-loading">Loading...</div>
        </div>
    `;

    return div;
}

async function renderWidget(widget) {
    const bodyElement = document.getElementById(`widget-body-${widget.widget_key}`);

    try {
        let dateFrom = currentAnalyticsStartDate || '';
        let dateTo = currentAnalyticsEndDate || '';

        // Special handling for price_trends - load all items and show initial chart
        if (widget.widget_key === 'price_trends') {
            await loadPriceTrendItems();
            return;
        }

        // Special handling for supplier_performance - use pagination
        if (widget.widget_key === 'supplier_performance') {
            await renderSupplierPerformancePaginated();
            return;
        }

        const endpoint = `/api/analytics/${widget.widget_key.replace(/_/g, '-')}?date_from=${dateFrom}&date_to=${dateTo}`;
        const response = await fetch(endpoint);
        const data = await response.json();

        bodyElement.innerHTML = '';

        if (widget.widget_type === 'chart') {
            const canvas = document.createElement('canvas');
            canvas.id = `chart-${widget.widget_key}`;
            bodyElement.appendChild(canvas);

            if (widget.chart_type === 'doughnut' || widget.chart_type === 'pie') {
                renderPieChart(widget.widget_key, data, canvas);
            } else if (widget.chart_type === 'line' || widget.chart_type === 'area') {
                // Special handling for price_trends line chart
                if (widget.widget_key === 'price_trends') {
                    renderPriceTrendChart(data, canvas);
                } else {
                    renderLineChart(widget.widget_key, data, canvas, widget.chart_type === 'area');
                }
            } else if (widget.chart_type === 'bar') {
                renderBarChart(widget.widget_key, data, canvas);
            } else if (widget.chart_type === 'scatter') {
                renderScatterChart(widget.widget_key, data, canvas);
            } else if (widget.chart_type === 'heatmap') {
                renderHeatmapChart(widget.widget_key, data, bodyElement);
            }
        } else if (widget.widget_type === 'table') {
            renderTableWidget(widget.widget_key, data, bodyElement);
        } else if (widget.widget_type === 'metric') {
            renderMetricWidget(widget.widget_key, data, bodyElement);
        }
    } catch (error) {
        console.error(`Error rendering widget ${widget.widget_key}:`, error);
        bodyElement.innerHTML = '<div class="widget-error">Failed to load data</div>';
    }
}

// Chart zoom state management
function saveChartZoomState(widgetKey, scales) {
    try {
        const zoomState = {
            x: scales.x ? {
                min: scales.x.min,
                max: scales.x.max
            } : null,
            y: scales.y ? {
                min: scales.y.min,
                max: scales.y.max
            } : null
        };
        localStorage.setItem(`chart_zoom_${widgetKey}`, JSON.stringify(zoomState));
    } catch (e) {
        console.warn('Failed to save zoom state:', e);
    }
}

function getChartZoomState(widgetKey) {
    try {
        const saved = localStorage.getItem(`chart_zoom_${widgetKey}`);
        return saved ? JSON.parse(saved) : null;
    } catch (e) {
        console.warn('Failed to load zoom state:', e);
        return null;
    }
}

function resetChartZoom(widgetKey) {
    localStorage.removeItem(`chart_zoom_${widgetKey}`);
    if (analyticsCharts[widgetKey]) {
        analyticsCharts[widgetKey].resetZoom();
    }
}

function getZoomPanConfig(widgetKey) {
    return {
        zoom: {
            wheel: {
                enabled: true,
                modifierKey: null  // No modifier key needed
            },
            pinch: {
                enabled: true
            },
            mode: 'xy',
            onZoomComplete: function({chart}) {
                saveChartZoomState(widgetKey, chart.scales);
            }
        },
        pan: {
            enabled: true,
            mode: 'xy',
            modifierKey: null,
            onPanComplete: function({chart}) {
                saveChartZoomState(widgetKey, chart.scales);
            }
        },
        limits: {
            x: {min: 'original', max: 'original'},
            y: {min: 'original', max: 'original'}
        }
    };
}

function renderPieChart(widgetKey, data, canvas) {
    if (analyticsCharts[widgetKey]) {
        analyticsCharts[widgetKey].destroy();
    }

    // Generate colors for all categories
    const baseColors = [
        '#667eea', '#764ba2', '#f093fb', '#4facfe',
        '#43e97b', '#fa709a', '#fee140', '#30cfd0',
        '#a8edea', '#fed6e3', '#eb3349', '#f45c43',
        '#ffd89b', '#19547b', '#2c3e50', '#3498db',
        '#e74c3c', '#9b59b6', '#1abc9c', '#f39c12'
    ];

    // Extend colors if we have more categories than base colors
    const numCategories = (data.labels || []).length;
    const colors = [];
    for (let i = 0; i < numCategories; i++) {
        colors.push(baseColors[i % baseColors.length]);
    }

    const ctx = canvas.getContext('2d');
    analyticsCharts[widgetKey] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels || [],
            datasets: [{
                data: data.values || [],
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        boxWidth: 12,
                        padding: 10,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: $${value.toLocaleString()} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

function renderLineChart(widgetKey, data, canvas, filled = false) {
    if (analyticsCharts[widgetKey]) {
        analyticsCharts[widgetKey].destroy();
    }

    const ctx = canvas.getContext('2d');
    const datasets = (data.datasets || []).map((ds, index) => ({
        label: ds.label,
        data: ds.data,
        borderColor: ['#667eea', '#43e97b', '#fa709a', '#fee140'][index % 4],
        backgroundColor: filled ? ['rgba(102, 126, 234, 0.1)', 'rgba(67, 233, 123, 0.1)', 'rgba(250, 112, 154, 0.1)'][index % 3] : 'transparent',
        borderWidth: 2,
        tension: 0.4,
        fill: filled,
        pointRadius: 3,
        pointHoverRadius: 5
    }));

    // Get saved zoom state
    const savedZoom = getChartZoomState(widgetKey);
    const scalesConfig = {
        y: {
            beginAtZero: true,
            ticks: {
                callback: function(value) {
                    return '$' + value.toLocaleString();
                }
            }
        }
    };

    // Restore saved zoom if available
    if (savedZoom) {
        if (savedZoom.x) {
            scalesConfig.x = { min: savedZoom.x.min, max: savedZoom.x.max };
        }
        if (savedZoom.y) {
            scalesConfig.y = { ...scalesConfig.y, min: savedZoom.y.min, max: savedZoom.y.max };
        }
    }

    analyticsCharts[widgetKey] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels || [],
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { font: { size: 11 } }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                },
                zoom: getZoomPanConfig(widgetKey)
            },
            scales: scalesConfig
        }
    });
}

function renderBarChart(widgetKey, data, canvas) {
    if (analyticsCharts[widgetKey]) {
        analyticsCharts[widgetKey].destroy();
    }

    const ctx = canvas.getContext('2d');

    // Determine if this is a percentage chart
    const isPercentage = (data.dataset_label || '').includes('%');

    // Format function based on data type
    const formatValue = function(value) {
        if (isPercentage) {
            return value.toFixed(1) + '%';
        } else {
            return '$' + value.toLocaleString();
        }
    };

    // Get saved zoom state
    const savedZoom = getChartZoomState(widgetKey);
    const scalesConfig = {
        y: {
            beginAtZero: true,
            ticks: {
                callback: formatValue
            }
        }
    };

    // Restore saved zoom if available
    if (savedZoom) {
        if (savedZoom.x) {
            scalesConfig.x = { min: savedZoom.x.min, max: savedZoom.x.max };
        }
        if (savedZoom.y) {
            scalesConfig.y = { ...scalesConfig.y, min: savedZoom.y.min, max: savedZoom.y.max };
        }
    }

    analyticsCharts[widgetKey] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels || [],
            datasets: [{
                label: data.dataset_label || 'Value',
                data: data.values || [],
                backgroundColor: '#667eea',
                borderColor: '#764ba2',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return formatValue(context.parsed.y);
                        }
                    }
                },
                zoom: getZoomPanConfig(widgetKey)
            },
            scales: scalesConfig
        }
    });
}

function renderScatterChart(widgetKey, data, canvas) {
    if (analyticsCharts[widgetKey]) {
        analyticsCharts[widgetKey].destroy();
    }

    const ctx = canvas.getContext('2d');
    const datasets = (data.quadrants || []).map((quad, index) => ({
        label: quad.label,
        data: quad.data,
        backgroundColor: ['#43e97b', '#667eea', '#fee140', '#fa709a'][index],
        pointRadius: 6,
        pointHoverRadius: 8
    }));

    // Get saved zoom state
    const savedZoom = getChartZoomState(widgetKey);
    const scalesConfig = {
        x: {
            title: { display: true, text: data.x_label || 'X Axis' }
        },
        y: {
            title: { display: true, text: data.y_label || 'Y Axis' }
        }
    };

    // Restore saved zoom if available
    if (savedZoom) {
        if (savedZoom.x) {
            scalesConfig.x = { ...scalesConfig.x, min: savedZoom.x.min, max: savedZoom.x.max };
        }
        if (savedZoom.y) {
            scalesConfig.y = { ...scalesConfig.y, min: savedZoom.y.min, max: savedZoom.y.max };
        }
    }

    analyticsCharts[widgetKey] = new Chart(ctx, {
        type: 'scatter',
        data: { datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { font: { size: 11 } }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.raw.name}: Margin ${context.parsed.x}%, Volume ${context.parsed.y}`;
                        }
                    }
                },
                zoom: getZoomPanConfig(widgetKey)
            },
            scales: scalesConfig
        }
    });
}

function renderHeatmapChart(widgetKey, data, container) {
    const table = document.createElement('table');
    table.className = 'heatmap-table';

    // Header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.innerHTML = '<th></th>';
    data.columns.forEach(col => {
        headerRow.innerHTML += `<th>${col}</th>`;
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Data rows
    const tbody = document.createElement('tbody');
    data.rows.forEach((row, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<th>${row}</th>`;
        data.values[i].forEach(val => {
            const intensity = Math.abs(val);
            const color = val > 0 ? `rgba(67, 233, 123, ${intensity})` : `rgba(250, 112, 154, ${intensity})`;
            tr.innerHTML += `<td style="background-color: ${color}">${val.toFixed(2)}</td>`;
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    container.appendChild(table);
}

function renderTableWidget(widgetKey, data, container) {
    const table = document.createElement('table');
    table.className = 'widget-table';

    // Header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    data.columns.forEach(col => {
        headerRow.innerHTML += `<th>${col}</th>`;
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Rows
    const tbody = document.createElement('tbody');
    data.rows.forEach(row => {
        const tr = document.createElement('tr');
        row.forEach((cell, index) => {
            const className = data.row_classes && data.row_classes[index] ? data.row_classes[index] : '';
            tr.innerHTML += `<td class="${className}">${cell}</td>`;
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    container.appendChild(table);
}

function renderMetricWidget(widgetKey, data, container) {
    container.innerHTML = `
        <div class="metric-display">
            <div class="metric-value">${data.value}</div>
            <div class="metric-label">${data.label}</div>
            ${data.trend ? `<div class="metric-trend ${data.trend > 0 ? 'trend-up' : 'trend-down'}">${data.trend > 0 ? '↑' : '↓'} ${Math.abs(data.trend)}%</div>` : ''}
        </div>
    `;
}

async function refreshAnalytics() {
    await loadAnalytics();
}

async function refreshWidget(widgetKey) {
    const response = await fetch('/api/analytics/widgets/enabled?user_id=default');
    const widgets = await response.json();
    const widget = widgets.find(w => w.widget_key === widgetKey);

    if (widget) {
        await renderWidget(widget);
    }
}

async function openCustomizeWidgets() {
    const modal = document.getElementById('customizeWidgetsModal');
    modal.style.display = 'block';

    // Load available widgets
    const availableResponse = await fetch('/api/analytics/widgets/available');
    const allWidgets = await availableResponse.json();

    // Load enabled widgets
    const enabledResponse = await fetch('/api/analytics/widgets/enabled?user_id=default');
    const enabledWidgets = await enabledResponse.json();

    const enabledKeys = new Set(enabledWidgets.map(w => w.widget_key));

    // Populate enabled widgets list
    const enabledList = document.getElementById('enabledWidgetsList');
    enabledList.innerHTML = '';
    enabledWidgets.forEach(widget => {
        const item = document.createElement('div');
        item.className = 'widget-list-item enabled';
        item.innerHTML = `
            <span class="drag-handle">⋮⋮</span>
            <span class="widget-icon">${widget.icon}</span>
            <div class="widget-info">
                <div class="widget-list-name">${widget.widget_name}</div>
                <div class="widget-list-desc">${widget.description}</div>
            </div>
            <button class="btn-small btn-danger" onclick="disableWidget('${widget.widget_key}')">Remove</button>
        `;
        enabledList.appendChild(item);
    });

    // Populate available widgets list
    const availableList = document.getElementById('availableWidgetsList');
    availableList.innerHTML = '';
    allWidgets.filter(w => !enabledKeys.has(w.widget_key)).forEach(widget => {
        const item = document.createElement('div');
        item.className = 'widget-list-item';
        item.innerHTML = `
            <span class="widget-icon">${widget.icon}</span>
            <div class="widget-info">
                <div class="widget-list-name">${widget.widget_name}</div>
                <div class="widget-list-desc">${widget.description}</div>
                <div class="widget-category">${widget.category}</div>
            </div>
            <button class="btn-small btn-success" onclick="enableWidget('${widget.widget_key}')">Add</button>
        `;
        availableList.appendChild(item);
    });
}

function closeCustomizeWidgets() {
    document.getElementById('customizeWidgetsModal').style.display = 'none';
    loadAnalytics();
}

async function enableWidget(widgetKey) {
    const response = await fetch('/api/analytics/widgets/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: 'default',
            widget_key: widgetKey,
            enabled: 1
        })
    });

    if (response.ok) {
        await openCustomizeWidgets();
    }
}

async function disableWidget(widgetKey) {
    const response = await fetch('/api/analytics/widgets/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: 'default',
            widget_key: widgetKey,
            enabled: 0
        })
    });

    if (response.ok) {
        await openCustomizeWidgets();
    }
}

function filterWidgets() {
    const searchTerm = document.getElementById('widgetSearch').value.toLowerCase();
    const category = document.getElementById('widgetCategoryFilter').value;

    const items = document.querySelectorAll('#availableWidgetsList .widget-list-item');
    items.forEach(item => {
        const name = item.querySelector('.widget-list-name').textContent.toLowerCase();
        const desc = item.querySelector('.widget-list-desc').textContent.toLowerCase();
        const cat = item.querySelector('.widget-category').textContent.toLowerCase();

        const matchesSearch = name.includes(searchTerm) || desc.includes(searchTerm);
        const matchesCategory = !category || cat === category;

        item.style.display = matchesSearch && matchesCategory ? 'flex' : 'none';
    });
}

async function exportWidget(widgetKey) {
    let dateFrom = currentAnalyticsStartDate || '';
    let dateTo = currentAnalyticsEndDate || '';

    // Build base URL
    let url = `/api/analytics/${widgetKey.replace(/_/g, '-')}/export?date_from=${dateFrom}&date_to=${dateTo}&format=csv`;

    // Add widget-specific parameters
    if (widgetKey === 'category_spending') {
        const select = document.getElementById('category-spending-selector');
        if (select) {
            const selected = Array.from(select.selectedOptions).map(opt => opt.value);
            if (selected.length > 0) {
                url += `&categories=${selected.join(',')}`;
            }
        }
    } else if (widgetKey === 'price_trends') {
        const hiddenInput = document.getElementById('pricetrend-selected-code');
        if (hiddenInput && hiddenInput.value) {
            url += `&ingredient_code=${hiddenInput.value}`;
        }
    }

    window.location.href = url;
}

// ========== PRICE TRENDS WIDGET FUNCTIONS ==========

// ========== PRICE TREND ANALYSIS WIDGET ==========

let allPriceTrendItems = []; // Store all items for search filtering

async function loadPriceTrendItems() {
    try {
        // Load items with price history and frequency data
        const [inventoryResponse, frequencyResponse, priceHistoryResponse] = await Promise.all([
            fetch('/api/inventory/detailed?status=active'),
            fetch('/api/analytics/purchase-frequency'),
            fetch('/api/analytics/ingredients-with-price-history')
        ]);

        const items = await inventoryResponse.json();
        const frequencyData = await frequencyResponse.json();
        const priceHistoryData = await priceHistoryResponse.json();

        // Create sets for faster lookup
        const frequencyMap = {};
        frequencyData.ingredients.forEach(item => {
            frequencyMap[item.code] = item.frequency;
        });

        const itemsWithHistory = new Set(priceHistoryData.ingredient_codes || []);

        // Filter to only items with price history, add frequency data
        allPriceTrendItems = items
            .filter(item => itemsWithHistory.has(item.ingredient_code))
            .map(item => ({
                code: item.ingredient_code,
                name: `${item.ingredient_name} - ${item.brand || 'No Brand'} (${item.supplier_name || 'No Supplier'})`,
                frequency: frequencyMap[item.ingredient_code] || 'monthly'
            }))
            .sort((a, b) => a.name.localeCompare(b.name));

        // Create custom side-by-side layout
        const bodyElement = document.getElementById('widget-body-price_trends');
        bodyElement.innerHTML = `
            <div style="display: flex; gap: 20px; min-height: 500px;">
                <div id="pricetrend-chart-container" style="flex: 0 0 60%; display: flex; flex-direction: column;">
                    <canvas id="chart-price_trends" style="flex: 1;"></canvas>
                </div>
                <div id="pricetrend-controls-container" style="flex: 0 0 38%; display: flex; flex-direction: column; gap: 20px; padding: 20px; background: linear-gradient(135deg, rgba(var(--theme-color-1-rgb), 0.05), rgba(var(--theme-color-2-rgb), 0.05)); border-radius: 12px; border: 2px solid var(--theme-color-1);">
                    <div>
                        <h3 style="margin: 0 0 15px 0; color: var(--theme-color-1); font-size: 18px;">📊 Chart Controls</h3>

                        <div style="margin-bottom: 25px;">
                            <label style="display: block; font-weight: 600; margin-bottom: 10px; font-size: 15px;">Purchase Frequency Filter:</label>
                            <div style="display: flex; flex-direction: column; gap: 8px; padding: 12px; background: white; border-radius: 8px;">
                                <label style="cursor: pointer; padding: 6px; border-radius: 4px; transition: background 0.2s;" onmouseover="this.style.background='rgba(var(--theme-color-1-rgb), 0.1)'" onmouseout="this.style.background='transparent'">
                                    <input type="radio" name="pricetrend-frequency" value="all" checked onchange="filterPriceTrendDropdown()"> <strong>All Items</strong>
                                </label>
                                <label style="cursor: pointer; padding: 6px; border-radius: 4px; transition: background 0.2s;" onmouseover="this.style.background='rgba(var(--theme-color-1-rgb), 0.1)'" onmouseout="this.style.background='transparent'">
                                    <input type="radio" name="pricetrend-frequency" value="daily" onchange="filterPriceTrendDropdown()"> Daily (&lt;3 days)
                                </label>
                                <label style="cursor: pointer; padding: 6px; border-radius: 4px; transition: background 0.2s;" onmouseover="this.style.background='rgba(var(--theme-color-1-rgb), 0.1)'" onmouseout="this.style.background='transparent'">
                                    <input type="radio" name="pricetrend-frequency" value="weekly" onchange="filterPriceTrendDropdown()"> Weekly (3-10 days)
                                </label>
                                <label style="cursor: pointer; padding: 6px; border-radius: 4px; transition: background 0.2s;" onmouseover="this.style.background='rgba(--theme-color-1-rgb), 0.1)'" onmouseout="this.style.background='transparent'">
                                    <input type="radio" name="pricetrend-frequency" value="monthly" onchange="filterPriceTrendDropdown()"> Monthly (&gt;10 days)
                                </label>
                            </div>
                        </div>

                        <div style="margin-bottom: 25px;">
                            <label style="display: block; font-weight: 600; margin-bottom: 10px; font-size: 15px;">Search & Select Item:</label>
                            <div style="position: relative;">
                                <input type="text" id="pricetrend-search" placeholder="Type to search items..."
                                       style="width: 100%; padding: 12px; font-size: 14px; border: 2px solid var(--theme-color-1); border-radius: 8px;"
                                       onfocus="showPriceTrendDropdown()"
                                       oninput="filterPriceTrendDropdown()">
                                <div id="pricetrend-dropdown" style="display: none; position: absolute; top: 100%; left: 0; right: 0; max-height: 250px; overflow-y: auto; background: white; border: 2px solid var(--theme-color-1); border-top: none; border-radius: 0 0 8px 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 1000; margin-top: -2px;">
                                </div>
                                <input type="hidden" id="pricetrend-selected-code" value="">
                            </div>
                            <div id="pricetrend-selected-item" style="margin-top: 12px; padding: 12px; background: white; border-radius: 8px; font-weight: 600; color: var(--theme-color-1); border: 2px solid var(--theme-color-1); min-height: 44px; display: flex; align-items: center;">
                                No item selected
                            </div>
                        </div>

                        <div style="margin-bottom: 20px;">
                            <label style="display: block; font-weight: 600; margin-bottom: 10px; font-size: 15px;">Date Range:</label>
                            <div style="background: white; padding: 15px; border-radius: 8px; display: flex; flex-direction: column; gap: 12px;">
                                <div>
                                    <label style="display: block; margin-bottom: 6px; color: #666; font-size: 13px;">From Date:</label>
                                    <input type="date" id="pricetrend-date-from" style="width: 100%; padding: 10px; font-size: 14px; border: 2px solid #ddd; border-radius: 6px;" onchange="updatePriceTrend()">
                                </div>
                                <div>
                                    <label style="display: block; margin-bottom: 6px; color: #666; font-size: 13px;">To Date:</label>
                                    <input type="date" id="pricetrend-date-to" style="width: 100%; padding: 10px; font-size: 14px; border: 2px solid #ddd; border-radius: 6px;" onchange="updatePriceTrend()">
                                </div>
                            </div>
                        </div>

                        <button onclick="updatePriceTrend()" style="width: 100%; padding: 14px; font-size: 16px; font-weight: 600; background: var(--theme-gradient); color: white; border: none; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 12px rgba(var(--theme-color-1-rgb), 0.3); transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                            📈 Update Chart
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Set default date range (last 90 days)
        const today = new Date();
        const ninetyDaysAgo = new Date(today);
        ninetyDaysAgo.setDate(today.getDate() - 90);

        const dateFrom = document.getElementById('pricetrend-date-from');
        const dateTo = document.getElementById('pricetrend-date-to');
        if (dateFrom) dateFrom.value = ninetyDaysAgo.toISOString().split('T')[0];
        if (dateTo) dateTo.value = today.toISOString().split('T')[0];

        // Set up click-outside to close dropdown
        document.addEventListener('click', function(e) {
            const searchInput = document.getElementById('pricetrend-search');
            const dropdown = document.getElementById('pricetrend-dropdown');
            if (dropdown && searchInput && !searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });

        // Auto-select first item and render
        if (allPriceTrendItems.length > 0) {
            selectPriceTrendItem(allPriceTrendItems[0].code, allPriceTrendItems[0].name);
        }
    } catch (error) {
        console.error('Error loading price trend items:', error);
        const bodyElement = document.getElementById('widget-body-price_trends');
        if (bodyElement) bodyElement.innerHTML = '<div style="padding: 20px; color: red;">Error loading price trend items</div>';
    }
}

function showPriceTrendDropdown() {
    const dropdown = document.getElementById('pricetrend-dropdown');
    if (dropdown && allPriceTrendItems.length > 0) {
        filterPriceTrendDropdown();
    }
}

function selectPriceTrendItem(code, name) {
    const hiddenInput = document.getElementById('pricetrend-selected-code');
    const selectedItemDiv = document.getElementById('pricetrend-selected-item');
    const dropdown = document.getElementById('pricetrend-dropdown');
    const searchInput = document.getElementById('pricetrend-search');

    if (hiddenInput) hiddenInput.value = code;
    if (selectedItemDiv) selectedItemDiv.textContent = name;
    if (dropdown) dropdown.style.display = 'none';
    if (searchInput) searchInput.value = '';

    updatePriceTrend();
}

function filterPriceTrendDropdown() {
    const searchInput = document.getElementById('pricetrend-search');
    const dropdown = document.getElementById('pricetrend-dropdown');
    if (!searchInput || !dropdown) return;

    // Get selected frequency
    const frequencyRadios = document.querySelectorAll('input[name="pricetrend-frequency"]');
    let selectedFrequency = 'all';
    frequencyRadios.forEach(radio => {
        if (radio.checked) selectedFrequency = radio.value;
    });

    // Filter by search term and frequency
    const searchTerm = searchInput.value.toLowerCase();
    let filtered = allPriceTrendItems;

    // Apply search filter
    if (searchTerm !== '') {
        filtered = filtered.filter(item => item.name.toLowerCase().includes(searchTerm));
    }

    // Apply frequency filter
    if (selectedFrequency !== 'all') {
        filtered = filtered.filter(item => item.frequency === selectedFrequency);
    }

    // Limit to first 50 results for performance
    filtered = filtered.slice(0, 50);

    // Populate dropdown with clickable results
    if (filtered.length === 0) {
        dropdown.innerHTML = '<div style="padding: 12px; color: #999;">No items found</div>';
    } else {
        dropdown.innerHTML = filtered.map(item => `
            <div onclick="selectPriceTrendItem('${item.code}', '${item.name.replace(/'/g, "\\'")}');"
                 style="padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #eee;"
                 onmouseover="this.style.background='var(--theme-color-1)'; this.style.color='white';"
                 onmouseout="this.style.background='white'; this.style.color='inherit';">
                ${item.name}
            </div>
        `).join('');
    }

    dropdown.style.display = 'block';
}

async function updatePriceTrend() {
    const hiddenInput = document.getElementById('pricetrend-selected-code');
    const dateFrom = document.getElementById('pricetrend-date-from');
    const dateTo = document.getElementById('pricetrend-date-to');

    if (!hiddenInput || !hiddenInput.value) {
        showMessage('Please select an item', 'warning');
        return;
    }

    const ingredientCode = hiddenInput.value;
    const chartContainer = document.getElementById('pricetrend-chart-container');
    if (!chartContainer) return;

    chartContainer.innerHTML = '<div class="widget-loading" style="display: flex; align-items: center; justify-content: center; height: 100%;">Loading chart...</div>';

    try {
        let url = `/api/analytics/price-trends?ingredient_code=${ingredientCode}`;
        if (dateFrom && dateFrom.value) url += `&date_from=${dateFrom.value}`;
        if (dateTo && dateTo.value) url += `&date_to=${dateTo.value}`;

        const response = await fetch(url);
        const data = await response.json();

        chartContainer.innerHTML = '';
        const canvas = document.createElement('canvas');
        canvas.id = 'chart-price_trends';
        canvas.style.flex = '1';
        chartContainer.appendChild(canvas);

        renderPriceTrendChart(data, canvas);
    } catch (error) {
        console.error('Error updating price trend:', error);
        bodyElement.innerHTML = '<div class="widget-error">Failed to load data</div>';
    }
}

function renderPriceTrendChart(data, canvas) {
    if (analyticsCharts['price_trends']) {
        analyticsCharts['price_trends'].destroy();
    }

    if (!data.data || data.data.length === 0) {
        canvas.parentElement.innerHTML = '<div class="widget-placeholder"><p>No price history available for this item in the selected date range</p></div>';
        return;
    }

    const ctx = canvas.getContext('2d');

    // Prepare chart data
    const chartData = data.data.map(d => ({
        x: d.date,
        y: d.price
    }));

    analyticsCharts['price_trends'] = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                label: data.name || 'Price',
                data: chartData,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 3,
                tension: 0.1,
                fill: true,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: '#667eea',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Price: $${context.parsed.y.toFixed(2)}`;
                        }
                    }
                },
                zoom: getZoomPanConfig('price_trends')
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day',
                        displayFormats: {
                            day: 'MMM d, yyyy'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Unit Price ($)'
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toFixed(2);
                        }
                    }
                }
            }
        }
    });
}

// ========== CATEGORY SPENDING WIDGET FUNCTIONS ==========

async function populateCategorySpendingSelector() {
    const select = document.getElementById('category-spending-selector');
    if (!select) return;

    try {
        // Fetch all available categories
        const response = await fetch('/api/analytics/categories');
        const data = await response.json();

        // Populate the multi-select with all categories
        select.innerHTML = data.categories.map(category => {
            return `<option value="${category}">${category}</option>`;
        }).join('');

        // Auto-select first 5 categories
        for (let i = 0; i < Math.min(5, select.options.length); i++) {
            select.options[i].selected = true;
        }

        // Trigger initial render with default selection
        await updateCategorySpending();
    } catch (error) {
        console.error('Error loading categories:', error);
        select.innerHTML = '<option value="">Error loading categories</option>';
    }
}

async function updateCategorySpending() {
    const select = document.getElementById('category-spending-selector');
    const selected = Array.from(select.selectedOptions).map(opt => opt.value);

    if (selected.length === 0) {
        showMessage('Please select at least one category', 'warning');
        return;
    }

    const bodyElement = document.getElementById('widget-body-category_spending');
    bodyElement.innerHTML = '<div class="widget-loading">Loading...</div>';

    try {
        let dateFrom = currentAnalyticsStartDate || '';
        let dateTo = currentAnalyticsEndDate || '';

        const params = `categories=${selected.join(',')}&date_from=${dateFrom}&date_to=${dateTo}`;
        const response = await fetch(`/api/analytics/category-spending?${params}`);
        const data = await response.json();

        // Clear and render chart
        bodyElement.innerHTML = '';
        const canvas = document.createElement('canvas');
        canvas.id = 'chart-category_spending';
        bodyElement.appendChild(canvas);

        // Render as doughnut chart (matching existing widget type)
        renderPieChart('category_spending', data, canvas);
    } catch (error) {
        console.error('Error updating category spending:', error);
        bodyElement.innerHTML = '<div class="widget-error">Failed to load data</div>';
    }
}

function selectAllCategories() {
    const select = document.getElementById('category-spending-selector');
    if (!select) return;

    for (let i = 0; i < select.options.length; i++) {
        select.options[i].selected = true;
    }
}

function clearCategorySelection() {
    const select = document.getElementById('category-spending-selector');
    if (!select) return;

    for (let i = 0; i < select.options.length; i++) {
        select.options[i].selected = false;
    }
}

// ========== SUPPLIER PERFORMANCE WIDGET FUNCTIONS ==========

let supplierPerformanceState = {
    currentPage: 1,
    pageSize: 10,
    allData: [],
    columns: []
};

async function renderSupplierPerformancePaginated() {
    const bodyElement = document.getElementById('widget-body-supplier_performance');
    bodyElement.innerHTML = '<div class="widget-loading">Loading...</div>';

    try {
        let dateFrom = currentAnalyticsStartDate || '';
        let dateTo = currentAnalyticsEndDate || '';

        const response = await fetch(`/api/analytics/supplier-performance?date_from=${dateFrom}&date_to=${dateTo}`);
        const data = await response.json();

        // Data comes in table format with columns and rows
        supplierPerformanceState.allData = data.rows || [];
        supplierPerformanceState.columns = data.columns || [];
        supplierPerformanceState.currentPage = 1;

        // Get page size from control
        const pageSizeSelect = document.getElementById('supplier-page-size');
        if (pageSizeSelect) {
            supplierPerformanceState.pageSize = parseInt(pageSizeSelect.value);
        }

        renderSupplierPerformancePage();
    } catch (error) {
        console.error('Error loading supplier performance:', error);
        bodyElement.innerHTML = '<div class="widget-error">Failed to load data</div>';
    }
}

function renderSupplierPerformancePage() {
    const bodyElement = document.getElementById('widget-body-supplier_performance');
    const { currentPage, pageSize, allData, columns } = supplierPerformanceState;

    if (!allData || allData.length === 0) {
        bodyElement.innerHTML = '<div class="widget-placeholder"><p>No supplier data available</p></div>';
        return;
    }

    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const pageData = allData.slice(startIndex, endIndex);
    const totalPages = Math.max(1, Math.ceil(allData.length / pageSize));

    // Create table
    let html = `
        <table class="widget-table">
            <thead>
                <tr>
    `;

    // Use the columns from the data
    columns.forEach(col => {
        html += `<th>${col}</th>`;
    });

    html += `
                </tr>
            </thead>
            <tbody>
    `;

    // Each row is an array of values
    pageData.forEach(row => {
        html += '<tr>';
        row.forEach(cell => {
            html += `<td>${cell}</td>`;
        });
        html += '</tr>';
    });

    html += `
            </tbody>
        </table>
    `;

    // Add pagination controls
    html += `
        <div class="widget-pagination">
            <button onclick="changeSupplierPage(-1)" ${currentPage === 1 ? 'disabled' : ''}>← Previous</button>
            <span class="page-info">Page ${currentPage} of ${totalPages} (${allData.length} suppliers)</span>
            <button onclick="changeSupplierPage(1)" ${currentPage >= totalPages ? 'disabled' : ''}>Next →</button>
        </div>
    `;

    bodyElement.innerHTML = html;
}

function changeSupplierPage(delta) {
    const totalPages = Math.ceil(supplierPerformanceState.allData.length / supplierPerformanceState.pageSize);
    const newPage = supplierPerformanceState.currentPage + delta;

    if (newPage >= 1 && newPage <= totalPages) {
        supplierPerformanceState.currentPage = newPage;
        renderSupplierPerformancePage();
    }
}

function updateSupplierPerformance() {
    const pageSizeSelect = document.getElementById('supplier-page-size');
    if (pageSizeSelect) {
        supplierPerformanceState.pageSize = parseInt(pageSizeSelect.value);
        supplierPerformanceState.currentPage = 1;
        renderSupplierPerformancePage();
    }
}

// ========== ANALYTICS PAGE FILTERING ==========

function showAnalyticsPage(category) {
    // Update active button
    document.querySelectorAll('.analytics-subtab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // Define widget categories
    const widgetCategories = {
        'spending': ['vendor_spend', 'category_spending', 'invoice_activity'],
        'pricing': ['price_trends', 'price_volatility', 'cost_variance'],
        'performance': ['supplier_performance', 'inventory_value', 'usage_forecast'],
        'all': [] // Empty means show all
    };

    const widgetsToShow = widgetCategories[category] || [];

    // Show/hide widgets based on category
    document.querySelectorAll('.analytics-widget').forEach(widget => {
        if (category === 'all') {
            widget.style.display = 'block';
        } else {
            const widgetKey = widget.id.replace('widget-', '');
            widget.style.display = widgetsToShow.includes(widgetKey) ? 'block' : 'none';
        }
    });
}

// Analytics is loaded via showTab('analytics') switch case

// ========== GENERIC MODAL SYSTEM (Layer 1.3) ==========

// Modal state
let modalState = {
    isOpen: false,
    currentModal: null
};

/**
 * Open a modal with custom content
 * @param {string} title - Modal title
 * @param {string} bodyHTML - HTML content for modal body
 * @param {Array} buttons - Array of button objects [{text, className, onclick}]
 * @param {boolean} wide - Use wide modal (900px instead of 600px)
 */
function openModal(title, bodyHTML, buttons = [], wide = false) {
    const modal = document.getElementById('genericModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    const modalFooter = document.getElementById('modalFooter');
    const modalContainer = modal.querySelector('.modal-container');

    if (!modal || !modalTitle || !modalBody || !modalFooter) {
        console.error('Modal elements not found');
        return;
    }

    // Set title and detect modal type for icon
    modalTitle.textContent = title;

    // Add data-modal attribute for icon styling
    const titleLower = title.toLowerCase();
    if (titleLower.includes('ingredient')) {
        modalTitle.setAttribute('data-modal', 'ingredient');
    } else if (titleLower.includes('supplier')) {
        modalTitle.setAttribute('data-modal', 'supplier');
    } else if (titleLower.includes('brand')) {
        modalTitle.setAttribute('data-modal', 'brand');
    } else if (titleLower.includes('product')) {
        modalTitle.setAttribute('data-modal', 'product');
    } else if (titleLower.includes('recipe')) {
        modalTitle.setAttribute('data-modal', 'recipe');
    } else if (titleLower.includes('category')) {
        modalTitle.setAttribute('data-modal', 'category');
    } else {
        modalTitle.removeAttribute('data-modal');
    }

    // Set body content
    modalBody.innerHTML = bodyHTML;

    // Clear and set footer buttons
    modalFooter.innerHTML = '';

    if (buttons.length === 0) {
        // Default close button
        buttons = [{
            text: 'Close',
            className: 'modal-btn-secondary',
            onclick: closeModal
        }];
    }

    buttons.forEach(btn => {
        const button = document.createElement('button');
        button.className = `modal-btn ${btn.className || 'modal-btn-secondary'}`;
        button.textContent = btn.text;
        button.onclick = btn.onclick;
        modalFooter.appendChild(button);
    });

    // Set width
    if (wide) {
        modalContainer.classList.add('modal-wide');
    } else {
        modalContainer.classList.remove('modal-wide');
    }

    // Show modal
    modal.style.display = 'flex';
    modal.classList.remove('closing');

    // Update state
    modalState.isOpen = true;
    modalState.currentModal = modal;

    // Prevent body scroll
    document.body.style.overflow = 'hidden';

    // Close on backdrop click (only if clicking directly on backdrop)
    modal.onclick = function(e) {
        if (e.target === modal) {
            closeModal();
        }
    };

    // Prevent clicks inside modal content from bubbling to backdrop
    if (modalContainer) {
        modalContainer.onclick = function(e) {
            e.stopPropagation();
        };
    }

    // Close on ESC key
    document.addEventListener('keydown', handleModalEscape);
}

/**
 * Close the currently open modal
 */
function closeModal() {
    const modal = document.getElementById('genericModal');

    if (!modal || !modalState.isOpen) {
        return;
    }

    // Add closing animation
    modal.classList.add('closing');

    // Wait for animation to finish
    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('closing');

        // Clear content
        document.getElementById('modalBody').innerHTML = '';
        document.getElementById('modalFooter').innerHTML = '';

        // Update state
        modalState.isOpen = false;
        modalState.currentModal = null;

        // Re-enable body scroll
        document.body.style.overflow = '';

        // Remove ESC key listener
        document.removeEventListener('keydown', handleModalEscape);
    }, 200); // Match animation duration
}

/**
 * Handle ESC key to close modal
 */
function handleModalEscape(e) {
    if (e.key === 'Escape' && modalState.isOpen) {
        closeModal();
    }
}

/**
 * Check if modal is currently open
 */
function isModalOpen() {
    return modalState.isOpen;
}

// ========== FORM UTILITIES (Layer 1.4) ==========

/**
 * Create a form field HTML
 * @param {string} type - Field type (text, number, email, select, textarea, checkbox)
 * @param {string} label - Field label
 * @param {string} id - Field ID
 * @param {object} options - Additional options {required, value, placeholder, min, max, step, options (for select)}
 */
function createFormField(type, label, id, options = {}) {
    const required = options.required ? ' *' : '';
    const value = options.value || '';
    const placeholder = options.placeholder || '';
    const requiredAttr = options.required ? 'required' : '';

    let fieldHTML = '';

    switch (type) {
        case 'text':
        case 'email':
        case 'number':
            fieldHTML = `
                <div class="form-group">
                    <label for="${id}">${label}${required}</label>
                    <input
                        type="${type}"
                        id="${id}"
                        name="${id}"
                        class="form-control"
                        value="${value}"
                        placeholder="${placeholder}"
                        ${requiredAttr}
                        ${type === 'number' && options.min !== undefined ? `min="${options.min}"` : ''}
                        ${type === 'number' && options.max !== undefined ? `max="${options.max}"` : ''}
                        ${type === 'number' && options.step ? `step="${options.step}"` : ''}
                    />
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        case 'select':
            const optionsHTML = (options.options || []).map(opt => {
                const selected = opt.value === value ? 'selected' : '';
                return `<option value="${opt.value}" ${selected}>${opt.label}</option>`;
            }).join('');

            fieldHTML = `
                <div class="form-group">
                    <label for="${id}">${label}${required}</label>
                    <select
                        id="${id}"
                        name="${id}"
                        class="form-control"
                        ${requiredAttr}
                    >
                        <option value="">-- Select ${label} --</option>
                        ${optionsHTML}
                    </select>
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        case 'textarea':
            fieldHTML = `
                <div class="form-group">
                    <label for="${id}">${label}${required}</label>
                    <textarea
                        id="${id}"
                        name="${id}"
                        class="form-control"
                        rows="${options.rows || 3}"
                        placeholder="${placeholder}"
                        ${requiredAttr}
                    >${value}</textarea>
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        case 'checkbox':
            const checked = options.checked || value ? 'checked' : '';
            fieldHTML = `
                <div class="form-group form-group-checkbox">
                    <label class="checkbox-label">
                        <input
                            type="checkbox"
                            id="${id}"
                            name="${id}"
                            ${checked}
                        />
                        <span>${label}</span>
                    </label>
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        default:
            console.error(`Unknown field type: ${type}`);
    }

    return fieldHTML;
}

/**
 * Create form field with optgroups for select dropdowns
 * @param {string} type - Field type (currently only 'select' supported)
 * @param {string} label - Field label
 * @param {string} id - Field ID
 * @param {object} options - Options including optgroups array
 * @returns {string} HTML string for the field
 */
function createFormFieldWithOptGroups(type, label, id, options = {}) {
    const required = options.required ? ' *' : '';
    const requiredAttr = options.required ? 'required' : '';

    if (type === 'select') {
        let optgroupsHTML = '';

        if (options.optgroups) {
            optgroupsHTML = options.optgroups.map(group => {
                const groupOptions = group.options.map(opt =>
                    `<option value="${opt.value}">${opt.label}</option>`
                ).join('');

                return `<optgroup label="${group.label}">${groupOptions}</optgroup>`;
            }).join('');
        }

        return `
            <div class="form-group">
                <label for="${id}">${label}${required}</label>
                <select id="${id}" name="${id}" class="form-control" ${requiredAttr}>
                    <option value="">-- ${label} --</option>
                    ${optgroupsHTML}
                </select>
                <div class="field-error" id="${id}-error"></div>
            </div>
        `;
    }

    // Fallback to regular createFormField for other types
    return createFormField(type, label, id, options);
}

/**
 * Get form data as an object
 * @param {string} formId - Form ID or container ID
 * @returns {object} Form data
 */
function getFormData(formId) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');
    const data = {};

    // Get all inputs, selects, textareas
    container.querySelectorAll('input, select, textarea').forEach(field => {
        if (field.type === 'checkbox') {
            data[field.id || field.name] = field.checked;
        } else if (field.type === 'number') {
            data[field.id || field.name] = field.value ? parseFloat(field.value) : null;
        } else {
            data[field.id || field.name] = field.value;
        }
    });

    return data;
}

/**
 * Set form data from an object
 * @param {string} formId - Form ID or container ID
 * @param {object} data - Data object
 */
function setFormData(formId, data) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');

    Object.keys(data).forEach(key => {
        const field = container.querySelector(`#${key}, [name="${key}"]`);
        if (!field) return;

        if (field.type === 'checkbox') {
            field.checked = data[key];
        } else {
            field.value = data[key] || '';
        }
    });
}

/**
 * Validate form fields
 * @param {string} formId - Form ID or container ID
 * @returns {object} {valid: boolean, errors: array}
 */
function validateForm(formId) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');
    const errors = [];

    // Clear previous errors
    container.querySelectorAll('.field-error').forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });

    container.querySelectorAll('.form-control').forEach(field => {
        field.classList.remove('error');
    });

    // Check required fields
    container.querySelectorAll('[required]').forEach(field => {
        if (!field.value || (field.type === 'checkbox' && !field.checked)) {
            const label = container.querySelector(`label[for="${field.id}"]`)?.textContent || field.id;
            errors.push({
                field: field.id,
                message: `${label} is required`
            });
            showFieldError(field.id, `This field is required`);
        }
    });

    // Validate email fields
    container.querySelectorAll('input[type="email"]').forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            errors.push({
                field: field.id,
                message: 'Invalid email format'
            });
            showFieldError(field.id, 'Invalid email format');
        }
    });

    // Validate number fields
    container.querySelectorAll('input[type="number"]').forEach(field => {
        if (field.value) {
            const value = parseFloat(field.value);
            if (isNaN(value)) {
                errors.push({
                    field: field.id,
                    message: 'Must be a number'
                });
                showFieldError(field.id, 'Must be a number');
            } else {
                if (field.min && value < parseFloat(field.min)) {
                    errors.push({
                        field: field.id,
                        message: `Must be at least ${field.min}`
                    });
                    showFieldError(field.id, `Must be at least ${field.min}`);
                }
                if (field.max && value > parseFloat(field.max)) {
                    errors.push({
                        field: field.id,
                        message: `Must be at most ${field.max}`
                    });
                    showFieldError(field.id, `Must be at most ${field.max}`);
                }
            }
        }
    });

    return {
        valid: errors.length === 0,
        errors: errors
    };
}

/**
 * Show error for a specific field
 * @param {string} fieldId - Field ID
 * @param {string} message - Error message
 */
function showFieldError(fieldId, message) {
    const errorEl = document.getElementById(`${fieldId}-error`);
    const field = document.getElementById(fieldId);

    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }

    if (field) {
        field.classList.add('error');
    }
}

/**
 * Clear all form errors
 * @param {string} formId - Form ID or container ID
 */
function clearFormErrors(formId) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');

    container.querySelectorAll('.field-error').forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });

    container.querySelectorAll('.form-control').forEach(field => {
        field.classList.remove('error');
    });
}

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean}
 */
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ========== DROPDOWN COMPONENTS (Layer 1.5) ==========

/**
 * Create an ingredient selector dropdown
 * @param {string} id - Field ID
 * @param {string} label - Field label
 * @param {number|null} selectedId - Selected ingredient ID
 * @param {object} options - Additional options {required, includeComposite}
 * @returns {Promise<string>} HTML for ingredient selector
 */
async function createIngredientSelector(id, label, selectedId = null, options = {}) {
    try {
        const response = await fetch('/api/ingredients/list');
        const ingredients = await response.json();

        // Filter out composites if requested
        let filteredIngredients = ingredients;
        if (options.includeComposite === false) {
            filteredIngredients = ingredients.filter(ing => !ing.is_composite);
        }

        const selectOptions = filteredIngredients.map(ing => ({
            value: ing.id,
            label: `${ing.ingredient_name} (${ing.unit_of_measure})`
        }));

        return createFormField('select', label, id, {
            ...options,
            value: selectedId,
            options: selectOptions
        });
    } catch (error) {
        console.error('Error loading ingredients:', error);
        return createFormField('select', label, id, {
            ...options,
            options: []
        });
    }
}

/**
 * Create a category selector dropdown
 * @param {string} id - Field ID
 * @param {string} label - Field label
 * @param {string|null} selectedCategory - Selected category
 * @param {object} options - Additional options
 * @returns {string} HTML for category selector
 */
function createCategorySelector(id, label, selectedCategory = null, options = {}) {
    const categories = [
        'Produce', 'Meat', 'Dairy', 'Dry Goods', 'Spices',
        'Oils', 'Prepared Foods', 'Packaging', 'Beverages',
        'Frozen', 'Bakery', 'Seafood', 'Uncategorized'
    ];

    const selectOptions = categories.map(cat => ({
        value: cat,
        label: cat
    }));

    return createFormField('select', label, id, {
        ...options,
        value: selectedCategory,
        options: selectOptions
    });
}

/**
 * Create a unit of measure selector
 * @param {string} id - Field ID
 * @param {string} label - Field label
 * @param {string|null} selectedUnit - Selected unit
 * @param {object} options - Additional options
 * @returns {string} HTML for unit selector
 */
function createUnitSelector(id, label, selectedUnit = null, options = {}) {
    const units = [
        'lb', 'oz', 'kg', 'g', 'gal', 'qt', 'pt', 'cup',
        'tbsp', 'tsp', 'each', 'case', 'box', 'bag', 'can', 'jar'
    ];

    const selectOptions = units.map(unit => ({
        value: unit,
        label: unit
    }));

    return createFormField('select', label, id, {
        ...options,
        value: selectedUnit,
        options: selectOptions
    });
}

/**
 * Create a supplier selector dropdown with "Create New" button
 * @param {string} id - Field ID
 * @param {string} label - Field label
 * @param {string|null} selectedSupplier - Selected supplier name
 * @param {object} options - Additional options
 * @returns {Promise<string>} HTML for supplier selector with create button
 */
async function createSupplierSelector(id, label, selectedSupplier = null, options = {}) {
    try {
        const response = await fetch('/api/suppliers/all');
        const suppliers = await response.json();

        const selectOptions = suppliers.map(supplier => ({
            value: supplier.supplier_name,
            label: supplier.supplier_name
        }));

        // Add empty option at the beginning
        selectOptions.unshift({ value: '', label: '-- Select Supplier --' });

        const selectHTML = createFormField('select', label, id, {
            ...options,
            value: selectedSupplier,
            options: selectOptions
        });

        // Wrap select with button
        return `
            <div class="form-group-with-action">
                ${selectHTML}
                <button type="button" class="btn-create-inline" onclick="openCreateSupplierModal('${id}')">
                    + New Supplier
                </button>
            </div>
        `;
    } catch (error) {
        console.error('Error loading suppliers:', error);
        return createFormField('select', label, id, {
            ...options,
            options: [{ value: '', label: '-- Select Supplier --' }]
        });
    }
}

/**
 * Create a brand selector dropdown with "Create New" button
 * @param {string} id - Field ID
 * @param {string} label - Field label
 * @param {string|null} selectedBrand - Selected brand name
 * @param {object} options - Additional options
 * @returns {Promise<string>} HTML for brand selector with create button
 */
async function createBrandSelector(id, label, selectedBrand = null, options = {}) {
    try {
        const response = await fetch('/api/brands/list');
        const brands = await response.json();

        const selectOptions = brands.map(brand => ({
            value: brand.brand_name,
            label: brand.brand_name
        }));

        // Add empty option at the beginning
        selectOptions.unshift({ value: '', label: '-- Select Brand --' });

        const selectHTML = createFormField('select', label, id, {
            ...options,
            value: selectedBrand,
            options: selectOptions
        });

        // Wrap select with button
        return `
            <div class="form-group-with-action">
                ${selectHTML}
                <button type="button" class="btn-create-inline" onclick="openCreateBrandModal('${id}')">
                    + New Brand
                </button>
            </div>
        `;
    } catch (error) {
        console.error('Error loading brands:', error);
        return createFormField('select', label, id, {
            ...options,
            options: [{ value: '', label: '-- Select Brand --' }]
        });
    }
}

/**
 * Open modal to create a new brand
 */
function openCreateBrandModal(brandSelectId) {
    console.log('openCreateBrandModal called');

    // Save the current ingredient form state before opening brand modal
    const ingredientForm = document.getElementById('ingredientForm');
    console.log('ingredientForm element:', ingredientForm);

    if (ingredientForm) {
        savedIngredientFormState = getFormData('ingredientForm');
        console.log('✓ Saved ingredient form state:', savedIngredientFormState);
    } else {
        console.error('✗ ERROR: Could not find ingredientForm element!');
    }

    const bodyHTML = `
        <div id="brandForm">
            <input type="hidden" id="brandSelectId" value="${brandSelectId}">

            ${createFormField('text', 'Brand Name', 'brandName', {
                required: true,
                placeholder: 'e.g., Heinz, Best Foods, Butterball'
            })}

            ${createFormField('textarea', 'Notes', 'brandNotes', {
                rows: 2,
                placeholder: 'Additional notes (optional)'
            })}
        </div>
    `;

    const buttons = [
        {
            text: 'Cancel',
            className: 'modal-btn-secondary',
            onclick: closeModal
        },
        {
            text: 'Create Brand',
            className: 'modal-btn-success',
            onclick: saveNewBrand
        }
    ];

    openModal('Create New Brand', bodyHTML, buttons);
}

/**
 * Save new brand to database
 */
async function saveNewBrand() {
    clearFormErrors('modalBody');

    const formData = getFormData('modalBody');
    const brandSelectId = formData.brandSelectId;

    console.log('saveNewBrand called with form data:', formData);

    // Validate brand name
    if (!formData.brandName || formData.brandName.trim() === '') {
        showFieldError('brandName', 'Brand name is required');
        showMessage('Please enter a brand name', 'error');
        return;
    }

    const brandData = {
        brand_name: formData.brandName.trim(),
        notes: formData.brandNotes || ''
    };

    console.log('Sending brand data to API:', brandData);

    try {
        const response = await fetch('/api/brands', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(brandData)
        });

        console.log('Brand API response status:', response.status);
        const result = await response.json();
        console.log('Brand API response data:', result);

        if (response.ok) {
            showMessage(`✓ Brand "${brandData.brand_name}" created successfully!`, 'success');

            console.log('Brand created successfully. Checking saved state:', savedIngredientFormState);

            // Restore the ingredient modal with the saved form data
            if (savedIngredientFormState) {
                // Update the saved state with the new brand
                savedIngredientFormState.ingredientBrand = brandData.brand_name;
                console.log('Restoring ingredient form with new brand:', brandData.brand_name);
                console.log('Full saved state:', savedIngredientFormState);

                closeModal();

                // Small delay to let modal close before reopening
                setTimeout(async () => {
                    await openCreateIngredientModal(savedIngredientFormState);
                    savedIngredientFormState = null; // Clear the saved state
                }, 200);
            } else {
                console.error('ERROR: savedIngredientFormState is null or undefined!');
                closeModal();
            }
        } else {
            console.error('Brand creation failed:', result.error);
            showMessage(`Failed to create brand: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error creating brand:', error);
        showMessage('Failed to create brand. Please try again.', 'error');
    }
}

// ========== NOTIFICATION SYSTEM (Layer 1.6) ==========

// Toast notification queue
let toastQueue = [];
let toastCounter = 0;

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: success, error, warning, info
 * @param {number} duration - Duration in ms (default 3000)
 */
function showMessage(message, type = 'info', duration = 3000) {
    const toast = {
        id: toastCounter++,
        message,
        type,
        duration
    };

    toastQueue.push(toast);
    displayToast(toast);
}

/**
 * Display a toast notification
 * @param {object} toast - Toast object
 */
function displayToast(toast) {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toastEl = document.createElement('div');
    toastEl.id = `toast-${toast.id}`;
    toastEl.className = `toast toast-${toast.type}`;

    // Icon based on type
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    toastEl.innerHTML = `
        <span class="toast-icon">${icons[toast.type] || icons.info}</span>
        <span class="toast-message">${toast.message}</span>
        <button class="toast-close" onclick="closeToast(${toast.id})">&times;</button>
    `;

    // Add to container
    container.appendChild(toastEl);

    // Animate in
    setTimeout(() => {
        toastEl.classList.add('show');
    }, 10);

    // Auto-remove
    setTimeout(() => {
        closeToast(toast.id);
    }, toast.duration);
}

/**
 * Close a toast notification
 * @param {number} toastId - Toast ID to close
 */
function closeToast(toastId) {
    const toastEl = document.getElementById(`toast-${toastId}`);
    if (!toastEl) return;

    toastEl.classList.remove('show');
    toastEl.classList.add('hide');

    setTimeout(() => {
        toastEl.remove();

        // Remove from queue
        toastQueue = toastQueue.filter(t => t.id !== toastId);

        // Remove container if empty
        const container = document.getElementById('toastContainer');
        if (container && container.children.length === 0) {
            container.remove();
        }
    }, 300);
}

// ========== INTEGRATION & TESTING (Layer 1.7) ==========

/**
 * Test the modal system with a sample form
 * Call this function from browser console to test: testModalSystem()
 */
function testModalSystem() {
    const bodyHTML = `
        <div style="margin-bottom: 20px;">
            <p style="color: #6c757d; margin-bottom: 20px;">
                This is a test modal to verify all Layer 1 components are working correctly.
            </p>
        </div>
        ${createFormField('text', 'Name', 'testName', { required: true, placeholder: 'Enter your name' })}
        ${createFormField('email', 'Email', 'testEmail', { required: true, placeholder: 'your@email.com' })}
        ${createFormField('number', 'Age', 'testAge', { min: 0, max: 120, placeholder: '25' })}
        ${createCategorySelector('testCategory', 'Category', null, { required: true })}
        ${createUnitSelector('testUnit', 'Unit', 'lb')}
        ${createFormField('textarea', 'Notes', 'testNotes', { rows: 3, placeholder: 'Optional notes...' })}
        ${createFormField('checkbox', 'I agree to the terms', 'testAgree', { required: true })}
    `;

    const buttons = [
        {
            text: 'Cancel',
            className: 'modal-btn-secondary',
            onclick: closeModal
        },
        {
            text: 'Test Validation',
            className: 'modal-btn-primary',
            onclick: () => {
                const validation = validateForm();
                if (validation.valid) {
                    const data = getFormData();
                    console.log('Form Data:', data);
                    showMessage('Form is valid! Check console for data.', 'success');
                } else {
                    console.log('Validation Errors:', validation.errors);
                    showMessage('Please fix the errors in the form', 'error');
                }
            }
        },
        {
            text: 'Test Success',
            className: 'modal-btn-success',
            onclick: () => {
                showMessage('This is a success message!', 'success');
            }
        }
    ];

    openModal('Test Modal System - Layer 1', bodyHTML, buttons, true);

    console.log('%c✓ Modal System Test Started', 'color: green; font-weight: bold; font-size: 16px');
    console.log('Components being tested:');
    console.log('  1. Modal open/close');
    console.log('  2. Form fields (text, email, number, select, textarea, checkbox)');
    console.log('  3. Form validation');
    console.log('  4. Form data extraction');
    console.log('  5. Toast notifications');
    console.log('\nTry:');
    console.log('  - Fill out the form and click "Test Validation"');
    console.log('  - Click "Test Success" to see a success toast');
    console.log('  - Press ESC to close modal');
    console.log('  - Click backdrop to close modal');
}

// Log Layer 1 completion
console.log('%c✓ Layer 1 Foundation Complete', 'color: green; font-weight: bold; font-size: 14px');
console.log('Available functions:');
console.log('  - openModal(title, bodyHTML, buttons, wide)');
console.log('  - closeModal()');
console.log('  - createFormField(type, label, id, options)');
console.log('  - validateForm(formId)');
console.log('  - getFormData(formId)');
console.log('  - setFormData(formId, data)');
console.log('  - showMessage(message, type, duration)');
console.log('  - createIngredientSelector(id, label, selectedId, options)');
console.log('  - createCategorySelector(id, label, selectedCategory, options)');
console.log('  - createUnitSelector(id, label, selectedUnit, options)');

// ============================================================================
// LAYER 2: INGREDIENT MANAGEMENT
// ============================================================================

// Global variable to preserve ingredient form state when opening supplier/brand modals
let savedIngredientFormState = null;

/**
 * Open modal to create a new ingredient
 */
async function openCreateIngredientModal(restoreData = null) {
    // If restoring, use the saved supplier/brand values
    const supplierValue = restoreData?.ingredientSupplier || null;
    const brandValue = restoreData?.ingredientBrand || null;

    const supplierHTML = await createSupplierSelector('ingredientSupplier', 'Supplier', supplierValue);
    const brandHTML = await createBrandSelector('ingredientBrand', 'Brand', brandValue);

    const bodyHTML = `
        <div id="ingredientForm">
            ${createFormField('text', 'Ingredient Code', 'ingredientCode', {
                required: true,
                placeholder: 'e.g., CHX, TMT, FLR'
            })}

            ${createFormField('text', 'Ingredient Name', 'ingredientName', {
                required: true,
                placeholder: 'e.g., Chicken Breast, Tomatoes'
            })}

            ${createCategorySelector('ingredientCategory', 'Category', null, {
                required: true
            })}

            ${createUnitSelector('ingredientUnit', 'Unit of Measure', 'lb', {
                required: true
            })}

            ${createFormField('number', 'Unit Cost ($)', 'ingredientCost', {
                placeholder: '0.00',
                min: 0,
                step: 0.01
            })}

            ${createFormField('number', 'Current Quantity', 'ingredientQuantity', {
                placeholder: '0',
                min: 0,
                step: 0.01
            })}

            ${createFormField('number', 'Reorder Point', 'ingredientReorderPoint', {
                placeholder: '0',
                min: 0,
                step: 0.01
            })}

            ${supplierHTML}

            ${brandHTML}

            ${createFormField('text', 'Storage Location', 'ingredientLocation', {
                placeholder: 'e.g., Walk-in Cooler, Dry Storage'
            })}

            ${createFormField('checkbox', 'Active', 'ingredientActive', {
                checked: true
            })}

            <div class="form-divider"></div>

            <div style="margin: 20px 0; padding: 15px; background: linear-gradient(135deg, #e3f2fd 0%, #f5f5f5 100%); border-radius: 8px; border: 2px solid var(--theme-color-1);">
                <p style="margin: 0 0 10px 0; font-weight: 600; color: var(--theme-color-1);">📱 Scan Product Barcode</p>
                <p style="margin: 0 0 10px 0; font-size: 0.9em; color: #666;">Have a product with a barcode? Scan it to auto-fill details from product databases!</p>
                <button type="button" class="btn btn-primary" onclick="openBarcodeScannerForIngredient()" style="width: 100%;">
                    📱 Scan Barcode
                </button>
            </div>

            <div class="form-divider"></div>

            ${createFormField('checkbox', 'Composite Ingredient', 'ingredientIsComposite', {
                checked: false,
                helpText: 'Check if this ingredient is made from other base ingredients (e.g., Pizza Sauce, House-Made Meatballs)'
            })}

            <div id="compositeIngredientSection" style="display: none;">
                <div class="form-section-highlight">
                    ${createFormField('number', 'Batch Size', 'ingredientBatchSize', {
                        placeholder: 'Total units produced per batch',
                        helpText: 'How many units (in the unit of measure) does one batch make?',
                        min: 0.01,
                        step: 0.01
                    })}

                    <h3 class="section-title">Recipe Builder</h3>
                    <p class="form-help-text">Add base ingredients that make up this composite ingredient</p>

                    <div class="recipe-builder">
                        <div class="recipe-add-section">
                            <div id="compositeIngredientSelectorContainer"></div>
                            ${createFormField('number', 'Quantity', 'compositeRecipeQuantity', {
                                placeholder: 'Amount needed',
                                step: '0.01',
                                min: '0'
                            })}
                            <button type="button" class="btn-create-inline" onclick="addBaseIngredientToComposite()">
                                + Add to Recipe
                            </button>
                        </div>

                        <div id="compositeRecipeList" class="recipe-ingredients-list">
                            <p class="text-muted">No ingredients added yet</p>
                        </div>

                        <div class="recipe-cost-summary">
                            <div class="cost-row">
                                <span>💰 Total Batch Cost:</span>
                                <strong id="compositeTotalCost">$0.00</strong>
                            </div>
                            <div class="cost-row">
                                <span>📊 Cost Per Unit:</span>
                                <strong id="compositeUnitCost">$0.00</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    const buttons = [
        {
            text: 'Cancel',
            className: 'modal-btn-secondary',
            onclick: closeModal
        },
        {
            text: 'Create Ingredient',
            className: 'modal-btn-success',
            onclick: saveNewIngredient
        }
    ];

    openModal('Create New Ingredient', bodyHTML, buttons, true);

    // Initialize composite ingredient functionality
    setTimeout(async () => {
        // Add event listener for composite checkbox
        const compositeCheckbox = document.getElementById('ingredientIsComposite');
        const compositeSection = document.getElementById('compositeIngredientSection');

        if (compositeCheckbox && compositeSection) {
            compositeCheckbox.addEventListener('change', () => {
                compositeSection.style.display = compositeCheckbox.checked ? 'block' : 'none';
            });
        }

        // Add event listener for batch size to recalculate costs
        const batchSizeInput = document.getElementById('ingredientBatchSize');
        if (batchSizeInput) {
            batchSizeInput.addEventListener('input', () => {
                updateCompositeCostSummary();
            });
        }

        // Fetch and populate base ingredients for composite recipe
        try {
            const response = await fetch('/api/ingredients-and-products/list');
            const data = await response.json();

            // Filter to only show non-composite ingredients
            const baseIngredients = data.ingredients.filter(ing => !ing.is_composite);

            // Create ingredient selector
            const selectorHTML = createFormField('select', 'Select Base Ingredient', 'compositeBaseIngredient', {
                required: false,
                options: baseIngredients.map(ing => ({
                    value: ing.id,
                    label: `${ing.name} (${ing.unit_of_measure}) - $${ing.unit_cost?.toFixed(4) || '0.00'}/unit`
                }))
            });

            const container = document.getElementById('compositeIngredientSelectorContainer');
            if (container) {
                container.innerHTML = selectorHTML;
            }
        } catch (error) {
            console.error('Error loading base ingredients:', error);
        }

        // Restore form data if provided
        if (restoreData) {
            setFormData('ingredientForm', restoreData);
        }
    }, 100);
}

// ========== COMPOSITE INGREDIENT RECIPE MANAGEMENT ==========

// Store composite recipe items globally
let compositeRecipeItems = [];

/**
 * Add base ingredient to composite recipe
 */
async function addBaseIngredientToComposite() {
    const ingredientSelect = document.getElementById('compositeBaseIngredient');
    const quantityInput = document.getElementById('compositeRecipeQuantity');

    if (!ingredientSelect || !quantityInput) {
        showMessage('Recipe fields not found', 'error');
        return;
    }

    const ingredientId = parseInt(ingredientSelect.value);
    const quantity = parseFloat(quantityInput.value);

    if (!ingredientId || isNaN(ingredientId)) {
        showMessage('Please select a base ingredient', 'error');
        return;
    }

    if (!quantity || quantity <= 0) {
        showMessage('Please enter a valid quantity', 'error');
        return;
    }

    // Get selected ingredient details
    const selectedOption = ingredientSelect.options[ingredientSelect.selectedIndex];
    const ingredientText = selectedOption.text;
    const ingredientName = ingredientText.split(' (')[0];
    const unitMatch = ingredientText.match(/\(([^)]+)\)/);
    const unitOfMeasure = unitMatch ? unitMatch[1].split(' - ')[0] : 'units';
    const costMatch = ingredientText.match(/\$([0-9.]+)\/unit/);
    const unitCost = costMatch ? parseFloat(costMatch[1]) : 0;

    // Check if ingredient already in recipe
    const existingIndex = compositeRecipeItems.findIndex(item => item.ingredient_id === ingredientId);

    if (existingIndex >= 0) {
        // Update existing quantity
        compositeRecipeItems[existingIndex].quantity_needed = quantity;
        showMessage(`Updated ${ingredientName} quantity to ${quantity} ${unitOfMeasure}`, 'success');
    } else {
        // Add new ingredient
        compositeRecipeItems.push({
            ingredient_id: ingredientId,
            ingredient_name: ingredientName,
            quantity_needed: quantity,
            unit_of_measure: unitOfMeasure,
            unit_cost: unitCost
        });
        showMessage(`Added ${ingredientName} to recipe`, 'success');
    }

    // Clear inputs
    quantityInput.value = '';

    // Update display
    renderCompositeRecipeList();
    updateCompositeCostSummary();
}

/**
 * Remove ingredient from composite recipe
 */
function removeFromCompositeRecipe(index) {
    if (index >= 0 && index < compositeRecipeItems.length) {
        const removed = compositeRecipeItems.splice(index, 1)[0];
        showMessage(`Removed ${removed.ingredient_name} from recipe`, 'success');
        renderCompositeRecipeList();
        updateCompositeCostSummary();
    }
}

/**
 * Render composite recipe ingredients list
 */
function renderCompositeRecipeList() {
    const listContainer = document.getElementById('compositeRecipeList');
    if (!listContainer) return;

    if (compositeRecipeItems.length === 0) {
        listContainer.innerHTML = '<p class="text-muted">No ingredients added yet</p>';
        return;
    }

    const itemsHTML = compositeRecipeItems.map((item, index) => `
        <div class="recipe-item">
            <div class="recipe-item-details">
                <span class="recipe-item-name">${item.ingredient_name}</span>
                <span class="recipe-item-qty">${item.quantity_needed} ${item.unit_of_measure}</span>
                <span class="recipe-item-cost">$${(item.quantity_needed * item.unit_cost).toFixed(2)}</span>
            </div>
            <button class="btn-remove-small" onclick="removeFromCompositeRecipe(${index})" title="Remove">×</button>
        </div>
    `).join('');

    listContainer.innerHTML = itemsHTML;
}

/**
 * Update composite cost summary
 */
function updateCompositeCostSummary() {
    const totalCost = compositeRecipeItems.reduce((sum, item) => {
        return sum + (item.quantity_needed * item.unit_cost);
    }, 0);

    const batchSizeInput = document.getElementById('ingredientBatchSize');
    const batchSize = batchSizeInput ? parseFloat(batchSizeInput.value) || 1 : 1;

    const unitCost = batchSize > 0 ? totalCost / batchSize : 0;

    // Update display
    const totalCostEl = document.getElementById('compositeTotalCost');
    const unitCostEl = document.getElementById('compositeUnitCost');

    if (totalCostEl) totalCostEl.textContent = `$${totalCost.toFixed(2)}`;
    if (unitCostEl) unitCostEl.textContent = `$${unitCost.toFixed(4)}`;

    // Also update the main unit cost field
    const unitCostInput = document.getElementById('ingredientCost');
    if (unitCostInput) {
        unitCostInput.value = unitCost.toFixed(4);
    }
}

/**
 * Validate ingredient form data
 */
function validateIngredientForm(data) {
    const errors = [];

    // Ingredient Code validation
    if (!data.ingredientCode || data.ingredientCode.trim() === '') {
        errors.push({ field: 'ingredientCode', message: 'Ingredient code is required' });
        showFieldError('ingredientCode', 'Ingredient code is required');
    } else if (!/^[A-Z0-9_-]+$/i.test(data.ingredientCode)) {
        errors.push({ field: 'ingredientCode', message: 'Code must contain only letters, numbers, hyphens, and underscores' });
        showFieldError('ingredientCode', 'Code must contain only letters, numbers, hyphens, and underscores');
    }

    // Ingredient Name validation
    if (!data.ingredientName || data.ingredientName.trim() === '') {
        errors.push({ field: 'ingredientName', message: 'Ingredient name is required' });
        showFieldError('ingredientName', 'Ingredient name is required');
    } else if (data.ingredientName.trim().length < 2) {
        errors.push({ field: 'ingredientName', message: 'Name must be at least 2 characters' });
        showFieldError('ingredientName', 'Name must be at least 2 characters');
    }

    // Category validation
    if (!data.ingredientCategory || data.ingredientCategory === '') {
        errors.push({ field: 'ingredientCategory', message: 'Category is required' });
        showFieldError('ingredientCategory', 'Category is required');
    }

    // Unit of Measure validation
    if (!data.ingredientUnit || data.ingredientUnit === '') {
        errors.push({ field: 'ingredientUnit', message: 'Unit of measure is required' });
        showFieldError('ingredientUnit', 'Unit of measure is required');
    }

    // Unit Cost validation
    if (data.ingredientCost && parseFloat(data.ingredientCost) < 0) {
        errors.push({ field: 'ingredientCost', message: 'Cost must be a positive number' });
        showFieldError('ingredientCost', 'Cost must be a positive number');
    }

    // Quantity validation
    if (data.ingredientQuantity && parseFloat(data.ingredientQuantity) < 0) {
        errors.push({ field: 'ingredientQuantity', message: 'Quantity must be a positive number' });
        showFieldError('ingredientQuantity', 'Quantity must be a positive number');
    }

    return {
        valid: errors.length === 0,
        errors: errors
    };
}

/**
 * Save new ingredient to database
 */
async function saveNewIngredient() {
    // Clear previous errors
    clearFormErrors('ingredientForm');

    // Get form data
    const formData = getFormData('ingredientForm');

    // Validate
    const validation = validateIngredientForm(formData);
    if (!validation.valid) {
        showMessage('Please fix the errors in the form', 'error');
        return;
    }

    // Check if composite ingredient
    const isComposite = formData.ingredientIsComposite ? 1 : 0;

    // Validate composite ingredients
    if (isComposite) {
        if (!formData.ingredientBatchSize || parseFloat(formData.ingredientBatchSize) <= 0) {
            showMessage('Batch size is required for composite ingredients', 'error');
            showFieldError('ingredientBatchSize', 'Batch size is required');
            return;
        }

        if (compositeRecipeItems.length === 0) {
            showMessage('Please add at least one base ingredient to the recipe', 'error');
            return;
        }
    }

    // Prepare ingredient data for API
    const ingredientData = {
        ingredient_code: formData.ingredientCode.trim(),
        ingredient_name: formData.ingredientName.trim(),
        category: formData.ingredientCategory,
        unit_of_measure: formData.ingredientUnit,
        unit_cost: formData.ingredientCost ? parseFloat(formData.ingredientCost) : 0,
        quantity_on_hand: formData.ingredientQuantity ? parseFloat(formData.ingredientQuantity) : 0,
        reorder_level: formData.ingredientReorderPoint ? parseFloat(formData.ingredientReorderPoint) : 0,
        supplier_name: formData.ingredientSupplier || '',
        brand: formData.ingredientBrand || '',
        storage_location: formData.ingredientLocation || '',
        active: formData.ingredientActive ? 1 : 0,
        is_composite: isComposite,
        batch_size: isComposite ? parseFloat(formData.ingredientBatchSize) : null
    };

    try {
        // Create ingredient
        const response = await fetch('/api/ingredients', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ingredientData)
        });

        const result = await response.json();

        if (!response.ok) {
            showMessage(`Failed to create ingredient: ${result.error || 'Unknown error'}`, 'error');
            return;
        }

        const ingredientId = result.ingredient_id;

        // If composite, save the recipe
        if (isComposite && compositeRecipeItems.length > 0) {
            const recipeResponse = await fetch(`/api/ingredients/${ingredientId}/recipe`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    base_ingredients: compositeRecipeItems.map(item => ({
                        ingredient_id: item.ingredient_id,
                        quantity_needed: item.quantity_needed,
                        unit_of_measure: item.unit_of_measure,
                        notes: ''
                    }))
                })
            });

            const recipeResult = await recipeResponse.json();

            if (!recipeResponse.ok) {
                showMessage(`Ingredient created but recipe failed: ${recipeResult.error}`, 'warning');
                closeModal();
                loadInventory();
                return;
            }

            showMessage('✓ Composite ingredient created with recipe!', 'success');
        } else {
            showMessage('✓ Ingredient created successfully!', 'success');
        }

        // Clear composite recipe items
        compositeRecipeItems = [];

        closeModal();
        loadInventory(); // Refresh the inventory table

    } catch (error) {
        console.error('Error creating ingredient:', error);
        showMessage('Failed to create ingredient. Please try again.', 'error');
    }
}

/**
 * Open modal to edit an existing ingredient
 */
async function openEditIngredientModal(ingredientId) {
    try {
        // Fetch ingredient data
        const response = await fetch(`/api/ingredients/${ingredientId}`);

        if (!response.ok) {
            showMessage('Failed to load ingredient data', 'error');
            return;
        }

        const ingredient = await response.json();

        // Load supplier and brand selectors with current values
        const supplierHTML = await createSupplierSelector('ingredientSupplier', 'Supplier', ingredient.supplier_name || null);
        const brandHTML = await createBrandSelector('ingredientBrand', 'Brand', ingredient.brand || null);

        // Create form HTML
        const bodyHTML = `
            <div id="ingredientForm">
                <input type="hidden" id="ingredientId" value="${ingredientId}">

                ${createFormField('text', 'Ingredient Code', 'ingredientCode', {
                    required: true,
                    value: ingredient.ingredient_code || ''
                })}

                ${createFormField('text', 'Ingredient Name', 'ingredientName', {
                    required: true,
                    value: ingredient.ingredient_name || ''
                })}

                ${createCategorySelector('ingredientCategory', 'Category', ingredient.category, {
                    required: true
                })}

                ${createUnitSelector('ingredientUnit', 'Unit of Measure', ingredient.unit_of_measure, {
                    required: true
                })}

                ${createFormField('number', 'Unit Cost ($)', 'ingredientCost', {
                    value: ingredient.unit_cost || 0,
                    min: 0,
                    step: 0.01
                })}

                ${createFormField('number', 'Current Quantity', 'ingredientQuantity', {
                    value: ingredient.quantity_on_hand || 0,
                    min: 0,
                    step: 0.01
                })}

                ${createFormField('number', 'Reorder Point', 'ingredientReorderPoint', {
                    value: ingredient.reorder_level || 0,
                    min: 0,
                    step: 0.01
                })}

                ${supplierHTML}

                ${brandHTML}

                ${createFormField('text', 'Storage Location', 'ingredientLocation', {
                    value: ingredient.storage_location || ''
                })}

                ${createFormField('checkbox', 'Active', 'ingredientActive', {
                    checked: ingredient.active === 1
                })}

                <div class="form-divider"></div>

                ${createFormField('checkbox', 'Composite Ingredient', 'ingredientIsComposite', {
                    checked: ingredient.is_composite === 1,
                    helpText: 'Check if this ingredient is made from other base ingredients (e.g., Pizza Sauce, House-Made Meatballs)'
                })}

                <div id="compositeIngredientSection" style="display: ${ingredient.is_composite === 1 ? 'block' : 'none'};">
                    <div class="form-section-highlight">
                        ${createFormField('number', 'Batch Size', 'ingredientBatchSize', {
                            placeholder: 'Total units produced per batch',
                            helpText: 'How many units (in the unit of measure) does one batch make?',
                            min: 0.01,
                            step: 0.01,
                            value: ingredient.batch_size || ''
                        })}

                        <h3 class="section-title">Recipe Builder</h3>
                        <p class="form-help-text">Add base ingredients that make up this composite ingredient</p>

                        <div class="recipe-builder">
                            <div class="recipe-add-section">
                                <div id="compositeIngredientSelectorContainer"></div>
                                ${createFormField('number', 'Quantity', 'compositeRecipeQuantity', {
                                    placeholder: 'Amount needed',
                                    step: '0.01',
                                    min: '0'
                                })}
                                <button type="button" class="btn-create-inline" onclick="addBaseIngredientToComposite()">
                                    + Add to Recipe
                                </button>
                            </div>

                            <div id="compositeRecipeList" class="recipe-ingredients-list">
                                <p class="text-muted">Loading recipe...</p>
                            </div>

                            <div class="recipe-cost-summary">
                                <div class="cost-row">
                                    <span>💰 Total Batch Cost:</span>
                                    <strong id="compositeTotalCost">$0.00</strong>
                                </div>
                                <div class="cost-row">
                                    <span>📊 Cost Per Unit:</span>
                                    <strong id="compositeUnitCost">$0.00</strong>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const buttons = [
            {
                text: 'Cancel',
                className: 'modal-btn-secondary',
                onclick: closeModal
            },
            {
                text: 'Save Changes',
                className: 'modal-btn-primary',
                onclick: updateIngredient
            }
        ];

        openModal(`Edit Ingredient: ${ingredient.ingredient_name}`, bodyHTML, buttons, true);

        // Initialize composite ingredient functionality for edit modal
        setTimeout(async () => {
            // Clear previous recipe items
            compositeRecipeItems = [];

            // Add event listener for composite checkbox
            const compositeCheckbox = document.getElementById('ingredientIsComposite');
            const compositeSection = document.getElementById('compositeIngredientSection');

            if (compositeCheckbox && compositeSection) {
                compositeCheckbox.addEventListener('change', () => {
                    compositeSection.style.display = compositeCheckbox.checked ? 'block' : 'none';
                });
            }

            // Add event listener for batch size
            const batchSizeInput = document.getElementById('ingredientBatchSize');
            if (batchSizeInput) {
                batchSizeInput.addEventListener('input', () => {
                    updateCompositeCostSummary();
                });
            }

            // Fetch and populate base ingredients for composite recipe
            try {
                const response = await fetch('/api/ingredients-and-products/list');
                const data = await response.json();

                // Filter to only show non-composite ingredients
                const baseIngredients = data.ingredients.filter(ing => !ing.is_composite);

                // Create ingredient selector
                const selectorHTML = createFormField('select', 'Select Base Ingredient', 'compositeBaseIngredient', {
                    required: false,
                    options: baseIngredients.map(ing => ({
                        value: ing.id,
                        label: `${ing.name} (${ing.unit_of_measure}) - $${ing.unit_cost?.toFixed(4) || '0.00'}/unit`
                    }))
                });

                const container = document.getElementById('compositeIngredientSelectorContainer');
                if (container) {
                    container.innerHTML = selectorHTML;
                }
            } catch (error) {
                console.error('Error loading base ingredients:', error);
            }

            // If this is a composite ingredient, load existing recipe
            if (ingredient.is_composite === 1) {
                try {
                    const recipeResponse = await fetch(`/api/ingredients/${ingredientId}/recipe`);
                    const recipeData = await recipeResponse.json();

                    if (recipeResponse.ok && recipeData.recipe_items) {
                        compositeRecipeItems = recipeData.recipe_items.map(item => ({
                            ingredient_id: item.base_ingredient_id,
                            ingredient_name: item.ingredient_name,
                            quantity_needed: item.quantity_needed,
                            unit_of_measure: item.unit_of_measure,
                            unit_cost: item.unit_cost || 0
                        }));

                        renderCompositeRecipeList();
                        updateCompositeCostSummary();
                    }
                } catch (error) {
                    console.error('Error loading recipe:', error);
                }
            }
        }, 100);
    } catch (error) {
        console.error('Error loading ingredient:', error);
        showMessage('Failed to load ingredient data', 'error');
    }
}

/**
 * Update existing ingredient in database
 */
async function updateIngredient() {
    // Clear previous errors
    clearFormErrors('ingredientForm');

    // Get form data
    const formData = getFormData('ingredientForm');
    const ingredientId = formData.ingredientId;

    // Validate
    const validation = validateIngredientForm(formData);
    if (!validation.valid) {
        showMessage('Please fix the errors in the form', 'error');
        return;
    }

    // Check if composite ingredient
    const isComposite = formData.ingredientIsComposite ? 1 : 0;

    // Validate composite ingredients
    if (isComposite) {
        if (!formData.ingredientBatchSize || parseFloat(formData.ingredientBatchSize) <= 0) {
            showMessage('Batch size is required for composite ingredients', 'error');
            showFieldError('ingredientBatchSize', 'Batch size is required');
            return;
        }

        if (compositeRecipeItems.length === 0) {
            showMessage('Please add at least one base ingredient to the recipe', 'error');
            return;
        }
    }

    // Prepare ingredient data for API
    const ingredientData = {
        ingredient_code: formData.ingredientCode.trim(),
        ingredient_name: formData.ingredientName.trim(),
        category: formData.ingredientCategory,
        unit_of_measure: formData.ingredientUnit,
        unit_cost: formData.ingredientCost ? parseFloat(formData.ingredientCost) : 0,
        quantity_on_hand: formData.ingredientQuantity ? parseFloat(formData.ingredientQuantity) : 0,
        reorder_level: formData.ingredientReorderPoint ? parseFloat(formData.ingredientReorderPoint) : 0,
        supplier_name: formData.ingredientSupplier || '',
        brand: formData.ingredientBrand || '',
        storage_location: formData.ingredientLocation || '',
        active: formData.ingredientActive ? 1 : 0,
        is_composite: isComposite,
        batch_size: isComposite ? parseFloat(formData.ingredientBatchSize) : null
    };

    try {
        // Update ingredient
        const response = await fetch(`/api/ingredients/${ingredientId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ingredientData)
        });

        const result = await response.json();

        if (!response.ok) {
            showMessage(`Failed to update ingredient: ${result.error || 'Unknown error'}`, 'error');
            return;
        }

        // If composite, save the recipe
        if (isComposite && compositeRecipeItems.length > 0) {
            const recipeResponse = await fetch(`/api/ingredients/${ingredientId}/recipe`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    base_ingredients: compositeRecipeItems.map(item => ({
                        ingredient_id: item.ingredient_id,
                        quantity_needed: item.quantity_needed,
                        unit_of_measure: item.unit_of_measure,
                        notes: ''
                    }))
                })
            });

            const recipeResult = await recipeResponse.json();

            if (!recipeResponse.ok) {
                showMessage(`Ingredient updated but recipe failed: ${recipeResult.error}`, 'warning');
                closeModal();
                loadInventory();
                return;
            }

            showMessage('✓ Composite ingredient updated with recipe!', 'success');
        } else {
            showMessage('✓ Ingredient updated successfully!', 'success');
        }

        // Clear composite recipe items
        compositeRecipeItems = [];

        closeModal();
        loadInventory(); // Refresh the inventory table

    } catch (error) {
        console.error('Error updating ingredient:', error);
        showMessage('Failed to update ingredient. Please try again.', 'error');
    }
}

/**
 * Confirm and delete an ingredient
 */
async function confirmDeleteIngredient(ingredientId, ingredientName) {
    // Show confirmation dialog
    if (!confirm(`Are you sure you want to delete "${ingredientName}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/ingredients/${ingredientId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showMessage(`✅ ${result.message}`, 'success');
            closeModal(); // Close the variants modal
            loadInventory(); // Refresh inventory table
        } else {
            showMessage(`Failed to delete ingredient: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting ingredient:', error);
        showMessage('Failed to delete ingredient. Please try again.', 'error');
    }
}

/**
 * Open modal to create a new supplier
 */
function openCreateSupplierModal(supplierSelectId) {
    console.log('openCreateSupplierModal called');

    // Save the current ingredient form state before opening supplier modal
    const ingredientForm = document.getElementById('ingredientForm');
    console.log('ingredientForm element:', ingredientForm);

    if (ingredientForm) {
        savedIngredientFormState = getFormData('ingredientForm');
        console.log('✓ Saved ingredient form state:', savedIngredientFormState);
    } else {
        console.error('✗ ERROR: Could not find ingredientForm element!');
    }

    const bodyHTML = `
        <div id="supplierForm">
            <input type="hidden" id="supplierSelectId" value="${supplierSelectId}">

            ${createFormField('text', 'Supplier Name', 'supplierName', {
                required: true,
                placeholder: 'e.g., Sysco, US Foods, Restaurant Depot'
            })}

            ${createFormField('text', 'Contact Person', 'supplierContact', {
                placeholder: 'Contact name (optional)'
            })}

            ${createFormField('text', 'Phone', 'supplierPhone', {
                placeholder: '(555) 123-4567'
            })}

            ${createFormField('email', 'Email', 'supplierEmail', {
                placeholder: 'supplier@email.com'
            })}

            ${createFormField('textarea', 'Address', 'supplierAddress', {
                rows: 2,
                placeholder: 'Supplier address (optional)'
            })}

            ${createFormField('text', 'Payment Terms', 'supplierPaymentTerms', {
                placeholder: 'e.g., Net 30, Net 60'
            })}

            ${createFormField('textarea', 'Notes', 'supplierNotes', {
                rows: 2,
                placeholder: 'Additional notes (optional)'
            })}
        </div>
    `;

    const buttons = [
        {
            text: 'Cancel',
            className: 'modal-btn-secondary',
            onclick: closeModal
        },
        {
            text: 'Create Supplier',
            className: 'modal-btn-success',
            onclick: saveNewSupplier
        }
    ];

    openModal('Create New Supplier', bodyHTML, buttons, true);
}

/**
 * Save new supplier to database
 */
async function saveNewSupplier() {
    clearFormErrors('modalBody');

    const formData = getFormData('modalBody');
    const supplierSelectId = formData.supplierSelectId;

    // Validate supplier name
    if (!formData.supplierName || formData.supplierName.trim() === '') {
        showFieldError('supplierName', 'Supplier name is required');
        showMessage('Please enter a supplier name', 'error');
        return;
    }

    const supplierData = {
        supplier_name: formData.supplierName.trim(),
        contact_person: formData.supplierContact || '',
        phone: formData.supplierPhone || '',
        email: formData.supplierEmail || '',
        address: formData.supplierAddress || '',
        payment_terms: formData.supplierPaymentTerms || '',
        notes: formData.supplierNotes || ''
    };

    try {
        const response = await fetch('/api/suppliers/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(supplierData)
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Supplier "${supplierData.supplier_name}" created successfully!`, 'success');

            console.log('Supplier created successfully. Checking saved state:', savedIngredientFormState);

            // Restore the ingredient modal with the saved form data
            if (savedIngredientFormState) {
                // Update the saved state with the new supplier
                savedIngredientFormState.ingredientSupplier = supplierData.supplier_name;
                console.log('Restoring ingredient form with new supplier:', supplierData.supplier_name);
                console.log('Full saved state:', savedIngredientFormState);

                closeModal();

                // Small delay to let modal close before reopening
                setTimeout(async () => {
                    await openCreateIngredientModal(savedIngredientFormState);
                    savedIngredientFormState = null; // Clear the saved state
                }, 200);
            } else {
                console.error('ERROR: savedIngredientFormState is null or undefined!');
                closeModal();
            }
        } else {
            showMessage(`Failed to create supplier: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error creating supplier:', error);
        showMessage('Failed to create supplier. Please try again.', 'error');
    }
}

// Log Layer 2 functions available
console.log('%c✓ Layer 2: Ingredient Management Ready', 'color: blue; font-weight: bold; font-size: 14px');
console.log('New functions available:');
console.log('  - openCreateIngredientModal()');
console.log('  - openEditIngredientModal(ingredientId)');
console.log('  - saveNewIngredient()');
console.log('  - updateIngredient()');
console.log('  - validateIngredientForm(data)');
console.log('\nTest the system: testModalSystem()');

// ========================================
// LAYER 3: PRODUCT MANAGEMENT
// ========================================

// Global state for recipe builder
let currentRecipeIngredients = [];

/**
 * Open Create Product Modal
 */
async function openCreateProductModal() {
    console.log('Opening Create Product modal...');

    // Load available ingredients AND products for recipe builder
    let availableIngredients = [];
    let availableProducts = [];
    try {
        const response = await fetch('/api/ingredients-and-products/list');
        const data = await response.json();
        availableIngredients = data.ingredients;
        availableProducts = data.products;
    } catch (error) {
        console.error('Error loading ingredients and products:', error);
    }

    // Reset recipe state
    currentRecipeIngredients = [];

    const bodyHTML = `
        <div id="productForm">
            <div class="form-section">
                <h3 class="section-title">Product Details</h3>
                ${createFormField('text', 'Product Code', 'productCode', {
                    required: true,
                    placeholder: 'e.g., BURGER-001, TACO-MIX'
                })}
                ${createFormField('text', 'Product Name', 'productName', {
                    required: true,
                    placeholder: 'e.g., Classic Cheeseburger, Beef Tacos'
                })}
                ${createFormField('select', 'Category', 'productCategory', {
                    required: true,
                    options: [
                        { value: '', label: '-- Select Category --' },
                        { value: 'Entrees', label: 'Entrees' },
                        { value: 'Sides', label: 'Sides' },
                        { value: 'Sauces', label: 'Sauces' },
                        { value: 'Pizza', label: 'Pizza' },
                        { value: 'Prepared Foods', label: 'Prepared Foods' }
                    ]
                })}
                ${createFormField('select', 'Unit of Measure', 'productUnit', {
                    required: true,
                    options: [
                        { value: '', label: '-- Select Unit --' },
                        { value: 'each', label: 'Each' },
                        { value: 'dozen', label: 'Dozen' },
                        { value: 'lbs', label: 'Pounds (lbs)' },
                        { value: 'oz', label: 'Ounces (oz)' },
                        { value: 'serving', label: 'Serving' }
                    ]
                })}
                ${createFormField('number', 'Selling Price', 'productPrice', {
                    required: true,
                    placeholder: '9.99',
                    step: '0.01',
                    min: '0'
                })}
                ${createFormField('number', 'Quantity on Hand', 'productQuantity', {
                    required: true,
                    placeholder: '0',
                    value: '0',
                    step: '0.01',
                    min: '0'
                })}
                ${createFormField('number', 'Shelf Life (Days)', 'productShelfLife', {
                    placeholder: 'e.g., 3, 7, 30',
                    min: '0'
                })}
                ${createFormField('textarea', 'Storage Requirements', 'productStorage', {
                    rows: 2,
                    placeholder: 'e.g., Refrigerate at 38°F, Keep frozen'
                })}
            </div>

            <div class="form-section">
                <h3 class="section-title">Recipe Builder</h3>
                <p class="form-help-text">Add ingredients that make up this product</p>

                <div class="recipe-builder">
                    <div class="recipe-add-section">
                        ${createFormFieldWithOptGroups('select', 'Select Ingredient or Product', 'recipeIngredient', {
                            optgroups: [
                                {
                                    label: '📦 Ingredients',
                                    options: availableIngredients.map(ing => ({
                                        value: `ingredient:${ing.id}`,
                                        label: `${ing.name} (${ing.unit_of_measure})`
                                    }))
                                },
                                {
                                    label: '🍔 Products',
                                    options: availableProducts.map(prod => ({
                                        value: `product:${prod.id}`,
                                        label: `${prod.name} (${prod.unit_of_measure})`
                                    }))
                                }
                            ]
                        })}
                        ${createFormField('number', 'Quantity', 'recipeQuantity', {
                            placeholder: 'Amount needed',
                            step: '0.01',
                            min: '0'
                        })}
                        <button type="button" class="btn-create-inline" onclick="addIngredientToRecipe()">
                            + Add to Recipe
                        </button>
                    </div>

                    <div id="recipeIngredientsList" class="recipe-ingredients-list">
                        <p class="text-muted">No ingredients added yet</p>
                    </div>

                    <div class="recipe-cost-summary">
                        <div class="cost-row">
                            <span>💰 Total Ingredient Cost:</span>
                            <strong id="recipeTotalCost">$0.00</strong>
                        </div>
                        <div class="cost-row">
                            <span>📊 Gross Profit:</span>
                            <strong id="recipeGrossProfit">$0.00</strong>
                        </div>
                        <div class="cost-row">
                            <span>📈 Profit Margin:</span>
                            <strong id="recipeMargin">0%</strong>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    const buttons = [
        { text: 'Cancel', className: 'modal-btn-secondary', onclick: closeModal },
        { text: 'Create Product', className: 'modal-btn-success', onclick: saveNewProduct }
    ];

    openModal('Create New Product', bodyHTML, buttons, true);

    // Add event listener to price field for real-time margin calculation
    setTimeout(() => {
        const priceField = document.getElementById('productPrice');
        if (priceField) {
            priceField.addEventListener('input', updateRecipeCostSummary);
        }

        // Prevent Enter key from closing modal unexpectedly
        const modalBody = document.getElementById('modalBody');
        if (modalBody) {
            modalBody.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && e.target.tagName !== 'BUTTON' && e.target.tagName !== 'TEXTAREA') {
                    e.preventDefault();
                    return false;
                }
            });
        }
    }, 100);
}

/**
 * Add ingredient or product to recipe
 */
async function addIngredientToRecipe() {
    const ingredientSelect = document.getElementById('recipeIngredient');
    const quantityInput = document.getElementById('recipeQuantity');

    const selectedValue = ingredientSelect.value;
    const quantity = parseFloat(quantityInput.value);

    if (!selectedValue || !quantity || quantity <= 0) {
        showMessage('Please select an ingredient/product and enter a valid quantity', 'error');
        return;
    }

    // Parse value: "ingredient:5" or "product:3"
    const [sourceType, sourceId] = selectedValue.split(':');
    const sourceIdInt = parseInt(sourceId);

    // Get name from dropdown
    const selectedOption = ingredientSelect.options[ingredientSelect.selectedIndex];
    const sourceName = selectedOption.text;

    // Check if already added
    if (currentRecipeIngredients.some(item =>
        item.source_type === sourceType && item.source_id === sourceIdInt)) {
        showMessage('This item is already in the recipe', 'warning');
        return;
    }

    // Validate before adding (for products)
    if (sourceType === 'product') {
        await validateAndAddProductToRecipe(sourceIdInt, sourceName, quantity);
    } else {
        // Add ingredient directly
        currentRecipeIngredients.push({
            source_type: sourceType,
            source_id: sourceIdInt,
            source_name: sourceName,
            quantity: quantity
        });

        // Clear inputs
        ingredientSelect.value = '';
        quantityInput.value = '';

        renderRecipeIngredientsList();
        updateRecipeCostSummary();

        showMessage('Ingredient added to recipe', 'success');
    }
}

/**
 * Validate and add product to recipe (with circular dependency and depth checks)
 */
async function validateAndAddProductToRecipe(productId, productName, quantity) {
    const currentProductId = document.getElementById('productId')?.value; // For edit mode

    // Build current recipe items for validation
    const recipeItems = [
        ...currentRecipeIngredients.map(item => ({
            source_type: item.source_type,
            source_id: item.source_id
        })),
        {
            source_type: 'product',
            source_id: productId
        }
    ];

    try {
        const response = await fetch('/api/products/validate-recipe', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                product_id: currentProductId ? parseInt(currentProductId) : null,
                recipe_items: recipeItems
            })
        });

        const result = await response.json();

        if (result.valid) {
            // Add to recipe
            currentRecipeIngredients.push({
                source_type: 'product',
                source_id: productId,
                source_name: productName,
                quantity: quantity
            });

            // Clear inputs
            document.getElementById('recipeIngredient').value = '';
            document.getElementById('recipeQuantity').value = '';

            renderRecipeIngredientsList();
            updateRecipeCostSummary();

            showMessage('Product added to recipe', 'success');
        } else {
            showMessage('Validation failed: ' + result.errors.join('; '), 'error');
        }
    } catch (error) {
        console.error('Validation error:', error);
        showMessage('Failed to validate product', 'error');
    }
}

/**
 * Remove ingredient or product from recipe
 */
function removeIngredientFromRecipe(sourceType, sourceId) {
    currentRecipeIngredients = currentRecipeIngredients.filter(
        item => !(item.source_type === sourceType && item.source_id === sourceId)
    );
    renderRecipeIngredientsList();
    updateRecipeCostSummary();
}

/**
 * Render recipe ingredients list with badges
 */
function renderRecipeIngredientsList() {
    const listContainer = document.getElementById('recipeIngredientsList');

    if (currentRecipeIngredients.length === 0) {
        listContainer.innerHTML = '<p class="text-muted">No ingredients added yet</p>';
        return;
    }

    listContainer.innerHTML = currentRecipeIngredients.map(item => {
        // Badge for type
        const badge = item.source_type === 'product'
            ? '<span class="badge badge-product">Product</span>'
            : '<span class="badge badge-ingredient">Ingredient</span>';

        return `
            <div class="recipe-ingredient-item">
                <div class="ingredient-info">
                    ${badge}
                    <strong>${item.source_name}</strong>
                    <span class="ingredient-quantity">${item.quantity} ${item.unit || ''}</span>
                </div>
                <button type="button" class="btn-remove-ingredient"
                        onclick="removeIngredientFromRecipe('${item.source_type}', ${item.source_id})"
                        title="Remove">
                    ✕
                </button>
            </div>
        `;
    }).join('');
}

/**
 * Update recipe cost summary (handles both ingredients and products)
 */
async function updateRecipeCostSummary() {
    const priceField = document.getElementById('productPrice');
    const sellingPrice = priceField ? parseFloat(priceField.value) || 0 : 0;

    let totalCost = 0;

    // Calculate total cost (ingredients + products)
    for (const item of currentRecipeIngredients) {
        try {
            if (item.source_type === 'ingredient') {
                // Fetch ingredient cost
                const response = await fetch(`/api/ingredients/${item.source_id}`);
                const ingredient = await response.json();
                const cost = ingredient.unit_cost * item.quantity;
                totalCost += cost;
            } else if (item.source_type === 'product') {
                // Fetch product ingredient cost
                const response = await fetch(`/api/products/${item.source_id}/ingredient-cost`);
                const result = await response.json();
                const cost = result.total_ingredient_cost * item.quantity;
                totalCost += cost;
            }
        } catch (error) {
            console.error('Error fetching cost:', error);
        }
    }

    const grossProfit = sellingPrice - totalCost;
    const margin = sellingPrice > 0 ? ((grossProfit / sellingPrice) * 100).toFixed(1) : 0;

    // Update display
    document.getElementById('recipeTotalCost').textContent = formatCurrency(totalCost);
    document.getElementById('recipeGrossProfit').textContent = formatCurrency(grossProfit);
    document.getElementById('recipeMargin').textContent = `${margin}%`;

    // Color-code margin
    const marginElement = document.getElementById('recipeMargin');
    marginElement.style.color = grossProfit < 0 ? '#dc3545' : '#28a745';
}

/**
 * Save new product
 */
async function saveNewProduct() {
    clearFormErrors('modalBody');
    const formData = getFormData('modalBody');

    // Validation
    const errors = [];
    if (!formData.productCode?.trim()) errors.push('Product Code is required');
    if (!formData.productName?.trim()) errors.push('Product Name is required');
    if (!formData.productCategory) errors.push('Category is required');
    if (!formData.productUnit) errors.push('Unit of Measure is required');
    if (!formData.productPrice || parseFloat(formData.productPrice) <= 0) {
        errors.push('Selling Price is required and must be greater than 0');
    }

    if (errors.length > 0) {
        showMessage(errors.join('; '), 'error');
        return;
    }

    const productData = {
        product_code: formData.productCode.trim(),
        product_name: formData.productName.trim(),
        category: formData.productCategory,
        unit_of_measure: formData.productUnit,
        quantity_on_hand: parseFloat(formData.productQuantity) || 0,
        selling_price: parseFloat(formData.productPrice),
        shelf_life_days: formData.productShelfLife ? parseInt(formData.productShelfLife) : null,
        storage_requirements: formData.productStorage?.trim() || '',
        recipe: currentRecipeIngredients.map(item => ({
            source_type: item.source_type,
            source_id: item.source_id,
            quantity_needed: item.quantity,
            unit_of_measure: item.unit || 'unit'
        }))
    };

    try {
        const response = await fetch('/api/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Product "${productData.product_name}" created successfully!`, 'success');
            closeModal();
            loadProducts(); // Refresh products table
        } else {
            showMessage(`Failed to create product: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error creating product:', error);
        showMessage('Failed to create product. Please try again.', 'error');
    }
}

/**
 * Open Edit Product Modal
 */
async function openEditProductModal(productId) {
    console.log('Opening Edit Product modal for ID:', productId);

    try {
        // Load product details
        const productResponse = await fetch(`/api/products/${productId}`);
        const product = await productResponse.json();

        // Load recipe
        const recipeResponse = await fetch(`/api/products/${productId}/recipe`);
        const recipe = await recipeResponse.json();

        // Load available ingredients AND products for recipe builder
        const response = await fetch(`/api/ingredients-and-products/list?exclude_product_id=${productId}`);
        const data = await response.json();
        const availableIngredients = data.ingredients;
        const availableProducts = data.products;

        // Set current recipe
        currentRecipeIngredients = recipe.map(r => ({
            source_type: r.source_type,
            source_id: r.source_id,
            source_name: r.name,
            quantity: r.quantity_needed,
            unit: r.unit_of_measure
        }));

        const bodyHTML = `
            <div id="productForm">
                <input type="hidden" id="productId" value="${productId}">
                <div class="form-section">
                    <h3 class="section-title">Product Details</h3>
                    ${createFormField('text', 'Product Code', 'productCode', {
                        required: true,
                        value: product.product_code
                    })}
                    ${createFormField('text', 'Product Name', 'productName', {
                        required: true,
                        value: product.product_name
                    })}
                    ${createFormField('select', 'Category', 'productCategory', {
                        required: true,
                        value: product.category,
                        options: [
                            { value: '', label: '-- Select Category --' },
                            { value: 'Entrees', label: 'Entrees' },
                            { value: 'Sides', label: 'Sides' },
                            { value: 'Sauces', label: 'Sauces' },
                            { value: 'Pizza', label: 'Pizza' },
                            { value: 'Prepared Foods', label: 'Prepared Foods' }
                        ]
                    })}
                    ${createFormField('select', 'Unit of Measure', 'productUnit', {
                        required: true,
                        value: product.unit_of_measure,
                        options: [
                            { value: '', label: '-- Select Unit --' },
                            { value: 'each', label: 'Each' },
                            { value: 'dozen', label: 'Dozen' },
                            { value: 'lbs', label: 'Pounds (lbs)' },
                            { value: 'oz', label: 'Ounces (oz)' },
                            { value: 'serving', label: 'Serving' }
                        ]
                    })}
                    ${createFormField('number', 'Selling Price', 'productPrice', {
                        required: true,
                        value: product.selling_price,
                        step: '0.01',
                        min: '0'
                    })}
                    ${createFormField('number', 'Quantity on Hand', 'productQuantity', {
                        required: true,
                        value: product.quantity_on_hand,
                        step: '0.01',
                        min: '0'
                    })}
                    ${createFormField('number', 'Shelf Life (Days)', 'productShelfLife', {
                        value: product.shelf_life_days || '',
                        min: '0'
                    })}
                    ${createFormField('textarea', 'Storage Requirements', 'productStorage', {
                        rows: 2,
                        value: product.storage_requirements || ''
                    })}
                </div>

                <div class="form-section">
                    <h3 class="section-title">Recipe Builder</h3>
                    <p class="form-help-text">Modify ingredients that make up this product</p>

                    <div class="recipe-builder">
                        <div class="recipe-add-section">
                            ${createFormFieldWithOptGroups('select', 'Select Ingredient or Product', 'recipeIngredient', {
                                optgroups: [
                                    {
                                        label: '📦 Ingredients',
                                        options: availableIngredients.map(ing => ({
                                            value: `ingredient:${ing.id}`,
                                            label: `${ing.name} (${ing.unit_of_measure})`
                                        }))
                                    },
                                    {
                                        label: '🍔 Products',
                                        options: availableProducts.map(prod => ({
                                            value: `product:${prod.id}`,
                                            label: `${prod.name} (${prod.unit_of_measure})`
                                        }))
                                    }
                                ]
                            })}
                            ${createFormField('number', 'Quantity', 'recipeQuantity', {
                                placeholder: 'Amount needed',
                                step: '0.01',
                                min: '0'
                            })}
                            <button type="button" class="btn-create-inline" onclick="addIngredientToRecipe()">
                                + Add to Recipe
                            </button>
                        </div>

                        <div id="recipeIngredientsList" class="recipe-ingredients-list">
                        </div>

                        <div class="recipe-cost-summary">
                            <div class="cost-row">
                                <span>💰 Total Ingredient Cost:</span>
                                <strong id="recipeTotalCost">$0.00</strong>
                            </div>
                            <div class="cost-row">
                                <span>📊 Gross Profit:</span>
                                <strong id="recipeGrossProfit">$0.00</strong>
                            </div>
                            <div class="cost-row">
                                <span>📈 Profit Margin:</span>
                                <strong id="recipeMargin">0%</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const buttons = [
            { text: 'Cancel', className: 'modal-btn-secondary', onclick: closeModal },
            { text: 'Update Product', className: 'modal-btn-success', onclick: updateProduct }
        ];

        openModal('Edit Product', bodyHTML, buttons, true);

        // Render existing recipe and update costs
        setTimeout(() => {
            renderRecipeIngredientsList();
            updateRecipeCostSummary();

            // Add event listener to price field
            const priceField = document.getElementById('productPrice');
            if (priceField) {
                priceField.addEventListener('input', updateRecipeCostSummary);
            }

            // Prevent Enter key from closing modal unexpectedly
            const modalBody = document.getElementById('modalBody');
            if (modalBody) {
                modalBody.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && e.target.tagName !== 'BUTTON' && e.target.tagName !== 'TEXTAREA') {
                        e.preventDefault();
                        return false;
                    }
                });
            }
        }, 100);

    } catch (error) {
        console.error('Error loading product for edit:', error);
        showMessage('Failed to load product details', 'error');
    }
}

/**
 * Update existing product
 */
async function updateProduct() {
    clearFormErrors('modalBody');
    const formData = getFormData('modalBody');
    const productId = formData.productId;

    // Validation
    const errors = [];
    if (!formData.productCode?.trim()) errors.push('Product Code is required');
    if (!formData.productName?.trim()) errors.push('Product Name is required');
    if (!formData.productCategory) errors.push('Category is required');
    if (!formData.productUnit) errors.push('Unit of Measure is required');
    if (!formData.productPrice || parseFloat(formData.productPrice) <= 0) {
        errors.push('Selling Price is required and must be greater than 0');
    }

    if (errors.length > 0) {
        showMessage(errors.join('; '), 'error');
        return;
    }

    const productData = {
        product_code: formData.productCode.trim(),
        product_name: formData.productName.trim(),
        category: formData.productCategory,
        unit_of_measure: formData.productUnit,
        quantity_on_hand: parseFloat(formData.productQuantity) || 0,
        selling_price: parseFloat(formData.productPrice),
        shelf_life_days: formData.productShelfLife ? parseInt(formData.productShelfLife) : null,
        storage_requirements: formData.productStorage?.trim() || '',
        recipe: currentRecipeIngredients.map(item => ({
            source_type: item.source_type,
            source_id: item.source_id,
            quantity_needed: item.quantity,
            unit_of_measure: item.unit || 'unit'
        }))
    };

    try {
        const response = await fetch(`/api/products/${productId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Product "${productData.product_name}" updated successfully!`, 'success');
            closeModal();
            loadProducts(); // Refresh products table
        } else {
            showMessage(`Failed to update product: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error updating product:', error);
        showMessage('Failed to update product. Please try again.', 'error');
    }
}

/**
 * Delete product
 */
async function deleteProduct(productId, productName) {
    if (!confirm(`Are you sure you want to delete "${productName}"?\n\nThis will also remove the product's recipe. This action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/products/${productId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Product "${productName}" deleted successfully!`, 'success');
            loadProducts(); // Refresh products table
        } else {
            showMessage(`Failed to delete product: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting product:', error);
        showMessage('Failed to delete product. Please try again.', 'error');
    }
}

// Log Layer 3 functions available
console.log('%c✓ Layer 3: Product Management Ready', 'color: green; font-weight: bold; font-size: 14px');
console.log('New functions available:');
console.log('  - openCreateProductModal()');
console.log('  - openEditProductModal(productId)');
console.log('  - saveNewProduct()');
console.log('  - updateProduct()');
console.log('  - deleteProduct(productId, productName)');
console.log('  - addIngredientToRecipe()');
console.log('  - removeIngredientFromRecipe(ingredientId)');