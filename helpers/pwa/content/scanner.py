"""Bounded LaTeX scanner primitives used by the PWA content compiler.

This is intentionally not a complete TeX interpreter.  It understands lexical
boundaries that matter to the product (comments, math, groups, commands and
environments) and reports everything else instead of guessing with global
regular-expression substitutions.
"""

from __future__ import annotations

import bisect
import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from .model import (
    DecodedSource,
    Diagnostic,
    DiagnosticSeverity,
    SourceEncoding,
    SourcePosition,
    SourceSpan,
)


@dataclass(frozen=True)
class ParserLimits:
    max_source_bytes: int = 2_000_000
    max_group_depth: int = 128
    max_environment_depth: int = 64
    max_nodes: int = 100_000
    max_tikz_chars: int = 250_000


@dataclass(frozen=True)
class CommandToken:
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class GroupToken:
    start: int
    content_start: int
    content_end: int
    end: int


@dataclass(frozen=True)
class MathToken:
    start: int
    content_start: int
    content_end: int
    end: int
    display: bool


class SourceMap:
    def __init__(self, source_name: str, text: str):
        self.source_name = source_name
        self.text = text
        self._line_starts = [0]
        self._line_starts.extend(
            index + 1 for index, character in enumerate(text) if character == "\n"
        )

    def position(self, offset: int) -> SourcePosition:
        bounded = max(0, min(offset, len(self.text)))
        line_index = bisect.bisect_right(self._line_starts, bounded) - 1
        return SourcePosition(
            offset=bounded,
            line=line_index + 1,
            column=bounded - self._line_starts[line_index] + 1,
        )

    def span(self, start: int, end: int) -> SourceSpan:
        return SourceSpan(
            source_name=self.source_name,
            start=self.position(start),
            end=self.position(max(start, end)),
        )


def decode_source(
    payload: bytes,
    *,
    source_name: str,
    limits: ParserLimits,
) -> DecodedSource:
    """Decode one immutable source while hashing the original byte sequence."""

    if len(payload) > limits.max_source_bytes:
        raise ValueError(
            f"LaTeX source exceeds the {limits.max_source_bytes}-byte parser limit"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        text = payload.decode("utf-8-sig")
        encoding = SourceEncoding.UTF8_BOM
    else:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            text = payload.decode("windows-1251")
            encoding = SourceEncoding.WINDOWS_1251
        else:
            encoding = SourceEncoding.UTF8

    # Canonical offsets refer to decoded Unicode with one newline convention;
    # the raw byte hash remains untouched for provenance.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return DecodedSource(
        source_name=source_name,
        raw_sha256=hashlib.sha256(payload).hexdigest(),
        raw_size_bytes=len(payload),
        encoding=encoding,
        text=text,
    )


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def skip_comment(text: str, index: int, end: int) -> int:
    newline = text.find("\n", index, end)
    return end if newline < 0 else newline


def read_command(text: str, index: int, end: int) -> CommandToken | None:
    if index >= end or text[index] != "\\":
        return None
    cursor = index + 1
    if cursor >= end:
        return CommandToken("", index, cursor)
    if text[cursor].isalpha() or text[cursor] == "@":
        cursor += 1
        while cursor < end and (text[cursor].isalpha() or text[cursor] == "@"):
            cursor += 1
        if cursor < end and text[cursor] == "*":
            cursor += 1
        return CommandToken(text[index + 1 : cursor], index, cursor)
    return CommandToken(text[cursor], index, cursor + 1)


def skip_space_and_comments(text: str, index: int, end: int) -> int:
    cursor = index
    while cursor < end:
        if text[cursor].isspace():
            cursor += 1
            continue
        if text[cursor] == "%" and not is_escaped(text, cursor):
            cursor = skip_comment(text, cursor, end)
            continue
        return cursor
    return cursor


def read_group(
    text: str,
    index: int,
    end: int,
    *,
    opening: str = "{",
    closing: str = "}",
    max_depth: int = 128,
) -> GroupToken | None:
    cursor = skip_space_and_comments(text, index, end)
    if cursor >= end or text[cursor] != opening:
        return None
    start = cursor
    depth = 1
    cursor += 1
    content_start = cursor
    while cursor < end:
        character = text[cursor]
        if character == "%" and not is_escaped(text, cursor):
            cursor = skip_comment(text, cursor, end)
            continue
        if character == opening and not is_escaped(text, cursor):
            depth += 1
            if depth > max_depth:
                return None
        elif character == closing and not is_escaped(text, cursor):
            depth -= 1
            if depth == 0:
                return GroupToken(start, content_start, cursor, cursor + 1)
        cursor += 1
    return None


