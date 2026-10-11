"""Shared frontend budget; docs/performance/2026-10-11-sentry-quota.md."""

import sqlite3
from datetime import UTC, datetime, timedelta

from db_methods.pwa.connection import PwaConnectionFactory
from db_methods.pwa.sentry_budget import (
    admission_counts,
    prune_admissions,
    record_admission,
)


LIMITS = {"query": (3, 100), "error": (30, 900)}


async def admit_frontend_event(
    factory: PwaConnectionFactory,
    *,
    lane: str,
    signature: str,
    now: datetime | None = None,
) -> str:
    """Reserve one event atomically; lost deliveries still consume reservation."""

    if lane not in LIMITS:
        raise ValueError("Unknown frontend Sentry lane")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    timestamp = current.isoformat(timespec="milliseconds")
    day_cutoff = (current - timedelta(days=1)).isoformat(timespec="milliseconds")
    period_cutoff = (current - timedelta(days=32)).isoformat(timespec="milliseconds")
    daily_limit, period_limit = LIMITS[lane]

    def reserve(connection: sqlite3.Connection) -> str:
        prune_admissions(connection, period_cutoff)
        period_count, day_count, repeated = admission_counts(
            connection, lane=lane, signature=signature, day_cutoff=day_cutoff,
        )
        if repeated:
            return "repeat"
        if period_count >= period_limit or day_count >= daily_limit:
            return "budget"
        record_admission(connection, lane=lane, signature=signature, occurred_at=timestamp)
        return "admitted"

    return await factory.run_write_async(reserve)
