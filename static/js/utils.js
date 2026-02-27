// WONTECH Shared Utilities
// Extracted from dashboard.js — shared across all domain modules

// ========== RENDER/LOAD REGISTRY ==========
// Domain modules register their render/load functions here
// so pagination and sorting can call them without hardcoded references
window.renderRegistry = {};
window.loadRegistry = {};

// ========== PAGINATION STATE ==========
const paginationState = {
    inventory: {
        currentPage: 1,
        pageSize: 25,
        totalItems: 0,
        allData: []
    },
    products: {
        currentPage: 1,
        pageSize: 10,
        totalItems: 0,
        allData: []
    },
    invoices: {
        currentPage: 1,
        pageSize: 25,
        totalItems: 0,
        allData: []
    },
    unreconciled: {
        currentPage: 1,
        pageSize: 10,
        totalItems: 0,
        allData: []
    },
    history: {
        currentPage: 1,
        pageSize: 25,
        totalItems: 0,
        allData: []
    }
};

// ========== FORMATTING FUNCTIONS ==========

function formatDateTime(dateString) {
    if (!dateString) return '-';

    try {
        const date = new Date(dateString.replace(' ', 'T'));
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    } catch (error) {
        console.error('Error formatting datetime:', dateString, error);
        return dateString;
    }
}

function formatDateOnly(dateString) {
    if (!dateString) return '-';

    try {
        const parts = dateString.split(/[- :T]/);
        const year = parseInt(parts[0]);
        const month = parseInt(parts[1]) - 1;
        const day = parseInt(parts[2]);

        const date = new Date(year, month, day);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    } catch (error) {
        console.error('Error formatting date:', dateString, error);
        return dateString;
    }
}

function formatDate(dateString) {
    return formatDateOnly(dateString);
}

