#!/usr/bin/env bash
# ============================================================================
# D6 Voice AI Write Actions — Test Script
# Tests all 7 action tools (~20 action types) against local server.
#
# Usage:  ./scripts/test_voice_actions.sh
# Prereq: Server running at localhost:5001
# ============================================================================

set -euo pipefail

BASE="http://localhost:5001"
COOKIE_JAR="/tmp/voice_test_cookies.txt"
PASS=0
FAIL=0
SKIP=0
RESULTS=()

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Helpers ---
log_header() { echo -e "\n${BOLD}${CYAN}=== $1 ===${NC}"; }
log_test()   { printf "  %-55s " "$1"; }

check_result() {
    local label="$1"
    local response="$2"
    local expect_success="$3"  # "true" or "false"
    local expect_substr="${4:-}"

    local success
    success=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d.get('success','')).lower())" 2>/dev/null || echo "parse_error")

    if [[ "$success" == "parse_error" ]]; then
        echo -e "${RED}FAIL${NC} (bad JSON)"
        echo "    Response: ${response:0:200}"
        FAIL=$((FAIL+1))
        RESULTS+=("FAIL: $label (bad JSON)")
        return
    fi

    if [[ "$success" != "$expect_success" ]]; then
        local msg
        msg=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message','') or d.get('error',''))" 2>/dev/null)
        echo -e "${RED}FAIL${NC} (expected success=$expect_success, got $success)"
        echo "    Message: $msg"
        FAIL=$((FAIL+1))
        RESULTS+=("FAIL: $label")
        return
    fi

    if [[ -n "$expect_substr" ]]; then
        if echo "$response" | grep -qi "$expect_substr"; then
            echo -e "${GREEN}PASS${NC}"
            PASS=$((PASS+1))
            RESULTS+=("PASS: $label")
        else
            echo -e "${RED}FAIL${NC} (missing: '$expect_substr')"
            echo "    Response: ${response:0:200}"
            FAIL=$((FAIL+1))
            RESULTS+=("FAIL: $label (missing substring)")
        fi
    else
        echo -e "${GREEN}PASS${NC}"
        PASS=$((PASS+1))
        RESULTS+=("PASS: $label")
    fi
}

action() {
    local action_name="$1"
    local params_json="$2"
    curl -s -b "$COOKIE_JAR" -X POST "$BASE/api/voice/action" \
        -H "Content-Type: application/json" \
        -d "{\"action\": \"$action_name\", \"params\": $params_json}"
}

# ============================================================================
# 0. LOGIN
# ============================================================================
log_header "LOGIN"
rm -f "$COOKIE_JAR"

echo -e "  Logging in as admin@wontech.com..."
LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST "$BASE/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@wontech.com","password":"admin123"}' \
    -w "\n%{http_code}")
HTTP_CODE=$(echo "$LOGIN_RESP" | tail -1)

if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "302" ]]; then
    echo -e "  ${GREEN}Login successful${NC} (HTTP $HTTP_CODE)"
else
    echo -e "  ${RED}Login failed${NC} (HTTP $HTTP_CODE)"
    echo "  Cannot proceed without auth. Exiting."
    exit 1
fi

# Quick auth check — hit a protected endpoint
AUTH_CHECK=$(curl -s -b "$COOKIE_JAR" "$BASE/api/employees" -w "\n%{http_code}")
AUTH_CODE=$(echo "$AUTH_CHECK" | tail -1)
if [[ "$AUTH_CODE" != "200" ]]; then
    echo -e "  ${RED}Auth check failed${NC} — /api/employees returned $AUTH_CODE"
    echo "  Session cookie may not have been set. Exiting."
    exit 1
fi
echo -e "  ${GREEN}Auth verified${NC}"

# ============================================================================
# 1. ATTENDANCE (4 actions)
# ============================================================================
log_header "MANAGE ATTENDANCE"

