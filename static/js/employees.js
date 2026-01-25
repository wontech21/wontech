/**
 * Employee Management JavaScript
 * Handles CRUD operations for employees
 */

let allEmployees = [];
let currentEmployeeId = null;
let currentEmployeesPage = 1;
let employeesPageSize = 10;
let employeesSortColumn = null;
let employeesSortDirection = 'asc';

// Load employees when employees tab is shown
function loadEmployees() {
    const status = document.getElementById('employeeStatusFilter')?.value || 'active';

    fetch('/api/employees')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                allEmployees = data.employees;
                filterAndDisplayEmployees();
            } else {
                showError('Failed to load employees');
            }
        })
        .catch(error => {
            console.error('Error loading employees:', error);
            showError('Error loading employees');
        });
}

function filterAndDisplayEmployees() {
    const status = document.getElementById('employeeStatusFilter')?.value || 'active';
    const searchTerm = document.getElementById('employeeSearch')?.value.toLowerCase() || '';

    let filtered = allEmployees;

    // Filter by status
    if (status !== 'all') {
        filtered = filtered.filter(emp => emp.status === status);
    }

    // Filter by search term
    if (searchTerm) {
        filtered = filtered.filter(emp =>
            emp.first_name.toLowerCase().includes(searchTerm) ||
            emp.last_name.toLowerCase().includes(searchTerm) ||
            emp.employee_code.toLowerCase().includes(searchTerm) ||
            (emp.email && emp.email.toLowerCase().includes(searchTerm)) ||
            (emp.position && emp.position.toLowerCase().includes(searchTerm))
        );
    }

    displayEmployees(filtered);
}

function displayEmployees(employees) {
    const tbody = document.getElementById('employeesTableBody');

    if (!employees || employees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="color: #6b7280; padding: 40px;">No employees found</td></tr>';
        updateEmployeesPagination(0);
        return;
    }

    // Apply pagination
    const totalEmployees = employees.length;
    const totalPages = employeesPageSize === 'all' ? 1 : Math.ceil(totalEmployees / employeesPageSize);
    currentEmployeesPage = Math.min(currentEmployeesPage, totalPages || 1);

    const startIndex = employeesPageSize === 'all' ? 0 : (currentEmployeesPage - 1) * employeesPageSize;
    const endIndex = employeesPageSize === 'all' ? totalEmployees : startIndex + employeesPageSize;
    const paginatedEmployees = employees.slice(startIndex, endIndex);

    tbody.innerHTML = paginatedEmployees.map(emp => {
        const fullName = `${emp.first_name} ${emp.last_name}`;
        const statusClass = emp.status === 'active' ? 'badge-success' : 'badge-secondary';
        const statusIcon = emp.status === 'active' ? '●' : '○';

        return `
        <tr class="hoverable-row">
            <td><strong style="color: #667eea;">${emp.employee_code}</strong></td>
            <td><strong>${fullName}</strong></td>
            <td>${emp.position || '<span style="color: #9ca3af;">—</span>'}</td>
            <td>${emp.email || '<span style="color: #9ca3af;">—</span>'}</td>
            <td>${emp.phone || '<span style="color: #9ca3af;">—</span>'}</td>
            <td>
                <span class="badge ${statusClass}">
                    ${statusIcon} ${emp.status.charAt(0).toUpperCase() + emp.status.slice(1)}
                </span>
            </td>
            <td class="text-center">
                ${emp.user_id
                    ? '<span style="color: #10b981; font-weight: 600;">✓</span>'
                    : '<span style="color: #9ca3af;">—</span>'}
            </td>
            <td class="actions-cell">
                <button class="btn-edit-dark"
                        onclick="editEmployee(${emp.id})"
                        title="Edit Employee">
                    <span style="font-weight: 700;">✏️</span>
                </button>
                <button class="btn-delete-dark"
                        onclick="deleteEmployee(${emp.id}, '${fullName.replace(/'/g, "\\'")}')"
                        title="Delete Employee">
                    <span style="font-weight: 700;">🗑️</span>
                </button>
            </td>
        </tr>
    `;
    }).join('');

    updateEmployeesPagination(totalEmployees);
}

function searchEmployees() {
    filterAndDisplayEmployees();
}

function openCreateEmployeeModal() {
    currentEmployeeId = null;
    document.getElementById('employeeModalTitle').textContent = 'Add New Employee';
    document.getElementById('employeeForm').reset();
    document.getElementById('employeeId').value = '';
    document.getElementById('employeeFormError').style.display = 'none';
    document.getElementById('employeeModal').classList.add('active');
}

