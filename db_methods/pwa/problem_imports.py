"""Small SQLite operations used by the problem workbook import."""

from __future__ import annotations

import sqlite3


PROBLEM_FIELDS = (
    "group_id",
    "lesson",
    "prob",
    "item",
    "title",
    "prob_text",
    "prob_type",
    "ans_type",
    "ans_validation",
    "validation_error",
    "cor_ans",
    "cor_ans_checker",
    "wrong_ans",
    "congrat",
)


def find_course(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT id, public_id, code, name, status FROM courses WHERE public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_course_groups(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT group_id, public_id, short_code, public_name, status "
        "FROM groups WHERE course_id = ? ORDER BY sort_order, group_id",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_course_problems(
    connection: sqlite3.Connection, *, course_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT problem.* FROM problems AS problem "
        "JOIN groups AS group_record ON group_record.group_id = problem.group_id "
        "WHERE group_record.course_id = ?",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def find_problem(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM problems WHERE public_id = ?", (public_id,)
    ).fetchone()
    return None if row is None else dict(row)


def insert_problem(
    connection: sqlite3.Connection, values: dict[str, object]
) -> dict[str, object]:
    placeholders = ", ".join("?" for _field in PROBLEM_FIELDS)
    cursor = connection.execute(
        f"INSERT INTO problems ({', '.join(PROBLEM_FIELDS)}) VALUES ({placeholders})",
        tuple(values[field] for field in PROBLEM_FIELDS),
    )
    row = connection.execute(
        "SELECT * FROM problems WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    assert row is not None
    return dict(row)


def update_problem(
    connection: sqlite3.Connection,
    *,
    problem_id: int,
    values: dict[str, object],
) -> None:
    assignments = ", ".join(f"{field} = ?" for field in PROBLEM_FIELDS)
    connection.execute(
        f"UPDATE problems SET {assignments} WHERE id = ?",
        (*tuple(values[field] for field in PROBLEM_FIELDS), problem_id),
    )


def delete_problem(connection: sqlite3.Connection, *, problem_id: int) -> None:
    connection.execute("DELETE FROM problems WHERE id = ?", (problem_id,))


def find_import_receipt_by_preview(
    connection: sqlite3.Connection,
    *,
    course_id: int,
    source_sha256: str,
    preview_sha256: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM problem_import_receipts "
        "WHERE course_id = ? AND source_sha256 = ? AND preview_sha256 = ?",
        (course_id, source_sha256, preview_sha256),
    ).fetchone()
    return None if row is None else dict(row)


def get_import_receipt(
    connection: sqlite3.Connection, *, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM problem_import_receipts WHERE public_id = ?", (public_id,)
    ).fetchone()
    return None if row is None else dict(row)


def insert_import_receipt(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    course_id: int,
    source_filename: str,
    source_sha256: str,
    preview_sha256: str,
    summary_json: str,
    changes_json: str,
    actor_user_id: int,
    applied_at: str,
) -> None:
    connection.execute(
        "INSERT INTO problem_import_receipts "
        "(public_id, course_id, source_filename, source_sha256, preview_sha256, state, "
        "summary_json, changes_json, applied_by_user_id, applied_at) "
        "VALUES (?, ?, ?, ?, ?, 'applied', ?, ?, ?, ?)",
        (
            public_id,
            course_id,
            source_filename,
            source_sha256,
            preview_sha256,
            summary_json,
            changes_json,
            actor_user_id,
            applied_at,
        ),
    )


def mark_import_rolled_back(
    connection: sqlite3.Connection,
    *,
    receipt_id: int,
    expected_version: int,
    actor_user_id: int,
    rolled_back_at: str,
) -> bool:
    cursor = connection.execute(
        "UPDATE problem_import_receipts SET state = 'rolled_back', "
        "rolled_back_by_user_id = ?, rolled_back_at = ?, version = version + 1 "
        "WHERE id = ? AND state = 'applied' AND version = ?",
        (actor_user_id, rolled_back_at, receipt_id, expected_version),
    )
    return cursor.rowcount == 1


__all__ = [
    "PROBLEM_FIELDS",
    "delete_problem",
    "find_course",
    "find_import_receipt_by_preview",
    "find_problem",
    "get_import_receipt",
    "insert_import_receipt",
    "insert_problem",
    "list_course_groups",
    "list_course_problems",
    "mark_import_rolled_back",
    "update_problem",
]
