"""
Database Connection Manager for Separate Database Architecture
SINGLE SOURCE OF TRUTH for all database schemas.

Two types of databases:
1. master.db - Users, organizations, sessions, invitations, audit (global data)
2. databases/org_{id}.db - Each organization's business data (isolated)

Usage:
    from db_manager import get_master_db, get_org_db, create_org_database, create_master_db

    # For user authentication, organization management
    conn = get_master_db()

    # For business data (inventory, sales, etc.)
    conn = get_org_db()  # Uses g.organization automatically

    # Initialize master schema (safe to call multiple times)
    create_master_db()

    # Create a new org database with full schema
    create_org_database(organization_id)
"""

import sqlite3
import os
import shutil
from contextlib import contextmanager
from flask import g

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_DB_PATH = os.path.join(BASE_DIR, 'master.db')
DATABASES_DIR = os.path.join(BASE_DIR, 'databases')

# Ensure directories exist
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(DATABASES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Org path cache  (org_id -> db filesystem path)
# Avoids querying master.db on every request for the same org.
# ---------------------------------------------------------------------------
_org_path_cache: dict[int, str] = {}


# ===========================================================================
#  Connection helpers
# ===========================================================================

def get_master_db():
    """
    Get connection to master database.
    Contains: organizations, users, sessions, invitations, audit_log,
              permission_definitions, role_templates.
    """
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_org_db(organization_id=None):
    """
    Get connection to an organization's database.
    Contains: ingredients, products, recipes, sales, invoices, employees, etc.

    Args:
        organization_id: Optional org ID. If not provided, uses g.organization.

    Returns:
        SQLite connection to organization's database.
    """
    if organization_id is None:
        if not hasattr(g, 'organization') or not g.organization:
            raise ValueError(
                "No organization context set. Use @organization_required decorator."
            )
        org_id = g.organization['id']
    else:
        org_id = organization_id

    # --- Check the cache first ---
    if org_id in _org_path_cache:
        db_path = _org_path_cache[org_id]
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            # Cached path is stale; remove it and fall through
            del _org_path_cache[org_id]

    # --- Cache miss: query master.db ---
    master_conn = get_master_db()
    cursor = master_conn.cursor()
    cursor.execute("SELECT db_filename FROM organizations WHERE id = ?", (org_id,))
    result = cursor.fetchone()
    master_conn.close()

    if not result:
        raise ValueError(f"Organization {org_id} not found")

    db_filename = result['db_filename']
    db_path = os.path.join(DATABASES_DIR, db_filename)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Organization database not found: {db_path}")

    # Store in cache for next time
    _org_path_cache[org_id] = db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def master_db():
    """Context-managed master database connection. Auto-closes on exit."""
    conn = get_master_db()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def org_db(organization_id=None):
    """Context-managed org database connection. Auto-closes on exit."""
    conn = get_org_db(organization_id)
    try:
        yield conn
    finally:
        conn.close()


def get_org_db_path(organization_id):
    """Get filesystem path to organization's database file."""
    master_conn = get_master_db()
    cursor = master_conn.cursor()
    cursor.execute(
        "SELECT db_filename FROM organizations WHERE id = ?",
        (organization_id,),
    )
    result = cursor.fetchone()
    master_conn.close()

    if not result:
        return None

    return os.path.join(DATABASES_DIR, result['db_filename'])


# ===========================================================================
#  Migration helpers
# ===========================================================================

def _ensure_org_column(cursor, column_name, column_def):
    """Add a column to organizations table if it doesn't exist yet."""
    try:
        cursor.execute(f"ALTER TABLE organizations ADD COLUMN {column_name} {column_def}")
    except Exception:
        pass  # Column already exists


def _ensure_column(cursor, table_name, column_name, column_def):
    """Add a column to any table if it doesn't exist yet."""
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
    except Exception:
        pass  # Column already exists


# ===========================================================================
#  Master database schema  (master.db)
# ===========================================================================

def create_master_db():
    """
    Create (or update) the master database with the canonical schema.
    Safe to call multiple times — every statement uses IF NOT EXISTS.

    Tables created:
        organizations, users, permission_definitions, role_templates,
        user_sessions, organization_invitations, audit_log
    """
    conn = sqlite3.connect(MASTER_DB_PATH)
    cursor = conn.cursor()

    # ---- organizations ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            db_filename TEXT NOT NULL UNIQUE,
            owner_name TEXT NOT NULL,
            owner_email TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            logo_url TEXT,
            primary_color TEXT DEFAULT '#2563eb',
            plan_type TEXT DEFAULT 'basic',
            subscription_status TEXT DEFAULT 'active',
            monthly_price DECIMAL(10,2) DEFAULT 99.00,
            billing_email TEXT,
            max_employees INTEGER DEFAULT 50,
            max_products INTEGER DEFAULT 1000,
            max_storage_mb INTEGER DEFAULT 5000,
            features TEXT,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_organizations_active ON organizations(active)"
    )
    # -- Storefront columns (added for customer-facing website + online ordering)
    _ensure_org_column(cursor, 'custom_domain', 'TEXT')
    _ensure_org_column(cursor, 'secondary_color', "TEXT DEFAULT '#1e40af'")
    _ensure_org_column(cursor, 'accent_color', "TEXT DEFAULT '#f59e0b'")
    _ensure_org_column(cursor, 'tagline', 'TEXT')
    _ensure_org_column(cursor, 'description', 'TEXT')
    _ensure_org_column(cursor, 'website_enabled', 'BOOLEAN DEFAULT 0')
    _ensure_org_column(cursor, 'online_ordering_enabled', 'BOOLEAN DEFAULT 0')
    _ensure_org_column(cursor, 'delivery_enabled', 'BOOLEAN DEFAULT 0')
    _ensure_org_column(cursor, 'pickup_enabled', 'BOOLEAN DEFAULT 1')
    _ensure_org_column(cursor, 'dinein_enabled', 'BOOLEAN DEFAULT 0')
    _ensure_org_column(cursor, 'delivery_fee', 'REAL DEFAULT 0')
    _ensure_org_column(cursor, 'delivery_minimum', 'REAL DEFAULT 0')
    _ensure_org_column(cursor, 'tax_rate', 'REAL DEFAULT 0')
    _ensure_org_column(cursor, 'estimated_pickup_minutes', 'INTEGER DEFAULT 20')
    _ensure_org_column(cursor, 'estimated_delivery_minutes', 'INTEGER DEFAULT 45')
    _ensure_org_column(cursor, 'facebook_url', 'TEXT')
    _ensure_org_column(cursor, 'instagram_url', 'TEXT')
    _ensure_org_column(cursor, 'google_maps_url', 'TEXT')
    _ensure_org_column(cursor, 'hero_image_url', 'TEXT')
    _ensure_org_column(cursor, 'order_cutoff_minutes', 'INTEGER DEFAULT 30')

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_organizations_custom_domain ON organizations(custom_domain)"
    )

    # ---- users ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT,
            avatar_url TEXT,
            role TEXT NOT NULL,
            permissions TEXT,
            can_switch_organizations BOOLEAN DEFAULT 0,
            current_organization_id INTEGER,
            active BOOLEAN DEFAULT 1,
            last_login TIMESTAMP,
            last_password_change TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (current_organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
            CHECK (
                (role = 'super_admin' AND organization_id IS NULL) OR
                (role != 'super_admin' AND organization_id IS NOT NULL)
            )
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_organization ON users(organization_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)"
    )

    # ---- permission_definitions ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS permission_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permission_key TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            required_role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---- role_templates ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            description TEXT,
            default_permissions TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---- user_sessions ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT NOT NULL UNIQUE,
            organization_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)"
    )

    # ---- organization_invitations ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organization_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            permissions TEXT,
            invited_by INTEGER NOT NULL,
            invitation_token TEXT NOT NULL UNIQUE,
            status TEXT DEFAULT 'pending',
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accepted_at TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_invitations_token ON organization_invitations(invitation_token)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_invitations_email ON organization_invitations(email)"
    )

    # ---- audit_log ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            changes TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_organization ON audit_log(organization_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)"
    )

    # ---- schema_migrations ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT
        )
    """)

    # ---- share_tokens (persistent share links) ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS share_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            organization_id INTEGER,
            file_data BLOB NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            created_by INTEGER,
            expires_at DATETIME NOT NULL,
            accessed_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_share_token ON share_tokens(token)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_share_expires ON share_tokens(expires_at)"
    )

    conn.commit()
    conn.close()
    print(f"Master database initialized: {MASTER_DB_PATH}")


# ===========================================================================
#  Organization database schema  (org_X.db)
# ===========================================================================

def create_org_database(organization_id):
    """
    Create a new database for an organization with the full canonical schema.

    If the database file already exists it is returned as-is (idempotent).
    All statements use IF NOT EXISTS so this is also safe to call on an
    existing database to bring it up-to-date with new tables/views/indexes.

    Args:
        organization_id: ID of organization from master database.

    Returns:
        Path to the created (or existing) database file.
    """
    os.makedirs(DATABASES_DIR, exist_ok=True)

    # Get organization info from master
    master_conn = get_master_db()
    cursor = master_conn.cursor()
    cursor.execute(
        "SELECT db_filename FROM organizations WHERE id = ?",
        (organization_id,),
    )
    result = cursor.fetchone()
    master_conn.close()

    if not result:
        raise ValueError(
            f"Organization {organization_id} not found in master database"
        )

    db_filename = result['db_filename']
    new_db_path = os.path.join(DATABASES_DIR, db_filename)

    already_existed = os.path.exists(new_db_path)
    if already_existed:
        print(f"   Database already exists: {new_db_path}")

    # Connect (creates file if it does not exist yet)
    conn = sqlite3.connect(new_db_path)
    cur = conn.cursor()

    # ------------------------------------------------------------------
    #  TABLES  (30 tables)
    # ------------------------------------------------------------------

    # -- Core: Ingredients -------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_code TEXT NOT NULL,
            ingredient_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_of_measure TEXT NOT NULL,
            quantity_on_hand REAL NOT NULL DEFAULT 0,
            unit_cost REAL NOT NULL,
            supplier_name TEXT,
            supplier_contact TEXT,
            reorder_level REAL DEFAULT 0,
            reorder_quantity REAL,
            storage_location TEXT,
            expiration_date TEXT,
            lot_number TEXT,
            date_received TEXT,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            brand TEXT,
            last_unit_price REAL,
            average_unit_price REAL,
            units_per_case REAL DEFAULT 1,
            active INTEGER DEFAULT 1,
            is_composite INTEGER DEFAULT 0,
            batch_size REAL DEFAULT NULL,
            barcode TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ingredient_code ON ingredients(ingredient_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ingredient_category ON ingredients(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ingredients_active ON ingredients(active)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ingredients_barcode ON ingredients(barcode)")

    # -- Core: Products ----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_of_measure TEXT NOT NULL,
            quantity_on_hand REAL NOT NULL DEFAULT 0,
            selling_price REAL NOT NULL,
            shelf_life_days INTEGER,
            storage_requirements TEXT,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            barcode TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_product_code ON products(product_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")

    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS update_product_timestamp
        AFTER UPDATE ON products
        BEGIN
            UPDATE products SET last_updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    """)

    # -- Core: Recipes (product ingredients) --------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            ingredient_id INTEGER NOT NULL,
            quantity_needed REAL NOT NULL,
            unit_of_measure TEXT NOT NULL,
            notes TEXT,
            source_type TEXT DEFAULT 'ingredient' NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recipe_product ON recipes(product_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recipe_ingredient ON recipes(ingredient_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recipes_source_type ON recipes(source_type)")

    # -- Core: Composite Ingredient Recipes --------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredient_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            composite_ingredient_id INTEGER NOT NULL,
            base_ingredient_id INTEGER NOT NULL,
            quantity_needed REAL NOT NULL,
            unit_of_measure TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (composite_ingredient_id) REFERENCES ingredients(id),
            FOREIGN KEY (base_ingredient_id) REFERENCES ingredients(id)
        )
    """)

    # -- Core: Categories --------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -- Core: Brands ------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT UNIQUE NOT NULL,
            notes TEXT
        )
    """)

    # -- Core: Suppliers ---------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT UNIQUE NOT NULL,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            payment_terms TEXT,
            notes TEXT
        )
    """)

    # -- Transactions: Sales History ---------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity_sold REAL NOT NULL,
            revenue REAL NOT NULL,
            cost_of_goods REAL NOT NULL,
            gross_profit REAL NOT NULL,
            processed_date TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            sale_time TEXT,
            original_price REAL,
            sale_price REAL,
            discount_amount REAL,
            discount_percent REAL,
            order_type TEXT DEFAULT 'dine_in',
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_history_date ON sales_history(sale_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_history_product ON sales_history(product_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_history_order_type ON sales_history(order_type)")

    # Migration: add order_type to existing databases that lack it
    try:
        cur.execute("ALTER TABLE sales_history ADD COLUMN order_type TEXT DEFAULT 'dine_in'")
    except Exception:
        pass  # Column already exists

    # -- Transactions: Ingredient Transactions -----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredient_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity_change REAL NOT NULL,
            unit_cost REAL,
            transaction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            related_batch_id INTEGER,
            notes TEXT,
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id),
            FOREIGN KEY (related_batch_id) REFERENCES production_batches(id)
        )
    """)

    # -- Transactions: Product Transactions --------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity_change REAL NOT NULL,
            transaction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            related_batch_id INTEGER,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (related_batch_id) REFERENCES production_batches(id)
        )
    """)

    # -- Transactions: Production Batches ----------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS production_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            batch_size REAL NOT NULL,
            production_date TEXT DEFAULT CURRENT_TIMESTAMP,
            expiration_date TEXT,
            batch_notes TEXT,
            produced_by TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_batch_product ON production_batches(product_id)")

    # -- Invoices ----------------------------------------------------------
    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_reconciled ON invoices(reconciled)")

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_line_items(invoice_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoice_line_items_invoice ON invoice_line_items(invoice_id)")

    # -- Purchase Orders ---------------------------------------------------
    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(po_number)")

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_po_line_items_po ON po_line_items(po_id)")

    # -- Reconciliation Log ------------------------------------------------
    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recon_log_invoice ON reconciliation_log(invoice_id)")

    # -- Inventory Counts --------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory_counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            count_number TEXT UNIQUE NOT NULL,
            count_date TEXT NOT NULL,
            counted_by TEXT,
            notes TEXT,
            reconciled TEXT DEFAULT 'NO',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS count_line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            count_id INTEGER NOT NULL,
            ingredient_code TEXT NOT NULL,
            ingredient_name TEXT NOT NULL,
            quantity_counted REAL NOT NULL,
            quantity_expected REAL,
            variance REAL,
            unit_of_measure TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (count_id) REFERENCES inventory_counts(id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_count_line_items_count_id ON count_line_items(count_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_count_line_items_ingredient_code ON count_line_items(ingredient_code)")

    # -- Audit Log ---------------------------------------------------------
    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_action_type ON audit_log(action_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id)")

    # -- Analytics: Widgets ------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analytics_widgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            widget_key TEXT UNIQUE NOT NULL,
            widget_name TEXT NOT NULL,
            widget_type TEXT NOT NULL,
            chart_type TEXT,
            category TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            default_enabled INTEGER DEFAULT 1,
            requires_recipe_data INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            size TEXT DEFAULT 'medium'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_widget_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            widget_key TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            position INTEGER,
            size TEXT DEFAULT 'medium',
            custom_settings TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (widget_key) REFERENCES analytics_widgets(widget_key)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS widget_data_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            widget_key TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            data TEXT NOT NULL,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_widget_cache ON widget_data_cache(widget_key, cache_key, expires_at)")

    # -- Barcode Support ---------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS barcode_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT NOT NULL,
            data_source TEXT NOT NULL,
            product_name TEXT,
            brand TEXT,
            category TEXT,
            unit_of_measure TEXT,
            quantity TEXT,
            image_url TEXT,
            raw_data TEXT,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(barcode, data_source)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_barcode_cache_barcode ON barcode_cache(barcode)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_barcode_cache_source ON barcode_cache(data_source)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS barcode_api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_name TEXT NOT NULL,
            request_date TEXT NOT NULL,
            request_count INTEGER DEFAULT 1,
            UNIQUE(api_name, request_date)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_barcode_api_usage_date ON barcode_api_usage(api_name, request_date)")

    # -- HR: Employees -----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            user_id INTEGER,
            employee_code TEXT UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            position TEXT,
            department TEXT,
            hire_date DATE,
            hourly_rate REAL DEFAULT 0,
            salary REAL DEFAULT 0,
            employment_type TEXT DEFAULT 'full-time',
            status TEXT DEFAULT 'active',
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            profile_picture TEXT,
            pto_hours_available REAL DEFAULT 80.0,
            pto_hours_used REAL DEFAULT 0.0,
            pto_accrual_rate REAL DEFAULT 0.0385,
            pto_last_accrual_date DATE,
            job_classification TEXT DEFAULT 'Front',
            bank_account_number TEXT,
            bank_routing_number TEXT,
            receives_tips INTEGER DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_employees_user_id ON employees(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_employees_code ON employees(employee_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status)")

    # -- HR: Attendance ----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            user_id INTEGER,
            clock_in TIMESTAMP,
            clock_out TIMESTAMP,
            break_start TIMESTAMP,
            break_end TIMESTAMP,
            total_hours REAL DEFAULT 0,
            break_duration INTEGER DEFAULT 0,
            status TEXT DEFAULT 'clocked_out',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cc_tips REAL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (organization_id) REFERENCES organizations(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(clock_in)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_status ON attendance(status)")

    # -- HR: Schedules -----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            shift_type TEXT DEFAULT 'regular',
            position TEXT,
            notes TEXT,
            break_duration INTEGER DEFAULT 30,
            status TEXT DEFAULT 'scheduled',
            change_requested_by INTEGER,
            change_request_reason TEXT,
            change_request_status TEXT,
            change_request_date TIMESTAMP,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (updated_by) REFERENCES users(id),
            FOREIGN KEY (change_requested_by) REFERENCES employees(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_employee ON schedules(employee_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_org_date ON schedules(organization_id, date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_status ON schedules(status)")

    # -- HR: Time Off Requests ---------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS time_off_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            request_type TEXT NOT NULL,
            total_hours REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            reason TEXT,
            admin_notes TEXT,
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_time_off_employee ON time_off_requests(employee_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_time_off_status ON time_off_requests(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_time_off_dates ON time_off_requests(start_date, end_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_time_off_org ON time_off_requests(organization_id)")

    # -- HR: Employee Availability -----------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employee_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            effective_from DATE,
            effective_until DATE,
            availability_type TEXT DEFAULT 'recurring',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_availability_employee ON employee_availability(employee_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_availability_day ON employee_availability(day_of_week)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_availability_org ON employee_availability(organization_id)")

    # -- Payroll: History --------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payroll_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            pay_period_start DATE NOT NULL,
            pay_period_end DATE NOT NULL,
            pay_period_type TEXT NOT NULL DEFAULT 'weekly',
            hourly_rate_used REAL DEFAULT 0,
            salary_used REAL DEFAULT 0,
            total_hours REAL DEFAULT 0,
            regular_hours REAL DEFAULT 0,
            ot_hours REAL DEFAULT 0,
            regular_wage REAL DEFAULT 0,
            ot_wage REAL DEFAULT 0,
            tips REAL DEFAULT 0,
            gross_pay REAL DEFAULT 0,
            job_classification TEXT,
            position TEXT,
            notes TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_by INTEGER,
            UNIQUE(organization_id, employee_id, pay_period_start, pay_period_end)
        )
    """)

    # -- POS: Orders -----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL,
            order_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            employee_id INTEGER,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            customer_address TEXT,
            delivery_distance REAL,
            delivery_fee REAL DEFAULT 0,
            subtotal REAL NOT NULL,
            tax_rate REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            tip_amount REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            discount_reason TEXT,
            total REAL NOT NULL,
            notes TEXT,
            estimated_ready_time DATETIME,
            actual_ready_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            voided_at DATETIME,
            voided_by INTEGER,
            void_reason TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            modifiers TEXT,
            line_total REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            amount REAL NOT NULL,
            tip_amount REAL DEFAULT 0,
            stripe_payment_intent_id TEXT,
            stripe_charge_id TEXT,
            card_last_four TEXT,
            cash_tendered REAL,
            change_given REAL,
            status TEXT DEFAULT 'completed',
            refund_amount REAL DEFAULT 0,
            refund_reason TEXT,
            refunded_at DATETIME,
            refunded_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_payments_order ON order_payments(order_id)")

    # 86 Groups — batch 86/un-86 by named group
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pos_86_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'custom',
            source_category TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pos_86_group_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            FOREIGN KEY (group_id) REFERENCES pos_86_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(group_id, product_id)
        )
    """)

    # POS Settings — org-level key/value, replaces localStorage
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pos_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL UNIQUE,
            setting_value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER
        )
    """)

    # Register sessions — shift-level cash accountability
    cur.execute("""
        CREATE TABLE IF NOT EXISTS register_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME,
            opening_cash REAL NOT NULL,
            closing_cash REAL,
            expected_cash REAL,
            cash_variance REAL,
            total_sales REAL DEFAULT 0,
            total_cash_sales REAL DEFAULT 0,
            total_card_sales REAL DEFAULT 0,
            total_tips REAL DEFAULT 0,
            total_refunds REAL DEFAULT 0,
            order_count INTEGER DEFAULT 0,
            notes TEXT
        )
    """)

    # Customer profiles — repeat customer recognition
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT UNIQUE,
            email TEXT,
            address TEXT,
            notes TEXT,
            first_order_at DATETIME,
            last_order_at DATETIME,
            total_orders INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone)")

    # -- Register sessions: terminal-based (not employee-based) ----------
    _ensure_column(cur, 'register_sessions', 'register_number', 'INTEGER NOT NULL DEFAULT 1')
    _ensure_column(cur, 'register_sessions', 'opened_by', 'INTEGER')
    _ensure_column(cur, 'register_sessions', 'closed_by', 'INTEGER')
    # Backfill opened_by from employee_id for existing rows
    try:
        cur.execute("UPDATE register_sessions SET opened_by = employee_id WHERE opened_by IS NULL AND employee_id IS NOT NULL")
    except Exception:
        pass
    # Explicit FK: orders → register_sessions
    _ensure_column(cur, 'orders', 'register_session_id', 'INTEGER')
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_register_session ON orders(register_session_id)")

    # -- Storefront: orders/order_items column extensions ----------------
    _ensure_column(cur, 'orders', 'source', "TEXT DEFAULT 'pos'")
    _ensure_column(cur, 'orders', 'online_tracking_token', 'TEXT')
    _ensure_column(cur, 'orders', 'scheduled_for', 'DATETIME')
    _ensure_column(cur, 'orders', 'customer_id', 'INTEGER')
    _ensure_column(cur, 'order_items', 'menu_item_id', 'INTEGER')
    _ensure_column(cur, 'order_items', 'size_name', 'TEXT')
    _ensure_column(cur, 'order_items', 'special_instructions', 'TEXT')
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_tracking ON orders(online_tracking_token)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_source ON orders(source)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")

    # -- Delivery: order extensions + routes + driver flag -----------------
    _ensure_column(cur, 'orders', 'customer_lat', 'REAL')
    _ensure_column(cur, 'orders', 'customer_lng', 'REAL')
    _ensure_column(cur, 'orders', 'driver_id', 'INTEGER')
    _ensure_column(cur, 'orders', 'dispatched_at', 'DATETIME')
    _ensure_column(cur, 'orders', 'delivered_at', 'DATETIME')
    _ensure_column(cur, 'orders', 'delivery_route_id', 'INTEGER')
    _ensure_column(cur, 'employees', 'is_driver', 'INTEGER DEFAULT 0')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS delivery_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            stops TEXT NOT NULL,
            estimated_duration_min REAL,
            actual_duration_min REAL,
            started_at DATETIME,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_delivery_routes_status ON delivery_routes(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_delivery_routes_driver ON delivery_routes(driver_id)")

    # -- Storefront: Business Hours --------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS business_hours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            open_time TEXT NOT NULL,
            close_time TEXT NOT NULL,
            is_closed BOOLEAN DEFAULT 0,
            UNIQUE(day_of_week)
        )
    """)

    # -- Storefront: Menu Categories -------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            icon TEXT,
            display_order INTEGER DEFAULT 0,
            parent_category_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_category_id) REFERENCES menu_categories(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_categories_slug ON menu_categories(slug)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_categories_order ON menu_categories(display_order)")

    # -- Storefront: Menu Items ------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            dietary_tags TEXT,
            is_popular BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            display_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES menu_categories(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_category ON menu_items(category_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_slug ON menu_items(slug)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_popular ON menu_items(is_popular)")

    # -- Storefront: Menu Item Sizes -------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_item_sizes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_item_id INTEGER NOT NULL,
            size_name TEXT NOT NULL,
            size_code TEXT NOT NULL,
            price REAL NOT NULL,
            is_default BOOLEAN DEFAULT 0,
            product_id INTEGER,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_item_sizes_item ON menu_item_sizes(menu_item_id)")

    # -- Storefront: Modifier Groups -------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_modifier_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            selection_type TEXT NOT NULL DEFAULT 'multiple',
            min_selections INTEGER DEFAULT 0,
            max_selections INTEGER DEFAULT 10,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -- Storefront: Modifiers -------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_modifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            default_price REAL DEFAULT 0,
            ingredient_id INTEGER,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (group_id) REFERENCES menu_modifier_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_modifiers_group ON menu_modifiers(group_id)")

    # -- Storefront: Per-Size Modifier Prices ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_modifier_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modifier_id INTEGER NOT NULL,
            size_id INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (modifier_id) REFERENCES menu_modifiers(id) ON DELETE CASCADE,
            FOREIGN KEY (size_id) REFERENCES menu_item_sizes(id) ON DELETE CASCADE,
            UNIQUE(modifier_id, size_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_modifier_prices_mod ON menu_modifier_prices(modifier_id)")

    # -- Storefront: Item ↔ Modifier Group Junction ----------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_item_modifier_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_item_id INTEGER NOT NULL,
            modifier_group_id INTEGER NOT NULL,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE,
            FOREIGN KEY (modifier_group_id) REFERENCES menu_modifier_groups(id) ON DELETE CASCADE,
            UNIQUE(menu_item_id, modifier_group_id)
        )
    """)

    # -- Storefront: Order Item Modifiers --------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_item_modifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_item_id INTEGER NOT NULL,
            modifier_id INTEGER,
            modifier_name TEXT NOT NULL,
            price REAL DEFAULT 0,
            FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_item_mods_item ON order_item_modifiers(order_item_id)")

    # -- Converter: File History ----------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS converter_file_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_type TEXT NOT NULL,
            file_category TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filepath TEXT NOT NULL,
            file_size_bytes INTEGER,
            month_year TEXT,
            file_hash TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_converter_fh_month ON converter_file_history(month_year)")

    # -- Converter: MOR Generation Log ----------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS converter_mor_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year TEXT NOT NULL UNIQUE,
            report_date TEXT,
            line_19_opening_balance REAL,
            line_20_receipts REAL,
            line_21_disbursements REAL,
            line_22_net_cash_flow REAL,
            line_23_ending_balance REAL,
            proj_receipts REAL,
            proj_disbursements REAL,
            proj_net REAL,
            employees_current TEXT,
            prof_fees_cumulative REAL,
            responsible_party TEXT,
            bank_statement_file_id INTEGER,
            exhibit_c_file_id INTEGER,
            exhibit_d_file_id INTEGER,
            mor_file_id INTEGER,
            verification_deposits_ok INTEGER DEFAULT 1,
            verification_withdrawals_ok INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_converter_mor_month ON converter_mor_log(month_year)")

    # -- Schema Migrations Tracking ------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT
        )
    """)

    # ------------------------------------------------------------------
    #  VIEWS  (9 views)
    # ------------------------------------------------------------------

    cur.execute("""
        CREATE VIEW IF NOT EXISTS ingredient_inventory_value AS
        SELECT ingredient_code, ingredient_name, category, quantity_on_hand, unit_of_measure, unit_cost,
            (quantity_on_hand * unit_cost) as total_value, supplier_name, reorder_level
        FROM ingredients ORDER BY category, ingredient_name
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS low_stock_ingredients AS
        SELECT ingredient_code, ingredient_name, quantity_on_hand, unit_of_measure,
            reorder_level, reorder_quantity, supplier_name
        FROM ingredients WHERE quantity_on_hand <= reorder_level ORDER BY category, ingredient_name
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS recipe_costs AS
        SELECT p.product_code, p.product_name, i.ingredient_name, r.quantity_needed,
            r.unit_of_measure, i.unit_cost,
            (r.quantity_needed * i.unit_cost) as ingredient_cost
        FROM recipes r JOIN products p ON r.product_id = p.id JOIN ingredients i ON r.ingredient_id = i.id
        ORDER BY p.product_name, i.ingredient_name
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS inventory_aggregated AS
        SELECT ingredient_name, category, unit_of_measure,
            SUM(quantity_on_hand) as total_quantity,
            AVG(unit_cost) as avg_unit_cost,
            SUM(quantity_on_hand * unit_cost) as total_value,
            COUNT(*) as brand_count,
            GROUP_CONCAT(DISTINCT brand) as brands,
            GROUP_CONCAT(DISTINCT supplier_name) as suppliers
        FROM ingredients GROUP BY ingredient_name, category, unit_of_measure
        ORDER BY category, ingredient_name
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS inventory_detailed AS
        SELECT ingredient_code, ingredient_name, brand, supplier_name, category,
            quantity_on_hand, unit_of_measure, unit_cost,
            (quantity_on_hand * unit_cost) as total_value,
            storage_location, reorder_level, date_received, lot_number, expiration_date
        FROM ingredients ORDER BY ingredient_name, brand, supplier_name
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS unreconciled_invoices AS
        SELECT * FROM invoices WHERE reconciled = 0
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS supplier_list AS
        SELECT DISTINCT supplier_name FROM ingredients
        WHERE supplier_name IS NOT NULL ORDER BY supplier_name
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS brand_list AS
        SELECT DISTINCT brand FROM ingredients
        WHERE brand IS NOT NULL ORDER BY brand
    """)

    cur.execute("""
        CREATE VIEW IF NOT EXISTS ingredient_clusters AS
        SELECT DISTINCT ingredient_name, category, unit_of_measure
        FROM ingredients ORDER BY category, ingredient_name
    """)

    # ------------------------------------------------------------------
    conn.commit()
    conn.close()

    if not already_existed:
        print(f"   Created org database with full schema: {new_db_path}")
    else:
        print(f"   Schema verified/updated: {new_db_path}")

    return new_db_path


# ===========================================================================
#  Utility helpers
# ===========================================================================

def list_organization_databases():
    """List all organization database files."""
    if not os.path.exists(DATABASES_DIR):
        return []

    return [
        f for f in os.listdir(DATABASES_DIR)
        if f.endswith('.db') and f.startswith('org_')
    ]


def backup_org_database(organization_id, backup_dir=None):
    """
    Create backup of organization's database.

    Args:
        organization_id: Organization ID.
        backup_dir: Optional backup directory (default: backups/).

    Returns:
        Path to backup file.
    """
    if backup_dir is None:
        backup_dir = os.path.join(BASE_DIR, 'backups')

    os.makedirs(backup_dir, exist_ok=True)

    org_db_path = get_org_db_path(organization_id)
    if not org_db_path or not os.path.exists(org_db_path):
        raise FileNotFoundError("Organization database not found")

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"org_{organization_id}_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    shutil.copy2(org_db_path, backup_path)

    return backup_path