function formatCurrency(value) {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

// ========== CATEGORY STYLING ==========

function getCategoryStyle(category) {
    const categoryStyles = {
        'Proteins': { icon: '🥩', colorClass: 'category-proteins' },
        'Seafood': { icon: '🦞', colorClass: 'category-seafood' },
        'Dairy': { icon: '🧀', colorClass: 'category-dairy' },
        'Produce': { icon: '🥬', colorClass: 'category-produce' },
        'Vegetables': { icon: '🥕', colorClass: 'category-vegetables' },
        'Fruits': { icon: '🍎', colorClass: 'category-fruits' },
        'Grains & Pasta': { icon: '🌾', colorClass: 'category-grains' },
        'Bread & Bakery': { icon: '🍞', colorClass: 'category-bread' },
        'Baking': { icon: '🧁', colorClass: 'category-baking' },
        'Spices & Seasonings': { icon: '🌶️', colorClass: 'category-spices' },
        'Herbs': { icon: '🌿', colorClass: 'category-herbs' },
        'Oils & Fats': { icon: '🫒', colorClass: 'category-oils' },
        'Sauces & Condiments': { icon: '🍯', colorClass: 'category-sauces' },
        'Beverages': { icon: '☕', colorClass: 'category-beverages' },
        'Canned Goods': { icon: '🥫', colorClass: 'category-canned' },
        'Frozen Foods': { icon: '❄️', colorClass: 'category-frozen' },
        'Prepared Foods': { icon: '🍱', colorClass: 'category-prepared' },
        'Snacks': { icon: '🍿', colorClass: 'category-snacks' },
        'Desserts': { icon: '🍰', colorClass: 'category-desserts' },
        'Specialty': { icon: '⭐', colorClass: 'category-specialty' },
        'Cleaning Supplies': { icon: '🧼', colorClass: 'category-cleaning' },
        'Paper Products': { icon: '🧻', colorClass: 'category-paper' },
        'Disposables': { icon: '🥤', colorClass: 'category-disposables' },
        'Uncategorized': { icon: '📦', colorClass: 'category-uncategorized' }
    };

    return categoryStyles[category] || { icon: '📦', colorClass: 'category-default' };
}

function formatCategoryBadge(category, itemId) {
    const style = getCategoryStyle(category);
    const escapedCategory = category.replace(/'/g, "\\'");

    const sizeClass = category.length > 18 ? 'category-long' : category.length > 12 ? 'category-medium' : '';

    return `<span class="badge category-badge ${style.colorClass} ${sizeClass} category-editable"
                  onclick="showCategoryDropdown(${itemId}, '${escapedCategory}')"
                  title="Click to change category">
                ${style.icon} ${category}
            </span>`;
}

// ========== PAGINATION HELPER FUNCTIONS ==========

function getPaginatedData(tableName) {
    const state = paginationState[tableName];
    const pageSize = state.pageSize === 'all' ? state.totalItems : parseInt(state.pageSize);
    const startIndex = (state.currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;

    return state.allData.slice(startIndex, endIndex);
}

function getTotalPages(tableName) {
    const state = paginationState[tableName];
    if (state.pageSize === 'all') return 1;
    return Math.ceil(state.totalItems / parseInt(state.pageSize));
}

function updatePaginationInfo(tableName, elementId) {
    const state = paginationState[tableName];
    const element = document.getElementById(elementId);

    if (!element || state.totalItems === 0) {
        if (element) element.textContent = 'Showing 0-0 of 0 items';
        return;
    }

    const pageSize = state.pageSize === 'all' ? state.totalItems : parseInt(state.pageSize);
    const startIndex = (state.currentPage - 1) * pageSize + 1;
    const endIndex = Math.min(startIndex + pageSize - 1, state.totalItems);

    element.textContent = `Showing ${startIndex}-${endIndex} of ${state.totalItems} items`;
}

function renderPageNumbers(tableName, elementId) {
    const state = paginationState[tableName];
    const element = document.getElementById(elementId);

    if (!element) return;

    const totalPages = getTotalPages(tableName);

    if (totalPages <= 1) {
        element.innerHTML = '';
        return;
    }

    let html = '';
    const maxButtons = 5;
    let startPage = Math.max(1, state.currentPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);

    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === state.currentPage ? 'active' : '';
        html += `<button class="page-number ${activeClass}" onclick="goToPage('${tableName}', ${i})">${i}</button>`;
    }

    element.innerHTML = html;
}

function updatePaginationButtons(tableName, prefix) {
    const state = paginationState[tableName];
    const totalPages = getTotalPages(tableName);

    const firstBtn = document.getElementById(`${prefix}FirstPage`);
    const prevBtn = document.getElementById(`${prefix}PrevPage`);
    const nextBtn = document.getElementById(`${prefix}NextPage`);
    const lastBtn = document.getElementById(`${prefix}LastPage`);

    if (firstBtn) firstBtn.disabled = state.currentPage === 1;
    if (prevBtn) prevBtn.disabled = state.currentPage === 1;
    if (nextBtn) nextBtn.disabled = state.currentPage >= totalPages;
    if (lastBtn) lastBtn.disabled = state.currentPage >= totalPages;
}

function goToPage(tableName, pageNumber) {
    const state = paginationState[tableName];
    const totalPages = getTotalPages(tableName);

    state.currentPage = Math.max(1, Math.min(pageNumber, totalPages));

    // Use the registry instead of hardcoded references
    if (window.renderRegistry[tableName]) {
        window.renderRegistry[tableName]();
    }
}

// ========== TOOLTIP FUNCTIONS ==========

const tooltip = document.getElementById('tooltip');
const tooltipContent = document.getElementById('tooltipContent');

function showTooltip(content, event) {
    tooltipContent.innerHTML = content;
    tooltip.classList.add('active');
    positionTooltip(event);
}

function hideTooltip() {
    tooltip.classList.remove('active');
    tooltip.style.display = 'none';
}

function positionTooltip(event) {
    tooltip.style.left = '-9999px';
    tooltip.style.top = '-9999px';
    tooltip.style.display = 'block';

    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width;
    const tooltipHeight = tooltipRect.height;

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    const offset = 15;

    let x = event.clientX + offset;
    let y = event.clientY + offset;

    if (x + tooltipWidth > viewportWidth - 10) {
        x = event.clientX - tooltipWidth - offset;
    }

    if (y + tooltipHeight > viewportHeight - 10) {
        y = event.clientY - tooltipHeight - offset;
    }

    if (x < 10) {
        x = 10;
    }

    if (y < 10) {
        y = 10;
    }

    if (tooltipWidth > viewportWidth - 20) {
        x = 10;
    }

    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
}

// ========== SORTING FUNCTIONS ==========

let sortState = {};

function sortTable(tableName, columnIndex, type) {
    const tableId = tableName + 'Table';
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');

    const key = `${tableName}-${columnIndex}`;
    if (!sortState[key]) {
        sortState[key] = { direction: 'none' };
    }

    if (sortState[key].direction === 'none') {
        sortState[key].direction = 'asc';
    } else if (sortState[key].direction === 'asc') {
        sortState[key].direction = 'desc';
    } else {
        sortState[key].direction = 'none';
    }

    // Handle paginated tables specially
    if (tableName === 'suppliers' || tableName === 'categories') {
        return sortPaginatedTable(tableName, columnIndex, type, key, table);
    }

    const rows = Array.from(tbody.querySelectorAll('tr'));

    table.querySelectorAll('.sort-arrow').forEach(arrow => {
        arrow.className = 'sort-arrow';
    });

    const header = table.querySelectorAll('th')[columnIndex];
    const arrow = header.querySelector('.sort-arrow');
    if (sortState[key].direction === 'asc') {
        arrow.className = 'sort-arrow sort-asc';
    } else if (sortState[key].direction === 'desc') {
        arrow.className = 'sort-arrow sort-desc';
    }

    if (sortState[key].direction === 'none') {
        // Use registry to reload data
        if (window.loadRegistry[tableName]) {
            window.loadRegistry[tableName]();
        }
        return;
    }

    rows.sort((rowA, rowB) => {
        const cellA = rowA.cells[columnIndex];
        const cellB = rowB.cells[columnIndex];

        let aValue = cellA.textContent.trim();
        let bValue = cellB.textContent.trim();

        if (type === 'number') {
            aValue = parseFloat(aValue.replace(/[$,]/g, '').split(' ')[0]) || 0;
            bValue = parseFloat(bValue.replace(/[$,]/g, '').split(' ')[0]) || 0;

            if (sortState[key].direction === 'asc') {
                return aValue - bValue;
            } else {
                return bValue - aValue;
            }
        } else if (type === 'date') {
            aValue = aValue === '-' ? new Date(0) : new Date(aValue);
            bValue = bValue === '-' ? new Date(0) : new Date(bValue);

            if (sortState[key].direction === 'asc') {
                return aValue - bValue;
            } else {
                return bValue - aValue;
            }
        } else {
            if (sortState[key].direction === 'asc') {
                return aValue.localeCompare(bValue);
            } else {
                return bValue.localeCompare(aValue);
            }
        }
    });

    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

function sortPaginatedTable(tableName, columnIndex, type, key, table) {
    const tableState = tableName === 'suppliers' ? suppliersTableState : categoriesTableState;

    table.querySelectorAll('.sort-arrow').forEach(arrow => {
        arrow.className = 'sort-arrow';
    });

    const header = table.querySelectorAll('th')[columnIndex];
    const arrow = header.querySelector('.sort-arrow');
    if (sortState[key].direction === 'asc') {
        arrow.className = 'sort-arrow sort-asc';
    } else if (sortState[key].direction === 'desc') {
        arrow.className = 'sort-arrow sort-desc';
    }

    if (sortState[key].direction === 'none') {
        if (tableName === 'suppliers') {
            loadSuppliersTable();
        } else {
            loadCategoriesTable();
        }
        return;
    }

    tableState.allData.sort((a, b) => {
        let aValue, bValue;

        if (tableName === 'suppliers') {
            const keys = ['supplier_name', 'contact_person', 'phone', 'email', 'address', 'payment_terms'];
            aValue = a[keys[columnIndex]] || '';
            bValue = b[keys[columnIndex]] || '';
        } else {
            const keys = ['category_name', 'item_count', 'created_at'];
            aValue = a[keys[columnIndex]] || '';
            bValue = b[keys[columnIndex]] || '';
        }

        if (type === 'number') {
            aValue = parseFloat(aValue) || 0;
            bValue = parseFloat(bValue) || 0;
            return sortState[key].direction === 'asc' ? aValue - bValue : bValue - aValue;
        } else if (type === 'date') {
            aValue = new Date(aValue || 0);
            bValue = new Date(bValue || 0);
            return sortState[key].direction === 'asc' ? aValue - bValue : bValue - aValue;
        } else {
            return sortState[key].direction === 'asc'
                ? String(aValue).localeCompare(String(bValue))
                : String(bValue).localeCompare(String(aValue));
        }
    });

    if (tableName === 'suppliers') {
        renderSuppliersTable();
    } else {
        renderCategoriesTable();
    }
}

// ========== GENERIC MODAL SYSTEM ==========

let modalState = {
    isOpen: false,
    currentModal: null
};

function openModal(title, bodyHTML, buttons = [], wide = false) {
    const modal = document.getElementById('genericModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    const modalFooter = document.getElementById('modalFooter');
    const modalContainer = modal.querySelector('.modal-container');

    if (!modal || !modalTitle || !modalBody || !modalFooter) {
        console.error('Modal elements not found');
        return;
    }

    modalTitle.textContent = title;

    const titleLower = title.toLowerCase();
    if (titleLower.includes('ingredient')) {
        modalTitle.setAttribute('data-modal', 'ingredient');
    } else if (titleLower.includes('supplier')) {
        modalTitle.setAttribute('data-modal', 'supplier');
    } else if (titleLower.includes('brand')) {
        modalTitle.setAttribute('data-modal', 'brand');
    } else if (titleLower.includes('product')) {
        modalTitle.setAttribute('data-modal', 'product');
    } else if (titleLower.includes('recipe')) {
        modalTitle.setAttribute('data-modal', 'recipe');
    } else if (titleLower.includes('category')) {
        modalTitle.setAttribute('data-modal', 'category');
    } else {
        modalTitle.removeAttribute('data-modal');
    }

    modalBody.innerHTML = bodyHTML;

    modalFooter.innerHTML = '';

    if (buttons.length === 0) {
        buttons = [{
            text: 'Close',
            className: 'modal-btn-secondary',
            onclick: closeModal
        }];
    }

    buttons.forEach(btn => {
        const button = document.createElement('button');
        button.className = `modal-btn ${btn.className || 'modal-btn-secondary'}`;
        button.textContent = btn.text;
        button.onclick = btn.onclick;
        modalFooter.appendChild(button);
    });

    if (wide) {
        modalContainer.classList.add('modal-wide');
    } else {
        modalContainer.classList.remove('modal-wide');
    }

    modal.style.display = 'flex';
    modal.classList.remove('closing');

    modalState.isOpen = true;
    modalState.currentModal = modal;

    document.body.style.overflow = 'hidden';

    modal.onclick = function(e) {
        if (e.target === modal) {
            closeModal();
        }
    };

    if (modalContainer) {
        modalContainer.onclick = function(e) {
            e.stopPropagation();
        };
    }

    document.addEventListener('keydown', handleModalEscape);
}

function closeModal() {
    const modal = document.getElementById('genericModal');

    if (!modal || !modalState.isOpen) {
        return;
    }

    modal.classList.add('closing');

    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('closing');

        document.getElementById('modalBody').innerHTML = '';
        document.getElementById('modalFooter').innerHTML = '';

        modalState.isOpen = false;
        modalState.currentModal = null;

        document.body.style.overflow = '';

        document.removeEventListener('keydown', handleModalEscape);
    }, 200);
}

function handleModalEscape(e) {
    if (e.key === 'Escape' && modalState.isOpen) {
        closeModal();
    }
}

function isModalOpen() {
    return modalState.isOpen;
}

// ========== FORM UTILITIES ==========

function createFormField(type, label, id, options = {}) {
    const required = options.required ? ' *' : '';
    const value = options.value || '';
    const placeholder = options.placeholder || '';
    const requiredAttr = options.required ? 'required' : '';

    let fieldHTML = '';

    switch (type) {
        case 'text':
        case 'email':
        case 'number':
            fieldHTML = `
                <div class="form-group">
                    <label for="${id}">${label}${required}</label>
                    <input
                        type="${type}"
                        id="${id}"
                        name="${id}"
                        class="form-control"
                        value="${value}"
                        placeholder="${placeholder}"
                        ${requiredAttr}
                        ${type === 'number' && options.min !== undefined ? `min="${options.min}"` : ''}
                        ${type === 'number' && options.max !== undefined ? `max="${options.max}"` : ''}
                        ${type === 'number' && options.step ? `step="${options.step}"` : ''}
                    />
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        case 'select':
            const optionsHTML = (options.options || []).map(opt => {
                const selected = opt.value === value ? 'selected' : '';
                return `<option value="${opt.value}" ${selected}>${opt.label}</option>`;
            }).join('');

            fieldHTML = `
                <div class="form-group">
                    <label for="${id}">${label}${required}</label>
                    <select
                        id="${id}"
                        name="${id}"
                        class="form-control"
                        ${requiredAttr}
                    >
                        <option value="">-- Select ${label} --</option>
                        ${optionsHTML}
                    </select>
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        case 'textarea':
            fieldHTML = `
                <div class="form-group">
                    <label for="${id}">${label}${required}</label>
                    <textarea
                        id="${id}"
                        name="${id}"
                        class="form-control"
                        rows="${options.rows || 3}"
                        placeholder="${placeholder}"
                        ${requiredAttr}
                    >${value}</textarea>
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        case 'checkbox':
            const checked = options.checked || value ? 'checked' : '';
            fieldHTML = `
                <div class="form-group form-group-checkbox">
                    <label class="checkbox-label">
                        <input
                            type="checkbox"
                            id="${id}"
                            name="${id}"
                            ${checked}
                        />
                        <span>${label}</span>
                    </label>
                    <div class="field-error" id="${id}-error"></div>
                </div>
            `;
            break;

        default:
            console.error(`Unknown field type: ${type}`);
    }

    return fieldHTML;
}

function createFormFieldWithOptGroups(type, label, id, options = {}) {
    const required = options.required ? ' *' : '';
    const requiredAttr = options.required ? 'required' : '';

    if (type === 'select') {
        let optgroupsHTML = '';

        if (options.optgroups) {
            optgroupsHTML = options.optgroups.map(group => {
                const groupOptions = group.options.map(opt =>
                    `<option value="${opt.value}">${opt.label}</option>`
                ).join('');

                return `<optgroup label="${group.label}">${groupOptions}</optgroup>`;
            }).join('');
        }

        return `
            <div class="form-group">
                <label for="${id}">${label}${required}</label>
                <select id="${id}" name="${id}" class="form-control" ${requiredAttr}>
                    <option value="">-- ${label} --</option>
                    ${optgroupsHTML}
                </select>
                <div class="field-error" id="${id}-error"></div>
            </div>
        `;
    }

    return createFormField(type, label, id, options);
}

function getFormData(formId) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');
    const data = {};

    container.querySelectorAll('input, select, textarea').forEach(field => {
        if (field.type === 'checkbox') {
            data[field.id || field.name] = field.checked;
        } else if (field.type === 'number') {
            data[field.id || field.name] = field.value ? parseFloat(field.value) : null;
        } else {
            data[field.id || field.name] = field.value;
        }
    });

    return data;
}

function setFormData(formId, data) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');

    Object.keys(data).forEach(key => {
        const field = container.querySelector(`#${key}, [name="${key}"]`);
        if (!field) return;

        if (field.type === 'checkbox') {
            field.checked = data[key];
        } else {
            field.value = data[key] || '';
        }
    });
}

function validateForm(formId) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');
    const errors = [];

    container.querySelectorAll('.field-error').forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });

    container.querySelectorAll('.form-control').forEach(field => {
        field.classList.remove('error');
    });

    container.querySelectorAll('[required]').forEach(field => {
        if (!field.value || (field.type === 'checkbox' && !field.checked)) {
            const label = container.querySelector(`label[for="${field.id}"]`)?.textContent || field.id;
            errors.push({
                field: field.id,
                message: `${label} is required`
            });
            showFieldError(field.id, `This field is required`);
        }
    });

    container.querySelectorAll('input[type="email"]').forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            errors.push({
                field: field.id,
                message: 'Invalid email format'
            });
            showFieldError(field.id, 'Invalid email format');
        }
    });

    container.querySelectorAll('input[type="number"]').forEach(field => {
        if (field.value) {
            const value = parseFloat(field.value);
            if (isNaN(value)) {
                errors.push({
                    field: field.id,
                    message: 'Must be a number'
                });
                showFieldError(field.id, 'Must be a number');
            } else {
                if (field.min && value < parseFloat(field.min)) {
                    errors.push({
                        field: field.id,
                        message: `Must be at least ${field.min}`
                    });
                    showFieldError(field.id, `Must be at least ${field.min}`);
                }
                if (field.max && value > parseFloat(field.max)) {
                    errors.push({
                        field: field.id,
                        message: `Must be at most ${field.max}`
                    });
                    showFieldError(field.id, `Must be at most ${field.max}`);
                }
            }
        }
    });

    return {
        valid: errors.length === 0,
        errors: errors
    };
}

