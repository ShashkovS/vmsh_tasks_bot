"""Focused SQLite reads for the Staff weekly dashboard."""

from __future__ import annotations

import sqlite3


def list_group_lesson_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT group_lesson.id AS group_lesson_id,
               group_lesson.public_id AS group_lesson_public_id,
               group_lesson.cycle_anchor_date,
               group_lesson.business_timezone,
               course.public_id AS course_public_id,
               course.code AS course_code,
               course.name AS course_name,
               course.sort_order AS course_sort_order,
               group_record.public_id AS group_public_id,
               group_record.short_code AS group_code,
               group_record.public_name AS group_name,
               group_record.color_key,
               group_record.sort_order AS group_sort_order,
               course_lesson.lesson_number,
               lesson_window.opens_at,
               lesson_window.submission_closes_at,
               lesson_window.hint_scheduled_at,
               lesson_window.solution_scheduled_at
        FROM group_lessons AS group_lesson
        JOIN course_lessons AS course_lesson
          ON course_lesson.id = group_lesson.course_lesson_id
        JOIN courses AS course ON course.id = group_lesson.course_id
        JOIN groups AS group_record
          ON group_record.course_id = group_lesson.course_id
         AND group_record.group_id = group_lesson.group_id
        LEFT JOIN lesson_windows AS lesson_window
          ON lesson_window.group_lesson_id = group_lesson.id
        WHERE group_lesson.status IN ('draft', 'active')
          AND course.status = 'active'
          AND group_record.status = 'active'
        ORDER BY course.sort_order, course.id, group_record.sort_order,
                 group_record.group_id, course_lesson.lesson_number
        """
    ).fetchall()
    return [dict(row) for row in rows]


def list_publication_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT publication.group_lesson_id, publication.kind, publication.state, "
        "publication.scheduled_at, publication.published_at "
        "FROM lesson_publications AS publication "
        "JOIN group_lessons AS group_lesson "
        "ON group_lesson.id = publication.group_lesson_id "
        "WHERE group_lesson.status IN ('draft', 'active') "
        "AND publication.state IN ('scheduled', 'published') "
        "ORDER BY publication.group_lesson_id, publication.kind, publication.id"
    ).fetchall()
    return [dict(row) for row in rows]


def list_oral_window_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT oral_window.group_lesson_id, oral_window.opens_at, "
        "oral_window.closes_at FROM oral_windows AS oral_window "
        "JOIN group_lessons AS group_lesson "
        "ON group_lesson.id = oral_window.group_lesson_id "
        "WHERE group_lesson.status IN ('draft', 'active') "
        "AND oral_window.status = 'active' "
        "ORDER BY oral_window.opens_at, oral_window.id"
    ).fetchall()
    return [dict(row) for row in rows]


def classroom_delivery_failures(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        "SELECT count(DISTINCT batch.id) AS failed_batches, "
        "count(*) AS failed_recipients "
        "FROM classroom_assignment_delivery_recipients AS recipient "
        "JOIN classroom_assignment_delivery_batches AS batch "
        "ON batch.id = recipient.batch_id "
        "WHERE recipient.pwa_state = 'failed' "
        "OR recipient.telegram_state = 'failed'"
    ).fetchone()
    return {
        "failed_batches": int(row["failed_batches"]),
        "failed_recipients": int(row["failed_recipients"]),
    }


__all__ = [
    "classroom_delivery_failures",
    "list_group_lesson_rows",
    "list_oral_window_rows",
    "list_publication_rows",
]
