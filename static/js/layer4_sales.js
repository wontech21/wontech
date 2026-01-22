// ========================================
// LAYER 4: SALES PROCESSING
// ========================================

// Global state for sales processing
let currentSalesPreview = null;
let currentSalesPage = 1;
let salesPerPage = 20;


/**
 * Handle CSV file upload
 */
function handleCsvFileUpload(event) {
    const file = event.target.files[0];

    if (!file) {
        return;
    }

    // Check if it's a CSV file
    if (!file.name.endsWith('.csv')) {
        showMessage('Please upload a CSV file', 'error');
        event.target.value = ''; // Clear the input
        return;
    }

    // Show file name and clear button
    document.getElementById('uploadedFileName').textContent = `✓ ${file.name}`;
    document.getElementById('clearUploadBtn').style.display = 'inline-block';

    // Read the file
    const reader = new FileReader();

    reader.onload = function(e) {
        const csvContent = e.target.result;

        // Populate the textarea with the file content
        document.getElementById('salesCsvText').value = csvContent;

        showMessage(`CSV file "${file.name}" loaded successfully! Click "Parse & Preview" to continue.`, 'success');
    };

    reader.onerror = function() {
        showMessage('Error reading file. Please try again.', 'error');
        document.getElementById('uploadedFileName').textContent = '';
        document.getElementById('clearUploadBtn').style.display = 'none';
        event.target.value = ''; // Clear the input
    };

    reader.readAsText(file);
}

/**
 * Clear CSV file upload
 */
function clearCsvUpload() {
    // Clear the file input
    document.getElementById('csvFileUpload').value = '';

    // Clear the textarea
    document.getElementById('salesCsvText').value = '';

    // Hide file name and clear button
    document.getElementById('uploadedFileName').textContent = '';
    document.getElementById('clearUploadBtn').style.display = 'none';

    showMessage('CSV cleared', 'info');
}


/**
 * Parse CSV text and preview sales
 */
async function parseSalesCSV() {
    console.log('📝 parseSalesCSV called');

    const csvTextElement = document.getElementById('salesCsvText');
    const saleDateElement = document.getElementById('saleDate');
    const saleTimeElement = document.getElementById('saleTime');

    if (!csvTextElement) {
        console.error('salesCsvText element not found!');
        showMessage('Error: CSV text field not found', 'error');
        return;
    }

    const csvText = csvTextElement.value.trim();
    const saleDate = saleDateElement ? (saleDateElement.value || new Date().toISOString().split('T')[0]) : new Date().toISOString().split('T')[0];
    const saleTime = saleTimeElement ? saleTimeElement.value : '';

    if (!csvText) {
        console.warn('No CSV text entered');
        showMessage('Please enter CSV data', 'error');
        return;
    }

    console.log(`Parsing CSV (${csvText.length} chars), date: ${saleDate}, time: ${saleTime}`);

    try {
        // First, parse the CSV
        const parseResponse = await fetch('/api/sales/parse-csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ csv_text: csvText })
        });

        const parseResult = await parseResponse.json();
        console.log('Parse result:', parseResult);

        if (!parseResult.success) {
            showMessage(`CSV parsing failed: ${parseResult.error}`, 'error');
            return;
        }

        const salesData = parseResult.sales_data;

        if (salesData.length === 0) {
            showMessage('No sales data found in CSV', 'warning');
            return;
        }

        showMessage(`Parsed ${salesData.length} sales. Calculating preview...`, 'info');

        // Now get the preview
        const previewResponse = await fetch('/api/sales/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sale_date: saleDate,
                sales_data: salesData
            })
        });

        const previewResult = await previewResponse.json();

        if (!previewResult.success) {
            showMessage(`Preview failed: ${previewResult.error}`, 'error');
            return;
        }

        // Store preview for later apply
        currentSalesPreview = {
            sale_date: saleDate,
            sale_time: saleTime,
            sales_data: salesData,
            preview: previewResult.preview
        };

        // Display the preview
        displaySalesPreview(previewResult.preview);

    } catch (error) {
        console.error('Error parsing/previewing sales:', error);
        showMessage('Failed to process sales data', 'error');
    }
}

