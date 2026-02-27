/**
 * Reports & Tools — Frontend Logic
 * Reports catalog + MOR Builder + File History
 */

let allReports = {};
let allCategories = [];
let currentCategory = 'all';
let currentReportKey = null;

// ==========================================
// TAB NAVIGATION
// ==========================================

function switchMainTab(tab, btn) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.main-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    if (btn) btn.classList.add('active');

    if (tab === 'file-history') loadFileHistory();
}

// ==========================================
// REPORT CATALOG (existing)
// ==========================================

async function loadReportCatalog() {
    const grid = document.getElementById('reportGrid');
    grid.innerHTML = '<div class="reports-loading"><div class="reports-spinner"></div><span>Loading reports...</span></div>';

    try {
        const res = await fetch('/api/reports/catalog');
        const data = await res.json();

        if (!data.success) {
            grid.innerHTML = '<div class="reports-empty">Failed to load reports.</div>';
            return;
        }

        allCategories = data.categories || [];
        allReports = data.reports || {};

        renderCategoryPills();
        renderReportCards();
        document.getElementById('reportCount').textContent = data.total + ' reports available';
    } catch (err) {
        console.error('Error loading catalog:', err);
        grid.innerHTML = '<div class="reports-empty">Unable to load reports. Please try again.</div>';
    }
}

function renderCategoryPills() {
    const container = document.getElementById('categoryPills');
    const icons = { costs: '\u{1F4B2}', inventory: '\u{1F4E6}', sales: '\u{1F4C8}', labor: '\u{1F465}', operations: '\u{2699}\uFE0F' };

    let html = '<button class="category-pill active" onclick="filterByCategory(\'all\', this)">All</button>';
    allCategories.forEach(cat => {
        const icon = icons[cat] || '\u{1F4CB}';
        const label = cat.charAt(0).toUpperCase() + cat.slice(1);
        html += `<button class="category-pill" onclick="filterByCategory('${cat}', this)">${icon} ${label}</button>`;
    });
    container.innerHTML = html;
}

function renderReportCards(filter = '') {
    const grid = document.getElementById('reportGrid');
    const icons = { costs: '\u{1F4B2}', inventory: '\u{1F4E6}', sales: '\u{1F4C8}', labor: '\u{1F465}', operations: '\u{2699}\uFE0F' };

    let cards = [];
    const cats = currentCategory === 'all' ? allCategories : [currentCategory];

    cats.forEach(cat => {
        (allReports[cat] || []).forEach(report => {
            if (filter && !report.name.toLowerCase().includes(filter) &&
                !report.description.toLowerCase().includes(filter)) return;
            const icon = icons[cat] || '\u{1F4CB}';
            const catLabel = cat.charAt(0).toUpperCase() + cat.slice(1);
            cards.push(`
                <div class="report-card" onclick="openReport('${report.key}')">
                    <div class="report-card-header">
                        <span class="report-category-badge badge-${cat}">${icon} ${catLabel}</span>
                        <span class="report-arrow">&rarr;</span>
                    </div>
                    <h3 class="report-card-title">${report.name}</h3>
                    <p class="report-card-desc">${report.description}</p>
                    <div class="report-card-formats">
                        <span class="format-icon">CSV</span>
                        <span class="format-icon">XLSX</span>
                        <span class="format-icon">PDF</span>
                    </div>
                </div>
            `);
        });
    });

    grid.innerHTML = cards.length === 0
        ? '<div class="reports-empty">No reports match your search.</div>'
        : cards.join('');
}

