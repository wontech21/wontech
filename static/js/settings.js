// WONTECH Settings Module
// Supplier CRUD, category CRUD, bulk edit, settings tab

// Register with global registries
window.renderRegistry['suppliers'] = renderSuppliersTable;
window.renderRegistry['categories'] = renderCategoriesTable;
window.loadRegistry['suppliers'] = loadSuppliersTable;
window.loadRegistry['categories'] = loadCategoriesTable;

// ============================================================
// Settings Tab Functions
// ============================================================

async function loadSettings() {
    // Load brands, suppliers, and categories
    await Promise.all([
        loadBrandsList(),
        loadSuppliersList(),
        loadSuppliersTable(),
        loadCategoriesTable()
    ]);
}

async function loadBrandsList() {
    try {
        const response = await fetch('/api/filters/brands');
        const brands = await response.json();

        const select = document.getElementById('brandSelect');
        select.innerHTML = '<option value="">-- Select a brand --</option>';

        brands.forEach(brand => {
            const option = document.createElement('option');
            option.value = brand;
            option.textContent = brand;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading brands:', error);
    }
}

async function loadSuppliersList() {
    try {
        const response = await fetch('/api/filters/suppliers');
        const suppliers = await response.json();

        const select = document.getElementById('supplierSelect');
        select.innerHTML = '<option value="">-- Select a supplier --</option>';

        suppliers.forEach(supplier => {
            const option = document.createElement('option');
            option.value = supplier;
            option.textContent = supplier;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading suppliers:', error);
    }
}

async function updateBrandPreview() {
    const brandSelect = document.getElementById('brandSelect');
    const selectedBrand = brandSelect.value;
    const preview = document.getElementById('brandPreview');

    if (!selectedBrand) {
        preview.innerHTML = '';
        preview.classList.remove('show');
        return;
    }

    try {
        const response = await fetch(`/api/inventory/detailed?brand=${encodeURIComponent(selectedBrand)}`);
        const items = await response.json();

        preview.innerHTML = `<strong>${items.length}</strong> item(s) will be updated`;
        preview.classList.add('show');
    } catch (error) {
        console.error('Error getting brand preview:', error);
        preview.innerHTML = 'Error loading preview';
    }
}

async function updateSupplierPreview() {
    const supplierSelect = document.getElementById('supplierSelect');
    const selectedSupplier = supplierSelect.value;
    const preview = document.getElementById('supplierPreview');

    if (!selectedSupplier) {
        preview.innerHTML = '';
        preview.classList.remove('show');
        return;
    }

    try {
        const response = await fetch(`/api/inventory/detailed?supplier=${encodeURIComponent(selectedSupplier)}`);
        const items = await response.json();

        preview.innerHTML = `<strong>${items.length}</strong> item(s) will be updated`;
        preview.classList.add('show');
    } catch (error) {
        console.error('Error getting supplier preview:', error);
        preview.innerHTML = 'Error loading preview';
    }
}

async function bulkUpdateBrand() {
    const oldBrand = document.getElementById('brandSelect').value;
    const newBrand = document.getElementById('newBrandName').value.trim();

    if (!oldBrand) {
        alert('Please select a brand to update');
        return;
    }

    if (!newBrand) {
        alert('Please enter a new brand name');
        return;
    }

    if (oldBrand === newBrand) {
        alert('New brand name must be different from the current name');
        return;
    }

    if (!confirm(`Are you sure you want to rename all items from "${oldBrand}" to "${newBrand}"?`)) {
        return;
    }

    try {
        const response = await fetch('/api/inventory/bulk-update-brand', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                old_brand: oldBrand,
                new_brand: newBrand
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            document.getElementById('brandSelect').value = '';
            document.getElementById('newBrandName').value = '';
            document.getElementById('brandPreview').innerHTML = '';

            const brandFilter = document.getElementById('brandFilter');
            if (brandFilter && brandFilter.value === oldBrand) {
                brandFilter.value = 'all';
            }

            await Promise.all([
                loadBrandsList(),
                loadBrandsFilter(),
                loadHeaderStats(),
                loadInventory(),
                loadProducts(),
                loadInvoices()
            ]);
        } else {
            alert('Error updating brand: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating brand:', error);
        alert('Error updating brand');
    }
}

async function bulkUpdateSupplier() {
    const oldSupplier = document.getElementById('supplierSelect').value;
    const newSupplier = document.getElementById('newSupplierName').value.trim();

    if (!oldSupplier) {
        alert('Please select a supplier to update');
        return;
    }

    if (!newSupplier) {
        alert('Please enter a new supplier name');
        return;
    }

    if (oldSupplier === newSupplier) {
        alert('New supplier name must be different from the current name');
        return;
    }

    if (!confirm(`Are you sure you want to rename all items from "${oldSupplier}" to "${newSupplier}"?`)) {
        return;
    }

    try {
        const response = await fetch('/api/inventory/bulk-update-supplier', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                old_supplier: oldSupplier,
                new_supplier: newSupplier
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            document.getElementById('supplierSelect').value = '';
            document.getElementById('newSupplierName').value = '';
            document.getElementById('supplierPreview').innerHTML = '';

            const supplierFilter = document.getElementById('supplierFilter');
            if (supplierFilter && supplierFilter.value === oldSupplier) {
                supplierFilter.value = 'all';
            }

            await Promise.all([
                loadSuppliersList(),
                loadSuppliersFilter(),
                loadHeaderStats(),
                loadInventory(),
                loadProducts(),
                loadInvoices()
            ]);
        } else {
            alert('Error updating supplier: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating supplier:', error);
        alert('Error updating supplier');
    }
}

// ============================================================
// Supplier Management Functions
// ============================================================

// Suppliers table pagination state
const suppliersTableState = {
    allData: [],
    currentPage: 1,
    pageSize: 10
};

async function loadSuppliersTable() {
    try {
        const response = await fetch('/api/suppliers/all');
        const suppliers = await response.json();

        suppliersTableState.allData = suppliers;
        suppliersTableState.currentPage = 1;

        renderSuppliersTable();
    } catch (error) {
        console.error('Error loading suppliers:', error);
        document.getElementById('suppliersTableBody').innerHTML =
            '<tr><td colspan="7" class="text-center text-danger">Error loading suppliers</td></tr>';
    }
}

function renderSuppliersTable() {
    const tbody = document.getElementById('suppliersTableBody');
    const { allData, currentPage, pageSize } = suppliersTableState;

    if (allData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No suppliers found. Create your first supplier!</td></tr>';
        updateSuppliersPagination();
        return;
    }

    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = allData.slice(startIdx, endIdx);

    tbody.innerHTML = pageData.map(supplier => {
        const escapedName = (supplier.supplier_name || '').replace(/'/g, "\\'");
        return `
            <tr>
                <td><strong>${supplier.supplier_name || '-'}</strong></td>
                <td>${supplier.contact_person || '-'}</td>
                <td>${supplier.phone || '-'}</td>
                <td>${supplier.email || '-'}</td>
                <td>${supplier.address || '-'}</td>
                <td>${supplier.payment_terms || '-'}</td>
                <td class="actions-cell">
                    <button class="btn-edit-dark" onclick="editSupplierProfile(${supplier.id})" title="Edit"><span style="font-weight: 700;">✏️</span></button>
                    <button class="btn-delete-dark" onclick="deleteSupplierProfile(${supplier.id}, '${escapedName}')" title="Delete"><span style="font-weight: 700;">🗑️</span></button>
                </td>
            </tr>
        `;
    }).join('');

    updateSuppliersPagination();
}

function updateSuppliersPagination() {
    const { allData, currentPage, pageSize } = suppliersTableState;
    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, allData.length);

    const paginationDiv = document.getElementById('suppliersPagination');
    if (!paginationDiv) return;

    if (allData.length === 0) {
        paginationDiv.innerHTML = '';
        return;
    }

    paginationDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: white; border-radius: 8px;">
            <div>Showing ${startIdx + 1}-${endIdx} of ${allData.length} suppliers</div>
            <div style="display: flex; gap: 10px; align-items: center;">
                <button class="btn btn-secondary" onclick="changeSuppliersPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                    ← Previous
                </button>
                <span>Page ${currentPage} of ${totalPages}</span>
                <button class="btn btn-secondary" onclick="changeSuppliersPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                    Next →
                </button>
            </div>
        </div>
    `;
}

function changeSuppliersPage(newPage) {
    const totalPages = Math.ceil(suppliersTableState.allData.length / suppliersTableState.pageSize);
    if (newPage < 1 || newPage > totalPages) return;

    suppliersTableState.currentPage = newPage;
    renderSuppliersTable();
}

function openCreateSupplierModal() {
    document.getElementById('supplierModalTitle').textContent = 'Create New Supplier';
    document.getElementById('supplierEditId').value = '';
    document.getElementById('supplierForm').reset();
    document.getElementById('supplierModal').classList.add('active');
}

async function editSupplierProfile(supplierId) {
    try {
        const response = await fetch('/api/suppliers/all');
        const suppliers = await response.json();
        const supplier = suppliers.find(s => s.id === supplierId);

        if (!supplier) {
            alert('Supplier not found');
            return;
        }

        document.getElementById('supplierModalTitle').textContent = 'Edit Supplier';
        document.getElementById('supplierEditId').value = supplier.id;
        document.getElementById('supplierName').value = supplier.supplier_name || '';
        document.getElementById('supplierContact').value = supplier.contact_person || '';
        document.getElementById('supplierPhone').value = supplier.phone || '';
        document.getElementById('supplierEmail').value = supplier.email || '';
        document.getElementById('supplierAddress').value = supplier.address || '';
        document.getElementById('supplierPaymentTerms').value = supplier.payment_terms || '';
        document.getElementById('supplierNotes').value = supplier.notes || '';

        document.getElementById('supplierModal').classList.add('active');
    } catch (error) {
        console.error('Error loading supplier:', error);
        alert('Error loading supplier details');
    }
}

function closeSupplierModal() {
    document.getElementById('supplierModal').classList.remove('active');
    document.getElementById('supplierForm').reset();
}

async function saveSupplier(event) {
    event.preventDefault();

    const supplierId = document.getElementById('supplierEditId').value;
    const isEdit = supplierId !== '';

    const data = {
        supplier_name: document.getElementById('supplierName').value,
        contact_person: document.getElementById('supplierContact').value || null,
        phone: document.getElementById('supplierPhone').value || null,
        email: document.getElementById('supplierEmail').value || null,
        address: document.getElementById('supplierAddress').value || null,
        payment_terms: document.getElementById('supplierPaymentTerms').value || null,
        notes: document.getElementById('supplierNotes').value || null
    };

    try {
        const url = isEdit ? `/api/suppliers/update/${supplierId}` : '/api/suppliers/create';
        const method = isEdit ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            closeSupplierModal();

            await Promise.all([
                loadSuppliersTable(),
                loadSuppliersList(),
                loadSuppliersFilter()
            ]);
        } else {
            alert('Error saving supplier: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving supplier:', error);
        alert('Error saving supplier');
    }
}

async function deleteSupplierProfile(supplierId, supplierName) {
    if (!confirm(`Are you sure you want to delete supplier "${supplierName}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/suppliers/delete/${supplierId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);

            await Promise.all([
                loadSuppliersTable(),
                loadSuppliersList(),
                loadSuppliersFilter()
            ]);
        } else {
            alert('Error deleting supplier: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting supplier:', error);
        alert('Error deleting supplier');
    }
}

// Close supplier modal when clicking outside
window.addEventListener('click', function(event) {
    const supplierModal = document.getElementById('supplierModal');
    if (event.target === supplierModal) {
        closeSupplierModal();
    }
});

// ============================================================
// Category Management Functions (Settings Tab)
// ============================================================

// Categories table pagination state
const categoriesTableState = {
    allData: [],
    currentPage: 1,
    pageSize: 10
};

async function loadCategoriesTable() {
    try {
        const response = await fetch('/api/categories/all');
        const categories = await response.json();

        categoriesTableState.allData = categories;
        categoriesTableState.currentPage = 1;

        renderCategoriesTable();
    } catch (error) {
        console.error('Error loading categories:', error);
        document.getElementById('categoriesTableBody').innerHTML =
            '<tr><td colspan="4" class="text-center text-danger">Error loading categories</td></tr>';
    }
}

function renderCategoriesTable() {
    const tbody = document.getElementById('categoriesTableBody');
    const { allData, currentPage, pageSize } = categoriesTableState;

    if (allData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">No categories found</td></tr>';
        updateCategoriesPagination();
        return;
    }

    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = allData.slice(startIdx, endIdx);

    tbody.innerHTML = pageData.map(category => {
        const escapedName = (category.category_name || '').replace(/'/g, "\\'");
        const isUncategorized = category.category_name === 'Uncategorized';
        const canDelete = category.item_count === 0 && !isUncategorized;
        const canEdit = !isUncategorized;

        const editButton = canEdit
            ? `<button class="btn-edit-dark" onclick="editCategoryFromSettings(${category.id}, '${escapedName}')" title="Edit"><span style="font-weight: 700;">✏️</span></button>`
            : `<button class="btn-edit-dark btn-disabled" title="Cannot edit Uncategorized"><span style="font-weight: 700;">✏️</span></button>`;

        let deleteButton;
        if (isUncategorized) {
            deleteButton = `<button class="btn-delete-dark btn-disabled" title="Cannot delete Uncategorized"><span style="font-weight: 700;">🗑️</span></button>`;
        } else if (category.item_count > 0) {
            deleteButton = `<button class="btn-delete-dark btn-disabled" title="Category in use by ${category.item_count} item(s) - reassign them first"><span style="font-weight: 700;">🗑️</span></button>`;
        } else {
            deleteButton = `<button class="btn-delete-dark" onclick="deleteCategoryFromSettings(${category.id}, '${escapedName}')" title="Delete"><span style="font-weight: 700;">🗑️</span></button>`;
        }

        return `
            <tr>
                <td><strong>${category.category_name}</strong></td>
                <td class="text-center">${category.item_count}</td>
                <td><small>${formatDateTime(category.created_at)}</small></td>
                <td class="actions-cell">
                    ${editButton}
                    ${deleteButton}
                </td>
            </tr>
        `;
    }).join('');

    updateCategoriesPagination();
}

function updateCategoriesPagination() {
    const { allData, currentPage, pageSize } = categoriesTableState;
    const totalPages = Math.ceil(allData.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, allData.length);

    const paginationDiv = document.getElementById('categoriesPagination');
    if (!paginationDiv) return;

    if (allData.length === 0) {
        paginationDiv.innerHTML = '';
        return;
    }

    paginationDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: white; border-radius: 8px;">
            <div>Showing ${startIdx + 1}-${endIdx} of ${allData.length} categories</div>
            <div style="display: flex; gap: 10px; align-items: center;">
                <button class="btn btn-secondary" onclick="changeCategoriesPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                    ← Previous
                </button>
                <span>Page ${currentPage} of ${totalPages}</span>
                <button class="btn btn-secondary" onclick="changeCategoriesPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                    Next →
                </button>
            </div>
        </div>
    `;
}

function changeCategoriesPage(newPage) {
    const totalPages = Math.ceil(categoriesTableState.allData.length / categoriesTableState.pageSize);
    if (newPage < 1 || newPage > totalPages) return;

    categoriesTableState.currentPage = newPage;
    renderCategoriesTable();
}

function openCreateCategoryModal() {
    document.getElementById('categoryForm').reset();
    document.getElementById('categoryEditId').value = '';
    document.getElementById('categoryOldName').value = '';

    document.getElementById('categoryModalTitle').textContent = 'Create New Category';
    document.getElementById('categorySaveBtn').textContent = 'Create Category';
    document.getElementById('categoryHelpText').style.display = 'none';

    document.getElementById('categoryModal').classList.add('active');
}

function editCategoryFromSettings(categoryId, categoryName) {
    document.getElementById('categoryEditId').value = categoryId;
    document.getElementById('categoryOldName').value = categoryName;
    document.getElementById('categoryName').value = categoryName;

    document.getElementById('categoryModalTitle').textContent = 'Edit Category';
    document.getElementById('categorySaveBtn').textContent = 'Save Changes';
    document.getElementById('categoryHelpText').style.display = 'block';

    document.getElementById('categoryModal').classList.add('active');
}

function closeCategoryModal() {
    document.getElementById('categoryModal').classList.remove('active');
    document.getElementById('categoryForm').reset();
}

async function saveCategory(event) {
    event.preventDefault();

    const categoryId = document.getElementById('categoryEditId').value;
    const newName = document.getElementById('categoryName').value.trim();
    const oldName = document.getElementById('categoryOldName').value;

    const isCreate = !categoryId;

    if (!isCreate && newName === oldName) {
        alert('Category name is unchanged');
        return;
    }

    try {
        let response;

        if (isCreate) {
            response = await fetch('/api/categories/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    category_name: newName
                })
            });
        } else {
            response = await fetch(`/api/categories/update/${categoryId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    category_name: newName
                })
            });
        }

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);
            closeCategoryModal();

            await Promise.all([
                loadCategoriesTable(),
                loadCategoriesList(),
                loadCategoriesFilter(),
                loadInventory()
            ]);
        } else {
            alert('❌ Error saving category: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving category:', error);
        alert('❌ Error saving category');
    }
}

async function deleteCategoryFromSettings(categoryId, categoryName) {
    if (!confirm(`Are you sure you want to delete the category "${categoryName}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/categories/delete/${categoryId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.message}`);

            await Promise.all([
                loadCategoriesTable(),
                loadCategoriesList(),
                loadCategoriesFilter()
            ]);
        } else {
            alert('❌ Error deleting category: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting category:', error);
        alert('❌ Error deleting category');
    }
}

// Close modals when clicking outside
window.addEventListener('click', function(event) {
    const categoryModal = document.getElementById('categoryModal');
    if (event.target === categoryModal) {
        closeCategoryModal();
    }
});
