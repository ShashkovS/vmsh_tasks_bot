"""SQLite projections and receipts for vmshpwa/docs/question-attention.md."""

from __future__ import annotations

import sqlite3


def thread_owner(connection: sqlite3.Connection, public_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT id, student_user_id FROM support_threads WHERE public_id=?",
        (public_id,),
    ).fetchone()


def reply_rows(
    connection: sqlite3.Connection, entry_ids: tuple[str, ...]
) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in entry_ids)
    return connection.execute(
        f"SELECT id, public_id, thread_id, author_kind, server_received_at "
        f"FROM support_entries WHERE public_id IN ({placeholders})",
        entry_ids,
    ).fetchall()


def save_read(
    connection: sqlite3.Connection, *, entry_id: int, student_user_id: int, now: str
) -> str:
    connection.execute(
        "INSERT INTO support_entry_reads(entry_id,student_user_id,read_at) VALUES(?,?,?) "
        "ON CONFLICT(entry_id) DO NOTHING",
        (entry_id, student_user_id, now),
    )
    return connection.execute(
        "SELECT read_at FROM support_entry_reads WHERE entry_id=?",
        (entry_id,),
    ).fetchone()["read_at"]


def read_matching_notifications(
    connection: sqlite3.Connection,
    *,
    entry_public_id: str,
    student_user_id: int,
    session_id: int | None,
    now: str,
) -> None:
    connection.execute(
        "UPDATE notification_events SET read_at=max(occurred_at,?), "
        "read_by_session_id=CASE WHEN account_id=(SELECT account_id FROM auth_sessions "
        "WHERE id=?) THEN ? ELSE NULL END "
        "WHERE category='thread_updated' AND dedupe_key=? AND read_at IS NULL "
        "AND account_id IN (SELECT id FROM auth_accounts WHERE audience='student' "
        "AND linked_user_id=?)",
        (now, session_id, session_id, entry_public_id, student_user_id),
    )


def inherit_notification_read(
    connection: sqlite3.Connection, *, entry_public_id: str, account_id: int
) -> None:
    connection.execute(
        "UPDATE notification_events SET read_at=(SELECT r.read_at FROM "
        "support_entry_reads r JOIN support_entries e ON e.id=r.entry_id WHERE e.public_id=?) "
        "WHERE account_id=? AND category='thread_updated' AND dedupe_key=? "
        "AND read_at IS NULL AND EXISTS(SELECT 1 FROM support_entry_reads r "
        "JOIN support_entries e ON e.id=r.entry_id WHERE e.public_id=?)",
        (entry_public_id, account_id, entry_public_id, entry_public_id),
    )


def unread_targets(
    connection: sqlite3.Connection, *, student_user_id: int, now: str
) -> list[sqlite3.Row]:
    # Match the current Student publication/access boundary, including frozen
    # figure-layout publications (db_methods/pwa/content.py's lesson projection).
    return connection.execute(
        """SELECT t.public_id AS threadId, course.public_id AS courseId,
        g.public_id AS groupId, gl.public_id AS groupLessonId,
        p.public_id AS problemId, e.public_id AS firstUnreadEntryId
        FROM support_threads t
        JOIN group_lessons gl ON gl.id=t.group_lesson_id AND gl.status='active'
        JOIN courses course ON course.id=gl.course_id AND course.status='active'
        JOIN groups g ON g.course_id=gl.course_id AND g.group_id=gl.group_id
        JOIN problems p ON p.id=t.problem_id
        JOIN support_entries e ON e.id=(
            SELECT reply.id FROM support_entries reply
            WHERE reply.thread_id=t.id AND reply.author_kind IN ('teacher','admin')
            AND NOT EXISTS(SELECT 1 FROM support_entry_reads r WHERE r.entry_id=reply.id)
            ORDER BY reply.server_received_at,reply.id LIMIT 1)
        WHERE t.student_user_id=? AND t.kind='problem_question'
        -- problem-release.md: navigation follows the same Off boundary as task lists.
        AND NOT EXISTS(SELECT 1 FROM lesson_problem_release release
            WHERE release.group_lesson_id=gl.id AND release.problem_id=t.problem_id
            AND release.is_open=0)
        AND EXISTS(SELECT 1 FROM course_enrollments enrollment
            WHERE enrollment.student_user_id=t.student_user_id
            AND enrollment.course_id=gl.course_id AND enrollment.status='active'
            AND (enrollment.active_group_id=gl.group_id OR EXISTS(
                SELECT 1 FROM course_group_access access
                WHERE access.enrollment_id=enrollment.id AND access.group_id=gl.group_id
                AND access.valid_from<=? AND (access.valid_to IS NULL OR access.valid_to>?))))
        AND EXISTS(SELECT 1 FROM lesson_publications pub
            JOIN content_revisions rev ON rev.id=pub.revision_id
            JOIN problem_revisions pr ON pr.content_revision_id=pub.revision_id
            WHERE pub.group_lesson_id=gl.id AND pub.kind='condition' AND pub.state='published'
            AND pr.problem_id=t.problem_id
            AND (rev.status='ready' OR EXISTS(SELECT 1 FROM publication_figure_layouts frozen
                WHERE frozen.publication_id=pub.id AND frozen.document_json IS NOT NULL))
            AND EXISTS(SELECT 1 FROM content_derivatives d WHERE d.revision_id=pub.revision_id
                AND d.kind='web_ast' AND (d.invalidated_at IS NULL OR EXISTS(
                    SELECT 1 FROM publication_figure_layouts frozen
                    WHERE frozen.publication_id=pub.id AND frozen.document_json IS NOT NULL))))
        ORDER BY e.server_received_at,e.id,t.id""",
        (student_user_id, now, now),
    ).fetchall()