function filterByCategory(cat, btn) {
    currentCategory = cat;
    document.querySelectorAll('.category-pill').forEach(p => p.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderReportCards(document.getElementById('reportSearch').value.toLowerCase());
}

function searchReports() {
    renderReportCards(document.getElementById('reportSearch').value.toLowerCase());
}

// ==========================================
// REPORT DETAIL MODAL (existing)
// ==========================================

async function openReport(key) {
    currentReportKey = key;
    const modal = document.getElementById('reportModal');
    const title = document.getElementById('modalReportTitle');
    const desc = document.getElementById('modalReportDesc');
    const preview = document.getElementById('modalPreviewBody');
    const previewHead = document.getElementById('modalPreviewHead');

    let reportMeta = null;
    for (const cat of allCategories) {
        const found = (allReports[cat] || []).find(r => r.key === key);
        if (found) { reportMeta = found; break; }
    }

    title.textContent = reportMeta ? reportMeta.name : key;
    desc.textContent = reportMeta ? reportMeta.description : '';
    previewHead.innerHTML = '';
    preview.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:32px;color:#9ca3af;">Loading preview...</td></tr>';
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    try {
        const dateFrom = document.getElementById('modalDateFrom').value;
        const dateTo = document.getElementById('modalDateTo').value;
        let url = `/api/reports/${key}/preview`;
        const params = [];
        if (dateFrom) params.push('date_from=' + dateFrom);
        if (dateTo) params.push('date_to=' + dateTo);
        if (params.length) url += '?' + params.join('&');

        const res = await fetch(url);
        const data = await res.json();

        if (!data.success) {
            preview.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:32px;color:#ef4444;">${data.error || 'Failed to load'}</td></tr>`;
            return;
        }

        previewHead.innerHTML = '<tr>' + data.headers.map(h => `<th>${h}</th>`).join('') + '</tr>';

        if (data.rows.length === 0) {
            preview.innerHTML = '<tr><td colspan="' + data.headers.length + '" style="text-align:center;padding:32px;color:#9ca3af;">No data for the selected period.</td></tr>';
        } else {
            preview.innerHTML = data.rows.map(row =>
                '<tr>' + row.map(cell => `<td>${cell != null ? cell : ''}</td>`).join('') + '</tr>'
            ).join('');
        }

        document.getElementById('modalRowCount').textContent =
            data.truncated ? `Showing 50 of ${data.total_rows} rows` : `${data.total_rows} rows`;
    } catch (err) {
        console.error('Error loading preview:', err);
        preview.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:32px;color:#ef4444;">Error loading preview.</td></tr>';
    }
}

function closeReportModal() {
    document.getElementById('reportModal').classList.remove('active');
    document.body.style.overflow = '';
    currentReportKey = null;
}

function refreshPreview() {
    if (currentReportKey) openReport(currentReportKey);
}

// ==========================================
// DOWNLOAD (existing)
// ==========================================

function downloadReport(format) {
    if (!currentReportKey) return;

    const dateFrom = document.getElementById('modalDateFrom').value;
    const dateTo = document.getElementById('modalDateTo').value;
    const params = ['format=' + format];
    if (dateFrom) params.push('date_from=' + dateFrom);
    if (dateTo) params.push('date_to=' + dateTo);

    const btn = event.target;
    const origText = btn.textContent;
    btn.textContent = 'Generating...';
    btn.disabled = true;

    fetch(`/api/reports/${currentReportKey}/generate?${params.join('&')}`)
        .then(res => {
            if (!res.ok) return res.json().then(d => { throw new Error(d.error || 'Download failed'); });
            return res.blob();
        })
        .then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `${currentReportKey}.${format}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(a.href);
        })
        .catch(err => {
            alert(err.message || 'Download failed');
            console.error('Download error:', err);
        })
        .finally(() => {
            btn.textContent = origText;
            btn.disabled = false;
        });
}

// ==========================================
// REPORT HISTORY (existing)
// ==========================================

async function loadReportHistory() {
    const list = document.getElementById('historyList');
    if (!list) return;

    try {
        const res = await fetch('/api/reports/history?limit=10');
        const data = await res.json();

        if (!data.success || !data.history.length) {
            list.innerHTML = '<div style="color:#9ca3af;font-size:14px;padding:12px;">No export history yet.</div>';
            return;
        }

        list.innerHTML = data.history.map(h => {
            const ago = timeAgo(h.exported_at);
            const fmt = (h.format || 'csv').toUpperCase();
            return `<div class="history-item">
                <span class="history-report">${h.report_key}</span>
                <span class="history-format">${fmt}</span>
                <span class="history-by">${h.exported_by}</span>
                <span class="history-time">${ago}</span>
            </div>`;
        }).join('');
    } catch (err) {
        console.error('Error loading history:', err);
    }
}

function timeAgo(dateStr) {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return mins + 'm ago';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    return Math.floor(hrs / 24) + 'd ago';
}


// Drag-and-drop for upload zones
function setupUploadZone(zoneId, inputId) {
    const zone = document.getElementById(zoneId);
    if (!zone) return;

    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const input = document.getElementById(inputId);
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            input.dispatchEvent(new Event('change'));
        }
    });
}


// ==========================================
// MOR BUILDER
// ==========================================

function handleMorBankStmt(input) {
    const file = input.files[0];
    if (!file) return;
    document.getElementById('morBankStmtName').textContent = file.name;
    document.getElementById('morBankStmtName').style.display = 'block';
    updateMorBtnState();
}

function handleMorPrevMor(input) {
    const file = input.files[0];
    if (!file) return;
    document.getElementById('morPrevMorName').textContent = file.name;
    document.getElementById('morPrevMorName').style.display = 'block';
}

function updateMorBtnState() {
    const hasMonth = document.getElementById('morMonthYear').value;
    const hasFile = document.getElementById('morBankStmtInput').files.length > 0;
    document.getElementById('morGenerateBtn').disabled = !(hasMonth && hasFile);
}

async function onMorMonthChange() {
    updateMorBtnState();
    const monthYear = document.getElementById('morMonthYear').value;
    if (!monthYear) return;

    try {
        const res = await fetch(`/api/converter/mor/previous-balance/${monthYear}`);
        const data = await res.json();
        if (data.success && data.found) {
            document.getElementById('morOpeningBalance').value = data.balance;
            document.getElementById('morOpeningBalance').placeholder = `Previous Line 23: $${data.balance.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        } else {
            document.getElementById('morOpeningBalance').placeholder = 'No previous MOR found — enter manually or upload';
        }
    } catch (err) {
        console.error('Error fetching previous balance:', err);
    }
}

