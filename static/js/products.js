// WONTECH Products Module
// Product loading/rendering, product CRUD (Layer 3), recipe builder

// Register with global registries
window.renderRegistry['products'] = renderProductsTable;
window.loadRegistry['products'] = loadProducts;

// ========== PRODUCTS PAGINATION FUNCTIONS ==========

function changeProductsPageSize() {
    const select = document.getElementById('productsPageSize');
    paginationState.products.pageSize = select.value;
    paginationState.products.currentPage = 1;
    renderProductsTable();
}

function changeProductsPage(direction) {
    const state = paginationState.products;
    const totalPages = getTotalPages('products');

    switch(direction) {
        case 'first':
            state.currentPage = 1;
            break;
        case 'prev':
            state.currentPage = Math.max(1, state.currentPage - 1);
            break;
        case 'next':
            state.currentPage = Math.min(totalPages, state.currentPage + 1);
            break;
        case 'last':
            state.currentPage = totalPages;
            break;
    }

    renderProductsTable();
}

// Load products and costs
async function loadProducts() {
    try {
        const response = await fetch('/api/products/costs');
        const products = await response.json();

        // Store data in pagination state
        paginationState.products.allData = products;
        paginationState.products.totalItems = products.length;
        paginationState.products.currentPage = 1;

        // Render the table with pagination
        renderProductsTable();
    } catch (error) {
        console.error('Error loading products:', error);
        document.getElementById('productsTableBody').innerHTML =
            '<tr><td colspan="5" class="text-danger">Error loading products</td></tr>';
    }
}

