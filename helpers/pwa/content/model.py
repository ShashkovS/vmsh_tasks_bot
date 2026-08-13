"""Typed, deterministic representation of educational LaTeX content.

The governing contract is ``vmshpwa/docs/latex-content-pipeline.md``.  The
types in this module deliberately contain no database, storage or Telegram
runtime dependencies: a source revision can be parsed and fingerprinted in a
pure process before any external side effect is considered.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import Any, TypeAlias


class SourceEncoding(StrEnum):
    UTF8 = "utf-8"
    UTF8_BOM = "utf-8-sig"
    WINDOWS_1251 = "windows-1251"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ContentRole(StrEnum):
    CONDITION = "condition"
    HINT = "hint"
    SOLUTION = "solution"
    FULL_PREVIEW = "full_preview"


class AnnouncementKind(StrEnum):
    REGULAR = "regular"
    IMPORTANT = "important"


@dataclass(frozen=True)
class SourcePosition:
    """One-based human position plus a zero-based Unicode text offset."""

    offset: int
    line: int
    column: int


@dataclass(frozen=True)
class SourceSpan:
    source_name: str
    start: SourcePosition
    end: SourcePosition


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    span: SourceSpan
    recovery: str | None = None


@dataclass(frozen=True)
class DecodedSource:
    source_name: str
    raw_sha256: str
    raw_size_bytes: int
    encoding: SourceEncoding
    text: str


@dataclass(frozen=True)
class TextNode:
    span: SourceSpan
    text: str


@dataclass(frozen=True)
class MathNode:
    span: SourceSpan
    latex: str
    display: bool


@dataclass(frozen=True)
class StrongNode:
    span: SourceSpan
    children: tuple["InlineNode", ...]


@dataclass(frozen=True)
class EmphasisNode:
    span: SourceSpan
    children: tuple["InlineNode", ...]


@dataclass(frozen=True)
class CodeNode:
    span: SourceSpan
    text: str


@dataclass(frozen=True)
class LinkNode:
    span: SourceSpan
    href: str
    children: tuple["InlineNode", ...]


InlineNode: TypeAlias = (
    TextNode | MathNode | StrongNode | EmphasisNode | CodeNode | LinkNode
)


@dataclass(frozen=True)
class ParagraphNode:
    span: SourceSpan
    children: tuple[InlineNode, ...]


@dataclass(frozen=True)
class HeadingNode:
    span: SourceSpan
    level: int
    children: tuple[InlineNode, ...]


@dataclass(frozen=True)
class ListItemNode:
    span: SourceSpan
    children: tuple["BlockNode", ...]


@dataclass(frozen=True)
class ListNode:
    span: SourceSpan
    ordered: bool
    items: tuple[ListItemNode, ...]


@dataclass(frozen=True)
class TableCellNode:
    span: SourceSpan
    children: tuple[InlineNode, ...]


@dataclass(frozen=True)
class TableRowNode:
    span: SourceSpan
    cells: tuple[TableCellNode, ...]


@dataclass(frozen=True)
class TableNode:
    span: SourceSpan
    rows: tuple[TableRowNode, ...]


class FigureKind(StrEnum):
    ASSET = "asset"
    TIKZ = "tikz"


@dataclass(frozen=True)
class FigureNode:
    span: SourceSpan
    kind: FigureKind
    logical_name: str
    content_sha256: str | None
    width_hint: str | None
    float_hint: str | None
    alt_text: str
    tikz_source: str | None = None


@dataclass(frozen=True)
class SubpartNode:
    span: SourceSpan
    label: str
    children: tuple["BlockNode", ...]


@dataclass(frozen=True)
class AnnouncementNode:
    span: SourceSpan
    kind: AnnouncementKind
    children: tuple["BlockNode", ...]


BlockNode: TypeAlias = (
    ParagraphNode
    | HeadingNode
    | ListNode
    | TableNode
    | FigureNode
    | SubpartNode
    | AnnouncementNode
)


@dataclass(frozen=True)
class ProblemNode:
    span: SourceSpan
    ordinal: int
    source_item: str | None
    source_title: str | None
    problem_type: int
    statement: tuple[BlockNode, ...]
    trailing: tuple[BlockNode, ...]
    answer: tuple[BlockNode, ...]
    hint: tuple[BlockNode, ...]
    solution: tuple[BlockNode, ...]


@dataclass(frozen=True)
class DocumentAst:
    schema_version: int
    source_name: str
    source_sha256: str
    source_encoding: SourceEncoding
    introduction: tuple[BlockNode, ...]
    problems: tuple[ProblemNode, ...]


@dataclass(frozen=True)
class ContentDerivative:
    kind: str
    renderer_version: str
    content: str
    sha256: str


@dataclass(frozen=True)
class CompileResult:
    source: DecodedSource
    role: ContentRole
    ast: DocumentAst
    diagnostics: tuple[Diagnostic, ...]
    ast_sha256: str
    web_document: ContentDerivative | None
    web: ContentDerivative
    telegram: ContentDerivative

    @property
    def has_errors(self) -> bool:
        return any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )


def _canonical_value(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: _canonical_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, tuple | list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return value


def canonical_json(value: Any) -> str:
    """Return the stable UTF-8 JSON form used for revision fingerprints."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ast_sha256(document: DocumentAst) -> str:
    return sha256_text(canonical_json(document))
