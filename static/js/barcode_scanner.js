/**
 * Barcode Scanner Module
 * Handles barcode scanning, lookup, and inventory integration
 */

let currentCountId = null;
let lastScannedBarcode = null;
let scannerActive = false;
let detectionBuffer = [];  // Store recent detections for validation
const REQUIRED_DETECTIONS = 3;  // Require 3 consistent reads
const DETECTION_WINDOW = 10;  // Clear buffer after 10 frames without match
let scannerContext = 'count';  // 'count', 'ingredient', or 'invoice'
let scannedExternalData = null;  // Store external API data for ingredient/invoice creation

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

    scannerContext = 'count';
    const modal = document.getElementById('barcodeScannerModal');
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.getElementById('barcode-results').style.display = 'none';
    initializeScanner();
}

/**
 * Open barcode scanner for creating ingredient
 */
function openBarcodeScannerForIngredient() {
    scannerContext = 'ingredient';
    currentCountId = null;
    const modal = document.getElementById('barcodeScannerModal');
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.getElementById('barcode-results').style.display = 'none';
    initializeScanner();
}

/**
 * Open barcode scanner for creating invoice
 */
function openBarcodeScannerForInvoice() {
    scannerContext = 'invoice';
    currentCountId = null;
    const modal = document.getElementById('barcodeScannerModal');
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.getElementById('barcode-results').style.display = 'none';
    initializeScanner();
}

/**
 * Open barcode scanner for inventory count
 */
function openBarcodeScanner(countId) {
    currentCountId = countId;
    const modal = document.getElementById('barcodeScannerModal');
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.getElementById('barcode-results').style.display = 'none';
    initializeScanner();
}

/**
 * Close barcode scanner modal
 */
function closeBarcodeScanner() {
    stopScanner();
    const modal = document.getElementById('barcodeScannerModal');
    modal.style.display = 'none';
    modal.classList.remove('active');
    currentCountId = null;
    lastScannedBarcode = null;
    scannedExternalData = null;  // Clear external data
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
            },
            area: { // Focus area in center
                top: "30%",
                right: "10%",
                left: "10%",
                bottom: "30%"
            }
        },
        decoder: {
            readers: [
                "ean_reader",      // European Article Number (most grocery items)
                "ean_8_reader",    // EAN-8 (shorter barcodes)
                "upc_reader",      // Universal Product Code (US/Canada)
                "upc_e_reader",    // UPC-E (compressed UPC)
                "code_128_reader"  // Re-added for difficult scans
            ],
            multiple: false,
            debug: {
                drawBoundingBox: true,
                showFrequency: false,
                drawScanline: true,
                showPattern: false
            }
        },
        locate: true,
        locator: {
            patchSize: "medium",
            halfSample: true
        },
        numOfWorkers: 4,
        frequency: 5,  // Scan more frequently (every 5 frames instead of 10)
        debug: false
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
    detectionBuffer = [];  // Clear detection buffer
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
    let barcode = result.codeResult.code;
    const quality = result.codeResult.decodedCodes
        .filter(code => code.error !== undefined)
        .reduce((sum, code) => sum + code.error, 0) / result.codeResult.decodedCodes.length;

    // Quality threshold - reject low quality scans (higher error = lower quality)
    if (quality > 0.15) {
        console.log('Low quality scan rejected:', barcode, 'quality:', quality);
        return;
    }

    // Normalize barcode (remove leading zero from UPC codes)
    barcode = normalizeBarcodeFormat(barcode);

    // Validate barcode format (must be valid length and digits only for UPC/EAN)
    if (!isValidBarcodeFormat(barcode)) {
        console.log('Invalid barcode format rejected:', barcode);
        return;
    }

    // Add to detection buffer
    detectionBuffer.push(barcode);

    // Keep only recent detections
    if (detectionBuffer.length > DETECTION_WINDOW) {
        detectionBuffer.shift();
    }

    // Count occurrences of this barcode in buffer
    const count = detectionBuffer.filter(b => b === barcode).length;

    // Show feedback
    updateScannerStatus(`Scanning... (${count}/${REQUIRED_DETECTIONS}) ${barcode}`);

    // Require multiple consistent detections to avoid false positives
    if (count >= REQUIRED_DETECTIONS) {
        // Ignore if already processed
        if (barcode === lastScannedBarcode) {
            return;
        }

        lastScannedBarcode = barcode;
        detectionBuffer = [];  // Clear buffer
        stopScanner();

        updateScannerStatus(`✅ Detected: ${barcode}`);
        document.getElementById('scanned-barcode-value').textContent = barcode;
        document.getElementById('barcode-results').style.display = 'block';
        document.getElementById('barcode-loading').style.display = 'block';
        document.getElementById('barcode-lookup-results').style.display = 'none';

        // Lookup barcode in all sources
        lookupBarcode(barcode);
    }
}