// Render products table with pagination
function renderProductsTable() {
    const tbody = document.getElementById('productsTableBody');
    const products = getPaginatedData('products');

    if (paginationState.products.totalItems === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No products found</td></tr>';
        updatePaginationInfo('products', 'productsPaginationInfo');
        return;
    }

    tbody.innerHTML = products.map((product, index) => {
        const marginClass = product.margin_pct < 0 ? 'text-danger' : 'text-success';
        const rowId = `product-row-${index}`;
        const detailsId = `product-details-${index}`;
        return `
            <tr class="hoverable-row product-row" id="${rowId}"
                data-product-index="${index}"
                data-details-id="${detailsId}"
                data-row-id="${rowId}"
                data-product-id="${product.product_id}">
                <td class="product-name-cell">
                    <span class="expand-icon" id="${rowId}-icon">▶</span>
                    <strong>${product.product_name}</strong>
                </td>
                <td class="text-right">${formatCurrency(product.ingredient_cost)}</td>
                <td class="text-right"><strong>${formatCurrency(product.selling_price)}</strong></td>
                <td class="text-right ${marginClass}"><strong>${formatCurrency(product.gross_profit)}</strong></td>
                <td class="text-right ${marginClass}"><strong>${product.margin_pct}%</strong></td>
                <td class="actions-cell">
                    <button class="btn-edit-dark"
                            onclick="event.stopPropagation(); openEditProductModal(${product.product_id})"
                            title="Edit Product">
                        <span style="font-weight: 700;">✏️</span>
                    </button>
                    <button class="btn-delete-dark"
                            onclick="event.stopPropagation(); deleteProduct(${product.product_id}, '${product.product_name.replace(/'/g, "\\'")}')"
                            title="Delete Product">
                        <span style="font-weight: 700;">🗑️</span>
                    </button>
                </td>
            </tr>
            <tr class="product-details-row" id="${detailsId}" style="display: none;">
                <td colspan="6">
                    <div class="product-ingredients-container">
                        <div class="loading-spinner">Loading ingredients...</div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    // Add click event listeners to product rows (for expand/collapse)
    tbody.querySelectorAll('.product-row').forEach(row => {
        row.addEventListener('click', function(event) {
            // Don't expand if clicking on action buttons
            if (event.target.closest('.actions-cell')) {
                return;
            }
            const productIndex = parseInt(this.getAttribute('data-product-index'));
            const product = products[productIndex];
            const detailsId = this.getAttribute('data-details-id');
            const rowId = this.getAttribute('data-row-id');
            toggleProductDetails(product.product_name, detailsId, rowId);
        });
    });

    // Update pagination controls
    updatePaginationInfo('products', 'productsPaginationInfo');
    renderPageNumbers('products', 'productsPageNumbers');
    updatePaginationButtons('products', 'products');
}

// Toggle product ingredient details
async function toggleProductDetails(productName, detailsId, rowId) {
    const detailsRow = document.getElementById(detailsId);
    const icon = document.getElementById(`${rowId}-icon`);

    if (detailsRow.style.display === 'none') {
        // Expand - load ingredient details
        detailsRow.style.display = 'table-row';
        icon.textContent = '▼';

        // Check if already loaded
        const container = detailsRow.querySelector('.product-ingredients-container');
        if (container.querySelector('.loading-spinner')) {
            try {
                const url = `/api/recipes/by-product/${encodeURIComponent(productName)}`;
                const response = await fetch(url);
                const ingredients = await response.json();

                if (ingredients.length === 0) {
                    container.innerHTML = '<p style="padding: 15px; color: #6c757d;">No recipe found for this product</p>';
                    return;
                }

                const totalCost = ingredients.reduce((sum, ing) => sum + ing.line_cost, 0);

                container.innerHTML = `
                    <div class="product-recipe-details">
                        <h4>Recipe Ingredients</h4>
                        <table class="ingredients-table">
                            <thead>
                                <tr>
                                    <th>Ingredient</th>
                                    <th>Quantity Needed</th>
                                    <th>Unit Cost</th>
                                    <th>Line Cost</th>
                                    <th>Notes</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${ingredients.map(ing => {
                                    let rows = `
                                        <tr class="${ing.is_composite ? 'composite-ingredient' : ''} ${ing.is_product ? 'product-ingredient' : ''}">
                                            <td>
                                                <strong>${ing.ingredient_name}</strong>
                                                ${ing.is_composite ? '<span class="composite-badge">🔧 Composite</span>' : ''}
                                                ${ing.is_product ? '<span class="badge badge-product">🍔 Product</span>' : ''}
                                            </td>
                                            <td class="text-right">${ing.quantity_needed} ${ing.unit_of_measure}</td>
                                            <td class="text-right">${formatCurrency(ing.unit_cost)}</td>
                                            <td class="text-right"><strong>${formatCurrency(ing.line_cost)}</strong></td>
                                            <td><small style="color: #6c757d;">${ing.notes || '-'}</small></td>
                                        </tr>
                                    `;

                                    // If composite, show sub-recipe
                                    if (ing.is_composite && ing.sub_recipe && ing.sub_recipe.length > 0) {
                                        rows += `
                                            <tr class="sub-recipe-row">
                                                <td colspan="5">
                                                    <div class="sub-recipe-container">
                                                        <div class="sub-recipe-header">↳ Made from:</div>
                                                        <table class="sub-recipe-table">
                                                            ${ing.sub_recipe.map(sub => `
                                                                <tr>
                                                                    <td>${sub.ingredient_name}</td>
                                                                    <td class="text-right">${sub.quantity_needed} ${sub.unit_of_measure}</td>
                                                                    <td class="text-right">${formatCurrency(sub.unit_cost)}</td>
                                                                    <td class="text-right">${formatCurrency(sub.line_cost)}</td>
                                                                    <td><small style="color: #6c757d;">${sub.notes || '-'}</small></td>
                                                                </tr>
                                                            `).join('')}
                                                        </table>
                                                    </div>
                                                </td>
                                            </tr>
                                        `;
                                    }

                                    return rows;
                                }).join('')}
                            </tbody>
                            <tfoot>
                                <tr>
                                    <td colspan="3" class="text-right"><strong>Total Ingredient Cost:</strong></td>
                                    <td class="text-right"><strong>${formatCurrency(totalCost)}</strong></td>
                                    <td></td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                `;
            } catch (error) {
                console.error('Error loading recipe details:', error);
                container.innerHTML = '<p style="padding: 15px; color: #dc3545;">Error loading recipe details</p>';
            }
        }
    } else {
        // Collapse
        detailsRow.style.display = 'none';
        icon.textContent = '▶';
    }
}

async function showProductRowTooltip(productName, ingredientCost, event) {
    try {
        const response = await fetch(`/api/recipes/by-product/${encodeURIComponent(productName)}`);
        const recipe = await response.json();

        if (recipe.length === 0) {
            showTooltip(`<h4>${productName}</h4><p>No recipe found</p>`, event);
            return;
        }

        const content = `
            <h4>${productName} - Ingredient Breakdown</h4>
            <table>
                ${recipe.map(item => `
                    <tr>
                        <td>${item.ingredient_name}</td>
                        <td class="text-right">${item.quantity_needed} ${item.unit_of_measure} × ${formatCurrency(item.unit_cost)}</td>
                        <td class="text-right"><strong>${formatCurrency(item.line_cost)}</strong></td>
                    </tr>
                `).join('')}
            </table>
            <div class="tooltip-total">Total Ingredient Cost: ${formatCurrency(ingredientCost)}</div>
        `;

        showTooltip(content, event);
    } catch (error) {
        console.error('Error loading product row tooltip:', error);
    }
}

// Show recipe on product name hover
async function showRecipeTooltip(productName, event) {
    try {
        const response = await fetch(`/api/recipes/by-product/${encodeURIComponent(productName)}`);
        const recipe = await response.json();

        if (recipe.length === 0) {
            showTooltip(`<h4>${productName}</h4><p>No recipe found</p>`, event);
            return;
        }

        const totalCost = recipe.reduce((sum, item) => sum + item.line_cost, 0);

        const content = `
            <h4>${productName} - Recipe</h4>
            <table>
                ${recipe.map(item => `
                    <tr>
                        <td>${item.ingredient_name}</td>
                        <td class="text-right">${item.quantity_needed} ${item.unit_of_measure}</td>
                        <td class="text-right">${formatCurrency(item.line_cost)}</td>
                    </tr>
                `).join('')}
            </table>
            <div class="tooltip-total">Total Cost: ${formatCurrency(totalCost)}</div>
        `;

        showTooltip(content, event);
    } catch (error) {
        console.error('Error loading recipe tooltip:', error);
    }
}

// Show cost breakdown on ingredient cost hover
async function showCostBreakdownTooltip(productName, event) {
    try {
        const response = await fetch(`/api/recipes/by-product/${encodeURIComponent(productName)}`);
        const recipe = await response.json();

        if (recipe.length === 0) {
            return;
        }

        const content = `
            <h4>${productName} - Cost Breakdown</h4>
            <table>
                ${recipe.map(item => `
                    <tr>
                        <td>${item.ingredient_name}</td>
                        <td class="text-right">${item.quantity_needed} ${item.unit_of_measure} × ${formatCurrency(item.unit_cost)}</td>
                        <td class="text-right"><strong>${formatCurrency(item.line_cost)}</strong></td>
                    </tr>
                `).join('')}
            </table>
        `;

        showTooltip(content, event);
    } catch (error) {
        console.error('Error loading cost breakdown:', error);
    }
}

// ========================================
// LAYER 3: PRODUCT MANAGEMENT
// ========================================

// Global state for recipe builder
let currentRecipeIngredients = [];

/**
 * Open Create Product Modal
 */
async function openCreateProductModal() {
    // Load available ingredients AND products for recipe builder
    let availableIngredients = [];
    let availableProducts = [];
    try {
        const response = await fetch('/api/ingredients-and-products/list');
        const data = await response.json();
        availableIngredients = data.ingredients;
        availableProducts = data.products;
    } catch (error) {
        console.error('Error loading ingredients and products:', error);
    }

    // Reset recipe state
    currentRecipeIngredients = [];

    const bodyHTML = `
        <div id="productForm">
            <div class="form-section">
                <h3 class="section-title">Product Details</h3>
                ${createFormField('text', 'Product Code', 'productCode', {
                    required: true,
                    placeholder: 'e.g., BURGER-001, TACO-MIX'
                })}
                ${createFormField('text', 'Product Name', 'productName', {
                    required: true,
                    placeholder: 'e.g., Classic Cheeseburger, Beef Tacos'
                })}
                ${createFormField('select', 'Category', 'productCategory', {
                    required: true,
                    options: [
                        { value: '', label: '-- Select Category --' },
                        { value: 'Entrees', label: 'Entrees' },
                        { value: 'Sides', label: 'Sides' },
                        { value: 'Sauces', label: 'Sauces' },
                        { value: 'Pizza', label: 'Pizza' },
                        { value: 'Prepared Foods', label: 'Prepared Foods' }
                    ]
                })}
                ${createFormField('select', 'Unit of Measure', 'productUnit', {
                    required: true,
                    options: [
                        { value: '', label: '-- Select Unit --' },
                        { value: 'each', label: 'Each' },
                        { value: 'dozen', label: 'Dozen' },
                        { value: 'lbs', label: 'Pounds (lbs)' },
                        { value: 'oz', label: 'Ounces (oz)' },
                        { value: 'serving', label: 'Serving' }
                    ]
                })}
                ${createFormField('number', 'Selling Price', 'productPrice', {
                    required: true,
                    placeholder: '9.99',
                    step: '0.01',
                    min: '0'
                })}
                ${createFormField('number', 'Quantity on Hand', 'productQuantity', {
                    required: true,
                    placeholder: '0',
                    value: '0',
                    step: '0.01',
                    min: '0'
                })}
                ${createFormField('number', 'Shelf Life (Days)', 'productShelfLife', {
                    placeholder: 'e.g., 3, 7, 30',
                    min: '0'
                })}
                ${createFormField('textarea', 'Storage Requirements', 'productStorage', {
                    rows: 2,
                    placeholder: 'e.g., Refrigerate at 38°F, Keep frozen'
                })}
            </div>

            <div class="form-section">
                <h3 class="section-title">Recipe Builder</h3>
                <p class="form-help-text">Add ingredients that make up this product</p>

                <div class="recipe-builder">
                    <div class="recipe-add-section">
                        ${createFormFieldWithOptGroups('select', 'Select Ingredient or Product', 'recipeIngredient', {
                            optgroups: [
                                {
                                    label: '📦 Ingredients',
                                    options: availableIngredients.map(ing => ({
                                        value: `ingredient:${ing.id}`,
                                        label: `${ing.name} (${ing.unit_of_measure})`
                                    }))
                                },
                                {
                                    label: '🍔 Products',
                                    options: availableProducts.map(prod => ({
                                        value: `product:${prod.id}`,
                                        label: `${prod.name} (${prod.unit_of_measure})`
                                    }))
                                }
                            ]
                        })}
                        ${createFormField('number', 'Quantity', 'recipeQuantity', {
                            placeholder: 'Amount needed',
                            step: '0.01',
                            min: '0'
                        })}
                        <button type="button" class="btn-create-inline" onclick="addIngredientToRecipe()">
                            + Add to Recipe
                        </button>
                    </div>

                    <div id="recipeIngredientsList" class="recipe-ingredients-list">
                        <p class="text-muted">No ingredients added yet</p>
                    </div>

                    <div class="recipe-cost-summary">
                        <div class="cost-row">
                            <span>💰 Total Ingredient Cost:</span>
                            <strong id="recipeTotalCost">$0.00</strong>
                        </div>
                        <div class="cost-row">
                            <span>📊 Gross Profit:</span>
                            <strong id="recipeGrossProfit">$0.00</strong>
                        </div>
                        <div class="cost-row">
                            <span>📈 Profit Margin:</span>
                            <strong id="recipeMargin">0%</strong>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    const buttons = [
        { text: 'Cancel', className: 'modal-btn-secondary', onclick: closeModal },
        { text: 'Create Product', className: 'modal-btn-success', onclick: saveNewProduct }
    ];

    openModal('Create New Product', bodyHTML, buttons, true);

    // Add event listener to price field for real-time margin calculation
    setTimeout(() => {
        const priceField = document.getElementById('productPrice');
        if (priceField) {
            priceField.addEventListener('input', updateRecipeCostSummary);
        }

        // Prevent Enter key from closing modal unexpectedly
        const modalBody = document.getElementById('modalBody');
        if (modalBody) {
            modalBody.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && e.target.tagName !== 'BUTTON' && e.target.tagName !== 'TEXTAREA') {
                    e.preventDefault();
                    return false;
                }
            });
        }
    }, 100);
}

