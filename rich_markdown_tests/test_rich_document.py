"""RichDocument v1 validation golden boundaries (Phase 8 Rich Markdown)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "rich_document_for_test",
    Path(__file__).parents[1] / "models" / "pwa" / "rich_document.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

InvalidRichDocument = _MODULE.InvalidRichDocument
rich_document_legacy_html = _MODULE.rich_document_legacy_html
rich_document_plain_text = _MODULE.rich_document_plain_text
validate_rich_document = _MODULE.validate_rich_document


def _document() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "media": [],
        "blocks": [
            {
                "type": "paragraph",
                "children": [
                    {
                        "type": "bold",
                        "children": [
                            {"type": "text", "text": "Bold "},
                            {
                                "type": "italic",
                                "children": [{"type": "text", "text": "italic"}],
                            },
                        ],
                    },
                    {"type": "text", "text": " and "},
                    {"type": "math", "latex": "x^2 + y^2"},
                    {"type": "footnoteRef", "id": "note"},
                ],
            },
            {
                "type": "footnote",
                "id": "note",
                "children": [{"type": "text", "text": "One line"}],
            },
            {"type": "math", "latex": "E = mc^2"},
        ],
    }


def test_rich_document_validates_nested_ast_and_derives_safe_projections() -> None:
    document = validate_rich_document(_document())
    assert (
        rich_document_plain_text(document)
        == "Bold italic and x^2 + y^2[^note]\nOne line\nE = mc^2"
    )
    html = rich_document_legacy_html(document)
    assert "<strong>Bold <em>italic</em></strong>" in html
    assert "javascript:" not in html


def test_rich_document_rejects_unknown_media_and_unsafe_link() -> None:
    document = _document()
    document["blocks"] = [{"type": "image", "mediaId": "missing", "alt": ""}]
    with pytest.raises(InvalidRichDocument, match="does not exist"):
        validate_rich_document(document)

    document = _document()
    document["blocks"] = [
        {
            "type": "paragraph",
            "children": [
                {
                    "type": "link",
                    "href": "http://example.test",
                    "children": [{"type": "text", "text": "unsafe"}],
                }
            ],
        }
    ]
    with pytest.raises(InvalidRichDocument, match="credential-free HTTPS"):
        validate_rich_document(document)

def test_rich_document_keeps_python_validation_as_strict_as_json_contract() -> None:
    document = _document()
    document["blocks"] = [
        {
            "type": "heading",
            "level": True,
            "children": [{"type": "text", "text": "not a number"}],
        }
    ]
    with pytest.raises(InvalidRichDocument, match="1 through 5"):
        validate_rich_document(document)

    document = _document()
    document["media"] = [
        {
            "mediaId": "picture",
            "sourceUrl": "https://example.test:bad-port/image.png",
            "alt": "",
            "mimeType": "image/webp",
            "width": True,
            "height": 1,
        }
    ]
    with pytest.raises(InvalidRichDocument, match="credential-free HTTPS"):
        validate_rich_document(document)

    document["media"][0]["sourceUrl"] = "https://example.test/image.png"
    with pytest.raises(InvalidRichDocument, match="must be 1..1920"):
        validate_rich_document(document)
