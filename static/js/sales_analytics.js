// ========================================
// SALES ANALYTICS DASHBOARD
// ========================================

// Global state
let currentSalesPeriod = '7days';
let currentStartDate = null;
let currentEndDate = null;
let salesTrendChart = null;
let hourlySalesChart = null;

/**
 * Initialize Sales Analytics when tab is shown
 */
function initSalesAnalytics() {
    changeSalesPeriod('7days');
}

/**
 * Change time period for sales analytics
 */
function changeSalesPeriod(period) {
    // Update active button - scoped to sales analytics content only
    document.querySelectorAll('#sales-analytics-content .btn-time-filter').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.period === period) {
            btn.classList.add('active');
        }
    });

    // Hide custom date range
    document.getElementById('custom-date-range').style.display = 'none';

    currentSalesPeriod = period;

    // Calculate date range
    const today = new Date();
    let startDate, endDate, displayText;

    switch (period) {
        case 'today':
            startDate = endDate = formatSalesDate(today);
            displayText = "Today's Sales";
            break;

        case '7days':
            const days7Ago = new Date(today);
            days7Ago.setDate(today.getDate() - 7);
            startDate = formatSalesDate(days7Ago);
            endDate = formatSalesDate(today);
            displayText = "Last 7 Days";
            break;

        case 'week':
            const weekStart = new Date(today);
            weekStart.setDate(today.getDate() - today.getDay());
            startDate = formatSalesDate(weekStart);
            endDate = formatSalesDate(today);
            displayText = "This Week's Sales";
            break;

        case 'month':
            const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
            startDate = formatSalesDate(monthStart);
            endDate = formatSalesDate(today);
            displayText = "This Month's Sales";
            break;

        case '30days':
            const days30Ago = new Date(today);
            days30Ago.setDate(today.getDate() - 30);
            startDate = formatSalesDate(days30Ago);
            endDate = formatSalesDate(today);
            displayText = "Last 30 Days";
            break;

        case 'all':
            startDate = null;
            endDate = null;
            displayText = "All Time Sales";
            break;
    }

    currentStartDate = startDate;
    currentEndDate = endDate;

    document.getElementById('selected-period-display').textContent = displayText;

    // Load data
    loadSalesOverview();
}

/**
 * Show custom date range inputs
 */
function showCustomDateRange() {
    document.getElementById('custom-date-range').style.display = 'flex';

    // Set default values
    const today = new Date();
    const weekAgo = new Date(today);
    weekAgo.setDate(today.getDate() - 7);

    document.getElementById('sales-start-date').value = formatSalesDate(weekAgo);
    document.getElementById('sales-end-date').value = formatSalesDate(today);
}

/**
 * Apply custom date range
 */
