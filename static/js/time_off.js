// Global state
let ptoBalance = {};
let timeOffRequests = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadPTOBalance();
    loadTimeOffRequests();

    // Set up form submission
    document.getElementById('timeOffRequestForm').addEventListener('submit', handleFormSubmit);

    // Auto-calculate hours when dates change
    document.getElementById('startDate').addEventListener('change', calculateDefaultHours);
    document.getElementById('endDate').addEventListener('change', calculateDefaultHours);
});

// Load PTO balance
async function loadPTOBalance() {
    try {
        const response = await fetch('/employee/pto-balance');
        const data = await response.json();

        if (data.success) {
            ptoBalance = data;
            document.getElementById('ptoAvailable').textContent = data.available.toFixed(1);
            document.getElementById('ptoUsed').textContent = data.used.toFixed(1);
            document.getElementById('ptoTotal').textContent = data.total.toFixed(1);
        }
    } catch (error) {
        console.error('Error loading PTO balance:', error);
        showNotification('Error loading PTO balance', 'error');
    }
}

// Load time off requests
async function loadTimeOffRequests() {
    try {
        const response = await fetch('/employee/time-off-requests');
        const data = await response.json();

        if (data.success) {
            timeOffRequests = data.requests || [];
            renderTimeOffHistory();
        }
    } catch (error) {
        console.error('Error loading time off requests:', error);
        showNotification('Error loading requests', 'error');
    }
}

// Render request history table
function renderTimeOffHistory() {
    const tbody = document.getElementById('timeOffHistoryBody');

    if (timeOffRequests.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <p>No time off requests yet</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = timeOffRequests.map(request => {
        const startDate = new Date(request.start_date).toLocaleDateString();
        const endDate = new Date(request.end_date).toLocaleDateString();
        const dateRange = startDate === endDate ? startDate : `${startDate} - ${endDate}`;

        const statusBadge = `<span class="status-badge ${request.status}">${capitalize(request.status)}</span>`;

        const actions = request.status === 'pending'
            ? `<button class="btn-cancel" onclick="cancelRequest(${request.id})">Cancel</button>`
            : '—';

        const displayReason = request.status === 'denied' && request.reason
            ? request.reason
            : (request.admin_notes || request.reason || '—');

        return `
            <tr>
                <td>${dateRange}</td>
                <td>${capitalize(request.request_type)}</td>
                <td>${request.total_hours} hrs</td>
                <td>${statusBadge}</td>
                <td>${displayReason}</td>
                <td>${actions}</td>
            </tr>
        `;
    }).join('');
}

// Handle form submission
async function handleFormSubmit(e) {
    e.preventDefault();

    const formData = {
        start_date: document.getElementById('startDate').value,
        end_date: document.getElementById('endDate').value,
        request_type: document.getElementById('requestType').value,
        total_hours: parseFloat(document.getElementById('totalHours').value),
        reason: document.getElementById('reason').value
    };

    // Validate dates
    if (new Date(formData.start_date) > new Date(formData.end_date)) {
        showNotification('End date must be after start date', 'error');
        return;
    }

    // Validate PTO balance if requesting PTO
    if (formData.request_type === 'pto' && formData.total_hours > ptoBalance.available) {
        showNotification(
            `Insufficient PTO balance. Available: ${ptoBalance.available} hours, Requested: ${formData.total_hours} hours`,
            'error'
        );
        return;
    }

    try {
        const response = await fetch('/employee/time-off-requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Time off request submitted successfully!', 'success');

            // Reset form
            document.getElementById('timeOffRequestForm').reset();

            // Reload data
            await loadTimeOffRequests();
            await loadPTOBalance();
        } else {
            showNotification(data.error || 'Error submitting request', 'error');
        }
    } catch (error) {
        console.error('Error submitting time off request:', error);
        showNotification('Error submitting request', 'error');
    }
}

// Cancel pending request
async function cancelRequest(requestId) {
    if (!confirm('Are you sure you want to cancel this request?')) {
        return;
    }

    try {
        const response = await fetch(`/employee/time-off-requests/${requestId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Request cancelled successfully', 'success');
            await loadTimeOffRequests();
        } else {
            showNotification(data.error || 'Error cancelling request', 'error');
        }
    } catch (error) {
        console.error('Error cancelling request:', error);
        showNotification('Error cancelling request', 'error');
    }
}

// Calculate default hours based on date range (assuming 8 hour work days)
function calculateDefaultHours() {
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;

    if (!startDate || !endDate) {
        return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);

    if (start > end) {
        return;
    }

    // Calculate business days
    let businessDays = 0;
    const current = new Date(start);

    while (current <= end) {
        const dayOfWeek = current.getDay();
        // Skip weekends (0 = Sunday, 6 = Saturday)
        if (dayOfWeek !== 0 && dayOfWeek !== 6) {
            businessDays++;
        }
        current.setDate(current.getDate() + 1);
    }

    // Assume 8 hours per business day
    const totalHours = businessDays * 8;
    document.getElementById('totalHours').value = totalHours;
}

// Show notification
function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';

    setTimeout(() => {
        notification.style.display = 'none';
    }, 4000);
}

// Capitalize first letter
function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}
