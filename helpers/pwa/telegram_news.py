"""Normalize Telegram Desktop export messages for the news ingest boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterator


_ENTITY_TYPES = {
    "plain": "plain",
    "bold": "bold",
    "italic": "italic",
    "underline": "underline",
    "strikethrough": "strike",
    "code": "code",
    "text_link": "link",
    "email": "link",
    "spoiler": "spoiler",
}


def _entity_type(entity: object) -> str | None:
    value = getattr(entity, "type", None)
    if hasattr(value, "value"):
        value = value.value
    return value if isinstance(value, str) else None


def _utf16_boundaries(text: str) -> dict[int, int]:
    boundaries = {0: 0}
    offset = 0
    for index, character in enumerate(text, start=1):
        offset += len(character.encode("utf-16-le")) // 2
        boundaries[offset] = index
    return boundaries


def _message_content(message: object) -> list[dict[str, object]]:
    text = getattr(message, "text", None) or getattr(message, "caption", None)
    if not isinstance(text, str) or not text:
        return []
    entities = getattr(message, "entities", None) or getattr(
        message, "caption_entities", None
    )
    if not entities:
        return [{"type": "plain", "text": text}]

    marks: list[tuple[int, int, dict[str, str]]] = []
    boundaries = _utf16_boundaries(text)
    for entity in entities:
        source_type = _entity_type(entity)
        offset = getattr(entity, "offset", None)
        length = getattr(entity, "length", None)
        if (
            source_type is None
            or not isinstance(offset, int)
            or not isinstance(length, int)
            or length <= 0
        ):
            continue
        end = offset + length
        if offset not in boundaries or end not in boundaries:
            raise ValueError("Telegram entity splits a Unicode character")
        mark_type = _ENTITY_TYPES.get(source_type)
        mark: dict[str, str]
        if mark_type is None:
            mark = {"type": "unsupported", "unsupportedType": source_type}
        else:
            mark = {"type": mark_type}
        if source_type == "text_link" and isinstance(getattr(entity, "url", None), str):
            mark["href"] = entity.url
        elif source_type == "email":
            start_index, end_index = boundaries[offset], boundaries[end]
            mark["href"] = f"mailto:{text[start_index:end_index]}"
        marks.append((offset, end, mark))

    points = sorted(
        {0, max(boundaries), *(value for mark in marks for value in mark[:2])}
    )
    result: list[dict[str, object]] = []
    for start, end in zip(points, points[1:]):
        if start == end:
            continue
        segment = text[boundaries[start] : boundaries[end]]
        active_marks = [
            mark for left, right, mark in marks if left <= start and end <= right
        ]
        node: dict[str, object] = {"type": "plain", "text": segment}
        if active_marks:
            node["marks"] = active_marks
        result.append(node)
    return result


def _message_media(message: object) -> dict[str, object] | None:
    message_id = getattr(message, "message_id", None)
    photo = getattr(message, "photo", None)
    if photo:
        largest = photo[-1]
        return {
            "kind": "image",
            "source_message_id": message_id,
            "source_file_id": largest.file_id,
            "mime_type": "image/jpeg",
            "width": getattr(largest, "width", None),
            "height": getattr(largest, "height", None),
            "storage_status": "pending",
        }
    for attribute, kind, default_mime in (
        ("video", "video", "video/mp4"),
        ("animation", "video", "video/mp4"),
        ("audio", "audio", "audio/mpeg"),
        ("voice", "audio", "audio/ogg"),
        ("document", "document", "application/octet-stream"),
    ):
        media = getattr(message, attribute, None)
        if media is not None:
            return {
                "kind": kind,
                "source_message_id": message_id,
                "source_file_id": media.file_id,
                "mime_type": getattr(media, "mime_type", None) or default_mime,
                "width": getattr(media, "width", None),
                "height": getattr(media, "height", None),
                "storage_status": "pending",
            }
    return None


def _iso(value: object) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def update_from_aiogram_messages(messages: list[object]) -> dict[str, object]:
    """Normalize one channel post or one complete media group."""

    if not messages:
        raise ValueError("Telegram news snapshot is empty")
    ordered = sorted(messages, key=lambda message: int(message.message_id))
    first = ordered[0]
    chat = getattr(first, "chat", None)
    chat_id = getattr(chat, "id", None)
    message_id = getattr(first, "message_id", None)
    published_at = _iso(getattr(first, "date", None))
    if (
        not isinstance(chat_id, int)
        or not isinstance(message_id, int)
        or published_at is None
    ):
        raise ValueError("Telegram channel identity is incomplete")
    content: list[dict[str, object]] = []
    for message in ordered:
        content = _message_content(message)
        if content:
            break
    media = [
        item for message in ordered if (item := _message_media(message)) is not None
    ]
    source_payload = []
    for message in ordered:
        dump = getattr(message, "model_dump", None)
        source_payload.append(
            dump(mode="json", exclude_none=True)
            if callable(dump)
            else {"message_id": message.message_id}
        )
    edited_values = [
        value
        for message in ordered
        if (value := _iso(getattr(message, "edit_date", None))) is not None
    ]
    media_group_id = getattr(first, "media_group_id", None)
    return {
        "chat_id": chat_id,
        "message_id": message_id,
        "media_group_id": str(media_group_id) if media_group_id is not None else None,
        "published_at": published_at,
        "edited_at": max(edited_values) if edited_values else None,
        "deleted": False,
        "content": content,
        "media": media,
        "source_payload": {"messages": source_payload},
    }


def _timestamp(value: object) -> str:
    if not isinstance(value, str) or not value.isdigit():
        raise ValueError("Telegram export timestamp is missing")
    return datetime.fromtimestamp(int(value), UTC).isoformat().replace("+00:00", "Z")


def _content(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    for message in messages:
        entities = message.get("text_entities")
        if isinstance(entities, list) and entities:
            result: list[dict[str, object]] = []
            for entity in entities:
                if not isinstance(entity, dict) or not isinstance(
                    entity.get("text"), str
                ):
                    continue
                source_type = entity.get("type")
                mapped_type = (
                    _ENTITY_TYPES.get(source_type)
                    if isinstance(source_type, str)
                    else None
                )
                node: dict[str, object] = {
                    "type": mapped_type or "plain",
                    "text": entity["text"],
                }
                if source_type == "text_link" and isinstance(entity.get("href"), str):
                    node["href"] = entity["href"]
                elif source_type == "email":
                    node["href"] = f"mailto:{entity['text']}"
                elif mapped_type is None and isinstance(source_type, str):
                    node["unsupportedType"] = source_type
                result.append(node)
            return result
        text = message.get("text")
        if isinstance(text, str) and text:
            return [{"type": "plain", "text": text}]
    return []


def _media(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for message in messages:
        photo = message.get("photo")
        if not isinstance(photo, str):
            continue
        result.append(
            {
                "kind": "image",
                "source_message_id": message.get("id"),
                "source_file_id": photo,
                "mime_type": "image/jpeg",
                "width": message.get("width"),
                "height": message.get("height"),
                "storage_status": "pending",
            }
        )
    return result


def _update(
    messages: list[dict[str, object]], *, chat_id: int, media_group_id: str | None
) -> dict[str, object]:
    first = messages[0]
    edited_values = [
        _timestamp(message["edited_unixtime"])
        for message in messages
        if message.get("edited_unixtime") is not None
    ]
    return {
        "chat_id": chat_id,
        "message_id": first["id"],
        "media_group_id": media_group_id,
        "published_at": _timestamp(first["date_unixtime"]),
        "edited_at": max(edited_values) if edited_values else None,
        "deleted": False,
        "content": _content(messages),
        "media": _media(messages),
        "source_payload": {"exportMessages": messages},
    }


def iter_export_updates(
    export: dict[str, object], *, chat_id: int
) -> Iterator[dict[str, object]]:
    """Yield deterministic post snapshots from a Telegram Desktop export.

    Desktop exports omit `media_group_id`. Consecutive photos with the same
    Unix timestamp are treated as one album and receive an import-only key.
    The eventual import command must preview this inference before committing.
    """

    messages = export.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Telegram export messages are missing")
    index = 0
    while index < len(messages):
        message = messages[index]
        index += 1
        if not isinstance(message, dict) or message.get("type") != "message":
            continue
        batch = [message]
        if isinstance(message.get("photo"), str):
            while index < len(messages):
                next_message = messages[index]
                if (
                    not isinstance(next_message, dict)
                    or next_message.get("type") != "message"
                    or not isinstance(next_message.get("photo"), str)
                    or next_message.get("date_unixtime") != message.get("date_unixtime")
                ):
                    break
                batch.append(next_message)
                index += 1
        media_group_id = None
        if len(batch) > 1:
            media_group_id = f"export:{message['date_unixtime']}:{message['id']}"
        yield _update(batch, chat_id=chat_id, media_group_id=media_group_id)


__all__ = ["iter_export_updates", "update_from_aiogram_messages"]
