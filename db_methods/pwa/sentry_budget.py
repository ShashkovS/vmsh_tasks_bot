"""Content-free admission ledger; docs/performance/2026-10-11-sentry-quota.md."""

import sqlite3


def prune_admissions(connection: sqlite3.Connection, cutoff: str) -> None:
    connection.execute(
        "DELETE FROM pwa_sentry_admissions WHERE occurred_at <= ?", (cutoff,),
    )


def admission_counts(
    connection: sqlite3.Connection,
    *,
    lane: str,
    signature: str,
    day_cutoff: str,
) -> tuple[int, int, int]:
    row = connection.execute(
        "SELECT count(*) AS period_count, coalesce(sum(occurred_at > ?), 0) AS day_count, "
        "coalesce(sum(signature = ? AND occurred_at > ?), 0) AS signature_count "
        "FROM pwa_sentry_admissions WHERE lane = ?",
        (day_cutoff, signature, day_cutoff, lane),
    ).fetchone()
    return int(row["period_count"]), int(row["day_count"]), int(row["signature_count"])


def record_admission(
    connection: sqlite3.Connection,
    *,
    lane: str,
    signature: str,
    occurred_at: str,
) -> None:
    connection.execute(
        "INSERT INTO pwa_sentry_admissions (occurred_at, lane, signature) VALUES (?, ?, ?)",
        (occurred_at, lane, signature),
    )
