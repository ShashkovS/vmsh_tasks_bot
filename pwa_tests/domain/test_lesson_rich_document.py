"""Parity-critical validation for the lesson-only rich-document extension."""

from __future__ import annotations

import pytest

from models.pwa.rich_document import InvalidRichDocument, validate_rich_document
from models.pwa.lesson_rich_document import (
    lesson_video_embed_url,
    validate_lesson_rich_document,
)


def _document(video: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "blocks": [
            {"type": "paragraph", "children": [{"type": "text", "text": "До"}]},
            video,
            {"type": "paragraph", "children": [{"type": "text", "text": "После"}]},
        ],
        "media": [],
    }


def test_lesson_document_accepts_normalized_youtube_and_vk_videos():
    youtube = {
        "type": "video",
        "provider": "youtube",
        "videoId": "FTXGKbAk9To",
        "startSeconds": 90,
        "title": "Разбор",
    }
    vk = {
        "type": "video",
        "provider": "vk",
        "ownerId": "-241691838",
        "videoId": "456239017",
        "accessHash": None,
        "hd": 2,
        "title": None,
    }

    assert validate_lesson_rich_document(_document(youtube))["blocks"][1] == youtube
    assert validate_lesson_rich_document(_document(vk))["blocks"][1] == vk
    assert lesson_video_embed_url(vk) == (
        "https://vkvideo.ru/video_ext.php?oid=-241691838&id=456239017&hd=2"
    )


@pytest.mark.parametrize(
    "video",
    (
        {"type": "video", "provider": "youtube", "videoId": "too-short", "startSeconds": 0, "title": None},
        {"type": "video", "provider": "youtube", "videoId": "FTXGKbAk9To", "startSeconds": -1, "title": None},
        {"type": "video", "provider": "vk", "ownerId": "0", "videoId": "1", "accessHash": None, "hd": 2, "title": None},
        {"type": "video", "provider": "vk", "ownerId": "-1", "videoId": "1", "accessHash": "bad hash", "hd": 2, "title": None},
    ),
)
def test_lesson_document_rejects_untrusted_video_fields(video: dict[str, object]):
    with pytest.raises(InvalidRichDocument):
        validate_lesson_rich_document(_document(video))


def test_existing_news_validator_still_rejects_video_nodes():
    with pytest.raises(InvalidRichDocument):
        validate_rich_document(_document({
            "type": "video",
            "provider": "youtube",
            "videoId": "FTXGKbAk9To",
            "startSeconds": 0,
            "title": None,
        }))
