#!/usr/bin/env python3
"""
Reconcile existing invoice and inventory data to match new pricing scheme:
- units_per_case from invoice size field
- unit_cost = last_unit_price / units_per_case
- last_unit_price from invoice unit_price
"""
import sqlite3

def get_db_connection(db_name):
    """Create database connection"""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

def reconcile_pricing():
    print("\n" + "="*70)
    print("🔄 RECONCILING INVOICE PRICING DATA")
    print("="*70 + "\n")

    conn_invoices = get_db_connection('invoices.db')
    cursor_invoices = conn_invoices.cursor()

    conn_inventory = get_db_connection('inventory.db')
    cursor_inventory = conn_inventory.cursor()

    # Get all invoice line items with their invoice details
    cursor_invoices.execute("""
        SELECT
            ili.id,
            ili.invoice_id,
            ili.ingredient_code,
            ili.ingredient_name,
            ili.size,
            ili.quantity_received,
            ili.unit_price,
            i.received_date,
            i.supplier_name
        FROM invoice_line_items ili
        JOIN invoices i ON ili.invoice_id = i.id
        ORDER BY i.received_date, ili.ingredient_code
    """)

    invoice_items = cursor_invoices.fetchall()

    print(f"Found {len(invoice_items)} invoice line items to process\n")

    updated_count = 0
    created_count = 0
    skipped_count = 0

    for item in invoice_items:
        ingredient_code = item['ingredient_code']
        size = item['size'] or 1.0  # units per case from invoice
        unit_price = item['unit_price']  # price per case
        qty_received = item['quantity_received']
        received_date = item['received_date']
        supplier = item['supplier_name']

        # Calculate inventory quantity (total units)
        inventory_qty = qty_received * size

        print(f"Processing: {ingredient_code} - {item['ingredient_name']}")
        print(f"  Invoice: {qty_received} cases × {size} units/case = {inventory_qty} units")
        print(f"  Price: ${unit_price}/case → ${unit_price/size:.4f}/unit")

        # Find matching inventory records
        cursor_inventory.execute("""
            SELECT id, quantity_on_hand, units_per_case, last_unit_price
            FROM ingredients
            WHERE ingredient_code = ?
        """, (ingredient_code,))

        inventory_records = cursor_inventory.fetchall()

        if inventory_records:
            for record in inventory_records:
                # Update units_per_case and recalculate unit_cost
                cursor_inventory.execute("""
                    UPDATE ingredients
                    SET units_per_case = ?,
                        last_unit_price = ?,
                        average_unit_price = ?
                    WHERE id = ?
                """, (size, unit_price, unit_price, record['id']))
                updated_count += 1
                print(f"  ✓ Updated inventory record (ID: {record['id']})")
        else:
            # No inventory record exists - this shouldn't happen if invoices created inventory
            print(f"  ⚠ No inventory record found for {ingredient_code}")
            skipped_count += 1

        print()

    conn_inventory.commit()
    conn_inventory.close()
    conn_invoices.close()

    print("="*70)
    print(f"✓ Reconciliation complete!")
    print(f"  - Updated: {updated_count} inventory records")
    print(f"  - Skipped: {skipped_count} items (no inventory found)")
    print("="*70 + "\n")

if __name__ == '__main__':
    reconcile_pricing()
