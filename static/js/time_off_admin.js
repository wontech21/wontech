/**
 * Admin Time Off Request Management
 * Handles viewing, approving, and denying employee time off requests
 */

// Global state
let allTimeOffRequests = [];
let filteredTimeOffRequests = [];
let timeOffCurrentPage = 1;
let timeOffPageSize = 10;
let timeOffSort = { column: 2, order: 'desc', type: 'date' }; // Default sort by start date descending
let pendingTimeOffAction = null; // Stores {action: 'approve'|'deny', requestId: number}

// Initialize when tab is shown
async function initializeTimeOffTab() {
    console.log('Initializing Time Off Requests tab...');
    createTimeOffModal();
    await loadTimeOffRequests();
    await populateTimeOffEmployeeFilter();
}

// Create the modal HTML and append to body
function createTimeOffModal() {
    // Remove existing modal if present
    const existingModal = document.getElementById('timeOffActionModal');
    if (existingModal) {
        existingModal.remove();
    }

    const modalHTML = `
        <div id="timeOffActionModal" class="time-off-modal-overlay" style="display: none;">
            <div class="time-off-modal">
                <div class="time-off-modal-header">
                    <h3 id="timeOffModalTitle">Approve Time Off Request</h3>
                    <button class="time-off-modal-close" onclick="closeTimeOffModal()">&times;</button>
                </div>
                <div class="time-off-modal-body">
                    <div id="timeOffModalRequestInfo" class="time-off-request-info"></div>

                    <div id="timeOffDenyReasonGroup" class="form-group" style="display: none;">
                        <label for="timeOffDenyReason">Reason for Denial <span style="color: #ef4444;">*</span></label>
                        <textarea id="timeOffDenyReason" rows="3" placeholder="Please provide a reason for denying this request..."></textarea>
                    </div>

                    <div class="form-group">
                        <label for="timeOffAdminNotes">Admin Notes <span style="color: #9ca3af;">(optional)</span></label>
                        <textarea id="timeOffAdminNotes" rows="3" placeholder="Add any notes for this request..."></textarea>
                    </div>
                </div>
                <div class="time-off-modal-footer">
                    <button class="btn-cancel" onclick="closeTimeOffModal()">Cancel</button>
                    <button id="timeOffModalSubmit" class="btn-submit" onclick="submitTimeOffAction()">Approve</button>
                </div>
            </div>
        </div>
        <style>
            /* Time Off Table Styles */
            #time-off-requests-tab {
                width: 100%;
                overflow: hidden;
            }
            #time-off-requests-tab .time-off-section {
                width: 100%;
                overflow: hidden;
            }
            #time-off-requests-tab .table-container {
                width: 100%;
                overflow-x: auto;
                border-radius: 8px;
                border: 1px solid #e5e7eb;
            }
            #timeOffRequestsTable {
                width: 100%;
                min-width: 800px;
                border-collapse: collapse;
                table-layout: fixed;
            }
            #timeOffRequestsTable th,
            #timeOffRequestsTable td {
                padding: 12px 10px;
                text-align: left;
                border-bottom: 1px solid #e5e7eb;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            #timeOffRequestsTable thead {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            #timeOffRequestsTable th {
                background: transparent;
                font-weight: 600;
                font-size: 0.85rem;
                color: white;
            }
            /* Column widths */
            #timeOffRequestsTable th:nth-child(1),
            #timeOffRequestsTable td:nth-child(1) { width: 14%; } /* Employee */
            #timeOffRequestsTable th:nth-child(2),
            #timeOffRequestsTable td:nth-child(2) { width: 10%; } /* Position */
            #timeOffRequestsTable th:nth-child(3),
            #timeOffRequestsTable td:nth-child(3) { width: 10%; } /* Start Date */
            #timeOffRequestsTable th:nth-child(4),
            #timeOffRequestsTable td:nth-child(4) { width: 10%; } /* End Date */
            #timeOffRequestsTable th:nth-child(5),
            #timeOffRequestsTable td:nth-child(5) { width: 8%; } /* Type */
            #timeOffRequestsTable th:nth-child(6),
            #timeOffRequestsTable td:nth-child(6) { width: 7%; } /* Hours */
            #timeOffRequestsTable th:nth-child(7),
            #timeOffRequestsTable td:nth-child(7) { width: 9%; } /* Status */
            #timeOffRequestsTable th:nth-child(8),
            #timeOffRequestsTable td:nth-child(8) { width: 15%; } /* Reason */
            #timeOffRequestsTable th:nth-child(9),
            #timeOffRequestsTable td:nth-child(9) { width: 17%; } /* Actions */

            #timeOffRequestsTable tbody tr:hover {
                background: #f9fafb;
            }
            #timeOffRequestsTable .status-active {
                background: #d1fae5;
                color: #065f46;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: 500;
            }
            #timeOffRequestsTable .status-inactive {
                background: #fee2e2;
                color: #991b1b;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: 500;
            }
            #timeOffRequestsTable .status-pending {
                background: #fef3c7;
                color: #92400e;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: 500;
            }

            /* Modal Styles */
            .time-off-modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                backdrop-filter: blur(4px);
            }
            .time-off-modal {
                background: white;
                border-radius: 12px;
                width: 90%;
                max-width: 500px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                animation: modalSlideIn 0.3s ease;
            }
            @keyframes modalSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(-20px) scale(0.95);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }
            .time-off-modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px 24px;
                border-bottom: 1px solid #e5e7eb;
            }
            .time-off-modal-header h3 {
                margin: 0;
                font-size: 1.25rem;
                font-weight: 600;
                color: #1f2937;
            }
            .time-off-modal-close {
                background: none;
                border: none;
                font-size: 1.5rem;
                color: #9ca3af;
                cursor: pointer;
                padding: 0;
                line-height: 1;
                transition: color 0.2s;
            }
            .time-off-modal-close:hover {
                color: #1f2937;
            }
            .time-off-modal-body {
                padding: 24px;
            }
            .time-off-request-info {
                background: #f9fafb;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 20px;
            }
            .time-off-request-info p {
                margin: 4px 0;
                color: #4b5563;
                font-size: 0.9rem;
            }
            .time-off-request-info p strong {
                color: #1f2937;
            }
            .time-off-modal-body .form-group {
                margin-bottom: 16px;
            }
            .time-off-modal-body label {
                display: block;
                margin-bottom: 8px;
                font-weight: 500;
                color: #374151;
                font-size: 0.9rem;
            }
            .time-off-modal-body textarea {
                width: 100%;
                padding: 12px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                font-size: 0.9rem;
                resize: vertical;
                font-family: inherit;
                transition: border-color 0.2s, box-shadow 0.2s;
                box-sizing: border-box;
            }
            .time-off-modal-body textarea:focus {
                outline: none;
                border-color: #6366f1;
                box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
            }
            .time-off-modal-footer {
                display: flex;
                justify-content: flex-end;
                gap: 12px;
                padding: 16px 24px;
                border-top: 1px solid #e5e7eb;
                background: #f9fafb;
                border-radius: 0 0 12px 12px;
            }
            .time-off-modal-footer .btn-cancel {
                padding: 10px 20px;
                border: 1px solid #d1d5db;
                background: white;
                color: #374151;
                border-radius: 8px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }
            .time-off-modal-footer .btn-cancel:hover {
                background: #f3f4f6;
            }
            .time-off-modal-footer .btn-submit {
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }
            .time-off-modal-footer .btn-submit.approve {
                background: #10b981;
                color: white;
            }
            .time-off-modal-footer .btn-submit.approve:hover {
                background: #059669;
            }
            .time-off-modal-footer .btn-submit.deny {
                background: #ef4444;
                color: white;
            }
            .time-off-modal-footer .btn-submit.deny:hover {
                background: #dc2626;
            }

            /* Success Animation Styles */
            .success-animation {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 40px 20px;
                text-align: center;
            }
            .success-icon {
                width: 80px;
                height: 80px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 40px;
                color: white;
                margin-bottom: 20px;
                animation: successPop 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            }
            .success-icon.approve {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                box-shadow: 0 10px 30px rgba(16, 185, 129, 0.4);
            }
            .success-icon.deny {
                background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                box-shadow: 0 10px 30px rgba(239, 68, 68, 0.4);
            }
            @keyframes successPop {
                0% {
                    transform: scale(0);
                    opacity: 0;
                }
                50% {
                    transform: scale(1.2);
                }
                100% {
                    transform: scale(1);
                    opacity: 1;
                }
            }
            .success-title {
                margin: 0 0 8px 0;
                font-size: 1.5rem;
                font-weight: 600;
                color: #1f2937;
                animation: fadeInUp 0.4s ease 0.2s both;
            }
            .success-message {
                margin: 0;
                color: #6b7280;
                font-size: 0.95rem;
                animation: fadeInUp 0.4s ease 0.3s both;
            }
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        </style>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

// Show modal for approval
function approveTimeOffRequest(requestId) {
    const request = allTimeOffRequests.find(r => r.id === requestId);
    if (!request) return;

    pendingTimeOffAction = { action: 'approve', requestId };

    const modal = document.getElementById('timeOffActionModal');
    const title = document.getElementById('timeOffModalTitle');
    const submitBtn = document.getElementById('timeOffModalSubmit');
    const denyReasonGroup = document.getElementById('timeOffDenyReasonGroup');
    const requestInfo = document.getElementById('timeOffModalRequestInfo');

    title.textContent = 'Approve Time Off Request';
    submitBtn.textContent = 'Approve';
    submitBtn.className = 'btn-submit approve';
    denyReasonGroup.style.display = 'none';

    requestInfo.innerHTML = `
        <p><strong>Employee:</strong> ${request.employee_name || 'Unknown'}</p>
        <p><strong>Type:</strong> ${capitalizeFirst(request.request_type)}</p>
        <p><strong>Dates:</strong> ${new Date(request.start_date).toLocaleDateString()} - ${new Date(request.end_date).toLocaleDateString()}</p>
        <p><strong>Hours:</strong> ${request.total_hours} hours</p>
        ${request.reason ? `<p><strong>Employee's Reason:</strong> ${request.reason}</p>` : ''}
    `;

    // Clear previous inputs
    document.getElementById('timeOffAdminNotes').value = '';
    document.getElementById('timeOffDenyReason').value = '';

    modal.style.display = 'flex';
    document.getElementById('timeOffAdminNotes').focus();
}

// Show modal for denial
function denyTimeOffRequest(requestId) {
    const request = allTimeOffRequests.find(r => r.id === requestId);
    if (!request) return;

    pendingTimeOffAction = { action: 'deny', requestId };

    const modal = document.getElementById('timeOffActionModal');
    const title = document.getElementById('timeOffModalTitle');
    const submitBtn = document.getElementById('timeOffModalSubmit');
    const denyReasonGroup = document.getElementById('timeOffDenyReasonGroup');
    const requestInfo = document.getElementById('timeOffModalRequestInfo');

    title.textContent = 'Deny Time Off Request';
    submitBtn.textContent = 'Deny Request';
    submitBtn.className = 'btn-submit deny';
    denyReasonGroup.style.display = 'block';

    requestInfo.innerHTML = `
        <p><strong>Employee:</strong> ${request.employee_name || 'Unknown'}</p>
        <p><strong>Type:</strong> ${capitalizeFirst(request.request_type)}</p>
        <p><strong>Dates:</strong> ${new Date(request.start_date).toLocaleDateString()} - ${new Date(request.end_date).toLocaleDateString()}</p>
        <p><strong>Hours:</strong> ${request.total_hours} hours</p>
        ${request.reason ? `<p><strong>Employee's Reason:</strong> ${request.reason}</p>` : ''}
    `;

    // Clear previous inputs
    document.getElementById('timeOffAdminNotes').value = '';
    document.getElementById('timeOffDenyReason').value = '';

    modal.style.display = 'flex';
    document.getElementById('timeOffDenyReason').focus();
}

// Close modal and reset its content
function closeTimeOffModal() {
    const modal = document.getElementById('timeOffActionModal');
    if (modal) {
        modal.style.display = 'none';
        // Reset modal content for next use
        resetModalContent();
    }
    pendingTimeOffAction = null;
}

// Reset modal to its original form state
function resetModalContent() {
    const modalBody = document.querySelector('.time-off-modal-body');
    const modalFooter = document.querySelector('.time-off-modal-footer');

    if (modalBody) {
        modalBody.innerHTML = `
            <div id="timeOffModalRequestInfo" class="time-off-request-info"></div>

            <div id="timeOffDenyReasonGroup" class="form-group" style="display: none;">
                <label for="timeOffDenyReason">Reason for Denial <span style="color: #ef4444;">*</span></label>
                <textarea id="timeOffDenyReason" rows="3" placeholder="Please provide a reason for denying this request..."></textarea>
            </div>

            <div class="form-group">
                <label for="timeOffAdminNotes">Admin Notes <span style="color: #9ca3af;">(optional)</span></label>
                <textarea id="timeOffAdminNotes" rows="3" placeholder="Add any notes for this request..."></textarea>
            </div>
        `;
    }

    if (modalFooter) {
        modalFooter.style.display = 'flex';
    }
}

// Submit the action (approve or deny)
async function submitTimeOffAction() {
    if (!pendingTimeOffAction) return;

    const { action, requestId } = pendingTimeOffAction;
    const adminNotes = document.getElementById('timeOffAdminNotes').value.trim();
    const denyReason = document.getElementById('timeOffDenyReason').value.trim();

    if (action === 'deny' && !denyReason) {
        showNotification('Please provide a reason for denial', 'error');
        document.getElementById('timeOffDenyReason').focus();
        return;
    }

    const submitBtn = document.getElementById('timeOffModalSubmit');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing...';

    try {
        let response;
        if (action === 'approve') {
            response = await fetch(`/api/schedules/time-off-requests/${requestId}/approve`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ admin_notes: adminNotes })
            });
        } else {
            response = await fetch(`/api/schedules/time-off-requests/${requestId}/deny`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    reason: denyReason,
                    admin_notes: adminNotes
                })
            });
        }

        const data = await response.json();

        if (response.ok && data.success) {
            // Show success animation in modal
            showModalSuccess(action);
        } else {
            showNotification(data.error || `Error ${action === 'approve' ? 'approving' : 'denying'} request`, 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    } catch (error) {
        console.error(`Error ${action === 'approve' ? 'approving' : 'denying'} time off request:`, error);
        showNotification(`Error ${action === 'approve' ? 'approving' : 'denying'} request`, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// Show success animation in modal then close
function showModalSuccess(action) {
    const modal = document.querySelector('.time-off-modal');
    const modalBody = document.querySelector('.time-off-modal-body');
    const modalFooter = document.querySelector('.time-off-modal-footer');

    if (!modal || !modalBody) return;

    // Hide footer
    if (modalFooter) {
        modalFooter.style.display = 'none';
    }

    // Replace body with success animation
    const isApprove = action === 'approve';
    modalBody.innerHTML = `
        <div class="success-animation">
            <div class="success-icon ${isApprove ? 'approve' : 'deny'}">
                ${isApprove ? '✓' : '✕'}
            </div>
            <h3 class="success-title">${isApprove ? 'Approved!' : 'Denied'}</h3>
            <p class="success-message">Time off request has been ${isApprove ? 'approved' : 'denied'} successfully.</p>
        </div>
    `;

    // After animation, close modal and refresh
    setTimeout(async () => {
        // Fade out the modal
        const overlay = document.getElementById('timeOffActionModal');
        if (overlay) {
            overlay.style.transition = 'opacity 0.3s ease';
            overlay.style.opacity = '0';
        }

        setTimeout(async () => {
            closeTimeOffModal();
            // Reset opacity for next use
            if (overlay) {
                overlay.style.opacity = '1';
            }
            // Refresh the time off requests list
            await loadTimeOffRequests();
            showNotification(
                action === 'approve'
                    ? 'Time off request approved successfully'
                    : 'Time off request denied',
                'success'
            );
        }, 300);
    }, 1200);
}

// Close modal on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeTimeOffModal();
    }
});

// Load all time off requests
async function loadTimeOffRequests() {
    try {
        const status = document.getElementById('timeOffStatusFilter')?.value || 'pending';

        const response = await fetch(`/api/schedules/time-off-requests?status=${status}`);

        if (!response.ok) {
            throw new Error('Failed to fetch time off requests');
        }

        const data = await response.json();
        console.log('Time off requests loaded:', data);

        allTimeOffRequests = data.requests || [];
        filterTimeOffRequests();
    } catch (error) {
        console.error('Error loading time off requests:', error);
        showNotification('Error loading time off requests', 'error');
        allTimeOffRequests = [];
        displayTimeOffRequests();
    }
}

// Populate employee filter dropdown
async function populateTimeOffEmployeeFilter() {
    const filter = document.getElementById('timeOffEmployeeFilter');
    if (!filter) return;

    // Get unique employees from requests
    const uniqueEmployees = new Map();
    allTimeOffRequests.forEach(request => {
        if (request.employee_id && request.employee_name) {
            uniqueEmployees.set(request.employee_id, request.employee_name);
        }
    });

    filter.innerHTML = '<option value="all">All Employees</option>';
    Array.from(uniqueEmployees.entries())
        .sort((a, b) => a[1].localeCompare(b[1]))
        .forEach(([id, name]) => {
            filter.innerHTML += `<option value="${id}">${name}</option>`;
        });
}

// Filter time off requests
function filterTimeOffRequests() {
    const employeeFilter = document.getElementById('timeOffEmployeeFilter')?.value || 'all';
    const statusFilter = document.getElementById('timeOffStatusFilter')?.value || 'all';
    const typeFilter = document.getElementById('timeOffTypeFilter')?.value || 'all';

    filteredTimeOffRequests = allTimeOffRequests.filter(request => {
        if (employeeFilter !== 'all' && request.employee_id != employeeFilter) return false;
        if (statusFilter !== 'all' && request.status !== statusFilter) return false;
        if (typeFilter !== 'all' && request.request_type !== typeFilter) return false;
        return true;
    });

    // Apply sorting
    sortTimeOffArray(filteredTimeOffRequests);

    timeOffCurrentPage = 1;
    displayTimeOffRequests();
}

// Display time off requests
function displayTimeOffRequests() {
    const tbody = document.getElementById('timeOffRequestsTableBody');
    if (!tbody) return;

    if (filteredTimeOffRequests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">No time off requests found</td></tr>';
        updateTimeOffPagination();
        return;
    }

    const startIdx = (timeOffCurrentPage - 1) * timeOffPageSize;
    const endIdx = timeOffPageSize === 'all' ? filteredTimeOffRequests.length : Math.min(startIdx + parseInt(timeOffPageSize), filteredTimeOffRequests.length);
    const pageRequests = filteredTimeOffRequests.slice(startIdx, endIdx);

    tbody.innerHTML = pageRequests.map(request => {
        const startDate = new Date(request.start_date).toLocaleDateString();
        const endDate = new Date(request.end_date).toLocaleDateString();

        const statusClass = request.status === 'approved' ? 'status-active' :
                          request.status === 'denied' ? 'status-inactive' :
                          'status-pending';

        const statusText = request.status.charAt(0).toUpperCase() + request.status.slice(1);

        const actions = request.status === 'pending' ?
            `<button onclick="approveTimeOffRequest(${request.id})" class="btn-approve" style="background: #10b981; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; margin-right: 5px;">Approve</button>
             <button onclick="denyTimeOffRequest(${request.id})" class="btn-deny" style="background: #ef4444; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer;">Deny</button>` :
            `<span style="color: #9ca3af;">—</span>`;

        const displayReason = request.status === 'denied' && request.reason
            ? request.reason
            : (request.admin_notes || request.reason || '—');

        return `
            <tr>
                <td>${request.employee_name || 'Unknown'}</td>
                <td>${request.position || '—'}</td>
                <td>${startDate}</td>
                <td>${endDate}</td>
                <td>${capitalizeFirst(request.request_type)}</td>
                <td>${request.total_hours} hrs</td>
                <td><span class="${statusClass}">${statusText}</span></td>
                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">${displayReason}</td>
                <td>${actions}</td>
            </tr>
        `;
    }).join('');

    updateTimeOffPagination();
}

// Sort time off table
function sortTimeOffTable(columnIndex, type) {
    if (timeOffSort.column === columnIndex) {
        timeOffSort.order = timeOffSort.order === 'asc' ? 'desc' : 'asc';
    } else {
        timeOffSort.column = columnIndex;
        timeOffSort.type = type;
        timeOffSort.order = 'asc';
    }

    sortTimeOffArray(filteredTimeOffRequests);
    displayTimeOffRequests();
    updateSortArrows('timeOffRequestsTable', columnIndex, timeOffSort.order);
}

// Sort array based on current sort settings
function sortTimeOffArray(array) {
    array.sort((a, b) => {
        let aVal, bVal;

        switch (timeOffSort.column) {
            case 0: // Employee
                aVal = a.employee_name || '';
                bVal = b.employee_name || '';
                break;
            case 1: // Position
                aVal = a.position || '';
                bVal = b.position || '';
                break;
            case 2: // Start Date
                aVal = new Date(a.start_date);
                bVal = new Date(b.start_date);
                break;
            case 3: // End Date
                aVal = new Date(a.end_date);
                bVal = new Date(b.end_date);
                break;
            case 4: // Type
                aVal = a.request_type || '';
                bVal = b.request_type || '';
                break;
            case 5: // Hours
                aVal = a.total_hours || 0;
                bVal = b.total_hours || 0;
                break;
            case 6: // Status
                aVal = a.status || '';
                bVal = b.status || '';
                break;
            default:
                return 0;
        }

        if (timeOffSort.type === 'number') {
            return timeOffSort.order === 'asc' ? aVal - bVal : bVal - aVal;
        } else if (timeOffSort.type === 'date') {
            return timeOffSort.order === 'asc' ? aVal - bVal : bVal - aVal;
        } else {
            const comparison = String(aVal).localeCompare(String(bVal));
            return timeOffSort.order === 'asc' ? comparison : -comparison;
        }
    });
}

// Pagination functions
function updateTimeOffPagination() {
    const totalItems = filteredTimeOffRequests.length;
    const pageSize = timeOffPageSize === 'all' ? totalItems : parseInt(timeOffPageSize);
    const totalPages = Math.ceil(totalItems / pageSize);

    const startIdx = (timeOffCurrentPage - 1) * pageSize + 1;
    const endIdx = Math.min(timeOffCurrentPage * pageSize, totalItems);

    const infoElement = document.getElementById('timeOffPaginationInfo');
    if (infoElement) {
        infoElement.textContent = `Showing ${startIdx}-${endIdx} of ${totalItems} items`;
    }

    // Update button states
    const firstBtn = document.getElementById('timeOffFirstPage');
    const prevBtn = document.getElementById('timeOffPrevPage');
    const nextBtn = document.getElementById('timeOffNextPage');
    const lastBtn = document.getElementById('timeOffLastPage');

    if (firstBtn) firstBtn.disabled = timeOffCurrentPage === 1;
    if (prevBtn) prevBtn.disabled = timeOffCurrentPage === 1;
    if (nextBtn) nextBtn.disabled = timeOffCurrentPage === totalPages || timeOffPageSize === 'all';
    if (lastBtn) lastBtn.disabled = timeOffCurrentPage === totalPages || timeOffPageSize === 'all';

    // Update page numbers
    const pageNumbersElement = document.getElementById('timeOffPageNumbers');
    if (pageNumbersElement && timeOffPageSize !== 'all') {
        let pageNumbersHTML = '';
        const maxButtons = 5;
        let startPage = Math.max(1, timeOffCurrentPage - Math.floor(maxButtons / 2));
        let endPage = Math.min(totalPages, startPage + maxButtons - 1);

        if (endPage - startPage + 1 < maxButtons) {
            startPage = Math.max(1, endPage - maxButtons + 1);
        }

        for (let i = startPage; i <= endPage; i++) {
            pageNumbersHTML += `<button class="${i === timeOffCurrentPage ? 'active' : ''}" onclick="goToTimeOffPage(${i})">${i}</button>`;
        }

        pageNumbersElement.innerHTML = pageNumbersHTML;
    }
}

function changeTimeOffPage(direction) {
    const totalPages = Math.ceil(filteredTimeOffRequests.length / (timeOffPageSize === 'all' ? filteredTimeOffRequests.length : parseInt(timeOffPageSize)));

    switch (direction) {
        case 'first':
            timeOffCurrentPage = 1;
            break;
        case 'prev':
            timeOffCurrentPage = Math.max(1, timeOffCurrentPage - 1);
            break;
        case 'next':
            timeOffCurrentPage = Math.min(totalPages, timeOffCurrentPage + 1);
            break;
        case 'last':
            timeOffCurrentPage = totalPages;
            break;
    }

    displayTimeOffRequests();
}

function goToTimeOffPage(page) {
    timeOffCurrentPage = page;
    displayTimeOffRequests();
}

function changeTimeOffPageSize() {
    const select = document.getElementById('timeOffPageSize');
    timeOffPageSize = select.value === 'all' ? 'all' : parseInt(select.value);
    timeOffCurrentPage = 1;
    displayTimeOffRequests();
}

// Helper function
function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Update sort arrows (reuse from existing dashboard code if available)
function updateSortArrows(tableId, columnIndex, order) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const arrows = table.querySelectorAll('.sort-arrow');
    arrows.forEach((arrow, index) => {
        if (index === columnIndex) {
            arrow.textContent = order === 'asc' ? '▲' : '▼';
        } else {
            arrow.textContent = '';
        }
    });
}
