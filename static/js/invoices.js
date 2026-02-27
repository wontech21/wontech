// WONTECH Invoices Module
// Invoice table, details modal, create/import/delete, reconciliation

// Register with global registries
window.renderRegistry['invoices'] = renderInvoicesTable;
window.renderRegistry['unreconciled'] = renderUnreconciledInvoicesTable;
window.loadRegistry['invoices'] = loadInvoices;
window.loadRegistry['unreconciled'] = loadInvoices;

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

// ========== LOAD INVOICES ==========

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

// ========== RENDER TABLES ==========

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
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><span class="badge ${inv.payment_status.toUpperCase() === 'PAID' ? 'badge-success' : 'badge-warning'}">${inv.payment_status}</span></td>
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
            <td class="invoice-clickable" onclick="showInvoiceDetails('${escapedInvoiceNum}')"><span class="badge ${inv.payment_status.toUpperCase() === 'PAID' ? 'badge-success' : 'badge-warning'}">${inv.payment_status}</span></td>
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

// ========== INVOICE DETAILS MODAL ==========

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

// ========== PAYMENT STATUS ==========

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

// ========== INVOICE MODAL EVENT LISTENERS ==========

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

// Close create/import modals when clicking outside
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
// Invoice Date Filters
// ============================================================

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
