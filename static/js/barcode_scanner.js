/**
 * Barcode Scanner Module
 * Handles barcode scanning, lookup, and inventory integration
 */

let currentCountId = null;
let lastScannedBarcode = null;
let scannerActive = false;

/**
 * Open barcode scanner for inventory count (from create count modal)
 */
function openBarcodeScannerForCount() {
    // Get the count ID from the form if it exists, otherwise use a temp ID
    const countNumberInput = document.getElementById('countNumber');
    if (countNumberInput && countNumberInput.value) {
        currentCountId = 'temp_' + countNumberInput.value;
    } else {
        currentCountId = 'temp_new_count';
    }

    document.getElementById('barcodeScannerModal').style.display = 'block';
    document.getElementById('barcode-results').style.display = 'none';
    initializeScanner();
}

/**
 * Open barcode scanner for inventory count
 */
function openBarcodeScanner(countId) {
    currentCountId = countId;
    document.getElementById('barcodeScannerModal').style.display = 'block';
    document.getElementById('barcode-results').style.display = 'none';
    initializeScanner();
}

/**
 * Close barcode scanner modal
 */
function closeBarcodeScanner() {
    stopScanner();
    document.getElementById('barcodeScannerModal').style.display = 'none';
    currentCountId = null;
    lastScannedBarcode = null;
}

/**
 * Initialize QuaggaJS barcode scanner
 */
function initializeScanner() {
    if (scannerActive) {
        return;
    }

    updateScannerStatus('Initializing camera...');

    Quagga.init({
        inputStream: {
            name: "Live",
            type: "LiveStream",
            target: document.querySelector('#scanner-container'),
            constraints: {
                width: 640,
                height: 480,
                facingMode: "environment" // Use rear camera on mobile
            }
        },
        decoder: {
            readers: [
                "ean_reader",      // European Article Number (most grocery items)
                "ean_8_reader",    // EAN-8 (shorter barcodes)
                "upc_reader",      // Universal Product Code (US/Canada)
                "upc_e_reader",    // UPC-E (compressed UPC)
                "code_128_reader", // Common in warehouses
                "code_39_reader"   // Alphanumeric barcodes
            ],
            multiple: false
        },
        locate: true,
        locator: {
            patchSize: "medium",
            halfSample: true
        }
    }, function(err) {
        if (err) {
            console.error('Scanner initialization error:', err);
            updateScannerStatus('Camera access denied or not available. Please check permissions.');
            return;
        }

        scannerActive = true;
        Quagga.start();
        updateScannerStatus('Position barcode in view...');
    });

    // Handle barcode detection
    Quagga.onDetected(handleBarcodeDetected);
}

/**
 * Stop the scanner
 */
function stopScanner() {
    if (scannerActive) {
        Quagga.stop();
        scannerActive = false;
        Quagga.offDetected(handleBarcodeDetected);
    }
}

/**
 * Restart scanner for another scan
 */
function restartScanner() {
    document.getElementById('barcode-results').style.display = 'none';
    lastScannedBarcode = null;
    updateScannerStatus('Position barcode in view...');

    if (!scannerActive) {
        initializeScanner();
    }
}

/**
 * Update scanner status message
 */
function updateScannerStatus(message) {
    document.getElementById('scanner-message').textContent = message;
}

/**
 * Handle barcode detection from QuaggaJS
 */
function handleBarcodeDetected(result) {
    const barcode = result.codeResult.code;

    // Ignore duplicate detections
    if (barcode === lastScannedBarcode) {
        return;
    }

    lastScannedBarcode = barcode;
    stopScanner();

    updateScannerStatus(`✅ Detected: ${barcode}`);
    document.getElementById('scanned-barcode-value').textContent = barcode;
    document.getElementById('barcode-results').style.display = 'block';
    document.getElementById('barcode-loading').style.display = 'block';
    document.getElementById('barcode-lookup-results').style.display = 'none';

    // Lookup barcode in all sources
    lookupBarcode(barcode);
}