/**
 * Normalize barcode format
 * Converts EAN-13 with leading zero to UPC-A (12 digits)
 * This fixes the issue where scanners add a leading 0
 */
function normalizeBarcodeFormat(barcode) {
    barcode = barcode.trim();

    // If it's a 13-digit EAN code starting with 0, convert to 12-digit UPC
    // Example: 0041220576555 (EAN-13) → 041220576555 (UPC-A)
    if (/^\d{13}$/.test(barcode) && barcode.charAt(0) === '0') {
        console.log('Converting EAN-13 to UPC-A:', barcode, '→', barcode.substring(1));
        return barcode.substring(1);  // Remove leading zero
    }

    return barcode;
}

/**
 * Validate barcode format
 */
function isValidBarcodeFormat(barcode) {
    // Remove any whitespace
    barcode = barcode.trim();

    // Check for valid barcode lengths
    // EAN-13: 13 digits (but we normalize to UPC-A if starts with 0)
    // EAN-8: 8 digits
    // UPC-A: 12 digits
    // UPC-E: 6-8 digits
    const validLengths = [6, 7, 8, 12, 13];

    // For numeric barcodes (UPC/EAN), must be digits only and valid length
    if (/^\d+$/.test(barcode)) {
        return validLengths.includes(barcode.length);
    }

    // For alphanumeric (Code 128/39), length should be reasonable (3-40 chars)
    if (/^[A-Z0-9\-]+$/i.test(barcode)) {
        return barcode.length >= 3 && barcode.length <= 40;
    }

    // Reject anything else
    return false;
}

/**
 * Manual barcode entry fallback
 */
function lookupManualBarcode() {
    const input = document.getElementById('manual-barcode-input');
    const barcode = input.value.trim();

    if (!barcode) {
        showError('Please enter a barcode');
        return;
    }

    // Normalize and validate
    const normalized = normalizeBarcodeFormat(barcode);
    if (!isValidBarcodeFormat(normalized)) {
        showError('Invalid barcode format. Must be 6-13 digits for UPC/EAN codes.');
        return;
    }

    // Show results section
    lastScannedBarcode = normalized;
    document.getElementById('scanned-barcode-value').textContent = normalized;
    document.getElementById('barcode-results').style.display = 'block';
    document.getElementById('barcode-loading').style.display = 'block';
    document.getElementById('barcode-lookup-results').style.display = 'none';

    // Clear input
    input.value = '';

    // Lookup
    lookupBarcode(normalized);
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

    // Show appropriate action section based on context
    const addToCountSection = document.getElementById('add-to-count-section');
    if (scannerContext === 'count' && currentCountId) {
        addToCountSection.style.display = 'block';
    } else if (scannerContext === 'ingredient') {
        // For ingredient context, show "Use This Item" button
        addToCountSection.style.display = 'block';
        addToCountSection.innerHTML = `
            <button class="btn-success" onclick="useScannedItemForIngredient()">Use This Item's Data</button>
        `;
    } else if (scannerContext === 'invoice') {
        // For invoice context, show "Add to Invoice" button
        addToCountSection.style.display = 'block';
        addToCountSection.innerHTML = `
            <label>Quantity:</label>
            <input type="number" id="barcode-quantity" step="0.01" min="0" value="1">
            <button class="btn-success" onclick="addScannedItemToInvoice()">Add to Invoice</button>
        `;
    } else {
        addToCountSection.style.display = 'none';
    }
}

/**
 * Display external database results
 */
