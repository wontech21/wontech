#!/usr/bin/env python3
"""
Create audit_log table in the inventory database
"""
import sqlite3

def create_audit_table():
    print("\n" + "="*70)
    print("📋 CREATING AUDIT LOG TABLE")
    print("="*70 + "\n")

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    try:
        # Create audit_log table
        print("Creating audit_log table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                action_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                entity_reference TEXT,
                details TEXT,
                user TEXT DEFAULT 'System',
                ip_address TEXT
            )
        """)

        # Create indexes for performance
        print("Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action_type
            ON audit_log(action_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_entity
            ON audit_log(entity_type, entity_id)
        """)

        conn.commit()

        print("\n✓ Audit log table created successfully!")
        print("  - Tracks all invoice and count operations")
        print("  - Sortable by timestamp, action type, entity")
        print("  - Includes detailed information for each action\n")

    except Exception as e:
        print(f"\n✗ Error: {str(e)}\n")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    create_audit_table()
