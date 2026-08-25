"""Small SQLite operations for the one-time classroom Excel import."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection


def existing_user_ids(
    connection: sqlite3.Connection, user_ids: Collection[int]
) -> set[int]:
    if not user_ids:
        return set()
    placeholders = ", ".join("?" for _value in user_ids)
    return {
        int(row[0])
        for row in connection.execute(
            f"SELECT id FROM users WHERE id IN ({placeholders})", tuple(user_ids)
        )
    }


def find_import_receipt(
    connection: sqlite3.Connection, event_id: int
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT receipt.public_id, receipt.source_sha256, receipt.preview_sha256, "
        "receipt.source_sheet, receipt.source_row_count, receipt.classroom_count, "
        "receipt.assignment_count, receipt.applied_at, "
        "layout.public_id AS layout_public_id, plan.public_id AS plan_public_id "
        "FROM classroom_import_receipts receipt "
        "JOIN classroom_layout_versions layout ON layout.id = receipt.layout_version_id "
        "JOIN classroom_assignment_plans plan ON plan.id = receipt.assignment_plan_id "
        "WHERE receipt.in_person_event_id = ?",
        (event_id,),
    ).fetchone()
    return None if row is None else dict(row)


def insert_import_receipt(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    source_sha256: str,
    preview_sha256: str,
    source_sheet: str,
    source_row_count: int,
    classroom_count: int,
    assignment_count: int,
    layout_id: int,
    plan_id: int,
    actor_user_id: int,
    applied_at: str,
) -> None:
    connection.execute(
        "INSERT INTO classroom_import_receipts "
        "(in_person_event_id, source_sha256, preview_sha256, "
        "source_sheet, source_row_count, classroom_count, assignment_count, "
        "layout_version_id, assignment_plan_id, actor_user_id, applied_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id,
            source_sha256,
            preview_sha256,
            source_sheet,
            source_row_count,
            classroom_count,
            assignment_count,
            layout_id,
            plan_id,
            actor_user_id,
            applied_at,
        ),
    )


__all__ = ["existing_user_ids", "find_import_receipt", "insert_import_receipt"]