# Clean up: clock out John Smith if still clocked in from prior run
curl -s -b "$COOKIE_JAR" -X POST "$BASE/api/voice/action" \
    -H "Content-Type: application/json" \
    -d '{"action":"manage_attendance","params":{"action_type":"clock_out","employee_name":"John Smith"}}' > /dev/null 2>&1

# 1a. Clock in by name
log_test "Clock in John Smith"
R=$(action "manage_attendance" '{"action_type":"clock_in","employee_name":"John Smith"}')
check_result "Clock in John Smith" "$R" "true" "clocked in"

# 1b. Clock in duplicate → error
log_test "Clock in John Smith again (expect error)"
R=$(action "manage_attendance" '{"action_type":"clock_in","employee_name":"John Smith"}')
check_result "Clock in duplicate" "$R" "false" "already clocked in"

# 1c. Break start
log_test "Start break for John Smith"
R=$(action "manage_attendance" '{"action_type":"break_start","employee_name":"John Smith"}')
check_result "Break start" "$R" "true" "started break"

# 1d. Break start duplicate → error
log_test "Start break again (expect error)"
R=$(action "manage_attendance" '{"action_type":"break_start","employee_name":"John Smith"}')
check_result "Break start duplicate" "$R" "false" "already on break"

# 1e. Break end
log_test "End break for John Smith"
R=$(action "manage_attendance" '{"action_type":"break_end","employee_name":"John Smith"}')
check_result "Break end" "$R" "true" "ended break"

# 1f. Break end when not on break → error
log_test "End break again (expect error)"
R=$(action "manage_attendance" '{"action_type":"break_end","employee_name":"John Smith"}')
check_result "Break end not on break" "$R" "false" "not on break"

# 1g. Clock out
log_test "Clock out John Smith"
R=$(action "manage_attendance" '{"action_type":"clock_out","employee_name":"John Smith"}')
check_result "Clock out" "$R" "true" "clocked out"

# 1h. Clock out when not clocked in → error
log_test "Clock out again (expect error)"
R=$(action "manage_attendance" '{"action_type":"clock_out","employee_name":"John Smith"}')
check_result "Clock out not in" "$R" "false" "not clocked in"

# 1i. Fuzzy match by first name
log_test "Clock in by first name 'Emily'"
R=$(action "manage_attendance" '{"action_type":"clock_in","employee_name":"Emily"}')
check_result "Fuzzy match first name" "$R" "true" "clocked in"
# Clean up
action "manage_attendance" '{"action_type":"clock_out","employee_name":"Emily"}' > /dev/null 2>&1

# 1j. Ambiguous name → error
log_test "Ambiguous name 'Gabriel' (expect error)"
R=$(action "manage_attendance" '{"action_type":"clock_in","employee_name":"Gabriel"}')
check_result "Ambiguous name" "$R" "false" "Multiple employees"

# 1k. Nonexistent name → error
log_test "Nonexistent employee (expect error)"
R=$(action "manage_attendance" '{"action_type":"clock_in","employee_name":"Zzzznotreal"}')
check_result "Nonexistent employee" "$R" "false" "No employee"

# 1l. By ID
log_test "Clock in by employee_id=1"
R=$(action "manage_attendance" '{"action_type":"clock_in","employee_id":1}')
check_result "Clock in by ID" "$R" "true" "clocked in"
action "manage_attendance" '{"action_type":"clock_out","employee_id":1}' > /dev/null 2>&1

# ============================================================================
# 2. SCHEDULE (4 actions)
# ============================================================================
log_header "MANAGE SCHEDULE"

TOMORROW=$(date -v+1d '+%Y-%m-%d' 2>/dev/null || date -d '+1 day' '+%Y-%m-%d')

# 2a. Create shift
log_test "Create shift for Emily tomorrow 9-5"
R=$(action "manage_schedule" "{\"action_type\":\"create_shift\",\"employee_name\":\"Emily\",\"date\":\"$TOMORROW\",\"start_time\":\"09:00\",\"end_time\":\"17:00\",\"position\":\"Server\"}")
check_result "Create shift" "$R" "true" "Shift created"

