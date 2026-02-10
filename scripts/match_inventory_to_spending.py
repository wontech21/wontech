import sqlite3
from datetime import datetime

INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

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

def match_inventory_to_spending():
    """
    Make inventory value exactly match total spending.
    This represents the scenario: All invoices received, nothing used yet.
    """

    print(f"\n{'='*70}")
    print("MATCHING INVENTORY TO SPENDING (Test Data Reset)")
    print(f"{'='*70}\n")

    # Get total spending
    conn_inv = get_db_connection(INVOICES_DB)
    cursor_inv = conn_inv.cursor()
    cursor_inv.execute("SELECT SUM(total_amount) as total FROM invoices")
    total_spending = float(cursor_inv.fetchone()['total'])
    conn_inv.close()

    # Get current inventory value
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(quantity_on_hand * average_unit_price) as total
        FROM ingredients WHERE active = 1
    """)
    current_inventory_value = float(cursor.fetchone()['total'])

    print(f"Current state:")
    print(f"  Total spending:    ${total_spending:,.2f}")
    print(f"  Inventory value:   ${current_inventory_value:,.2f}")

    # Calculate adjustment factor
    adjustment_factor = total_spending / current_inventory_value

    print(f"\nAdjustment:")
    print(f"  Factor: {adjustment_factor:.6f} ({adjustment_factor*100:.2f}%)")

    # Update all ingredient quantities to match
    cursor.execute("""
        SELECT id, quantity_on_hand, unit_of_measure
        FROM ingredients WHERE active = 1
    """)

    ingredients = cursor.fetchall()
    updates = 0

    for ing in ingredients:
        new_qty = float(ing['quantity_on_hand']) * adjustment_factor

        # Set minimum based on UOM
        uom = ing['unit_of_measure']
        if uom in ['lb', 'kg']:
            min_qty = 1.0
        elif uom in ['gal', 'liter']:
            min_qty = 0.5
        elif uom in ['oz', 'ml']:
            min_qty = 4.0
        elif uom == 'each':
            min_qty = 1.0
        elif uom == 'case':
            min_qty = 0.25
        else:
            min_qty = 0.5

        new_qty = max(new_qty, min_qty)

        # Round appropriately
        if new_qty < 10:
            new_qty = round(new_qty, 2)
        else:
            new_qty = round(new_qty, 1)

        cursor.execute("""
            UPDATE ingredients
            SET quantity_on_hand = ?
            WHERE id = ?
        """, (new_qty, ing['id']))

        updates += 1

    conn.commit()

    # Verify new totals
    cursor.execute("""
        SELECT SUM(quantity_on_hand * average_unit_price) as total
        FROM ingredients WHERE active = 1
    """)
    new_inventory_value = float(cursor.fetchone()['total'])

    conn.close()

    print(f"\n✓ Updated {updates} ingredients")
    print(f"\nFinal state:")
    print(f"  Total spending:    ${total_spending:,.2f}")
    print(f"  Inventory value:   ${new_inventory_value:,.2f}")
    print(f"  Difference:        ${abs(total_spending - new_inventory_value):,.2f}")
    print(f"  Match:             {abs(total_spending - new_inventory_value) < 5.00}")

    print(f"\n✓ Inventory now matches spending!")
    print(f"  Scenario: All invoices received, nothing used/sold yet")
    print(f"  As you add sales/production data, inventory will naturally decrease\n")

    # Log to audit trail
    log_audit(
        'INVENTORY_SPENDING_MATCH',
        'inventory',
        'All Active Items',
        f'Matched inventory to spending. Updated {updates} ingredients. Total spending: ${total_spending:,.2f}, Inventory value: ${new_inventory_value:,.2f}'
    )

if __name__ == '__main__':
    match_inventory_to_spending()
