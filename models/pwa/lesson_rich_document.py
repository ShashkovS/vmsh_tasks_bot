"""Safe LessonBlock RichDocument validation, including normalized video blocks.

Lesson blocks deliberately extend the Phase-8 document format without making
video an accepted news or banner node.  See ``vmshpwa/docs/lesson-blocks.md``.
"""

from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlencode

from models.pwa.rich_document import InvalidRichDocument, validate_rich_document

def _fail(message: str) -> None:
    raise InvalidRichDocument(f"document.blocks: {message}")


def _nonempty(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        _fail(f"{field} is invalid")
    return value.strip()


def validate_lesson_video(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or value.get("type") != "video":
        _fail("video node is invalid")
    provider = value.get("provider")
    title = value.get("title")
    if title is not None and (not isinstance(title, str) or len(title.strip()) > 200):
        _fail("video title is invalid")
    if provider == "youtube":
        allowed = {"type", "provider", "videoId", "startSeconds", "title"}
        video_id = value.get("videoId")
        start = value.get("startSeconds")
        if set(value) != allowed or not isinstance(video_id, str) or len(video_id) != 11 or not all(c.isascii() and (c.isalnum() or c in "_-") for c in video_id):
            _fail("YouTube video ID is invalid")
        if not isinstance(start, int) or isinstance(start, bool) or not 0 <= start <= 604800:
            _fail("YouTube start time is invalid")
        return {"type": "video", "provider": "youtube", "videoId": video_id, "startSeconds": start, "title": None if title is None else title.strip()}
    if provider == "vk":
        allowed = {"type", "provider", "ownerId", "videoId", "accessHash", "hd", "title"}
        owner, video, access_hash, hd = value.get("ownerId"), value.get("videoId"), value.get("accessHash"), value.get("hd")
        def decimal(item: object, signed: bool = False) -> bool:
            return isinstance(item, str) and 1 <= len(item) <= 20 and ((item[1:].isdigit() and item.startswith("-")) if signed else item.isdigit())
        if set(value) != allowed or not decimal(owner, True) or str(owner) in {"0", "-0"} or not decimal(video) or int(str(video)) < 1:
            _fail("VK video identifier is invalid")
        if access_hash is not None and (not isinstance(access_hash, str) or not 1 <= len(access_hash) <= 256 or not all(c.isascii() and (c.isalnum() or c in "_-") for c in access_hash)):
            _fail("VK access hash is invalid")
        if hd not in {0, 1, 2, 3}:
            _fail("VK quality is invalid")
        return {"type": "video", "provider": "vk", "ownerId": owner, "videoId": video, "accessHash": access_hash, "hd": hd, "title": None if title is None else title.strip()}
    _fail("video provider is invalid")


def lesson_video_embed_url(video: dict[str, object]) -> str:
    checked = validate_lesson_video(video)
    if checked["provider"] == "youtube":
        return "https://www.youtube.com/embed/" + str(checked["videoId"]) + "?" + urlencode({"start": checked["startSeconds"]})
    query = {"oid": checked["ownerId"], "id": checked["videoId"], "hd": checked["hd"]}
    if checked["accessHash"] is not None:
        query["hash"] = checked["accessHash"]
    return "https://vkvideo.ru/video_ext.php?" + urlencode(query)


def validate_lesson_rich_document(value: object) -> dict[str, object]:
    """Validate normal RichDocument nodes plus root-level provider video nodes."""
    if not isinstance(value, dict) or set(value) != {"schemaVersion", "blocks", "media"}:
        _fail("document must contain schemaVersion, blocks and media")
    blocks = value.get("blocks")
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 1_000:
        _fail("block count is invalid")
    videos = 0
    sanitized = deepcopy(value)
    sanitized_blocks: list[object] = []
    result_blocks: list[object] = []
    for item in blocks:
        if isinstance(item, dict) and item.get("type") == "video":
            videos += 1
            result_blocks.append(validate_lesson_video(item))
            sanitized_blocks.append({"type": "divider"})
        else:
            result_blocks.append(item)
            sanitized_blocks.append(item)
    if videos > 20:
        _fail("at most 20 videos are allowed")
    sanitized["blocks"] = sanitized_blocks
    validated = validate_rich_document(sanitized)
    return {"schemaVersion": 1, "blocks": result_blocks, "media": validated["media"]}


__all__ = ["lesson_video_embed_url", "validate_lesson_rich_document", "validate_lesson_video"]
