# Voice AI — Write Actions ("Execute Functions")

## Context

The voice AI assistant currently has **read-only** access — it can query any data via 11 domain tools + ad-hoc SQL. The user wants the AI to **execute functions** within the digital infrastructure: clock employees in, approve time off, 86 items, process payroll, etc.

**Why a centralized action endpoint:** Many existing write endpoints are self-service only (e.g., attendance clock-in uses the logged-in user — no admin-on-behalf-of). Rather than retrofitting every endpoint, we create a single `POST /api/voice/action` that handles name resolution, admin-override logic, audit logging, and execution in one place.

---

## Architecture

```
User speaks: "Clock in John"
        ↓
OpenAI calls: manage_attendance({ action_type: "clock_in", employee_name: "John" })
        ↓
Browser receives function call via WebRTC data channel
        ↓
JS POSTs to: /api/voice/action
    { "action": "manage_attendance", "params": { "action_type": "clock_in", "employee_name": "John" } }
        ↓
Backend:
    1. Resolve "John" → employee_id 47
    2. Validate (not already clocked in, etc.)
    3. Execute (INSERT into attendance)
    4. Audit log
    5. Return { success: true, message: "John Smith clocked in at 2:15 PM" }
        ↓
JS sends result back to OpenAI → AI speaks confirmation
```

**Confirmation flow:** The system prompt instructs the AI to ALWAYS describe the action and ask "Shall I go ahead?" before calling any write tool. The user says "yes" → AI calls the tool. Natural voice UX, no special code needed.

---

## Action Tools (7 tools, ~20 action types)

### 1. `manage_attendance`
| Action | Description | Key Params |
|--------|-------------|------------|
| `clock_in` | Clock an employee in | `employee_name` or `employee_id` |
| `clock_out` | Clock an employee out | `employee_name` or `employee_id` |
| `break_start` | Start employee break | `employee_name` or `employee_id` |
| `break_end` | End employee break | `employee_name` or `employee_id` |

*Note: Existing endpoints are self-service only. The action handler creates attendance records directly on behalf of the employee.*

### 2. `manage_schedule`
| Action | Description | Key Params |
|--------|-------------|------------|
| `create_shift` | Create a schedule shift | `employee_name/id`, `date`, `start_time`, `end_time`, `position` (optional) |
| `cancel_shift` | Cancel/delete a shift | `schedule_id` or `employee_name` + `date` |
| `approve_time_off` | Approve a pending request | `request_id` or `employee_name` |
| `deny_time_off` | Deny a pending request | `request_id` or `employee_name`, `reason` |

### 3. `manage_orders`
| Action | Description | Key Params |
|--------|-------------|------------|
| `update_status` | Change order status | `order_id`, `status` (preparing/ready/completed/picked_up/delivered) |
| `void_order` | Void an order (reverses inventory) | `order_id`, `reason` |

### 4. `manage_86`
| Action | Description | Key Params |
|--------|-------------|------------|
| `eighty_six` | Mark item as unavailable | `product_name` or `product_id`, `reason` |
| `un_eighty_six` | Mark item as available again | `product_name` or `product_id` |

### 5. `manage_inventory`
| Action | Description | Key Params |
|--------|-------------|------------|
| `adjust_quantity` | Update stock level | `item_name` or `item_id`, `new_quantity`, `unit` |
| `toggle_active` | Activate/deactivate item | `item_name` or `item_id` |
| `update_invoice_status` | Mark invoice as paid/unpaid | `invoice_number`, `payment_status` |

### 6. `manage_payroll`
| Action | Description | Key Params |
|--------|-------------|------------|
| `process` | Process payroll for a period | `period_start`, `period_end`, `period_type` (weekly/biweekly/monthly) |
| `unprocess` | Reverse processed payroll | `period_start`, `period_end` |

### 7. `manage_menu`
| Action | Description | Key Params |
|--------|-------------|------------|
| `update_price` | Change menu item price | `item_name` or `item_id`, `size_name`, `new_price` |
| `toggle_item` | Enable/disable menu item | `item_name` or `item_id`, `active` (true/false) |
| `update_hours` | Change business hours | `day`, `open_time`, `close_time`, `is_closed` |

---

## Files to Change

### 1. `routes/voice_routes.py` — Add action tools + action endpoint

