// WONTECH Counts Module
// Stocktake counts, variance, audit history, date filters

// Register with global registries
window.renderRegistry['counts'] = function() { /* counts don't use pagination render */ };
window.loadRegistry['counts'] = loadCounts;

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
            row.dataset.ingredientCode = ingredient.ingredient_code;
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
        varianceInput.style.color = '#28a745';
    } else if (variance < 0) {
        varianceInput.style.color = '#dc3545';
    } else {
        varianceInput.style.color = '#6c757d';
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
            loadInventory();
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

// ========== COUNT DATE FILTER FUNCTIONS ==========

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