/**
 * Lookup barcode across all databases (inventory + external APIs)
 */
async function lookupBarcode(barcode) {
    try {
        const response = await fetch(`/api/barcode/lookup/${barcode}`);
        const data = await response.json();

        document.getElementById('barcode-loading').style.display = 'none';
        document.getElementById('barcode-lookup-results').style.display = 'block';

        if (data.success) {
            displayBarcodeResults(data);
        } else {
            showError('Barcode lookup failed: ' + data.error);
        }

    } catch (error) {
        console.error('Barcode lookup error:', error);
        document.getElementById('barcode-loading').style.display = 'none';
        showError('Failed to lookup barcode. Please try again.');
    }
}

/**
 * Display barcode lookup results
 */
function displayBarcodeResults(data) {
    // Reset sections
    document.getElementById('inventory-match-section').style.display = 'none';
    document.getElementById('external-sources-section').style.display = 'none';
    document.getElementById('barcode-not-found').style.display = 'none';

    // Check if found in inventory
    if (data.found_in_inventory && data.inventory_items.length > 0) {
        displayInventoryMatch(data.inventory_items[0]);
    }
    // Check external sources
    else if (data.results && data.results.length > 0) {
        displayExternalSources(data.results, data.best_match);
    }
    // Not found anywhere
    else {
        document.getElementById('barcode-not-found').style.display = 'block';
    }
}

/**
 * Display inventory match
 */
function displayInventoryMatch(item) {
    const section = document.getElementById('inventory-match-section');
    const detailsDiv = document.getElementById('inventory-match-details');

    detailsDiv.innerHTML = `
        <p><strong>Name:</strong> ${item.name}</p>
        <p><strong>Category:</strong> ${item.category}</p>
        <p><strong>Brand:</strong> ${item.brand || 'N/A'}</p>
        <p><strong>Unit:</strong> ${item.unit_of_measure}</p>
        <p><strong>Current Stock:</strong> ${item.quantity_on_hand} ${item.unit_of_measure}</p>
    `;

    // Pre-fill quantity with current stock for verification
    document.getElementById('barcode-quantity').value = item.quantity_on_hand;

    section.style.display = 'block';

    // Show or hide add to count section based on context
    if (currentCountId) {
        document.getElementById('add-to-count-section').style.display = 'block';
    } else {
        document.getElementById('add-to-count-section').style.display = 'none';
    }
}

/**
 * Display external database results
 */
function displayExternalSources(results, bestMatch) {
    const section = document.getElementById('external-sources-section');
    const listDiv = document.getElementById('external-sources-list');

    let html = '';

    // Show best match prominently
    if (bestMatch) {
        html += `
            <div style="border: 2px solid #28a745; padding: 15px; border-radius: 8px; background: #f8f9fa;">
                <h5 style="margin-top: 0; color: #28a745;">⭐ Best Match</h5>
                ${formatExternalResult(bestMatch)}
            </div>
        `;
    }

    // Show other sources
    results.forEach(result => {
        if (result !== bestMatch) {
            html += `
                <div style="border: 1px solid #dee2e6; padding: 15px; border-radius: 8px;">
                    ${formatExternalResult(result)}
                </div>
            `;
        }
    });

    listDiv.innerHTML = html;
    section.style.display = 'block';

    // Store best match data for creating ingredient
    if (bestMatch) {
        document.getElementById('new-item-external-data').value = JSON.stringify(bestMatch);
    }
}

/**
 * Format external result for display
 */
function formatExternalResult(result) {
    return `
        <p><strong>Source:</strong> ${result.source || 'Unknown'}${result.cached ? ' (Cached)' : ''}</p>
        <p><strong>Product:</strong> ${result.product_name || 'N/A'}</p>
        <p><strong>Brand:</strong> ${result.brand || 'N/A'}</p>
        <p><strong>Category:</strong> ${result.category || 'N/A'}</p>
        ${result.quantity ? `<p><strong>Quantity:</strong> ${result.quantity}</p>` : ''}
        ${result.image_url ? `<img src="${result.image_url}" style="max-width: 150px; border-radius: 4px; margin-top: 10px;" alt="Product">` : ''}
    `;
}

