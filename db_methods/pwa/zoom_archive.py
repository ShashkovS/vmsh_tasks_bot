"""Append-only receipt storage; see docs/deploy/tlf-app/README.md and migration 0102."""

import sqlite3


def insert_receipt(
    connection: sqlite3.Connection,
    *,
    received_at: str,
    event_type: str,
    meeting_id: str | None,
    request_id: str | None,
    request_timestamp: str,
    raw_body: bytes,
) -> int:
    # FULL protects acknowledged WAL commits, not only normal process restarts.
    if connection.execute("PRAGMA synchronous").fetchone()["synchronous"] < 2:
        raise RuntimeError("Zoom receipt storage requires synchronous=FULL")
    return connection.execute(
        "INSERT INTO zoom_webhook_receipts "
        "(received_at, event_type, meeting_id, request_id, request_timestamp, raw_body) "
        "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
        (received_at, event_type, meeting_id, request_id, request_timestamp, raw_body),
    ).fetchone()["id"]
