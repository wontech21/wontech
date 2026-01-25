# Database Migrations

This directory contains database migration scripts for the WONTECH multi-tenant platform.

## Running Migrations

### Run All Migrations
```bash
python3 run_migrations.py
```

### Run Single Migration
```bash
python3 migrations/add_last_password_change.py
```

## Available Migrations

### add_last_password_change.py
- **Date:** 2026-01-25
- **Purpose:** Adds password change tracking for session invalidation
- **Changes:**
  - Adds `last_password_change` TIMESTAMP column to `users` table in master.db
  - Sets default timestamp for existing users

## Migration Best Practices

1. **Idempotent:** All migrations check if changes already exist before applying
2. **Reversible:** Document rollback steps in migration comments
3. **Tested:** Test locally before deploying to production
4. **Logged:** Migrations output detailed status information

## Cloud Deployment

When deploying to cloud:

1. SSH into the server
2. Navigate to the app directory
3. Run: `python3 run_migrations.py`
4. Restart the application

## Creating New Migrations

1. Create a new file in `/migrations/` directory
2. Implement a `run_migration()` function that returns `True` on success
3. Add migration to `run_migrations.py` migrations list
4. Test locally before deploying
