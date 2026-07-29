"""Direct SQLite operations for the PWA news mirror."""

from __future__ import annotations

import sqlite3


def find_news_source_bindings(
    connection: sqlite3.Connection, chat_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT binding.public_id, binding.owner_course_id, binding.owner_group_id "
        "FROM telegram_bindings binding "
        "WHERE binding.status = 'verified' AND binding.purpose = 'news_source' "
        "AND binding.chat_id = ? ORDER BY binding.id",
        (chat_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def find_telegram_post(
    connection: sqlite3.Connection,
    *,
    chat_id: int,
    message_id: int,
    media_group_id: str | None,
) -> dict[str, object] | None:
    if media_group_id is None:
        row = connection.execute(
            "SELECT * FROM news_posts WHERE source_type = 'telegram' "
            "AND source_chat_id = ? AND source_message_id = ? "
            "AND source_media_group_id IS NULL",
            (chat_id, message_id),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT * FROM news_posts WHERE source_type = 'telegram' "
            "AND source_chat_id = ? AND source_media_group_id = ?",
            (chat_id, media_group_id),
        ).fetchone()
    return None if row is None else dict(row)


def insert_telegram_post(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    source_binding_public_id: str,
    owner_course_id: int | None,
    owner_group_id: str | None,
    chat_id: int,
    message_id: int,
    media_group_id: str | None,
    published_at: str,
    edited_at: str | None,
    now: str,
) -> int:
    row = connection.execute(
        "INSERT INTO news_posts "
        "(public_id, source_type, source_binding_public_id, owner_course_id, "
        "owner_group_id, source_chat_id, source_message_id, source_media_group_id, "
        "published_at, last_source_edited_at, created_at, updated_at) "
        "VALUES (?, 'telegram', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            public_id,
            source_binding_public_id,
            owner_course_id,
            owner_group_id,
            chat_id,
            message_id,
            media_group_id,
            published_at,
            edited_at,
            now,
            now,
        ),
    ).fetchone()
    post_id = int(row["id"])
    connection.execute(
        "INSERT INTO news_visibility (post_id, state, updated_at) "
        "VALUES (?, 'visible', ?)",
        (post_id, now),
    )
    return post_id


def revision_exists(
    connection: sqlite3.Connection, *, post_id: int, source_hash: str
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM news_revisions WHERE post_id = ? AND source_hash = ?",
            (post_id, source_hash),
        ).fetchone()
        is not None
    )


def insert_revision(
    connection: sqlite3.Connection,
    *,
    post_id: int,
    source_hash: str,
    source_edited_at: str | None,
    text_plain: str,
    content_json: str,
    source_payload_json: str,
    now: str,
) -> int:
    row = connection.execute(
        "INSERT INTO news_revisions "
        "(post_id, revision_number, source_hash, source_edited_at, text_plain, "
        "content_json, source_payload_json, created_at) "
        "SELECT ?, coalesce(max(revision_number), 0) + 1, ?, ?, ?, ?, ?, ? "
        "FROM news_revisions WHERE post_id = ? RETURNING id",
        (
            post_id,
            source_hash,
            source_edited_at,
            text_plain,
            content_json,
            source_payload_json,
            now,
            post_id,
        ),
    ).fetchone()
    return int(row["id"])


def insert_media(
    connection: sqlite3.Connection,
    *,
    revision_id: int,
    media: list[dict[str, object]],
    now: str,
) -> None:
    for ordinal, item in enumerate(media):
        connection.execute(
            "INSERT INTO news_media "
            "(revision_id, ordinal, media_kind, source_message_id, source_file_id, "
            "storage_key, public_url, mime_type, width, height, storage_status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                revision_id,
                ordinal,
                item["kind"],
                item.get("source_message_id"),
                item.get("source_file_id"),
                item.get("storage_key"),
                item.get("public_url"),
                item.get("mime_type"),
                item.get("width"),
                item.get("height"),
                item.get("storage_status", "pending"),
                now,
                now,
            ),
        )


def touch_post(
    connection: sqlite3.Connection,
    *,
    post_id: int,
    edited_at: str | None,
    now: str,
) -> None:
    connection.execute(
        "UPDATE news_posts SET last_source_edited_at = ?, source_deleted_at = NULL, "
        "updated_at = ?, version = version + 1 WHERE id = ?",
        (edited_at, now, post_id),
    )
    connection.execute(
        "UPDATE news_visibility SET state = 'visible', moderation_reason = NULL, "
        "updated_by_user_id = NULL, updated_at = ?, version = version + 1 "
        "WHERE post_id = ? AND state = 'source_deleted'",
        (now, post_id),
    )


def mark_source_deleted(
    connection: sqlite3.Connection, *, post_id: int, now: str
) -> None:
    connection.execute(
        "UPDATE news_posts SET source_deleted_at = ?, updated_at = ?, "
        "version = version + 1 WHERE id = ? AND source_deleted_at IS NULL",
        (now, now, post_id),
    )
    connection.execute(
        "UPDATE news_visibility SET state = 'source_deleted', "
        "moderation_reason = NULL, updated_by_user_id = NULL, updated_at = ?, "
        "version = version + 1 WHERE post_id = ? AND state <> 'source_deleted'",
        (now, post_id),
    )


def insert_diagnostic(
    connection: sqlite3.Connection,
    *,
    chat_id: int | None,
    message_id: int | None,
    code: str,
    detail: str | None,
    now: str,
) -> None:
    connection.execute(
        "INSERT INTO news_ingest_diagnostics "
        "(source_chat_id, source_message_id, code, detail, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, message_id, code, detail, now),
    )


def get_post(connection: sqlite3.Connection, post_id: int) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT post.*, visibility.state AS visibility_state, "
        "revision.id AS revision_id, revision.revision_number, revision.source_hash, "
        "revision.text_plain, revision.content_json, revision.source_payload_json "
        "FROM news_posts post JOIN news_visibility visibility ON visibility.post_id = post.id "
        "LEFT JOIN news_revisions revision ON revision.id = ("
        "SELECT latest.id FROM news_revisions latest WHERE latest.post_id = post.id "
        "ORDER BY latest.revision_number DESC LIMIT 1) WHERE post.id = ?",
        (post_id,),
    ).fetchone()
    return None if row is None else dict(row)


def list_media(
    connection: sqlite3.Connection, revision_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT * FROM news_media WHERE revision_id = ? ORDER BY ordinal",
        (revision_id,),
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "find_news_source_bindings",
    "find_telegram_post",
    "get_post",
    "insert_diagnostic",
    "insert_media",
    "insert_revision",
    "insert_telegram_post",
    "list_media",
    "mark_source_deleted",
    "revision_exists",
    "touch_post",
]