function showFieldError(fieldId, message) {
    const errorEl = document.getElementById(`${fieldId}-error`);
    const field = document.getElementById(fieldId);

    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }

    if (field) {
        field.classList.add('error');
    }
}

function clearFormErrors(formId) {
    const container = document.getElementById(formId) || document.getElementById('modalBody');

    container.querySelectorAll('.field-error').forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });

    container.querySelectorAll('.form-control').forEach(field => {
        field.classList.remove('error');
    });
}

function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ========== DROPDOWN SELECTORS ==========

async function createIngredientSelector(id, label, selectedId = null, options = {}) {
    try {
        const response = await fetch('/api/ingredients/list');
        const ingredients = await response.json();

        let filteredIngredients = ingredients;
        if (options.includeComposite === false) {
            filteredIngredients = ingredients.filter(ing => !ing.is_composite);
        }

        const selectOptions = filteredIngredients.map(ing => ({
            value: ing.id,
            label: `${ing.ingredient_name} (${ing.unit_of_measure})`
        }));

        return createFormField('select', label, id, {
            ...options,
            value: selectedId,
            options: selectOptions
        });
    } catch (error) {
        console.error('Error loading ingredients:', error);
        return createFormField('select', label, id, {
            ...options,
            options: []
        });
    }
}

function createCategorySelector(id, label, selectedCategory = null, options = {}) {
    const categories = [
        'Produce', 'Meat', 'Dairy', 'Dry Goods', 'Spices',
        'Oils', 'Prepared Foods', 'Packaging', 'Beverages',
        'Frozen', 'Bakery', 'Seafood', 'Uncategorized'
    ];

    const selectOptions = categories.map(cat => ({
        value: cat,
        label: cat
    }));

    return createFormField('select', label, id, {
        ...options,
        value: selectedCategory,
        options: selectOptions
    });
}