function editEmployee(employeeId) {
    currentEmployeeId = employeeId;

    fetch(`/api/employees/${employeeId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const emp = data.employee;

                document.getElementById('employeeModalTitle').textContent = 'Edit Employee';
                document.getElementById('employeeId').value = emp.id;
                document.getElementById('employeeFirstName').value = emp.first_name;
                document.getElementById('employeeLastName').value = emp.last_name;
                document.getElementById('employeeCode').value = emp.employee_code;
                document.getElementById('employeePosition').value = emp.position || '';
                document.getElementById('employeeDepartment').value = emp.department || '';
                document.getElementById('employeeType').value = emp.employment_type || 'full-time';
                document.getElementById('employeeEmail').value = emp.email || '';
                document.getElementById('employeePhone').value = emp.phone || '';
                document.getElementById('employeeHireDate').value = emp.hire_date || '';
                document.getElementById('employeeHourlyRate').value = emp.hourly_rate || '';

                document.getElementById('employeeFormError').style.display = 'none';
                document.getElementById('employeeModal').classList.add('active');
            } else {
                showError('Failed to load employee details');
            }
        })
        .catch(error => {
            console.error('Error loading employee:', error);
            showError('Error loading employee details');
        });
}

function closeEmployeeModal() {
    document.getElementById('employeeModal').classList.remove('active');
    document.getElementById('employeeForm').reset();
    currentEmployeeId = null;
}

function saveEmployee(event) {
    event.preventDefault();

    const formData = {
        first_name: document.getElementById('employeeFirstName').value,
        last_name: document.getElementById('employeeLastName').value,
        employee_code: document.getElementById('employeeCode').value,
        position: document.getElementById('employeePosition').value,
        department: document.getElementById('employeeDepartment').value,
        employment_type: document.getElementById('employeeType').value,
        email: document.getElementById('employeeEmail').value,
        phone: document.getElementById('employeePhone').value,
        hire_date: document.getElementById('employeeHireDate').value,
        hourly_rate: document.getElementById('employeeHourlyRate').value || 0
    };

    const employeeId = document.getElementById('employeeId').value;
    const isEdit = employeeId !== '';

    const url = isEdit ? `/api/employees/${employeeId}` : '/api/employees';
    const method = isEdit ? 'PUT' : 'POST';

    // Disable submit button
    const submitBtn = document.getElementById('saveEmployeeBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';

    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
            closeEmployeeModal();
            loadEmployees();
        } else {
            document.getElementById('employeeFormError').textContent = data.error;
            document.getElementById('employeeFormError').style.display = 'block';
        }
    })
    .catch(error => {
        console.error('Error saving employee:', error);
        document.getElementById('employeeFormError').textContent = 'Error saving employee';
        document.getElementById('employeeFormError').style.display = 'block';
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.textContent = '💾 Save Employee';
    });
}

function deleteEmployee(employeeId, employeeName) {
    if (!confirm(`Are you sure you want to deactivate ${employeeName}?\n\nThis will set their status to inactive and disable their login if they have one.`)) {
        return;
    }

    fetch(`/api/employees/${employeeId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
            loadEmployees();
        } else {
            showError(data.error || 'Failed to delete employee');
        }
    })
    .catch(error => {
        console.error('Error deleting employee:', error);
        showError('Error deleting employee');
    });
}

// Helper functions
function showSuccess(message) {
    // Use existing notification system if available
    if (typeof showNotification === 'function') {
        showNotification(message, 'success');
    } else {
        alert(message);
    }
}

function showError(message) {
    // Use existing notification system if available
    if (typeof showNotification === 'function') {
        showNotification(message, 'error');
    } else {
        alert(message);
    }
}