/**
 * Add ingredient or product to recipe
 */
async function addIngredientToRecipe() {
    const ingredientSelect = document.getElementById('recipeIngredient');
    const quantityInput = document.getElementById('recipeQuantity');

    const selectedValue = ingredientSelect.value;
    const quantity = parseFloat(quantityInput.value);

    if (!selectedValue || !quantity || quantity <= 0) {
        showMessage('Please select an ingredient/product and enter a valid quantity', 'error');
        return;
    }

    // Parse value: "ingredient:5" or "product:3"
    const [sourceType, sourceId] = selectedValue.split(':');
    const sourceIdInt = parseInt(sourceId);

    // Get name from dropdown
    const selectedOption = ingredientSelect.options[ingredientSelect.selectedIndex];
    const sourceName = selectedOption.text;

    // Check if already added
    if (currentRecipeIngredients.some(item =>
        item.source_type === sourceType && item.source_id === sourceIdInt)) {
        showMessage('This item is already in the recipe', 'warning');
        return;
    }

    // Validate before adding (for products)
    if (sourceType === 'product') {
        await validateAndAddProductToRecipe(sourceIdInt, sourceName, quantity);
    } else {
        // Add ingredient directly
        currentRecipeIngredients.push({
            source_type: sourceType,
            source_id: sourceIdInt,
            source_name: sourceName,
            quantity: quantity
        });

        // Clear inputs
        ingredientSelect.value = '';
        quantityInput.value = '';

        renderRecipeIngredientsList();
        updateRecipeCostSummary();

        showMessage('Ingredient added to recipe', 'success');
    }
}

