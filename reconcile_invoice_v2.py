#!/usr/bin/env python3
"""
Invoice Reconciliation Script v2
Automatically updates inventory database when invoices are received
Supports multi-brand/multi-supplier ingredient clustering
"""

import sqlite3
import sys
from datetime import datetime

def reconcile_invoice(invoice_number, reconciled_by="System"):
    """
    Reconcile an invoice by updating the main inventory database
    with received items and marking the invoice as reconciled.
    Matches ingredients by ingredient_code + brand + supplier.

    Args:
        invoice_number: The invoice number to reconcile
        reconciled_by: Name of person reconciling (default: "System")
    """

    # Connect to both databases
    invoices_conn = sqlite3.connect('invoices.db')
    inventory_conn = sqlite3.connect('inventory.db')

    invoices_cur = invoices_conn.cursor()
    inventory_cur = inventory_conn.cursor()

    try:
        # Get invoice ID and check if already reconciled
        invoices_cur.execute("""
            SELECT id, reconciled, invoice_number, supplier_name, received_date
            FROM invoices
            WHERE invoice_number = ?
        """, (invoice_number,))

        invoice = invoices_cur.fetchone()

        if not invoice:
            print(f"ERROR: Invoice {invoice_number} not found!")
            return False

        invoice_id, reconciled, inv_num, supplier, received_date = invoice

        if reconciled == 'YES':
            print(f"WARNING: Invoice {invoice_number} is already reconciled!")
            return False

        # Get all line items from this invoice (NOW INCLUDING BRAND)
        invoices_cur.execute("""
            SELECT id, ingredient_code, ingredient_name, brand, quantity_received,
                   unit_of_measure, unit_price, lot_number, expiration_date
            FROM invoice_line_items
            WHERE invoice_id = ? AND reconciled_to_inventory = 'NO'
        """, (invoice_id,))

        line_items = invoices_cur.fetchall()

        if not line_items:
            print(f"WARNING: No unreconciled line items found for invoice {invoice_number}")
            return False

        print(f"\nReconciling Invoice: {invoice_number}")
        print(f"Supplier: {supplier}")
        print(f"Received Date: {received_date}")
        print(f"Line Items: {len(line_items)}")
        print("-" * 60)

        reconciled_count = 0

        for line_item in line_items:
            line_id, ing_code, ing_name, brand, qty, uom, unit_price, lot_num, exp_date = line_item

            # UPDATED: Check if ingredient exists with matching code + brand + supplier
            inventory_cur.execute("""
                SELECT id, ingredient_name, quantity_on_hand, unit_of_measure, brand, supplier_name
                FROM ingredients
                WHERE ingredient_code = ? AND brand = ? AND supplier_name = ?
            """, (ing_code, brand, supplier))

            ingredient = inventory_cur.fetchone()

            if not ingredient:
                # Try to find by ingredient_name + brand + supplier if code doesn't match
                print(f"  INFO: Exact match not found for {ing_code}, trying name/brand/supplier match...")
                inventory_cur.execute("""
                    SELECT id, ingredient_name, quantity_on_hand, unit_of_measure, brand, supplier_name
                    FROM ingredients
                    WHERE ingredient_name = ? AND brand = ? AND supplier_name = ?
                """, (ing_name, brand, supplier))

                ingredient = inventory_cur.fetchone()

                if not ingredient:
                    print(f"  WARNING: Ingredient {ing_code} ({ing_name}, Brand: {brand}, Supplier: {supplier})")
                    print(f"           not found in inventory!")
                    print(f"           Consider adding this brand/supplier combination to inventory first.")
                    continue

            ing_id, inv_name, current_qty, inv_uom, inv_brand, inv_supplier = ingredient

            # Verify unit of measure matches
            if uom != inv_uom:
                print(f"  WARNING: Unit mismatch for {ing_code}!")
                print(f"           Invoice: {uom}, Inventory: {inv_uom}")
                print(f"           Skipping this line item.")
                continue

            # Update inventory quantity
            new_quantity = current_qty + qty
            inventory_cur.execute("""
                UPDATE ingredients
                SET quantity_on_hand = ?,
                    unit_cost = ?,
                    date_received = ?,
                    lot_number = ?,
                    expiration_date = ?
                WHERE id = ?
            """, (new_quantity, unit_price, received_date, lot_num, exp_date, ing_id))

            # Record transaction in inventory database
            inventory_cur.execute("""
                INSERT INTO ingredient_transactions
                (ingredient_id, transaction_type, quantity_change, unit_cost, notes)
                VALUES (?, 'PURCHASE', ?, ?, ?)
            """, (ing_id, qty, unit_price, f"Invoice {invoice_number} - {supplier} - {brand}"))

            # Mark line item as reconciled in invoice database
            invoices_cur.execute("""
                UPDATE invoice_line_items
                SET reconciled_to_inventory = 'YES'
                WHERE id = ?
            """, (line_id,))

            # Add to reconciliation log
            invoices_cur.execute("""
                INSERT INTO reconciliation_log
                (invoice_id, invoice_line_item_id, ingredient_code, quantity_added, reconciled_by)
                VALUES (?, ?, ?, ?, ?)
            """, (invoice_id, line_id, ing_code, qty, reconciled_by))

            print(f"  ✓ {ing_code}: {ing_name} ({brand})")
            print(f"    Quantity: {current_qty} → {new_quantity} {uom}")
            print(f"    Unit Price: ${unit_price}")
            print(f"    Supplier: {inv_supplier}")

            reconciled_count += 1

        # Mark invoice as reconciled if all items processed
        invoices_cur.execute("""
            SELECT COUNT(*) FROM invoice_line_items
            WHERE invoice_id = ? AND reconciled_to_inventory = 'NO'
        """, (invoice_id,))

        remaining = invoices_cur.fetchone()[0]

        if remaining == 0:
            invoices_cur.execute("""
                UPDATE invoices
                SET reconciled = 'YES',
                    reconciled_date = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), invoice_id))
            print(f"\n✓ Invoice {invoice_number} fully reconciled!")
        else:
            print(f"\n⚠ Invoice {invoice_number} partially reconciled ({remaining} items remaining)")

        # Commit both databases
        invoices_conn.commit()
        inventory_conn.commit()

        print(f"\n{reconciled_count} items added to inventory successfully!")
        return True

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        invoices_conn.rollback()
        inventory_conn.rollback()
        return False

    finally:
        invoices_conn.close()
        inventory_conn.close()


def list_unreconciled_invoices():
    """List all unreconciled invoices"""
    conn = sqlite3.connect('invoices.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM unreconciled_invoices")
    invoices = cur.fetchall()

    if not invoices:
        print("No unreconciled invoices found.")
        conn.close()
        return

    print("\nUnreconciled Invoices:")
    print("-" * 80)
    for inv in invoices:
        inv_num, supplier, inv_date, recv_date, total, payment = inv
        print(f"Invoice: {inv_num}")
        print(f"  Supplier: {supplier}")
        print(f"  Invoice Date: {inv_date}")
        print(f"  Received: {recv_date}")
        print(f"  Amount: ${total}")
        print(f"  Payment Status: {payment}")
        print()

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 reconcile_invoice_v2.py <invoice_number> [reconciled_by]")
        print("  python3 reconcile_invoice_v2.py list")
        print("\nExamples:")
        print("  python3 reconcile_invoice_v2.py INV-2024-001")
        print("  python3 reconcile_invoice_v2.py INV-2024-001 'John Smith'")
        print("  python3 reconcile_invoice_v2.py list")
        sys.exit(1)

    if sys.argv[1] == "list":
        list_unreconciled_invoices()
    else:
        invoice_number = sys.argv[1]
        reconciled_by = sys.argv[2] if len(sys.argv) > 2 else "System"
        reconcile_invoice(invoice_number, reconciled_by)
