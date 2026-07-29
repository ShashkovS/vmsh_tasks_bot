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


__all__ = ["iter_export_updates"]