**Add to VOICE_TOOLS:** 7 new action tool definitions (same format as existing read tools).

**New endpoint:** `POST /api/voice/action`
- Admin-only (super_admin or org_admin)
- Receives `{ action, params }`
- Dispatch table maps action names → handler functions
- Each handler: resolve names → validate → execute → audit log → return result

**Helper functions:**
- `_resolve_employee(params, db)` — fuzzy match employee name → ID
- `_resolve_product(params, db)` — fuzzy match product/menu item name → ID
- `_resolve_inventory_item(params, db)` — fuzzy match ingredient name → ID

**Action handlers** (one per tool, with switch on `action_type`):
- `_handle_attendance(params, db, user_id)` — direct DB insert/update (bypasses self-service limitation)
- `_handle_schedule(params, db, user_id)` — uses existing schedule creation/deletion logic
- `_handle_orders(params, db, user_id)` — updates order status, handles void with inventory reversal
- `_handle_86(params, db, user_id)` — toggles `pos_86d` flag on products
- `_handle_inventory(params, db, user_id)` — updates quantity, toggles active, updates invoice payment status
- `_handle_payroll(params, db, user_id)` — calls into existing payroll processing logic
- `_handle_menu(params, db, user_id)` — updates prices, toggles items, updates hours

**Update `_build_system_instructions()`:** Add section explaining action capabilities and the MANDATORY confirmation rule.

### 2. `static/js/voice-ai.js` — Handle action tool dispatch

**Update `handleFunctionCall()`:** Add case for all `manage_*` tools — POST to `/api/voice/action` with action name + params (same pattern as existing `run_sql_query` handler).

**Update `renderData()`:** Add action result pattern — show success/error message as a styled confirmation card (green for success, red for error).

### 3. `static/css/voice-ai.css` — Action confirmation card styles

Add `.voice-data-action` card: success (green border/icon) and error (red border/icon) variants. Slide-in animation matching existing data cards.

### 4. `templates/dashboard.html` + `templates/dashboard_home.html` — Bump cache version

Bump `voice-ai.js?v=10` → `?v=11`.

---

## Safety & Guardrails

1. **Verbal confirmation** — System prompt requires AI to describe action + ask "Shall I go ahead?" before every write tool call
2. **Admin-only** — Action endpoint requires super_admin or org_admin role
3. **Audit logging** — Every action logged with timestamp, user, action type, params, result
4. **Name resolution errors** — If name is ambiguous (multiple matches), return error asking for clarification
5. **Validation** — Each handler validates business rules (can't clock in if already in, can't void completed order, etc.)
6. **No cascading deletes** — All "deletes" are soft-deletes (status changes)
7. **Payroll warning** — Extra stern confirmation language for payroll processing (it's immutable once done)

---

## Verification

1. Restart server with `OPENAI_API_KEY` set
2. Hard refresh dashboard (`Cmd+Shift+R`)
3. Test each action domain:
   - "Clock in [employee name]" → should ask confirmation → execute → show green card
   - "Create a shift for [employee] tomorrow 9am to 5pm" → confirm → execute
   - "Approve [employee]'s time off request" → confirm → execute
   - "86 the [menu item]" → confirm → execute → item marked unavailable
   - "Update the flour quantity to 50 pounds" → confirm → execute
   - "Mark order #[N] as ready" → confirm → execute
   - "Process payroll for this week" → extra confirmation → execute
4. Test error cases:
   - "Clock in [already clocked in employee]" → should return friendly error
   - "86 the [nonexistent item]" → should say item not found
   - "Approve time off for [ambiguous name]" → should ask which one
5. Verify audit log entries in database after each action

---

## Key Findings from Codebase Exploration

- **Attendance clock-in/out/breaks are SELF-SERVICE ONLY** — use logged-in user's employee record, no admin override. Action handler must bypass this by writing directly to DB.
- **Invoice payment-status update endpoint does NOT exist** — needs to be built as part of `manage_inventory` handler.
- **POS void reverses inventory** — the void handler needs to replicate this logic (marks sales as voided + adds ingredients back).
- **Payroll processing is IMMUTABLE** — once processed, a period is locked. Extra confirmation needed.
- **Schedule deletions are soft-deletes** — sets status to 'cancelled', safe to expose via voice.
- **127 total write endpoints exist** — this plan covers the ~20 most voice-natural actions. Easy to expand later.
