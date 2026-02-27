// WONTECH Analytics Module
// Analytics loading, all widget/chart rendering, price trends, supplier perf, category spending

// Register with global registries
window.loadRegistry['analytics'] = loadAnalytics;

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
    try {
        await loadAnalyticsKPIs();
        await loadAnalyticsWidgets();
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
    const response = await fetch('/api/analytics/widgets/enabled?user_id=default');
    const result = await response.json();
    const widgets = result.widgets || [];

    const container = document.getElementById('analyticsWidgetsContainer');
    container.innerHTML = '';

    if (widgets.length === 0) {
        container.innerHTML = '<div class="widget-placeholder"><p>No widgets enabled. Click "Customize" to add widgets.</p></div>';
        return;
    }

    for (const widget of widgets) {
        const widgetElement = createWidgetElement(widget);
        container.appendChild(widgetElement);
        await renderWidget(widget);
    }

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
        // zoom state save failed silently
    }
}

function getChartZoomState(widgetKey) {
    try {
        const saved = localStorage.getItem(`chart_zoom_${widgetKey}`);
        return saved ? JSON.parse(saved) : null;
    } catch (e) {
        // zoom state load failed silently
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
    const result = await response.json();
    const widgets = result.widgets || [];
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
    const availableResult = await availableResponse.json();
    const allWidgets = availableResult.widgets || [];

    // Load enabled widgets
    const enabledResponse = await fetch('/api/analytics/widgets/enabled?user_id=default');
    const enabledResult = await enabledResponse.json();
    const enabledWidgets = enabledResult.widgets || [];

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
