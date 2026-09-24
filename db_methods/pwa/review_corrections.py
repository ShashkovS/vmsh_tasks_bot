"""Mechanical SQLite operations for completed written-review corrections.

Domain policy lives in :mod:`models.pwa.review_corrections`; these helpers only
read and write the rows required by the Phase-6 correction transaction.
"""

from __future__ import annotations

import sqlite3
import hashlib
import json
from datetime import datetime

from helpers.consts import WRITTEN_STATUS


def find_source_review(
    connection: sqlite3.Connection, review_public_id: str
) -> dict[str, object] | None:
    return connection.execute(
        "SELECT review.*, thread.student_user_id, thread.problem_id, "
        "thread.public_id AS thread_public_id, thread.version AS thread_version, "
        "thread.status AS thread_status, thread.updated_at AS thread_updated_at, "
        "problem.public_id AS problem_public_id, problem.group_id, problem.lesson, "
        "groups.public_id AS group_public_id, course.public_id AS course_public_id "
        "FROM submission_reviews AS review "
        "JOIN submission_threads AS thread ON thread.id = review.thread_id "
        "JOIN problems AS problem ON problem.id = thread.problem_id "
        "LEFT JOIN groups ON groups.group_id = problem.group_id "
        "LEFT JOIN courses AS course ON course.id = groups.course_id "
        "WHERE review.public_id = ?",
        (review_public_id,),
    ).fetchone()


def find_replay(
    connection: sqlite3.Connection, reviewer_user_id: int, idempotency_key: str
) -> dict[str, object] | None:
    return connection.execute(
        "SELECT review.*, thread.public_id AS thread_public_id, "
        "problem.public_id AS problem_public_id, "
        "comment.public_id AS comment_public_id "
        "FROM submission_reviews AS review "
        "JOIN submission_threads AS thread ON thread.id = review.thread_id "
        "JOIN problems AS problem ON problem.id = thread.problem_id "
        "LEFT JOIN submission_entries AS comment ON comment.id = review.comment_entry_id "
        "WHERE review.reviewer_user_id = ? AND review.idempotency_key = ?",
        (reviewer_user_id, idempotency_key),
    ).fetchone()


def evidence_scopes(connection, review_id):
    return connection.execute(
        "SELECT DISTINCT groups.public_id AS group_public_id, course.public_id AS course_public_id "
        "FROM submission_review_evidence_entries evidence JOIN problems problem ON problem.id = evidence.problem_id "
        "LEFT JOIN groups ON groups.group_id = problem.group_id LEFT JOIN courses course ON course.id = groups.course_id "
        "WHERE evidence.review_id = ?",
        (review_id,),
    ).fetchall()


def latest_review_public_id(
    connection: sqlite3.Connection, thread_id: int
) -> str | None:
    row = connection.execute(
        "SELECT public_id FROM submission_reviews WHERE thread_id = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (thread_id,),
    ).fetchone()
    return None if row is None else str(row["public_id"])


def invalidate_current_written_results(
    connection: sqlite3.Connection, *, student_user_id: int, problem_id: int
) -> None:
    connection.execute(
        "UPDATE results SET verdict = -2 WHERE student_id = ? AND problem_id = ? "
        "AND res_type = 2 AND verdict > 0",
        (student_user_id, problem_id),
    )


def insert_result(
    connection: sqlite3.Connection,
    *,
    student_user_id: int,
    problem_id: int,
    group_id: str,
    lesson: int,
    reviewer_user_id: int,
    verdict: int,
    created_at: str,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO results "
            "(student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, "
            "answer, res_type) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 2) RETURNING id",
            (
                student_user_id,
                problem_id,
                group_id,
                lesson,
                reviewer_user_id,
                created_at,
                verdict,
            ),
        ).fetchone()["id"]
    )


