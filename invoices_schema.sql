-- Firing Up Purchase Order & Invoice Reconciliation Database
-- Created: 2026-01-10
-- This database tracks purchase orders and invoices, then automatically updates inventory

-- Purchase Orders (planned purchases)
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT UNIQUE NOT NULL,
    supplier_name TEXT NOT NULL,
    order_date TEXT DEFAULT CURRENT_TIMESTAMP,
    expected_delivery_date TEXT,
    status TEXT DEFAULT 'PENDING', -- 'PENDING', 'RECEIVED', 'PARTIAL', 'CANCELLED'
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Purchase Order Line Items
CREATE TABLE IF NOT EXISTS po_line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id INTEGER NOT NULL,
    ingredient_code TEXT NOT NULL,
    ingredient_name TEXT NOT NULL,
    quantity_ordered REAL NOT NULL,
    unit_of_measure TEXT NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
);

-- Invoices (actual received shipments)
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    po_id INTEGER, -- Can be null if invoice received without PO
    supplier_name TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    received_date TEXT DEFAULT CURRENT_TIMESTAMP,
    total_amount REAL NOT NULL,
    payment_status TEXT DEFAULT 'UNPAID', -- 'UNPAID', 'PAID', 'PARTIAL'
    payment_date TEXT,
    reconciled TEXT DEFAULT 'NO', -- 'YES' or 'NO' - has this been added to inventory?
    reconciled_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
);

-- Invoice Line Items (what was actually received)
CREATE TABLE IF NOT EXISTS invoice_line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    ingredient_code TEXT NOT NULL,
    ingredient_name TEXT NOT NULL,
    brand TEXT, -- Brand name of the ingredient
    size_modifier TEXT, -- CS (Case), EA (Each), BX (Box), etc.
    size REAL, -- Numeric size of the modifier (e.g., 15, 6, 10) - unit is in unit_of_measure
    quantity_ordered REAL, -- What was ordered (can be null)
    quantity_received REAL NOT NULL, -- What was actually received
    unit_of_measure TEXT NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    lot_number TEXT,
    expiration_date TEXT,
    reconciled_to_inventory TEXT DEFAULT 'NO', -- 'YES' or 'NO'
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);

-- Reconciliation log (tracks when invoice items were added to inventory)
CREATE TABLE IF NOT EXISTS reconciliation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    invoice_line_item_id INTEGER NOT NULL,
    ingredient_code TEXT NOT NULL,
    quantity_added REAL NOT NULL,
    reconciled_date TEXT DEFAULT CURRENT_TIMESTAMP,
    reconciled_by TEXT,
    notes TEXT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (invoice_line_item_id) REFERENCES invoice_line_items(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(po_number);
CREATE INDEX IF NOT EXISTS idx_invoice_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoice_reconciled ON invoices(reconciled);
CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders(supplier_name);
CREATE INDEX IF NOT EXISTS idx_invoice_supplier ON invoices(supplier_name);

-- View: Outstanding purchase orders
CREATE VIEW IF NOT EXISTS outstanding_pos AS
SELECT
    po_number,
    supplier_name,
    order_date,
    expected_delivery_date,
    status,
    (SELECT SUM(total_price) FROM po_line_items WHERE po_id = purchase_orders.id) as total_amount
FROM purchase_orders
WHERE status IN ('PENDING', 'PARTIAL')
ORDER BY expected_delivery_date;

-- View: Unreconciled invoices
CREATE VIEW IF NOT EXISTS unreconciled_invoices AS
SELECT
    invoice_number,
    supplier_name,
    invoice_date,
    received_date,
    total_amount,
    payment_status
FROM invoices
WHERE reconciled = 'NO'
ORDER BY received_date;

-- View: Invoice summary with line items
CREATE VIEW IF NOT EXISTS invoice_summary AS
SELECT
    i.invoice_number,
    i.supplier_name,
    i.invoice_date,
    i.received_date,
    ili.ingredient_code,
    ili.ingredient_name,
    ili.brand,
    ili.size_modifier,
    ili.size,
    ili.quantity_ordered,
    ili.quantity_received,
    ili.unit_of_measure,
    ili.unit_price,
    ili.total_price,
    ili.lot_number,
    ili.expiration_date,
    ili.reconciled_to_inventory
FROM invoices i
JOIN invoice_line_items ili ON i.id = ili.invoice_id
ORDER BY i.received_date DESC, i.invoice_number;

-- View: Payment tracking
CREATE VIEW IF NOT EXISTS payment_tracking AS
SELECT
    invoice_number,
    supplier_name,
    invoice_date,
    total_amount,
    payment_status,
    payment_date,
    CASE
        WHEN payment_status = 'UNPAID' THEN
            CAST((julianday('now') - julianday(invoice_date)) AS INTEGER)
        ELSE NULL
    END as days_outstanding
FROM invoices
WHERE payment_status != 'PAID'
ORDER BY invoice_date;

-- View: Order vs Received Discrepancies
CREATE VIEW IF NOT EXISTS order_discrepancies AS
SELECT
    i.invoice_number,
    i.supplier_name,
    i.invoice_date,
    ili.ingredient_code,
    ili.ingredient_name,
    ili.quantity_ordered,
    ili.quantity_received,
    (ili.quantity_received - ili.quantity_ordered) as discrepancy,
    ili.unit_of_measure,
    CASE
        WHEN ili.quantity_received < ili.quantity_ordered THEN 'SHORT'
        WHEN ili.quantity_received > ili.quantity_ordered THEN 'OVER'
        ELSE 'MATCHED'
    END as status
FROM invoices i
JOIN invoice_line_items ili ON i.id = ili.invoice_id
WHERE ili.quantity_ordered IS NOT NULL
ORDER BY i.invoice_date DESC, i.invoice_number;
