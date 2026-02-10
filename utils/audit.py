"""Organization-level audit logging.

Logs actions to the org database's audit_log table.
This is distinct from the middleware log_audit which logs to master.db.
"""

from flask import request
from db_manager import get_org_db


def log_audit(action_type, entity_type, entity_id, entity_reference, details, user='System'):
    """Log an audit entry to the organization's audit_log table."""
    try:
        conn = get_org_db()
        cursor = conn.cursor()

        ip_address = request.remote_addr if request else None

        cursor.execute("""
            INSERT INTO audit_log (
                action_type, entity_type, entity_id, entity_reference,
                details, user, ip_address
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (action_type, entity_type, entity_id, entity_reference, details, user, ip_address))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit logging error: {str(e)}")
