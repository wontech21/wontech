# WONTECH POS System — Enterprise Build Plan

> **Location**: `/Users/dell/WONTECH/docs/POS_BUILD_PLAN.md`
> **Created**: 2026-02-08
> **Status**: Complete — all 8 phases implemented (B1-B8)
> **Context**: Firing Up pizzeria is the first deployment. POS must integrate fully with existing WONTECH modules (inventory, HR/scheduling, payroll, sales analytics, audit).

---

## Current State

The POS has a polished frontend (`templates/pos.html`, 3,705 lines) and Stripe payment endpoints (`routes/pos_routes.py`, 271 lines). What works today:

| Feature | Status | Location |
|---------|--------|----------|
| Product grid with categories | Working | `pos.html` — loads from `/api/products/list` |
| Shopping cart with qty adjusters | Working | `pos.html` — in-memory `orderItems[]` |
| Order types (dine-in/pickup/delivery) | Working | `pos.html` — form validation, address collection |
| Google Maps delivery distance/time | Working | `pos.html` — Maps API integration |
| Tax/delivery fee configuration | Working | `pos.html` — localStorage only |
| Cash payment with change calculation | Working | `pos.html` |
| Card payment via Stripe Elements | Working | `pos_routes.py` — create-payment-intent, capture, refund |
| Order history display | Working | `pos.html` — localStorage only |
| CSV export of orders | Working | `pos.html` |
| Stripe Terminal (card reader) | Stub | `pos_routes.py` — connection-token endpoint exists, no reader logic |
| Receipt (print/email/SMS) | Stub | `pos.html` — `window.print()` only |
| Inventory deduction on sale | Exists but disconnected | `sales_operations.py:260-266` — recipe lookup + deduction code exists, POS never calls it |
| Sales recording to database | Exists but disconnected | `sales_operations.py` — `/api/sales/apply` endpoint exists, POS never calls it |

### Critical Gap

Orders never reach the database. Current data flow:

```
Customer order → browser memory → Stripe payment (works) → localStorage → gone
```

Nothing reaches inventory. Nothing reaches sales analytics. Nothing reaches payroll. The POS is an island.

---

## Database Schema Required

### New Tables (in org database)

```sql
-- Order header
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT NOT NULL,           -- daily sequential: ORD-20260208-001
    order_type TEXT NOT NULL,             -- 'dine_in', 'pickup', 'delivery'
    status TEXT NOT NULL DEFAULT 'new',   -- 'new','confirmed','preparing','ready','picked_up','delivered','served','closed','voided'
    employee_id INTEGER,                  -- who took the order (FK employees)
    customer_name TEXT,
    customer_phone TEXT,
    customer_email TEXT,
    customer_address TEXT,                -- delivery only
    delivery_distance REAL,              -- miles, delivery only
    delivery_fee REAL DEFAULT 0,
    subtotal REAL NOT NULL,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    tip_amount REAL DEFAULT 0,
    discount_amount REAL DEFAULT 0,
    discount_reason TEXT,
    total REAL NOT NULL,
    notes TEXT,
    estimated_ready_time DATETIME,
    actual_ready_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    voided_at DATETIME,
    voided_by INTEGER,                   -- FK employees
    void_reason TEXT
);

-- Order line items
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,            -- FK orders
    product_id INTEGER NOT NULL,          -- FK products
    product_name TEXT NOT NULL,           -- denormalized for history
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL,
    modifiers TEXT,                       -- JSON: special requests, add-ons
    line_total REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Payment records (supports split payments)
CREATE TABLE order_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,            -- FK orders
    payment_method TEXT NOT NULL,         -- 'cash', 'card', 'terminal'
    amount REAL NOT NULL,
    tip_amount REAL DEFAULT 0,
    stripe_payment_intent_id TEXT,        -- null for cash
    stripe_charge_id TEXT,
    card_last_four TEXT,
    cash_tendered REAL,                  -- cash only
    change_given REAL,                   -- cash only
    status TEXT DEFAULT 'completed',     -- 'completed', 'refunded', 'partial_refund'
    refund_amount REAL DEFAULT 0,
    refund_reason TEXT,
    refunded_at DATETIME,
    refunded_by INTEGER,                 -- FK employees
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- POS settings (org-level, replaces localStorage)
CREATE TABLE pos_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE,
    setting_value TEXT NOT NULL,          -- JSON for complex values
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER                   -- FK employees
);

-- Register sessions (open/close shifts)
CREATE TABLE register_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,         -- FK employees
    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME,
    opening_cash REAL NOT NULL,
    closing_cash REAL,
    expected_cash REAL,                  -- calculated from transactions
    cash_variance REAL,                  -- closing - expected
    total_sales REAL DEFAULT 0,
    total_cash_sales REAL DEFAULT 0,
    total_card_sales REAL DEFAULT 0,
    total_tips REAL DEFAULT 0,
    total_refunds REAL DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    notes TEXT
);
```

