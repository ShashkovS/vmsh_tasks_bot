"""Direct SQLite operations for group banner windows."""

from __future__ import annotations

import sqlite3


def get_group_banner(
    connection: sqlite3.Connection, public_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT banner.*, owner_group.public_id AS group_public_id, "
        "owner_group.public_name AS group_name, course.public_id AS course_public_id, "
        "course.name AS course_name FROM group_banners banner "
        "JOIN groups owner_group ON owner_group.group_id = banner.group_id "
        "JOIN courses course ON course.id = owner_group.course_id "
        "WHERE banner.public_id = ?",
        (public_id,),
    ).fetchone()
    return None if row is None else dict(row)


def insert_group_banner(
    connection: sqlite3.Connection,
    *,
    group_id: str,
    audience: str,
    html_sanitized: str,
    starts_at: str,
    ends_at: str,
    priority: int,
    dismissible: bool,
    actor_user_id: int,
    now: str,
    content_format: str = "legacy_html",
    markdown_source: str | None = None,
    rich_document_json: str | None = None,
) -> dict[str, object]:
    row = connection.execute(
        "INSERT INTO group_banners "
        "(group_id, audience, html_sanitized, content_format, markdown_source, "
        "rich_document_json, starts_at, ends_at, "
        "priority, dismissible, created_by_user_id, updated_by_user_id, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "RETURNING public_id",
        (
            group_id,
            audience,
            html_sanitized,
            content_format,
            markdown_source,
            rich_document_json,
            starts_at,
            ends_at,
            priority,
            int(dismissible),
            actor_user_id,
            actor_user_id,
            now,
            now,
        ),
    ).fetchone()
    item = get_group_banner(connection, str(row["public_id"]))
    assert item is not None
    return item


def update_group_banner(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    audience: str,
    html_sanitized: str,
    starts_at: str,
    ends_at: str,
    priority: int,
    dismissible: bool,
    actor_user_id: int,
    now: str,
    content_format: str = "legacy_html",
    markdown_source: str | None = None,
    rich_document_json: str | None = None,
) -> dict[str, object] | None:
    cursor = connection.execute(
        "UPDATE group_banners SET audience = ?, html_sanitized = ?, content_format = ?, "
        "markdown_source = ?, rich_document_json = ?, starts_at = ?, "
        "ends_at = ?, priority = ?, dismissible = ?, updated_by_user_id = ?, "
        "updated_at = ?, version = version + 1 WHERE public_id = ? "
        "AND version = ? AND status = 'active'",
        (
            audience,
            html_sanitized,
            content_format,
            markdown_source,
            rich_document_json,
            starts_at,
            ends_at,
            priority,
            int(dismissible),
            actor_user_id,
            now,
            public_id,
            expected_version,
        ),
    )
    return get_group_banner(connection, public_id) if cursor.rowcount == 1 else None


def replace_group_banner_media(
    connection: sqlite3.Connection,
    *,
    banner_id: int,
    media: list[dict[str, object]],
    now: str,
) -> None:
    connection.execute("DELETE FROM group_banner_media WHERE banner_id = ?", (banner_id,))
    for ordinal, item in enumerate(media):
        connection.execute(
            "INSERT INTO group_banner_media "
            "(banner_id, ordinal, media_id, source_url, storage_key, public_url, "
            "mime_type, width, height, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                banner_id,
                ordinal,
                item["media_id"],
                item["source_url"],
                item["storage_key"],
                item["public_url"],
                item["mime_type"],
                item["width"],
                item["height"],
                now,
            ),
        )


def cancel_group_banner(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    expected_version: int,
    actor_user_id: int,
    now: str,
) -> dict[str, object] | None:
    cursor = connection.execute(
        "UPDATE group_banners SET status = 'cancelled', cancelled_at = ?, "
        "updated_by_user_id = ?, updated_at = ?, version = version + 1 "
        "WHERE public_id = ? AND version = ? AND status = 'active'",
        (now, actor_user_id, now, public_id, expected_version),
    )
    return get_group_banner(connection, public_id) if cursor.rowcount == 1 else None


def list_current_group_banners(
    connection: sqlite3.Connection,
    *,
    group_ids: tuple[str, ...],
    audience: str,
    now: str,
) -> list[dict[str, object]]:
    if not group_ids:
        return []
    rows = connection.execute(
        "SELECT banner.*, owner_group.public_id AS group_public_id, "
        "owner_group.public_name AS group_name, course.public_id AS course_public_id, "
        "course.name AS course_name FROM group_banners banner "
        "JOIN groups owner_group ON owner_group.group_id = banner.group_id "
        "JOIN courses course ON course.id = owner_group.course_id "
        "WHERE banner.group_id IN ("
        + ",".join("?" for _ in group_ids)
        + ") AND banner.status = 'active' AND banner.starts_at <= ? "
        "AND banner.ends_at > ? AND banner.audience IN (?, 'both') "
        "ORDER BY banner.priority DESC, banner.starts_at DESC, banner.id DESC",
        (*group_ids, now, now, audience),
    ).fetchall()
    return [dict(row) for row in rows]


def find_group_id(connection: sqlite3.Connection, public_id: str) -> str | None:
    row = connection.execute(
        "SELECT group_id FROM groups WHERE public_id = ? AND status = 'active'",
        (public_id,),
    ).fetchone()
    return None if row is None else str(row["group_id"])


def list_group_banners(
    connection: sqlite3.Connection,
    *,
    group_public_id: str | None,
    status: str | None,
    limit: int,
) -> list[dict[str, object]]:
    filters: list[str] = []
    parameters: list[object] = []
    if group_public_id is not None:
        filters.append("owner_group.public_id = ?")
        parameters.append(group_public_id)
    if status is not None:
        filters.append("banner.status = ?")
        parameters.append(status)
    where = " WHERE " + " AND ".join(filters) if filters else ""
    rows = connection.execute(
        "SELECT banner.*, owner_group.public_id AS group_public_id, "
        "owner_group.public_name AS group_name, course.public_id AS course_public_id, "
        "course.name AS course_name FROM group_banners banner "
        "JOIN groups owner_group ON owner_group.group_id = banner.group_id "
        "JOIN courses course ON course.id = owner_group.course_id"
        + where
        + " ORDER BY banner.starts_at DESC, banner.id DESC LIMIT ?",
        (*parameters, limit),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "cancel_group_banner",
    "get_group_banner",
    "find_group_id",
    "insert_group_banner",
    "list_current_group_banners",
    "list_group_banners",
    "replace_group_banner_media",
    "update_group_banner",
]
