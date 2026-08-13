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


AST_SCHEMA_VERSION = 2

_PROBLEM_STARTS = {"задача", "problem", "problemn"}
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

_FORMATTING_COMMANDS = {
    "textbf": StrongNode,
    "выд": EmphasisNode,
    "emph": EmphasisNode,
    "textit": EmphasisNode,
    "it": EmphasisNode,
    "texttt": CodeNode,
}
_PRESERVE_GROUP_COMMANDS = {
    "boldrunes",
    "text",
    "textrm",
    "textsf",
    "hbox",
    "mbox",
    "centerline",
    "mathord",
    "phantom",
    "runes",
    "shortstack",
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
    "УстановитьГраницы",
    "УвеличитьВысоту",
    "УвеличитьШирину",
}
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
    "hfil",
    "hss",
    "break",
    "newpage",
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
    "em",
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
    "dots": "…",
    "ldots": "…",
    "dotsb": "…",
    "ldotsb": "…",
    "textbackslash": "\\",
    "dhchar": "ð",
    "thornchar": "þ",
    ",": "\u202f",
    "quad": " ",
    "qquad": " ",
}
_LINE_BREAK_COMMANDS = {"\\", "newline", "linebreak", "par"}
_STRUCTURAL_COMMANDS = {
    "пункт",
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
} | _ANNOUNCEMENT_COMMANDS
_SUPPORTED_ENVIRONMENTS = {
    "center",
    "itemize",
    "enumerate",
    "nums",
    "tabular",
    "tabularx",
    "tikzpicture",
}


@dataclass(frozen=True)
class _ProblemSlice:
    start_command: CommandToken
    statement_end: int
    fields_start: int
    outer_end: int


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

    def parse(self) -> DocumentAst:
        try:
            body_start, body_end = self._document_body()
            slices = self._problem_slices(body_start, body_end)
            introduction_end = slices[0].start_command.start if slices else body_end
            introduction = self._parse_blocks(body_start, introduction_end)
            problems = tuple(
                self._parse_problem(problem_slice, ordinal)
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

    def _parse_problem(self, problem_slice: _ProblemSlice, ordinal: int) -> ProblemNode:
        command = problem_slice.start_command
        header_end = command.end
        source_item: str | None = None
        source_title: str | None = None
        if command.name == "problemn":
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
        sections["statement"].append((header_end, problem_slice.statement_end))
        consumed_fields: list[tuple[int, int]] = []
        command_index = 0
        while command_index < len(commands):
            field_start = commands[command_index]
            field_kind = _FIELD_STARTS.get(field_start.name)
            if field_kind is None:
                command_index += 1
                continue
            expected_ends = _FIELD_ENDS[field_kind]
            field_end_index = next(
                (
                    candidate_index
                    for candidate_index in range(command_index + 1, len(commands))
                    if commands[candidate_index].name in expected_ends
                ),
                None,
            )
            if field_end_index is None:
                self._diagnose(
                    "latex.field_unclosed",
                    f"Блок {field_kind} не имеет завершающей команды.",
                    field_start.start,
                    problem_slice.outer_end,
                    recovery="Закройте блок соответствующей парной командой.",
                )
                sections[field_kind].append((field_start.end, problem_slice.outer_end))
                consumed_fields.append((field_start.start, problem_slice.outer_end))
                break
            field_end = commands[field_end_index]
            sections[field_kind].append((field_start.end, field_end.start))
            consumed_fields.append((field_start.start, field_end.end))
            command_index = field_end_index + 1

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
        structural = list(
            self._top_level_commands(start, end, set(_STRUCTURAL_COMMANDS))
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
            if command.name == "пункт":
                next_subpart = next(
                    (
                        candidate
                        for candidate in structural[structural_index + 1 :]
                        if candidate.start >= command.end and candidate.name == "пункт"
                    ),
                    None,
                )
                subpart_end = next_subpart.start if next_subpart is not None else end
                label = self._subpart_label(
                    sum(isinstance(node, SubpartNode) for node in nodes) + 1
                )
                nodes.append(
                    self._count(
                        SubpartNode(
                            span=self.source_map.span(command.start, subpart_end),
                            label=label,
                            children=self._parse_blocks(command.end, subpart_end),
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
        if 1 <= ordinal <= 26:
            return chr(ord("a") + ordinal - 1)
        return str(ordinal)

    def _paragraphs(self, start: int, end: int) -> list[ParagraphNode]:
        if start >= end:
            return []
        ranges: list[tuple[int, int]] = []
        paragraph_start = start
        for match in re.finditer(r"\n[ \t]*\n+", self.text[start:end]):
            boundary_start = start + match.start()
            if self._has_visible_source(paragraph_start, boundary_start):
                ranges.append((paragraph_start, boundary_start))
            paragraph_start = start + match.end()
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
                nodes.append(
                    self._count(
                        MathNode(
                            span=self.source_map.span(math.start, math.end),
                            latex=self.text[math.content_start : math.content_end],
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
        if command.name in _PRESERVE_GROUP_COMMANDS:
            group = read_group(
                self.text,
                command.end,
                end,
                max_depth=self.limits.max_group_depth,
            )
            if group is None:
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
        if command.name in {"resizebox", "multicolumn"}:
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
        if command.name in {"newcommand", "renewcommand"}:
            cursor = command.end
            name_group = read_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if name_group is None:
                self._missing_argument(command)
                return command.end
            cursor = name_group.end
            optional = read_optional_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            if optional is not None:
                cursor = optional.end
            body_group = read_group(
                self.text, cursor, end, max_depth=self.limits.max_group_depth
            )
            return body_group.end if body_group is not None else cursor
        if command.name in _NO_OUTPUT_COMMANDS:
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
            tikz_source = self.text[
                content_group.content_start : content_group.content_end
            ].strip()
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
            if environment in {"center", "tabular", "tabularx"}:
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
                if environment in {"tabular", "tabularx"}:
                    preamble_groups = self._read_groups(
                        cursor, end, 2 if environment == "tabularx" else 1
                    )
                    if preamble_groups:
                        cursor = preamble_groups[-1].end
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
        if environment == "tikzpicture":
            raw = self.text[command.start : environment_end]
            figure = self._tikz_figure(
                command.start,
                environment_end,
                raw.strip(),
                width_hint=None,
                float_hint=None,
            )
            return ((figure,) if figure is not None else ()), environment_end
        if environment == "center":
            return self._parse_blocks(group.end, environment_end_start), environment_end
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
        return (
            self._parse_table(
                command,
                group,
                environment,
                environment_end_start,
                environment_end,
            ),
        ), environment_end

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
        cursor = environment_group.end
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
                break
            cursor = group.end
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


class PureAssetName:
    @staticmethod
    def for_alt(logical_name: str) -> str:
        filename = logical_name.rsplit("/", 1)[-1]
        stem = filename.rsplit(".", 1)[0]
        return stem.replace("_", " ").replace("-", " ").strip() or "Рисунок"
