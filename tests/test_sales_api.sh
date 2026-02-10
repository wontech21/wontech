#!/bin/bash

# Sales Processing API Test Suite
# Tests Layer 4 backend without requiring Python packages

BASE_URL="http://127.0.0.1:5001"
TESTS_PASSED=0
TESTS_FAILED=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}${BOLD}============================================================${NC}"
    echo -e "${BLUE}${BOLD}$1${NC}"
    echo -e "${BLUE}${BOLD}============================================================${NC}\n"
}

print_test() {
    echo -ne "${BOLD}Testing:${NC} $1... "
}

print_pass() {
    ((TESTS_PASSED++))
    echo -e "${GREEN}✓ PASS${NC} $1"
}

print_fail() {
    ((TESTS_FAILED++))
    echo -e "${RED}✗ FAIL${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Setup test data
setup_test_data() {
    print_header "SETUP: Creating Test Data"

    sqlite3 inventory.db << 'EOF'
-- Check if test data exists
SELECT COUNT(*) FROM products WHERE product_code = 'TEST-PIZZA';
EOF

    local exists=$(sqlite3 inventory.db "SELECT COUNT(*) FROM products WHERE product_code = 'TEST-PIZZA';")

    if [ "$exists" -gt 0 ]; then
        print_info "Test data already exists, skipping setup"
        return 0
    fi

    print_info "Creating test ingredients and products..."

    sqlite3 inventory.db << 'EOF'
-- Create test ingredients
INSERT INTO ingredients (ingredient_code, ingredient_name, category, unit_of_measure, unit_cost, quantity_on_hand, reorder_level)
VALUES
    ('TEST-MOZ', 'Test Mozzarella', 'Cheese', 'lbs', 5.00, 100.0, 20.0),
    ('TEST-DOUGH', 'Test Pizza Dough', 'Bread', 'lbs', 2.00, 80.0, 15.0),
    ('TEST-SAUCE', 'Test Tomato Sauce', 'Sauces', 'lbs', 3.00, 50.0, 10.0),
    ('TEST-BEEF', 'Test Ground Beef', 'Meat', 'lbs', 6.00, 150.0, 30.0),
    ('TEST-SHELL', 'Test Taco Shells', 'Bread', 'each', 0.15, 500.0, 100.0);

-- Create test products
INSERT INTO products (product_code, product_name, category, unit_of_measure, selling_price)
VALUES
    ('TEST-PIZZA', 'Test Cheese Pizza', 'Pizza', 'each', 12.99),
    ('TEST-TACOS', 'Test Beef Tacos', 'Entrees', 'each', 8.99);

-- Create recipes
INSERT INTO recipes (product_id, ingredient_id, quantity_needed, unit_of_measure)
SELECT
    p.id,
    i.id,
    qty,
    unit
FROM (
    SELECT 'TEST-PIZZA' as pcode, 'TEST-MOZ' as icode, 0.5 as qty, 'lbs' as unit
    UNION SELECT 'TEST-PIZZA', 'TEST-DOUGH', 0.3, 'lbs'
    UNION SELECT 'TEST-PIZZA', 'TEST-SAUCE', 0.2, 'lbs'
    UNION SELECT 'TEST-TACOS', 'TEST-BEEF', 0.33, 'lbs'
    UNION SELECT 'TEST-TACOS', 'TEST-SHELL', 3.0, 'each'
) recipe_data
JOIN products p ON p.product_code = recipe_data.pcode
JOIN ingredients i ON i.ingredient_code = recipe_data.icode;
EOF

    if [ $? -eq 0 ]; then
        print_pass "Test data created successfully"
        return 0
    else
        print_fail "Failed to create test data"
        return 1
    fi
}

# Cleanup test data
cleanup_test_data() {
    print_header "CLEANUP: Removing Test Data"

    sqlite3 inventory.db << 'EOF'
DELETE FROM recipes WHERE product_id IN (SELECT id FROM products WHERE product_code LIKE 'TEST-%');
DELETE FROM products WHERE product_code LIKE 'TEST-%';
DELETE FROM ingredients WHERE ingredient_code LIKE 'TEST-%';
DELETE FROM sales_history WHERE product_name LIKE 'Test %';
EOF

    if [ $? -eq 0 ]; then
        print_pass "Test data cleaned up"
    else
        print_fail "Cleanup failed"
    fi
}

# Test 1: Parse CSV
test_parse_csv() {
    print_test "CSV Parsing"

    local response=$(curl -s -X POST "$BASE_URL/api/sales/parse-csv" \
        -H "Content-Type: application/json" \
        -d '{"csv_text":"Product Name, Quantity\nTest Cheese Pizza, 10\nTest Beef Tacos, 25"}')

    if echo "$response" | grep -q '"success": *true'; then
        local count=$(echo "$response" | grep -o '"count": *[0-9]*' | grep -o '[0-9]*')
        if [ "$count" == "2" ]; then
            print_pass "Parsed 2 sales correctly"
        else
            print_fail "Expected 2 sales, got $count"
        fi
    else
        print_fail "API returned error"
        echo "$response"
    fi
}

# Test 2: Preview Sales
test_preview_sales() {
    print_test "Sales Preview Calculation"

    local response=$(curl -s -X POST "$BASE_URL/api/sales/preview" \
        -H "Content-Type: application/json" \
        -d '{
            "sale_date": "2026-01-20",
            "sales_data": [
                {"product_name": "Test Cheese Pizza", "quantity": 10},
                {"product_name": "Test Beef Tacos", "quantity": 25}
            ]
        }')

    if echo "$response" | grep -q '"success": *true'; then
        local revenue=$(echo "$response" | grep -o '"revenue": *[0-9.]*' | head -1 | grep -o '[0-9.]*')
        if [ -n "$revenue" ]; then
            print_pass "Preview calculated (Revenue: \$$revenue)"
        else
            print_fail "No revenue calculated"
        fi
    else
        print_fail "API returned error"
        echo "$response"
    fi
}

# Test 3: Unmatched Products
test_unmatched_products() {
    print_test "Unmatched Product Detection"

    local response=$(curl -s -X POST "$BASE_URL/api/sales/preview" \
        -H "Content-Type: application/json" \
        -d '{
            "sale_date": "2026-01-20",
            "sales_data": [
                {"product_name": "Test Cheese Pizza", "quantity": 10},
                {"product_name": "Nonexistent Product", "quantity": 5}
            ]
        }')

    if echo "$response" | grep -q '"unmatched"'; then
        if echo "$response" | grep -q "Nonexistent Product"; then
            print_pass "Correctly identified unmatched product"
        else
            print_fail "Did not detect unmatched product"
        fi
    else
        print_fail "No unmatched array in response"
    fi
}

# Test 4: Apply Sales
test_apply_sales() {
    print_test "Apply Sales to Inventory"

    # Get before inventory
    local before=$(sqlite3 inventory.db "SELECT quantity_on_hand FROM ingredients WHERE ingredient_code = 'TEST-MOZ';")
    print_info "Before - Mozzarella: $before lbs"

    local response=$(curl -s -X POST "$BASE_URL/api/sales/apply" \
        -H "Content-Type: application/json" \
        -d '{
            "sale_date": "2026-01-20",
            "sales_data": [
                {"product_name": "Test Cheese Pizza", "quantity": 10}
            ]
        }')

    if echo "$response" | grep -q '"success": *true'; then
        # Get after inventory
        local after=$(sqlite3 inventory.db "SELECT quantity_on_hand FROM ingredients WHERE ingredient_code = 'TEST-MOZ';")
        print_info "After - Mozzarella: $after lbs"

        local deducted=$(echo "$before - $after" | bc)
        local expected="5.0"

        if [ "$deducted" == "$expected" ] || [ "${deducted%.*}" == "${expected%.*}" ]; then
            print_pass "Inventory correctly deducted ($deducted lbs)"
        else
            print_fail "Expected $expected lbs deducted, got $deducted"
        fi
    else
        print_fail "API returned error"
        echo "$response"
    fi
}

# Test 5: Sales History
test_sales_history() {
    print_test "Sales History Retrieval"

    local response=$(curl -s "$BASE_URL/api/sales/history")

    if echo "$response" | grep -q '\['; then
        local count=$(echo "$response" | grep -o '"product_name"' | wc -l | xargs)
        if [ "$count" -gt 0 ]; then
            print_pass "Retrieved $count sale(s) from history"
        else
            print_pass "Endpoint works (empty result)"
        fi
    else
        print_fail "Invalid response format"
    fi
}

# Test 6: Sales Summary
test_sales_summary() {
    print_test "Sales Summary Statistics"

    local response=$(curl -s "$BASE_URL/api/sales/summary")

    if echo "$response" | grep -q '"summary"'; then
        if echo "$response" | grep -q '"total_revenue"'; then
            print_pass "Summary statistics retrieved"
        else
            print_fail "Missing required fields"
        fi
    else
        print_fail "Invalid response format"
    fi
}

# Main test runner
run_all_tests() {
    echo -e "\n${BOLD}============================================================"
    echo "🧪 LAYER 4: SALES PROCESSING TEST SUITE"
    echo -e "============================================================${NC}\n"
    echo -e "Testing backend at: ${BLUE}$BASE_URL${NC}"
    echo -e "Database: ${BLUE}inventory.db${NC}\n"

    # Check if server is running
    if ! curl -s "$BASE_URL/api/products/costs" > /dev/null 2>&1; then
        echo -e "${RED}ERROR: Flask server is not running at $BASE_URL${NC}"
        echo -e "${YELLOW}Please start the server first with: python3 app.py${NC}\n"
        exit 1
    fi

    # Setup
    setup_test_data || exit 1

    # Run tests
    print_header "RUNNING TESTS"

    test_parse_csv
    test_preview_sales
    test_unmatched_products
    test_apply_sales
    test_sales_history
    test_sales_summary

    # Cleanup
    cleanup_test_data

    # Results
    print_header "TEST RESULTS"

    local total=$((TESTS_PASSED + TESTS_FAILED))
    local pass_rate=$((TESTS_PASSED * 100 / total))

    echo "Total Tests: ${BOLD}$total${NC}"
    echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
    echo -e "Pass Rate: ${GREEN}$pass_rate%${NC}\n"

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}${BOLD}✓ ALL TESTS PASSED!${NC}"
        echo -e "${GREEN}Layer 4 backend is ready for frontend implementation.${NC}\n"
        return 0
    else
        echo -e "${RED}${BOLD}✗ SOME TESTS FAILED${NC}"
        echo -e "${RED}Please fix issues before continuing.${NC}\n"
        return 1
    fi
}

# Run tests
run_all_tests
exit $?
