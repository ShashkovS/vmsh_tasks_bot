"""Validation and safe legacy projections for Phase-8 RichDocument v1.

The browser creates the AST with ``@puregram/rich``. This module never accepts
HTML as authority: it validates every node received by the API before deriving
plain text and the compatibility HTML projection.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from urllib.parse import urlparse


class InvalidRichDocument(ValueError):
    """A client supplied RichDocument does not satisfy the v1 contract."""


_INLINE_WRAPPERS = frozenset(
    {"bold", "italic", "underline", "strike", "mark", "spoiler", "sub", "sup"}
)
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")
_MAX_DEPTH = 16


def _fail(path: str, message: str) -> None:
    raise InvalidRichDocument(f"{path}: {message}")


def _mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _list(value: object, path: str, *, minimum: int = 0, maximum: int = 1_000) -> list[object]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail(path, f"must contain {minimum}..{maximum} items")
    return value


def _exact(value: dict[str, object], fields: set[str], path: str) -> None:
    if set(value) != fields:
        _fail(path, "has unknown or missing fields")


def is_rich_https_url(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 4_096
        or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value)
    ):
        return False
    try:
        parsed = urlparse(value)
        # Accessing ``port`` forces urllib to reject malformed numeric ports
        # that otherwise look like valid hostnames to urlparse.
        _ = parsed.port
        hostname = parsed.hostname
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(hostname)
        and not parsed.username
        and not parsed.password
    )


def _identifier(value: object, path: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _fail(path, "must be a canonical identifier")
    return value


def _text(value: object, path: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 32_768 or (nonempty and not value.strip()):
        _fail(path, "must be text")
    return value


def _validate_inline(value: object, path: str, depth: int) -> dict[str, object]:
    if depth > _MAX_DEPTH:
        _fail(path, "nesting is too deep")
    node = _mapping(value, path)
    node_type = node.get("type")
    if node_type == "text":
        _exact(node, {"type", "text"}, path)
        _text(node["text"], f"{path}.text")
    elif node_type == "code":
        _exact(node, {"type", "text"}, path)
        _text(node["text"], f"{path}.text")
    elif node_type in _INLINE_WRAPPERS:
        _exact(node, {"type", "children"}, path)
        _validate_inlines(node["children"], f"{path}.children", depth + 1)
    elif node_type == "link":
        _exact(node, {"type", "href", "children"}, path)
        if not is_rich_https_url(node["href"]):
            _fail(f"{path}.href", "must be credential-free HTTPS")
        _validate_inlines(node["children"], f"{path}.children", depth + 1)
    elif node_type == "math":
        _exact(node, {"type", "latex"}, path)
        _text(node["latex"], f"{path}.latex", nonempty=True)
    elif node_type == "footnoteRef":
        _exact(node, {"type", "id"}, path)
        _identifier(node["id"], f"{path}.id")
    else:
        _fail(path, "uses an unsupported inline node")
    return node


def _validate_inlines(value: object, path: str, depth: int) -> list[dict[str, object]]:
    return [_validate_inline(item, f"{path}[{index}]", depth) for index, item in enumerate(_list(value, path, minimum=1))]


def _validate_block(value: object, path: str, depth: int, media_ids: set[str], footnotes: set[str], refs: set[str]) -> dict[str, object]:
    if depth > _MAX_DEPTH:
        _fail(path, "nesting is too deep")
    node = _mapping(value, path)
    node_type = node.get("type")
    if node_type == "paragraph":
        _exact(node, {"type", "children"}, path)
        children = _validate_inlines(node["children"], f"{path}.children", depth)
        refs.update(str(item["id"]) for item in _walk_footnote_refs(children))
    elif node_type == "heading":
        _exact(node, {"type", "level", "children"}, path)
        if isinstance(node.get("level"), bool) or node.get("level") not in {1, 2, 3, 4, 5}:
            _fail(f"{path}.level", "must be from 1 through 5")
        children = _validate_inlines(node["children"], f"{path}.children", depth)
        refs.update(str(item["id"]) for item in _walk_footnote_refs(children))
    elif node_type == "quote":
        _exact(node, {"type", "blocks"}, path)
        _validate_blocks(node["blocks"], f"{path}.blocks", depth + 1, media_ids, footnotes, refs)
    elif node_type == "divider":
        _exact(node, {"type"}, path)
    elif node_type == "code":
        if set(node) not in ({"type", "code"}, {"type", "code", "language"}):
            _fail(path, "has unknown or missing fields")
        _text(node.get("code"), f"{path}.code")
        if "language" in node:
            language = node["language"]
            if not isinstance(language, str) or not language.strip() or len(language) > 64:
                _fail(f"{path}.language", "must be a short language name")
    elif node_type == "list":
        allowed = {"type", "ordered", "items"}
        if set(node) not in (allowed, allowed | {"start"}):
            _fail(path, "has unknown or missing fields")
        if not isinstance(node.get("ordered"), bool):
            _fail(f"{path}.ordered", "must be boolean")
        if "start" in node and (
            not isinstance(node["start"], int)
            or isinstance(node["start"], bool)
            or not 1 <= node["start"] <= 10_000
        ):
            _fail(f"{path}.start", "must be a positive integer")
        for index, item in enumerate(_list(node.get("items"), f"{path}.items", minimum=1, maximum=200)):
            children = _validate_inlines(item, f"{path}.items[{index}]", depth)
            refs.update(str(ref["id"]) for ref in _walk_footnote_refs(children))
    elif node_type == "taskList":
        _exact(node, {"type", "items"}, path)
        for index, item in enumerate(_list(node["items"], f"{path}.items", minimum=1, maximum=200)):
            task = _mapping(item, f"{path}.items[{index}]")
            _exact(task, {"checked", "children"}, f"{path}.items[{index}]")
            if not isinstance(task["checked"], bool):
                _fail(f"{path}.items[{index}].checked", "must be boolean")
            children = _validate_inlines(task["children"], f"{path}.items[{index}].children", depth)
            refs.update(str(ref["id"]) for ref in _walk_footnote_refs(children))
    elif node_type == "details":
        _exact(node, {"type", "summary", "open", "blocks"}, path)
        if not isinstance(node["open"], bool):
            _fail(f"{path}.open", "must be boolean")
        children = _validate_inlines(node["summary"], f"{path}.summary", depth)
        refs.update(str(ref["id"]) for ref in _walk_footnote_refs(children))
        _validate_blocks(node["blocks"], f"{path}.blocks", depth + 1, media_ids, footnotes, refs)
    elif node_type == "math":
        _exact(node, {"type", "latex"}, path)
        _text(node["latex"], f"{path}.latex", nonempty=True)
    elif node_type == "footnote":
        _exact(node, {"type", "id", "children"}, path)
        footnote_id = _identifier(node["id"], f"{path}.id")
        if footnote_id in footnotes:
            _fail(f"{path}.id", "duplicates a footnote")
        footnotes.add(footnote_id)
        children = _validate_inlines(node["children"], f"{path}.children", depth)
        refs.update(str(ref["id"]) for ref in _walk_footnote_refs(children))
    elif node_type == "image":
        _exact(node, {"type", "mediaId", "alt"}, path)
        if _identifier(node["mediaId"], f"{path}.mediaId") not in media_ids:
            _fail(f"{path}.mediaId", "does not exist in the media manifest")
        if not isinstance(node["alt"], str) or len(node["alt"]) > 1_000:
            _fail(f"{path}.alt", "must be alt text")
    else:
        _fail(path, "uses an unsupported block")
    return node


def _walk_footnote_refs(nodes: Iterable[dict[str, object]]) -> Iterable[dict[str, object]]:
    for node in nodes:
        if node["type"] == "footnoteRef":
            yield node
        children = node.get("children")
        if isinstance(children, list):
            yield from _walk_footnote_refs(item for item in children if isinstance(item, dict))


def _validate_blocks(value: object, path: str, depth: int, media_ids: set[str], footnotes: set[str], refs: set[str]) -> list[dict[str, object]]:
    return [_validate_block(item, f"{path}[{index}]", depth, media_ids, footnotes, refs) for index, item in enumerate(_list(value, path, minimum=1, maximum=1_000))]


def validate_rich_document(value: object) -> dict[str, object]:
    """Return the typed JSON-compatible document or raise a path-specific error."""

    document = _mapping(value, "document")
    _exact(document, {"schemaVersion", "blocks", "media"}, "document")
    if document.get("schemaVersion") != 1:
        _fail("document.schemaVersion", "must equal 1")
    media = _list(document["media"], "document.media", maximum=10)
    media_ids: set[str] = set()
    for index, item in enumerate(media):
        media_item = _mapping(item, f"document.media[{index}]")
        allowed = {"mediaId", "sourceUrl", "alt", "mimeType", "width", "height"}
        if set(media_item) not in (allowed, allowed | {"url"}):
            _fail(f"document.media[{index}]", "has unknown or missing fields")
        media_id = _identifier(media_item.get("mediaId"), f"document.media[{index}].mediaId")
        if media_id in media_ids:
            _fail(f"document.media[{index}].mediaId", "duplicates a media item")
        media_ids.add(media_id)
        if not is_rich_https_url(media_item.get("sourceUrl")):
            _fail(f"document.media[{index}].sourceUrl", "must be credential-free HTTPS")
        if "url" in media_item and not is_rich_https_url(media_item["url"]):
            _fail(f"document.media[{index}].url", "must be credential-free HTTPS")
        if not isinstance(media_item.get("alt"), str) or len(str(media_item["alt"])) > 1_000:
            _fail(f"document.media[{index}].alt", "must be alt text")
        if media_item.get("mimeType") not in {"image/webp", "image/gif"}:
            _fail(f"document.media[{index}].mimeType", "must be image/webp or image/gif")
        for dimension in ("width", "height"):
            if (
                not isinstance(media_item.get(dimension), int)
                or isinstance(media_item[dimension], bool)
                or not 1 <= int(media_item[dimension]) <= 1_920
            ):
                _fail(f"document.media[{index}].{dimension}", "must be 1..1920")
    footnotes: set[str] = set()
    refs: set[str] = set()
    _validate_blocks(document["blocks"], "document.blocks", 0, media_ids, footnotes, refs)
    for ref in refs:
        if ref not in footnotes:
            _fail("document.blocks", f"references unknown footnote {ref}")
    return document


def rich_document_plain_text(document: dict[str, object]) -> str:
    """Extract a plain-text excerpt without trusting any author-supplied HTML."""

    def inline(nodes: Iterable[object]) -> str:
        result: list[str] = []
        for raw in nodes:
            node = _mapping(raw, "inline")
            if node["type"] in {"text", "code"}:
                result.append(str(node["text"]))
            elif node["type"] == "math":
                result.append(str(node["latex"]))
            elif node["type"] == "footnoteRef":
                result.append(f"[^{node['id']}]")
            elif "children" in node:
                result.append(inline(_list(node["children"], "inline.children")))
        return "".join(result)

    def blocks(items: Iterable[object]) -> str:
        result: list[str] = []
        for raw in items:
            node = _mapping(raw, "block")
            node_type = node["type"]
            if node_type in {"paragraph", "heading", "footnote"}:
                result.append(inline(_list(node["children"], "block.children")))
            elif node_type in {"quote"}:
                result.append(blocks(_list(node["blocks"], "block.blocks")))
            elif node_type == "details":
                result.extend((inline(_list(node["summary"], "block.summary")), blocks(_list(node["blocks"], "block.blocks"))))
            elif node_type == "list":
                result.extend(inline(_list(entry, "list.item")) for entry in _list(node["items"], "list.items"))
            elif node_type == "taskList":
                result.extend(inline(_list(_mapping(entry, "task")["children"], "task.children")) for entry in _list(node["items"], "task.items"))
            elif node_type == "code":
                result.append(str(node["code"]))
            elif node_type == "math":
                result.append(str(node["latex"]))
            elif node_type == "image":
                result.append(str(node["alt"]) or "[Картинка]")
        return "\n".join(part for part in result if part)

    return blocks(_list(document["blocks"], "document.blocks"))


def rich_document_legacy_html(document: dict[str, object]) -> str:
    """Conservative readable fallback for old banner clients, derived from AST only."""

    def inline(nodes: Iterable[object]) -> str:
        output: list[str] = []
        tags = {"bold": "strong", "italic": "em", "underline": "u", "strike": "s", "mark": "mark", "spoiler": "span", "sub": "sub", "sup": "sup"}
        for raw in nodes:
            node = _mapping(raw, "inline")
            node_type = str(node["type"])
            if node_type in {"text", "code"}:
                text = html.escape(str(node["text"]))
                output.append(f"<code>{text}</code>" if node_type == "code" else text)
            elif node_type == "math":
                output.append(f"<code>{html.escape(str(node['latex']))}</code>")
            elif node_type == "footnoteRef":
                output.append(f"<sup>[{html.escape(str(node['id']))}]</sup>")
            elif node_type == "link":
                output.append(f'<a href="{html.escape(str(node["href"]), quote=True)}" rel="noopener noreferrer">{inline(_list(node["children"], "link.children"))}</a>')
            else:
                tag = tags[node_type]
                output.append(f"<{tag}>{inline(_list(node['children'], 'inline.children'))}</{tag}>")
        return "".join(output)

    def blocks(items: Iterable[object]) -> str:
        output: list[str] = []
        for raw in items:
            node = _mapping(raw, "block")
            node_type = str(node["type"])
            if node_type == "paragraph":
                output.append(
                    f"<p>{inline(_list(node['children'], 'paragraph.children'))}</p>"
                )
            elif node_type == "heading":
                output.append(
                    f"<h{node['level']}>{inline(_list(node['children'], 'heading.children'))}</h{node['level']}>"
                )
            elif node_type == "quote":
                output.append(
                    f"<blockquote>{blocks(_list(node['blocks'], 'quote.blocks'))}</blockquote>"
                )
            elif node_type == "divider":
                output.append("<hr>")
            elif node_type == "code":
                output.append(
                    f"<pre><code>{html.escape(str(node['code']))}</code></pre>"
                )
            elif node_type == "math":
                output.append(
                    f"<p><code>{html.escape(str(node['latex']))}</code></p>"
                )
            elif node_type == "list":
                tag = "ol" if node["ordered"] else "ul"
                items = "".join(
                    f"<li>{inline(_list(entry, 'list.item'))}</li>"
                    for entry in _list(node["items"], "list.items")
                )
                output.append(f"<{tag}>{items}</{tag}>")
            elif node_type == "taskList":
                items = "".join(
                    f"<li>{'☑' if _mapping(entry, 'task')['checked'] else '☐'} "
                    f"{inline(_list(_mapping(entry, 'task')['children'], 'task.children'))}</li>"
                    for entry in _list(node["items"], "tasks")
                )
                output.append(f"<ul>{items}</ul>")
            elif node_type == "details":
                output.append(
                    f"<details><summary>{inline(_list(node['summary'], 'details.summary'))}</summary>"
                    f"{blocks(_list(node['blocks'], 'details.blocks'))}</details>"
                )
            elif node_type == "footnote":
                output.append(
                    f"<p><sup>[{html.escape(str(node['id']))}]</sup> "
                    f"{inline(_list(node['children'], 'footnote.children'))}</p>"
                )
            elif node_type == "image":
                output.append(f"<p>{html.escape(str(node['alt']) or 'Картинка')}</p>")
        return "".join(output)

    return blocks(_list(document["blocks"], "document.blocks"))


__all__ = ["InvalidRichDocument", "is_rich_https_url", "rich_document_legacy_html", "rich_document_plain_text", "validate_rich_document"]