def insert_comment(
    connection: sqlite3.Connection,
    *,
    thread_id: int,
    author_kind: str,
    author_user_id: int,
    text: str,
    created_at: str,
) -> int:
    return int(
        connection.execute(
            "INSERT INTO submission_entries "
            "(thread_id, author_kind, author_user_id, channel, entry_kind, "
            "state, text, server_received_at, version, locked_at) "
            "VALUES (?, ?, ?, 'staff', 'teacher_comment', 'locked', ?, ?, 1, ?) "
            "RETURNING id",
            (
                thread_id,
                author_kind,
                author_user_id,
                text,
                created_at,
                created_at,
            ),
        ).fetchone()["id"]
    )


def insert_review(
    connection: sqlite3.Connection,
    *,
    source: dict[str, object],
    reviewer_user_id: int,
    verdict: int,
    comment_entry_id: int | None,
    result_id: int,
    idempotency_key: str,
    payload_sha256: str,
    created_at: str,
) -> tuple[int, str]:
    row = connection.execute(
        "INSERT INTO submission_reviews "
        "(thread_id, queue_id, reviewer_user_id, "
        "evidence_through_entry_id, expected_thread_version, verdict, "
        "comment_entry_id, result_id, source, idempotency_key, payload_sha256, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'staff', ?, ?, ?) "
        "RETURNING id, public_id",
        (
            source["thread_id"],
            source["queue_id"],
            reviewer_user_id,
            source["evidence_through_entry_id"],
            source["thread_version"],
            verdict,
            comment_entry_id,
            result_id,
            idempotency_key,
            payload_sha256,
            created_at,
        ),
    ).fetchone()
    return int(row["id"]), str(row["public_id"])


def copy_evidence(
    connection: sqlite3.Connection, *, source_review_id: int, review_id: int
) -> None:
    connection.execute(
        "INSERT INTO submission_review_evidence_entries "
        "(review_id, entry_id, thread_id, problem_id, entry_version, server_received_at) "
        "SELECT ?, entry_id, thread_id, problem_id, entry_version, server_received_at "
        "FROM submission_review_evidence_entries WHERE review_id = ?",
        (review_id, source_review_id),
    )
    connection.execute(
        "INSERT INTO submission_review_evidence_attachments "
        "(review_id, attachment_id, entry_id, asset_id, ordinal) "
        "SELECT ?, attachment_id, entry_id, asset_id, ordinal "
        "FROM submission_review_evidence_attachments WHERE review_id = ?",
        (review_id, source_review_id),
    )


def update_thread_result(
    connection: sqlite3.Connection,
    *,
    thread_id: int,
    result_id: int,
    current_status: str,
    status: str,
    comment_created: bool,
    created_at: str,
) -> None:
    # A correction grades its old evidence, not newer queued submissions.
    pending = connection.execute(
        "SELECT 1 FROM written_tasks_queue AS queue JOIN submission_threads AS thread "
        "ON queue.student_id = thread.student_user_id AND queue.problem_id = thread.problem_id "
        "WHERE thread.id = ? LIMIT 1",
        (thread_id,),
    ).fetchone()
    if pending is not None:
        status = current_status
    if current_status != status:
        # The existing schema deliberately routes every post-review status
        # change through awaiting_review. A correction is one transaction, but
        # it still follows that persisted transition contract.
        connection.execute(
            "UPDATE submission_threads SET status = 'awaiting_review', "
            "updated_at = ?, version = version + 1 WHERE id = ?",
            (created_at, thread_id),
        )
    connection.execute(
        "UPDATE submission_threads SET status = ?, latest_result_id = ?, "
        "latest_entry_at = CASE WHEN ? THEN ? ELSE latest_entry_at END, "
        "updated_at = ?, version = version + 1 WHERE id = ?",
        (status, result_id, comment_created, created_at, created_at, thread_id),
    )