// Pagination functions
function updateEmployeesPagination(totalEmployees) {
    const totalPages = employeesPageSize === 'all' ? 1 : Math.ceil(totalEmployees / employeesPageSize);
    const startIndex = employeesPageSize === 'all' ? 1 : (currentEmployeesPage - 1) * employeesPageSize + 1;
    const endIndex = employeesPageSize === 'all' ? totalEmployees : Math.min(currentEmployeesPage * employeesPageSize, totalEmployees);

    // Update pagination info
    document.getElementById('employeesPaginationInfo').textContent =
        `Showing ${startIndex}-${endIndex} of ${totalEmployees} employees`;

    // Update page numbers
    const pageNumbersDiv = document.getElementById('employeesPageNumbers');
    let pageNumbersHTML = '';

    if (totalPages <= 7) {
        for (let i = 1; i <= totalPages; i++) {
            pageNumbersHTML += `<button class="${i === currentEmployeesPage ? 'active' : ''}"
                onclick="goToEmployeesPage(${i})">${i}</button>`;
        }
    } else {
        if (currentEmployeesPage <= 4) {
            for (let i = 1; i <= 5; i++) {
                pageNumbersHTML += `<button class="${i === currentEmployeesPage ? 'active' : ''}"
                    onclick="goToEmployeesPage(${i})">${i}</button>`;
            }
            pageNumbersHTML += `<span>...</span>`;
            pageNumbersHTML += `<button onclick="goToEmployeesPage(${totalPages})">${totalPages}</button>`;
        } else if (currentEmployeesPage >= totalPages - 3) {
            pageNumbersHTML += `<button onclick="goToEmployeesPage(1)">1</button>`;
            pageNumbersHTML += `<span>...</span>`;
            for (let i = totalPages - 4; i <= totalPages; i++) {
                pageNumbersHTML += `<button class="${i === currentEmployeesPage ? 'active' : ''}"
                    onclick="goToEmployeesPage(${i})">${i}</button>`;
            }
        } else {
            pageNumbersHTML += `<button onclick="goToEmployeesPage(1)">1</button>`;
            pageNumbersHTML += `<span>...</span>`;
            for (let i = currentEmployeesPage - 1; i <= currentEmployeesPage + 1; i++) {
                pageNumbersHTML += `<button class="${i === currentEmployeesPage ? 'active' : ''}"
                    onclick="goToEmployeesPage(${i})">${i}</button>`;
            }
            pageNumbersHTML += `<span>...</span>`;
            pageNumbersHTML += `<button onclick="goToEmployeesPage(${totalPages})">${totalPages}</button>`;
        }
    }

    pageNumbersDiv.innerHTML = pageNumbersHTML;

    // Enable/disable navigation buttons
    document.getElementById('employeesFirstPage').disabled = currentEmployeesPage === 1;
    document.getElementById('employeesPrevPage').disabled = currentEmployeesPage === 1;
    document.getElementById('employeesNextPage').disabled = currentEmployeesPage === totalPages || totalPages === 0;
    document.getElementById('employeesLastPage').disabled = currentEmployeesPage === totalPages || totalPages === 0;
}

function changeEmployeesPage(direction) {
    const totalPages = Math.ceil(allEmployees.length / employeesPageSize);

    switch (direction) {
        case 'first':
            currentEmployeesPage = 1;
            break;
        case 'prev':
            currentEmployeesPage = Math.max(1, currentEmployeesPage - 1);
            break;
        case 'next':
            currentEmployeesPage = Math.min(totalPages, currentEmployeesPage + 1);
            break;
        case 'last':
            currentEmployeesPage = totalPages;
            break;
    }

    filterAndDisplayEmployees();
}

function goToEmployeesPage(pageNum) {
    currentEmployeesPage = pageNum;
    filterAndDisplayEmployees();
}

function changeEmployeesPageSize() {
    const pageSize = document.getElementById('employeesPageSize').value;
    employeesPageSize = pageSize === 'all' ? 'all' : parseInt(pageSize);
    currentEmployeesPage = 1;
    filterAndDisplayEmployees();
}

// Sorting function
function sortEmployeesTable(columnIndex, dataType) {
    // Store column being sorted
    const wasAscending = employeesSortColumn === columnIndex && employeesSortDirection === 'asc';
    employeesSortColumn = columnIndex;
    employeesSortDirection = wasAscending ? 'desc' : 'asc';

    // Update sort arrows
    document.querySelectorAll('#employeesTable .sort-arrow').forEach(arrow => {
        arrow.textContent = '';
    });

    const arrow = document.querySelectorAll('#employeesTable .sort-arrow')[columnIndex];
    arrow.textContent = employeesSortDirection === 'asc' ? '▲' : '▼';

    // Sort the data
    const columnMap = ['employee_code', 'name', 'position', 'email', 'phone', 'status'];
    const sortKey = columnMap[columnIndex];

    allEmployees.sort((a, b) => {
        let aVal, bVal;

        if (sortKey === 'name') {
            aVal = `${a.first_name} ${a.last_name}`.toLowerCase();
            bVal = `${b.first_name} ${b.last_name}`.toLowerCase();
        } else {
            aVal = (a[sortKey] || '').toString().toLowerCase();
            bVal = (b[sortKey] || '').toString().toLowerCase();
        }

        if (employeesSortDirection === 'asc') {
            return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
            return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
        }
    });

    filterAndDisplayEmployees();
}

// Load employees when the employees tab becomes active
document.addEventListener('DOMContentLoaded', function() {
    // Hook into tab switching to load employees when tab is shown
    const originalShowTab = window.showTab;
    window.showTab = function(tabName) {
        if (originalShowTab) {
            originalShowTab(tabName);
        }
        if (tabName === 'employees') {
            loadEmployees();
        }
    };
});
