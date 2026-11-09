"""Focused SQLite storage for vmshpwa/docs/problem-release.md."""

from __future__ import annotations

import json
import sqlite3


def ready_condition(
    connection: sqlite3.Connection, group_lesson_id: int, revision_public_id: str
):
    return connection.execute(
        "SELECT revision.id FROM content_revisions revision "
        "JOIN content_sources source ON source.id = revision.source_id "
        "WHERE revision.public_id = ? AND source.group_lesson_id = ? "
        "AND source.kind = 'condition' AND (revision.status = 'ready' OR EXISTS ("
        "SELECT 1 FROM lesson_publications publication WHERE publication.revision_id = revision.id "
        "AND publication.state = 'published'))",
        (revision_public_id, group_lesson_id),
    ).fetchone()


def material_rows(connection: sqlite3.Connection, revision_id: int):
    return connection.execute(
        "SELECT source_ordinal, problem_id FROM content_problem_matches "
        "WHERE content_revision_id = ? AND resolved_at IS NOT NULL AND decision <> 'omit'",
        (revision_id,),
    ).fetchall()


def revision_rows(
    connection: sqlite3.Connection, group_lesson_id: int, revision_id: int
):
    return connection.execute(
        "SELECT pr.source_ordinal, pr.problem_id, p.public_id, release.is_open "
        "FROM problem_revisions pr JOIN problems p ON p.id = pr.problem_id "
        "LEFT JOIN lesson_problem_release release "
        "ON release.group_lesson_id = ? AND release.problem_id = pr.problem_id "
        "WHERE pr.content_revision_id = ? ORDER BY pr.source_ordinal, pr.source_item",
        (group_lesson_id, revision_id),
    ).fetchall()


def current_condition(connection: sqlite3.Connection, group_lesson_id: int):
    return connection.execute(
        "SELECT revision_id FROM lesson_publications WHERE group_lesson_id = ? "
        "AND kind = 'condition' AND state = 'published'",
        (group_lesson_id,),
    ).fetchone()


def has_closed_tasks(connection: sqlite3.Connection, group_lesson_id: int) -> bool:
    current = current_condition(connection, group_lesson_id)
    if current is not None:
        return any(
            row["is_open"] == 0
            for row in revision_rows(
                connection,
                group_lesson_id,
                int(current["revision_id"]),
            )
        )
    return (
        connection.execute(
            "SELECT 1 FROM lesson_problem_release WHERE group_lesson_id = ? "
            "AND is_open = 0 LIMIT 1",
            (group_lesson_id,),
        ).fetchone()
        is not None
    )


def version(connection: sqlite3.Connection, group_lesson_id: int) -> int:
    return int(
        connection.execute(
            "SELECT problem_release_version FROM group_lessons WHERE id = ?",
            (group_lesson_id,),
        ).fetchone()["problem_release_version"]
    )


def save_states(
    connection: sqlite3.Connection, group_lesson_id: int, states: dict[int, bool]
) -> None:
    connection.executemany(
        "INSERT INTO lesson_problem_release (group_lesson_id, problem_id, is_open) "
        "VALUES (?, ?, ?) ON CONFLICT(group_lesson_id, problem_id) "
        "DO UPDATE SET is_open = excluded.is_open",
        [
            (group_lesson_id, problem_id, int(is_open))
            for problem_id, is_open in states.items()
        ],
    )


def record_change(
    connection: sqlite3.Connection,
    *,
    group_lesson_id: int,
    revision_id: int,
    before: dict[int, bool],
    after: dict[int, bool],
    actor_user_id: int,
    request_id: str,
    timestamp: str,
) -> None:
    connection.execute(
        "UPDATE group_lessons SET problem_release_version = problem_release_version + 1 "
        "WHERE id = ?",
        (group_lesson_id,),
    )
    connection.execute(
        "INSERT INTO lesson_problem_release_events "
        "(group_lesson_id, condition_revision_id, version, before_json, after_json, "
        "actor_user_id, request_id, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            group_lesson_id,
            revision_id,
            version(connection, group_lesson_id),
            json.dumps(before, sort_keys=True),
            json.dumps(after, sort_keys=True),
            actor_user_id,
            request_id,
            timestamp,
        ),
    )


def is_closed(
    connection: sqlite3.Connection, group_lesson_id: int, problem_id: int
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM lesson_problem_release WHERE group_lesson_id = ? "
            "AND problem_id = ? AND is_open = 0",
            (group_lesson_id, problem_id),
        ).fetchone()
        is not None
    )
