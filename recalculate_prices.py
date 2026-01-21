#!/usr/bin/env python3
"""
One-time script to recalculate prices for all existing ingredients
"""
import sqlite3

def get_db_connection(db_name):
    """Create database connection"""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

def update_ingredient_prices(ingredient_code, cursor_invoices, cursor_inventory):
    """Update last_unit_price and average_unit_price for an ingredient based on invoice history"""
    try:
        # Get all prices for this ingredient from invoice line items, ordered by invoice date (most recent first)
        cursor_invoices.execute("""
            SELECT ili.unit_price, i.invoice_date, ili.quantity_received
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
            WHERE ili.ingredient_code = ?
            ORDER BY i.invoice_date DESC
        """, (ingredient_code,))

        price_records = cursor_invoices.fetchall()

        if price_records:
            # Last price is the most recent (first in the list)
            last_price = price_records[0]['unit_price']

            # Calculate weighted average price (weighted by quantity received)
            total_cost = sum(rec['unit_price'] * rec['quantity_received'] for rec in price_records)
            total_quantity = sum(rec['quantity_received'] for rec in price_records)
            average_price = total_cost / total_quantity if total_quantity > 0 else last_price

            # Update all inventory records for this ingredient code
            cursor_inventory.execute("""
                UPDATE ingredients
                SET last_unit_price = ?, average_unit_price = ?
                WHERE ingredient_code = ?
            """, (last_price, average_price, ingredient_code))

            print(f"  {ingredient_code}: Last=${last_price:.2f}, Avg=${average_price:.2f}")
            return last_price, average_price

        return None, None
    except Exception as e:
        print(f"  Error updating {ingredient_code}: {str(e)}")
        return None, None

def main():
    print("\n" + "="*60)
    print("🔄 RECALCULATING PRICES FOR ALL INGREDIENTS")
    print("="*60 + "\n")

    conn_inventory = get_db_connection('inventory.db')
    cursor_inventory = conn_inventory.cursor()

    conn_invoices = get_db_connection('invoices.db')
    cursor_invoices = conn_invoices.cursor()

    # Get all unique ingredient codes
    cursor_inventory.execute("SELECT DISTINCT ingredient_code FROM ingredients")
    ingredient_codes = [row['ingredient_code'] for row in cursor_inventory.fetchall()]

    print(f"Found {len(ingredient_codes)} unique ingredient codes\n")

    updated_from_invoices = 0
    updated_from_unit_cost = 0

    for ingredient_code in ingredient_codes:
        last_price, avg_price = update_ingredient_prices(ingredient_code, cursor_invoices, cursor_inventory)
        if last_price is not None:
            updated_from_invoices += 1
        else:
            # No invoice history - use unit_cost as fallback
            cursor_inventory.execute("""
                SELECT unit_cost FROM ingredients
                WHERE ingredient_code = ? AND unit_cost IS NOT NULL AND unit_cost > 0
                LIMIT 1
            """, (ingredient_code,))
            result = cursor_inventory.fetchone()
            if result and result['unit_cost']:
                unit_cost = result['unit_cost']
                cursor_inventory.execute("""
                    UPDATE ingredients
                    SET last_unit_price = ?, average_unit_price = ?
                    WHERE ingredient_code = ?
                """, (unit_cost, unit_cost, ingredient_code))
                print(f"  {ingredient_code}: Using unit_cost=${unit_cost:.2f} (no invoice history)")
                updated_from_unit_cost += 1

    conn_inventory.commit()
    conn_inventory.close()
    conn_invoices.close()

    print(f"\n✓ Updated prices:")
    print(f"  - {updated_from_invoices} from invoice history")
    print(f"  - {updated_from_unit_cost} from unit_cost (no invoices)")
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