function displayExternalSources(results, bestMatch) {
    const section = document.getElementById('external-sources-section');
    const listDiv = document.getElementById('external-sources-list');

    let html = '';

    if (results.length === 0) {
        html = `
            <div style="padding: 15px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px;">
                <p style="margin: 0;"><strong>⚠️ Not found in external databases</strong></p>
                <p style="margin: 10px 0 0 0; font-size: 0.9em;">
                    Checked: Open Food Facts, UPC Item DB, Barcode Lookup
                </p>
            </div>
        `;
    } else {
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
    }

    listDiv.innerHTML = html;
    section.style.display = 'block';

    // Store best match data for creating ingredient
    if (bestMatch) {
        scannedExternalData = bestMatch;  // Store in global variable for all contexts

        // Also store in DOM element if it exists (for count context)
        const externalDataEl = document.getElementById('new-item-external-data');
        if (externalDataEl) {
            externalDataEl.value = JSON.stringify(bestMatch);
        }
    }

    // Add context-appropriate action buttons
    const actionsDiv = document.getElementById('external-sources-actions');
    if (actionsDiv) {
        if (scannerContext === 'count') {
            actionsDiv.innerHTML = '<button class="btn-primary" onclick="showCreateFromBarcodeModal()">Create New Ingredient from Barcode</button>';
        } else if (scannerContext === 'ingredient') {
            actionsDiv.innerHTML = '<button class="btn-primary" onclick="useScannedItemForIngredient()">Use This Product Data</button>';
        } else if (scannerContext === 'invoice') {
            actionsDiv.innerHTML = '<button class="btn-primary" onclick="showCreateFromBarcodeModal()">Create New Ingredient from Barcode</button>';
        }
    }
}

/**
 * Format external result for display
 */
function formatExternalResult(result) {
    let html = `
        <p><strong>Source:</strong> ${result.source || 'Unknown'}${result.cached ? ' (Cached)' : ''}</p>
        <p><strong>Product:</strong> ${result.product_name || 'N/A'}</p>
        <p><strong>Brand:</strong> ${result.brand || 'N/A'}</p>
        <p><strong>Category:</strong> ${result.category || 'N/A'}</p>
        ${result.quantity ? `<p><strong>Quantity:</strong> ${result.quantity}</p>` : ''}
    `;

    // Show which barcode format was used (if available)
    if (result.barcode_format_used) {
        html += `<p style="font-size: 0.85em; color: #666;"><em>Found using: ${result.barcode_format_used}</em></p>`;
    }

    // Show image if available
    if (result.image_url) {
        html += `<img src="${result.image_url}" style="max-width: 150px; border-radius: 4px; margin-top: 10px;" alt="Product">`;
    }

    return html;
}

/**
 * Add barcode item to count
 */
async function addBarcodeItemToCount() {
    console.log('addBarcodeItemToCount called');
    console.log('currentCountId:', currentCountId);
    console.log('lastScannedBarcode:', lastScannedBarcode);

    if (!currentCountId || !lastScannedBarcode) {
        showError('No active count or barcode');
        console.error('Missing currentCountId or lastScannedBarcode');
        return;
    }

    const quantityInput = document.getElementById('barcode-quantity');
    if (!quantityInput) {
        showError('Quantity input field not found');
        console.error('barcode-quantity input element not found');
        return;
    }

    const quantity = parseFloat(quantityInput.value);
    console.log('Quantity to add:', quantity);

    if (isNaN(quantity) || quantity < 0) {
        showError('Please enter a valid quantity');
        return;
    }

    // Check if we're in create count modal (temp ID) or editing existing count
    if (currentCountId.toString().startsWith('temp_')) {
        console.log('Adding to create count form (temp ID)');
        // Adding to create count form - add a row directly
        await addBarcodeToCountForm(quantity);
    } else {
        console.log('Adding to existing saved count');
        // Adding to existing saved count - use API
        await addBarcodeToSavedCount(quantity);
    }
}

/**
 * Add barcode item to the create count form (before count is saved)
 */
