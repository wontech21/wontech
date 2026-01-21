/**
 * Layer 2 Browser Testing Suite - Ingredient Management
 *
 * Run this in the browser console at http://localhost:5001
 *
 * Usage: Copy and paste this entire script into the browser console
 */

(async function() {
    console.log('%c🧪 LAYER 2 TESTING SUITE - INGREDIENT MANAGEMENT', 'background: #222; color: #4CAF50; font-size: 20px; padding: 10px;');
    console.log('%c='.repeat(70), 'color: #888;');

    let passedTests = 0;
    let failedTests = 0;
    let totalTests = 0;
    const testResults = [];

    // Helper function to log test results
    function logTest(phase, testNum, name, passed, details = '') {
        totalTests++;
        const status = passed ? '✅ PASSED' : '❌ FAILED';
        const color = passed ? 'color: green' : 'color: red';

        if (passed) {
            passedTests++;
        } else {
            failedTests++;
        }

        console.log(`%c${status} - ${phase}.${testNum}: ${name}`, color);
        if (details) {
            console.log(`   ${details}`);
        }

        testResults.push({
            phase,
            testNum,
            name,
            passed,
            details
        });
    }

    // Sleep helper
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Generate random test data
    const testId = Date.now();
    const testIngredient = {
        code: `TEST${testId}`,
        name: `Test Ingredient ${testId}`,
        category: 'Produce',
        unit: 'lb',
        cost: '3.50',
        quantity: '100'
    };

    console.log('\n%c📋 PHASE 1: UI ELEMENT VERIFICATION', 'background: #333; color: #fff; font-size: 16px; padding: 5px;');
    console.log('');

    // Test 1.1: Create Button Exists
    try {
        const createButton = document.querySelector('.btn-create-primary');
        const passed = createButton !== null;

        logTest('Phase 1', '1.1', 'Create Ingredient Button Exists', passed,
               `Button found: ${passed}`);
    } catch (e) {
        logTest('Phase 1', '1.1', 'Create Ingredient Button Exists', false, `Error: ${e.message}`);
    }

    // Test 1.2: Create Button Text
    try {
        const createButton = document.querySelector('.btn-create-primary');
        const text = createButton ? createButton.textContent : '';
        const passed = text.includes('Create Ingredient');

        logTest('Phase 1', '1.2', 'Create Button Has Correct Text', passed,
               `Text: "${text.trim()}"`);
    } catch (e) {
        logTest('Phase 1', '1.2', 'Create Button Has Correct Text', false, `Error: ${e.message}`);
    }

    // Test 1.3: Edit Buttons in Table
    try {
        const editButtons = document.querySelectorAll('.btn-edit');
        const passed = editButtons.length > 0;

        logTest('Phase 1', '1.3', 'Edit Buttons Exist in Table', passed,
               `Found ${editButtons.length} edit buttons`);
    } catch (e) {
        logTest('Phase 1', '1.3', 'Edit Buttons Exist in Table', false, `Error: ${e.message}`);
    }

    // Test 1.4: Create Button is Clickable
    try {
        const createButton = document.querySelector('.btn-create-primary');
        const hasOnclick = createButton && createButton.getAttribute('onclick');
        const passed = hasOnclick !== null;

        logTest('Phase 1', '1.4', 'Create Button is Clickable', passed,
               `onclick attribute: ${hasOnclick}`);
    } catch (e) {
        logTest('Phase 1', '1.4', 'Create Button is Clickable', false, `Error: ${e.message}`);
    }

    console.log('\n%c📋 PHASE 2: CREATE MODAL FUNCTIONALITY', 'background: #333; color: #fff; font-size: 16px; padding: 5px;');
    console.log('');

    // Test 2.1: Open Create Modal
    try {
        if (typeof openCreateIngredientModal === 'function') {
            openCreateIngredientModal();
            await sleep(500);

            const modal = document.getElementById('genericModal');
            const passed = modal && modal.style.display === 'flex';

            logTest('Phase 2', '2.1', 'Create Modal Opens', passed,
                   `Modal display: ${modal ? modal.style.display : 'not found'}`);
        } else {
            logTest('Phase 2', '2.1', 'Create Modal Opens', false,
                   'Function openCreateIngredientModal not found');
        }
    } catch (e) {
        logTest('Phase 2', '2.1', 'Create Modal Opens', false, `Error: ${e.message}`);
    }

    // Test 2.2: Modal Title
    try {
        const modalTitle = document.getElementById('modalTitle');
        const text = modalTitle ? modalTitle.textContent : '';
        const passed = text.includes('Create New Ingredient');

        logTest('Phase 2', '2.2', 'Modal Has Correct Title', passed,
               `Title: "${text}"`);
    } catch (e) {
        logTest('Phase 2', '2.2', 'Modal Has Correct Title', false, `Error: ${e.message}`);
    }

    // Test 2.3: All Required Form Fields Present
    try {
        const requiredFields = [
            'ingredientCode',
            'ingredientName',
            'ingredientCategory',
            'ingredientUnit'
        ];

        const allPresent = requiredFields.every(id => document.getElementById(id) !== null);
        const foundFields = requiredFields.filter(id => document.getElementById(id) !== null);

        logTest('Phase 2', '2.3', 'All Required Fields Present', allPresent,
               `Found ${foundFields.length}/${requiredFields.length} fields`);
    } catch (e) {
        logTest('Phase 2', '2.3', 'All Required Fields Present', false, `Error: ${e.message}`);
    }

    // Test 2.4: Optional Form Fields Present
    try {
        const optionalFields = [
            'ingredientCost',
            'ingredientQuantity',
            'ingredientReorderPoint',
            'ingredientSupplier',
            'ingredientBrand',
            'ingredientLocation',
            'ingredientActive'
        ];

        const foundFields = optionalFields.filter(id => document.getElementById(id) !== null);
        const passed = foundFields.length === optionalFields.length;

        logTest('Phase 2', '2.4', 'All Optional Fields Present', passed,
               `Found ${foundFields.length}/${optionalFields.length} fields`);
    } catch (e) {
        logTest('Phase 2', '2.4', 'All Optional Fields Present', false, `Error: ${e.message}`);
    }

    // Test 2.5: Category Dropdown Populated
    try {
        const categorySelect = document.getElementById('ingredientCategory');
        const options = categorySelect ? categorySelect.querySelectorAll('option') : [];
        const passed = options.length >= 13; // 13 categories

        logTest('Phase 2', '2.5', 'Category Dropdown Populated', passed,
               `Found ${options.length} category options`);
    } catch (e) {
        logTest('Phase 2', '2.5', 'Category Dropdown Populated', false, `Error: ${e.message}`);
    }

    // Test 2.6: Unit Dropdown Populated
    try {
        const unitSelect = document.getElementById('ingredientUnit');
        const options = unitSelect ? unitSelect.querySelectorAll('option') : [];
        const passed = options.length >= 10; // Multiple units

        logTest('Phase 2', '2.6', 'Unit Dropdown Populated', passed,
               `Found ${options.length} unit options`);
    } catch (e) {
        logTest('Phase 2', '2.6', 'Unit Dropdown Populated', false, `Error: ${e.message}`);
    }

    // Test 2.7: Active Checkbox Default Checked
    try {
        const activeCheckbox = document.getElementById('ingredientActive');
        const passed = activeCheckbox && activeCheckbox.checked === true;

        logTest('Phase 2', '2.7', 'Active Checkbox Default Checked', passed,
               `Checked: ${activeCheckbox ? activeCheckbox.checked : 'not found'}`);
    } catch (e) {
        logTest('Phase 2', '2.7', 'Active Checkbox Default Checked', false, `Error: ${e.message}`);
    }

    // Test 2.8: Create Button Present
    try {
        const buttons = document.querySelectorAll('.modal-btn-success');
        const createButton = Array.from(buttons).find(btn => btn.textContent.includes('Create Ingredient'));
        const passed = createButton !== undefined;

        logTest('Phase 2', '2.8', 'Create Button in Modal Present', passed,
               `Button found: ${passed}`);
    } catch (e) {
        logTest('Phase 2', '2.8', 'Create Button in Modal Present', false, `Error: ${e.message}`);
    }

    // Test 2.9: Cancel Button Present
    try {
        const buttons = document.querySelectorAll('.modal-btn-secondary');
        const cancelButton = Array.from(buttons).find(btn => btn.textContent.includes('Cancel'));
        const passed = cancelButton !== undefined;

        logTest('Phase 2', '2.9', 'Cancel Button Present', passed,
               `Button found: ${passed}`);
    } catch (e) {
        logTest('Phase 2', '2.9', 'Cancel Button Present', false, `Error: ${e.message}`);
    }

    // Close modal before validation tests
    closeModal();
    await sleep(300);

    console.log('\n%c📋 PHASE 3: FORM VALIDATION', 'background: #333; color: #fff; font-size: 16px; padding: 5px;');
    console.log('');

    // Test 3.1: Validation Function Exists
    try {
        const passed = typeof validateIngredientForm === 'function';

        logTest('Phase 3', '3.1', 'Validation Function Exists', passed,
               `Function found: ${passed}`);
    } catch (e) {
        logTest('Phase 3', '3.1', 'Validation Function Exists', false, `Error: ${e.message}`);
    }

    // Test 3.2: Empty Required Fields Fail Validation
    try {
        if (typeof validateIngredientForm === 'function') {
            const result = validateIngredientForm({
                ingredientCode: '',
                ingredientName: '',
                ingredientCategory: '',
                ingredientUnit: ''
            });

            const passed = result.valid === false && result.errors.length > 0;

            logTest('Phase 3', '3.2', 'Empty Required Fields Fail Validation', passed,
                   `Valid: ${result.valid}, Errors: ${result.errors.length}`);
        } else {
            logTest('Phase 3', '3.2', 'Empty Required Fields Fail Validation', false,
                   'Validation function not found');
        }
    } catch (e) {
        logTest('Phase 3', '3.2', 'Empty Required Fields Fail Validation', false, `Error: ${e.message}`);
    }

    // Test 3.3: Invalid Code Format Fails
    try {
        if (typeof validateIngredientForm === 'function') {
            const result = validateIngredientForm({
                ingredientCode: 'TEST@#$',
                ingredientName: 'Test',
                ingredientCategory: 'Produce',
                ingredientUnit: 'lb'
            });

            const codeError = result.errors.find(e => e.field === 'ingredientCode');
            const passed = codeError !== undefined;

            logTest('Phase 3', '3.3', 'Invalid Code Format Fails', passed,
                   `Code error found: ${passed}`);
        } else {
            logTest('Phase 3', '3.3', 'Invalid Code Format Fails', false,
                   'Validation function not found');
        }
    } catch (e) {
        logTest('Phase 3', '3.3', 'Invalid Code Format Fails', false, `Error: ${e.message}`);
    }

    // Test 3.4: Short Name Fails
    try {
        if (typeof validateIngredientForm === 'function') {
            const result = validateIngredientForm({
                ingredientCode: 'TEST',
                ingredientName: 'A',
                ingredientCategory: 'Produce',
                ingredientUnit: 'lb'
            });

            const nameError = result.errors.find(e => e.field === 'ingredientName');
            const passed = nameError !== undefined;

            logTest('Phase 3', '3.4', 'Short Name (1 char) Fails', passed,
                   `Name error found: ${passed}`);
        } else {
            logTest('Phase 3', '3.4', 'Short Name (1 char) Fails', false,
                   'Validation function not found');
        }
    } catch (e) {
        logTest('Phase 3', '3.4', 'Short Name (1 char) Fails', false, `Error: ${e.message}`);
    }

    // Test 3.5: Valid Data Passes
    try {
        if (typeof validateIngredientForm === 'function') {
            const result = validateIngredientForm({
                ingredientCode: testIngredient.code,
                ingredientName: testIngredient.name,
                ingredientCategory: testIngredient.category,
                ingredientUnit: testIngredient.unit,
                ingredientCost: testIngredient.cost,
                ingredientQuantity: testIngredient.quantity
            });

            const passed = result.valid === true && result.errors.length === 0;

            logTest('Phase 3', '3.5', 'Valid Data Passes Validation', passed,
                   `Valid: ${result.valid}, Errors: ${result.errors.length}`);
        } else {
            logTest('Phase 3', '3.5', 'Valid Data Passes Validation', false,
                   'Validation function not found');
        }
    } catch (e) {
        logTest('Phase 3', '3.5', 'Valid Data Passes Validation', false, `Error: ${e.message}`);
    }

    console.log('\n%c📋 PHASE 4: CREATE INGREDIENT (API)', 'background: #333; color: #fff; font-size: 16px; padding: 5px;');
    console.log('');

    let createdIngredientId = null;

    // Test 4.1: Create Function Exists
    try {
        const passed = typeof saveNewIngredient === 'function';

        logTest('Phase 4', '4.1', 'Create Function Exists', passed,
               `Function found: ${passed}`);
    } catch (e) {
        logTest('Phase 4', '4.1', 'Create Function Exists', false, `Error: ${e.message}`);
    }

    // Test 4.2: Create Ingredient via API
    try {
        openCreateIngredientModal();
        await sleep(500);

        // Fill form
        document.getElementById('ingredientCode').value = testIngredient.code;
        document.getElementById('ingredientName').value = testIngredient.name;
        document.getElementById('ingredientCategory').value = testIngredient.category;
        document.getElementById('ingredientUnit').value = testIngredient.unit;
        document.getElementById('ingredientCost').value = testIngredient.cost;
        document.getElementById('ingredientQuantity').value = testIngredient.quantity;

        // Submit
        await saveNewIngredient();
        await sleep(2000); // Wait for API call

        // Check if modal closed (success indicator)
        const modal = document.getElementById('genericModal');
        const passed = modal.style.display === 'none';

        logTest('Phase 4', '4.2', 'Create Ingredient via API', passed,
               `Modal closed: ${passed} (indicates success)`);

        // Try to find the created ingredient in the table
        if (passed) {
            const rows = document.querySelectorAll('#inventoryTableBody tr');
            const foundRow = Array.from(rows).find(row => row.textContent.includes(testIngredient.code));
            if (foundRow) {
                // Extract ID from edit button
                const editBtn = foundRow.querySelector('.btn-edit');
                if (editBtn) {
                    createdIngredientId = parseInt(editBtn.getAttribute('data-item-id'));
                    console.log(`   Created ingredient ID: ${createdIngredientId}`);
                }
            }
        }
    } catch (e) {
        logTest('Phase 4', '4.2', 'Create Ingredient via API', false, `Error: ${e.message}`);
    }

    // Test 4.3: Success Toast Appears
    try {
        await sleep(500);
        const successToast = document.querySelector('.toast-success');
        const passed = successToast !== null;

        logTest('Phase 4', '4.3', 'Success Toast Appears', passed,
               `Toast found: ${passed}`);

        // Clean up toast
        if (successToast) {
            const toastId = successToast.id.replace('toast-', '');
            closeToast(parseInt(toastId));
        }
    } catch (e) {
        logTest('Phase 4', '4.3', 'Success Toast Appears', false, `Error: ${e.message}`);
    }

    // Test 4.4: Ingredient Appears in Table
    try {
        await sleep(1000);
        const rows = document.querySelectorAll('#inventoryTableBody tr');
        const foundRow = Array.from(rows).find(row => row.textContent.includes(testIngredient.code));
        const passed = foundRow !== undefined;

        logTest('Phase 4', '4.4', 'New Ingredient Appears in Table', passed,
               `Ingredient "${testIngredient.code}" found in table: ${passed}`);
    } catch (e) {
        logTest('Phase 4', '4.4', 'New Ingredient Appears in Table', false, `Error: ${e.message}`);
    }

    console.log('\n%c📋 PHASE 5: EDIT INGREDIENT', 'background: #333; color: #fff; font-size: 16px; padding: 5px;');
    console.log('');

    // Test 5.1: Edit Function Exists
    try {
        const passed = typeof openEditIngredientModal === 'function';

        logTest('Phase 5', '5.1', 'Edit Function Exists', passed,
               `Function found: ${passed}`);
    } catch (e) {
        logTest('Phase 5', '5.1', 'Edit Function Exists', false, `Error: ${e.message}`);
    }

    // Test 5.2: Open Edit Modal
    if (createdIngredientId) {
        try {
            await openEditIngredientModal(createdIngredientId);
            await sleep(1000);

            const modal = document.getElementById('genericModal');
            const passed = modal && modal.style.display === 'flex';

            logTest('Phase 5', '5.2', 'Edit Modal Opens', passed,
                   `Modal display: ${modal ? modal.style.display : 'not found'}`);
        } catch (e) {
            logTest('Phase 5', '5.2', 'Edit Modal Opens', false, `Error: ${e.message}`);
        }

        // Test 5.3: Edit Modal Title Shows Ingredient Name
        try {
            const modalTitle = document.getElementById('modalTitle');
            const text = modalTitle ? modalTitle.textContent : '';
            const passed = text.includes('Edit Ingredient') && text.includes(testIngredient.name);

            logTest('Phase 5', '5.3', 'Edit Modal Title Correct', passed,
                   `Title: "${text}"`);
        } catch (e) {
            logTest('Phase 5', '5.3', 'Edit Modal Title Correct', false, `Error: ${e.message}`);
        }

        // Test 5.4: Form Fields Pre-populated
        try {
            const codeValue = document.getElementById('ingredientCode')?.value || '';
            const nameValue = document.getElementById('ingredientName')?.value || '';
            const passed = codeValue === testIngredient.code && nameValue === testIngredient.name;

            logTest('Phase 5', '5.4', 'Form Fields Pre-populated', passed,
                   `Code: "${codeValue}", Name: "${nameValue}"`);
        } catch (e) {
            logTest('Phase 5', '5.4', 'Form Fields Pre-populated', false, `Error: ${e.message}`);
        }

        // Test 5.5: Update Ingredient
        try {
            // Modify cost
            const newCost = '7.99';
            document.getElementById('ingredientCost').value = newCost;

            // Save
            if (typeof updateIngredient === 'function') {
                await updateIngredient();
                await sleep(2000);

                // Check if modal closed
                const modal = document.getElementById('genericModal');
                const passed = modal.style.display === 'none';

                logTest('Phase 5', '5.5', 'Update Ingredient via API', passed,
                       `Modal closed: ${passed} (indicates success)`);
            } else {
                logTest('Phase 5', '5.5', 'Update Ingredient via API', false,
                       'Function updateIngredient not found');
            }
        } catch (e) {
            logTest('Phase 5', '5.5', 'Update Ingredient via API', false, `Error: ${e.message}`);
        }

        // Test 5.6: Update Success Toast
        try {
            await sleep(500);
            const successToast = document.querySelector('.toast-success');
            const passed = successToast !== null;

            logTest('Phase 5', '5.6', 'Update Success Toast Appears', passed,
                   `Toast found: ${passed}`);

            // Clean up
            if (successToast) {
                const toastId = successToast.id.replace('toast-', '');
                closeToast(parseInt(toastId));
            }
        } catch (e) {
            logTest('Phase 5', '5.6', 'Update Success Toast Appears', false, `Error: ${e.message}`);
        }
    } else {
        logTest('Phase 5', '5.2', 'Edit Modal Opens', false, 'No ingredient ID to test with');
        logTest('Phase 5', '5.3', 'Edit Modal Title Correct', false, 'No ingredient ID to test with');
        logTest('Phase 5', '5.4', 'Form Fields Pre-populated', false, 'No ingredient ID to test with');
        logTest('Phase 5', '5.5', 'Update Ingredient via API', false, 'No ingredient ID to test with');
        logTest('Phase 5', '5.6', 'Update Success Toast Appears', false, 'No ingredient ID to test with');
    }

    // Print Summary
    console.log('\n%c📊 TEST SUMMARY', 'background: #222; color: #4CAF50; font-size: 18px; padding: 10px;');
    console.log('%c='.repeat(70), 'color: #888;');
    console.log(`%cTotal Tests: ${totalTests}`, 'font-weight: bold; font-size: 14px;');
    console.log(`%c✅ Passed: ${passedTests}`, 'color: green; font-weight: bold; font-size: 14px;');
    console.log(`%c❌ Failed: ${failedTests}`, 'color: red; font-weight: bold; font-size: 14px;');
    console.log(`%cSuccess Rate: ${((passedTests / totalTests) * 100).toFixed(1)}%`, 'font-weight: bold; font-size: 14px;');
    console.log('');

    if (failedTests === 0) {
        console.log('%c🎉 ALL TESTS PASSED! Layer 2 is fully functional!', 'background: green; color: white; font-size: 16px; padding: 10px;');
    } else {
        console.log(`%c⚠️ ${failedTests} test(s) failed. Review the failures above.`, 'background: orange; color: white; font-size: 16px; padding: 10px;');
    }

    console.log('\n%c📝 Test Ingredient Created:', 'font-weight: bold;');
    console.log(`   Code: ${testIngredient.code}`);
    console.log(`   Name: ${testIngredient.name}`);
    console.log(`   ID: ${createdIngredientId || 'unknown'}`);
    console.log('   You can manually delete this test ingredient from the database if needed.');

    // Return results object
    return {
        totalTests,
        passedTests,
        failedTests,
        successRate: ((passedTests / totalTests) * 100).toFixed(1) + '%',
        details: testResults,
        testIngredient: testIngredient,
        createdIngredientId: createdIngredientId
    };
})().then(results => {
    console.log('\n%c✅ Test execution complete. Results stored in window.layer2TestResults', 'color: blue;');
    window.layer2TestResults = results;
});