function createUnitSelector(id, label, selectedUnit = null, options = {}) {
    const units = [
        'lb', 'oz', 'kg', 'g', 'gal', 'qt', 'pt', 'cup',
        'tbsp', 'tsp', 'each', 'case', 'box', 'bag', 'can', 'jar'
    ];

    const selectOptions = units.map(unit => ({
        value: unit,
        label: unit
    }));

    return createFormField('select', label, id, {
        ...options,
        value: selectedUnit,
        options: selectOptions
    });
}

async function createSupplierSelector(id, label, selectedSupplier = null, options = {}) {
    try {
        const response = await fetch('/api/suppliers/all');
        const suppliers = await response.json();

        const selectOptions = suppliers.map(supplier => ({
            value: supplier.supplier_name,
            label: supplier.supplier_name
        }));

        selectOptions.unshift({ value: '', label: '-- Select Supplier --' });

        const selectHTML = createFormField('select', label, id, {
            ...options,
            value: selectedSupplier,
            options: selectOptions
        });

        return `
            <div class="form-group-with-action">
                ${selectHTML}
                <button type="button" class="btn-create-inline" onclick="openCreateSupplierModal('${id}')">
                    + New Supplier
                </button>
            </div>
        `;
    } catch (error) {
        console.error('Error loading suppliers:', error);
        return createFormField('select', label, id, {
            ...options,
            options: [{ value: '', label: '-- Select Supplier --' }]
        });
    }
}