/**
 * Validate and add product to recipe (with circular dependency and depth checks)
 */
async function validateAndAddProductToRecipe(productId, productName, quantity) {
    const currentProductId = document.getElementById('productId')?.value; // For edit mode

    // Build current recipe items for validation
    const recipeItems = [
        ...currentRecipeIngredients.map(item => ({
            source_type: item.source_type,
            source_id: item.source_id
        })),
        {
            source_type: 'product',
            source_id: productId
        }
    ];

    try {
        const response = await fetch('/api/products/validate-recipe', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                product_id: currentProductId ? parseInt(currentProductId) : null,
                recipe_items: recipeItems
            })
        });

        const result = await response.json();

        if (result.valid) {
            // Add to recipe
            currentRecipeIngredients.push({
                source_type: 'product',
                source_id: productId,
                source_name: productName,
                quantity: quantity
            });

            // Clear inputs
            document.getElementById('recipeIngredient').value = '';
            document.getElementById('recipeQuantity').value = '';

            renderRecipeIngredientsList();
            updateRecipeCostSummary();

            showMessage('Product added to recipe', 'success');
        } else {
            showMessage('Validation failed: ' + result.errors.join('; '), 'error');
        }
    } catch (error) {
        console.error('Validation error:', error);
        showMessage('Failed to validate product', 'error');
    }
}