async function addBarcodeToCountForm(quantity) {
    console.log('addBarcodeToCountForm called with quantity:', quantity);

    // Get item details from the displayed inventory match
    const detailsDiv = document.getElementById('inventory-match-details');
    console.log('inventory-match-details div:', detailsDiv);
    console.log('innerHTML:', detailsDiv ? detailsDiv.innerHTML : 'null');

    if (!detailsDiv || !detailsDiv.innerHTML) {
        console.error('No item details div or empty');
        showError('No item details available');
        return;
    }

    // Fetch ingredient details by barcode to get all info
    try {
        console.log('Fetching detailed inventory...');
        const response = await fetch(`/api/inventory/detailed`);
        const items = await response.json();
        console.log('Total items fetched:', items.length);

        console.log('Looking for barcode:', lastScannedBarcode);
        const item = items.find(i => i.barcode === lastScannedBarcode);
        console.log('Found item:', item);

        if (!item) {
            console.error('Item not found in detailed inventory');
            showError('Item not found in inventory');
            return;
        }

        // Add row to count items table
        console.log('Checking addCountRow function:', typeof addCountRow);
        if (typeof addCountRow === 'function') {
            console.log('Calling addCountRow()');
            addCountRow();

            // Get the last added row
            const tbody = document.getElementById('countItemsTableBody');
            console.log('Count items tbody:', tbody);

            const lastRow = tbody ? tbody.lastElementChild : null;
            console.log('Last row:', lastRow);

            if (lastRow) {
                console.log('Filling row with data...');
                // Fill in the values
                lastRow.querySelector('.count-ingredient-code-input').value = item.ingredient_code;
                lastRow.querySelector('.count-ingredient-name-input').value = item.ingredient_name;
                lastRow.querySelector('.count-expected-input').value = item.quantity_on_hand;
                lastRow.querySelector('.count-counted-input').value = quantity;
                lastRow.querySelector('.count-uom-input').value = item.unit_of_measure;
                lastRow.querySelector('.count-notes-input').value = `Scanned: ${lastScannedBarcode} | Brand: ${item.brand || 'N/A'}`;

                // Store data
                lastRow.dataset.ingredientName = item.ingredient_name;
                lastRow.dataset.unitOfMeasure = item.unit_of_measure;

                // Calculate variance
                const variance = quantity - item.quantity_on_hand;
                lastRow.querySelector('.count-variance-input').value = variance.toFixed(2);

                console.log('Row filled successfully');

                // Update summary
                if (typeof updateCountSummary === 'function') {
                    console.log('Updating count summary');
                    updateCountSummary();
                }

                showSuccess(`✅ Added to count: ${item.ingredient_name}`);

                // Close scanner after short delay
                setTimeout(() => {
                    closeBarcodeScanner();
                }, 1500);
            } else {
                console.error('No last row found after addCountRow()');
                showError('Failed to add row to count table');
            }
        } else {
            console.error('addCountRow is not a function');
            showError('Count table not available');
        }

    } catch (error) {
        console.error('Error adding to count form:', error);
        showError('Failed to add item: ' + error.message);
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

    // Show/hide count quantity section based on context
    const countQtySection = document.getElementById('count-quantity-section');
    const countQtyInput = document.getElementById('new-ingredient-counted-qty');
    const createButtonText = document.getElementById('create-button-text');

    if (currentCountId) {
        // We're in a count context
        countQtySection.style.display = 'block';
        countQtyInput.setAttribute('required', 'required');
        createButtonText.textContent = 'Create & Add to Count';
    } else {
        // Not in a count
        countQtySection.style.display = 'none';
        countQtyInput.removeAttribute('required');
        createButtonText.textContent = 'Create Ingredient';
    }

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

    const modal = document.getElementById('createFromBarcodeModal');
    modal.style.display = 'flex';
    modal.classList.add('active');
}

/**
 * Close create from barcode modal
 */
function closeCreateFromBarcodeModal() {
    const modal = document.getElementById('createFromBarcodeModal');
    modal.style.display = 'none';
    modal.classList.remove('active');
    document.getElementById('create-from-barcode-form').reset();
    document.getElementById('new-item-external-data').value = '';
    document.getElementById('new-ingredient-counted-qty').value = '';
}

/**
 * Load categories for barcode ingredient creation
 */
async function loadCategoriesForBarcode() {
    try {
        const response = await fetch('/api/categories/all');
        const categories = await response.json();

        const select = document.getElementById('new-ingredient-category');
        if (!select) {
            console.error('Category select element not found');
            return;
        }

        select.innerHTML = '<option value="">Select Category</option>';

        // Response is an array directly
        if (Array.isArray(categories) && categories.length > 0) {
            console.log(`Loaded ${categories.length} categories`);
            categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat.category_name;
                option.textContent = cat.category_name;
                select.appendChild(option);
            });
        } else {
            console.warn('No categories returned from API, using fallback');
            useFallbackCategories(select);
        }

    } catch (error) {
        console.error('Failed to load categories:', error);
        const select = document.getElementById('new-ingredient-category');
        if (select) {
            useFallbackCategories(select);
        }
    }
}

