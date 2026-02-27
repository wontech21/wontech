// WONTECH Inventory Module
// Extracted from dashboard.js — inventory loading, rendering, filtering, category management, ingredient CRUD

// ========== REGISTER WITH GLOBAL REGISTRIES ==========
window.renderRegistry['inventory'] = renderInventoryTable;
window.loadRegistry['inventory'] = loadInventory;

// ========== MODULE-SCOPE STATE ==========
let inventoryItemsMap = {};
let availableCategories = [];
let savedIngredientFormState = null;

// Store composite recipe items globally
let compositeRecipeItems = [];

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

// ========== INVENTORY LOADING AND RENDERING ==========

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

// ========== VARIANT DISPLAY FUNCTIONS ==========

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

// ========== FILTER LOADING ==========

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

// ========== EDIT ITEM (LEGACY) ==========

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
// Category Management and Selection Functions
// ============================================================

async function loadCategoriesList() {
    try {
        const response = await fetch('/api/filters/categories');
        availableCategories = await response.json();
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

        if (result.success) {
            // Remove dropdown
            const dropdown = document.querySelector('.category-dropdown');
            if (dropdown) dropdown.remove();

            // Reload inventory and refresh categories list
            await Promise.all([
                loadInventory(),
                loadCategoriesFilter(),
                loadCategoriesList()  // IMPORTANT: Refresh the available categories list
            ]);
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
// Layer 2: Inline Brand/Supplier Creation (from ingredient form)
// ============================================================

/**
 * Open modal to create a new brand
 */
function openCreateBrandModal(brandSelectId) {
    // Save the current ingredient form state before opening brand modal
    const ingredientForm = document.getElementById('ingredientForm');

    if (ingredientForm) {
        savedIngredientFormState = getFormData('ingredientForm');
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

    try {
        const response = await fetch('/api/brands', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(brandData)
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Brand "${brandData.brand_name}" created successfully!`, 'success');

            // Restore the ingredient modal with the saved form data
            if (savedIngredientFormState) {
                // Update the saved state with the new brand
                savedIngredientFormState.ingredientBrand = brandData.brand_name;

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

/**
 * Open modal to create a new supplier
 */
function openCreateSupplierModal(supplierSelectId) {
    // Save the current ingredient form state before opening supplier modal
    const ingredientForm = document.getElementById('ingredientForm');

    if (ingredientForm) {
        savedIngredientFormState = getFormData('ingredientForm');
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

            // Restore the ingredient modal with the saved form data
            if (savedIngredientFormState) {
                // Update the saved state with the new supplier
                savedIngredientFormState.ingredientSupplier = supplierData.supplier_name;

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

// ============================================================================
// LAYER 2: INGREDIENT MANAGEMENT
// ============================================================================

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