/**
 * Remove ingredient or product from recipe
 */
function removeIngredientFromRecipe(sourceType, sourceId) {
    currentRecipeIngredients = currentRecipeIngredients.filter(
        item => !(item.source_type === sourceType && item.source_id === sourceId)
    );
    renderRecipeIngredientsList();
    updateRecipeCostSummary();
}

/**
 * Render recipe ingredients list with badges
 */
function renderRecipeIngredientsList() {
    const listContainer = document.getElementById('recipeIngredientsList');

    if (currentRecipeIngredients.length === 0) {
        listContainer.innerHTML = '<p class="text-muted">No ingredients added yet</p>';
        return;
    }

    listContainer.innerHTML = currentRecipeIngredients.map(item => {
        // Badge for type
        const badge = item.source_type === 'product'
            ? '<span class="badge badge-product">Product</span>'
            : '<span class="badge badge-ingredient">Ingredient</span>';

        return `
            <div class="recipe-ingredient-item">
                <div class="ingredient-info">
                    ${badge}
                    <strong>${item.source_name}</strong>
                    <span class="ingredient-quantity">${item.quantity} ${item.unit || ''}</span>
                </div>
                <button type="button" class="btn-remove-ingredient"
                        onclick="removeIngredientFromRecipe('${item.source_type}', ${item.source_id})"
                        title="Remove">
                    ✕
                </button>
            </div>
        `;
    }).join('');
}

