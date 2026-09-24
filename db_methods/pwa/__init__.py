"""Persistence infrastructure shared by the PWA adapters and domain services."""

from .connection import (
    BusyRetryExhausted,
    JournalModeMismatchError,
    PwaConnectionFactory,
    SqliteConcurrencyPolicy,
)
from .product_analytics import ProductAnalyticsConnectionFactory
from .migrations import (
    MigrationState,
    SchemaMismatchError,
    apply_schema_migrations,
    inspect_migration_state,
    require_current_schema,
)
from .runtime_lock import (
    DatabaseLifecycleBusyError,
    DatabaseLifecycleLock,
    DatabaseLifecycleLockMode,
    lifecycle_lock_path,
    maintenance_database_lock,
    runtime_database_lock,
)

__all__ = [
    "BusyRetryExhausted",
    "DatabaseLifecycleBusyError",
    "DatabaseLifecycleLock",
    "DatabaseLifecycleLockMode",
    "JournalModeMismatchError",
    "MigrationState",
    "PwaConnectionFactory",
    "ProductAnalyticsConnectionFactory",
    "SchemaMismatchError",
    "SqliteConcurrencyPolicy",
    "apply_schema_migrations",
    "inspect_migration_state",
    "lifecycle_lock_path",
    "maintenance_database_lock",
    "require_current_schema",
    "runtime_database_lock",
]
