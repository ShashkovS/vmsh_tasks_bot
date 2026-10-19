"""Rollback only 0120 indexes/bookkeeping, preserving all user data."""
import sys
import yoyo
from db_methods.pwa.migrations import MIGRATIONS_ROOT

backend = yoyo.get_backend(f"sqlite:///{sys.argv[1]}")
with backend.lock():
    migrations = backend.to_rollback(yoyo.read_migrations(str(MIGRATIONS_ROOT)))
    backend.rollback_migrations([
        migration for migration in migrations
        if migration.id == "0120.scoped_read_indexes"
    ])