/**
 * Update recipe cost summary (handles both ingredients and products)
 */
async function updateRecipeCostSummary() {
    const priceField = document.getElementById('productPrice');
    const sellingPrice = priceField ? parseFloat(priceField.value) || 0 : 0;

    let totalCost = 0;

    // Calculate total cost (ingredients + products)
    for (const item of currentRecipeIngredients) {
        try {
            if (item.source_type === 'ingredient') {
                // Fetch ingredient cost
                const response = await fetch(`/api/ingredients/${item.source_id}`);
                const ingredient = await response.json();
                const cost = ingredient.unit_cost * item.quantity;
                totalCost += cost;
            } else if (item.source_type === 'product') {
                // Fetch product ingredient cost
                const response = await fetch(`/api/products/${item.source_id}/ingredient-cost`);
                const result = await response.json();
                const cost = result.total_ingredient_cost * item.quantity;
                totalCost += cost;
            }
        } catch (error) {
            console.error('Error fetching cost:', error);
        }
    }

    const grossProfit = sellingPrice - totalCost;
    const margin = sellingPrice > 0 ? ((grossProfit / sellingPrice) * 100).toFixed(1) : 0;

    // Update display
    document.getElementById('recipeTotalCost').textContent = formatCurrency(totalCost);
    document.getElementById('recipeGrossProfit').textContent = formatCurrency(grossProfit);
    document.getElementById('recipeMargin').textContent = `${margin}%`;

    // Color-code margin
    const marginElement = document.getElementById('recipeMargin');
    marginElement.style.color = grossProfit < 0 ? '#dc3545' : '#28a745';
}

/**
 * Save new product
 */