/**
 * Use fallback categories if API fails
 */
function useFallbackCategories(select) {
    const commonCategories = [
        'Produce', 'Meat', 'Dairy', 'Bakery', 'Dry Goods', 'Canned Goods',
        'Frozen', 'Beverages', 'Condiments', 'Spices', 'Other'
    ];
    commonCategories.forEach(catName => {
        const option = document.createElement('option');
        option.value = catName;
        option.textContent = catName;
        select.appendChild(option);
    });
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

    // Get counted quantity if in count context
    const countedQty = parseFloat(document.getElementById('new-ingredient-counted-qty').value);
    const inCountContext = currentCountId && countedQty;

    const ingredientData = {
        barcode: document.getElementById('new-item-barcode').value,
        ingredient_code: document.getElementById('new-ingredient-code').value,
        ingredient_name: document.getElementById('new-ingredient-name').value,
        brand: document.getElementById('new-ingredient-brand').value || '',
        category: document.getElementById('new-ingredient-category').value,
        unit_of_measure: document.getElementById('new-ingredient-uom').value,
        unit_cost: parseFloat(document.getElementById('new-ingredient-cost').value),
        quantity_on_hand: parseFloat(document.getElementById('new-ingredient-quantity').value) || 0,
        supplier_name: document.getElementById('new-ingredient-supplier').value || ''
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

            // If in count context, add to count with the counted quantity
            if (inCountContext) {
                // Add directly to count form using the ingredient data we already have
                addNewlyCreatedItemToCount(ingredientData, countedQty);
            } else {
                // Not in count context, just close
                setTimeout(() => closeBarcodeScanner(), 500);
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
 * Add newly created ingredient directly to count
 * (different from addBarcodeToCountForm which expects existing inventory item)
 */
function addNewlyCreatedItemToCount(ingredientData, countedQty) {
    // Add row to count items table
    if (typeof addCountRow === 'function') {
        addCountRow();

        // Get the last added row
        const tbody = document.getElementById('countItemsTableBody');
        const lastRow = tbody.lastElementChild;

        if (lastRow) {
            // Fill in the values with data from the form
            lastRow.querySelector('.count-ingredient-code-input').value = ingredientData.ingredient_code;
            lastRow.querySelector('.count-ingredient-name-input').value = ingredientData.ingredient_name;
            lastRow.querySelector('.count-expected-input').value = ingredientData.quantity_on_hand;
            lastRow.querySelector('.count-counted-input').value = countedQty;
            lastRow.querySelector('.count-uom-input').value = ingredientData.unit_of_measure;
            lastRow.querySelector('.count-notes-input').value = `Scanned: ${ingredientData.barcode} | Brand: ${ingredientData.brand} | Supplier: ${ingredientData.supplier_name}`;

            // Store data
            lastRow.dataset.ingredientName = ingredientData.ingredient_name;
            lastRow.dataset.unitOfMeasure = ingredientData.unit_of_measure;

            // Calculate variance
            const variance = countedQty - ingredientData.quantity_on_hand;
            lastRow.querySelector('.count-variance-input').value = variance.toFixed(2);

            // Update summary
            if (typeof updateCountSummary === 'function') {
                updateCountSummary();
            }

            showSuccess(`✅ Added to count: ${ingredientData.ingredient_name} (${countedQty} ${ingredientData.unit_of_measure})`);

            // Close scanner after short delay
            setTimeout(() => {
                closeBarcodeScanner();
            }, 1500);
        }
    } else {
        showError('Count form not available');
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

/**
 * Use scanned item data to pre-fill ingredient form
 */
function useScannedItemForIngredient() {
    // Get the external data from global variable
    const data = scannedExternalData;

    if (!data) {
        showError('No product data available');
        return;
    }

    // Close the scanner modal
    closeBarcodeScanner();

    // Pre-fill the Create Ingredient form
    setTimeout(() => {
        if (data.product_name) {
            const nameInput = document.getElementById('ingredientName');
            if (nameInput) nameInput.value = data.product_name;

            // Auto-generate ingredient code from name
            const codeInput = document.getElementById('ingredientCode');
            if (codeInput && !codeInput.value) {
                const code = data.product_name
                    .toUpperCase()
                    .replace(/[^A-Z0-9]/g, '')
                    .substring(0, 10);
                codeInput.value = code;
            }
        }

        if (data.brand) {
            const brandInput = document.getElementById('ingredientBrand');
            if (brandInput) brandInput.value = data.brand;
        }

        if (data.category) {
            // Try to match category
            const categorySelect = document.getElementById('ingredientCategory');
            if (categorySelect) {
                // Look for matching option
                for (let option of categorySelect.options) {
                    if (option.text.toLowerCase().includes(data.category.toLowerCase()) ||
                        data.category.toLowerCase().includes(option.text.toLowerCase())) {
                        categorySelect.value = option.value;
                        break;
                    }
                }
            }
        }

        // Store barcode if available
        if (lastScannedBarcode) {
            // We'll need to add this when saving the ingredient
            window.scannedBarcodeForIngredient = lastScannedBarcode;
        }

        showSuccess(`✅ Pre-filled with: ${data.product_name || 'scanned product'}`);
    }, 300);
}

/**
 * Add scanned item to invoice
 */
async function addScannedItemToInvoice() {
    const quantityInput = document.getElementById('barcode-quantity');
    const quantity = parseFloat(quantityInput ? quantityInput.value : 1);

    if (isNaN(quantity) || quantity <= 0) {
        showError('Please enter a valid quantity');
        return;
    }

    // Get item details from inventory match or create prompt
    try {
        const response = await fetch(`/api/inventory/detailed`);
        const items = await response.json();

        const item = items.find(i => i.barcode === lastScannedBarcode);

        if (item) {
            // Add to invoice
            if (typeof addInvoiceLineItem === 'function') {
                addInvoiceLineItem();

                // Get the last added row
                const tbody = document.getElementById('newInvoiceItemsBody');
                const lastRow = tbody ? tbody.lastElementChild : null;

                if (lastRow) {
                    // Fill in the values - using correct class names from invoice form
                    const codeInput = lastRow.querySelector('.ingredient-input');
                    const brandInput = lastRow.querySelector('.brand-input');
                    const qtyReceivedInput = lastRow.querySelector('.qty-received-input');
                    const qtyOrderedInput = lastRow.querySelector('.qty-ordered-input');
                    const unitPriceInput = lastRow.querySelector('.unit-price-input');

                    if (codeInput) codeInput.value = item.ingredient_code;
                    if (brandInput) brandInput.value = item.brand || '';
                    if (qtyReceivedInput) qtyReceivedInput.value = quantity;
                    if (qtyOrderedInput) qtyOrderedInput.value = quantity;
                    if (unitPriceInput) unitPriceInput.value = item.unit_cost || 0;

                    // Trigger calculation using the row ID from the last row
                    const rowIdMatch = lastRow.id.match(/lineItem-(\d+)/);
                    if (rowIdMatch) {
                        const rowId = parseInt(rowIdMatch[1]);
                        if (typeof calculateLineTotal === 'function') {
                            calculateLineTotal(rowId);
                        }
                    }

                    showSuccess(`✅ Added to invoice: ${item.ingredient_name}`);

                    // Close scanner
                    setTimeout(() => {
                        closeBarcodeScanner();
                    }, 1500);
                } else {
                    showError('Failed to add row to invoice');
                }
            } else {
                showError('Invoice form not available');
            }
        } else {
            showError('Item not found in inventory. Please create it first.');
        }
    } catch (error) {
        console.error('Error adding to invoice:', error);
        showError('Failed to add item to invoice');
    }
}
