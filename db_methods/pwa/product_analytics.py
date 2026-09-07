"""Small, isolated SQLite store for best-effort PWA product analytics.

It deliberately has no foreign keys to the teaching database.  Analytics must
remain writable (or safely droppable) while the primary database is busy or
under maintenance; account names are resolved only when Staff reads a report.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .connection import PwaConnectionFactory, SqliteConcurrencyPolicy


ANALYTICS_SCHEMA_VERSION = 1


class ProductAnalyticsConnectionFactory(PwaConnectionFactory):
    """PWA connection policy with a self-contained analytics schema and WAL."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        policy: SqliteConcurrencyPolicy | None = None,
    ) -> None:
        # PwaConnectionFactory's operation and busy handling is exactly what
        # this database needs, but its schema preflight targets the teaching DB.
        super().__init__(database_path, policy=policy, verify_schema=False)
        self._initialize_schema()
        self._require_wal_mode()

    def _initialize_schema(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path, autocommit=True) as connection:
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).casefold() != "wal":
                raise RuntimeError("Could not enable WAL for product analytics")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS analytics_schema "
                "(version INTEGER NOT NULL)"
            )
            row = connection.execute("SELECT version FROM analytics_schema").fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO analytics_schema (version) VALUES (?)",
                    (ANALYTICS_SCHEMA_VERSION,),
                )
            elif int(row[0]) != ANALYTICS_SCHEMA_VERSION:
                raise RuntimeError("Unsupported product analytics schema version")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS product_events ("
                "id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, "
                "audience TEXT NOT NULL, account_public_id TEXT NOT NULL, "
                "session_public_id TEXT NOT NULL, event_type TEXT NOT NULL, "
                "route_id TEXT NOT NULL, entity_type TEXT, entity_public_id TEXT, "
                "viewport_width INTEGER NOT NULL, viewport_height INTEGER NOT NULL, "
                "device_pixel_ratio REAL NOT NULL, pointer_type TEXT NOT NULL, "
                "display_mode TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS product_events_occurred_idx "
                "ON product_events (occurred_at DESC, id DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS product_events_account_idx "
                "ON product_events (account_public_id, occurred_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS product_events_filter_idx "
                "ON product_events (audience, event_type, occurred_at DESC)"
            )


def utc_now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def school_year_cutoff(now: datetime) -> datetime:
    """Start of the current school-year retention window (10 Aug, Moscow)."""

    from zoneinfo import ZoneInfo

    moscow = now.astimezone(ZoneInfo("Europe/Moscow"))
    year = moscow.year if (moscow.month, moscow.day) >= (8, 10) else moscow.year - 1
    return datetime(year, 8, 10, tzinfo=ZoneInfo("Europe/Moscow")).astimezone(UTC)


def prune_expired_events(connection: sqlite3.Connection, *, now: datetime) -> int:
    cutoff = school_year_cutoff(now).isoformat(timespec="milliseconds")
    result = connection.execute("DELETE FROM product_events WHERE occurred_at < ?", (cutoff,))
    return int(result.rowcount)


__all__ = [
    "ProductAnalyticsConnectionFactory",
    "prune_expired_events",
    "school_year_cutoff",
    "utc_now_text",
]