/**
 * Add barcode item to count
 */
async function addBarcodeItemToCount() {
    if (!currentCountId || !lastScannedBarcode) {
        showError('No active count or barcode');
        return;
    }

    const quantity = parseFloat(document.getElementById('barcode-quantity').value);

    if (isNaN(quantity) || quantity < 0) {
        showError('Please enter a valid quantity');
        return;
    }

    // Check if we're in create count modal (temp ID) or editing existing count
    if (currentCountId.toString().startsWith('temp_')) {
        // Adding to create count form - add a row directly
        addBarcodeToCountForm(quantity);
    } else {
        // Adding to existing saved count - use API
        addBarcodeToSavedCount(quantity);
    }
}

/**
 * Add barcode item to the create count form (before count is saved)
 */
async function addBarcodeToCountForm(quantity) {
    // Get item details from the displayed inventory match
    const detailsDiv = document.getElementById('inventory-match-details');
    if (!detailsDiv || !detailsDiv.innerHTML) {
        showError('No item details available');
        return;
    }

    // Fetch ingredient details by barcode to get all info
    try {
        const response = await fetch(`/api/inventory/detailed`);
        const items = await response.json();

        const item = items.find(i => i.barcode === lastScannedBarcode);

        if (!item) {
            showError('Item not found');
            return;
        }

        // Add row to count items table
        if (typeof addCountRow === 'function') {
            addCountRow();

            // Get the last added row
            const tbody = document.getElementById('countItemsTableBody');
            const lastRow = tbody.lastElementChild;

            if (lastRow) {
                // Fill in the values
                lastRow.querySelector('.count-ingredient-code-input').value = item.ingredient_code;
                lastRow.querySelector('.count-ingredient-name-input').value = item.ingredient_name;
                lastRow.querySelector('.count-expected-input').value = item.quantity_on_hand;
                lastRow.querySelector('.count-counted-input').value = quantity;
                lastRow.querySelector('.count-uom-input').value = item.unit_of_measure;
                lastRow.querySelector('.count-notes-input').value = `Scanned: ${lastScannedBarcode}`;

                // Store data
                lastRow.dataset.ingredientName = item.ingredient_name;
                lastRow.dataset.unitOfMeasure = item.unit_of_measure;

                // Calculate variance
                const variance = quantity - item.quantity_on_hand;
                lastRow.querySelector('.count-variance-input').value = variance.toFixed(2);

                // Update summary
                if (typeof updateCountSummary === 'function') {
                    updateCountSummary();
                }
            }
        }

        showSuccess(`✅ Added to count: ${item.ingredient_name}`);

        // Close scanner after short delay
        setTimeout(() => {
            closeBarcodeScanner();
        }, 1500);

    } catch (error) {
        console.error('Error adding to count form:', error);
        showError('Failed to add item');
    }
}

/**
 * Add barcode item to saved count via API
 */
async function addBarcodeToSavedCount(quantity) {
    try {
        const response = await fetch('/api/barcode/add-to-count', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                count_id: currentCountId,
                barcode: lastScannedBarcode,
                quantity: quantity
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess(`✅ Added to count: ${data.item.name}`);

            // Reload count items if function exists
            if (typeof loadCountItems === 'function') {
                setTimeout(() => loadCountItems(currentCountId), 500);
            }

            // Close scanner or scan another
            setTimeout(() => {
                closeBarcodeScanner();
            }, 1500);

        } else if (data.prompt_create) {
            showError('Item not found in inventory. Create it first.');
        } else {
            showError('Failed to add to count: ' + data.error);
        }

    } catch (error) {
        console.error('Add to count error:', error);
        showError('Failed to add item to count');
    }
}

/**
 * Show create from barcode modal
 */
