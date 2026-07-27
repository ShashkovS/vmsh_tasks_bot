"""Persistence infrastructure shared by the PWA adapters and domain services."""

from .connection import (
    BusyRetryExhausted,
    JournalModeMismatchError,
    PwaConnectionFactory,
    SqliteConcurrencyPolicy,
)
from .migrations import (
    MigrationState,
    SchemaMismatchError,
    apply_schema_migrations,
    inspect_migration_state,
    require_current_schema,
)

__all__ = [
    "BusyRetryExhausted",
    "JournalModeMismatchError",
    "MigrationState",
    "PwaConnectionFactory",
    "SchemaMismatchError",
    "SqliteConcurrencyPolicy",
    "apply_schema_migrations",
    "inspect_migration_state",
    "require_current_schema",
]
