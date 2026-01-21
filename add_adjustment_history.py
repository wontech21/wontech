import sqlite3
from datetime import datetime

INVENTORY_DB = 'inventory.db'

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def add_audit_entries():
    """Add retroactive audit entries for bulk inventory adjustments"""

    conn = get_db_connection(INVENTORY_DB)
    cursor = conn.cursor()

    # Entries to add (in chronological order)
    entries = [
        {
            'timestamp': '2026-01-12 14:00:00',  # Approximate time
            'action_type': 'BULK_INVENTORY_ADJUSTMENT',
            'entity_type': 'inventory',
            'entity_reference': 'All Active Items',
            'details': 'Adjusted inventory quantities to realistic levels for $100k/month business. Reduced from $237,658 to $14,039 (94.1% reduction across 941 items).',
            'user': 'System Script',
            'ip_address': 'localhost'
        },
        {
            'timestamp': '2026-01-12 14:05:00',
            'action_type': 'BULK_INVOICE_ADJUSTMENT',
            'entity_type': 'invoice',
            'entity_reference': 'All Invoices',
            'details': 'Proportionally adjusted all invoice quantities to match inventory reduction. Reduced from $236,749 to $13,968 (94.1% reduction across 173 invoices).',
            'user': 'System Script',
            'ip_address': 'localhost'
        },
        {
            'timestamp': '2026-01-12 14:10:00',
            'action_type': 'EXACT_MATCH_ADJUSTMENT',
            'entity_type': 'inventory',
            'entity_reference': 'Spending Reconciliation',
            'details': 'Performed exact match adjustment: Inventory value = Total spending = $13,968.16. Zero rounding errors achieved using precise decimal math.',
            'user': 'System Script',
            'ip_address': 'localhost'
        }
    ]

    print(f"\n{'='*70}")
    print("ADDING RETROACTIVE AUDIT ENTRIES")
    print(f"{'='*70}\n")

    for entry in entries:
        cursor.execute("""
            INSERT INTO audit_log
            (timestamp, action_type, entity_type, entity_reference, details, user, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry['timestamp'],
            entry['action_type'],
            entry['entity_type'],
            entry['entity_reference'],
            entry['details'],
            entry['user'],
            entry['ip_address']
        ))

        print(f"✓ Added: {entry['action_type']}")
        print(f"  Time: {entry['timestamp']}")
        print(f"  Details: {entry['details'][:80]}...")
        print()

    conn.commit()

    # Verify entries were added
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM audit_log
        WHERE action_type IN ('BULK_INVENTORY_ADJUSTMENT', 'BULK_INVOICE_ADJUSTMENT', 'EXACT_MATCH_ADJUSTMENT')
    """)
    count = cursor.fetchone()['count']

    conn.close()

    print(f"{'='*70}")
    print(f"✓ Successfully added {count} audit entries")
    print(f"✓ These will now appear in the History tab")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    add_audit_entries()