async function createBrandSelector(id, label, selectedBrand = null, options = {}) {
    try {
        const response = await fetch('/api/brands/list');
        const brands = await response.json();

        const selectOptions = brands.map(brand => ({
            value: brand.brand_name,
            label: brand.brand_name
        }));

        selectOptions.unshift({ value: '', label: '-- Select Brand --' });

        const selectHTML = createFormField('select', label, id, {
            ...options,
            value: selectedBrand,
            options: selectOptions
        });

        return `
            <div class="form-group-with-action">
                ${selectHTML}
                <button type="button" class="btn-create-inline" onclick="openCreateBrandModal('${id}')">
                    + New Brand
                </button>
            </div>
        `;
    } catch (error) {
        console.error('Error loading brands:', error);
        return createFormField('select', label, id, {
            ...options,
            options: [{ value: '', label: '-- Select Brand --' }]
        });
    }
}

// ========== NOTIFICATION SYSTEM ==========

let toastQueue = [];
let toastCounter = 0;

function showMessage(message, type = 'info', duration = 3000) {
    const toast = {
        id: toastCounter++,
        message,
        type,
        duration
    };

    toastQueue.push(toast);
    displayToast(toast);
}

function displayToast(toast) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toastEl = document.createElement('div');
    toastEl.id = `toast-${toast.id}`;
    toastEl.className = `toast toast-${toast.type}`;

    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    toastEl.innerHTML = `
        <span class="toast-icon">${icons[toast.type] || icons.info}</span>
        <span class="toast-message">${toast.message}</span>
        <button class="toast-close" onclick="closeToast(${toast.id})">&times;</button>
    `;

    container.appendChild(toastEl);

    setTimeout(() => {
        toastEl.classList.add('show');
    }, 10);

    setTimeout(() => {
        closeToast(toast.id);
    }, toast.duration);
}

function closeToast(toastId) {
    const toastEl = document.getElementById(`toast-${toastId}`);
    if (!toastEl) return;

    toastEl.classList.remove('show');
    toastEl.classList.add('hide');

    setTimeout(() => {
        toastEl.remove();

        toastQueue = toastQueue.filter(t => t.id !== toastId);

        const container = document.getElementById('toastContainer');
        if (container && container.children.length === 0) {
            container.remove();
        }
    }, 300);
}

// ========== API FETCH HELPER ==========

async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
}
