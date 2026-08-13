"""Pure extraction of self-contained TikZ asset sources from legacy TeX.

The old HTML pipeline in ``_external_pipelines/a16_html_from_tex.py`` attached
``% addToTikz`` blocks and declarations immediately preceding a picture before
running TeX.  Keep that compatibility rule in one bounded scanner so parsing,
cache lookup and the later batch converter all hash the same source.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

from .scanner import (
    CommandToken,
    ParserLimits,
    command_group,
    find_environment_end,
    is_escaped,
    read_command,
    read_group,
    read_math,
    read_optional_group,
    scan_commands,
    skip_comment,
    skip_space_and_comments,
)


_ADD_TO_TIKZ_MARKER = re.compile(
    r"(?m)^[ \t]*%[ \t]*addToTikz[ \t]*(?:\n|$)", re.IGNORECASE
)
_GROUP_DECLARATION_COUNTS = {
    "addtolength": 2,
    "colorlet": 2,
    "definecolor": 3,
    "newcounter": 1,
    "newlength": 1,
    "pgfdeclarepatternformonly": 5,
    "pgfmathsetlengthmacro": 2,
    "pgfmathsetmacro": 2,
    "setcounter": 2,
    "setlength": 2,
    "tikzset": 1,
    "usetikzlibrary": 1,
}
_COMMAND_DECLARATIONS = {"newcommand", "providecommand", "renewcommand"}
_DEF_DECLARATIONS = {"def", "edef", "gdef", "xdef"}
_TIKZ_WRAPPERS = {"lefttikz", "lefttikzw", "righttikz", "righttikzw"}

_CHESS_BOARD_CONTEXT = r"""
\definecolor{zinnwalditebrown}{rgb}{0.17, 0.09, 0.03}
\definecolor{sand}{rgb}{0.76, 0.7, 0.5}
\newcommand{\ChessBoard}[2]{%
  \foreach \x in {1,...,#1}{
    \foreach \y in {1,...,#2}{
      \pgfmathparse{mod(\x+\y,2) ? "zinnwalditebrown" : "sand"}
      \edef\tmpcellcol{\pgfmathresult}%
      \fill[fill=\tmpcellcol] (\x,\y) rectangle ++ (1,1);
    }
  }
}
""".strip()

_CHESS_PIECE_CONTEXT = r"""
\newcommand{\ChessPiece}[3]{%
  \draw (#2+0.5,#3+0.5) node
    {\includegraphics[width=7mm,height=7mm,keepaspectratio]{#1}};
}
""".strip()


@dataclass(frozen=True)
class TikzScanIssue:
    code: str
    start: int
    end: int
    message: str


@dataclass(frozen=True)
class TikzSource:
    start: int
    end: int
    source: str
    raw_source: str
    kind: str
    context_kinds: tuple[str, ...]
    context_starts: tuple[int, ...]


@dataclass(frozen=True)
class TikzScanResult:
    sources: tuple[TikzSource, ...]
    issues: tuple[TikzScanIssue, ...]


@dataclass(frozen=True)
class _Declaration:
    start: int
    end: int
    kind: str
    defined_command: str | None = None
    defined_literal: str | None = None


def _group_text(text: str, cursor: int, end: int, limits: ParserLimits) -> str | None:
    group = read_group(text, cursor, end, max_depth=limits.max_group_depth)
    if group is None:
        return None
    return text[group.content_start : group.content_end].strip()


def _declared_identity(
    text: str, command: CommandToken, end: int, limits: ParserLimits
) -> tuple[str | None, str | None]:
    if command.name in _COMMAND_DECLARATIONS | _DEF_DECLARATIONS:
        cursor = skip_space_and_comments(text, command.end, end)
        group = read_group(text, cursor, end, max_depth=limits.max_group_depth)
        if group is not None:
            cursor = skip_space_and_comments(text, group.content_start, group.content_end)
        declared = read_command(text, cursor, end)
        return (declared.name if declared is not None else None), None
    if command.name in {"newlength", "setlength", "addtolength"}:
        value = _group_text(text, command.end, end, limits)
        if value:
            declared = read_command(value, 0, len(value))
            return (declared.name if declared is not None else None), None
    if command.name in {"definecolor", "pgfdeclarepatternformonly"}:
        return None, _group_text(text, command.end, end, limits)
    return None, None


def _read_command_name_argument(
    text: str, cursor: int, end: int, limits: ParserLimits
) -> int | None:
    group = read_group(text, cursor, end, max_depth=limits.max_group_depth)
    if group is not None:
        return group.end
    cursor = skip_space_and_comments(text, cursor, end)
    command = read_command(text, cursor, end)
    return command.end if command is not None else None


def _declaration_end(
    text: str, command: CommandToken, end: int, limits: ParserLimits
) -> int | None:
    group_count = _GROUP_DECLARATION_COUNTS.get(command.name)
    if group_count is not None:
        cursor = command.end
        if command.name == "colorlet":
            optional = read_optional_group(
                text, cursor, end, max_depth=limits.max_group_depth
            )
            if optional is not None:
                cursor = optional.end
        for _ in range(group_count):
            group = read_group(text, cursor, end, max_depth=limits.max_group_depth)
            if group is None:
                return None
            cursor = group.end
        return cursor

    if command.name in _COMMAND_DECLARATIONS:
        cursor = _read_command_name_argument(text, command.end, end, limits)
        if cursor is None:
            return None
        argument_count = read_optional_group(
            text, cursor, end, max_depth=limits.max_group_depth
        )
        if argument_count is not None:
            cursor = argument_count.end
            default = read_optional_group(
                text, cursor, end, max_depth=limits.max_group_depth
            )
            if default is not None:
                cursor = default.end
        body = read_group(text, cursor, end, max_depth=limits.max_group_depth)
        return body.end if body is not None else None

    if command.name in _DEF_DECLARATIONS:
        cursor = skip_space_and_comments(text, command.end, end)
        declared = read_command(text, cursor, end)
        if declared is None:
            return None
        cursor = declared.end
        while cursor < end:
            if text[cursor] == "%" and not is_escaped(text, cursor):
                cursor = skip_comment(text, cursor, end)
                continue
            if text[cursor] == "{" and not is_escaped(text, cursor):
                body = read_group(
                    text, cursor, end, max_depth=limits.max_group_depth
                )
                return body.end if body is not None else None
            cursor += 1
    return None


def _declarations(
    text: str, limits: ParserLimits, end: int
) -> tuple[tuple[_Declaration, ...], tuple[TikzScanIssue, ...]]:
    declarations: list[_Declaration] = []
    issues: list[TikzScanIssue] = []
    commands = scan_commands(
        text,
        start=0,
        end=end,
        limits=limits,
    )
    enclosing_declaration_end = -1
    for command in commands:
        if command.start < enclosing_declaration_end:
            continue
        if (
            command.name not in _GROUP_DECLARATION_COUNTS
            and command.name not in _COMMAND_DECLARATIONS
            and command.name not in _DEF_DECLARATIONS
        ):
            continue
        declaration_end = _declaration_end(text, command, end, limits)
        if declaration_end is None:
            issues.append(
                TikzScanIssue(
                    code="tikz.context_declaration_malformed",
                    start=command.start,
                    end=command.end,
                    message=f"Не удалось разобрать объявление \\{command.name}.",
                )
            )
            continue
        defined_command, defined_literal = _declared_identity(
            text, command, end, limits
        )
        declarations.append(
            _Declaration(
                command.start,
                declaration_end,
                command.name,
                defined_command,
                defined_literal,
            )
        )
        enclosing_declaration_end = declaration_end
    return tuple(declarations), tuple(issues)


def _is_ignorable(text: str, start: int, end: int) -> bool:
    cursor = start
    while cursor < end:
        if text[cursor].isspace():
            cursor += 1
            continue
        if text[cursor] == "%" and not is_escaped(text, cursor):
            comment_end = skip_comment(text, cursor, end)
            if text[cursor:comment_end].lstrip().casefold().startswith(
                "% addtotikz"
            ):
                return False
            cursor = comment_end
            continue
        return False
    return True


def _adjacent_context(
    text: str,
    picture_start: int,
    declarations: tuple[_Declaration, ...],
) -> tuple[_Declaration, ...]:
    ends = [declaration.end for declaration in declarations]
    cursor = picture_start
    attached: list[_Declaration] = []
    search_to = len(declarations)
    while search_to:
        index = bisect.bisect_right(ends, cursor, hi=search_to) - 1
        if index < 0:
            break
        candidate = declarations[index]
        if not _is_ignorable(text, candidate.end, cursor):
            break
        attached.append(candidate)
        cursor = candidate.start
        search_to = index
    attached.reverse()
    return tuple(attached)


def _command_names(text: str) -> set[str]:
    names: set[str] = set()
    cursor = 0
    end = len(text)
    while cursor < end:
        if text[cursor] == "%" and not is_escaped(text, cursor):
            cursor = skip_comment(text, cursor, end)
            continue
        command = read_command(text, cursor, end)
        if command is None:
            cursor += 1
            continue
        if command.name:
            names.add(command.name)
        cursor = command.end
    return names


def _effective_context(
    text: str,
    picture_start: int,
    raw_source: str,
    declarations: tuple[_Declaration, ...],
) -> tuple[_Declaration, ...]:
    prior = tuple(item for item in declarations if item.end <= picture_start)
    selected = {item.start for item in _adjacent_context(text, picture_start, prior)}
    selected.update(
        item.start for item in prior if item.kind == "usetikzlibrary"
    )
    while True:
        dependency_text = raw_source + "\n" + "\n".join(
            text[item.start : item.end]
            for item in prior
            if item.start in selected
        )
        command_names = _command_names(dependency_text)
        changed = False
        for item in prior:
            if item.start in selected:
                continue
            needed = False
            if item.defined_command and item.defined_command in command_names:
                needed = True
            elif item.defined_literal and item.defined_literal in dependency_text:
                needed = True
            elif item.kind == "tikzset":
                # Global/every-picture styles have no explicit command token.
                needed = True
            if needed:
                selected.add(item.start)
                changed = True
        if not changed:
            break
    return tuple(item for item in prior if item.start in selected)


def _global_context(
    text: str,
) -> tuple[tuple[str, ...], tuple[TikzScanIssue, ...]]:
    markers = tuple(_ADD_TO_TIKZ_MARKER.finditer(text))
    contexts: list[str] = []
    for index in range(0, len(markers) - 1, 2):
        content = text[markers[index].end() : markers[index + 1].start()].strip()
        if content:
            contexts.append(content)
    issues: list[TikzScanIssue] = []
    if len(markers) % 2:
        marker = markers[-1]
        issues.append(
            TikzScanIssue(
                code="tikz.add_to_tikz_unclosed",
                start=marker.start(),
                end=marker.end(),
                message="Маркер % addToTikz не имеет парного закрывающего маркера.",
            )
        )
    return tuple(contexts), tuple(issues)


def _active_document_end(text: str, limits: ParserLimits) -> int:
    for command in scan_commands(text, start=0, end=len(text), limits=limits):
        if command.name != "end":
            continue
        group = command_group(text, command, len(text), limits=limits)
        if (
            group is not None
            and text[group.content_start : group.content_end].strip() == "document"
        ):
            return command.start
    return len(text)


def _compose_source(
    raw_source: str,
    global_context: tuple[str, ...],
    local_context: tuple[_Declaration, ...],
    text: str,
) -> tuple[str, tuple[str, ...]]:
    pieces: list[str] = []
    kinds: list[str] = []
    seen: set[str] = set()
    for context in global_context:
        normalized = context.strip()
        if normalized and normalized not in seen:
            pieces.append(normalized)
            kinds.append("addToTikz")
            seen.add(normalized)
    for declaration in local_context:
        normalized = text[declaration.start : declaration.end].strip()
        if not normalized or normalized in seen:
            continue
        pieces.append(normalized)
        kinds.append(declaration.kind)
        seen.add(normalized)
    combined = "\n".join((*pieces, raw_source.strip()))
    compat: list[str] = []
    if (
        "\\ChessBoard" in raw_source
        and "\\newcommand{\\ChessBoard}" not in combined
    ):
        compat.append(_CHESS_BOARD_CONTEXT)
    if (
        "\\ChessPiece" in raw_source
        and "\\newcommand{\\ChessPiece}" not in combined
    ):
        compat.append(_CHESS_PIECE_CONTEXT)
    if compat:
        combined = "\n".join((*compat, combined))
        kinds.insert(0, "chess-compat")
    return combined.strip(), tuple(kinds)


def _inline_tikz_source(
    text: str, command: CommandToken, end: int, limits: ParserLimits
) -> tuple[str, int] | None:
    cursor = command.end
    options = read_optional_group(
        text, cursor, end, max_depth=limits.max_group_depth
    )
    if options is not None:
        cursor = options.end
    body = read_group(text, cursor, end, max_depth=limits.max_group_depth)
    if body is not None:
        option_text = text[options.start : options.end] if options else ""
        return (
            f"\\begin{{tikzpicture}}{option_text}"
            f"{text[body.content_start : body.content_end]}"
            "\\end{tikzpicture}",
            body.end,
        )

    # TikZ also accepts ``\tikz\node ...;`` without braces.  The terminating
    # semicolon is structural only at top group level; labels commonly contain
    # punctuation and nested TeX groups.
    body_start = skip_space_and_comments(text, cursor, end)
    cursor = body_start
    brace_depth = 0
    while cursor < end:
        if text[cursor] == "%" and not is_escaped(text, cursor):
            cursor = skip_comment(text, cursor, end)
            continue
        character = text[cursor]
        if character == "{" and not is_escaped(text, cursor):
            brace_depth += 1
        elif character == "}" and not is_escaped(text, cursor):
            brace_depth = max(0, brace_depth - 1)
        elif character == ";" and brace_depth == 0:
            inline_end = cursor + 1
            option_text = text[options.start : options.end] if options else ""
            return (
                f"\\begin{{tikzpicture}}{option_text}"
                f"{text[body_start:inline_end]}"
                "\\end{tikzpicture}",
                inline_end,
            )
        cursor += 1
    return None


def _wrapper_tikz_source(
    text: str, command: CommandToken, end: int, limits: ParserLimits
) -> tuple[str, int] | None:
    argument_count = 4 if command.name.endswith("w") else 3
    cursor = command.end
    groups = []
    for _ in range(argument_count):
        group = read_group(text, cursor, end, max_depth=limits.max_group_depth)
        if group is None:
            return None
        groups.append(group)
        cursor = group.end
    content = text[groups[-1].content_start : groups[-1].content_end].strip()
    if not content:
        return None
    if r"\begin{tikzpicture}" not in content:
        content = f"\\begin{{tikzpicture}}{content}\\end{{tikzpicture}}"
    return content, cursor


def scan_tikz_sources(
    text: str, *, limits: ParserLimits | None = None
) -> TikzScanResult:
    """Return every environment/inline TikZ source with its effective context."""

    parser_limits = limits or ParserLimits()
    end = _active_document_end(text, parser_limits)
    declarations, declaration_issues = _declarations(text, parser_limits, end)
    global_context, marker_issues = _global_context(text[:end])
    declarations_by_start = {item.start: item for item in declarations}
    sources: list[TikzSource] = []
    issues = [*declaration_issues, *marker_issues]
    cursor = 0
    while cursor < end:
        if text[cursor] == "%" and not is_escaped(text, cursor):
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
        declaration = declarations_by_start.get(command.start)
        if declaration is not None:
            cursor = declaration.end
            continue

        if command.name == "begin":
            group = command_group(text, command, end, limits=parser_limits)
            if (
                group is not None
                and text[group.content_start : group.content_end].strip() == "comment"
            ):
                match = find_environment_end(
                    text,
                    body_start=group.end,
                    end=end,
                    environment="comment",
                    limits=parser_limits,
                )
                cursor = match[1] if match is not None else group.end
                continue

        raw_source: str | None = None
        picture_end: int | None = None
        kind: str | None = None
        if command.name in _TIKZ_WRAPPERS:
            wrapper = _wrapper_tikz_source(text, command, end, parser_limits)
            if wrapper is not None:
                raw_source, picture_end = wrapper
                kind = "wrapper"
        elif command.name == "begin":
            group = command_group(text, command, end, limits=parser_limits)
            environment = (
                text[group.content_start : group.content_end].strip()
                if group is not None
                else None
            )
            if environment == "tikzpicture" and group is not None:
                match = find_environment_end(
                    text,
                    body_start=group.end,
                    end=end,
                    environment=environment,
                    limits=parser_limits,
                )
                if match is None:
                    issues.append(
                        TikzScanIssue(
                            code="tikz.environment_unclosed",
                            start=command.start,
                            end=group.end,
                            message="Environment tikzpicture не закрыт.",
                        )
                    )
                    cursor = group.end
                    continue
                picture_end = match[1]
                raw_source = text[command.start:picture_end]
                kind = "environment"
        elif command.name == "tikz":
            inline = _inline_tikz_source(text, command, end, parser_limits)
            if inline is None:
                issues.append(
                    TikzScanIssue(
                        code="tikz.inline_argument_missing",
                        start=command.start,
                        end=command.end,
                        message="Команда \\tikz не содержит braced-тело.",
                    )
                )
                cursor = command.end
                continue
            raw_source, picture_end = inline
            kind = "inline"

        if raw_source is None or picture_end is None or kind is None:
            cursor = command.end
            continue
        local_context = _effective_context(
            text, command.start, raw_source, declarations
        )
        source, context_kinds = _compose_source(
            raw_source, global_context, local_context, text
        )
        sources.append(
            TikzSource(
                start=command.start,
                end=picture_end,
                source=source,
                raw_source=raw_source.strip(),
                kind=kind,
                context_kinds=context_kinds,
                context_starts=tuple(item.start for item in local_context),
            )
        )
        cursor = picture_end
    return TikzScanResult(tuple(sources), tuple(issues))


__all__ = [
    "TikzScanIssue",
    "TikzScanResult",
    "TikzSource",
    "scan_tikz_sources",
]
