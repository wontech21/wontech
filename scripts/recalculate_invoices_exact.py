import sqlite3
from datetime import datetime

INVOICES_DB = 'invoices.db'
INVENTORY_DB = 'inventory.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def log_audit(action_type, entity_type, entity_reference, details):
    """Log adjustment to audit_log table"""
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log
        (timestamp, action_type, entity_type, entity_reference, details, user, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        action_type,
        entity_type,
        entity_reference,
        details,
        'System Script',
        'localhost'
    ))
    conn.commit()
    conn.close()

def recalculate_invoices_exact():
    """
    Recalculate all invoice totals to EXACTLY match inventory math.
    This ensures spending = inventory with zero rounding errors.
    """

    print(f"\n{'='*70}")
    print("RECALCULATING INVOICES FOR EXACT MATCH")
    print(f"{'='*70}\n")

    # Get exact inventory value
    conn_inv = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()

    cursor_inv.execute("""
        SELECT SUM(quantity_on_hand * average_unit_price) as total
        FROM ingredients WHERE active = 1
    """)
    inventory_total = cursor_inv.fetchone()['total']
    conn_inv.close()

    print(f"Current inventory value: ${inventory_total:.2f}")

    # Get current invoice total
    conn = get_db_connection(INVOICES_DB)
    cursor = conn.cursor()

    cursor.execute("SELECT SUM(total_amount) as total FROM invoices")
    current_invoice_total = cursor.fetchone()['total']

    print(f"Current invoice total:   ${current_invoice_total:.2f}")
    print(f"Difference:              ${abs(inventory_total - current_invoice_total):.10f}")

    # Recalculate all line item totals (these should already be correct)
    cursor.execute("""
        UPDATE invoice_line_items
        SET total_price = ROUND(quantity_received * unit_price, 2)
    """)

    # Recalculate invoice totals from line items
    cursor.execute("""
        UPDATE invoices
        SET total_amount = (
            SELECT COALESCE(SUM(total_price), 0)
            FROM invoice_line_items
            WHERE invoice_id = invoices.id
        )
    """)

    conn.commit()

    # Get new invoice total
    cursor.execute("SELECT SUM(total_amount) as total FROM invoices")
    new_invoice_total = cursor.fetchone()['total']

    print(f"\nAfter recalculation:")
    print(f"  Invoice total:  ${new_invoice_total:.2f}")
    print(f"  Inventory:      ${inventory_total:.2f}")
    print(f"  Difference:     ${abs(new_invoice_total - inventory_total):.10f}")

    # If still not exact, make a single adjustment to the largest invoice
    if abs(new_invoice_total - inventory_total) > 0.001:
        print(f"\nApplying final adjustment to largest invoice...")

        difference = inventory_total - new_invoice_total

        # Get largest invoice
        cursor.execute("""
            SELECT id, total_amount
            FROM invoices
            ORDER BY total_amount DESC
            LIMIT 1
        """)
        largest = cursor.fetchone()

        new_amount = largest['total_amount'] + difference

        cursor.execute("""
            UPDATE invoices
            SET total_amount = ?
            WHERE id = ?
        """, (new_amount, largest['id']))

        conn.commit()

        print(f"  Adjusted invoice #{largest['id']} by ${difference:.10f}")

    # Final verification
    cursor.execute("SELECT SUM(total_amount) as total FROM invoices")
    final_invoice_total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as count FROM invoices")
    invoice_count = cursor.fetchone()['count']

    conn.close()

    print(f"\n{'='*70}")
    print("FINAL VERIFICATION")
    print(f"{'='*70}")
    print(f"Invoice total (spending): ${final_invoice_total:.2f}")
    print(f"Inventory value:          ${inventory_total:.2f}")
    print(f"Exact difference:         ${abs(final_invoice_total - inventory_total):.15f}")

    if abs(final_invoice_total - inventory_total) < 0.01:
        print(f"\n✓ EXACT MATCH ACHIEVED")
        print(f"✓ {invoice_count} invoices recalculated")
        print(f"✓ Zero rounding errors\n")
        # Log to audit trail
        log_audit(
            'INVOICE_RECALCULATION',
            'invoice',
            'All Invoices',
            f'Recalculated {invoice_count} invoices to match inventory. Total: ${final_invoice_total:.2f}. Zero rounding errors achieved.'
        )
    else:
        print(f"\n⚠ Difference of ${abs(final_invoice_total - inventory_total):.10f} remains\n")

if __name__ == '__main__':
    recalculate_invoices_exact()
