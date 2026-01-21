#!/bin/bash

# Layer 2 Automated Test Suite
# Tests that can be run without a browser

echo "🧪 LAYER 2 AUTOMATED TEST SUITE"
echo "================================"
echo ""

PASSED=0
FAILED=0

# Helper function
test_result() {
    if [ $1 -eq 0 ]; then
        echo "✅ PASSED: $2"
        ((PASSED++))
    else
        echo "❌ FAILED: $2"
        ((FAILED++))
    fi
}

echo "📋 PHASE 1: STATIC FILE VERIFICATION"
echo "-----------------------------------"

# Test 1.1: Create button in HTML
grep -q "btn-create-primary" templates/dashboard.html
test_result $? "Create button element exists in HTML"

# Test 1.2: Create button text
grep -q "Create Ingredient" templates/dashboard.html
test_result $? "Create button text is correct"

# Test 1.3: Button calls correct function
grep -q "openCreateIngredientModal" templates/dashboard.html
test_result $? "Button calls openCreateIngredientModal()"

# Test 1.4: Page header styling exists
grep -q "\.page-header" static/css/style.css
test_result $? "Page header CSS exists"

# Test 1.5: Create button styling exists
grep -q "\.btn-create-primary" static/css/style.css
test_result $? "Create button CSS exists"

echo ""
echo "📋 PHASE 2: JAVASCRIPT FUNCTION VERIFICATION"
echo "-------------------------------------------"

# Test 2.1: openCreateIngredientModal function
grep -q "function openCreateIngredientModal" static/js/dashboard.js
test_result $? "openCreateIngredientModal() function exists"

# Test 2.2: openEditIngredientModal function
grep -q "async function openEditIngredientModal" static/js/dashboard.js
test_result $? "openEditIngredientModal() function exists"

# Test 2.3: validateIngredientForm function
grep -q "function validateIngredientForm" static/js/dashboard.js
test_result $? "validateIngredientForm() function exists"

# Test 2.4: saveNewIngredient function
grep -q "async function saveNewIngredient" static/js/dashboard.js
test_result $? "saveNewIngredient() function exists"

# Test 2.5: updateIngredient function
grep -q "async function updateIngredient" static/js/dashboard.js
test_result $? "updateIngredient() function exists"

# Test 2.6: Form field creation for ingredient code
grep -q "ingredientCode" static/js/dashboard.js
test_result $? "Ingredient code field in form"

# Test 2.7: Form field creation for ingredient name
grep -q "ingredientName" static/js/dashboard.js
test_result $? "Ingredient name field in form"

# Test 2.8: Category selector used
grep -q "createCategorySelector.*ingredientCategory" static/js/dashboard.js
test_result $? "Category selector in create form"

# Test 2.9: Unit selector used
grep -q "createUnitSelector.*ingredientUnit" static/js/dashboard.js
test_result $? "Unit selector in create form"

# Test 2.10: API POST call for create
grep -q "fetch('/api/ingredients'" static/js/dashboard.js
test_result $? "API POST call for ingredient creation"

# Test 2.11: API PUT call for update
grep -q "fetch(\`/api/ingredients/\${ingredientId}\`" static/js/dashboard.js
test_result $? "API PUT call for ingredient update"

# Test 2.12: Success toast on create
grep -q "Ingredient created successfully" static/js/dashboard.js
test_result $? "Success message on create"

# Test 2.13: Success toast on update
grep -q "Ingredient updated successfully" static/js/dashboard.js
test_result $? "Success message on update"

# Test 2.14: Table refresh after save
grep -q "loadInventory()" static/js/dashboard.js
test_result $? "Table refresh call after save"

# Test 2.15: Edit button calls new function
grep -q "openEditIngredientModal(itemId)" static/js/dashboard.js
test_result $? "Edit button calls openEditIngredientModal()"

echo ""
echo "📋 PHASE 3: BACKEND API ENDPOINTS"
echo "--------------------------------"

# Test 3.1: GET endpoint exists
grep -q "@app.route('/api/ingredients/<int:ingredient_id>', methods=\['GET'\])" crud_operations.py
test_result $? "GET /api/ingredients/{id} endpoint exists"

# Test 3.2: POST endpoint exists
grep -q "@app.route('/api/ingredients', methods=\['POST'\])" crud_operations.py
test_result $? "POST /api/ingredients endpoint exists"

# Test 3.3: PUT endpoint exists
grep -q "@app.route('/api/ingredients/<int:ingredient_id>', methods=\['PUT'\])" crud_operations.py
test_result $? "PUT /api/ingredients/{id} endpoint exists"

# Test 3.4: GET function implementation
grep -q "def get_ingredient" crud_operations.py
test_result $? "get_ingredient() function exists"

# Test 3.5: Create function implementation
grep -q "def create_ingredient" crud_operations.py
test_result $? "create_ingredient() function exists"

# Test 3.6: Update function implementation
grep -q "def update_ingredient" crud_operations.py
test_result $? "update_ingredient() function exists"

echo ""
echo "📋 PHASE 4: VALIDATION LOGIC"
echo "---------------------------"

# Test 4.1: Code validation
grep -q "ingredientCode.*required" static/js/dashboard.js
test_result $? "Ingredient code validation exists"

# Test 4.2: Name validation
grep -q "ingredientName.*required" static/js/dashboard.js
test_result $? "Ingredient name validation exists"

# Test 4.3: Category validation
grep -q "ingredientCategory.*required" static/js/dashboard.js
test_result $? "Category validation exists"

# Test 4.4: Unit validation
grep -q "ingredientUnit.*required" static/js/dashboard.js
test_result $? "Unit validation exists"

# Test 4.5: Code format validation
grep -q "^[A-Z0-9_-]" static/js/dashboard.js
test_result $? "Code format regex validation exists"

# Test 4.6: Name length validation
grep -q "length.*2" static/js/dashboard.js
test_result $? "Name minimum length validation exists"

echo ""
echo "📊 TEST SUMMARY"
echo "==============="
TOTAL=$((PASSED + FAILED))
echo "Total Tests: $TOTAL"
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo "🎉 ALL AUTOMATED TESTS PASSED!"
    exit 0
else
    echo ""
    echo "⚠️ Some tests failed."
    exit 1
fi
