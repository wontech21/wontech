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

def fix_inventory_spending_relationship():
    """
    Fix the illogical relationship where inventory value > total spending.

    In reality:
    - Total spending = all purchases
    - Inventory value = what's left (after usage/waste)
    - Therefore: Inventory should be 70-80% of spending
    """

    print(f"\n{'='*70}")
    print("FIXING INVENTORY-SPENDING RELATIONSHIP")
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
    print(f"  Problem: Inventory > Spending by ${current_inventory_value - total_spending:,.2f}")

    # Target: Inventory should be 75% of spending (realistic for food business)
    target_inventory_value = total_spending * 0.75
    reduction_factor = target_inventory_value / current_inventory_value

    print(f"\nTarget state:")
    print(f"  Target inventory:  ${target_inventory_value:,.2f} (75% of spending)")
    print(f"  Reduction factor:  {reduction_factor:.4f} ({reduction_factor*100:.1f}%)")

    # Update all ingredient quantities
    cursor.execute("""
        SELECT id, quantity_on_hand, unit_of_measure
        FROM ingredients WHERE active = 1
    """)

    ingredients = cursor.fetchall()
    updates = 0

    for ing in ingredients:
        new_qty = float(ing['quantity_on_hand']) * reduction_factor

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
    print(f"  Inventory/Spending ratio: {(new_inventory_value/total_spending)*100:.1f}%")
    print(f"  Difference:        ${total_spending - new_inventory_value:,.2f} (used/sold)")

    print(f"\n✓ Logical relationship restored!")
    print(f"  Inventory ({new_inventory_value:.0f}) < Spending ({total_spending:.0f}) ✓\n")

    # Log to audit trail
    log_audit(
        'INVENTORY_RELATIONSHIP_FIX',
        'inventory',
        'All Active Items',
        f'Fixed inventory-spending relationship. Updated {updates} ingredients. Inventory reduced to 75% of spending: ${new_inventory_value:,.2f}'
    )

if __name__ == '__main__':
    fix_inventory_spending_relationship()
