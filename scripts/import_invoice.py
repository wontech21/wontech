#!/usr/bin/env python3
"""
Import invoice from CSV file to invoices database
"""

import sqlite3
import csv
import sys
from datetime import datetime

def import_invoice_csv(csv_file, invoice_number, supplier_name, invoice_date, received_date):
    """
    Import invoice from CSV file

    Args:
        csv_file: Path to CSV file
        invoice_number: Invoice number
        supplier_name: Supplier name
        invoice_date: Invoice date (YYYY-MM-DD)
        received_date: Date received (YYYY-MM-DD)
    """

    conn = sqlite3.connect('invoices.db')
    cur = conn.cursor()

    try:
        # Read CSV file
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            print("ERROR: CSV file is empty")
            return False

        # Get total from first row or calculate
        invoice_total_str = rows[0].get('invoice_total', '0') or '0'
        invoice_total = float(invoice_total_str.replace('$', '').replace(',', '').strip() or 0)
        payment_status = rows[0].get('payment_status', 'UNPAID').upper() or 'UNPAID'

        # If invoice_total not in CSV, sum all line items
        if invoice_total == 0:
            invoice_total = sum(float((row.get('total_price', '0') or '0').replace('$', '').replace(',', '').strip() or 0) for row in rows)

        print(f"\nImporting Invoice: {invoice_number}")
        print(f"Supplier: {supplier_name}")
        print(f"Invoice Date: {invoice_date}")
        print(f"Received Date: {received_date}")
        print(f"Total Amount: ${invoice_total:.2f}")
        print(f"Payment Status: {payment_status}")
        print(f"Line Items: {len(rows)}")
        print("-" * 60)

        # Insert invoice header
        cur.execute("""
            INSERT INTO invoices (invoice_number, supplier_name, invoice_date, received_date, total_amount, payment_status, reconciled)
            VALUES (?, ?, ?, ?, ?, ?, 'NO')
        """, (invoice_number, supplier_name, invoice_date, received_date, invoice_total, payment_status))

        invoice_id = cur.lastrowid

        # Insert line items
        for idx, row in enumerate(rows, 1):
            ingredient_code = row.get('code', '').strip()
            ingredient_name = row.get('item', '').strip()
            brand = row.get('brand', '').strip()
            size_modifier = row.get('size', '').strip()
            quantity_ordered = float(row.get('ordered', '0') or 0)
            quantity_received = float(row.get('received', '0') or 0)
            unit_of_measure = row.get('unit', '').strip()
            unit_price = float((row.get('unit_price', '0') or '0').replace('$', '').replace(',', '').strip() or 0)
            total_price = float((row.get('total_price', '0') or '0').replace('$', '').replace(',', '').strip() or 0)
            lot_number = row.get('lot_number', '').strip()
            expiration_date = row.get('expiration_date', '').strip()

            # Calculate total_quantity if not explicitly provided
            size = float(row.get('total_quantity', 0) or 0)
            if size == 0 and quantity_received > 0:
                size = quantity_received

            cur.execute("""
                INSERT INTO invoice_line_items
                (invoice_id, ingredient_code, ingredient_name, brand, size_modifier, size,
                 quantity_ordered, quantity_received, unit_of_measure, unit_price, total_price,
                 lot_number, expiration_date, reconciled_to_inventory)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NO')
            """, (invoice_id, ingredient_code, ingredient_name, brand, size_modifier, size,
                  quantity_ordered, quantity_received, unit_of_measure, unit_price, total_price,
                  lot_number or None, expiration_date or None))

            print(f"  ✓ {idx}. {ingredient_code}: {ingredient_name} - {quantity_received} {unit_of_measure} @ ${unit_price}")

        conn.commit()
        print(f"\n✓ Invoice {invoice_number} imported successfully!")
        print(f"\nNext step: Run reconciliation to add to inventory:")
        print(f"  python3 reconcile_invoice_v2.py {invoice_number}")

        return True

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: python3 import_invoice.py <csv_file> <invoice_number> <supplier> <invoice_date> <received_date>")
        print("\nExample:")
        print("  python3 import_invoice.py invoice.csv INV-2026-001 'Sysco Foods' 2026-01-10 2026-01-10")
        sys.exit(1)

    csv_file = sys.argv[1]
    invoice_number = sys.argv[2]
    supplier = sys.argv[3]
    invoice_date = sys.argv[4]
    received_date = sys.argv[5]

    import_invoice_csv(csv_file, invoice_number, supplier, invoice_date, received_date)
