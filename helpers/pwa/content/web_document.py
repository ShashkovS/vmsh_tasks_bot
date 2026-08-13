"""Pure adapter from the private compiler AST to the browser wire contract.

The internal :class:`DocumentAst` contains all semantic branches and source
positions and must never cross the API boundary.  This module projects exactly
one requested material into ``WebContentDocument v1`` as defined by
``vmshpwa/packages/contracts/src/content.ts``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .model import (
    AnnouncementKind,
    AnnouncementNode,
    BlockNode,
    CodeNode,
    ContentRole,
    DocumentAst,
    EmphasisNode,
    FigureNode,
    HeadingNode,
    InlineNode,
    LinkNode,
    ListNode,
    MathNode,
    ParagraphNode,
    ProblemNode,
    StrongNode,
    SubpartNode,
    TableNode,
    TextNode,
)


WEB_CONTENT_CONTRACT_VERSION = 1
_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_WEB_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "image/svg+xml",
    "image/webp",
}


class WebDocumentError(ValueError):
    """Raised when an AST cannot be represented by the strict wire contract."""


@dataclass(frozen=True)
class WebAssetDescriptor:
    """Published asset metadata required for an ``available`` figure."""

    asset_id: str
    content_sha256: str
    src: str
    media_type: str
    width: int
    height: int


def _bounded(value: str, maximum: int, field: str, *, required: bool) -> str | None:
    normalized = value.strip()
    if not normalized:
        if required:
            raise WebDocumentError(f"{field} must not be empty")
        return None
    if len(normalized) > maximum:
        raise WebDocumentError(f"{field} exceeds {maximum} characters")
    return normalized


def _is_web_asset_url(value: str) -> bool:
    if value != value.strip() or any(
        character in value for character in "\x00\r\n\t\\"
    ):
        return False
    if value.startswith("/") and not value.startswith("//"):
        return True
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )


def _is_web_link_url(value: str) -> bool:
    if value != value.strip() or any(
        character in value for character in "\x00\r\n\t\\"
    ):
        return False
    if re.fullmatch(r"#[a-z][a-z0-9._:-]*", value):
        return True
    if _is_web_asset_url(value):
        return True
    parsed = urlsplit(value)
    return parsed.scheme == "mailto" and bool(parsed.path)


def _asset(descriptor: WebAssetDescriptor) -> dict[str, Any]:
    if not all(
        isinstance(value, str)
        for value in (
            descriptor.asset_id,
            descriptor.content_sha256,
            descriptor.src,
            descriptor.media_type,
        )
    ):
        raise WebDocumentError("asset text metadata has an invalid type")
    if _PUBLIC_ID.fullmatch(descriptor.asset_id) is None:
        raise WebDocumentError("asset_id is not a canonical public ID")
    if _SHA256.fullmatch(descriptor.content_sha256) is None:
        raise WebDocumentError("asset content_sha256 is invalid")
    if len(descriptor.src) > 4_096:
        raise WebDocumentError("asset src exceeds 4096 characters")
    if not _is_web_asset_url(descriptor.src):
        raise WebDocumentError(
            "asset src is not root-relative or credential-free HTTPS"
        )
    if descriptor.media_type not in _WEB_MEDIA_TYPES:
        raise WebDocumentError(
            "asset media_type is not supported by WebContentDocument"
        )
    if type(descriptor.width) is not int or type(descriptor.height) is not int:
        raise WebDocumentError("asset dimensions must be integers")
    if not 1 <= descriptor.width <= 20_000 or not 1 <= descriptor.height <= 20_000:
        raise WebDocumentError("asset dimensions are outside 1..20000")
    return {
        "status": "available",
        "assetId": descriptor.asset_id,
        "contentSha256": descriptor.content_sha256,
        "src": descriptor.src,
        "mediaType": descriptor.media_type,
        "width": descriptor.width,
        "height": descriptor.height,
    }


def validate_web_asset_descriptor(descriptor: WebAssetDescriptor) -> None:
    """Validate one descriptor before any renderer consumes its public URL."""

    if not isinstance(descriptor, WebAssetDescriptor):
        raise WebDocumentError("asset descriptor has an invalid type")
    _asset(descriptor)


def _inline(nodes: Sequence[InlineNode]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        if isinstance(node, TextNode):
            # Zod bounds individual tokens. Splitting does not alter rendering.
            text = node.text
            result.extend(
                {"type": "text", "value": text[index : index + 32_768]}
                for index in range(0, len(text), 32_768)
            )
        elif isinstance(node, MathNode):
            latex = _bounded(node.latex, 8_192, "inline math latex", required=True)
            assert latex is not None
            result.append({"type": "math", "latex": latex})
        elif isinstance(node, CodeNode):
            if len(node.text) > 8_192:
                raise WebDocumentError("inline code exceeds 8192 characters")
            result.append({"type": "code", "value": node.text})
        elif isinstance(node, StrongNode):
            result.append({"type": "strong", "children": _inline(node.children)})
        elif isinstance(node, EmphasisNode):
            result.append({"type": "emphasis", "children": _inline(node.children)})
        elif isinstance(node, LinkNode):
            children = _inline(node.children)
            if not children:
                raise WebDocumentError("web links require visible children")
            if not _is_web_link_url(node.href):
                raise WebDocumentError("web link URL is outside the contract allowlist")
            result.append({"type": "link", "href": node.href, "children": children})
    if len(result) > 1_000:
        raise WebDocumentError("inline node list exceeds 1000 items")
    return result


def _paragraph_blocks(node: ParagraphNode) -> list[dict[str, Any]]:
    """Promote display formulas out of paragraphs for semantic rendering."""

    blocks: list[dict[str, Any]] = []
    buffered: list[InlineNode] = []

    def flush() -> None:
        nonlocal buffered
        if any(
            not isinstance(item, TextNode) or bool(item.text.strip())
            for item in buffered
        ):
            blocks.append({"type": "paragraph", "children": _inline(buffered)})
        buffered = []

    for child in node.children:
        if isinstance(child, MathNode) and child.display:
            flush()
            latex = _bounded(child.latex, 16_384, "formula latex", required=True)
            blocks.append({"type": "formula", "latex": latex})
        else:
            buffered.append(child)
    flush()
    return blocks


def _blocks(
    nodes: Sequence[BlockNode],
    *,
    assets: Mapping[str, WebAssetDescriptor],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        if isinstance(node, ParagraphNode):
            result.extend(_paragraph_blocks(node))
        elif isinstance(node, HeadingNode):
            children = _inline(node.children)
            if children:
                result.append(
                    {
                        "type": "heading",
                        "level": max(2, min(node.level, 4)),
                        "children": children,
                    }
                )
        elif isinstance(node, ListNode):
            if len(node.items) > 1_000:
                raise WebDocumentError("list exceeds 1000 items")
            items = [
                _blocks(item.children, assets=assets)
                or [{"type": "paragraph", "children": []}]
                for item in node.items
            ]
            if any(len(item) > 100 for item in items):
                raise WebDocumentError("list item exceeds 100 blocks")
            if items:
                result.append({"type": "list", "ordered": node.ordered, "items": items})
        elif isinstance(node, TableNode):
            if len(node.rows) > 200:
                raise WebDocumentError("table exceeds 200 rows")
            if any(len(row.cells) > 20 for row in node.rows):
                raise WebDocumentError("table exceeds 20 columns")
            rows = [
                [
                    {"type": "data", "children": _inline(cell.children)}
                    for cell in row.cells
                ]
                for row in node.rows
                if row.cells
            ]
            if rows:
                result.append({"type": "table", "rows": rows})
        elif isinstance(node, FigureNode):
            alt = _bounded(node.alt_text, 2_000, "figure alt", required=True)
            descriptor = assets.get(node.logical_name)
            asset = (
                _asset(descriptor)
                if descriptor is not None
                else {
                    "status": "missing",
                    "logicalName": _bounded(
                        node.logical_name,
                        2_000,
                        "figure logicalName",
                        required=True,
                    ),
                }
            )
            result.append({"type": "figure", "alt": alt, "asset": asset})
        elif isinstance(node, SubpartNode):
            blocks = _blocks(node.children, assets=assets)
            if blocks:
                result.append(
                    {
                        "type": "subpart",
                        "label": _bounded(
                            node.label, 2_000, "subpart label", required=True
                        ),
                        "blocks": blocks,
                    }
                )
        elif isinstance(node, AnnouncementNode):
            blocks = _blocks(node.children, assets=assets)
            if blocks:
                result.append(
                    {
                        "type": "callout",
                        "kind": (
                            "note"
                            if node.kind is AnnouncementKind.REGULAR
                            else "theorem"
                        ),
                        **(
                            {}
                            if node.kind is AnnouncementKind.REGULAR
                            else {"title": "Важно"}
                        ),
                        "blocks": blocks,
                    }
                )
    if len(result) > 2_000:
        raise WebDocumentError("block list exceeds 2000 items")
    return result


def _selected_blocks(problem: ProblemNode, role: ContentRole) -> tuple[BlockNode, ...]:
    if role is ContentRole.CONDITION:
        return problem.statement + problem.trailing
    if role is ContentRole.HINT:
        return problem.hint
    if role is ContentRole.SOLUTION:
        return problem.statement + problem.trailing + problem.answer + problem.solution
    raise WebDocumentError("full_preview has no browser wire representation")


def render_web_document(
    document: DocumentAst,
    *,
    role: ContentRole,
    revision_id: str | None = None,
    title: str | None = None,
    assets: Mapping[str, WebAssetDescriptor] | None = None,
) -> dict[str, Any]:
    """Return a JSON-ready ``WebContentDocument v1`` projection.

    ``revision_id`` is storage/publication identity and is never derived from a
    source hash.  Before persistence it is legitimately ``None`` in preview and
    characterization flows.
    """

    if role is ContentRole.FULL_PREVIEW:
        raise WebDocumentError("full_preview is intentionally not a wire materialKind")
    if revision_id is not None and _PUBLIC_ID.fullmatch(revision_id) is None:
        raise WebDocumentError("revision_id is not a canonical public ID")
    if _SHA256.fullmatch(document.source_sha256) is None:
        raise WebDocumentError("document source_sha256 is invalid")
    mapping = assets or {}
    problems = []
    for problem in document.problems:
        blocks = _blocks(_selected_blocks(problem, role), assets=mapping)
        if not blocks:
            continue
        problems.append(
            {
                "ordinal": problem.ordinal,
                "sourceItem": _bounded(
                    problem.source_item or "", 80, "problem sourceItem", required=False
                ),
                "title": _bounded(
                    problem.source_title or "", 500, "problem title", required=False
                ),
                "blocks": blocks,
            }
        )
    if len(problems) > 2_000:
        raise WebDocumentError("problem list exceeds 2000 items")
    return {
        "contractVersion": WEB_CONTENT_CONTRACT_VERSION,
        "revisionId": revision_id,
        "sourceSha256": document.source_sha256,
        "materialKind": role.value,
        "title": _bounded(title or "", 500, "document title", required=False),
        "introduction": _blocks(document.introduction, assets=mapping),
        "problems": problems,
    }