function applyCustomDateRange() {
    const startDate = document.getElementById('sales-start-date').value;
    const endDate = document.getElementById('sales-end-date').value;
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

    currentStartDate = startDate;
    currentEndDate = endDate;

    document.querySelectorAll('#sales-analytics-content .btn-time-filter').forEach(btn => {
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

    document.getElementById('selected-period-display').textContent =
        `${startFormatted} - ${endFormatted}`;

    // Hide custom date range section after applying
    document.getElementById('custom-date-range').style.display = 'none';

    loadSalesOverview().then(() => {
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

/**
 * Load sales overview data
 */
async function loadSalesOverview() {
    try {
        console.log('=== LOADING SALES OVERVIEW ===');
        console.log('Period:', currentSalesPeriod);
        console.log('Start Date:', currentStartDate);
        console.log('End Date:', currentEndDate);

        // Build query params
        let url = '/api/analytics/sales-overview';
        const params = new URLSearchParams();
        if (currentStartDate) params.append('start_date', currentStartDate);
        if (currentEndDate) params.append('end_date', currentEndDate);
        if (params.toString()) url += '?' + params.toString();

        console.log('API URL:', url);

        const response = await fetch(url);
        const data = await response.json();

        console.log('Response data:', data);

        if (!data.success) {
            showMessage('Failed to load sales data', 'error');
            return;
        }

        // Check if there's any sales data
        if (!data.summary || data.summary.total_transactions === 0) {
            // Show empty state
            updateSummaryStats({ total_revenue: 0, total_profit: 0, total_transactions: 0, avg_transaction_value: 0 });
            updateTopProducts([]);
            updateSalesTrendChart([]);
            updateHourlySalesChart([]);
            updateQuickStats({ summary: { total_revenue: 0 } });
            return;
        }

        // Update summary stats
        updateSummaryStats(data.summary);

        // Update top products
        updateTopProducts(data.top_products);

        // Update sales trend chart
        updateSalesTrendChart(data.sales_by_date);

        // Update hourly sales chart
        updateHourlySalesChart(data.sales_by_hour);

        // Update quick stats
        updateQuickStats(data);

    } catch (error) {
        console.error('Error loading sales overview:', error);
        showMessage('Failed to load sales analytics', 'error');
    }
}

/**
 * Update summary statistics
 */
function updateSummaryStats(summary) {
    document.getElementById('sales-total-revenue').textContent =
        formatCurrency(summary.total_revenue || 0);

    document.getElementById('sales-total-profit').textContent =
        formatCurrency(summary.total_profit || 0);

    document.getElementById('sales-total-transactions').textContent =
        (summary.total_transactions || 0).toLocaleString();

    document.getElementById('sales-avg-transaction').textContent =
        formatCurrency(summary.avg_transaction_value || 0);
}

/**
 * Update top products list
 */
function updateTopProducts(products) {
    const container = document.getElementById('top-products-list');

    if (!products || products.length === 0) {
        container.innerHTML = '<p class="text-muted">No sales data available</p>';
        return;
    }

    let html = '';
    products.forEach((product, index) => {
        const rank = index + 1;
        const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `${rank}.`;

        html += `
            <div class="product-item" onclick="viewProductDetails('${escapeHtml(product.product_name)}')">
                <div>
                    <span style="font-size: 1.2em; margin-right: 10px;">${medal}</span>
                    <span class="product-item-name">${escapeHtml(product.product_name)}</span>
                </div>
                <div class="product-item-stats">
                    <div class="product-stat">
                        <span class="product-stat-label">Sold</span>
                        <span class="product-stat-value">${product.total_sold.toLocaleString()}</span>
                    </div>
                    <div class="product-stat">
                        <span class="product-stat-label">Revenue</span>
                        <span class="product-stat-value">${formatCurrency(product.total_revenue)}</span>
                    </div>
                    <div class="product-stat">
                        <span class="product-stat-label">Transactions</span>
                        <span class="product-stat-value">${product.num_transactions}</span>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Update sales trend chart
 */
function updateSalesTrendChart(salesByDate) {
    const canvas = document.getElementById('salesTrendCanvas');
    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (salesTrendChart) {
        salesTrendChart.destroy();
    }

    if (!salesByDate || salesByDate.length === 0) {
        ctx.font = '16px Arial';
        ctx.fillStyle = '#6c757d';
        ctx.textAlign = 'center';
        ctx.fillText('No sales data available', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Prepare data (reverse to show chronologically)
    const reversedData = [...salesByDate].reverse();
    const labels = reversedData.map(d => d.sale_date);
    const revenues = reversedData.map(d => d.revenue || 0);
    const profits = reversedData.map(d => d.profit || 0);

    salesTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Revenue',
                    data: revenues,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Profit',
                    data: profits,
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#28a745',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': $' + context.parsed.y.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

/**
 * Update hourly sales chart
 */
function updateHourlySalesChart(salesByHour) {
    const canvas = document.getElementById('hourlySalesCanvas');
    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (hourlySalesChart) {
        hourlySalesChart.destroy();
    }

    if (!salesByHour || salesByHour.length === 0) {
        ctx.font = '14px Arial';
        ctx.fillStyle = '#6c757d';
        ctx.textAlign = 'center';
        ctx.fillText('No hourly data', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Fill in missing hours with 0
    const hourData = new Array(24).fill(0);
    salesByHour.forEach(item => {
        const hour = parseInt(item.hour);
        if (!isNaN(hour) && hour >= 0 && hour < 24) {
            hourData[hour] = item.revenue || 0;
        }
    });

    const labels = Array.from({length: 24}, (_, i) => {
        const hour = i % 12 || 12;
        const period = i < 12 ? 'AM' : 'PM';
        return `${hour}${period}`;
    });

    hourlySalesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Revenue',
                data: hourData,
                backgroundColor: 'rgba(102, 126, 234, 0.6)',
                borderColor: '#667eea',
                borderWidth: 2,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Revenue: $' + context.parsed.y.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Update quick stats sidebar
 */
function updateQuickStats(data) {
    const { summary, top_products, sales_by_hour, highest_transaction } = data;

    // Best seller
    if (top_products && top_products.length > 0) {
        const best = top_products[0];
        document.getElementById('stat-best-seller').textContent =
            `${best.product_name} (${best.total_sold} sold)`;
    } else {
        document.getElementById('stat-best-seller').textContent = 'N/A';
    }

    // Busiest hour
    if (sales_by_hour && sales_by_hour.length > 0) {
        const busiest = sales_by_hour.reduce((max, item) =>
            item.revenue > max.revenue ? item : max, sales_by_hour[0]);
        const hour = parseInt(busiest.hour);
        const displayHour = hour % 12 || 12;
        const period = hour < 12 ? 'AM' : 'PM';
        document.getElementById('stat-busiest-hour').textContent =
            `${displayHour}:00 ${period} (${formatCurrency(busiest.revenue)})`;
    } else {
        document.getElementById('stat-busiest-hour').textContent = 'N/A';
    }

    // Highest sale
    if (highest_transaction) {
        document.getElementById('stat-highest-sale').textContent =
            `${formatCurrency(highest_transaction.revenue)} - ${highest_transaction.product_name}`;
    } else {
        document.getElementById('stat-highest-sale').textContent = 'N/A';
    }

    // Items sold
    document.getElementById('stat-items-sold').textContent =
        (summary.total_items_sold || 0).toLocaleString();

    // Discounts
    document.getElementById('stat-discounts').textContent =
        formatCurrency(summary.total_discounts || 0);
}

/**
 * View product details
 */
async function viewProductDetails(productName) {
    try {
        // Build query params
        let url = '/api/analytics/product-details?product_name=' + encodeURIComponent(productName);
        if (currentStartDate) url += '&start_date=' + currentStartDate;
        if (currentEndDate) url += '&end_date=' + currentEndDate;

        const response = await fetch(url);
        const data = await response.json();

        if (!data.success || !data.summary) {
            showMessage('No data available for this product', 'error');
            return;
        }

        displayProductDetails(data);

    } catch (error) {
        console.error('Error loading product details:', error);
        showMessage('Failed to load product details', 'error');
    }
}

/**
 * Display product details modal
 */
function displayProductDetails(data) {
    const { summary, sales_by_date, sales_by_hour, recent_sales } = data;

    document.getElementById('product-detail-title').textContent = summary.product_name;

    let html = `
        <!-- Summary Stats -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
            <div class="stat-item">
                <div style="color: #6c757d; font-size: 0.85em;">Total Sold</div>
                <div style="font-size: 1.5em; font-weight: 600; color: #667eea;">${summary.total_sold.toLocaleString()}</div>
            </div>
            <div class="stat-item">
                <div style="color: #6c757d; font-size: 0.85em;">Total Revenue</div>
                <div style="font-size: 1.5em; font-weight: 600; color: #667eea;">${formatCurrency(summary.total_revenue)}</div>
            </div>
            <div class="stat-item">
                <div style="color: #6c757d; font-size: 0.85em;">Total Profit</div>
                <div style="font-size: 1.5em; font-weight: 600; color: #28a745;">${formatCurrency(summary.total_profit)}</div>
            </div>
            <div class="stat-item">
                <div style="color: #6c757d; font-size: 0.85em;">Avg Price</div>
                <div style="font-size: 1.5em; font-weight: 600; color: #667eea;">${formatCurrency(summary.avg_sale_price)}</div>
            </div>
        </div>

        <!-- Price Range -->
        <div class="card" style="margin-bottom: 20px;">
            <h4>💵 Price Range</h4>
            <p>Min: ${formatCurrency(summary.min_sale_price || 0)} | Max: ${formatCurrency(summary.max_sale_price || 0)}</p>
            ${summary.total_discounts > 0 ? `<p style="color: #ffc107;">Total Discounts Given: ${formatCurrency(summary.total_discounts)}</p>` : ''}
        </div>

        <!-- Recent Sales -->
        <div class="card">
            <h4>📋 Recent Transactions</h4>
            <div style="max-height: 300px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead style="background: #f8f9fa; position: sticky; top: 0;">
                        <tr>
                            <th style="padding: 10px; text-align: left;">Date</th>
                            <th style="padding: 10px; text-align: left;">Time</th>
                            <th style="padding: 10px; text-align: right;">Qty</th>
                            <th style="padding: 10px; text-align: right;">Price</th>
                            <th style="padding: 10px; text-align: right;">Revenue</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    recent_sales.forEach(sale => {
        html += `
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 10px;">${sale.sale_date}</td>
                <td style="padding: 10px;">${sale.sale_time || 'N/A'}</td>
                <td style="padding: 10px; text-align: right;">${sale.quantity_sold}</td>
                <td style="padding: 10px; text-align: right;">${formatCurrency(sale.sale_price)}</td>
                <td style="padding: 10px; text-align: right; font-weight: 600;">${formatCurrency(sale.revenue)}</td>
            </tr>
        `;
    });

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    document.getElementById('product-detail-content').innerHTML = html;
    document.getElementById('product-detail-modal').style.display = 'flex';
}

/**
 * Close product detail modal
 */
function closeProductDetail() {
    document.getElementById('product-detail-modal').style.display = 'none';
}

/**
 * Format date to YYYY-MM-DD for sales analytics
 * Handles both Date objects and date strings
 */
function formatSalesDate(date) {
    if (!date) return '-';

    // If it's already a string in YYYY-MM-DD format, return as is
    if (typeof date === 'string') {
        return date;
    }

    // If it's a Date object, format it
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Export sales records to CSV for current date range
 */
async function exportSalesRecords() {
    try {
        const exportBtn = event.target;
        const originalText = exportBtn.innerHTML;

        // Show loading state
        exportBtn.innerHTML = '⏳ Exporting...';
        exportBtn.disabled = true;

        // Build API URL with date filters
        let url = '/api/sales/history';
        const params = new URLSearchParams();

        if (currentStartDate) params.append('start_date', currentStartDate);
        if (currentEndDate) params.append('end_date', currentEndDate);
        params.append('per_page', '10000'); // Get all records (up to 10k)

        if (params.toString()) url += '?' + params.toString();

        // Fetch sales data
        const response = await fetch(url);
        const result = await response.json();

        if (!result.data || result.data.length === 0) {
            showMessage('No sales records found for the selected period', 'warning');
            exportBtn.innerHTML = originalText;
            exportBtn.disabled = false;
            return;
        }

        const salesData = result.data;

        // Convert to CSV
        const headers = [
            'Sale Date',
            'Sale Time',
            'Product Name',
            'Quantity Sold',
            'Original Price',
            'Sale Price',
            'Discount Amount',
            'Discount %',
            'Revenue',
            'Cost of Goods',
            'Gross Profit',
            'Processed Date'
        ];

        // Create CSV content
        let csvContent = headers.join(',') + '\n';

        salesData.forEach(record => {
            const row = [
                record.sale_date || '',
                record.sale_time || '',
                `"${(record.product_name || '').replace(/"/g, '""')}"`, // Escape quotes
                record.quantity_sold || 0,
                (record.original_price || 0).toFixed(2),
                (record.sale_price || 0).toFixed(2),
                (record.discount_amount || 0).toFixed(2),
                (record.discount_percent || 0).toFixed(1),
                (record.revenue || 0).toFixed(2),
                (record.cost_of_goods || 0).toFixed(2),
                (record.gross_profit || 0).toFixed(2),
                record.processed_date || ''
            ];
            csvContent += row.join(',') + '\n';
        });

        // Create filename with date range
        let filename = 'sales_records';
        if (currentStartDate && currentEndDate) {
            filename += `_${currentStartDate}_to_${currentEndDate}`;
        } else if (currentStartDate) {
            filename += `_from_${currentStartDate}`;
        } else if (currentEndDate) {
            filename += `_until_${currentEndDate}`;
        } else {
            filename += '_all_time';
        }
        filename += '.csv';

        // Open share modal for email/text/download options
        if (typeof shareCSV === 'function') {
            shareCSV(csvContent, filename);
        } else {
            // Fallback to direct download if share.js not loaded
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const downloadUrl = URL.createObjectURL(blob);

            link.setAttribute('href', downloadUrl);
            link.setAttribute('download', filename);
            link.style.display = 'none';

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            URL.revokeObjectURL(downloadUrl);
        }

        // Show success message
        showMessage(`✅ ${salesData.length} sales records ready to share`, 'success');

        // Restore button
        exportBtn.innerHTML = originalText;
        exportBtn.disabled = false;

    } catch (error) {
        console.error('Error exporting sales records:', error);
        showMessage('Failed to export sales records', 'error');

        // Restore button
        const exportBtn = event.target;
        exportBtn.innerHTML = '📊 Export CSV';
        exportBtn.disabled = false;
    }
}

console.log('%c✓ Sales Analytics Ready', 'color: green; font-weight: bold; font-size: 14px');
