# Invoice & Purchase Order Reconciliation System

Separate database system for tracking purchase orders and invoices, with automatic reconciliation to the main inventory database.

## Database Files

- `invoices.db` - Invoice and purchase order tracking database
- `inventory.db` - Main inventory database (automatically updated)
- `invoices_schema.sql` - Invoice database schema
- `sample_invoices.sql` - Sample invoice data
- `reconcile_invoice.py` - Python script to reconcile invoices to inventory

## Workflow

1. **Create Purchase Order (optional)** - Plan what you're ordering
2. **Receive Invoice** - Enter invoice data when shipment arrives
3. **Reconcile Invoice** - Run script to automatically update inventory
4. **Track Payments** - Monitor payment status

## Database Structure

### Purchase Orders Table
- Track planned purchases before they arrive
- Link to invoices when received
- Status: PENDING, RECEIVED, PARTIAL, CANCELLED

### Invoices Table
- Actual received shipments with invoice details
- Invoice number, supplier, dates, amounts
- Payment tracking
- Reconciliation status

### Invoice Line Items
- Individual items on each invoice
- Quantity received, unit price, lot numbers, expiration dates
- Tracks reconciliation to inventory

### Reconciliation Log
- Audit trail of when items were added to inventory
- Who reconciled and when

## How to Use

### 1. Add a New Invoice

When you receive a shipment, add it to the invoices database:

```sql
sqlite3 invoices.db

-- Add the invoice header
INSERT INTO invoices (invoice_number, supplier_name, invoice_date, received_date, total_amount, payment_status)
VALUES ('INV-2024-004', 'Sysco Foods', '2024-01-15', '2024-01-15', 450.00, 'UNPAID');

-- Add invoice line items
INSERT INTO invoice_line_items (invoice_id, ingredient_code, ingredient_name, quantity_received, unit_of_measure, unit_price, total_price, lot_number, expiration_date)
VALUES
(4, 'ING-BEF-001', 'Ground Beef 80/20', 100, 'lbs', 4.50, 450.00, 'LOT-BEEF-20240115', '2024-01-22');
```

### 2. View Unreconciled Invoices

```bash
python3 reconcile_invoice.py list
```

This shows all invoices that haven't been added to inventory yet.

### 3. Reconcile an Invoice

This automatically updates the inventory database:

```bash
python3 reconcile_invoice.py INV-2024-004
# or with user name
python3 reconcile_invoice.py INV-2024-004 'John Smith'
```

What happens:
- ✓ Reads invoice line items
- ✓ Checks ingredient codes exist in inventory
- ✓ Verifies units of measure match
- ✓ Updates inventory quantities
- ✓ Records lot numbers and expiration dates
- ✓ Creates transaction records
- ✓ Marks invoice as reconciled
- ✓ Logs who reconciled and when

### 4. View Reconciliation Results

Check updated inventory:
```bash
sqlite3 inventory.db "SELECT ingredient_code, ingredient_name, quantity_on_hand, date_received, lot_number FROM ingredients WHERE ingredient_code = 'ING-BEF-001';"
```

View reconciliation log:
```bash
sqlite3 invoices.db "SELECT * FROM reconciliation_log ORDER BY reconciled_date DESC LIMIT 10;"
```

## Common Queries

### View all invoices with line items
```sql
sqlite3 invoices.db "SELECT * FROM invoice_summary ORDER BY received_date DESC;"
```

### Check payment status
```sql
sqlite3 invoices.db "SELECT * FROM payment_tracking;"
```

### View outstanding purchase orders
```sql
sqlite3 invoices.db "SELECT * FROM outstanding_pos;"
```

### Find invoices by supplier
```sql
sqlite3 invoices.db "SELECT invoice_number, invoice_date, total_amount, payment_status, reconciled
FROM invoices WHERE supplier_name = 'Sysco Foods' ORDER BY invoice_date DESC;"
```

### View reconciliation history for an ingredient
```sql
sqlite3 invoices.db "SELECT r.reconciled_date, r.ingredient_code, i.ingredient_name, r.quantity_added, r.reconciled_by, inv.invoice_number
FROM reconciliation_log r
JOIN invoice_line_items i ON r.invoice_line_item_id = i.id
JOIN invoices inv ON r.invoice_id = inv.id
WHERE r.ingredient_code = 'ING-TOM-001'
ORDER BY r.reconciled_date DESC;"
```

### Mark invoice as paid
```sql
sqlite3 invoices.db "UPDATE invoices SET payment_status = 'PAID', payment_date = date('now') WHERE invoice_number = 'INV-2024-001';"
```

### Total unpaid invoices
```sql
sqlite3 invoices.db "SELECT SUM(total_amount) as total_unpaid FROM invoices WHERE payment_status = 'UNPAID';"
```

## Creating Purchase Orders

While optional, POs help plan orders:

```sql
-- Create PO
INSERT INTO purchase_orders (po_number, supplier_name, order_date, expected_delivery_date)
VALUES ('PO-2024-005', 'Fresh Produce Wholesalers', date('now'), date('now', '+2 days'));

-- Add line items
INSERT INTO po_line_items (po_id, ingredient_code, ingredient_name, quantity_ordered, unit_of_measure, unit_price, total_price)
VALUES
(5, 'ING-TOM-001', 'Roma Tomatoes', 50, 'lbs', 2.50, 125.00),
(5, 'ING-ONI-001', 'Yellow Onions', 30, 'lbs', 1.25, 37.50);

-- When invoice arrives, link it to PO
INSERT INTO invoices (invoice_number, po_id, supplier_name, invoice_date, received_date, total_amount)
VALUES ('INV-2024-005', 5, 'Fresh Produce Wholesalers', date('now'), date('now'), 162.50);
```

## Reconciliation Script Details

The `reconcile_invoice.py` script:

**Safety Features:**
- Verifies ingredient codes exist before updating
- Checks unit of measure matches
- Prevents double-reconciliation
- Rolls back on errors
- Creates audit trail

**What it updates:**
1. Inventory database:
   - quantity_on_hand (adds received quantity)
   - unit_cost (updates to invoice price)
   - date_received (invoice received date)
   - lot_number (from invoice)
   - expiration_date (from invoice)
   - Creates transaction record

2. Invoice database:
   - Marks line items as reconciled
   - Marks invoice as reconciled when all items done
   - Creates reconciliation log entry

## Important Notes

- Always enter invoices BEFORE reconciling
- Ingredient codes must match exactly between databases
- Units of measure must match (can't reconcile "lbs" invoice to "kg" inventory)
- Once reconciled, invoices cannot be un-reconciled (maintain data integrity)
- The reconciliation script can be run multiple times safely (won't double-add)
- Keep both databases in the same folder for the script to work

## Backup

Always backup both databases:
```bash
cp inventory.db inventory_backup_$(date +%Y%m%d).db
cp invoices.db invoices_backup_$(date +%Y%m%d).db
```

## Troubleshooting

**Script says ingredient not found:**
- Check ingredient code spelling matches exactly
- Verify ingredient exists in inventory database

**Unit mismatch warning:**
- Invoice and inventory must use same units
- Update one or the other to match

**Invoice already reconciled:**
- Normal if you run script twice
- Check reconciliation_log to see when it was done