async function saveNewProduct() {
    clearFormErrors('modalBody');
    const formData = getFormData('modalBody');

    // Validation
    const errors = [];
    if (!formData.productCode?.trim()) errors.push('Product Code is required');
    if (!formData.productName?.trim()) errors.push('Product Name is required');
    if (!formData.productCategory) errors.push('Category is required');
    if (!formData.productUnit) errors.push('Unit of Measure is required');
    if (!formData.productPrice || parseFloat(formData.productPrice) <= 0) {
        errors.push('Selling Price is required and must be greater than 0');
    }

    if (errors.length > 0) {
        showMessage(errors.join('; '), 'error');
        return;
    }

    const productData = {
        product_code: formData.productCode.trim(),
        product_name: formData.productName.trim(),
        category: formData.productCategory,
        unit_of_measure: formData.productUnit,
        quantity_on_hand: parseFloat(formData.productQuantity) || 0,
        selling_price: parseFloat(formData.productPrice),
        shelf_life_days: formData.productShelfLife ? parseInt(formData.productShelfLife) : null,
        storage_requirements: formData.productStorage?.trim() || '',
        recipe: currentRecipeIngredients.map(item => ({
            source_type: item.source_type,
            source_id: item.source_id,
            quantity_needed: item.quantity,
            unit_of_measure: item.unit || 'unit'
        }))
    };

    try {
        const response = await fetch('/api/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Product "${productData.product_name}" created successfully!`, 'success');
            closeModal();
            loadProducts(); // Refresh products table
        } else {
            showMessage(`Failed to create product: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error creating product:', error);
        showMessage('Failed to create product. Please try again.', 'error');
    }
}

/**
 * Open Edit Product Modal
 */
async function openEditProductModal(productId) {
    try {
        // Load product details
        const productResponse = await fetch(`/api/products/${productId}`);
        const product = await productResponse.json();

        // Load recipe
        const recipeResponse = await fetch(`/api/products/${productId}/recipe`);
        const recipe = await recipeResponse.json();

        // Load available ingredients AND products for recipe builder
        const response = await fetch(`/api/ingredients-and-products/list?exclude_product_id=${productId}`);
        const data = await response.json();
        const availableIngredients = data.ingredients;
        const availableProducts = data.products;

        // Set current recipe
        currentRecipeIngredients = recipe.map(r => ({
            source_type: r.source_type,
            source_id: r.source_id,
            source_name: r.name,
            quantity: r.quantity_needed,
            unit: r.unit_of_measure
        }));

        const bodyHTML = `
            <div id="productForm">
                <input type="hidden" id="productId" value="${productId}">
                <div class="form-section">
                    <h3 class="section-title">Product Details</h3>
                    ${createFormField('text', 'Product Code', 'productCode', {
                        required: true,
                        value: product.product_code
                    })}
                    ${createFormField('text', 'Product Name', 'productName', {
                        required: true,
                        value: product.product_name
                    })}
                    ${createFormField('select', 'Category', 'productCategory', {
                        required: true,
                        value: product.category,
                        options: [
                            { value: '', label: '-- Select Category --' },
                            { value: 'Entrees', label: 'Entrees' },
                            { value: 'Sides', label: 'Sides' },
                            { value: 'Sauces', label: 'Sauces' },
                            { value: 'Pizza', label: 'Pizza' },
                            { value: 'Prepared Foods', label: 'Prepared Foods' }
                        ]
                    })}
                    ${createFormField('select', 'Unit of Measure', 'productUnit', {
                        required: true,
                        value: product.unit_of_measure,
                        options: [
                            { value: '', label: '-- Select Unit --' },
                            { value: 'each', label: 'Each' },
                            { value: 'dozen', label: 'Dozen' },
                            { value: 'lbs', label: 'Pounds (lbs)' },
                            { value: 'oz', label: 'Ounces (oz)' },
                            { value: 'serving', label: 'Serving' }
                        ]
                    })}
                    ${createFormField('number', 'Selling Price', 'productPrice', {
                        required: true,
                        value: product.selling_price,
                        step: '0.01',
                        min: '0'
                    })}
                    ${createFormField('number', 'Quantity on Hand', 'productQuantity', {
                        required: true,
                        value: product.quantity_on_hand,
                        step: '0.01',
                        min: '0'
                    })}
                    ${createFormField('number', 'Shelf Life (Days)', 'productShelfLife', {
                        value: product.shelf_life_days || '',
                        min: '0'
                    })}
                    ${createFormField('textarea', 'Storage Requirements', 'productStorage', {
                        rows: 2,
                        value: product.storage_requirements || ''
                    })}
                </div>

                <div class="form-section">
                    <h3 class="section-title">Recipe Builder</h3>
                    <p class="form-help-text">Modify ingredients that make up this product</p>

                    <div class="recipe-builder">
                        <div class="recipe-add-section">
                            ${createFormFieldWithOptGroups('select', 'Select Ingredient or Product', 'recipeIngredient', {
                                optgroups: [
                                    {
                                        label: '📦 Ingredients',
                                        options: availableIngredients.map(ing => ({
                                            value: `ingredient:${ing.id}`,
                                            label: `${ing.name} (${ing.unit_of_measure})`
                                        }))
                                    },
                                    {
                                        label: '🍔 Products',
                                        options: availableProducts.map(prod => ({
                                            value: `product:${prod.id}`,
                                            label: `${prod.name} (${prod.unit_of_measure})`
                                        }))
                                    }
                                ]
                            })}
                            ${createFormField('number', 'Quantity', 'recipeQuantity', {
                                placeholder: 'Amount needed',
                                step: '0.01',
                                min: '0'
                            })}
                            <button type="button" class="btn-create-inline" onclick="addIngredientToRecipe()">
                                + Add to Recipe
                            </button>
                        </div>

                        <div id="recipeIngredientsList" class="recipe-ingredients-list">
                        </div>

                        <div class="recipe-cost-summary">
                            <div class="cost-row">
                                <span>💰 Total Ingredient Cost:</span>
                                <strong id="recipeTotalCost">$0.00</strong>
                            </div>
                            <div class="cost-row">
                                <span>📊 Gross Profit:</span>
                                <strong id="recipeGrossProfit">$0.00</strong>
                            </div>
                            <div class="cost-row">
                                <span>📈 Profit Margin:</span>
                                <strong id="recipeMargin">0%</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const buttons = [
            { text: 'Cancel', className: 'modal-btn-secondary', onclick: closeModal },
            { text: 'Update Product', className: 'modal-btn-success', onclick: updateProduct }
        ];

        openModal('Edit Product', bodyHTML, buttons, true);

        // Render existing recipe and update costs
        setTimeout(() => {
            renderRecipeIngredientsList();
            updateRecipeCostSummary();

            // Add event listener to price field
            const priceField = document.getElementById('productPrice');
            if (priceField) {
                priceField.addEventListener('input', updateRecipeCostSummary);
            }

            // Prevent Enter key from closing modal unexpectedly
            const modalBody = document.getElementById('modalBody');
            if (modalBody) {
                modalBody.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && e.target.tagName !== 'BUTTON' && e.target.tagName !== 'TEXTAREA') {
                        e.preventDefault();
                        return false;
                    }
                });
            }
        }, 100);

    } catch (error) {
        console.error('Error loading product for edit:', error);
        showMessage('Failed to load product details', 'error');
    }
}

