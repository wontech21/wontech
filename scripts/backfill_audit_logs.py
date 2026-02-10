#!/usr/bin/env python3
"""
Backfill audit logs for generated historical data
"""

import sqlite3
from datetime import datetime

INVENTORY_DB = 'inventory.db'
INVOICES_DB = 'invoices.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def backfill_sales_audit_logs():
    """Create audit logs for all sales records"""
    print("\n📝 Backfilling sales audit logs...")

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get all sales that don't have audit logs
    cursor.execute("""
        SELECT id, sale_date, sale_time, product_id, product_name, quantity_sold, revenue, processed_date
        FROM sales_history
        WHERE sale_date >= '2025-10-25'
        ORDER BY sale_date, sale_time
    """)

    sales = cursor.fetchall()

    audit_entries = []
    for sale in sales:
        # Create timestamp from sale_date and sale_time
        if sale['sale_time']:
            timestamp = f"{sale['sale_date']} {sale['sale_time']}"
        else:
            timestamp = sale['processed_date']

        audit_entries.append({
            'timestamp': timestamp,
            'action_type': 'SALE_RECORDED',
            'entity_type': 'SALE',
            'entity_id': sale['id'],
            'entity_reference': f"Sale #{sale['id']}",
            'details': f"Product: {sale['product_name']}, Qty: {sale['quantity_sold']}, Revenue: ${sale['revenue']:.2f}",
            'user': 'System',
            'ip_address': None
        })

    if audit_entries:
        print(f"   Inserting {len(audit_entries)} sales audit entries...")
        cursor.executemany("""
            INSERT INTO audit_log (timestamp, action_type, entity_type, entity_id, entity_reference, details, user, ip_address)
            VALUES (:timestamp, :action_type, :entity_type, :entity_id, :entity_reference, :details, :user, :ip_address)
        """, audit_entries)

        conn.commit()
        print(f"   ✅ Added {len(audit_entries)} sales audit logs")
    else:
        print("   No sales to add")

    conn.close()

def backfill_invoice_audit_logs():
    """Create audit logs for all invoices"""
    print("\n📝 Backfilling invoice audit logs...")

    conn_inv = get_db_connection(INVOICES_DB)
    conn_inventory = get_db_connection(INVENTORY_DB)
    cursor_inv = conn_inv.cursor()
    cursor_inventory = conn_inventory.cursor()

    # Get all invoices from the historical period
    cursor_inv.execute("""
        SELECT id, invoice_number, supplier_name, invoice_date, total_amount, payment_status, received_date
        FROM invoices
        WHERE invoice_date >= '2025-10-25'
        ORDER BY invoice_date
    """)

    invoices = cursor_inv.fetchall()

    audit_entries = []
    for invoice in invoices:
        timestamp = invoice['received_date'] or f"{invoice['invoice_date']} 12:00:00"

        # Invoice created
        audit_entries.append({
            'timestamp': timestamp,
            'action_type': 'INVOICE_CREATED',
            'entity_type': 'INVOICE',
            'entity_id': invoice['id'],
            'entity_reference': invoice['invoice_number'],
            'details': f"Supplier: {invoice['supplier_name']}, Total: ${invoice['total_amount']:.2f}",
            'user': 'System',
            'ip_address': None
        })

        # Payment status if paid
        if invoice['payment_status'] == 'PAID':
            audit_entries.append({
                'timestamp': timestamp,
                'action_type': 'INVOICE_PAYMENT_PAID',
                'entity_type': 'INVOICE',
                'entity_id': invoice['id'],
                'entity_reference': invoice['invoice_number'],
                'details': f"Invoice fully paid: ${invoice['total_amount']:.2f}",
                'user': 'System',
                'ip_address': None
            })

    if audit_entries:
        print(f"   Inserting {len(audit_entries)} invoice audit entries...")
        cursor_inventory.executemany("""
            INSERT INTO audit_log (timestamp, action_type, entity_type, entity_id, entity_reference, details, user, ip_address)
            VALUES (:timestamp, :action_type, :entity_type, :entity_id, :entity_reference, :details, :user, :ip_address)
        """, audit_entries)

        conn_inventory.commit()
        print(f"   ✅ Added {len(audit_entries)} invoice audit logs")
    else:
        print("   No invoices to add")

    conn_inv.close()
    conn_inventory.close()

def backfill_count_audit_logs():
    """Create audit logs for all inventory counts"""
    print("\n📝 Backfilling inventory count audit logs...")

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Get all counts from the historical period
    cursor.execute("""
        SELECT id, count_number, count_date, counted_by, created_at
        FROM inventory_counts
        WHERE count_date >= '2025-10-25'
        ORDER BY count_date
    """)

    counts = cursor.fetchall()

    audit_entries = []
    for count in counts:
        timestamp = count['created_at'] or f"{count['count_date']} 18:00:00"

        # Get count summary
        cursor.execute("""
            SELECT COUNT(*) as items_counted, SUM(ABS(variance)) as total_variance
            FROM count_line_items
            WHERE count_id = ?
        """, (count['id'],))

        summary = cursor.fetchone()

        audit_entries.append({
            'timestamp': timestamp,
            'action_type': 'COUNT_CREATED',
            'entity_type': 'COUNT',
            'entity_id': count['id'],
            'entity_reference': count['count_number'],
            'details': f"Counted by: {count['counted_by'] or 'Unknown'}, Items: {summary['items_counted']}, Total Variance: {summary['total_variance']:.2f}",
            'user': count['counted_by'] or 'System',
            'ip_address': None
        })

    if audit_entries:
        print(f"   Inserting {len(audit_entries)} count audit entries...")
        cursor.executemany("""
            INSERT INTO audit_log (timestamp, action_type, entity_type, entity_id, entity_reference, details, user, ip_address)
            VALUES (:timestamp, :action_type, :entity_type, :entity_id, :entity_reference, :details, :user, :ip_address)
        """, audit_entries)

        conn.commit()
        print(f"   ✅ Added {len(audit_entries)} count audit logs")
    else:
        print("   No counts to add")

    conn.close()

def main():
    print("=" * 70)
    print("🔍 BACKFILLING AUDIT LOGS FOR HISTORICAL DATA")
    print("=" * 70)

    backfill_sales_audit_logs()
    backfill_invoice_audit_logs()
    backfill_count_audit_logs()

    print("\n" + "=" * 70)
    print("✅ AUDIT LOG BACKFILL COMPLETE!")
    print("=" * 70)

    # Show summary
    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT action_type, COUNT(*) as count
        FROM audit_log
        GROUP BY action_type
        ORDER BY count DESC
    """)

    print("\n📊 Audit Log Summary:")
    for row in cursor.fetchall():
        print(f"   {row['action_type']}: {row['count']}")

    cursor.execute("SELECT COUNT(*) as total FROM audit_log")
    total = cursor.fetchone()['total']
    print(f"\n   Total audit entries: {total}")

    conn.close()

if __name__ == '__main__':
    main()