# Extract schedule ID for cancel test
SCHED_ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('entity_id',''))" 2>/dev/null || echo "")

# 2b. Create conflicting shift → error
log_test "Create conflicting shift (expect error)"
R=$(action "manage_schedule" "{\"action_type\":\"create_shift\",\"employee_name\":\"Emily\",\"date\":\"$TOMORROW\",\"start_time\":\"10:00\",\"end_time\":\"14:00\"}")
check_result "Conflicting shift" "$R" "false" "conflicting"

# 2c. Cancel shift
if [[ -n "$SCHED_ID" && "$SCHED_ID" != "None" ]]; then
    log_test "Cancel shift #$SCHED_ID"
    R=$(action "manage_schedule" "{\"action_type\":\"cancel_shift\",\"schedule_id\":$SCHED_ID}")
    check_result "Cancel shift" "$R" "true" "cancelled"
else
    log_test "Cancel shift (skipped — no ID)"
    echo -e "${YELLOW}SKIP${NC}"
    SKIP=$((SKIP+1))
fi

# 2d. Approve time-off request
log_test "Approve time-off request #5"
R=$(action "manage_schedule" '{"action_type":"approve_time_off","request_id":5}')
# Could be success or already approved
SUCCESS=$(echo "$R" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('success','')).lower())" 2>/dev/null)
if [[ "$SUCCESS" == "true" ]]; then
    check_result "Approve time off" "$R" "true" "approved"
else
    log_test "  (request already processed)"
    check_result "Approve time off (already)" "$R" "false" "already"
fi

# 2e. Deny time-off request
log_test "Deny time-off request #6"
R=$(action "manage_schedule" '{"action_type":"deny_time_off","request_id":6,"reason":"Understaffed that week"}')
SUCCESS=$(echo "$R" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('success','')).lower())" 2>/dev/null)
if [[ "$SUCCESS" == "true" ]]; then
    check_result "Deny time off" "$R" "true" "denied"
else
    check_result "Deny time off (already)" "$R" "false" "already"
fi

# 2f. Missing required fields → error
log_test "Create shift missing date (expect error)"
R=$(action "manage_schedule" '{"action_type":"create_shift","employee_name":"Emily"}')
check_result "Missing shift fields" "$R" "false" "required"

# ============================================================================
# 3. ORDERS (2 actions)
# ============================================================================
log_header "MANAGE ORDERS"

# 3a. Update order status
log_test "Update order #76 to 'preparing'"
R=$(action "manage_orders" '{"action_type":"update_status","order_id":76,"status":"preparing"}')
check_result "Update order status" "$R" "true" "preparing"

# 3b. Update to ready (tests actual_ready_time)
log_test "Update order #76 to 'ready'"
R=$(action "manage_orders" '{"action_type":"update_status","order_id":76,"status":"ready"}')
check_result "Update to ready" "$R" "true" "ready"

# 3c. Invalid status → error
log_test "Invalid status 'flying' (expect error)"
R=$(action "manage_orders" '{"action_type":"update_status","order_id":76,"status":"flying"}')
check_result "Invalid status" "$R" "false" "Invalid status"

# 3d. Void order — use #74 (un-void it first if needed from prior run)
# Reset: set back to confirmed so the test is idempotent
curl -s -b "$COOKIE_JAR" -X POST "$BASE/api/voice/action" \
    -H "Content-Type: application/json" \
    -d '{"action":"manage_orders","params":{"action_type":"update_status","order_id":74,"status":"confirmed"}}' > /dev/null 2>&1
log_test "Void order #74"
R=$(action "manage_orders" '{"action_type":"void_order","order_id":74,"reason":"Test void via voice"}')
check_result "Void order" "$R" "true" "voided"

# 3e. Void already voided → error
log_test "Void order #74 again (expect error)"
R=$(action "manage_orders" '{"action_type":"void_order","order_id":74}')
check_result "Void already voided" "$R" "false" "already voided"