async function generateMor() {
    const btn = document.getElementById('morGenerateBtn');
    btn.textContent = 'Generating...';
    btn.disabled = true;

    const formData = new FormData();
    formData.append('bank_statement', document.getElementById('morBankStmtInput').files[0]);
    formData.append('month_year', document.getElementById('morMonthYear').value);
    formData.append('report_date', document.getElementById('morReportDate').value);
    formData.append('proj_receipts', document.getElementById('morProjReceipts').value || 0);
    formData.append('proj_disbursements', document.getElementById('morProjDisbursements').value || 0);
    formData.append('responsible', document.getElementById('morResponsible').value);

    const openingBal = document.getElementById('morOpeningBalance').value;
    if (openingBal) formData.append('opening_balance', openingBal);

    const prevMorFile = document.getElementById('morPrevMorInput').files[0];
    if (prevMorFile) formData.append('prev_mor', prevMorFile);

    try {
        const res = await fetch('/api/converter/mor/generate', { method: 'POST', body: formData });
        const data = await res.json();

        if (!data.success) {
            alert(data.error || 'MOR generation failed');
            return;
        }

        const cash = data.cash_activity;
        const v = data.verification;

        let html = '<div class="results-card"><h4>MOR Generated &mdash; ' + data.month_label + '</h4>';

        // Cash activity
        html += '<div style="margin-bottom:12px;">';
        html += `<div class="results-row"><span class="label">Line 19 &mdash; Opening Balance</span><span class="value">$${cash.opening.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></div>`;
        html += `<div class="results-row"><span class="label">Line 20 &mdash; Receipts</span><span class="value">$${cash.receipts.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></div>`;
        html += `<div class="results-row"><span class="label">Line 21 &mdash; Disbursements</span><span class="value">$${cash.disbursements.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></div>`;
        html += `<div class="results-row"><span class="label">Line 22 &mdash; Net Cash Flow</span><span class="value">$${cash.net_cf.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></div>`;
        html += `<div class="results-row"><span class="label">Line 23 &mdash; Ending Balance</span><span class="value">$${cash.ending.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></div>`;
        html += '</div>';

        // Verification
        if (!v.no_summary) {
            const depClass = v.deposits_ok ? 'verify-ok' : 'verify-warn';
            const wdClass = v.withdrawals_ok ? 'verify-ok' : 'verify-warn';
            html += '<div style="margin-bottom:12px;padding:10px;background:#f9fafb;border-radius:8px;">';
            html += `<div class="results-row"><span class="label">Deposit Verification</span><span class="${depClass}">${v.deposits_ok ? 'Match' : 'MISMATCH'} ($${v.parsed_deposits.toLocaleString(undefined, {minimumFractionDigits: 2})} vs $${v.summary_deposits.toLocaleString(undefined, {minimumFractionDigits: 2})})</span></div>`;
            html += `<div class="results-row"><span class="label">Withdrawal Verification</span><span class="${wdClass}">${v.withdrawals_ok ? 'Match' : 'MISMATCH'} ($${v.parsed_withdrawals.toLocaleString(undefined, {minimumFractionDigits: 2})} vs $${v.summary_withdrawals.toLocaleString(undefined, {minimumFractionDigits: 2})})</span></div>`;
            html += '</div>';
        }

        // Downloads
        html += '<div style="margin-top:8px;">';
        html += `<a class="download-link" href="/api/converter/download/${data.files.mor.file_id}" target="_blank">Complete MOR Package (PDF)</a>`;
        html += '</div>';

        html += '</div>';

        document.getElementById('morResults').innerHTML = html;
        document.getElementById('morResults').style.display = 'block';
    } catch (err) {
        console.error('MOR generation error:', err);
        alert('MOR generation failed');
    } finally {
        btn.textContent = 'Generate MOR';
        btn.disabled = false;
    }
}