def read_optional_group(
    text: str, index: int, end: int, *, max_depth: int = 128
) -> GroupToken | None:
    return read_group(
        text,
        index,
        end,
        opening="[",
        closing="]",
        max_depth=max_depth,
    )


def read_math(text: str, index: int, end: int) -> MathToken | None:
    if index >= end:
        return None
    if text.startswith("$$", index):
        opening, closing, display = "$$", "$$", True
    elif text[index] == "$" and not is_escaped(text, index):
        opening, closing, display = "$", "$", False
    elif text.startswith("\\[", index):
        opening, closing, display = "\\[", "\\]", True
    elif text.startswith("\\(", index):
        opening, closing, display = "\\(", "\\)", False
    else:
        return None

    cursor = index + len(opening)
    content_start = cursor
    while cursor < end:
        if text.startswith(closing, cursor) and not is_escaped(text, cursor):
            return MathToken(
                start=index,
                content_start=content_start,
                content_end=cursor,
                end=cursor + len(closing),
                display=display,
            )
        cursor += 1
    return None


def command_group(
    text: str,
    command: CommandToken,
    end: int,
    *,
    limits: ParserLimits,
) -> GroupToken | None:
    return read_group(
        text,
        command.end,
        end,
        max_depth=limits.max_group_depth,
    )


def find_environment_end(
    text: str,
    *,
    body_start: int,
    end: int,
    environment: str,
    limits: ParserLimits,
) -> tuple[int, int] | None:
    """Find a balanced ``\\end`` while ignoring comments and math."""

    depth = 1
    cursor = body_start
    while cursor < end:
        character = text[cursor]
        if character == "%" and not is_escaped(text, cursor):
            cursor = skip_comment(text, cursor, end)
            continue
        math = read_math(text, cursor, end)
        if math is not None:
            cursor = math.end
            continue
        command = read_command(text, cursor, end)
        if command is None:
            cursor += 1
            continue
        if command.name not in {"begin", "end"}:
            cursor = command.end
            continue
        group = command_group(text, command, end, limits=limits)
        if group is None:
            cursor = command.end
            continue
        name = text[group.content_start : group.content_end].strip()
        if name == environment:
            depth += 1 if command.name == "begin" else -1
            if depth > limits.max_environment_depth:
                return None
            if depth == 0:
                return command.start, group.end
        cursor = group.end
    return None


def scan_commands(
    text: str,
    *,
    start: int,
    end: int,
    limits: ParserLimits,
    skip_environments: frozenset[str] = frozenset(
        {
            "align",
            "align*",
            "comment",
            "equation",
            "equation*",
            "gather",
            "gather*",
            "picture",
            "tikzpicture",
        }
    ),
) -> tuple[CommandToken, ...]:
    """Return commands outside comments, math and selected opaque environments."""

    commands: list[CommandToken] = []
    cursor = start
    while cursor < end:
        character = text[cursor]
        if character == "%" and not is_escaped(text, cursor):
            cursor = skip_comment(text, cursor, end)
            continue
        math = read_math(text, cursor, end)
        if math is not None:
            cursor = math.end
            continue
        command = read_command(text, cursor, end)
        if command is None:
            cursor += 1
            continue
        commands.append(command)
        if command.name == "begin":
            group = command_group(text, command, end, limits=limits)
            if group is not None:
                environment = text[group.content_start : group.content_end].strip()
                if environment in skip_environments:
                    match = find_environment_end(
                        text,
                        body_start=group.end,
                        end=end,
                        environment=environment,
                        limits=limits,
                    )
                    if match is not None:
                        cursor = match[1]
                        continue
        cursor = command.end
    return tuple(commands)


_SAFE_ASSET_COMPONENT = re.compile(r"^[^\x00-\x1f\x7f<>:\\]+$")


def normalize_asset_reference(reference: str) -> str | None:
    normalized = " ".join(reference.strip().split())
    if not normalized or not _SAFE_ASSET_COMPONENT.fullmatch(normalized):
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def is_safe_link(href: str) -> bool:
    value = href.strip()
    if not value or any(character in value for character in "\x00\r\n\t"):
        return False
    if value.startswith("#"):
        return bool(re.fullmatch(r"#[A-Za-z0-9_.:-]+", value))
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https", "mailto", "tel"}:
        return False
    if parsed.scheme.lower() in {"http", "https"}:
        return (
            bool(parsed.netloc) and parsed.username is None and parsed.password is None
        )
    return bool(parsed.path)


def syntax_diagnostic(
    *,
    code: str,
    message: str,
    source_map: SourceMap,
    start: int,
    end: int,
    recovery: str | None = None,
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=severity,
        message=message,
        span=source_map.span(start, end),
        recovery=recovery,
    )