/**
 * Update existing product
 */
async function updateProduct() {
    clearFormErrors('modalBody');
    const formData = getFormData('modalBody');
    const productId = formData.productId;

    // Validation
    const errors = [];
    if (!formData.productCode?.trim()) errors.push('Product Code is required');
    if (!formData.productName?.trim()) errors.push('Product Name is required');
    if (!formData.productCategory) errors.push('Category is required');
    if (!formData.productUnit) errors.push('Unit of Measure is required');
    if (!formData.productPrice || parseFloat(formData.productPrice) <= 0) {
        errors.push('Selling Price is required and must be greater than 0');
    }

    if (errors.length > 0) {
        showMessage(errors.join('; '), 'error');
        return;
    }

    const productData = {
        product_code: formData.productCode.trim(),
        product_name: formData.productName.trim(),
        category: formData.productCategory,
        unit_of_measure: formData.productUnit,
        quantity_on_hand: parseFloat(formData.productQuantity) || 0,
        selling_price: parseFloat(formData.productPrice),
        shelf_life_days: formData.productShelfLife ? parseInt(formData.productShelfLife) : null,
        storage_requirements: formData.productStorage?.trim() || '',
        recipe: currentRecipeIngredients.map(item => ({
            source_type: item.source_type,
            source_id: item.source_id,
            quantity_needed: item.quantity,
            unit_of_measure: item.unit || 'unit'
        }))
    };

    try {
        const response = await fetch(`/api/products/${productId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Product "${productData.product_name}" updated successfully!`, 'success');
            closeModal();
            loadProducts(); // Refresh products table
        } else {
            showMessage(`Failed to update product: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error updating product:', error);
        showMessage('Failed to update product. Please try again.', 'error');
    }
}

/**
 * Delete product
 */
async function deleteProduct(productId, productName) {
    if (!confirm(`Are you sure you want to delete "${productName}"?\n\nThis will also remove the product's recipe. This action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/products/${productId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(`✓ Product "${productName}" deleted successfully!`, 'success');
            loadProducts(); // Refresh products table
        } else {
            showMessage(`Failed to delete product: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting product:', error);
        showMessage('Failed to delete product. Please try again.', 'error');
    }
}
