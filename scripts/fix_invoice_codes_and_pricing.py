#!/usr/bin/env python3
"""
1. Standardize ingredient codes in invoice_line_items
2. Recalculate inventory pricing based on corrected invoice data
"""
import sqlite3

def fix_codes_and_pricing():
    print("\n" + "="*70)
    print("🔧 STANDARDIZING INGREDIENT CODES AND RECALCULATING PRICING")
    print("="*70 + "\n")

    conn_invoices = sqlite3.connect('invoices.db')
    conn_invoices.row_factory = sqlite3.Row
    cursor_invoices = conn_invoices.cursor()

    conn_inv = sqlite3.connect('inventory.db')
    conn_inv.row_factory = sqlite3.Row
    cursor_inv = conn_inv.cursor()

    try:
        # Step 1: Standardize ingredient codes in invoices
        print("Step 1: Standardizing ingredient codes in invoice_line_items\n")

        code_mappings = {
            '10"-938620': 'SUB-10',
            '8" -954476': 'SUB-8'
        }

        for old_code, new_code in code_mappings.items():
            cursor_invoices.execute("""
                UPDATE invoice_line_items
                SET ingredient_code = ?
                WHERE ingredient_code = ?
            """, (new_code, old_code))
            rows_updated = cursor_invoices.rowcount
            if rows_updated > 0:
                print(f"   ✓ Updated {rows_updated} line items: {old_code} → {new_code}")

        conn_invoices.commit()

        # Step 2: Recalculate pricing for affected items
        print("\nStep 2: Recalculating inventory pricing\n")

        affected_codes = ['SUB-10', 'SUB-8']

        for ingredient_code in affected_codes:
            # Get all invoice data for this ingredient (now with corrected codes)
            cursor_invoices.execute("""
                SELECT ili.unit_price, ili.quantity_received, i.invoice_date
                FROM invoice_line_items ili
                JOIN invoices i ON ili.invoice_id = i.id
                WHERE ili.ingredient_code = ?
                ORDER BY i.invoice_date DESC
            """, (ingredient_code,))

            invoice_records = cursor_invoices.fetchall()

            if not invoice_records:
                continue

            # Get current inventory record
            cursor_inv.execute("""
                SELECT * FROM ingredients WHERE ingredient_code = ?
            """, (ingredient_code,))
            item = cursor_inv.fetchone()

            if not item:
                print(f"   ⚠️  {ingredient_code}: Not found in inventory, skipping")
                continue

            # Calculate correct units_per_case
            total_cases_received = sum(rec['quantity_received'] for rec in invoice_records)
            current_qty = item['quantity_on_hand']

            if current_qty > 0 and total_cases_received > 0:
                calculated_units_per_case = round(current_qty / total_cases_received)
            else:
                calculated_units_per_case = 1

            # Get latest price per case
            latest_price_per_case = invoice_records[0]['unit_price']

            # Calculate correct unit_cost
            correct_unit_cost = latest_price_per_case / calculated_units_per_case if calculated_units_per_case > 0 else latest_price_per_case

            # Calculate values
            old_value = current_qty * item['unit_cost']
            new_value = current_qty * correct_unit_cost

            print(f"📦 {ingredient_code} - {item['ingredient_name']}")
            print(f"   Cases received (from invoices): {total_cases_received}")
            print(f"   Current quantity: {current_qty} {item['unit_of_measure']}")
            print(f"   Units per case: {item['units_per_case']} → {calculated_units_per_case}")
            print(f"   Unit cost: ${item['unit_cost']:.4f} → ${correct_unit_cost:.4f}")
            print(f"   Total value: ${old_value:.2f} → ${new_value:.2f}")

            # Update inventory
            cursor_inv.execute("""
                UPDATE ingredients
                SET unit_cost = ?, units_per_case = ?
                WHERE ingredient_code = ?
            """, (correct_unit_cost, calculated_units_per_case, ingredient_code))

            print(f"   ✓ Updated\n")

        conn_inv.commit()

        # Step 3: Show final inventory value
        print("="*70)
        print("Final Inventory Summary:\n")

        cursor_inv.execute("""
            SELECT ingredient_code, ingredient_name, quantity_on_hand,
                   unit_of_measure, unit_cost, units_per_case,
                   (quantity_on_hand * unit_cost) as total_value
            FROM ingredients
            ORDER BY ingredient_name
        """)

        items = cursor_inv.fetchall()
        total_value = 0

        for item in items:
            value = item['total_value']
            total_value += value
            print(f"  {item['ingredient_code']:15} | {item['ingredient_name']:20} | "
                  f"{item['quantity_on_hand']:6.1f} {item['unit_of_measure']:4} @ "
                  f"${item['unit_cost']:.4f} = ${value:7.2f}")

        print("="*70)
        print(f"📊 TOTAL INVENTORY VALUE: ${total_value:.2f}")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {str(e)}\n")
        conn_invoices.rollback()
        conn_inv.rollback()
    finally:
        conn_invoices.close()
        conn_inv.close()

if __name__ == '__main__':
    fix_codes_and_pricing()
