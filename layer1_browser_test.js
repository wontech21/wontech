/**
 * Layer 1 Browser Testing Suite
 *
 * Run this in the browser console at http://localhost:5001
 *
 * Usage: Copy and paste this entire script into the browser console
 */

(function() {
    console.log('%c🧪 LAYER 1 TESTING SUITE', 'background: #222; color: #bada55; font-size: 20px; padding: 10px;');
    console.log('%c='.repeat(60), 'color: #888;');

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

    // Main test execution
    async function runAllTests() {
        console.log('\n%c📋 PHASE 3: FUNCTIONAL TESTS', 'background: #333; color: #fff; font-size: 16px; padding: 5px;');
        console.log('');

        // Test 3.1: Modal Opens
        try {
            openModal('Test Modal', '<p>Hello World</p>');
            const modal = document.getElementById('genericModal');
            const modalTitle = document.getElementById('modalTitle');
            const modalBody = document.getElementById('modalBody');

            const passed = modal.style.display === 'flex' &&
                          modalTitle.textContent === 'Test Modal' &&
                          modalBody.innerHTML.includes('Hello World');

            logTest('Phase 3', '3.1', 'Modal Opens', passed,
                   `Modal display: ${modal.style.display}, Title: ${modalTitle.textContent}`);

            await sleep(500);
        } catch (e) {
            logTest('Phase 3', '3.1', 'Modal Opens', false, `Error: ${e.message}`);
        }

        // Test 3.2: Modal Closes - Button
        try {
            const closeBtn = document.querySelector('.modal-close');
            const initialDisplay = document.getElementById('genericModal').style.display;

            closeBtn.click();
            await sleep(300);

            const finalDisplay = document.getElementById('genericModal').style.display;
            const passed = initialDisplay === 'flex' && finalDisplay === 'none';

            logTest('Phase 3', '3.2', 'Modal Closes - Button', passed,
                   `Initial: ${initialDisplay}, Final: ${finalDisplay}`);
        } catch (e) {
            logTest('Phase 3', '3.2', 'Modal Closes - Button', false, `Error: ${e.message}`);
        }

        // Test 3.3: Modal Closes - ESC Key
        try {
            openModal('ESC Test', '<p>Press ESC to close</p>');
            await sleep(200);

            const escEvent = new KeyboardEvent('keydown', { key: 'Escape' });
            document.dispatchEvent(escEvent);
            await sleep(300);

            const modal = document.getElementById('genericModal');
            const passed = modal.style.display === 'none';

            logTest('Phase 3', '3.3', 'Modal Closes - ESC Key', passed,
                   `Display after ESC: ${modal.style.display}`);
        } catch (e) {
            logTest('Phase 3', '3.3', 'Modal Closes - ESC Key', false, `Error: ${e.message}`);
        }

        // Test 3.4: Modal Closes - Backdrop Click
        try {
            openModal('Backdrop Test', '<p>Click backdrop to close</p>');
            await sleep(200);

            const modal = document.getElementById('genericModal');
            modal.click(); // Click backdrop
            await sleep(300);

            const passed = modal.style.display === 'none';

            logTest('Phase 3', '3.4', 'Modal Closes - Backdrop Click', passed,
                   `Display after backdrop click: ${modal.style.display}`);
        } catch (e) {
            logTest('Phase 3', '3.4', 'Modal Closes - Backdrop Click', false, `Error: ${e.message}`);
        }

        // Test 3.5: Form Field - Text Input
        try {
            const html = createFormField('text', 'Name', 'testName', {
                required: true,
                placeholder: 'Enter name'
            });

            const passed = html.includes('type="text"') &&
                          html.includes('id="testName"') &&
                          html.includes('Name *') &&
                          html.includes('placeholder="Enter name"') &&
                          html.includes('required');

            logTest('Phase 3', '3.5', 'Form Field - Text Input', passed,
                   `Contains required elements: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.5', 'Form Field - Text Input', false, `Error: ${e.message}`);
        }

        // Test 3.6: Form Field - Number Input
        try {
            const html = createFormField('number', 'Age', 'testAge', {
                min: 0,
                max: 120
            });

            const passed = html.includes('type="number"') &&
                          html.includes('id="testAge"') &&
                          html.includes('min="0"') &&
                          html.includes('max="120"');

            logTest('Phase 3', '3.6', 'Form Field - Number Input', passed,
                   `Contains min/max attributes: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.6', 'Form Field - Number Input', false, `Error: ${e.message}`);
        }

        // Test 3.7: Form Field - Select Dropdown
        try {
            const html = createFormField('select', 'Type', 'testType', {
                options: [
                    { value: 'a', label: 'Option A' },
                    { value: 'b', label: 'Option B' }
                ]
            });

            const passed = html.includes('<select') &&
                          html.includes('id="testType"') &&
                          html.includes('value="a"') &&
                          html.includes('Option A');

            logTest('Phase 3', '3.7', 'Form Field - Select Dropdown', passed,
                   `Contains select with options: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.7', 'Form Field - Select Dropdown', false, `Error: ${e.message}`);
        }

        // Test 3.8: Form Field - Checkbox
        try {
            const html = createFormField('checkbox', 'Agree', 'testAgree');

            const passed = html.includes('type="checkbox"') &&
                          html.includes('id="testAgree"') &&
                          html.includes('Agree');

            logTest('Phase 3', '3.8', 'Form Field - Checkbox', passed,
                   `Contains checkbox: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.8', 'Form Field - Checkbox', false, `Error: ${e.message}`);
        }

        // Test 3.9: Form Field - Textarea
        try {
            const html = createFormField('textarea', 'Notes', 'testNotes', {
                rows: 3
            });

            const passed = html.includes('<textarea') &&
                          html.includes('id="testNotes"') &&
                          html.includes('rows="3"');

            logTest('Phase 3', '3.9', 'Form Field - Textarea', passed,
                   `Contains textarea with rows: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.9', 'Form Field - Textarea', false, `Error: ${e.message}`);
        }

        // Test 3.10: Form Validation - Required Fields
        try {
            const formHTML = createFormField('text', 'Required Field', 'reqField', {
                required: true
            });

            openModal('Validation Test', formHTML);
            await sleep(200);

            const validation = validateForm();
            const passed = validation.valid === false && validation.errors.length > 0;

            logTest('Phase 3', '3.10', 'Form Validation - Required Fields', passed,
                   `Validation.valid: ${validation.valid}, Errors: ${validation.errors.length}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 3', '3.10', 'Form Validation - Required Fields', false, `Error: ${e.message}`);
        }

        // Test 3.11: Form Validation - Email Format
        try {
            const formHTML = createFormField('email', 'Email', 'testEmail', {
                required: true
            });

            openModal('Email Test', formHTML);
            await sleep(200);

            const emailInput = document.getElementById('testEmail');
            emailInput.value = 'notanemail';

            const validation = validateForm();
            const errorShown = document.getElementById('testEmail-error').textContent.length > 0;

            const passed = !validation.valid || errorShown;

            logTest('Phase 3', '3.11', 'Form Validation - Email Format', passed,
                   `Invalid email detected: ${passed}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 3', '3.11', 'Form Validation - Email Format', false, `Error: ${e.message}`);
        }

        // Test 3.12: Form Validation - Number Range
        try {
            const formHTML = createFormField('number', 'Age', 'testAge', {
                min: 0,
                max: 120
            });

            openModal('Number Test', formHTML);
            await sleep(200);

            const ageInput = document.getElementById('testAge');
            ageInput.value = 200;

            const validation = validateForm();
            const errorShown = document.getElementById('testAge-error').textContent.length > 0;

            const passed = !validation.valid || errorShown;

            logTest('Phase 3', '3.12', 'Form Validation - Number Range', passed,
                   `Out of range number detected: ${passed}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 3', '3.12', 'Form Validation - Number Range', false, `Error: ${e.message}`);
        }

        // Test 3.13: Get Form Data
        try {
            const formHTML = `
                ${createFormField('text', 'Name', 'getName', {})}
                ${createFormField('number', 'Age', 'getAge', {})}
            `;

            openModal('Get Data Test', formHTML);
            await sleep(200);

            document.getElementById('getName').value = 'John Doe';
            document.getElementById('getAge').value = '30';

            const data = getFormData();
            const passed = data.getName === 'John Doe' && data.getAge === 30;

            logTest('Phase 3', '3.13', 'Get Form Data', passed,
                   `Name: ${data.getName}, Age: ${data.getAge}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 3', '3.13', 'Get Form Data', false, `Error: ${e.message}`);
        }

        // Test 3.14: Set Form Data
        try {
            const formHTML = `
                ${createFormField('text', 'Name', 'setName', {})}
                ${createFormField('number', 'Age', 'setAge', {})}
            `;

            openModal('Set Data Test', formHTML);
            await sleep(200);

            setFormData('modalBody', { setName: 'Jane Doe', setAge: 25 });

            const nameValue = document.getElementById('setName').value;
            const ageValue = document.getElementById('setAge').value;

            const passed = nameValue === 'Jane Doe' && ageValue === '25';

            logTest('Phase 3', '3.14', 'Set Form Data', passed,
                   `Name: ${nameValue}, Age: ${ageValue}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 3', '3.14', 'Set Form Data', false, `Error: ${e.message}`);
        }

        // Test 3.15: Ingredient Selector
        try {
            const html = await createIngredientSelector('testIng', 'Ingredient');
            const passed = html.includes('<select') && html.includes('id="testIng"');

            logTest('Phase 3', '3.15', 'Ingredient Selector', passed,
                   `Selector created: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.15', 'Ingredient Selector', false, `Error: ${e.message}`);
        }

        // Test 3.16: Category Selector
        try {
            const html = createCategorySelector('testCat', 'Category');
            const passed = html.includes('<select') &&
                          html.includes('id="testCat"') &&
                          html.includes('Produce');

            logTest('Phase 3', '3.16', 'Category Selector', passed,
                   `Selector with 13 categories: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.16', 'Category Selector', false, `Error: ${e.message}`);
        }

        // Test 3.17: Unit Selector
        try {
            const html = createUnitSelector('testUnit', 'Unit', 'lb');
            const passed = html.includes('<select') &&
                          html.includes('id="testUnit"') &&
                          html.includes('value="lb" selected');

            logTest('Phase 3', '3.17', 'Unit Selector', passed,
                   `Unit selector with 'lb' selected: ${passed}`);
        } catch (e) {
            logTest('Phase 3', '3.17', 'Unit Selector', false, `Error: ${e.message}`);
        }

        // Test 3.18: Toast Notification - Success
        try {
            showMessage('Test Success', 'success', 1000);
            await sleep(200);

            const toast = document.querySelector('.toast-success');
            const passed = toast !== null && toast.textContent.includes('Test Success');

            logTest('Phase 3', '3.18', 'Toast Notification - Success', passed,
                   `Green toast displayed: ${passed}`);

            await sleep(1000);
        } catch (e) {
            logTest('Phase 3', '3.18', 'Toast Notification - Success', false, `Error: ${e.message}`);
        }

        // Test 3.19: Toast Notification - Error
        try {
            showMessage('Test Error', 'error', 1000);
            await sleep(200);

            const toast = document.querySelector('.toast-error');
            const passed = toast !== null && toast.textContent.includes('Test Error');

            logTest('Phase 3', '3.19', 'Toast Notification - Error', passed,
                   `Red toast displayed: ${passed}`);

            await sleep(1000);
        } catch (e) {
            logTest('Phase 3', '3.19', 'Toast Notification - Error', false, `Error: ${e.message}`);
        }

        // Test 3.20: Toast Notification - Multiple
        try {
            showMessage('Toast 1', 'info', 2000);
            showMessage('Toast 2', 'warning', 2000);
            showMessage('Toast 3', 'success', 2000);
            await sleep(300);

            const toasts = document.querySelectorAll('.toast');
            const passed = toasts.length === 3;

            logTest('Phase 3', '3.20', 'Toast Notification - Multiple', passed,
                   `${toasts.length} toasts stacked: ${passed}`);

            await sleep(2000);
        } catch (e) {
            logTest('Phase 3', '3.20', 'Toast Notification - Multiple', false, `Error: ${e.message}`);
        }

        // Test 3.21: Toast Close Button
        try {
            showMessage('Closeable Toast', 'info', 5000);
            await sleep(300);

            const closeBtn = document.querySelector('.toast-close');
            if (closeBtn) {
                closeBtn.click();
                await sleep(300);

                const toastGone = document.querySelector('.toast') === null ||
                                 document.querySelectorAll('.toast').length === 0;

                logTest('Phase 3', '3.21', 'Toast Close Button', toastGone,
                       `Toast closed by button: ${toastGone}`);
            } else {
                logTest('Phase 3', '3.21', 'Toast Close Button', false,
                       'Close button not found');
            }
        } catch (e) {
            logTest('Phase 3', '3.21', 'Toast Close Button', false, `Error: ${e.message}`);
        }

        console.log('\n%c📋 PHASE 4: EDGE CASE TESTS', 'background: #333; color: #fff; font-size: 16px; padding: 5px;');
        console.log('');

        // Test 4.1: Modal With Empty Content
        try {
            openModal('Empty Test', '');
            await sleep(200);

            const modal = document.getElementById('genericModal');
            const passed = modal.style.display === 'flex';

            logTest('Phase 4', '4.1', 'Modal With Empty Content', passed,
                   `Modal displayed with empty content: ${passed}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 4', '4.1', 'Modal With Empty Content', false, `Error: ${e.message}`);
        }

        // Test 4.2: Modal With No Buttons
        try {
            openModal('No Buttons', '<p>Test</p>', []);
            await sleep(200);

            const footer = document.getElementById('modalFooter');
            const passed = footer.querySelector('button') !== null;

            logTest('Phase 4', '4.2', 'Modal With No Buttons', passed,
                   `Default Close button added: ${passed}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 4', '4.2', 'Modal With No Buttons', false, `Error: ${e.message}`);
        }

        // Test 4.3: Form With Special Characters
        try {
            const html = createFormField('text', "Name's Field", 'specialField', {
                placeholder: 'Enter "value"'
            });

            openModal('Special Chars', html);
            await sleep(200);

            const passed = document.getElementById('specialField') !== null;

            logTest('Phase 4', '4.3', 'Form With Special Characters', passed,
                   `Handles special characters safely: ${passed}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 4', '4.3', 'Form With Special Characters', false, `Error: ${e.message}`);
        }

        // Test 4.4: Form Validation - All Valid
        try {
            const formHTML = createFormField('text', 'Name', 'validField', {
                required: true
            });

            openModal('Valid Form', formHTML);
            await sleep(200);

            document.getElementById('validField').value = 'Valid Name';

            const validation = validateForm();
            const passed = validation.valid === true && validation.errors.length === 0;

            logTest('Phase 4', '4.4', 'Form Validation - All Valid', passed,
                   `Validation.valid: ${validation.valid}, Errors: ${validation.errors.length}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 4', '4.4', 'Form Validation - All Valid', false, `Error: ${e.message}`);
        }

        // Test 4.5: Open Modal While Modal Open
        try {
            openModal('First Modal', '<p>First</p>');
            await sleep(200);

            openModal('Second Modal', '<p>Second</p>');
            await sleep(200);

            const modalTitle = document.getElementById('modalTitle');
            const passed = modalTitle.textContent === 'Second Modal';

            logTest('Phase 4', '4.5', 'Open Modal While Modal Open', passed,
                   `Second modal replaced first: ${passed}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 4', '4.5', 'Open Modal While Modal Open', false, `Error: ${e.message}`);
        }

        // Test 4.6: Close Modal When Not Open
        try {
            closeModal();
            await sleep(200);

            // Should not throw error
            logTest('Phase 4', '4.6', 'Close Modal When Not Open', true,
                   'No error thrown');
        } catch (e) {
            logTest('Phase 4', '4.6', 'Close Modal When Not Open', false, `Error: ${e.message}`);
        }

        // Test 4.7: Very Long Content
        try {
            let longContent = '';
            for (let i = 0; i < 50; i++) {
                longContent += `<p>Paragraph ${i + 1} - This is a long content test to ensure scrolling works properly.</p>`;
            }

            openModal('Long Content', longContent);
            await sleep(200);

            const modalBody = document.getElementById('modalBody');
            const passed = modalBody.scrollHeight > modalBody.clientHeight;

            logTest('Phase 4', '4.7', 'Very Long Content', passed,
                   `Body is scrollable: ${passed}`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 4', '4.7', 'Very Long Content', false, `Error: ${e.message}`);
        }

        // Test 4.8: Wide Modal
        try {
            openModal('Wide Modal', '<p>Test</p>', [], true);
            await sleep(200);

            const modalContainer = document.querySelector('.modal-container');
            const width = modalContainer.offsetWidth;
            const passed = width > 700; // Should be wider than default 600px

            logTest('Phase 4', '4.8', 'Wide Modal', passed,
                   `Modal width: ${width}px`);

            closeModal();
            await sleep(200);
        } catch (e) {
            logTest('Phase 4', '4.8', 'Wide Modal', false, `Error: ${e.message}`);
        }

        // Test 4.10: Rapid Open/Close
        try {
            for (let i = 0; i < 10; i++) {
                openModal(`Test ${i}`, `<p>Content ${i}</p>`);
                await sleep(50);
                closeModal();
                await sleep(50);
            }

            const modal = document.getElementById('genericModal');
            const passed = modal.style.display === 'none';

            logTest('Phase 4', '4.10', 'Rapid Open/Close', passed,
                   'No errors during rapid operations');
        } catch (e) {
            logTest('Phase 4', '4.10', 'Rapid Open/Close', false, `Error: ${e.message}`);
        }

        // Print Summary
        console.log('\n%c📊 TEST SUMMARY', 'background: #222; color: #bada55; font-size: 18px; padding: 10px;');
        console.log('%c='.repeat(60), 'color: #888;');
        console.log(`%cTotal Tests: ${totalTests}`, 'font-weight: bold; font-size: 14px;');
        console.log(`%c✅ Passed: ${passedTests}`, 'color: green; font-weight: bold; font-size: 14px;');
        console.log(`%c❌ Failed: ${failedTests}`, 'color: red; font-weight: bold; font-size: 14px;');
        console.log(`%cSuccess Rate: ${((passedTests / totalTests) * 100).toFixed(1)}%`, 'font-weight: bold; font-size: 14px;');
        console.log('');

        if (failedTests === 0) {
            console.log('%c🎉 ALL TESTS PASSED! Layer 1 is ready for Layer 2!', 'background: green; color: white; font-size: 16px; padding: 10px;');
        } else {
            console.log('%c⚠️ Some tests failed. Review the failures above.', 'background: orange; color: white; font-size: 16px; padding: 10px;');
        }

        // Return results object
        return {
            totalTests,
            passedTests,
            failedTests,
            successRate: ((passedTests / totalTests) * 100).toFixed(1) + '%',
            details: testResults
        };
    }

    // Run tests
    runAllTests().then(results => {
        console.log('\n%c✅ Test execution complete. Results stored in window.layer1TestResults', 'color: blue;');
        window.layer1TestResults = results;
    });
})();