# 3f. Nonexistent order → error
log_test "Void nonexistent order #99999 (expect error)"
R=$(action "manage_orders" '{"action_type":"void_order","order_id":99999}')
check_result "Nonexistent order" "$R" "false" "not found"

# 3g. Missing order_id → error
log_test "Update status without order_id (expect error)"
R=$(action "manage_orders" '{"action_type":"update_status","status":"ready"}')
check_result "Missing order_id" "$R" "false" "required"

# ============================================================================
# 4. 86 (2 actions)
# ============================================================================
log_header "MANAGE 86"

# 4a. 86 a product by name
log_test "86 'Beef Tacos'"
R=$(action "manage_86" '{"action_type":"eighty_six","product_name":"Beef Tacos"}')
check_result "86 product" "$R" "true" "86"

# 4b. Un-86
log_test "Un-86 'Beef Tacos'"
R=$(action "manage_86" '{"action_type":"un_eighty_six","product_name":"Beef Tacos"}')
check_result "Un-86 product" "$R" "true" "un-86"

# 4c. Fuzzy match
log_test "86 fuzzy match 'Burrito'"
R=$(action "manage_86" '{"action_type":"eighty_six","product_name":"Burrito"}')
check_result "86 fuzzy match" "$R" "true" "86"
action "manage_86" '{"action_type":"un_eighty_six","product_name":"Burrito"}' > /dev/null 2>&1

# 4d. Nonexistent product → error
log_test "86 nonexistent 'Unicorn Steak' (expect error)"
R=$(action "manage_86" '{"action_type":"eighty_six","product_name":"Unicorn Steak"}')
check_result "86 nonexistent" "$R" "false" "No product"

# 4e. By product_id
log_test "86 by product_id=1"
R=$(action "manage_86" '{"action_type":"eighty_six","product_id":1}')
check_result "86 by ID" "$R" "true" "86"
action "manage_86" '{"action_type":"un_eighty_six","product_id":1}' > /dev/null 2>&1

# ============================================================================
# 5. INVENTORY (3 actions)
# ============================================================================
log_header "MANAGE INVENTORY"

# 5a. Adjust quantity
log_test "Set 'Yeast' quantity to 150"
R=$(action "manage_inventory" '{"action_type":"adjust_quantity","item_name":"Yeast","new_quantity":150,"unit":"oz"}')
check_result "Adjust quantity" "$R" "true" "150"

# 5b. Restore original
log_test "Restore 'Yeast' quantity to 200"
R=$(action "manage_inventory" '{"action_type":"adjust_quantity","item_name":"Yeast","new_quantity":200}')
check_result "Restore quantity" "$R" "true" "200"

# 5c. Toggle active
log_test "Toggle 'Potato Roll' active status"
R=$(action "manage_inventory" '{"action_type":"toggle_active","item_name":"Potato Roll"}')
check_result "Toggle active" "$R" "true" ""

# Restore
action "manage_inventory" '{"action_type":"toggle_active","item_name":"Potato Roll"}' > /dev/null 2>&1

# 5d. Missing quantity → error
log_test "Adjust without new_quantity (expect error)"
R=$(action "manage_inventory" '{"action_type":"adjust_quantity","item_name":"Yeast"}')
check_result "Missing quantity" "$R" "false" "required"

# 5e. Nonexistent ingredient → error
log_test "Adjust nonexistent 'Dragon Eggs' (expect error)"
R=$(action "manage_inventory" '{"action_type":"adjust_quantity","item_name":"Dragon Eggs","new_quantity":5}')
check_result "Nonexistent ingredient" "$R" "false" "Dragon Eggs"

# 5f. Update invoice payment status to PAID
log_test "Mark invoice INV-01000 as PAID"
R=$(action "manage_inventory" '{"action_type":"update_invoice_status","invoice_number":"INV-01000","payment_status":"PAID"}')
check_result "Invoice PAID" "$R" "true" "PAID"

