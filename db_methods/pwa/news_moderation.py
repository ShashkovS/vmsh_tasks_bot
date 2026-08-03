"""Direct SQLite reads and writes for PWA news visibility."""

from __future__ import annotations

import sqlite3


def list_news_for_moderation(
    connection: sqlite3.Connection,
    *,
    state: str | None,
    limit: int,
    public_id: str | None = None,
) -> list[dict[str, object]]:
    filters: list[str] = []
    values: list[object] = []
    if state is not None:
        filters.append("visibility.state = ?")
        values.append(state)
    if public_id is not None:
        filters.append("post.public_id = ?")
        values.append(public_id)
    where = "" if not filters else "WHERE " + " AND ".join(filters)
    values.append(limit)
    rows = connection.execute(
        "SELECT post.public_id, post.source_type, post.published_at, "
        "post.last_source_edited_at, post.source_deleted_at, "
        "visibility.state AS visibility_state, "
        "visibility.moderation_reason, visibility.updated_at AS visibility_updated_at, "
        "visibility.version AS visibility_version, revision.revision_number, "
        "revision.text_plain, binding.title_cached AS channel_title, "
        "CASE WHEN post.owner_course_id IS NOT NULL THEN 'course' ELSE 'group' END "
        "AS owner_type, coalesce(course.public_id, owner_group.public_id) AS owner_public_id, "
        "coalesce(course.name, owner_group.public_name) AS owner_name, "
        "(SELECT count(*) FROM news_media media WHERE media.revision_id = revision.id) "
        "AS media_count FROM news_posts post "
        "JOIN news_visibility visibility ON visibility.post_id = post.id "
        "JOIN news_revisions revision ON revision.id = ("
        "SELECT latest.id FROM news_revisions latest WHERE latest.post_id = post.id "
        "ORDER BY latest.revision_number DESC LIMIT 1) "
        "LEFT JOIN telegram_bindings binding "
        "ON binding.public_id = post.source_binding_public_id "
        "LEFT JOIN courses course ON course.id = post.owner_course_id "
        "LEFT JOIN groups owner_group ON owner_group.group_id = post.owner_group_id "
        + where
        + " ORDER BY post.published_at DESC, post.id DESC LIMIT ?",
        tuple(values),
    ).fetchall()
    return [dict(row) for row in rows]


def update_news_visibility(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    state: str,
    reason: str | None,
    actor_user_id: int,
    now: str,
) -> dict[str, object] | None:
    cursor = connection.execute(
        "UPDATE news_visibility SET state = ?, moderation_reason = ?, "
        "updated_by_user_id = ?, updated_at = ?, version = version + 1 "
        "WHERE post_id = (SELECT id FROM news_posts WHERE public_id = ?) "
        "AND version = ?",
        (state, reason, actor_user_id, now, public_id, expected_version),
    )
    if cursor.rowcount != 1:
        return None
    rows = list_news_for_moderation(
        connection, state=None, limit=1, public_id=public_id
    )
    return rows[0] if rows else None


def update_news_source_state(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    source_state: str,
    actor_user_id: int,
    now: str,
) -> dict[str, object] | None:
    """Apply one optimistic Telegram-source reconciliation write."""

    if source_state == "deleted":
        visibility_state = "source_deleted"
        source_deleted_at: str | None = now
    else:
        visibility_state = "visible"
        source_deleted_at = None
    cursor = connection.execute(
        "UPDATE news_visibility SET state = ?, moderation_reason = NULL, "
        "updated_by_user_id = ?, updated_at = ?, version = version + 1 "
        "WHERE post_id = (SELECT id FROM news_posts "
        "WHERE public_id = ? AND source_type = 'telegram') AND version = ?",
        (visibility_state, actor_user_id, now, public_id, expected_version),
    )
    if cursor.rowcount != 1:
        return None
    connection.execute(
        "UPDATE news_posts SET source_deleted_at = ?, updated_at = ?, "
        "version = version + 1 WHERE public_id = ? AND source_type = 'telegram'",
        (source_deleted_at, now, public_id),
    )
    rows = list_news_for_moderation(
        connection, state=None, limit=1, public_id=public_id
    )
    return rows[0] if rows else None


__all__ = [
    "list_news_for_moderation",
    "update_news_source_state",
    "update_news_visibility",
]
