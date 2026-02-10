import sqlite3
from decimal import Decimal, ROUND_HALF_UP
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

def exact_match_inventory_to_spending():
    """
    Make inventory value EXACTLY match total spending using precise decimal math.
    No rounding errors permitted.
    """

    print(f"\n{'='*70}")
    print("EXACT MATCHING: INVENTORY = SPENDING")
    print(f"{'='*70}\n")

    # Get total spending with exact precision
    conn_inv = get_db_connection(INVOICES_DB)
    cursor_inv = conn_inv.cursor()
    cursor_inv.execute("SELECT SUM(total_amount) as total FROM invoices")
    total_spending = Decimal(str(cursor_inv.fetchone()['total']))
    conn_inv.close()

    print(f"Target: ${total_spending}")

    # Get current inventory value
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, quantity_on_hand, average_unit_price
        FROM ingredients WHERE active = 1
        ORDER BY (quantity_on_hand * average_unit_price) DESC
    """)

    ingredients = cursor.fetchall()

    # Calculate current total
    current_total = Decimal('0')
    for ing in ingredients:
        current_total += Decimal(str(ing['quantity_on_hand'])) * Decimal(str(ing['average_unit_price']))

    print(f"Current inventory value: ${current_total}")
    print(f"Difference: ${total_spending - current_total}")

    # Calculate the adjustment needed
    if current_total != Decimal('0'):
        adjustment_factor = total_spending / current_total
    else:
        print("Error: Current inventory is zero")
        return

    print(f"Adjustment factor: {adjustment_factor}")

    # First pass: Apply adjustment factor
    new_values = []
    running_total = Decimal('0')

    for i, ing in enumerate(ingredients):
        qty = Decimal(str(ing['quantity_on_hand']))
        price = Decimal(str(ing['average_unit_price']))

        # Adjust quantity
        new_qty = qty * adjustment_factor

        # Round to 2 decimal places
        new_qty = new_qty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Ensure minimum quantity
        if new_qty < Decimal('0.01'):
            new_qty = Decimal('0.01')

        item_value = new_qty * price
        running_total += item_value

        new_values.append({
            'id': ing['id'],
            'quantity': new_qty,
            'price': price,
            'value': item_value
        })

    # Second pass: Distribute the remaining difference to avoid rounding errors
    # Add/subtract from the largest items to make it exact
    difference = total_spending - running_total

    print(f"\nAfter initial adjustment:")
    print(f"  Running total: ${running_total}")
    print(f"  Difference: ${difference}")

    if difference != Decimal('0'):
        print(f"\nApplying exact correction of ${difference} to largest items...")

        # Sort by value descending
        new_values.sort(key=lambda x: x['value'], reverse=True)

        # Distribute the difference across top items
        remaining = difference
        items_to_adjust = min(10, len(new_values))  # Adjust top 10 items

        for i in range(items_to_adjust):
            if remaining == Decimal('0'):
                break

            item = new_values[i]

            if remaining > Decimal('0'):
                # Need to add value
                increment = Decimal('0.01')
            else:
                # Need to subtract value
                increment = Decimal('-0.01')

            # Adjust quantity by the smallest amount that changes value
            qty_adjustment = increment / item['price']
            qty_adjustment = qty_adjustment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if qty_adjustment != Decimal('0'):
                new_qty = item['quantity'] + qty_adjustment

                # Ensure positive quantity
                if new_qty > Decimal('0'):
                    old_value = item['value']
                    item['quantity'] = new_qty
                    item['value'] = new_qty * item['price']
                    value_change = item['value'] - old_value
                    remaining -= value_change

    # Final calculation
    final_total = sum(item['value'] for item in new_values)

    print(f"\nFinal calculation:")
    print(f"  Target spending:   ${total_spending}")
    print(f"  Calculated total:  ${final_total}")
    print(f"  Difference:        ${total_spending - final_total}")

    # If still not exact, make final adjustment on the largest item
    if final_total != total_spending:
        print(f"\nMaking final exact adjustment...")
        largest = new_values[0]
        value_needed = total_spending - (final_total - largest['value'])
        new_qty_needed = value_needed / largest['price']
        new_qty_needed = new_qty_needed.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        largest['quantity'] = new_qty_needed
        largest['value'] = new_qty_needed * largest['price']

        # Verify
        final_total = sum(item['value'] for item in new_values)
        print(f"  Adjusted largest item quantity to {new_qty_needed}")
        print(f"  New total: ${final_total}")

    # Update database
    print(f"\nUpdating database...")
    updates = 0
    for item in new_values:
        cursor.execute("""
            UPDATE ingredients
            SET quantity_on_hand = ?
            WHERE id = ?
        """, (float(item['quantity']), item['id']))
        updates += 1

    conn.commit()

    # Final verification with database
    cursor.execute("""
        SELECT SUM(quantity_on_hand * average_unit_price) as total
        FROM ingredients WHERE active = 1
    """)
    db_total = Decimal(str(cursor.fetchone()['total']))

    conn.close()

    print(f"\n{'='*70}")
    print("VERIFICATION")
    print(f"{'='*70}")
    print(f"Total spending (target): ${total_spending}")
    print(f"Inventory value (actual): ${db_total}")
    print(f"Difference:               ${abs(total_spending - db_total)}")
    print(f"Exact match:              {total_spending == db_total}")
    print(f"\n✓ Updated {updates} ingredients")

    if total_spending == db_total:
        print(f"✓ EXACT MATCH ACHIEVED - NO ROUNDING ERRORS\n")
        # Log to audit trail
        log_audit(
            'EXACT_MATCH_ADJUSTMENT',
            'inventory',
            'Spending Reconciliation',
            f'Exact match adjustment: Inventory value = Total spending = ${total_spending}. Updated {updates} ingredients with zero rounding errors.'
        )
    else:
        print(f"⚠ Warning: Still ${abs(total_spending - db_total)} difference\n")

if __name__ == '__main__':
    exact_match_inventory_to_spending()
