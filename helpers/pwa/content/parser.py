"""Pure bounded parser from supported LaTeX into the canonical content AST."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

from .model import (
    AnnouncementKind,
    AnnouncementNode,
    BlockNode,
    CodeNode,
    Diagnostic,
    DiagnosticSeverity,
    DocumentAst,
    EmphasisNode,
    FigureKind,
    FigureNode,
    HeadingNode,
    InlineNode,
    LinkNode,
    ListItemNode,
    ListNode,
    MathNode,
    ParagraphNode,
    ProblemNode,
    StrongNode,
    SubpartNode,
    TableCellNode,
    TableNode,
    TableRowNode,
    TextNode,
)
from .scanner import (
    CommandToken,
    GroupToken,
    ParserLimits,
    SourceMap,
    command_group,
    find_environment_end,
    is_escaped,
    is_safe_link,
    normalize_asset_reference,
    read_command,
    read_group,
    read_math,
    read_optional_group,
    scan_commands,
    skip_comment,
    skip_space_and_comments,
    syntax_diagnostic,
)
from .tikz import scan_tikz_sources


AST_SCHEMA_VERSION = 3

_PROBLEM_STARTS = {
    "задача",
    "задачабк",
    "задачан",
    "problem",
    "problemn",
    "сзадача",
}
_PROBLEM_ENDS = {"кзадача", "eproblem"}
_FIELD_STARTS = {
    "ответ": "answer",
    "answer": "answer",
    "указание": "hint",
    "подсказка": "hint",
    "hint": "hint",
    "решение": "solution",
    "solution": "solution",
}
_FIELD_ENDS = {
    "answer": {"кответ", "eanswer"},
    "hint": {"куказание", "кподсказка", "ehint"},
    "solution": {"крешение", "esolution"},
}
_ANNOUNCEMENT_STARTS = {
    "объявление": AnnouncementKind.REGULAR,
    "важноеОбъявление": AnnouncementKind.IMPORTANT,
}
_ANNOUNCEMENT_ENDS = {
    "кобъявление": AnnouncementKind.REGULAR,
    "кважноеОбъявление": AnnouncementKind.IMPORTANT,
}
_ANNOUNCEMENT_COMMANDS = set(_ANNOUNCEMENT_STARTS) | set(_ANNOUNCEMENT_ENDS)
_SUBPART_COMMANDS = {"пункт", "пунктн", "спункт", "сспункт"}
_SINGLE_GROUP_FIELDS = {"answ": "answer"}

_FORMATTING_COMMANDS = {
    "textbf": StrongNode,
    "выд": EmphasisNode,
    "выдж": EmphasisNode,
    "выдд": EmphasisNode,
    "emph": EmphasisNode,
    "textit": EmphasisNode,
    "it": EmphasisNode,
    "texttt": CodeNode,
    "mathbf": StrongNode,
}
_PRESERVE_GROUP_COMMANDS = {
    "boldrunes",
    "doublebox",
    "fbox",
    "footnote",
    "sout",
    "text",
    "textrm",
    "textsf",
    "textsc",
    "hbox",
    "mbox",
    "centerline",
    "mathord",
    "phantom",
    "runes",
    "shortstack",
    "smash",
    "textsuperscript",
    "textup",
    "underline",
    "vbox",
}
_DISCARD_ONE_GROUP_COMMANDS = {
    "vspace",
    "vspace*",
    "hspace",
    "hspace*",
    "label",
    "pageref",
    "ref",
    "tags",
    "noalign",
    "Заголовок",
    "НомерЛистка",
    "ДатаЛистка",
    "Подзаголовок",
    "УвеличитьВысоту",
    "УвеличитьШирину",
    "bans",
    "batype",
    "baval",
    "bchecker",
    "bcongrat",
    "bptype",
    "btitle",
    "bvalerr",
    "bwrong",
    "cline",
    "newlength",
    "newsavebox",
    "npcopy",
    "refstepcounter",
    "usetikzlibrary",
}
_SKIP_TO_LINE_COMMANDS = {
    "arraycolsep",
    "hangafter",
    "hsize",
    "parshape",
    "tabcolsep",
    "vskip",
}
_SKIP_TO_NEXT_COMMAND = {"hangindent", "hskip"}
_NO_OUTPUT_COMMANDS = {
    "noindent",
    "small",
    "normalsize",
    "large",
    "Large",
    "LARGE",
    "Huge",
    "centering",
    "raggedright",
    "sloppy",
    "hfill",
    "vfill",
    "vfil",
    "hfil",
    "hss",
    "break",
    "newpage",
    "newaaaaaalpage",
    "smallskip",
    "medskip",
    "bigskip",
    "ВосстановитьГраницы",
    "ВключитьКолонтитул",
    "скрытьРешения",
    "ifhidesol",
    "else",
    "fi",
    "ignorespaces",
    "relax",
    "toprule",
    "midrule",
    "bottomrule",
    "hline",
    "hrule",
    "spacer",
    "СоздатьЗаголовок",
    "разделитель",
    "bfseries",
    "bf",
    "em",
    "sffamily",
    "tt",
    "rm",
    "sc",
    "sl",
    "scriptsize",
    "footnotesize",
    "itshape",
    "selectfont",
    "tab",
    "theFullTitleLine",
    "ОбнулитьДанные",
    "problemheight",
    "nolinebreak",
    "nopagebreak",
    "pagebreak",
    "columnbreak",
    "indent",
    "strut",
    "makeatletter",
    "makeatother",
    "вСтрочку",
    "-",
    "center",
    "hrulefill",
    "largeskip",
    "linewidth",
    "невСтрочку",
    "rightskip",
    "textwidth",
}
_TEXT_SYMBOLS = {
    "%": "%",
    "$": "$",
    "{": "{",
    "}": "}",
    "_": "_",
    "#": "#",
    "&": "&",
    " ": " ",
    "No": "№",
    "лк": "«",
    "пк": "»",
    "т": " — ",
    "bullet": "•",
    "textbullet": "•",
    "textdollar": "$",
    "textnumero": "№",
    "vdots": "⋮",
    "ddots": "⋱",
    "dots": "…",
    "ldots": "…",
    "dotsb": "…",
    "ldotsb": "…",
    "textbackslash": "\\",
    "dhchar": "ð",
    "thornchar": "þ",
    ",": "\u202f",
    ";": "\u202f",
    "quad": " ",
    "qquad": " ",
    "cdotp": "·",
    ":": "\u202f",
    "grqq": "“",
    "i": "ı",
    "blacksquare": "■",
    "cdot": "·",
    "*": "*",
}
_LINE_BREAK_COMMANDS = {
    "\\",
    "newline",
    "linebreak",
    "par",
    "subitem",
    "subsubitem",
    "сНовойСтроки",
}
_BLOCK_GROUP_WRAPPERS = {
    "centerline",
    "doublebox",
    "hbox",
    "makebox",
    "parbox",
    "scalebox",
    "smash",
    "textit",
    "vbox",
}
_STRUCTURAL_COMMANDS = (
    {
        "includegraphics",
        "rightpicture",
        "leftpicture",
        "righttikz",
        "lefttikz",
        "righttikzw",
        "lefttikzw",
        "begin",
        "раздел",
        "допраздел",
        "resizebox",
        "putthere",
        "tikz",
        "note",
        "phantom",
        "raisebox",
    }
    | _ANNOUNCEMENT_COMMANDS
    | _SUBPART_COMMANDS
    | _BLOCK_GROUP_WRAPPERS
)
_DISPLAY_MATH_ENVIRONMENTS = {
    "align",
    "align*",
    "equation",
    "equation*",
    "gather",
    "gather*",
    "multline*",
}
_CROSS_SEMANTIC_LAYOUT_ENVIRONMENTS = {
    "center",
    "figure",
    "footnotesize",
    "minipage",
    "multicols",
    "sideways",
    "small",
    "spacing",
    "table",
    "tabbing",
    "tabular",
    "tabularx",
    "wrapfigure",
    "wraptable",
}
_SUPPORTED_ENVIRONMENTS = {
    *_DISPLAY_MATH_ENVIRONMENTS,
    "center",
    "comment",
    "itemize",
    "enumerate",
    "figure",
    "footnotesize",
    "minipage",
    "nums",
    "tabular",
    "tabularx",
    "tabbing",
    "tikzpicture",
    "multicols",
    "picture",
    "quote",
    "sideways",
    "small",
    "spacing",
    "table",
    "wrapfigure",
    "wraptable",
}


@dataclass(frozen=True)
class _ProblemSlice:
    start_command: CommandToken
    statement_end: int
    fields_start: int
    outer_end: int


@dataclass(frozen=True)
class _StructuralGroup:
    start: int
    content_start: int
    content_end: int
    end: int


class _NodeLimitExceeded(ValueError):
    pass


class LatexAstParser:
    """Parse one decoded immutable source without evaluating TeX commands."""

    def __init__(
        self,
        *,
        source_name: str,
        source_sha256: str,
        source_encoding,
        text: str,
        limits: ParserLimits,
        known_assets: Mapping[str, str] | None = None,
    ):
        self.source_name = source_name
        self.source_sha256 = source_sha256
        self.source_encoding = source_encoding
        self.text = text
        self.limits = limits
        self.known_assets = dict(known_assets) if known_assets is not None else None
        self.source_map = SourceMap(source_name, text)
        self.diagnostics: list[Diagnostic] = []
        self._node_count = 0
        tikz_scan = scan_tikz_sources(text, limits=limits)
        self._tikz_sources = {source.start: source for source in tikz_scan.sources}
        self._tikz_context_starts = {
            start for source in tikz_scan.sources for start in source.context_starts
        }

    def parse(self) -> DocumentAst:
        replacement_offset = self.text.find("\ufffd")
        if replacement_offset >= 0:
            replacement_count = self.text.count("\ufffd")
            self._diagnose(
                "source.replacement_character",
                (
                    "Source содержит символ замены U+FFFD "
                    f"({replacement_count} вхождений) и уже повреждён до загрузки."
                ),
                replacement_offset,
                replacement_offset + 1,
                recovery=(
                    "Восстановите исходный файл из корректной UTF-8/Windows-1251 "
                    "копии; перекодирование текущих байтов не вернёт утраченные буквы."
                ),
            )
        try:
            body_start, body_end = self._document_body()
            slices = self._problem_slices(body_start, body_end)
            introduction_end = slices[0].start_command.start if slices else body_end
            introduction = self._parse_blocks(body_start, introduction_end)
            problems = tuple(
                self._parse_problem(
                    problem_slice,
                    ordinal,
                    problem_type=self._problem_type_at(
                        body_start, problem_slice.start_command.start
                    ),
                )
                for ordinal, problem_slice in enumerate(slices, start=1)
            )
        except _NodeLimitExceeded:
            introduction = ()
            problems = ()
        if not problems:
            self._diagnose(
                "latex.no_problems",
                "В источнике не найдено ни одной поддерживаемой команды задачи.",
                body_start,
                body_end,
                recovery="Используйте \\задача…\\кзадача или \\problem…\\eproblem.",
            )
        return DocumentAst(
            schema_version=AST_SCHEMA_VERSION,
            source_name=self.source_name,
            source_sha256=self.source_sha256,
            source_encoding=self.source_encoding,
            introduction=introduction,
            problems=problems,
        )

    def _count(self, node):
        self._node_count += 1
        if self._node_count > self.limits.max_nodes:
            self._diagnose(
                "latex.node_limit",
                "Документ превышает безопасный лимит структурных узлов.",
                0,
                len(self.text),
                recovery="Разделите материал на несколько source-файлов.",
            )
            raise _NodeLimitExceeded
        return node

    def _diagnose(
        self,
        code: str,
        message: str,
        start: int,
        end: int,
        *,
        recovery: str | None = None,
        severity: DiagnosticSeverity = DiagnosticSeverity.ERROR,
    ) -> None:
        self.diagnostics.append(
            syntax_diagnostic(
                code=code,
                message=message,
                source_map=self.source_map,
                start=start,
                end=end,
                recovery=recovery,
                severity=severity,
            )
        )

    def _document_body(self) -> tuple[int, int]:
        commands = scan_commands(
            self.text,
            start=0,
            end=len(self.text),
            limits=self.limits,
        )
        begin_document: GroupToken | None = None
        for command in commands:
            if command.name != "begin":
                continue
            group = command_group(
                self.text, command, len(self.text), limits=self.limits
            )
            if (
                group is not None
                and self.text[group.content_start : group.content_end].strip()
                == "document"
            ):
                begin_document = group
                break
        if begin_document is None:
            self._diagnose(
                "latex.document_fragment",
                "Source не содержит оболочку \\begin{document}; разобран как фрагмент.",
                0,
                min(len(self.text), 1),
                severity=DiagnosticSeverity.WARNING,
            )
            return 0, len(self.text)
        for command in commands:
            if command.start < begin_document.end or command.name != "end":
                continue
            group = command_group(
                self.text, command, len(self.text), limits=self.limits
            )
            if (
                group is not None
                and self.text[group.content_start : group.content_end].strip()
                == "document"
            ):
                return begin_document.end, command.start
        self._diagnose(
            "latex.document_unclosed",
            "Не найдена завершающая команда \\end{document}.",
            begin_document.start,
            len(self.text),
            recovery="Закройте document environment и повторите compile.",
        )
        return begin_document.end, len(self.text)

    def _problem_slices(
        self, body_start: int, body_end: int
    ) -> tuple[_ProblemSlice, ...]:
        commands = scan_commands(
            self.text,
            start=body_start,
            end=body_end,
            limits=self.limits,
        )
        starts = [command for command in commands if command.name in _PROBLEM_STARTS]
        slices: list[_ProblemSlice] = []
        for index, start in enumerate(starts):
            next_start = (
                starts[index + 1].start if index + 1 < len(starts) else body_end
            )
            matching_end = next(
                (
                    command
                    for command in commands
                    if start.end <= command.start < next_start
                    and command.name in _PROBLEM_ENDS
                ),
                None,
            )
            if matching_end is None:
                self._diagnose(
                    "latex.problem_unclosed",
                    "Задача не имеет явной завершающей команды.",
                    start.start,
                    next_start,
                    recovery="Добавьте \\кзадача или \\eproblem.",
                )
                slices.append(_ProblemSlice(start, next_start, next_start, next_start))
            else:
                slices.append(
                    _ProblemSlice(
                        start,
                        matching_end.start,
                        matching_end.end,
                        next_start,
                    )
                )
        return tuple(slices)

    def _problem_type_at(self, body_start: int, problem_start: int) -> int:
        problem_type = 2
        for command in scan_commands(
            self.text,
            start=body_start,
            end=problem_start,
            limits=self.limits,
        ):
            if command.name not in {"раздел", "допраздел"}:
                continue
            group = command_group(self.text, command, problem_start, limits=self.limits)
            if group is None:
                continue
            heading = self.text[group.content_start : group.content_end].casefold()
            if "тест" in heading:
                problem_type = 1
            elif "устн" in heading:
                problem_type = 3
            elif "письм" in heading:
                problem_type = 2
        return problem_type

    def _parse_problem(
        self,
        problem_slice: _ProblemSlice,
        ordinal: int,
        *,
        problem_type: int,
    ) -> ProblemNode:
        command = problem_slice.start_command
        header_end = command.end
        source_item: str | None = None
        source_title: str | None = None
        if command.name in {"problemn", "задачан"}:
            item_group = read_group(
                self.text,
                header_end,
                problem_slice.statement_end,
                max_depth=self.limits.max_group_depth,
            )
            if item_group is not None:
                source_item = self.text[
                    item_group.content_start : item_group.content_end
                ].strip()
                header_end = item_group.end
        optional = read_optional_group(
            self.text,
            header_end,
            problem_slice.statement_end,
            max_depth=self.limits.max_group_depth,
        )
        if optional is not None:
            source_item, source_title = self._parse_problem_options(
                self.text[optional.content_start : optional.content_end],
                source_item,
            )
            header_end = optional.end

        sections: dict[str, list[tuple[int, int]]] = {
            "statement": [],
            "trailing": [],
            "answer": [],
            "hint": [],
            "solution": [],
        }
        commands = scan_commands(
            self.text,
            start=header_end,
            end=problem_slice.outer_end,
            limits=self.limits,
        )
        consumed_fields: list[tuple[int, int]] = []
        command_index = 0
        while command_index < len(commands):
            field_start = commands[command_index]
            single_group_kind = _SINGLE_GROUP_FIELDS.get(field_start.name)
            if single_group_kind is not None:
                field_group = read_group(
                    self.text,
                    field_start.end,
                    problem_slice.outer_end,
                    max_depth=self.limits.max_group_depth,
                )
                if field_group is None:
                    self._missing_argument(field_start)
                    command_index += 1
                    continue
                sections[single_group_kind].append(
                    (field_group.content_start, field_group.content_end)
                )
                consumed_fields.append((field_start.start, field_group.end))
                command_index += 1
                continue
            field_kind = _FIELD_STARTS.get(field_start.name)
            if field_kind is None:
                command_index += 1
                continue
            expected_ends = _FIELD_ENDS[field_kind]
            next_field_start_index = next(
                (
                    candidate_index
                    for candidate_index in range(command_index + 1, len(commands))
                    if commands[candidate_index].name in _FIELD_STARTS
                ),
                None,
            )
            field_end_index = next(
                (
                    candidate_index
                    for candidate_index in range(command_index + 1, len(commands))
                    if commands[candidate_index].name in expected_ends
                ),
                None,
            )
            if next_field_start_index is not None and (
                field_end_index is None or next_field_start_index < field_end_index
            ):
                field_end_index = None
            if field_end_index is None:
                recovery_end = (
                    commands[next_field_start_index].start
                    if next_field_start_index is not None
                    else problem_slice.outer_end
                )
                self._diagnose(
                    "latex.field_unclosed",
                    f"Блок {field_kind} не имеет завершающей команды.",
                    field_start.start,
                    recovery_end,
                    recovery="Закройте блок соответствующей парной командой.",
                )
                sections[field_kind].append((field_start.end, recovery_end))
                consumed_fields.append((field_start.start, recovery_end))
                if next_field_start_index is None:
                    break
                command_index = next_field_start_index
                continue
            field_end = commands[field_end_index]
            sections[field_kind].append((field_start.end, field_end.start))
            consumed_fields.append((field_start.start, field_end.end))
            command_index = field_end_index + 1

        statement_ranges = [(header_end, problem_slice.statement_end)]
        for consumed_start, consumed_end in consumed_fields:
            next_ranges: list[tuple[int, int]] = []
            for range_start, range_end in statement_ranges:
                if consumed_end <= range_start or consumed_start >= range_end:
                    next_ranges.append((range_start, range_end))
                    continue
                if range_start < consumed_start:
                    next_ranges.append((range_start, consumed_start))
                if consumed_end < range_end:
                    next_ranges.append((consumed_end, range_end))
            statement_ranges = next_ranges
        sections["statement"].extend(statement_ranges)

        trailing_cursor = problem_slice.fields_start
        for consumed_start, consumed_end in consumed_fields:
            if consumed_start < problem_slice.fields_start:
                continue
            if trailing_cursor < consumed_start:
                sections["trailing"].append((trailing_cursor, consumed_start))
            trailing_cursor = max(trailing_cursor, consumed_end)
        if trailing_cursor < problem_slice.outer_end:
            sections["trailing"].append((trailing_cursor, problem_slice.outer_end))

        parsed_sections = {
            key: tuple(
                node
                for section_start, section_end in ranges
                for node in self._parse_blocks(section_start, section_end)
            )
            for key, ranges in sections.items()
        }
        return self._count(
            ProblemNode(
                span=self.source_map.span(command.start, problem_slice.outer_end),
                ordinal=ordinal,
                source_item=source_item,
                source_title=source_title,
                problem_type=problem_type,
                statement=parsed_sections["statement"],
                trailing=parsed_sections["trailing"],
                answer=parsed_sections["answer"],
                hint=parsed_sections["hint"],
                solution=parsed_sections["solution"],
            )
        )

    @staticmethod
    def _parse_problem_options(
        raw: str, source_item: str | None
    ) -> tuple[str | None, str | None]:
        title = None
        item = source_item
        for part in raw.split(","):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            value = value.strip().strip("\"'")
            if key.strip() == "name":
                item = value
            elif key.strip() == "title":
                title = value
        return item, title

    def _parse_blocks(self, start: int, end: int) -> tuple[BlockNode, ...]:
        if start >= end:
            return ()
        structural: list[CommandToken | _StructuralGroup] = sorted(
            (
                *self._top_level_commands(start, end, set(_STRUCTURAL_COMMANDS)),
                *self._top_level_structural_groups(start, end),
            ),
            key=lambda item: item.start,
        )
        nodes: list[BlockNode] = []
        cursor = start
        structural_index = 0
        while structural_index < len(structural):
            command = structural[structural_index]
            if command.start < cursor:
                structural_index += 1
                continue
            nodes.extend(self._paragraphs(cursor, command.start))
            if isinstance(command, _StructuralGroup):
                nodes.extend(
                    self._parse_blocks(command.content_start, command.content_end)
                )
                cursor = command.end
                structural_index += 1
                continue
            if command.name in _SUBPART_COMMANDS:
                next_subpart = next(
                    (
                        candidate
                        for candidate in structural[structural_index + 1 :]
                        if candidate.start >= command.end
                        and isinstance(candidate, CommandToken)
                        and candidate.name in _SUBPART_COMMANDS
                    ),
                    None,
                )
                subpart_end = next_subpart.start if next_subpart is not None else end
                content_start = command.end
                explicit_label = (
                    read_group(
                        self.text,
                        command.end,
                        subpart_end,
                        max_depth=self.limits.max_group_depth,
                    )
                    if command.name == "пунктн"
                    else None
                )
                if explicit_label is not None:
                    label = self.text[
                        explicit_label.content_start : explicit_label.content_end
                    ].strip()
                    content_start = explicit_label.end
                else:
                    label = self._subpart_label(
                        sum(isinstance(node, SubpartNode) for node in nodes) + 1
                    )
                nodes.append(
                    self._count(
                        SubpartNode(
                            span=self.source_map.span(command.start, subpart_end),
                            label=label,
                            children=self._parse_blocks(content_start, subpart_end),
                        )
                    )
                )
                cursor = subpart_end
            elif command.name in {
                "includegraphics",
                "rightpicture",
                "leftpicture",
                "righttikz",
                "lefttikz",
                "righttikzw",
                "lefttikzw",
            }:
                figure, cursor = self._parse_figure_command(command, end)
                if figure is not None:
                    nodes.append(figure)
            elif command.name in {"раздел", "допраздел"}:
                heading, cursor = self._parse_heading(command, end)
                if heading is not None:
                    nodes.append(heading)
            elif command.name == "resizebox":
                groups = self._read_groups(command.end, end, 3)
                if len(groups) != 3:
                    self._missing_argument(command)
                    cursor = groups[-1].end if groups else command.end
                else:
                    nodes.extend(
                        self._parse_blocks(
                            groups[2].content_start, groups[2].content_end
                        )
                    )
                    cursor = groups[2].end
            elif command.name == "putthere":
                groups = self._read_groups(command.end, end, 3)
                if len(groups) != 3:
                    self._missing_argument(command)
                    cursor = groups[-1].end if groups else command.end
                else:
                    nodes.extend(
                        self._parse_blocks(
                            groups[2].content_start, groups[2].content_end
                        )
                    )
                    cursor = groups[2].end
            elif command.name == "tikz":
                extracted = self._tikz_sources.get(command.start)
                if extracted is not None:
                    figure = self._tikz_figure(
                        command.start,
                        extracted.end,
                        extracted.source,
                        width_hint=None,
                        float_hint=None,
                    )
                    if figure is not None:
                        nodes.append(figure)
                    cursor = extracted.end
                    structural_index += 1
                    continue
                cursor = command.end
                options = read_optional_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if options is not None:
                    cursor = options.end
                body = read_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if body is None:
                    self._missing_argument(command)
                    cursor = options.end if options is not None else command.end
                else:
                    option_text = (
                        self.text[options.start : options.end]
                        if options is not None
                        else ""
                    )
                    raw = (
                        f"\\begin{{tikzpicture}}{option_text}"
                        f"{self.text[body.content_start : body.content_end]}"
                        "\\end{tikzpicture}"
                    )
                    figure = self._tikz_figure(
                        command.start,
                        body.end,
                        raw,
                        width_hint=None,
                        float_hint=None,
                    )
                    if figure is not None:
                        nodes.append(figure)
                    cursor = body.end
            elif command.name == "note":
                group = read_group(
                    self.text,
                    command.end,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if group is None:
                    self._missing_argument(command)
                    cursor = command.end
                else:
                    nodes.extend(
                        self._parse_blocks(group.content_start, group.content_end)
                    )
                    cursor = group.end
            elif command.name == "phantom":
                group = read_group(
                    self.text,
                    command.end,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if group is None:
                    self._missing_argument(command)
                    cursor = command.end
                else:
                    cursor = group.end
            elif command.name in _BLOCK_GROUP_WRAPPERS:
                if command.name in {"hbox", "vbox"}:
                    group = self._box_content_group(command, end)
                else:
                    wrapper_cursor = command.end
                    if command.name == "makebox":
                        for _ in range(2):
                            optional = read_optional_group(
                                self.text,
                                wrapper_cursor,
                                end,
                                max_depth=self.limits.max_group_depth,
                            )
                            if optional is None:
                                break
                            wrapper_cursor = optional.end
                    if command.name in {"parbox", "scalebox"}:
                        layout_argument = read_group(
                            self.text,
                            wrapper_cursor,
                            end,
                            max_depth=self.limits.max_group_depth,
                        )
                        wrapper_cursor = (
                            layout_argument.end
                            if layout_argument is not None
                            else wrapper_cursor
                        )
                    group = read_group(
                        self.text,
                        wrapper_cursor,
                        end,
                        max_depth=self.limits.max_group_depth,
                    )
                if group is None:
                    group_start = self.text.find("{", command.end, end)
                    if command.name in {"hbox", "vbox"} and group_start >= 0:
                        self._diagnose(
                            "latex.layout_group_crosses_semantic_boundary",
                            (
                                f"Print-layout command \\{command.name} пересекает "
                                "границу условия/подсказки/решения и не переносится "
                                "в web AST."
                            ),
                            command.start,
                            group_start + 1,
                            severity=DiagnosticSeverity.WARNING,
                        )
                        cursor = group_start + 1
                    else:
                        self._missing_argument(command)
                        cursor = command.end
                else:
                    nodes.extend(
                        self._parse_blocks(group.content_start, group.content_end)
                    )
                    cursor = group.end
            elif command.name == "raisebox":
                lift = read_group(
                    self.text,
                    command.end,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                cursor = lift.end if lift is not None else command.end
                for _ in range(2):
                    optional = read_optional_group(
                        self.text,
                        cursor,
                        end,
                        max_depth=self.limits.max_group_depth,
                    )
                    if optional is None:
                        break
                    cursor = optional.end
                content = read_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if lift is None or content is None:
                    self._missing_argument(command)
                else:
                    nodes.extend(
                        self._parse_blocks(content.content_start, content.content_end)
                    )
                    cursor = content.end
            elif command.name == "begin":
                environment_nodes, cursor = self._parse_environment(command, end)
                nodes.extend(environment_nodes)
            elif command.name in _ANNOUNCEMENT_STARTS:
                announcement, cursor = self._parse_announcement(command, end)
                nodes.append(announcement)
            elif command.name in _ANNOUNCEMENT_ENDS:
                self._diagnose(
                    "latex.announcement_end_unexpected",
                    f"Завершающая команда \\{command.name} не имеет начала объявления.",
                    command.start,
                    command.end,
                    recovery="Удалите лишнюю команду или добавьте соответствующее начало объявления.",
                )
                cursor = command.end
            structural_index += 1
        nodes.extend(self._paragraphs(cursor, end))
        return tuple(nodes)

    def _parse_announcement(
        self, command: CommandToken, end: int
    ) -> tuple[AnnouncementNode, int]:
        kind = _ANNOUNCEMENT_STARTS[command.name]
        boundary = next(
            iter(
                self._top_level_commands(
                    command.end,
                    end,
                    _ANNOUNCEMENT_COMMANDS,
                )
            ),
            None,
        )
        if boundary is None:
            self._diagnose(
                "latex.announcement_unclosed",
                f"Объявление \\{command.name} не имеет завершающей команды.",
                command.start,
                end,
                recovery=(
                    "Добавьте \\кобъявление для обычного или "
                    "\\кважноеОбъявление для важного объявления."
                ),
            )
            content_end = end
            outer_end = end
        elif boundary.name in _ANNOUNCEMENT_STARTS:
            self._diagnose(
                "latex.announcement_nested",
                "Объявления нельзя вкладывать друг в друга.",
                boundary.start,
                boundary.end,
                recovery="Закройте текущее объявление до начала следующего.",
            )
            content_end = boundary.start
            outer_end = boundary.start
        else:
            closing_kind = _ANNOUNCEMENT_ENDS[boundary.name]
            if closing_kind is not kind:
                self._diagnose(
                    "latex.announcement_end_mismatch",
                    (
                        f"Команда \\{boundary.name} не соответствует началу "
                        f"\\{command.name}."
                    ),
                    boundary.start,
                    boundary.end,
                    recovery="Используйте завершающую команду того же вида объявления.",
                )
            content_end = boundary.start
            outer_end = boundary.end

        children = self._parse_blocks(command.end, content_end)
        if not children:
            self._diagnose(
                "latex.announcement_empty",
                "Объявление не содержит отображаемого текста.",
                command.start,
                outer_end,
                recovery="Добавьте текст объявления или удалите пустой блок.",
            )
        return (
            self._count(
                AnnouncementNode(
                    span=self.source_map.span(command.start, outer_end),
                    kind=kind,
                    children=children,
                )
            ),
            outer_end,
        )

    @staticmethod
    def _subpart_label(ordinal: int) -> str:
        labels = "абвгдежзиклмнопрстуфхцчшщъыьэюя"
        if 1 <= ordinal <= len(labels):
            return labels[ordinal - 1]
        return str(ordinal)

    def _paragraphs(self, start: int, end: int) -> list[ParagraphNode]:
        if start >= end:
            return []
        ranges: list[tuple[int, int]] = []
        paragraph_start = start
        cursor = start
        brace_depth = 0
        while cursor < end:
            if self.text[cursor] == "%" and not is_escaped(self.text, cursor):
                cursor = skip_comment(self.text, cursor, end)
                continue
            math = read_math(self.text, cursor, end)
            if math is not None:
                cursor = math.end
                continue
            if self.text[cursor] == "{" and not is_escaped(self.text, cursor):
                brace_depth += 1
                cursor += 1
                continue
            if self.text[cursor] == "}" and not is_escaped(self.text, cursor):
                brace_depth = max(0, brace_depth - 1)
                cursor += 1
                continue
            if self.text[cursor] == "\n" and brace_depth == 0:
                match = re.match(r"\n[ \t]*\n+", self.text[cursor:end])
                if match is not None:
                    boundary_end = cursor + match.end()
                    if self._has_visible_source(paragraph_start, cursor):
                        ranges.append((paragraph_start, cursor))
                    paragraph_start = boundary_end
                    cursor = boundary_end
                    continue
            cursor += 1
        if self._has_visible_source(paragraph_start, end):
            ranges.append((paragraph_start, end))
        paragraphs = []
        for paragraph_start, paragraph_end in ranges:
            children = self._parse_inline(paragraph_start, paragraph_end)
            if children:
                paragraphs.append(
                    self._count(
                        ParagraphNode(
                            span=self.source_map.span(paragraph_start, paragraph_end),
                            children=children,
                        )
                    )
                )
        return paragraphs

    def _has_visible_source(self, start: int, end: int) -> bool:
        cursor = start
        while cursor < end:
            if self.text[cursor] == "%" and not is_escaped(self.text, cursor):
                cursor = skip_comment(self.text, cursor, end)
                continue
            if not self.text[cursor].isspace():
                return True
            cursor += 1
        return False

    def _parse_inline(
        self, start: int, end: int, *, depth: int = 0
    ) -> tuple[InlineNode, ...]:
        if depth > self.limits.max_group_depth:
            self._diagnose(
                "latex.group_depth",
                "Превышена максимальная глубина вложенности фигурных скобок.",
                start,
                end,
            )
            return ()
        nodes: list[InlineNode] = []
        text_start = start
        cursor = start

        def flush(until: int) -> None:
            nonlocal text_start
            if until > text_start:
                raw = self._normalize_text(self.text[text_start:until])
                if raw:
                    nodes.append(
                        self._count(
                            TextNode(
                                span=self.source_map.span(text_start, until),
                                text=raw,
                            )
                        )
                    )
            text_start = until

        while cursor < end:
            if self.text[cursor] == "%" and not is_escaped(self.text, cursor):
                flush(cursor)
                cursor = skip_comment(self.text, cursor, end)
                text_start = cursor
                continue
            math = read_math(self.text, cursor, end)
            if math is not None:
                flush(cursor)
                latex = self.text[math.content_start : math.content_end]
                if latex.strip():
                    nodes.append(
                        self._count(
                            MathNode(
                                span=self.source_map.span(math.start, math.end),
                                latex=latex,
                                display=math.display,
                            )
                        )
                    )
                cursor = math.end
                text_start = cursor
                continue
            if self.text[cursor] == "$" and not is_escaped(self.text, cursor):
                flush(cursor)
                self._diagnose(
                    "latex.math_unclosed",
                    "Не найдена закрывающая граница математической формулы.",
                    cursor,
                    end,
                )
                nodes.append(
                    self._count(TextNode(self.source_map.span(cursor, cursor + 1), "$"))
                )
                cursor += 1
                text_start = cursor
                continue
            if self.text[cursor] == "{" and not is_escaped(self.text, cursor):
                group = read_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if group is None:
                    flush(cursor)
                    source_group = read_group(
                        self.text,
                        cursor,
                        len(self.text),
                        max_depth=self.limits.max_group_depth,
                    )
                    if source_group is not None:
                        cursor += 1
                        text_start = cursor
                        continue
                    self._diagnose(
                        "latex.group_unclosed",
                        "Не найдена закрывающая фигурная скобка.",
                        cursor,
                        end,
                    )
                    cursor += 1
                    text_start = cursor
                    continue
                flush(cursor)
                nodes.extend(
                    self._parse_inline(
                        group.content_start,
                        group.content_end,
                        depth=depth + 1,
                    )
                )
                cursor = group.end
                text_start = cursor
                continue
            command = read_command(self.text, cursor, end)
            if command is None:
                cursor += 1
                continue
            flush(cursor)
            cursor = self._parse_inline_command(command, end, nodes, depth)
            text_start = cursor
        flush(end)
        return tuple(nodes)

    def _parse_inline_command(
        self,
        command: CommandToken,
        end: int,
        nodes: list[InlineNode],
        depth: int,
    ) -> int:
        if command.name in _TEXT_SYMBOLS:
            nodes.append(
                self._count(
                    TextNode(
                        self.source_map.span(command.start, command.end),
                        _TEXT_SYMBOLS[command.name],
                    )
                )
            )
            return command.end
        if command.name in _LINE_BREAK_COMMANDS:
            nodes.append(
                self._count(
                    TextNode(self.source_map.span(command.start, command.end), "\n")
                )
            )
            return command.end
        formatter = _FORMATTING_COMMANDS.get(command.name)
        if formatter is not None:
            group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
                if command.name in {"it", "выд", "выдж"}:
                    nodes.append(
                        self._count(
                            EmphasisNode(
                                span=self.source_map.span(command.start, end),
                                children=self._parse_inline(
                                    command.end,
                                    end,
                                    depth=depth + 1,
                                ),
                            )
                        )
                    )
                    return end
                token_start = skip_space_and_comments(self.text, command.end, end)
                if token_start < end and self.text[token_start] not in "\\{}":
                    token_end = token_start + 1
                    if formatter is CodeNode:
                        nodes.append(
                            self._count(
                                CodeNode(
                                    span=self.source_map.span(command.start, token_end),
                                    text=self.text[token_start:token_end],
                                )
                            )
                        )
                    else:
                        child = self._count(
                            TextNode(
                                span=self.source_map.span(token_start, token_end),
                                text=self.text[token_start:token_end],
                            )
                        )
                        nodes.append(
                            self._count(
                                formatter(
                                    span=self.source_map.span(command.start, token_end),
                                    children=(child,),
                                )
                            )
                        )
                    return token_end
                self._missing_argument(command)
                return command.end
            if formatter is CodeNode:
                node = CodeNode(
                    span=self.source_map.span(command.start, group.end),
                    text=self.text[group.content_start : group.content_end],
                )
            else:
                node = formatter(
                    span=self.source_map.span(command.start, group.end),
                    children=self._parse_inline(
                        group.content_start,
                        group.content_end,
                        depth=depth + 1,
                    ),
                )
            nodes.append(self._count(node))
            return group.end
        if command.name == "bf":
            nodes.append(
                self._count(
                    StrongNode(
                        span=self.source_map.span(command.start, end),
                        children=self._parse_inline(
                            command.end,
                            end,
                            depth=depth + 1,
                        ),
                    )
                )
            )
            return end
        if command.name == "verb":
            delimiter_offset = command.end
            if delimiter_offset >= end or self.text[delimiter_offset].isspace():
                self._missing_argument(command)
                return command.end
            delimiter = self.text[delimiter_offset]
            content_end = self.text.find(delimiter, delimiter_offset + 1, end)
            if content_end < 0:
                self._diagnose(
                    "latex.verb_unclosed",
                    "Команда \\verb не имеет завершающего delimiter.",
                    command.start,
                    end,
                )
                return end
            nodes.append(
                self._count(
                    CodeNode(
                        span=self.source_map.span(command.start, content_end + 1),
                        text=self.text[delimiter_offset + 1 : content_end],
                    )
                )
            )
            return content_end + 1
        if command.name == "overline":
            group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
                self._missing_argument(command)
                return command.end
            nodes.append(
                self._count(
                    MathNode(
                        span=self.source_map.span(command.start, group.end),
                        latex=self.text[command.start : group.end],
                        display=False,
                    )
                )
            )
            return group.end
        if command.name == "sfrac":
            groups = self._read_groups(command.end, end, 2)
            if len(groups) != 2:
                self._missing_argument(command)
                return groups[-1].end if groups else command.end
            nodes.append(
                self._count(
                    MathNode(
                        span=self.source_map.span(command.start, groups[1].end),
                        latex=self.text[command.start : groups[1].end],
                        display=False,
                    )
                )
            )
            return groups[1].end
        if command.name == "ensuremath":
            group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
                self._missing_argument(command)
                return command.end
            latex = self.text[group.content_start : group.content_end].strip()
            if latex:
                nodes.append(
                    self._count(
                        MathNode(
                            span=self.source_map.span(command.start, group.end),
                            latex=latex,
                            display=False,
                        )
                    )
                )
            return group.end
        if command.name in {"'", '"'}:
            group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is not None:
                nodes.extend(
                    self._parse_inline(
                        group.content_start, group.content_end, depth=depth + 1
                    )
                )
                return group.end
            if command.end < end:
                nodes.append(
                    self._count(
                        TextNode(
                            span=self.source_map.span(command.end, command.end + 1),
                            text=self.text[command.end],
                        )
                    )
                )
                return command.end + 1
            return command.end
        if command.name == "href":
            href_group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            label_group = (
                read_group(
                    self.text,
                    href_group.end,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if href_group is not None
                else None
            )
            if href_group is None or label_group is None:
                self._missing_argument(command)
                return command.end
            href = self.text[href_group.content_start : href_group.content_end].strip()
            children = self._parse_inline(
                label_group.content_start,
                label_group.content_end,
                depth=depth + 1,
            )
            if not is_safe_link(href):
                self._diagnose(
                    "latex.link_unsafe",
                    "Ссылка использует запрещённую или некорректную схему URL.",
                    href_group.start,
                    href_group.end,
                    recovery="Используйте абсолютный HTTPS URL, mailto, tel или локальный #anchor.",
                )
                nodes.extend(children)
            else:
                nodes.append(
                    self._count(
                        LinkNode(
                            span=self.source_map.span(command.start, label_group.end),
                            href=href,
                            children=children,
                        )
                    )
                )
            return label_group.end
        if command.name == "url":
            href_group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if href_group is None:
                self._missing_argument(command)
                return command.end
            href = self.text[href_group.content_start : href_group.content_end].strip()
            label = self._count(
                TextNode(
                    span=self.source_map.span(
                        href_group.content_start, href_group.content_end
                    ),
                    text=href,
                )
            )
            if is_safe_link(href):
                nodes.append(
                    self._count(
                        LinkNode(
                            span=self.source_map.span(command.start, href_group.end),
                            href=href,
                            children=(label,),
                        )
                    )
                )
            else:
                nodes.append(label)
            return href_group.end
        if command.name in _PRESERVE_GROUP_COMMANDS:
            group = (
                self._box_content_group(command, end)
                if command.name in {"hbox", "vbox"}
                else read_group(
                    self.text,
                    command.end,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
            )
            if group is None:
                token_start = skip_space_and_comments(self.text, command.end, end)
                if token_start < end and self.text[token_start] not in "\\{}":
                    nodes.append(
                        self._count(
                            TextNode(
                                span=self.source_map.span(token_start, token_start + 1),
                                text=self.text[token_start : token_start + 1],
                            )
                        )
                    )
                    return token_start + 1
                self._missing_argument(command)
                return command.end
            nodes.extend(
                self._parse_inline(
                    group.content_start,
                    group.content_end,
                    depth=depth + 1,
                )
            )
            return group.end
        if command.name == "makebox":
            cursor = command.end
            for _ in range(2):
                optional = read_optional_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if optional is None:
                    break
                cursor = optional.end
            group = read_group(
                self.text,
                cursor,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
                self._missing_argument(command)
                return cursor
            nodes.extend(
                self._parse_inline(
                    group.content_start,
                    group.content_end,
                    depth=depth + 1,
                )
            )
            return group.end
        if command.name in {"fbox", "framebox"}:
            cursor = command.end
            for _ in range(2):
                optional = read_optional_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if optional is None:
                    break
                cursor = optional.end
            group = read_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if group is None:
                self._missing_argument(command)
                return cursor
            nodes.extend(
                self._parse_inline(
                    group.content_start, group.content_end, depth=depth + 1
                )
            )
            return group.end
        if command.name in {"parbox", "scalebox"}:
            groups = self._read_groups(command.end, end, 2)
            if len(groups) != 2:
                self._missing_argument(command)
                return groups[-1].end if groups else command.end
            nodes.extend(
                self._parse_inline(
                    groups[1].content_start,
                    groups[1].content_end,
                    depth=depth + 1,
                )
            )
            return groups[1].end
        if command.name == "raisebox":
            lift = read_group(
                self.text, command.end, end, max_depth=self.limits.max_group_depth
            )
            if lift is None:
                self._missing_argument(command)
                return command.end
            cursor = lift.end
            for _ in range(2):
                optional = read_optional_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if optional is None:
                    break
                cursor = optional.end
            content = read_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if content is None:
                self._missing_argument(command)
                return cursor
            nodes.extend(
                self._parse_inline(
                    content.content_start, content.content_end, depth=depth + 1
                )
            )
            return content.end
        if command.name == "textcolor":
            groups = self._read_groups(command.end, end, 2)
            if len(groups) != 2:
                self._missing_argument(command)
                return groups[-1].end if groups else command.end
            nodes.extend(
                self._parse_inline(
                    groups[1].content_start,
                    groups[1].content_end,
                    depth=depth + 1,
                )
            )
            return groups[1].end
        if command.name == "contour":
            groups = self._read_groups(command.end, end, 2)
            if len(groups) != 2:
                self._missing_argument(command)
                return groups[-1].end if groups else command.end
            nodes.extend(
                self._parse_inline(
                    groups[1].content_start,
                    groups[1].content_end,
                    depth=depth + 1,
                )
            )
            return groups[1].end
        if command.name == "rule":
            return self._skip_groups(command, end, 2)
        if command.name == "tikzset":
            group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
                self._missing_argument(command)
                return command.end
            if command.start not in self._tikz_context_starts:
                self._diagnose(
                    "latex.tikz_preamble_ignored",
                    "Команда \\tikzset не примыкает к TikZ и не включена в asset.",
                    command.start,
                    group.end,
                    recovery=(
                        "Разместите локальный \\tikzset непосредственно перед "
                        "\\begin{tikzpicture} или внутри % addToTikz-блока."
                    ),
                    severity=DiagnosticSeverity.WARNING,
                )
            return group.end
        if command.name in _SKIP_TO_LINE_COMMANDS:
            newline = self.text.find("\n", command.end, end)
            return end if newline < 0 else newline
        if command.name in _SKIP_TO_NEXT_COMMAND:
            newline = self.text.find("\n", command.end, end)
            line_end = end if newline < 0 else newline
            next_command = self.text.find("\\", command.end, line_end)
            return line_end if next_command < 0 else next_command
        if command.name == "УстановитьГраницы":
            first = read_group(
                self.text, command.end, end, max_depth=self.limits.max_group_depth
            )
            second = (
                read_group(
                    self.text, first.end, end, max_depth=self.limits.max_group_depth
                )
                if first is not None
                else None
            )
            return second.end if second is not None else (first.end if first else command.end)
        if command.name in _DISCARD_ONE_GROUP_COMMANDS:
            group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            return group.end if group is not None else command.end
        if command.name == "setlength":
            first = read_group(
                self.text, command.end, end, max_depth=self.limits.max_group_depth
            )
            second = (
                read_group(
                    self.text, first.end, end, max_depth=self.limits.max_group_depth
                )
                if first is not None
                else None
            )
            return (
                second.end
                if second is not None
                else (first.end if first else command.end)
            )
        if command.name == "setcounter":
            return self._skip_groups(command, end, 2)
        if command.name == "definecolor":
            return self._skip_groups(command, end, 3)
        if command.name == "pgfdeclarepatternformonly":
            return self._skip_groups(command, end, 5)
        if command.name == "newdimen":
            next_cursor = skip_space_and_comments(self.text, command.end, end)
            declared = read_command(self.text, next_cursor, end)
            return declared.end if declared is not None else command.end
        if command.name in {"DotStep", "DotSize"}:
            newline = self.text.find("\n", command.end, end)
            return end if newline < 0 else newline
        if command.name in {"resizebox", "multicolumn", "multirow"}:
            groups = self._read_groups(command.end, end, 3)
            if len(groups) != 3:
                self._missing_argument(command)
                return groups[-1].end if groups else command.end
            nodes.extend(
                self._parse_inline(
                    groups[2].content_start,
                    groups[2].content_end,
                    depth=depth + 1,
                )
            )
            return groups[2].end
        if command.name == "end":
            group = read_group(
                self.text, command.end, end, max_depth=self.limits.max_group_depth
            )
            return group.end if group is not None else command.end
        if command.name in {
            "newcommand",
            "newcommand*",
            "providecommand",
            "providecommand*",
            "renewcommand",
            "renewcommand*",
            "def",
        }:
            declaration_end = self._local_macro_declaration_end(command, end)
            if declaration_end is None:
                self._missing_argument(command)
                return command.end
            return declaration_end
        if command.name in _NO_OUTPUT_COMMANDS:
            return command.end
        if command.name in _SUBPART_COMMANDS:
            optional = read_optional_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            nodes.append(
                self._count(
                    TextNode(
                        self.source_map.span(
                            command.start,
                            optional.end if optional is not None else command.end,
                        ),
                        " • ",
                    )
                )
            )
            if command.name == "пунктн":
                explicit = read_group(
                    self.text,
                    command.end,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                return explicit.end if explicit is not None else command.end
            return optional.end if optional is not None else command.end
        if command.name and set(command.name) == {"\ufffd"}:
            return command.end
        if command.name in {"", "\n", "\r", " "}:
            # A command may be clipped by the current semantic/block slice.
            # Only a backslash at the real source EOF is genuinely dangling.
            if command.end < len(self.text):
                return command.end
            self._diagnose(
                "latex.dangling_backslash",
                "Одиночный обратный слеш не образует LaTeX-команду.",
                command.start,
                command.end,
                recovery="Удалите слеш или используйте \\\\ для переноса строки.",
            )
            return command.end
        if command.name in _STRUCTURAL_COMMANDS:
            # A structural command nested inside a formatting group cannot be
            # represented safely as inline content. The outer block parser
            # handles top-level occurrences.
            self._diagnose(
                "latex.structure_in_inline_group",
                f"Структурная команда \\{command.name} вложена в inline-группу.",
                command.start,
                command.end,
                recovery="Вынесите конструкцию из команды форматирования.",
            )
            return command.end
        self._diagnose(
            "latex.unknown_macro",
            f"Команда \\{command.name} не входит в поддерживаемый LaTeX-корпус.",
            command.start,
            command.end,
            recovery="Замените команду поддерживаемой конструкцией или расширьте compiler с тестом.",
        )
        nodes.append(
            self._count(
                TextNode(
                    self.source_map.span(command.start, command.end),
                    self.text[command.start : command.end],
                )
            )
        )
        return command.end

    def _read_groups(self, start: int, end: int, count: int) -> tuple[GroupToken, ...]:
        groups: list[GroupToken] = []
        cursor = start
        for _ in range(count):
            group = read_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if group is None:
                break
            groups.append(group)
            cursor = group.end
        return tuple(groups)

    def _box_content_group(self, command: CommandToken, end: int) -> GroupToken | None:
        cursor = skip_space_and_comments(self.text, command.end, end)
        if self.text.startswith("to", cursor):
            group_start = self.text.find("{", cursor + 2, end)
            if group_start < 0:
                return None
            cursor = group_start
        return read_group(
            self.text,
            cursor,
            end,
            max_depth=self.limits.max_group_depth,
        )

    def _skip_groups(self, command: CommandToken, end: int, count: int) -> int:
        groups = self._read_groups(command.end, end, count)
        if len(groups) != count:
            self._missing_argument(command)
        return groups[-1].end if groups else command.end

    def _missing_argument(self, command: CommandToken) -> None:
        self._diagnose(
            "latex.argument_missing",
            f"Команда \\{command.name} не получила обязательную braced-группу.",
            command.start,
            command.end,
        )

    @staticmethod
    def _normalize_text(raw: str) -> str:
        return (
            raw.replace("---", "—")
            .replace("--", "–")
            .replace("<<", "«")
            .replace(">>", "»")
            .replace("~", "\u00a0")
        )

    def _parse_heading(
        self, command: CommandToken, end: int
    ) -> tuple[HeadingNode | None, int]:
        if command.name == "допраздел":
            return (
                self._count(
                    HeadingNode(
                        span=self.source_map.span(command.start, command.end),
                        level=2,
                        children=(
                            self._count(
                                TextNode(
                                    self.source_map.span(command.start, command.end),
                                    "Дополнительные задачи",
                                )
                            ),
                        ),
                    )
                ),
                command.end,
            )
        group = read_group(
            self.text,
            command.end,
            end,
            max_depth=self.limits.max_group_depth,
        )
        if group is None:
            self._missing_argument(command)
            return None, command.end
        return (
            self._count(
                HeadingNode(
                    span=self.source_map.span(command.start, group.end),
                    level=2,
                    children=self._parse_inline(group.content_start, group.content_end),
                )
            ),
            group.end,
        )

    def _parse_figure_command(
        self, command: CommandToken, end: int
    ) -> tuple[FigureNode | None, int]:
        optional = read_optional_group(
            self.text,
            command.end,
            end,
            max_depth=self.limits.max_group_depth,
        )
        cursor = optional.end if optional is not None else command.end
        if command.name == "includegraphics":
            group = read_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if group is None:
                self._missing_argument(command)
                return None, command.end
            options = (
                self.text[optional.content_start : optional.content_end]
                if optional is not None
                else ""
            )
            return self._asset_figure(
                command,
                group,
                width_hint=self._width_from_options(options),
                float_hint=None,
            ), group.end

        argument_count = (
            4 if command.name.endswith("w") or "picture" in command.name else 3
        )
        groups: list[GroupToken] = []
        for _ in range(argument_count):
            group = read_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if group is None:
                self._missing_argument(command)
                return None, cursor
            groups.append(group)
            cursor = group.end
        float_hint = "right" if command.name.startswith("right") else "left"
        width_hint = self.text[
            groups[-2].content_start : groups[-2].content_end
        ].strip()
        content_group = groups[-1]
        if "tikz" in command.name:
            wrapper_source = self._tikz_sources.get(command.start)
            nested_sources = tuple(
                source
                for source in self._tikz_sources.values()
                if content_group.content_start
                <= source.start
                < content_group.content_end
            )
            tikz_source = (
                wrapper_source.source
                if wrapper_source is not None
                else nested_sources[0].source
                if len(nested_sources) == 1
                else self.text[
                    content_group.content_start : content_group.content_end
                ].strip()
            )
            return self._tikz_figure(
                command.start,
                cursor,
                tikz_source,
                width_hint=width_hint,
                float_hint=float_hint,
            ), cursor
        return self._asset_figure(
            command,
            content_group,
            width_hint=width_hint,
            float_hint=float_hint,
            outer_end=cursor,
        ), cursor

    @staticmethod
    def _width_from_options(options: str) -> str | None:
        match = re.search(r"(?:^|,)\s*width\s*=\s*([^,]+)", options)
        return match.group(1).strip() if match is not None else None

    def _asset_figure(
        self,
        command: CommandToken,
        group: GroupToken,
        *,
        width_hint: str | None,
        float_hint: str | None,
        outer_end: int | None = None,
    ) -> FigureNode | None:
        raw_reference = self.text[group.content_start : group.content_end]
        logical_name = normalize_asset_reference(raw_reference)
        if logical_name is None:
            self._diagnose(
                "asset.reference_invalid",
                "Имя asset пусто, выходит из логического namespace или содержит опасные символы.",
                group.start,
                group.end,
                recovery="Используйте относительное логическое имя без .., URL и абсолютного пути.",
            )
            return None
        content_sha256 = (
            self.known_assets.get(logical_name)
            if self.known_assets is not None
            else None
        )
        if self.known_assets is not None and content_sha256 is None:
            self._diagnose(
                "asset.missing",
                "Указанный рисунок отсутствует в переданной библиотеке assets.",
                group.start,
                group.end,
                recovery="Сопоставьте существующий hash или загрузите недостающий asset.",
            )
        return self._count(
            FigureNode(
                span=self.source_map.span(command.start, outer_end or group.end),
                kind=FigureKind.ASSET,
                logical_name=logical_name,
                content_sha256=content_sha256,
                width_hint=width_hint or None,
                float_hint=float_hint,
                alt_text=PureAssetName.for_alt(logical_name),
            )
        )

    def _tikz_figure(
        self,
        start: int,
        end: int,
        tikz_source: str,
        *,
        width_hint: str | None,
        float_hint: str | None,
    ) -> FigureNode | None:
        if not tikz_source:
            self._diagnose("tikz.empty", "TikZ-блок пуст.", start, end)
            return None
        if len(tikz_source) > self.limits.max_tikz_chars:
            self._diagnose(
                "tikz.size_limit",
                "TikZ-блок превышает безопасный лимит размера.",
                start,
                end,
            )
            return None
        content_hash = hashlib.sha256(tikz_source.encode("utf-8")).hexdigest()
        logical_name = f"tikz-{content_hash[:16]}"
        if self.known_assets is not None and logical_name not in self.known_assets:
            self._diagnose(
                "asset.missing",
                "Сгенерированный SVG для TikZ отсутствует в переданной библиотеке assets.",
                start,
                end,
                recovery="Сконвертируйте TikZ в SVG и прикрепите полученный asset.",
            )
        return self._count(
            FigureNode(
                span=self.source_map.span(start, end),
                kind=FigureKind.TIKZ,
                logical_name=logical_name,
                content_sha256=content_hash,
                width_hint=width_hint or None,
                float_hint=float_hint,
                alt_text="Математический рисунок",
                tikz_source=tikz_source,
            )
        )

    def _parse_environment(
        self, command: CommandToken, end: int
    ) -> tuple[tuple[BlockNode, ...], int]:
        group = command_group(self.text, command, end, limits=self.limits)
        if group is None:
            self._missing_argument(command)
            return (), command.end
        environment = self.text[group.content_start : group.content_end].strip()
        match = find_environment_end(
            self.text,
            body_start=group.end,
            end=end,
            environment=environment,
            limits=self.limits,
        )
        if match is None:
            if environment in _CROSS_SEMANTIC_LAYOUT_ENVIRONMENTS:
                self._diagnose(
                    "latex.layout_crosses_semantic_boundary",
                    (
                        f"Print-layout environment {environment!r} пересекает границу "
                        "условия/подсказки/решения и не переносится в web AST."
                    ),
                    command.start,
                    group.end,
                    recovery="Web renderer сохраняет semantic field blocks без печатной раскладки.",
                    severity=DiagnosticSeverity.WARNING,
                )
                cursor = group.end
                if environment == "multicols":
                    argument_count = 1
                elif environment == "minipage":
                    placement = read_optional_group(
                        self.text,
                        cursor,
                        end,
                        max_depth=self.limits.max_group_depth,
                    )
                    if placement is not None:
                        cursor = placement.end
                    argument_count = 1
                elif environment in {"spacing", "tabular"}:
                    argument_count = 1
                elif environment in {"tabularx", "wrapfigure", "wraptable"}:
                    argument_count = 2
                else:
                    argument_count = 0
                if argument_count:
                    preamble_groups = self._read_groups(cursor, end, argument_count)
                    if preamble_groups:
                        cursor = preamble_groups[-1].end
                if environment == "center":
                    return self._parse_blocks(group.end, end), end
                return (), cursor
            self._diagnose(
                "latex.environment_unclosed",
                f"Environment {environment!r} не закрыт.",
                command.start,
                end,
            )
            return (), end
        environment_end_start, environment_end = match
        if environment not in _SUPPORTED_ENVIRONMENTS:
            self._diagnose(
                "latex.environment_unsupported",
                f"Environment {environment!r} не поддерживается compiler.",
                command.start,
                environment_end,
                recovery="Замените environment поддерживаемой структурой или добавьте parser fixture.",
            )
            return (), environment_end
        if environment == "comment":
            return (), environment_end
        if environment == "picture":
            self._diagnose(
                "latex.picture_ignored",
                "Legacy environment 'picture' пропущен до будущей конвертации в TikZ.",
                command.start,
                environment_end,
                recovery="Перенесите рисунок в TikZ для отображения в web-производной.",
                severity=DiagnosticSeverity.WARNING,
            )
            return (), environment_end
        if environment == "tikzpicture":
            raw = self.text[command.start : environment_end]
            extracted = self._tikz_sources.get(command.start)
            if extracted is not None:
                raw = extracted.source
            figure = self._tikz_figure(
                command.start,
                environment_end,
                raw.strip(),
                width_hint=None,
                float_hint=None,
            )
            return ((figure,) if figure is not None else ()), environment_end
        if environment in {
            "center",
            "figure",
            "footnotesize",
            "quote",
            "sideways",
            "small",
            "table",
            "tabbing",
        }:
            body_start = group.end
            if environment == "figure":
                placement = read_optional_group(
                    self.text,
                    body_start,
                    environment_end_start,
                    max_depth=self.limits.max_group_depth,
                )
                if placement is not None:
                    body_start = placement.end
            return self._parse_blocks(
                body_start, environment_end_start
            ), environment_end
        if environment in {"minipage", "spacing", "wrapfigure", "wraptable"}:
            body_start = group.end
            if environment == "minipage":
                placement = read_optional_group(
                    self.text,
                    body_start,
                    environment_end_start,
                    max_depth=self.limits.max_group_depth,
                )
                if placement is not None:
                    body_start = placement.end
                argument_count = 1
            elif environment in {"wrapfigure", "wraptable"}:
                argument_count = 2
            else:
                argument_count = 1
            arguments = self._read_groups(
                body_start, environment_end_start, argument_count
            )
            if len(arguments) != argument_count:
                self._diagnose(
                    "latex.environment_argument_missing",
                    f"Environment {environment!r} не содержит обязательные аргументы.",
                    command.start,
                    group.end,
                )
            elif arguments:
                body_start = arguments[-1].end
            return self._parse_blocks(
                body_start, environment_end_start
            ), environment_end
        if environment == "multicols":
            column_count = read_group(
                self.text,
                group.end,
                environment_end_start,
                max_depth=self.limits.max_group_depth,
            )
            if column_count is None:
                self._diagnose(
                    "latex.multicols_count_missing",
                    "Environment 'multicols' не содержит число колонок.",
                    command.start,
                    group.end,
                )
                body_start = group.end
            else:
                body_start = column_count.end
            return self._parse_blocks(
                body_start, environment_end_start
            ), environment_end
        if environment in _DISPLAY_MATH_ENVIRONMENTS:
            latex = self.text[group.end : environment_end_start].strip()
            if not latex:
                self._diagnose(
                    "latex.math_environment_empty",
                    f"Environment {environment!r} не содержит формулу.",
                    command.start,
                    environment_end,
                )
                return (), environment_end
            if environment.startswith("align"):
                latex = f"\\begin{{aligned}}{latex}\\end{{aligned}}"
            elif environment.startswith("gather") or environment == "multline*":
                latex = f"\\begin{{gathered}}{latex}\\end{{gathered}}"
            math = self._count(
                MathNode(
                    span=self.source_map.span(command.start, environment_end),
                    latex=latex,
                    display=True,
                )
            )
            return (
                self._count(
                    ParagraphNode(
                        span=self.source_map.span(command.start, environment_end),
                        children=(math,),
                    )
                ),
            ), environment_end
        if environment in {"itemize", "enumerate", "nums"}:
            return (
                self._parse_list(
                    command.start,
                    group.end,
                    environment_end_start,
                    environment_end,
                    ordered=environment != "itemize",
                ),
            ), environment_end
        flattened_figures = self._table_block_figures(
            command,
            group,
            environment,
            environment_end_start,
            environment_end,
        )
        if flattened_figures is not None:
            return flattened_figures, environment_end
        return (
            self._parse_table(
                command,
                group,
                environment,
                environment_end_start,
                environment_end,
            ),
        ), environment_end

    def _table_body_start(
        self,
        command: CommandToken,
        environment_group: GroupToken,
        environment: str,
        body_end: int,
    ) -> int:
        cursor = environment_group.end
        placement = read_optional_group(
            self.text,
            cursor,
            body_end,
            max_depth=self.limits.max_group_depth,
        )
        if placement is not None:
            cursor = placement.end
        argument_count = 2 if environment == "tabularx" else 1
        for _ in range(argument_count):
            group = read_group(
                self.text,
                cursor,
                body_end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
                self._diagnose(
                    "latex.table_preamble_missing",
                    "Таблица не содержит полного column preamble.",
                    command.start,
                    min(body_end, command.end + 1),
                )
                return cursor
            cursor = group.end
        return cursor

    def _table_block_figures(
        self,
        command: CommandToken,
        environment_group: GroupToken,
        environment: str,
        body_end: int,
        outer_end: int,
    ) -> tuple[BlockNode, ...] | None:
        # Compatibility boundary: vmshpwa/docs/content-compiler-support-matrix.md.
        body_start = self._table_body_start(
            command, environment_group, environment, body_end
        )
        structural = self._top_level_commands(
            body_start,
            body_end,
            {
                "begin",
                "includegraphics",
                "rightpicture",
                "leftpicture",
                "righttikz",
                "lefttikz",
                "righttikzw",
                "lefttikzw",
                "tikz",
            },
        )
        nested_tikz_sources = tuple(
            sorted(
                (
                    source
                    for source in self._tikz_sources.values()
                    if body_start <= source.start < body_end
                ),
                key=lambda source: source.start,
            )
        )
        if nested_tikz_sources:
            figures: list[BlockNode] = []
            for source in nested_tikz_sources:
                figure = self._tikz_figure(
                    source.start,
                    source.end,
                    source.source,
                    width_hint=None,
                    float_hint=None,
                )
                if figure is not None:
                    figures.append(figure)
            for candidate in structural:
                if candidate.name not in {
                    "includegraphics",
                    "leftpicture",
                    "rightpicture",
                }:
                    continue
                figure, _cursor = self._parse_figure_command(candidate, body_end)
                if figure is not None:
                    figures.append(figure)
            self._diagnose(
                "latex.table_figure_layout_flattened",
                "Табличная раскладка рисунков преобразована в последовательные web-блоки.",
                command.start,
                outer_end,
                severity=DiagnosticSeverity.WARNING,
            )
            return tuple(figures)
        has_figure = False
        for candidate in structural:
            if candidate.name != "begin":
                has_figure = True
                break
            group = command_group(self.text, candidate, body_end, limits=self.limits)
            if (
                group is not None
                and self.text[group.content_start : group.content_end].strip()
                == "tikzpicture"
            ):
                has_figure = True
                break
        if not has_figure:
            return None
        figures = tuple(
            node
            for node in self._parse_blocks(body_start, body_end)
            if isinstance(node, FigureNode)
        )
        self._diagnose(
            "latex.table_figure_layout_flattened",
            "Табличная раскладка рисунков преобразована в последовательные web-блоки.",
            command.start,
            outer_end,
            severity=DiagnosticSeverity.WARNING,
        )
        return figures

    def _parse_list(
        self,
        outer_start: int,
        body_start: int,
        body_end: int,
        outer_end: int,
        *,
        ordered: bool,
    ) -> ListNode:
        item_commands = self._top_level_commands(body_start, body_end, {"item"})
        items: list[ListItemNode] = []
        if not item_commands and self._has_visible_source(body_start, body_end):
            self._diagnose(
                "latex.list_without_items",
                "Список не содержит команд \\item.",
                body_start,
                body_end,
            )
        for index, item_command in enumerate(item_commands):
            item_end = (
                item_commands[index + 1].start
                if index + 1 < len(item_commands)
                else body_end
            )
            optional = read_optional_group(
                self.text,
                item_command.end,
                item_end,
                max_depth=self.limits.max_group_depth,
            )
            content_start = optional.end if optional is not None else item_command.end
            items.append(
                self._count(
                    ListItemNode(
                        span=self.source_map.span(item_command.start, item_end),
                        children=self._parse_blocks(content_start, item_end),
                    )
                )
            )
        return self._count(
            ListNode(
                span=self.source_map.span(outer_start, outer_end),
                ordered=ordered,
                items=tuple(items),
            )
        )

    def _parse_table(
        self,
        command: CommandToken,
        environment_group: GroupToken,
        environment: str,
        body_end: int,
        outer_end: int,
    ) -> TableNode:
        cursor = self._table_body_start(
            command, environment_group, environment, body_end
        )
        row_ranges = self._split_top_level(cursor, body_end, row_mode=True)
        rows: list[TableRowNode] = []
        for row_start, row_end in row_ranges:
            if not self._has_visible_source(row_start, row_end):
                continue
            cells: list[TableCellNode] = []
            for cell_start, cell_end in self._split_top_level(
                row_start, row_end, row_mode=False
            ):
                children = tuple(
                    inline
                    for paragraph in self._paragraphs(cell_start, cell_end)
                    for inline in paragraph.children
                )
                cells.append(
                    self._count(
                        TableCellNode(
                            span=self.source_map.span(cell_start, cell_end),
                            children=children,
                        )
                    )
                )
            if cells:
                rows.append(
                    self._count(
                        TableRowNode(
                            span=self.source_map.span(row_start, row_end),
                            cells=tuple(cells),
                        )
                    )
                )
        return self._count(
            TableNode(
                span=self.source_map.span(command.start, outer_end),
                rows=tuple(rows),
            )
        )

    def _split_top_level(
        self, start: int, end: int, *, row_mode: bool
    ) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []
        part_start = start
        cursor = start
        brace_depth = 0
        while cursor < end:
            if self.text[cursor] == "%" and not is_escaped(self.text, cursor):
                cursor = skip_comment(self.text, cursor, end)
                continue
            math = read_math(self.text, cursor, end)
            if math is not None:
                cursor = math.end
                continue
            character = self.text[cursor]
            if character == "{" and not is_escaped(self.text, cursor):
                bounded_group = read_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if bounded_group is None:
                    source_group = read_group(
                        self.text,
                        cursor,
                        len(self.text),
                        max_depth=self.limits.max_group_depth,
                    )
                    if source_group is not None:
                        cursor += 1
                        continue
                brace_depth += 1
                cursor += 1
                continue
            if character == "}" and not is_escaped(self.text, cursor):
                brace_depth = max(0, brace_depth - 1)
                cursor += 1
                continue
            command = read_command(self.text, cursor, end)
            is_row_boundary = (
                row_mode
                and brace_depth == 0
                and command is not None
                and command.name == "\\"
            )
            is_cell_boundary = not row_mode and brace_depth == 0 and character == "&"
            if is_row_boundary or is_cell_boundary:
                ranges.append((part_start, cursor))
                cursor = (
                    command.end
                    if command is not None and is_row_boundary
                    else cursor + 1
                )
                part_start = cursor
                continue
            cursor = command.end if command is not None else cursor + 1
        ranges.append((part_start, end))
        return ranges

    def _top_level_commands(
        self, start: int, end: int, names: set[str]
    ) -> tuple[CommandToken, ...]:
        result: list[CommandToken] = []
        cursor = start
        brace_depth = 0
        environment_depth = 0
        while cursor < end:
            if self.text[cursor] == "%" and not is_escaped(self.text, cursor):
                cursor = skip_comment(self.text, cursor, end)
                continue
            math = read_math(self.text, cursor, end)
            if math is not None:
                cursor = math.end
                continue
            character = self.text[cursor]
            if character == "{" and not is_escaped(self.text, cursor):
                bounded_group = read_group(
                    self.text,
                    cursor,
                    end,
                    max_depth=self.limits.max_group_depth,
                )
                if bounded_group is None:
                    source_group = read_group(
                        self.text,
                        cursor,
                        len(self.text),
                        max_depth=self.limits.max_group_depth,
                    )
                    if source_group is not None:
                        cursor += 1
                        continue
                brace_depth += 1
                cursor += 1
                continue
            if character == "}" and not is_escaped(self.text, cursor):
                brace_depth = max(0, brace_depth - 1)
                cursor += 1
                continue
            command = read_command(self.text, cursor, end)
            if command is None:
                cursor += 1
                continue
            if brace_depth == 0 and environment_depth == 0 and command.name in names:
                result.append(command)
            if command.name == "begin":
                environment_depth += 1
            elif command.name == "end":
                environment_depth = max(0, environment_depth - 1)
            cursor = command.end
        return tuple(result)

    def _top_level_structural_groups(
        self, start: int, end: int
    ) -> tuple[_StructuralGroup, ...]:
        result: list[_StructuralGroup] = []
        cursor = start
        while cursor < end:
            if self.text[cursor] == "%" and not is_escaped(self.text, cursor):
                cursor = skip_comment(self.text, cursor, end)
                continue
            math = read_math(self.text, cursor, end)
            if math is not None:
                cursor = math.end
                continue
            if self.text[cursor] != "{" or is_escaped(self.text, cursor):
                command = read_command(self.text, cursor, end)
                if command is not None and command.name in {
                    "newcommand",
                    "newcommand*",
                    "providecommand",
                    "providecommand*",
                    "renewcommand",
                    "renewcommand*",
                    "def",
                }:
                    declaration_end = self._local_macro_declaration_end(command, end)
                    if declaration_end is not None:
                        cursor = declaration_end
                        continue
                if command is not None and command.name in _FORMATTING_COMMANDS:
                    group = read_group(
                        self.text,
                        command.end,
                        end,
                        max_depth=self.limits.max_group_depth,
                    )
                    if group is not None and self._top_level_commands(
                        group.content_start,
                        group.content_end,
                        set(_STRUCTURAL_COMMANDS),
                    ):
                        result.append(
                            _StructuralGroup(
                                start=command.start,
                                content_start=group.content_start,
                                content_end=group.content_end,
                                end=group.end,
                            )
                        )
                        cursor = group.end
                        continue
                cursor = command.end if command is not None else cursor + 1
                continue
            group = read_group(
                self.text,
                cursor,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
                cursor += 1
                continue
            if self._top_level_commands(
                group.content_start,
                group.content_end,
                set(_STRUCTURAL_COMMANDS),
            ):
                result.append(
                    _StructuralGroup(
                        start=group.start,
                        content_start=group.content_start,
                        content_end=group.content_end,
                        end=group.end,
                    )
                )
            cursor = group.end
        return tuple(result)

    def _local_macro_declaration_end(
        self, command: CommandToken, end: int
    ) -> int | None:
        """Return the end of an inert local macro declaration.

        Declarations are never executed by the bounded parser. Their bodies must
        also stay opaque: otherwise braces containing TikZ or semantic commands
        can be mistaken for visible document blocks.
        """

        if command.name == "def":
            declared = read_command(
                self.text,
                skip_space_and_comments(self.text, command.end, end),
                end,
            )
            if declared is None:
                return None
            body_start = self.text.find("{", declared.end, end)
            if body_start < 0:
                return None
            body_group = read_group(
                self.text,
                body_start,
                end,
                max_depth=self.limits.max_group_depth,
            )
            return body_group.end if body_group is not None else None

        cursor = command.end
        name_group = read_group(
            self.text, cursor, end, max_depth=self.limits.max_group_depth
        )
        if name_group is None:
            name_command = read_command(
                self.text, skip_space_and_comments(self.text, cursor, end), end
            )
            if name_command is None:
                return None
            cursor = name_command.end
        else:
            cursor = name_group.end
        for _ in range(2):
            optional = read_optional_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if optional is None:
                break
            cursor = optional.end
        body_group = read_group(
            self.text, cursor, end, max_depth=self.limits.max_group_depth
        )
        return body_group.end if body_group is not None else None


class PureAssetName:
    @staticmethod
    def for_alt(logical_name: str) -> str:
        filename = logical_name.rsplit("/", 1)[-1]
        stem = filename.rsplit(".", 1)[0]
        return stem.replace("_", " ").replace("-", " ").strip() or "Рисунок"