/**
 * Display sales preview
 */
function displaySalesPreview(preview) {
    console.log('🎨 displaySalesPreview called', preview);
    const previewSection = document.getElementById('preview-section');
    const summaryDiv = document.getElementById('preview-summary');
    const detailsDiv = document.getElementById('preview-details');
    const warningsDiv = document.getElementById('preview-warnings');

    if (!previewSection) {
        console.error('preview-section element not found!');
        return;
    }

    // Show preview section
    previewSection.style.display = 'block';
    console.log('Preview section shown');

    // Summary cards
    const totals = preview.totals;
    summaryDiv.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
            <div class="summary-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 0.9em; opacity: 0.9;">💰 Total Revenue</div>
                <div style="font-size: 1.8em; font-weight: bold; margin-top: 5px;">
                    ${formatCurrency(totals.revenue)}
                </div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                 color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 0.9em; opacity: 0.9;">💵 Total Cost</div>
                <div style="font-size: 1.8em; font-weight: bold; margin-top: 5px;">
                    ${formatCurrency(totals.cost)}
                </div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                 color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 0.9em; opacity: 0.9;">📊 Gross Profit</div>
                <div style="font-size: 1.8em; font-weight: bold; margin-top: 5px;">
                    ${formatCurrency(totals.profit)}
                </div>
            </div>
        </div>
    `;

    // Details
    let detailsHTML = '';

    // Matched products
    if (preview.matched.length > 0) {
        detailsHTML += '<h4 style="color: #28a745; margin-top: 20px;">✅ Matched Products</h4>';
        preview.matched.forEach(product => {
            detailsHTML += `
                <div style="border: 2px solid #28a745; border-radius: 10px; padding: 15px; margin: 10px 0;
                     background: linear-gradient(135deg, rgba(40, 167, 69, 0.05) 0%, rgba(40, 167, 69, 0.02) 100%);">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <strong style="font-size: 1.1em;">${product.product_name}</strong>
                        <span style="color: #667eea; font-weight: bold;">× ${product.quantity_sold}</span>
                    </div>
                    ${product.discount_amount > 0 ? `
                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin-bottom: 10px;">
                        <div style="color: #856404; font-size: 0.95em;">
                            <div style="margin-bottom: 5px;">
                                <strong>🏷️ Adjusted Pricing:</strong>
                            </div>
                            <div style="display: grid; grid-template-columns: auto auto; gap: 5px 15px; font-size: 0.9em;">
                                <span>Database Price:</span>
                                <span><s>${formatCurrency(product.original_price)}</s></span>
                                <span>Actual Sale Price:</span>
                                <span style="font-weight: bold; color: #28a745;">${formatCurrency(product.sale_price)}</span>
                                <span>Discount:</span>
                                <span style="font-weight: bold;">${formatCurrency(product.discount_amount)} (${product.discount_percent.toFixed(1)}% off)</span>
                            </div>
                        </div>
                    </div>
                    ` : ''}
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px;">
                        <div>
                            <small style="color: #6c757d;">Revenue</small><br>
                            <strong>${formatCurrency(product.revenue)}</strong>
                            ${product.discount_amount > 0 ?
                                `<br><small style="color: #666; font-size: 0.8em;">${formatCurrency(product.sale_price)} × ${product.quantity_sold}</small>` :
                                `<br><small style="color: #666; font-size: 0.8em;">${formatCurrency(product.original_price)} × ${product.quantity_sold}</small>`
                            }
                        </div>
                        <div>
                            <small style="color: #6c757d;">Cost</small><br>
                            <strong>${formatCurrency(product.cost)}</strong>
                        </div>
                        <div>
                            <small style="color: #6c757d;">Profit</small><br>
                            <strong style="color: #28a745;">${formatCurrency(product.profit)}</strong>
                            <br><small style="color: #666; font-size: 0.8em;">Revenue - Cost</small>
                        </div>
                    </div>
                    <details style="margin-top: 10px;">
                        <summary style="cursor: pointer; color: #667eea; font-weight: 600;">
                            📋 Ingredient Deductions (${product.ingredients.length})
                        </summary>
                        <div style="margin-top: 10px; padding-left: 20px;">
                            ${product.ingredients.map(ing => `
                                <div style="display: flex; justify-content: space-between; padding: 5px 0;
                                     border-bottom: 1px solid #e9ecef;">
                                    <span>${ing.ingredient_name}</span>
                                    <span style="color: #dc3545; font-weight: 600;">
                                        -${ing.deduction.toFixed(2)} ${ing.unit}
                                    </span>
                                    <span style="color: #6c757d; font-size: 0.9em;">
                                        (${ing.current_qty.toFixed(2)} → ${ing.new_qty.toFixed(2)} ${ing.unit})
                                    </span>
                                </div>
                            `).join('')}
                        </div>
                    </details>
                </div>
            `;
        });
    }

    // Unmatched products
    if (preview.unmatched.length > 0) {
        detailsHTML += '<h4 style="color: #dc3545; margin-top: 20px;">❌ Unmatched Products</h4>';
        preview.unmatched.forEach(product => {
            detailsHTML += `
                <div style="border: 2px solid #dc3545; border-radius: 10px; padding: 15px; margin: 10px 0;
                     background: rgba(220, 53, 69, 0.05);">
                    <strong>${product.product_name}</strong> × ${product.quantity}
                    <br><small style="color: #6c757d;">${product.reason}</small>
                </div>
            `;
        });
    }

    detailsDiv.innerHTML = detailsHTML;

    // Warnings
    if (preview.warnings.length > 0) {
        warningsDiv.innerHTML = `
            <div style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 10px; padding: 15px; margin-top: 15px;">
                <h4 style="color: #856404; margin: 0 0 10px 0;">⚠️ Warnings</h4>
                ${preview.warnings.map(warning => `
                    <div style="padding: 5px 0; color: #856404;">
                        ${warning}
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        warningsDiv.innerHTML = '';
    }

    // Scroll to preview
    previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Apply sales to inventory
 */
async function applySales() {
    if (!currentSalesPreview) {
        showMessage('No preview available', 'error');
        return;
    }

    if (!confirm('Apply these sales to inventory?\n\nThis will deduct ingredients and cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch('/api/sales/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sale_date: currentSalesPreview.sale_date,
                sale_time: currentSalesPreview.sale_time,
                sales_data: currentSalesPreview.sales_data
            })
        });

        const result = await response.json();

        if (!result.success) {
            showMessage(`Failed to apply sales: ${result.error}`, 'error');
            return;
        }

        const summary = result.summary;
        showMessage(
            `✓ Successfully processed ${summary.sales_processed} sales!\n` +
            `Revenue: ${formatCurrency(summary.total_revenue)}\n` +
            `Profit: ${formatCurrency(summary.total_profit)}`,
            'success'
        );

        // Clear preview
        cancelPreview();

        // Clear inputs
        document.getElementById('salesCsvText').value = '';

        // Reload history
        loadSalesHistory();

        // Refresh inventory if on that tab
        if (currentTab === 'inventory') {
            loadInventory();
        }

    } catch (error) {
        console.error('Error applying sales:', error);
        showMessage('Failed to apply sales', 'error');
    }
}

/**
 * Cancel preview
 */
function cancelPreview() {
    currentSalesPreview = null;
    document.getElementById('preview-section').style.display = 'none';
}

/**
 * Load sales history with pagination
 */
async function loadSalesHistory(page = 1) {
    const container = document.getElementById('sales-history-container');

    if (!container) return;

    try {
        container.innerHTML = '<div class="loading">Loading sales history...</div>';

        currentSalesPage = page;
        const response = await fetch(`/api/sales/history?page=${page}&per_page=${salesPerPage}`);
        const result = await response.json();

        if (!result.data || result.data.length === 0) {
            container.innerHTML = '<p class="text-muted" style="text-align: center; padding: 40px;">No sales processed yet</p>';
            return;
        }

        const history = result.data;
        const pagination = result.pagination;

        // Display as table
        let html = `
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                        <th style="padding: 12px; text-align: left;">Date</th>
                        <th style="padding: 12px; text-align: left;">Time</th>
                        <th style="padding: 12px; text-align: left;">Product</th>
                        <th style="padding: 12px; text-align: right;">Qty</th>
                        <th style="padding: 12px; text-align: right;">Orig. Price</th>
                        <th style="padding: 12px; text-align: right;">Sale Price</th>
                        <th style="padding: 12px; text-align: right;">Discount</th>
                        <th style="padding: 12px; text-align: right;">Revenue</th>
                        <th style="padding: 12px; text-align: right;">Cost</th>
                        <th style="padding: 12px; text-align: right;">Profit</th>
                    </tr>
                </thead>
                <tbody>
        `;

        history.forEach((sale, index) => {
            const bgColor = index % 2 === 0 ? '#ffffff' : '#f8f9fa';
            const displayTime = sale.sale_time || '--:--:--';
            const originalPrice = sale.original_price || 0;
            const salePrice = sale.sale_price || originalPrice;
            const discountAmount = sale.discount_amount || 0;
            const discountPercent = sale.discount_percent || 0;

            const discountDisplay = discountAmount > 0
                ? `${formatCurrency(discountAmount)} (${discountPercent.toFixed(0)}%)`
                : '-';

            html += `
                <tr style="background: ${bgColor};">
                    <td style="padding: 10px;">${sale.sale_date}</td>
                    <td style="padding: 10px;">${displayTime}</td>
                    <td style="padding: 10px;">${sale.product_name}</td>
                    <td style="padding: 10px; text-align: right;">${sale.quantity_sold}</td>
                    <td style="padding: 10px; text-align: right;">${formatCurrency(originalPrice)}</td>
                    <td style="padding: 10px; text-align: right; ${discountAmount > 0 ? 'color: #28a745; font-weight: bold;' : ''}">${formatCurrency(salePrice)}</td>
                    <td style="padding: 10px; text-align: right; color: #ffc107;">${discountDisplay}</td>
                    <td style="padding: 10px; text-align: right;">${formatCurrency(sale.revenue)}</td>
                    <td style="padding: 10px; text-align: right;">${formatCurrency(sale.cost_of_goods)}</td>
                    <td style="padding: 10px; text-align: right; color: #28a745; font-weight: bold;">
                        ${formatCurrency(sale.gross_profit)}
                    </td>
                </tr>
            `;
        });

        html += '</tbody></table>';

        // Add pagination controls
        if (pagination.total_pages > 1) {
            html += renderPaginationControls(pagination);
        }

        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading sales history:', error);
        container.innerHTML = '<p class="text-danger">Failed to load sales history</p>';
    }
}

/**
 * Render pagination controls
 */
function renderPaginationControls(pagination) {
    const { page, total_pages, total_records, per_page } = pagination;
    const startRecord = (page - 1) * per_page + 1;
    const endRecord = Math.min(page * per_page, total_records);

    let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <div style="color: #6c757d; font-size: 0.9em;">
                Showing ${startRecord}-${endRecord} of ${total_records} sales
            </div>
            <div style="display: flex; gap: 5px;">
    `;

    // Previous button
    if (page > 1) {
        html += `
            <button onclick="loadSalesHistory(${page - 1})"
                    style="padding: 8px 12px; background: #667eea; color: white; border: none;
                           border-radius: 5px; cursor: pointer; font-weight: 600;">
                ← Previous
            </button>
        `;
    } else {
        html += `
            <button disabled
                    style="padding: 8px 12px; background: #e9ecef; color: #6c757d; border: none;
                           border-radius: 5px; cursor: not-allowed;">
                ← Previous
            </button>
        `;
    }

    // Page numbers
    const maxPages = 5;
    let startPage = Math.max(1, page - Math.floor(maxPages / 2));
    let endPage = Math.min(total_pages, startPage + maxPages - 1);

    if (endPage - startPage < maxPages - 1) {
        startPage = Math.max(1, endPage - maxPages + 1);
    }

    if (startPage > 1) {
        html += `
            <button onclick="loadSalesHistory(1)"
                    style="padding: 8px 12px; background: white; color: #667eea; border: 2px solid #667eea;
                           border-radius: 5px; cursor: pointer; font-weight: 600;">
                1
            </button>
        `;
        if (startPage > 2) {
            html += `<span style="padding: 8px;">...</span>`;
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        if (i === page) {
            html += `
                <button style="padding: 8px 12px; background: #667eea; color: white; border: none;
                               border-radius: 5px; font-weight: 600;">
                    ${i}
                </button>
            `;
        } else {
            html += `
                <button onclick="loadSalesHistory(${i})"
                        style="padding: 8px 12px; background: white; color: #667eea; border: 2px solid #667eea;
                               border-radius: 5px; cursor: pointer; font-weight: 600;">
                    ${i}
                </button>
            `;
        }
    }

    if (endPage < total_pages) {
        if (endPage < total_pages - 1) {
            html += `<span style="padding: 8px;">...</span>`;
        }
        html += `
            <button onclick="loadSalesHistory(${total_pages})"
                    style="padding: 8px 12px; background: white; color: #667eea; border: 2px solid #667eea;
                           border-radius: 5px; cursor: pointer; font-weight: 600;">
                ${total_pages}
            </button>
        `;
    }

    // Next button
    if (page < total_pages) {
        html += `
            <button onclick="loadSalesHistory(${page + 1})"
                    style="padding: 8px 12px; background: #667eea; color: white; border: none;
                           border-radius: 5px; cursor: pointer; font-weight: 600;">
                Next →
            </button>
        `;
    } else {
        html += `
            <button disabled
                    style="padding: 8px 12px; background: #e9ecef; color: #6c757d; border: none;
                           border-radius: 5px; cursor: not-allowed;">
                Next →
            </button>
        `;
    }

    html += `
            </div>
        </div>
    `;

    return html;
}

/**
 * Initialize sales tab
 */
function initializeSalesTab() {
    // Set today's date and current time
    const now = new Date();
    const today = now.toISOString().split('T')[0];
    const currentTime = now.toTimeString().split(' ')[0]; // HH:MM:SS format

    const saleDateInput = document.getElementById('saleDate');
    const saleTimeInput = document.getElementById('saleTime');

    if (saleDateInput) saleDateInput.value = today;
    if (saleTimeInput) saleTimeInput.value = currentTime;

    // Load sales history
    loadSalesHistory();

    console.log('%c✓ Sales tab initialized', 'color: blue; font-weight: bold;');
}

// Initialize when sales tab is opened
const originalShowTab = window.showTab;
window.showTab = function(tabName) {
    originalShowTab(tabName);
    if (tabName === 'sales') {
        initializeSalesTab();
    }
};

// Log Layer 4 functions available
console.log('%c✓ Layer 4: Sales Processing Ready', 'color: purple; font-weight: bold; font-size: 14px');
console.log('Available functions:');
console.log('  - parseSalesCSV()');
console.log('  - applySales()');
console.log('  - loadSalesHistory()');
console.log('  - displaySalesPreview()');
console.log('  - cancelPreview()');
