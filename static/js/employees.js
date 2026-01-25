/**
 * Employee Management JavaScript
 * Handles CRUD operations for employees
 */

let allEmployees = [];
let currentEmployeeId = null;

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
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px; color: #6b7280;">
                    No employees found
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = employees.map(emp => `
        <tr>
            <td><strong>${emp.employee_code}</strong></td>
            <td>${emp.first_name} ${emp.last_name}</td>
            <td>${emp.position || '-'}</td>
            <td>${emp.email || '-'}</td>
            <td>${emp.phone || '-'}</td>
            <td>
                <span class="status-badge status-${emp.status}">
                    ${emp.status === 'active' ? '✓' : '✕'} ${emp.status}
                </span>
            </td>
            <td>
                ${emp.user_id ? '<span style="color: #10b981;">✓ Yes</span>' : '<span style="color: #6b7280;">✕ No</span>'}
            </td>
            <td>
                <div class="action-buttons">
                    <button onclick="editEmployee(${emp.id})" class="btn-icon" title="Edit">
                        ✏️
                    </button>
                    <button onclick="deleteEmployee(${emp.id}, '${emp.first_name} ${emp.last_name}')"
                            class="btn-icon" title="Delete">
                        🗑️
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function searchEmployees() {
    filterAndDisplayEmployees();
}

function openCreateEmployeeModal() {
    currentEmployeeId = null;
    document.getElementById('employeeModalTitle').textContent = 'Add New Employee';
    document.getElementById('employeeForm').reset();
    document.getElementById('employeeId').value = '';
    document.getElementById('passwordFieldGroup').style.display = 'none';
    document.getElementById('createUserAccount').checked = false;
    document.getElementById('employeeFormError').style.display = 'none';
    document.getElementById('employeeModal').style.display = 'block';
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

                // Hide user account creation option when editing
                document.getElementById('createUserAccount').parentElement.parentElement.style.display = 'none';

                document.getElementById('employeeFormError').style.display = 'none';
                document.getElementById('employeeModal').style.display = 'block';
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
    document.getElementById('employeeModal').style.display = 'none';
    document.getElementById('employeeForm').reset();
    currentEmployeeId = null;
    // Show user account creation option again
    document.getElementById('createUserAccount').parentElement.parentElement.style.display = 'block';
}

function togglePasswordField() {
    const checkbox = document.getElementById('createUserAccount');
    const passwordField = document.getElementById('passwordFieldGroup');
    passwordField.style.display = checkbox.checked ? 'block' : 'none';
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
        hourly_rate: document.getElementById('employeeHourlyRate').value || 0,
        create_user_account: document.getElementById('createUserAccount')?.checked || false,
        password: document.getElementById('employeePassword')?.value || ''
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
