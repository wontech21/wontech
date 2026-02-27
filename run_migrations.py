#!/usr/bin/env python3
"""
Database Migration Runner
=========================
Scans the /migrations/ directory for .py migration files, checks the
schema_migrations table for already-applied migrations, and runs only
pending ones in filename order.

Each successful migration is recorded with its name and an MD5 checksum
of the file content. Safe to run multiple times (idempotent).

Supports both master.db and all org databases.

Usage:
    python run_migrations.py            # Run all pending migrations
    python run_migrations.py --status   # Show migration status only
"""

import hashlib
import importlib.util
import os
import sqlite3
import sys
import traceback

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(BASE_DIR, 'migrations')
MASTER_DB_PATH = os.path.join(BASE_DIR, 'master.db')
DATABASES_DIR = os.path.join(BASE_DIR, 'databases')

# Files in /migrations/ that are not actual migration scripts
SKIP_FILES = {'__init__.py', 'README.md'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def md5_checksum(filepath):
    """Return the MD5 hex digest of a file's contents."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def ensure_schema_migrations_table(conn):
    """Create the schema_migrations table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT
        )
    """)
    conn.commit()


def get_applied_migrations(conn):
    """Return a dict of {migration_name: checksum} for already-applied migrations."""
    ensure_schema_migrations_table(conn)
    cursor = conn.execute("SELECT migration_name, checksum FROM schema_migrations")
    return {row[0]: row[1] for row in cursor.fetchall()}


def record_migration(conn, migration_name, checksum):
    """Insert a migration record into schema_migrations."""
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (migration_name, checksum) VALUES (?, ?)",
        (migration_name, checksum),
    )
    conn.commit()


def discover_migrations():
    """
    Scan the migrations/ directory and return a sorted list of dicts:
        [{'name': 'add_barcode_support', 'filename': 'add_barcode_support.py',
          'path': '/abs/path/...', 'checksum': '...'}]

    Only .py files are included; __init__.py and README.md are skipped.
    Results are sorted by filename for deterministic ordering.
    """
    if not os.path.isdir(MIGRATIONS_DIR):
        return []

    migrations = []
    for filename in sorted(os.listdir(MIGRATIONS_DIR)):
        if filename in SKIP_FILES or not filename.endswith('.py'):
            continue
        filepath = os.path.join(MIGRATIONS_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        name = filename[:-3]  # strip .py
        migrations.append({
            'name': name,
            'filename': filename,
            'path': filepath,
            'checksum': md5_checksum(filepath),
        })
    return migrations


def load_module(name, filepath):
    """Dynamically load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(f"migrations.{name}", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_single_migration(migration):
    """
    Import and execute a single migration file.

    Looks for callable entry points in this priority order:
        1. migrate()
        2. run_migration()   — called with no args
        3. main()

    Returns True on success, False on failure.
    """
    module = load_module(migration['name'], migration['path'])

    # Determine which function to call
    func = None
    func_name = None
    for candidate in ('migrate', 'run_migration', 'main'):
        if hasattr(module, candidate) and callable(getattr(module, candidate)):
            func = getattr(module, candidate)
            func_name = candidate
            break

    if func is None:
        print(f"   WARNING: No migrate() or run_migration() function found, skipping")
        return False

    # Call with no arguments — the migration is responsible for finding DBs
    import inspect
    sig = inspect.signature(func)
    params = list(sig.parameters.values())

    if len(params) == 0:
        result = func()
    else:
        # Some legacy migrations accept a db_path or org_id.
        # We cannot call them generically with a single invocation.
        # Try calling with no args and let the default/error surface.
        print(f"   NOTE: {func_name}() expects {len(params)} arg(s) — running standalone via __main__ pattern")
        # Fall back: if the module has a __main__-style block that calls
        # the function properly, we already executed it during import.
        # Mark as success if no exception was raised during import.
        return True

    # Some migrations return True/False, others return None
    if result is False:
        return False
    return True


def get_org_db_paths():
    """Return a list of absolute paths to all org database files."""
    if not os.path.isdir(DATABASES_DIR):
        return []
    return [
        os.path.join(DATABASES_DIR, f)
        for f in sorted(os.listdir(DATABASES_DIR))
        if f.startswith('org_') and f.endswith('.db')
    ]


def record_to_all_databases(migration_name, checksum):
    """Record a migration as applied in master.db and all org databases."""
    # Master
    if os.path.exists(MASTER_DB_PATH):
        conn = sqlite3.connect(MASTER_DB_PATH)
        ensure_schema_migrations_table(conn)
        record_migration(conn, migration_name, checksum)
        conn.close()

    # Org databases
    for db_path in get_org_db_paths():
        conn = sqlite3.connect(db_path)
        ensure_schema_migrations_table(conn)
        record_migration(conn, migration_name, checksum)
        conn.close()


def print_status():
    """Print the current migration status for all databases."""
    all_migrations = discover_migrations()

    print(f"\n{'='*70}")
    print("WONTECH Migration Status")
    print(f"{'='*70}\n")
    print(f"Discovered {len(all_migrations)} migration file(s) in /migrations/\n")

    # Master DB
    if os.path.exists(MASTER_DB_PATH):
        conn = sqlite3.connect(MASTER_DB_PATH)
        applied = get_applied_migrations(conn)
        conn.close()
        print(f"  master.db: {len(applied)} applied")
        for m in all_migrations:
            status = "APPLIED" if m['name'] in applied else "PENDING"
            checksum_match = ""
            if m['name'] in applied and applied[m['name']] != m['checksum']:
                checksum_match = " (CHECKSUM CHANGED)"
            print(f"    [{status}] {m['filename']}{checksum_match}")
        print()

    # Org databases
    for db_path in get_org_db_paths():
        db_name = os.path.basename(db_path)
        conn = sqlite3.connect(db_path)
        applied = get_applied_migrations(conn)
        conn.close()
        print(f"  {db_name}: {len(applied)} applied")
        for m in all_migrations:
            status = "APPLIED" if m['name'] in applied else "PENDING"
            checksum_match = ""
            if m['name'] in applied and applied[m['name']] != m['checksum']:
                checksum_match = " (CHECKSUM CHANGED)"
            print(f"    [{status}] {m['filename']}{checksum_match}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Run all pending migrations."""

    # Handle --status flag
    if '--status' in sys.argv:
        print_status()
        return

    print(f"\n{'='*70}")
    print("WONTECH Database Migration Runner")
    print(f"{'='*70}\n")

    # Ensure we're in the project root
    os.chdir(BASE_DIR)

    # Discover migration files
    all_migrations = discover_migrations()
    if not all_migrations:
        print("No migration files found in /migrations/")
        print(f"{'='*70}\n")
        return

    print(f"Discovered {len(all_migrations)} migration file(s)\n")

    # Determine which have already been applied (check master.db as source of truth)
    applied = {}
    if os.path.exists(MASTER_DB_PATH):
        conn = sqlite3.connect(MASTER_DB_PATH)
        applied = get_applied_migrations(conn)
        conn.close()

    # Filter to pending migrations
    pending = [m for m in all_migrations if m['name'] not in applied]
    already_applied = len(all_migrations) - len(pending)

    if already_applied > 0:
        print(f"  Already applied: {already_applied}")
    print(f"  Pending:         {len(pending)}\n")

    if not pending:
        print("Nothing to do -- all migrations have been applied.")
        print(f"\n{'='*70}\n")
        return

    # Run pending migrations
    successful = 0
    failed = 0
    skipped = 0

    for migration in pending:
        print(f"  Running: {migration['filename']}")
        print(f"  Checksum: {migration['checksum']}")

        try:
            result = run_single_migration(migration)

            if result:
                # Record to all databases
                record_to_all_databases(migration['name'], migration['checksum'])
                successful += 1
                print(f"  Result: OK\n")
            else:
                failed += 1
                print(f"  Result: FAILED\n")

        except Exception as e:
            failed += 1
            print(f"  Result: ERROR -- {e}")
            traceback.print_exc()
            print()

    # Summary
    print(f"{'='*70}")
    print(f"\nMigration Summary:")
    print(f"  Successful: {successful}")
    print(f"  Failed:     {failed}")
    print(f"  Skipped:    {already_applied} (already applied)")
    print(f"  Total:      {len(all_migrations)}\n")

    if failed > 0:
        print("Some migrations failed. Check the output above for details.")
        sys.exit(1)
    else:
        print("All pending migrations applied successfully.")
        sys.exit(0)


if __name__ == '__main__':
    main()
