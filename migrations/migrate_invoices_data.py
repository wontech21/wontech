"""
Migration: Migrate Invoice Data to Multi-Tenant Architecture

This script migrates invoice data from invoices.db to databases/org_1.db
Handles schema differences between the old and new invoice structures.
"""

import sqlite3
import os
from datetime import datetime

def migrate():
    base_dir = os.environ.get('DATABASE_DIR', os.path.dirname(os.path.dirname(__file__)))

    invoices_db_path = os.path.join(base_dir, 'invoices.db')
    org_db_path = os.path.join(base_dir, 'databases', 'org_1.db')

    print("\n" + "="*70)
    print("📦 MIGRATING INVOICE DATA TO MULTI-TENANT DATABASE")
    print("="*70)

    # Check if source database exists
    if not os.path.exists(invoices_db_path):
        print(f"\n⚠️  Source database not found: {invoices_db_path}")
        print("   No invoice data to migrate. Skipping...")
        return True

    # Check if destination database exists
    if not os.path.exists(org_db_path):
        print(f"\n❌ Destination database not found: {org_db_path}")
        print("   Please create organization database first.")
        return False

    try:
        # Connect to both databases
        source_conn = sqlite3.connect(invoices_db_path)
        source_conn.row_factory = sqlite3.Row
        source_cursor = source_conn.cursor()

        dest_conn = sqlite3.connect(org_db_path)
        dest_cursor = dest_conn.cursor()

        print(f"\n✓ Connected to source: {invoices_db_path}")
        print(f"✓ Connected to destination: {org_db_path}")

        # ==========================================
        # MIGRATE PURCHASE ORDERS
        # ==========================================
        print("\n1️⃣  Migrating purchase orders...")

        # First, ensure the purchase_orders table exists in org_1.db
        dest_cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT UNIQUE NOT NULL,
                supplier_name TEXT NOT NULL,
                order_date TEXT NOT NULL,
                expected_delivery TEXT,
                status TEXT DEFAULT 'PENDING',
                total_amount REAL DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Copy purchase orders
        source_cursor.execute("SELECT * FROM purchase_orders")
        pos = source_cursor.fetchall()

        po_count = 0
        for po_row in pos:
            po = dict(po_row)
            try:
                dest_cursor.execute("""
                    INSERT OR IGNORE INTO purchase_orders
                    (id, po_number, supplier_name, order_date, expected_delivery, status, total_amount, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    po['id'], po['po_number'], po['supplier_name'], po['order_date'],
                    po.get('expected_delivery'), po.get('status', 'PENDING'),
                    po.get('total_amount', 0), po.get('notes'), po.get('created_at')
                ))
                po_count += 1
            except sqlite3.IntegrityError:
                # PO already exists, skip
                pass

        print(f"   ✓ Migrated {po_count} purchase orders")

        # ==========================================
        # MIGRATE PO LINE ITEMS
        # ==========================================
        print("\n2️⃣  Migrating PO line items...")

        dest_cursor.execute("""
            CREATE TABLE IF NOT EXISTS po_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id INTEGER NOT NULL,
                ingredient_id INTEGER,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                received_quantity REAL DEFAULT 0,
                FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
            )
        """)

        source_cursor.execute("SELECT * FROM po_line_items")
        po_items = source_cursor.fetchall()

        po_item_count = 0
        for item_row in po_items:
            item = dict(item_row)

            # Try to find ingredient_id by ingredient_code
            ingredient_id = None
            if item.get('ingredient_code'):
                dest_cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?",
                                   (item['ingredient_code'],))
                result = dest_cursor.fetchone()
                if result:
                    ingredient_id = result[0]

            try:
                dest_cursor.execute("""
                    INSERT OR IGNORE INTO po_line_items
                    (id, po_id, ingredient_id, item_name, quantity, unit, unit_price, total_price, received_quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item['id'], item['po_id'], ingredient_id,
                    item['ingredient_name'], item['quantity_ordered'], item['unit_of_measure'],
                    item['unit_price'], item['total_price'], 0
                ))
                po_item_count += 1
            except sqlite3.IntegrityError:
                pass

        print(f"   ✓ Migrated {po_item_count} PO line items")

        # ==========================================
        # MIGRATE INVOICES
        # ==========================================
        print("\n3️⃣  Migrating invoices...")

        # Get existing invoices from org_1.db to avoid duplicates
        dest_cursor.execute("SELECT invoice_number FROM invoices")
        existing_invoices = {row[0] for row in dest_cursor.fetchall()}

        source_cursor.execute("SELECT * FROM invoices")
        invoices = source_cursor.fetchall()

        invoice_count = 0
        for inv_row in invoices:
            inv = dict(inv_row)
            # Skip if already exists
            if inv['invoice_number'] in existing_invoices:
                continue

            # Convert reconciled from 'YES'/'NO' to boolean
            reconciled = 1 if inv.get('reconciled') == 'YES' else 0

            # Map payment status
            payment_status_map = {
                'UNPAID': 'pending',
                'PAID': 'paid',
                'PARTIAL': 'partial'
            }
            payment_status = payment_status_map.get(inv.get('payment_status', 'UNPAID'), 'pending')

            try:
                # Note: org_1.db doesn't have po_id, payment_date, reconciled_date columns
                # We'll include them in notes if they exist
                notes = inv.get('notes') or ''
                if inv.get('payment_date'):
                    notes += f"\nPayment Date: {inv['payment_date']}"
                if inv.get('reconciled_date'):
                    notes += f"\nReconciled Date: {inv['reconciled_date']}"
                if inv.get('po_id'):
                    notes += f"\nPO ID: {inv['po_id']}"

                dest_cursor.execute("""
                    INSERT INTO invoices
                    (invoice_number, supplier_name, invoice_date, received_date,
                     total_amount, payment_status, reconciled, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    inv['invoice_number'], inv['supplier_name'], inv['invoice_date'],
                    inv.get('received_date'), inv['total_amount'], payment_status,
                    reconciled, notes.strip(), inv.get('created_at')
                ))
                invoice_count += 1
            except sqlite3.IntegrityError as e:
                print(f"   ⚠️  Skipped duplicate invoice: {inv['invoice_number']}")

        print(f"   ✓ Migrated {invoice_count} invoices")

        # ==========================================
        # MIGRATE INVOICE LINE ITEMS
        # ==========================================
        print("\n4️⃣  Migrating invoice line items...")

        # Table already exists with different schema, use it
        # Schema: description (not item_name), no unit, brand, lot_number, expiration_date columns

        # Need to map old invoice IDs to new invoice IDs
        # Get mapping based on invoice_number
        dest_cursor.execute("SELECT id, invoice_number FROM invoices")
        invoice_id_map = {row[1]: row[0] for row in dest_cursor.fetchall()}

        source_cursor.execute("""
            SELECT ili.*, i.invoice_number
            FROM invoice_line_items ili
            JOIN invoices i ON ili.invoice_id = i.id
        """)
        line_items = source_cursor.fetchall()

        line_item_count = 0
        for item_row in line_items:
            item = dict(item_row)
            # Map to new invoice ID
            new_invoice_id = invoice_id_map.get(item['invoice_number'])
            if not new_invoice_id:
                continue

            # Try to find ingredient_id by ingredient_code
            ingredient_id = None
            if item.get('ingredient_code'):
                dest_cursor.execute("SELECT id FROM ingredients WHERE ingredient_code = ?",
                                   (item['ingredient_code'],))
                result = dest_cursor.fetchone()
                if result:
                    ingredient_id = result[0]

            # Build description with all relevant info
            description = item['ingredient_name']
            if item.get('brand'):
                description += f" - {item['brand']}"
            if item.get('size'):
                description += f" ({item['size']} {item['unit_of_measure']})"
            if item.get('lot_number'):
                description += f" [Lot: {item['lot_number']}]"
            if item.get('expiration_date'):
                description += f" [Exp: {item['expiration_date']}]"

            try:
                dest_cursor.execute("""
                    INSERT INTO invoice_line_items
                    (invoice_id, ingredient_id, description, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    new_invoice_id, ingredient_id,
                    description, item['quantity_received'],
                    item['unit_price'], item['total_price']
                ))
                line_item_count += 1
            except sqlite3.IntegrityError:
                pass

        print(f"   ✓ Migrated {line_item_count} invoice line items")

        # ==========================================
        # MIGRATE RECONCILIATION LOG
        # ==========================================
        print("\n5️⃣  Migrating reconciliation log...")

        dest_cursor.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                quantity_added REAL NOT NULL,
                unit_cost REAL NOT NULL,
                reconciled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reconciled_by TEXT,
                notes TEXT,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
            )
        """)

        source_cursor.execute("""
            SELECT rl.*, i.invoice_number
            FROM reconciliation_log rl
            JOIN invoices i ON rl.invoice_id = i.id
        """)
        recon_logs = source_cursor.fetchall()

        recon_count = 0
        for log_row in recon_logs:
            log = dict(log_row)
            new_invoice_id = invoice_id_map.get(log['invoice_number'])
            if not new_invoice_id:
                continue

            try:
                dest_cursor.execute("""
                    INSERT INTO reconciliation_log
                    (invoice_id, ingredient_id, quantity_added, unit_cost, reconciled_at, reconciled_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_invoice_id, log['ingredient_id'], log['quantity_added'],
                    log['unit_cost'], log.get('reconciled_at'), log.get('reconciled_by'),
                    log.get('notes')
                ))
                recon_count += 1
            except sqlite3.IntegrityError:
                pass

        print(f"   ✓ Migrated {recon_count} reconciliation log entries")

        # Create indexes
        print("\n6️⃣  Creating indexes...")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(po_number)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_line_items_po ON po_line_items(po_id)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_line_items_invoice ON invoice_line_items(invoice_id)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_recon_log_invoice ON reconciliation_log(invoice_id)")
        print("   ✓ Indexes created")

        # Commit changes
        dest_conn.commit()

        print("\n" + "="*70)
        print("✅ INVOICE DATA MIGRATION COMPLETE!")
        print("="*70)

        print("\n📊 Migration Summary:")
        print(f"   Purchase Orders:     {po_count}")
        print(f"   PO Line Items:       {po_item_count}")
        print(f"   Invoices:            {invoice_count}")
        print(f"   Invoice Line Items:  {line_item_count}")
        print(f"   Reconciliation Logs: {recon_count}")

        print("\n✓ All invoice data has been migrated to multi-tenant database")
        print(f"✓ Source: {invoices_db_path}")
        print(f"✓ Destination: {org_db_path}")

        # Close connections
        source_conn.close()
        dest_conn.close()

        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = migrate()
    exit(0 if success else 1)
