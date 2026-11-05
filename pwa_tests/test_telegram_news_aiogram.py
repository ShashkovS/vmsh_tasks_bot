from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from helpers.pwa.telegram_news import update_from_aiogram_messages


def _message(
    message_id: int,
    *,
    text: str | None = None,
    entities: list[object] | None = None,
    photo: bool = False,
):
    return SimpleNamespace(
        message_id=message_id,
        chat=SimpleNamespace(id=-100179),
        date=datetime(2026, 7, 29, 16, tzinfo=UTC),
        edit_date=None,
        media_group_id="album-41" if photo else None,
        text=text,
        caption=None,
        entities=entities,
        caption_entities=None,
        photo=(
            [SimpleNamespace(file_id=f"photo-{message_id}", width=1200, height=900)]
            if photo
            else None
        ),
        video=None,
        animation=None,
        audio=None,
        voice=None,
        document=None,
    )


def test_aiogram_snapshot_preserves_nested_entities_and_utf16_offsets():
    # The emoji occupies two UTF-16 code units. Bold covers everything, while
    # the link covers only the final Cyrillic character.
    message = _message(
        41,
        text="A😀Б",
        entities=[
            SimpleNamespace(type="bold", offset=0, length=4, url=None),
            SimpleNamespace(
                type="text_link", offset=3, length=1, url="https://example.test"
            ),
        ],
    )
    update = update_from_aiogram_messages([message])
    assert update["content"] == [
        {"type": "plain", "text": "A😀", "marks": [{"type": "bold"}]},
        {
            "type": "plain",
            "text": "Б",
            "marks": [
                {"type": "bold"},
                {"type": "link", "href": "https://example.test"},
            ],
        },
    ]


def test_aiogram_album_is_ordered_and_uses_its_single_caption():
    second = _message(42, photo=True)
    first = _message(41, text="Альбом", photo=True)
    update = update_from_aiogram_messages([second, first])
    assert update["message_id"] == 41
    assert update["media_group_id"] == "album-41"
    assert [item["source_file_id"] for item in update["media"]] == [
        "photo-41",
        "photo-42",
    ]
    assert update["content"] == [{"type": "plain", "text": "Альбом"}]
