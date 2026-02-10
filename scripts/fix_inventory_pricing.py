#!/usr/bin/env python3
"""
Fix inventory unit_cost values by recalculating from invoice data
The unit_cost should be price per individual unit, not price per case/bag
"""
import sqlite3

def fix_inventory_pricing():
    print("\n" + "="*70)
    print("💰 FIXING INVENTORY UNIT COST VALUES")
    print("="*70 + "\n")

    conn_inv = sqlite3.connect('inventory.db')
    conn_inv.row_factory = sqlite3.Row
    cursor_inv = conn_inv.cursor()

    conn_invoices = sqlite3.connect('invoices.db')
    conn_invoices.row_factory = sqlite3.Row
    cursor_invoices = conn_invoices.cursor()

    try:
        # Get all inventory items
        cursor_inv.execute("SELECT * FROM ingredients")
        items = cursor_inv.fetchall()

        print(f"Found {len(items)} inventory items to analyze\n")

        for item in items:
            ingredient_code = item['ingredient_code']
            current_unit_cost = item['unit_cost']
            current_units_per_case = item['units_per_case'] or 1
            current_qty = item['quantity_on_hand']

            # Get invoice data for this ingredient to determine correct units_per_case
            cursor_invoices.execute("""
                SELECT ili.unit_price, ili.quantity_received, i.invoice_date
                FROM invoice_line_items ili
                JOIN invoices i ON ili.invoice_id = i.id
                WHERE ili.ingredient_code = ?
                ORDER BY i.invoice_date DESC
            """, (ingredient_code,))

            invoice_records = cursor_invoices.fetchall()

            if not invoice_records:
                print(f"⚠️  {ingredient_code}: No invoice data found, skipping")
                continue

            # Calculate the actual units_per_case from invoice data
            # Sum all quantity_received (cases/bags) from invoices
            total_cases_received = sum(rec['quantity_received'] for rec in invoice_records)

            # If current quantity is greater than total cases, then units_per_case > 1
            if current_qty > total_cases_received and total_cases_received > 0:
                calculated_units_per_case = round(current_qty / total_cases_received)
            else:
                calculated_units_per_case = 1

            # Get the most recent unit_price (price per case/bag from invoice)
            latest_price_per_case = invoice_records[0]['unit_price']

            # Calculate correct unit_cost (price per individual unit)
            correct_unit_cost = latest_price_per_case / calculated_units_per_case if calculated_units_per_case > 0 else latest_price_per_case

            # Calculate current vs correct inventory value
            current_value = current_qty * current_unit_cost
            correct_value = current_qty * correct_unit_cost

            print(f"📦 {ingredient_code} - {item['ingredient_name']}")
            print(f"   Quantity: {current_qty} {item['unit_of_measure']}")
            print(f"   Units per case: {current_units_per_case} → {calculated_units_per_case}")
            print(f"   Unit cost: ${current_unit_cost:.4f} → ${correct_unit_cost:.4f}")
            print(f"   Inventory value: ${current_value:.2f} → ${correct_value:.2f}")

            # Update the record
            cursor_inv.execute("""
                UPDATE ingredients
                SET unit_cost = ?, units_per_case = ?
                WHERE ingredient_code = ?
            """, (correct_unit_cost, calculated_units_per_case, ingredient_code))

            print(f"   ✓ Updated\n")

        conn_inv.commit()

        # Show final totals
        cursor_inv.execute("""
            SELECT SUM(quantity_on_hand * unit_cost) as total_value
            FROM ingredients
        """)
        result = cursor_inv.fetchone()
        total_value = result['total_value']

        print("="*70)
        print(f"✓ All inventory pricing fixed!")
        print(f"📊 Total inventory value: ${total_value:.2f}")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {str(e)}\n")
        conn_inv.rollback()
    finally:
        conn_inv.close()
        conn_invoices.close()

if __name__ == '__main__':
    fix_inventory_pricing()