---

## Build Phases

### Phase 1: Order Persistence + Sales Recording
**Goal**: Orders hit the database. Sales analytics see POS transactions.

**Backend:**
- [x] Create migration: `migrations/create_pos_tables.py` — orders, order_items, order_payments, pos_settings tables
- [x] New endpoint: `POST /api/pos/orders` — accepts order from frontend, inserts into orders + order_items
- [x] New endpoint: `GET /api/pos/orders` — fetch orders with filters (date, status, type)
- [x] New endpoint: `GET /api/pos/orders/<id>` — single order with items and payments
- [x] New endpoint: `POST /api/pos/orders/<id>/pay` — record payment to order_payments, call `/api/sales/apply` to record in sales_history
- [x] Wire POS order completion into existing sales pipeline so analytics dashboards update automatically

**Frontend (`pos.html`):**
- [x] Modify `completeOrder()` to POST to `/api/pos/orders` instead of localStorage
- [x] Modify payment functions to POST to `/api/pos/orders/<id>/pay`
- [x] Order history loads from database via `/api/pos/orders` instead of localStorage
- [x] Keep localStorage as offline fallback only (sync when connection restored)

**Integration test**: Place order → check `orders` table → check `sales_history` table → verify analytics dashboard reflects the sale.

---

### Phase 2: Inventory Deduction on Sale
**Goal**: Sell a pizza, ingredients go down automatically. Out-of-stock items are flagged.

**Backend:**
- [x] On order confirmation, loop through order_items → look up recipe → deduct ingredients (code exists in `sales_operations.py:260-266`, wire it in)
- [x] New endpoint: `GET /api/pos/product-availability` — for each product, check if all recipe ingredients are in stock
- [x] If stock drops below reorder level after deduction, trigger `inventory_warnings` alert
- [x] On order void, reverse ingredient deductions

**Frontend:**
- [x] On product grid load, call `/api/pos/product-availability` — gray out / badge "86'd" on out-of-stock items
- [x] Show warning when adding an item with low-stock ingredients
- [x] Real-time update: when stock runs out mid-shift, update the grid

**Integration test**: Record ingredient quantities → place POS order → verify ingredient quantities decreased by recipe amounts → verify warning triggers if below reorder level.

---

### Phase 3: Employee Assignment + POS Auth
**Goal**: Every order is tied to a person. POS respects permissions.

**Backend:**
- [x] POS login endpoint — employee selects themselves or enters PIN (fast auth, not full login)
- [x] `employee_id` populated on every order
- [x] Permission checks: `pos_void`, `pos_refund`, `pos_discount`, `pos_open_drawer`
- [x] Tip recorded against employee for payroll integration

