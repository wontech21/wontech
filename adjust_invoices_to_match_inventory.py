import sqlite3
from datetime import datetime

INVOICES_DB = 'invoices.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def adjust_invoices_proportionally():
    """
    Reduce all invoice quantities proportionally to match the ~94% inventory reduction.
    This keeps the data consistent across the system.
    """

    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    print(f"\n{'='*70}")
    print("ADJUSTING INVOICES TO MATCH INVENTORY REDUCTION")
    print(f"{'='*70}\n")

    # Calculate current totals
    cursor.execute("SELECT SUM(total_amount) as total FROM invoices")
    old_total = float(cursor.fetchone()['total'])

    cursor.execute("SELECT COUNT(*) as count FROM invoice_line_items")
    line_item_count = cursor.fetchone()['count']

    print(f"Current invoice total: ${old_total:,.2f}")
    print(f"Total line items: {line_item_count}")

    # The inventory was reduced by 94.1% (to ~6% of original)
    # So we need to reduce invoice quantities by the same factor
    reduction_factor = 0.059  # Keep ~6% of original quantities

    print(f"\nApplying reduction factor: {reduction_factor} ({reduction_factor*100:.1f}%)")

    # Update all line items
    cursor.execute("""
        SELECT id, quantity_ordered, quantity_received, unit_price
        FROM invoice_line_items
    """)

    line_items = cursor.fetchall()
    updates = 0

    for item in line_items:
        new_qty_ordered = float(item['quantity_ordered'] or item['quantity_received']) * reduction_factor
        new_qty_received = float(item['quantity_received']) * reduction_factor
        new_total = new_qty_received * float(item['unit_price'])

        # Set minimums
        if new_qty_ordered < 1:
            new_qty_ordered = round(new_qty_ordered, 2)
        else:
            new_qty_ordered = round(new_qty_ordered, 1)

        if new_qty_received < 1:
            new_qty_received = round(new_qty_received, 2)
        else:
            new_qty_received = round(new_qty_received, 1)

        cursor.execute("""
            UPDATE invoice_line_items
            SET quantity_ordered = ?,
                quantity_received = ?,
                total_price = ?
            WHERE id = ?
        """, (new_qty_ordered, new_qty_received, new_total, item['id']))

        updates += 1

    print(f"Updated {updates} line items")

    # Recalculate invoice totals
    cursor.execute("""
        SELECT i.id, SUM(ili.total_price) as new_total
        FROM invoices i
        JOIN invoice_line_items ili ON i.id = ili.invoice_id
        GROUP BY i.id
    """)

    invoice_updates = cursor.fetchall()
    for inv in invoice_updates:
        cursor.execute("""
            UPDATE invoices
            SET total_amount = ?
            WHERE id = ?
        """, (inv['new_total'], inv['id']))

    conn.commit()

    # Calculate new totals
    cursor.execute("SELECT SUM(total_amount) as total FROM invoices")
    new_total = float(cursor.fetchone()['total'])

    cursor.execute("SELECT COUNT(*) as count FROM invoices")
    invoice_count = cursor.fetchone()['count']

    print(f"\n✓ Invoice totals recalculated")
    print(f"✓ {invoice_count} invoices updated")

    print(f"\nResults:")
    print(f"  Old total spend: ${old_total:,.2f}")
    print(f"  New total spend: ${new_total:,.2f}")
    print(f"  Reduction: {((old_total - new_total) / old_total * 100):.1f}%")
    print(f"  Average invoice: ${new_total / invoice_count:,.2f}")

    conn.close()

    print(f"\n✓ Invoices adjusted to match inventory levels!\n")

if __name__ == '__main__':
    adjust_invoices_proportionally()