def active_review_owner(connection, source, now: datetime):
    """Read the active holder across the same student's synonym case."""
    return connection.execute(
        "SELECT queue.teacher_id, trim(coalesce(owner.name, '') || ' ' || "
        "coalesce(owner.surname, '')) AS display_name FROM written_tasks_queue AS queue "
        "JOIN users AS owner ON owner.id = queue.teacher_id "
        "WHERE queue.student_id = ? AND queue.cur_status = ? "
        "AND (queue.problem_id = ? OR queue.problem_id IN ("
        "SELECT peer.problem_id FROM problem_synonym_members AS member "
        "JOIN problem_synonym_groups AS synonym ON synonym.id = member.synonym_group_id "
        "JOIN problem_synonym_members AS peer ON peer.synonym_group_id = synonym.id "
        "WHERE member.problem_id = ? AND synonym.status = 'active')) "
        "AND (julianday(queue.lease_expires_at) > julianday(?) OR "
        "(queue.claim_token IS NULL AND julianday(queue.teacher_ts) > julianday(?) - 1.0/48)) "
        "LIMIT 1",
        (
            source["student_user_id"],
            int(WRITTEN_STATUS.BEING_CHECKED),
            source["problem_id"],
            source["problem_id"],
            now.isoformat(),
            now.isoformat(),
        ),
    ).fetchone()


def copy_annotations(connection, source_review_id, review_id, created_at):
    connection.execute(
        "INSERT INTO submission_review_annotations "
        "(review_id, attachment_id, schema_version, rotation, marks_json, payload_sha256, created_at) "
        "SELECT ?, attachment_id, schema_version, rotation, marks_json, payload_sha256, ? "
        "FROM submission_review_annotations WHERE review_id = ?",
        (review_id, created_at, source_review_id),
    )


def read_verdict_mode(connection, course_public_id):
    row = connection.execute(
        "SELECT settings.values_json FROM course_runtime_settings settings "
        "JOIN courses course ON course.id = settings.course_id WHERE course.public_id = ?",
        (course_public_id,),
    ).fetchone()
    return None if row is None else json.loads(row["values_json"])["verdictMode"]


def store_annotations(connection, review_id, annotations, created_at):
    attachments = {
        row["public_id"]: row["id"]
        for row in connection.execute(
            "SELECT attachment.public_id, attachment.id FROM submission_review_evidence_attachments AS evidence "
            "JOIN submission_attachments AS attachment ON attachment.id = evidence.attachment_id "
            "WHERE evidence.review_id = ?",
            (review_id,),
        ).fetchall()
    }
    seen = set()
    for annotation in annotations:
        public_id = annotation.attachment_public_id
        if public_id not in attachments or public_id in seen:
            raise ValueError("annotation is outside selected evidence or duplicated")
        seen.add(public_id)
        payload = json.dumps(
            annotation.payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        marks = json.dumps(
            annotation.marks_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        connection.execute(
            "INSERT INTO submission_review_annotations "
            "(review_id, attachment_id, schema_version, rotation, marks_json, payload_sha256, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                review_id,
                attachments[public_id],
                annotation.schema_version,
                annotation.rotation,
                marks,
                hashlib.sha256(payload.encode()).hexdigest(),
                created_at,
            ),
        )


def insert_event(
    connection: sqlite3.Connection,
    *,
    review_id: int,
    payload_json: str,
    created_at: str,
) -> None:
    connection.execute(
        "INSERT INTO submission_review_events "
        "(review_id, event_kind, payload_json, created_at) "
        "VALUES (?, 'completed', ?, ?)",
        (review_id, payload_json, created_at),
    )


def recipient_account_public_ids(
    connection: sqlite3.Connection, student_user_id: int
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    owners = connection.execute(
        "SELECT public_id FROM auth_accounts WHERE audience = 'student' "
        "AND linked_user_id = ? AND status = 'active' ORDER BY id",
        (student_user_id,),
    ).fetchall()
    family = connection.execute(
        "SELECT account.public_id FROM family_student_links AS link "
        "JOIN auth_accounts AS account ON account.id = link.family_account_id "
        "WHERE link.student_user_id = ? AND account.status = 'active' ORDER BY account.id",
        (student_user_id,),
    ).fetchall()
    return (
        tuple(str(row["public_id"]) for row in owners),
        tuple(str(row["public_id"]) for row in family),
    )