# 5g. Update back to UNPAID
log_test "Mark invoice INV-01000 as UNPAID"
R=$(action "manage_inventory" '{"action_type":"update_invoice_status","invoice_number":"INV-01000","payment_status":"UNPAID"}')
check_result "Invoice UNPAID" "$R" "true" "UNPAID"

# 5h. Nonexistent invoice → error
log_test "Update nonexistent invoice (expect error)"
R=$(action "manage_inventory" '{"action_type":"update_invoice_status","invoice_number":"FAKE-999"}')
check_result "Nonexistent invoice" "$R" "false" "not found"

# ============================================================================
# 6. PAYROLL (2 actions)
# ============================================================================
log_header "MANAGE PAYROLL"

# Use a test period unlikely to conflict
TEST_START="2026-02-09"
TEST_END="2026-02-15"

# Clean up any leftover from prior test runs
curl -s -b "$COOKIE_JAR" -X POST "$BASE/api/voice/action" \
    -H "Content-Type: application/json" \
    -d "{\"action\":\"manage_payroll\",\"params\":{\"action_type\":\"unprocess\",\"period_start\":\"$TEST_START\",\"period_end\":\"$TEST_END\"}}" > /dev/null 2>&1

# 6a. Process payroll
log_test "Process payroll $TEST_START to $TEST_END"
R=$(action "manage_payroll" "{\"action_type\":\"process\",\"period_start\":\"$TEST_START\",\"period_end\":\"$TEST_END\",\"period_type\":\"weekly\"}")
check_result "Process payroll" "$R" "true" "processed"

# 6b. Process again → error (already processed)
log_test "Process same period again (expect error)"
R=$(action "manage_payroll" "{\"action_type\":\"process\",\"period_start\":\"$TEST_START\",\"period_end\":\"$TEST_END\"}")
check_result "Process duplicate" "$R" "false" "already processed"

# 6c. Unprocess
log_test "Unprocess payroll $TEST_START to $TEST_END"
R=$(action "manage_payroll" "{\"action_type\":\"unprocess\",\"period_start\":\"$TEST_START\",\"period_end\":\"$TEST_END\"}")
check_result "Unprocess payroll" "$R" "true" "unprocessed"

# 6d. Unprocess nonexistent → error
log_test "Unprocess nonexistent period (expect error)"
R=$(action "manage_payroll" '{"action_type":"unprocess","period_start":"1999-01-01","period_end":"1999-01-07"}')
check_result "Unprocess nonexistent" "$R" "false" "No payroll"

# 6e. Missing dates → error
log_test "Process without dates (expect error)"
R=$(action "manage_payroll" '{"action_type":"process"}')
check_result "Missing dates" "$R" "false" "required"

# ============================================================================
# 7. MENU (3 actions)
# ============================================================================
log_header "MANAGE MENU"

# 7a. Update price (products table)
log_test "Update 'Supreme Pizza' to \$21.99"
R=$(action "manage_menu" '{"action_type":"update_price","item_name":"Supreme Pizza","new_price":21.99}')
check_result "Update price" "$R" "true" "21.99"

# 7b. Restore price
log_test "Restore Supreme Pizza to \$20.99"
R=$(action "manage_menu" '{"action_type":"update_price","item_name":"Supreme Pizza","new_price":20.99}')
check_result "Restore price" "$R" "true" "20.99"

# 7c. Fuzzy match — partial name
log_test "Update 'Classic Burger' to \$14.99"
R=$(action "manage_menu" '{"action_type":"update_price","item_name":"Classic Burger","new_price":14.99}')
check_result "Fuzzy price update" "$R" "true" "14.99"

# Restore
action "manage_menu" '{"action_type":"update_price","item_name":"Classic Burger","new_price":12.99}' > /dev/null 2>&1

# 7d. Missing price → error
log_test "Update price without new_price (expect error)"
R=$(action "manage_menu" '{"action_type":"update_price","item_name":"Beef Tacos"}')
check_result "Missing price" "$R" "false" "required"

