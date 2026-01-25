"""
Migration to create invoice-related tables in organization database
"""
import sqlite3
import os

def create_invoice_tables(db_path):
    """Create invoice tables in the specified database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create invoices table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL UNIQUE,
            supplier_name TEXT NOT NULL,
            invoice_date DATE NOT NULL,
            received_date DATE,
            total_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'pending',
            reconciled BOOLEAN DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create unreconciled_invoices view
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS unreconciled_invoices AS
        SELECT * FROM invoices WHERE reconciled = 0
    """)

    # Create invoice_line_items table for detailed invoice tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            ingredient_id INTEGER,
            product_id INTEGER,
            description TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE SET NULL,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        )
    """)

    # Create indexes for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_reconciled ON invoices(reconciled)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_line_items(invoice_id)")

    conn.commit()
    conn.close()
    print(f"✅ Invoice tables created successfully in {db_path}")

if __name__ == '__main__':
    # Apply to all organization databases
    databases_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'databases')

    if os.path.exists(databases_dir):
        for filename in os.listdir(databases_dir):
            if filename.startswith('org_') and filename.endswith('.db'):
                db_path = os.path.join(databases_dir, filename)
                print(f"Migrating {filename}...")
                create_invoice_tables(db_path)
    else:
        print(f"❌ Databases directory not found: {databases_dir}")
