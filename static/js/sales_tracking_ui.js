
// ========== SALES TRACKING FUNCTIONS ==========

// Handle file selection display
document.addEventListener('DOMContentLoaded', function() {
    const salesFileInput = document.getElementById('salesFile');
    if (salesFileInput) {
        salesFileInput.addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name || 'Choose CSV File...';
            document.getElementById('fileName').textContent = fileName;
        });
    }
});

// Handle sales upload form submission
async function setupSalesUploadForm() {
    const form = document.getElementById('salesUploadForm');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const fileInput = document.getElementById('salesFile');
        const file = fileInput.files[0];

        if (!file) {
            showMessage('Please select a CSV file', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        // Show progress
        document.getElementById('uploadProgress').style.display = 'block';
        document.getElementById('uploadResult').innerHTML = '';
        document.getElementById('progressFill').style.width = '50%';
        document.getElementById('uploadStatus').textContent = 'Processing sales data...';

        try {
            const response = await fetch('/api/sales/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            // Complete progress
            document.getElementById('progressFill').style.width = '100%';
            document.getElementById('uploadStatus').textContent = 'Complete!';

            setTimeout(() => {
                document.getElementById('uploadProgress').style.display = 'none';
            }, 1000);

            // Display results
            displaySalesUploadResult(result);

            // Reset form
            form.reset();
            document.getElementById('fileName').textContent = 'Choose CSV File...';

            // Refresh data
            setTimeout(() => {
                loadRecentSales();
                loadHeaderStats();
            }, 1500);

        } catch (error) {
            console.error('Upload error:', error);
            document.getElementById('uploadProgress').style.display = 'none';
            document.getElementById('uploadResult').innerHTML = `
                <div class="upload-result-error">
                    <h4>❌ Upload Failed</h4>
                    <p>An error occurred during upload</p>
                </div>
            `;
        }
    });
}

function displaySalesUploadResult(result) {
    const container = document.getElementById('uploadResult');

    if (!result.success && result.error) {
        container.innerHTML = `
            <div class="upload-result-error">
                <h4>❌ Upload Failed</h4>
                <p>${result.error}</p>
            </div>
        `;
        return;
    }

    const hasErrors = result.errors_count > 0;
    const resultClass = hasErrors ? 'upload-result-error' : 'upload-result-success';

    let html = `
        <div class="${resultClass}">
            <h4>${hasErrors ? '⚠️' : '✅'} Upload Complete</h4>

            <div class="upload-result-summary">
                <div class="upload-result-stat">
                    <span class="stat-value">${result.processed}</span>
                    <span class="stat-label">Sales Processed</span>
                </div>
                <div class="upload-result-stat">
                    <span class="stat-value">${result.summary?.total_items_sold || 0}</span>
                    <span class="stat-label">Items Sold</span>
                </div>
                <div class="upload-result-stat">
                    <span class="stat-value">$${result.summary?.total_revenue?.toFixed(2) || '0.00'}</span>
                    <span class="stat-label">Revenue</span>
                </div>
                <div class="upload-result-stat">
                    <span class="stat-value">${result.errors_count}</span>
                    <span class="stat-label">Errors</span>
                </div>
            </div>
    `;

    // Show processed sales
    if (result.sales && result.sales.length > 0) {
        html += `
            <div class="sales-deduction-list">
                <h5>Processed Sales & Inventory Deductions:</h5>
        `;

        result.sales.forEach(sale => {
            html += `
                <div class="sales-deduction-item">
                    <div class="product-name">
                        ${sale.quantity_sold}x ${sale.product_name} - $${sale.revenue.toFixed(2)}
                    </div>
                    <div class="deduction-details">
                        ${sale.deductions.join('<br>')}
                    </div>
                </div>
            `;
        });

        html += `</div>`;
    }

    // Show errors
    if (result.errors && result.errors.length > 0) {
        html += `
            <div class="error-list">
                <h5>Errors (${result.errors.length}):</h5>
        `;

        result.errors.slice(0, 10).forEach(error => {
            html += `<div class="error-list-item">⚠️ ${error}</div>`;
        });

        if (result.errors.length > 10) {
            html += `<div class="error-list-item">...and ${result.errors.length - 10} more errors</div>`;
        }

        html += `</div>`;
    }

    html += `</div>`;
    container.innerHTML = html;
}

async function loadRecentSales() {
    const container = document.getElementById('recentSalesContainer');
    if (!container) return;

    try {
        const response = await fetch('/api/sales/summary?days=7');
        const data = await response.json();

        if (!data.recent_sales || data.recent_sales.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #6c757d; padding: 40px;">No recent sales recorded</p>';
            return;
        }

        let html = `
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>Date/Time</th>
                        <th>Product</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.recent_sales.forEach(sale => {
            // Extract quantity from details
            const match = sale.details.match(/Sold ([\d.]+) x/);
            const qty = match ? match[1] : '';

            html += `
                <tr>
                    <td>${formatDateTime(sale.timestamp)}</td>
                    <td><strong>${sale.product_name}</strong> ${qty ? `(${qty})` : ''}</td>
                    <td style="font-size: 0.9em; color: #6c757d;">${sale.details}</td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading recent sales:', error);
        container.innerHTML = '<p style="text-align: center; color: #dc3545;">Error loading sales data</p>';
    }
}

function downloadSampleSalesCSV() {
    const today = new Date().toISOString().split('T')[0];
    const csvContent = `product_code,product_name,quantity_sold,sale_date,sale_price
PIZZA-CHZ-S,"Cheese Pizza - Small (10")",2,${today},9.99
PIZZA-CHZ-M,"Cheese Pizza - Medium (14")",5,${today},13.99
PIZZA-CHZ-L,"Cheese Pizza - Large (16")",3,${today},16.99
PIZZA-PEP-M,"Pepperoni Pizza - Medium (14")",4,${today},15.99
PIZZA-SUP-L,"Supreme Pizza - Large (16")",2,${today},20.99`;

    const fileName = `sample_sales_${today}.csv`;

    // Open share modal for email/text/download options
    if (typeof shareCSV === 'function') {
        shareCSV(csvContent, fileName);
    } else {
        // Fallback to direct download if share.js not loaded
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    showMessage('Sample CSV ready', 'success');
}