# 7e. Toggle product availability (86/un-86 via manage_menu)
log_test "Mark 'Fish and Chips' unavailable"
R=$(action "manage_menu" '{"action_type":"toggle_item","item_name":"Fish and Chips","active":false}')
check_result "Mark unavailable" "$R" "true" "unavailable"

# 7f. Mark available again
log_test "Mark 'Fish and Chips' available"
R=$(action "manage_menu" '{"action_type":"toggle_item","item_name":"Fish and Chips","active":true}')
check_result "Mark available" "$R" "true" "available"

# 7g. Nonexistent product → error
log_test "Toggle nonexistent 'Alien Pizza' (expect error)"
R=$(action "manage_menu" '{"action_type":"toggle_item","item_name":"Alien Pizza"}')
check_result "Nonexistent product" "$R" "false" "Alien"

# 7h. Update business hours
log_test "Set Monday hours to 10:00-22:00"
R=$(action "manage_menu" '{"action_type":"update_hours","day":"monday","open_time":"10:00","close_time":"22:00"}')
check_result "Update hours" "$R" "true" "Monday"

# 7i. Restore Monday hours
log_test "Restore Monday hours to 09:00-21:30"
R=$(action "manage_menu" '{"action_type":"update_hours","day":"monday","open_time":"09:00","close_time":"21:30"}')
check_result "Restore hours" "$R" "true" "Monday"

# 7j. Set day as closed
log_test "Set Sunday as closed"
R=$(action "manage_menu" '{"action_type":"update_hours","day":"sunday","is_closed":true}')
check_result "Set closed" "$R" "true" "closed"

# 7k. Reopen Sunday
log_test "Reopen Sunday 11:00-20:00"
R=$(action "manage_menu" '{"action_type":"update_hours","day":"sunday","open_time":"11:00","close_time":"20:00","is_closed":false}')
check_result "Reopen day" "$R" "true" "Sunday"

# 7l. Invalid day → error
log_test "Update hours for 'funday' (expect error)"
R=$(action "manage_menu" '{"action_type":"update_hours","day":"funday"}')
check_result "Invalid day" "$R" "false" "Invalid day"

# ============================================================================
# 8. AUTH GUARD — non-admin should be rejected
# ============================================================================
log_header "AUTH GUARD"

log_test "Unauthenticated request (expect non-200)"
AUTH_RESP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/voice/action" \
    -H "Content-Type: application/json" \
    -d '{"action":"manage_attendance","params":{"action_type":"clock_in","employee_name":"John Smith"}}')
# Should get 302 (redirect to login), 401, or 403 — anything but 200
if [[ "$AUTH_RESP" != "200" ]]; then
    echo -e "${GREEN}PASS${NC} (HTTP $AUTH_RESP)"
    PASS=$((PASS+1))
    RESULTS+=("PASS: Unauthenticated rejected (HTTP $AUTH_RESP)")
else
    echo -e "${RED}FAIL${NC} (got HTTP 200 — should have been rejected)"
    FAIL=$((FAIL+1))
    RESULTS+=("FAIL: Unauthenticated not rejected")
fi

# ============================================================================
# 9. UNKNOWN ACTION → error
# ============================================================================
log_header "EDGE CASES"

log_test "Unknown action 'manage_unicorns' (expect error)"
R=$(action "manage_unicorns" '{"action_type":"fly"}')
check_result "Unknown action" "$R" "false" "Unknown action"

log_test "Unknown action_type in valid tool (expect error)"
R=$(action "manage_attendance" '{"action_type":"teleport","employee_name":"John Smith"}')
check_result "Unknown action_type" "$R" "false" "Unknown"

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${BOLD}  RESULTS: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$SKIP skipped${NC}"
echo -e "${BOLD}============================================${NC}"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo -e "${RED}Failed tests:${NC}"
    for r in "${RESULTS[@]}"; do
        if [[ "$r" == FAIL* ]]; then
            echo "  - ${r#FAIL: }"
        fi
    done
fi

# Cleanup
rm -f "$COOKIE_JAR"

echo ""
exit $FAIL