// ==========================================
// FILE HISTORY
// ==========================================

async function loadFileHistory() {
    const container = document.getElementById('fileHistoryTable');
    if (!container) return;

    const params = new URLSearchParams();
    const fileType = document.getElementById('historyTypeFilter')?.value;
    const monthYear = document.getElementById('historyMonthFilter')?.value;

    if (fileType) params.append('file_type', fileType);
    if (monthYear) params.append('month_year', monthYear);

    try {
        const res = await fetch('/api/converter/history?' + params.toString());
        const data = await res.json();

        if (!data.success || !data.files.length) {
            container.innerHTML = '<div style="color:#9ca3af;font-size:14px;padding:20px;">No files found.</div>';
            return;
        }

        let html = '<table class="history-table"><thead><tr>';
        html += '<th>Date</th><th>Type</th><th>Filename</th><th>Size</th><th></th>';
        html += '</tr></thead><tbody>';

        data.files.forEach(f => {
            const date = f.created_at ? new Date(f.created_at).toLocaleDateString() : '';
            const typeClass = f.file_type === 'mor' ? 'mor' : f.file_type.startsWith('exhibit') ? 'exhibit' : f.file_type === 'bank_statement' ? 'bank' : 'other';
            const typeLabel = f.file_type.replace(/_/g, ' ').toUpperCase();
            const size = f.file_size_bytes ? formatBytes(f.file_size_bytes) : '';

            html += `<tr>`;
            html += `<td>${date}</td>`;
            html += `<td><span class="type-badge ${typeClass}">${typeLabel}</span></td>`;
            html += `<td>${f.original_filename}</td>`;
            html += `<td>${size}</td>`;
            html += `<td><a class="download-link" href="/api/converter/download/${f.id}" target="_blank" style="margin:0;">Download</a></td>`;
            html += `</tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (err) {
        console.error('Error loading file history:', err);
    }
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}


// ==========================================
// INIT
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    loadReportCatalog();
    loadReportHistory();

    // Setup drag-and-drop zones
    setupUploadZone('morBankStmtZone', 'morBankStmtInput');
    setupUploadZone('morPrevMorZone', 'morPrevMorInput');
});