**Frontend:**
- [x] POS opens with employee selection screen (shift employees only — pulled from today's schedule)
- [x] Employee name displayed on POS header
- [x] Void/refund/discount buttons check permissions, prompt for manager override if needed
- [x] Quick-switch employee (for shared terminals)

**Integration**: Ties into existing `employees` table and `permission_definitions` in middleware.

---

### Phase 4: Order Lifecycle + Status Tracking
**Goal**: Orders have a lifecycle. Kitchen sees the queue. Customers can check status.

**Backend:**
- [x] New endpoint: `PATCH /api/pos/orders/<id>/status` — update order status with timestamp
- [x] New endpoint: `GET /api/pos/kitchen` — orders in 'confirmed' or 'preparing' status, sorted by time
- [x] New endpoint: `GET /api/pos/order-status/<order_number>` — public, no auth, for customer lookup
- [x] Auto-transition: order paid → status = 'confirmed'
- [x] Timestamp tracking: `created_at`, `confirmed_at`, `preparing_at`, `ready_at`, `completed_at`

**Frontend:**
- [x] Kitchen Display view — separate page or tab showing order queue with timers
- [x] Status update buttons for kitchen staff (tap to advance: preparing → ready)
- [x] Color-coded time warnings (green < 10min, yellow 10-20min, red > 20min)
- [x] Order status visible in POS order history

**New template**: `templates/kitchen.html` — KDS display optimized for a mounted screen

---

### Phase 5: Tips → Payroll Pipeline
**Goal**: Tips at POS flow through to payroll automatically.

**Backend:**
- [x] On payment with tip, write to `order_payments.tip_amount` AND update employee tip accumulator
- [x] New endpoint or modify existing: `GET /api/payroll/tips-summary?employee_id=X&period=Y` — aggregate tips for pay period
- [x] Payroll calculation (`routes/payroll_routes.py`) pulls POS tip data when processing pay period
- [x] Tip reporting: daily tip-out summary per employee

**Integration**: Connects `order_payments` → `payroll_history` through existing payroll processing pipeline.

---

### Phase 6: Register Management + Settlement
**Goal**: Cash accountability. Shift-level reconciliation.

**Backend:**
- [x] Create `register_sessions` table (schema above)
- [x] New endpoint: `POST /api/pos/register/open` — start session, record opening cash count
- [x] New endpoint: `POST /api/pos/register/close` — end session, record closing count, calculate variance
- [x] New endpoint: `GET /api/pos/register/current` — active session details + running totals
- [x] Auto-calculate expected cash: opening_cash + cash_sales - cash_refunds - cash_payouts

**Frontend:**
- [x] Register open screen at start of shift — count drawer, enter amount
- [x] Register close flow — count drawer, system shows expected vs actual, note variance
- [x] Shift summary: total sales, breakdown by payment method, tips collected, refunds issued
- [x] Print shift report

---

### Phase 7: Receipt System
**Goal**: Customer gets a receipt — print, email, or text.

**Backend:**
- [x] New endpoint: `POST /api/pos/orders/<id>/receipt/email` — sends formatted receipt via existing email infrastructure (`share_routes.py`)
- [x] New endpoint: `POST /api/pos/orders/<id>/receipt/sms` — sends receipt link via existing Twilio scaffold
- [x] Receipt template: order number, items, subtotal, tax, tip, total, payment method, timestamp, business name/address

**Frontend:**
- [x] Replace `printReceipt()` stub with formatted thermal-printer-friendly HTML
- [x] Replace `emailReceipt()` stub with actual API call
- [x] Replace `textReceipt()` stub with actual API call
- [x] Post-payment screen: "Receipt sent!" confirmation

---

### Phase 8: Customer Profiles + History
**Goal**: Repeat customers are recognized. Order history enables AI insights later.

**Backend:**
- [x] New table: `customers` — name, phone, email, address, first_order, last_order, total_orders, total_spent
- [x] Auto-create customer profile on first order (match by phone number)
- [x] Link `orders.customer_id` to `customers` table
- [x] New endpoint: `GET /api/pos/customers/<phone>` — lookup by phone, return profile + recent orders

**Frontend:**
- [x] Phone number lookup during order entry — "Welcome back, John. Same as last time?"
- [x] Quick reorder from past orders
- [x] Customer notes visible during order entry ("allergic to shellfish", "always asks for extra sauce")

**AI integration point**: Customer data feeds future retention analysis, purchase pattern predictions, personalized upsell suggestions.

---

## Full Integration Map (When Complete)

```
POS Order Placed
  ├→ orders + order_items tables              (persistence)
  ├→ order_payments table                     (payment tracking)
  ├→ sales_history table                      (analytics pipeline)
  ├→ ingredients table                        (inventory deduction via recipes)
  ├→ inventory_warnings                       (reorder alerts if stock drops)
  ├→ employees table                          (who processed it)
  ├→ order_payments.tip_amount → payroll      (tip accumulation for pay period)
  ├→ register_sessions                        (cash reconciliation)
  ├→ customers table                          (customer profile + history)
  ├→ audit_log                                (full transaction trail)
  └→ analytics dashboards                     (real-time updates)
```

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `routes/pos_routes.py` | Expand from 271 lines to full order management API |
| `templates/pos.html` | Wire `completeOrder()` to backend, add employee auth, availability badges |
| `sales_operations.py` | Ensure POS orders flow through existing sales + inventory deduction pipeline |
| `migrations/` | New migration for POS tables |
| `app.py` | Register new POS endpoints if not in blueprint, add inline table creation |
| `routes/payroll_routes.py` | Pull POS tip data into payroll calculations |
| `middleware/tenant_context_separate_db.py` | Add POS-specific permissions (`pos_void`, `pos_refund`, `pos_discount`) |
| `templates/kitchen.html` | New — Kitchen Display System |
| `static/js/kitchen.js` | New — KDS frontend logic |

---

## Dependencies & External Services

| Service | Purpose | Status |
|---------|---------|--------|
| Stripe API | Card payments | Working — keys configured |
| Stripe Terminal | Physical card reader | Stubbed — needs reader hardware |
| Google Maps API | Delivery distance/time | Working |
| SendGrid / SMTP | Email receipts | Scaffolded in `share_routes.py` |
| Twilio | SMS receipts | Scaffolded in `share_routes.py` |