function showCreateFromBarcodeModal() {
    if (!lastScannedBarcode) {
        showError('No barcode scanned');
        return;
    }

    // Load categories
    loadCategoriesForBarcode();

    // Fill in barcode
    document.getElementById('new-item-barcode').value = lastScannedBarcode;
    document.getElementById('display-barcode').value = lastScannedBarcode;

    // Pre-fill from external data if available
    const externalDataEl = document.getElementById('new-item-external-data');
    if (externalDataEl.value) {
        try {
            const data = JSON.parse(externalDataEl.value);

            if (data.product_name) {
                document.getElementById('new-ingredient-name').value = data.product_name;
            }
            if (data.brand) {
                document.getElementById('new-ingredient-brand').value = data.brand;
            }

            // Try to generate ingredient code from name
            if (data.product_name) {
                const code = data.product_name
                    .toUpperCase()
                    .replace(/[^A-Z0-9]/g, '')
                    .substring(0, 10);
                document.getElementById('new-ingredient-code').value = code;
            }

        } catch (e) {
            console.error('Error parsing external data:', e);
        }
    }

    document.getElementById('createFromBarcodeModal').style.display = 'block';
}

/**
 * Close create from barcode modal
 */
function closeCreateFromBarcodeModal() {
    document.getElementById('createFromBarcodeModal').style.display = 'none';
    document.getElementById('create-from-barcode-form').reset();
}

/**
 * Load categories for barcode ingredient creation
 */
async function loadCategoriesForBarcode() {
    try {
        const response = await fetch('/api/categories/list');
        const categories = await response.json();

        const select = document.getElementById('new-ingredient-category');
        select.innerHTML = '<option value="">Select Category</option>';

        categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat.category_name;
            option.textContent = cat.category_name;
            select.appendChild(option);
        });

    } catch (error) {
        console.error('Failed to load categories:', error);
    }
}

/**
 * Save ingredient created from barcode
 */
async function saveIngredientFromBarcode() {
    const form = document.getElementById('create-from-barcode-form');

    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const ingredientData = {
        barcode: document.getElementById('new-item-barcode').value,
        ingredient_code: document.getElementById('new-ingredient-code').value,
        ingredient_name: document.getElementById('new-ingredient-name').value,
        brand: document.getElementById('new-ingredient-brand').value,
        category: document.getElementById('new-ingredient-category').value,
        unit_of_measure: document.getElementById('new-ingredient-uom').value,
        unit_cost: parseFloat(document.getElementById('new-ingredient-cost').value),
        quantity_on_hand: parseFloat(document.getElementById('new-ingredient-quantity').value) || 0,
        supplier_name: document.getElementById('new-ingredient-supplier').value
    };

    try {
        const response = await fetch('/api/barcode/create-ingredient', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ingredientData)
        });

        const data = await response.json();

        if (data.success) {
            showSuccess(`✅ Ingredient created: ${ingredientData.ingredient_name}`);
            closeCreateFromBarcodeModal();

            // Reload inventory if function exists
            if (typeof loadDetailedInventory === 'function') {
                setTimeout(() => loadDetailedInventory(), 500);
            }

            // If in count context, add to count
            if (currentCountId) {
                setTimeout(() => addBarcodeItemToCount(), 1000);
            } else {
                closeBarcodeScanner();
            }

        } else {
            showError('Failed to create ingredient: ' + data.error);
        }

    } catch (error) {
        console.error('Create ingredient error:', error);
        showError('Failed to create ingredient');
    }
}

/**
 * Show manual create modal (no barcode data)
 */
function showCreateManualModal() {
    // This would open the standard create ingredient modal
    // For now, just show the barcode modal with no pre-fill
    showCreateFromBarcodeModal();
}

/**
 * Show success message
 */
function showSuccess(message) {
    updateScannerStatus(message);
}

/**
 * Show error message
 */
function showError(message) {
    updateScannerStatus('❌ ' + message);
}

// Add CSS for spinner
const style = document.createElement('style');
style.textContent = `
.spinner {
    border: 4px solid #f3f3f3;
    border-top: 4px solid #3498db;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
    margin: 0 auto;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
`;
document.head.appendChild(style);
