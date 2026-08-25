"""Direct SQLite operations for the PWA news mirror."""

from __future__ import annotations

import sqlite3


def find_news_source_bindings(
    connection: sqlite3.Connection, chat_id: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT binding.id, binding.owner_course_id, binding.owner_group_id "
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
    source_binding_id: int,
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
        "(source_type, source_binding_id, owner_course_id, "
        "owner_group_id, source_chat_id, source_message_id, source_media_group_id, "
        "published_at, last_source_edited_at, created_at, updated_at) "
        "VALUES ('telegram', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            source_binding_id,
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


def find_local_news_owner(
    connection: sqlite3.Connection, *, owner_type: str, owner_public_id: str
) -> dict[str, object] | None:
    """Resolve one active course or group for a local PWA publication."""

    if owner_type == "course":
        row = connection.execute(
            "SELECT id AS owner_course_id, NULL AS owner_group_id "
            "FROM courses WHERE public_id = ? AND status = 'active'",
            (owner_public_id,),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT NULL AS owner_course_id, group_id AS owner_group_id "
            "FROM groups WHERE public_id = ? AND status = 'active'",
            (owner_public_id,),
        ).fetchone()
    return None if row is None else dict(row)


def insert_local_post(
    connection: sqlite3.Connection,
    *,
    owner_course_id: int | None,
    owner_group_id: str | None,
    published_at: str,
    actor_user_id: int,
    now: str,
) -> int:
    """Insert the local post header and its initial visible state."""

    row = connection.execute(
        "INSERT INTO news_posts "
        "(source_type, owner_course_id, owner_group_id, published_at, "
        "created_at, updated_at) VALUES ('local', ?, ?, ?, ?, ?) RETURNING id",
        (owner_course_id, owner_group_id, published_at, now, now),
    ).fetchone()
    post_id = int(row["id"])
    connection.execute(
        "INSERT INTO news_visibility "
        "(post_id, state, updated_by_user_id, updated_at) "
        "VALUES (?, 'visible', ?, ?)",
        (post_id, actor_user_id, now),
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
    content_format: str = "legacy",
    markdown_source: str | None = None,
    rich_document_json: str | None = None,
) -> int:
    row = connection.execute(
        "INSERT INTO news_revisions "
        "(post_id, revision_number, source_hash, source_edited_at, text_plain, "
        "content_json, source_payload_json, content_format, markdown_source, "
        "rich_document_json, created_at) "
        "SELECT ?, coalesce(max(revision_number), 0) + 1, ?, ?, ?, ?, ?, ?, ?, ?, ? "
        "FROM news_revisions WHERE post_id = ? RETURNING id",
        (
            post_id,
            source_hash,
            source_edited_at,
            text_plain,
            content_json,
            source_payload_json,
            content_format,
            markdown_source,
            rich_document_json,
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
            "storage_key, public_url, mime_type, width, height, storage_status, source_url, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                item.get("source_url"),
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


def list_news_recipient_accounts(
    connection: sqlite3.Connection,
    *,
    owner_course_id: int | None,
    owner_group_id: str | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        "WITH recipient_students AS ("
        "SELECT DISTINCT enrollment.student_user_id FROM course_enrollments enrollment "
        "WHERE enrollment.status = 'active' AND ("
        "(? IS NOT NULL AND enrollment.course_id = ?) OR "
        "(? IS NOT NULL AND EXISTS (SELECT 1 FROM course_group_access access "
        "WHERE access.enrollment_id = enrollment.id AND access.group_id = ? "
        "AND access.valid_to IS NULL)))) "
        "SELECT account.id, account.audience FROM auth_accounts account "
        "WHERE account.status = 'active' AND ("
        "(account.audience = 'student' AND account.linked_user_id IN "
        "(SELECT student_user_id FROM recipient_students)) OR "
        "(account.audience = 'family' AND EXISTS (SELECT 1 FROM family_student_links link "
        "WHERE link.family_account_id = account.id AND link.revoked_at IS NULL "
        "AND link.student_user_id IN (SELECT student_user_id FROM recipient_students)))) "
        "ORDER BY account.id",
        (owner_course_id, owner_course_id, owner_group_id, owner_group_id),
    ).fetchall()
    return [dict(row) for row in rows]


def news_course_public_id(
    connection: sqlite3.Connection,
    *,
    owner_course_id: int | None,
    owner_group_id: str | None,
) -> str:
    row = connection.execute(
        "SELECT course.public_id FROM courses course WHERE "
        "(? IS NOT NULL AND course.id = ?) OR "
        "(? IS NOT NULL AND EXISTS (SELECT 1 FROM groups owner_group "
        "WHERE owner_group.course_id = course.id AND owner_group.group_id = ?)) "
        "LIMIT 1",
        (owner_course_id, owner_course_id, owner_group_id, owner_group_id),
    ).fetchone()
    if row is None:
        raise LookupError("news owner course is missing")
    return str(row["public_id"])


def has_visible_local_post_due_between(
    connection: sqlite3.Connection, *, after: str, through: str
) -> bool:
    row = connection.execute(
        "SELECT 1 FROM news_posts post "
        "JOIN news_visibility visibility ON visibility.post_id = post.id "
        "WHERE post.source_type = 'local' AND visibility.state = 'visible' "
        "AND post.published_at > ? AND post.published_at <= ? LIMIT 1",
        (after, through),
    ).fetchone()
    return row is not None


def list_visible_posts(
    connection: sqlite3.Connection,
    *,
    course_ids: tuple[int, ...],
    group_ids: tuple[str, ...],
    cursor_public_id: str | None,
    now: str,
    limit: int,
) -> list[dict[str, object]]:
    if not course_ids and not group_ids:
        return []
    scope_parts: list[str] = []
    values: list[object] = []
    if course_ids:
        scope_parts.append(
            f"post.owner_course_id IN ({','.join('?' for _ in course_ids)})"
        )
        values.extend(course_ids)
    if group_ids:
        scope_parts.append(
            f"post.owner_group_id IN ({','.join('?' for _ in group_ids)})"
        )
        values.extend(group_ids)
    cursor_clause = ""
    values.append(now)
    if cursor_public_id is not None:
        cursor_clause = (
            "AND (post.published_at, post.id) < ("
            "SELECT cursor.published_at, cursor.id FROM news_posts cursor "
            "WHERE cursor.public_id = ?) "
        )
        values.append(cursor_public_id)
    values.append(limit)
    rows = connection.execute(
        "SELECT post.id, post.public_id, post.source_type, post.source_chat_id, "
        "post.source_message_id, post.published_at, post.last_source_edited_at, "
        "revision.id AS revision_id, revision.revision_number, revision.text_plain, "
        "revision.content_json, revision.content_format, revision.rich_document_json, "
        "binding.title_cached AS channel_title "
        "FROM news_posts post "
        "JOIN news_visibility visibility ON visibility.post_id = post.id "
        "LEFT JOIN telegram_bindings binding "
        "ON binding.id = post.source_binding_id "
        "JOIN news_revisions revision ON revision.id = ("
        "SELECT latest.id FROM news_revisions latest WHERE latest.post_id = post.id "
        "ORDER BY latest.revision_number DESC LIMIT 1) "
        "WHERE visibility.state = 'visible' AND ("
        + " OR ".join(scope_parts)
        + ") AND post.published_at <= ? "
        + cursor_clause
        + "AND NOT EXISTS (SELECT 1 FROM news_media media "
        "WHERE media.revision_id = revision.id AND media.storage_status <> 'stored') "
        "ORDER BY post.published_at DESC, post.id DESC LIMIT ?",
        tuple(values),
    ).fetchall()
    return [dict(row) for row in rows]


def get_visible_post_by_public_id(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    course_ids: tuple[int, ...],
    group_ids: tuple[str, ...],
    now: str,
) -> dict[str, object] | None:
    if not course_ids and not group_ids:
        return None
    scope_parts: list[str] = []
    values: list[object] = [public_id]
    if course_ids:
        scope_parts.append(
            f"post.owner_course_id IN ({','.join('?' for _ in course_ids)})"
        )
        values.extend(course_ids)
    if group_ids:
        scope_parts.append(
            f"post.owner_group_id IN ({','.join('?' for _ in group_ids)})"
        )
        values.extend(group_ids)
    row = connection.execute(
        "SELECT post.id, post.public_id, post.source_type, post.source_chat_id, "
        "post.source_message_id, post.published_at, post.last_source_edited_at, "
        "revision.id AS revision_id, revision.revision_number, revision.text_plain, "
        "revision.content_json, revision.content_format, revision.rich_document_json, "
        "binding.title_cached AS channel_title "
        "FROM news_posts post "
        "JOIN news_visibility visibility ON visibility.post_id = post.id "
        "LEFT JOIN telegram_bindings binding "
        "ON binding.id = post.source_binding_id "
        "JOIN news_revisions revision ON revision.id = ("
        "SELECT latest.id FROM news_revisions latest WHERE latest.post_id = post.id "
        "ORDER BY latest.revision_number DESC LIMIT 1) "
        "WHERE post.public_id = ? AND visibility.state = 'visible' AND ("
        + " OR ".join(scope_parts)
        + ") AND post.published_at <= ? "
        "AND NOT EXISTS (SELECT 1 FROM news_media media "
        "WHERE media.revision_id = revision.id AND media.storage_status <> 'stored')",
        (*values, now),
    ).fetchone()
    return None if row is None else dict(row)


def list_media_for_revisions(
    connection: sqlite3.Connection, revision_ids: tuple[int, ...]
) -> list[dict[str, object]]:
    if not revision_ids:
        return []
    rows = connection.execute(
        "SELECT id, revision_id, ordinal, media_kind, public_url, mime_type, "
        "width, height FROM news_media WHERE revision_id IN ("
        + ",".join("?" for _ in revision_ids)
        + ") AND storage_status = 'stored' ORDER BY revision_id, ordinal",
        revision_ids,
    ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "find_news_source_bindings",
    "find_telegram_post",
    "find_local_news_owner",
    "get_post",
    "get_visible_post_by_public_id",
    "has_visible_local_post_due_between",
    "insert_diagnostic",
    "insert_media",
    "insert_local_post",
    "insert_revision",
    "insert_telegram_post",
    "list_media",
    "list_news_recipient_accounts",
    "news_course_public_id",
    "list_media_for_revisions",
    "list_visible_posts",
    "mark_source_deleted",
    "revision_exists",
    "touch_post",
]
