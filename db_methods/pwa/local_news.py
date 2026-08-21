"""Focused SQLite reads and writes for Staff-authored local news."""

from __future__ import annotations

import sqlite3


def find_local_post_for_edit(
    connection: sqlite3.Connection,
    *,
    public_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT post.id, post.public_id, post.published_at, visibility.state, "
        "visibility.version, revision.revision_number, revision.text_plain, "
        "revision.source_payload_json, revision.content_format, "
        "revision.markdown_source, revision.rich_document_json "
        "FROM news_posts post "
        "JOIN news_visibility visibility ON visibility.post_id = post.id "
        "JOIN news_revisions revision ON revision.id = ("
        "SELECT latest.id FROM news_revisions latest WHERE latest.post_id = post.id "
        "ORDER BY latest.revision_number DESC LIMIT 1) "
        "WHERE post.public_id = ? AND post.source_type = 'local'",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def update_local_post_header(
    connection: sqlite3.Connection,
    *,
    post_id: int,
    public_id: str,
    expected_version: int,
    published_at: str,
    actor_user_id: int,
    now: str,
) -> bool:
    visibility = connection.execute(
        "UPDATE news_visibility SET updated_by_user_id = ?, updated_at = ?, "
        "version = version + 1 WHERE post_id = ? AND version = ?",
        (actor_user_id, now, post_id, expected_version),
    )
    if visibility.rowcount != 1:
        return False
    connection.execute(
        "UPDATE news_posts SET published_at = ?, last_source_edited_at = ?, "
        "updated_at = ?, version = version + 1 "
        "WHERE id = ? AND public_id = ? AND source_type = 'local'",
        (published_at, now, now, post_id, public_id),
    )
    return True


def reschedule_local_news_events(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    published_at: str,
) -> int:
    cursor = connection.execute(
        "UPDATE notification_events SET occurred_at = ?, deliver_after = ? "
        "WHERE category = 'news' AND dedupe_key = ?",
        (published_at, published_at, public_id),
    )
    return cursor.rowcount


def delete_local_news_events(
    connection: sqlite3.Connection,
    *,
    public_id: str,
) -> int:
    cursor = connection.execute(
        "DELETE FROM notification_events WHERE category = 'news' AND dedupe_key = ?",
        (public_id,),
    )
    return cursor.rowcount


__all__ = [
    "delete_local_news_events",
    "find_local_post_for_edit",
    "reschedule_local_news_events",
    "update_local_post_header",
]
