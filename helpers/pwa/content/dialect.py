"""Static newlistok/newlistokutf vocabulary; never execute style definitions.

See vmshpwa/docs/latex-content-pipeline.md and test_content_dialects.py.
Only parser tokens are normalized: original source, math and spans stay intact.
"""

from dataclasses import replace

from . import scanner


COMMAND_ALIASES: dict[str, str] = {}


def _aliases(canonical: str, names: str) -> None:
    for name in names.split():
        COMMAND_ALIASES[name] = canonical


_aliases(
    "problem",
    "задача задачабк сзадача ссзадача взадача ввзадача пзадача пввзадача впвзадача "
    "ввпзадача здч сздч ссздч вздч ввздч problem hproblem hhproblem iproblem "
    "iiproblem wproblem wiiproblem prb hprb hhprb iprb iiprb wprb ",
)
_aliases(
    "problemn",
    "задачан сзадачан ссзадачан взадачан ввзадачан пзадачан пввзадачан впвзадачан "
    "ввпзадачан problemn hproblemn hhproblemn iproblemn iiproblemn wproblemn ",
)
_aliases("eproblem", "кзадача кздч eproblem eprb")
_aliases(
    "пункт", "пункт спункт сспункт впункт ввпункт ппункт itm hitm hhitm iitm iiitm witm"
)
_aliases(
    "пунктн",
    "пунктн спунктн сспунктн впунктн ввпунктн ппунктн itmn hitmn hhitmn iitmn iiitmn witmn",
)
_aliases("answer", "answer ответ отв")
_aliases("eanswer", "eanswer кответ котв")
_aliases("solution", "solution решение реш")
_aliases("esolution", "esolution крешение креш")
_aliases("hint", "hint suggestion указание указ подсказка")
_aliases("ehint", "ehint esuggestion куказание куказ кподсказка")
_aliases("объявление", "объявление announcement")
_aliases("кобъявление", "кобъявление endобъявление endannouncement")
_aliases("важноеОбъявление", "важноеОбъявление impAnnouncement")
_aliases(
    "кважноеОбъявление", "кважноеОбъявление endважноеОбъявление endimpAnnouncement"
)
_aliases("definition", "definition определение")
_aliases("edefinition", "edefinition копределение")
_aliases("раздел", "раздел Sect")
_aliases("допраздел", "допраздел AdditSect")
_aliases("mark", "mark markI выд выдк")
_aliases("markB", "markB выдд выдж")
for canonical, english in {
    "Заголовок": "ListTitle",
    "Подзаголовок": "ListSubtitle",
    "НомерЛистка": "ListNumber ExamNumber НомерСобеседования",
    "ДатаЛистка": "ListDate",
    "УвеличитьВысоту": "IncreaseHeight",
    "УвеличитьШирину": "IncreaseWidth",
    "СоздатьЗаголовок": "CreateTitle",
    "ВосстановитьГраницы": "DefaultIndents",
    "УстановитьГраницы": "SetIndents",
    "ВключитьКолонтитул": "ShowPageHeader ВключитьКолонитул",
    "ОбнулитьДанные": "ResetNumbers",
    "скрытьРешения": "hidesol",
    "разделитель": "solsep",
    "вСтрочку": "itmInline",
    "невСтрочку": "itmNewline",
    "сНовойСтроки": "wrapLine",
    "лк": "lk",
    "пк": "pk",
    "т": "mdash",
}.items():
    _aliases(canonical, english)

# Environment syntax is supported only for semantic paired commands.
ENVIRONMENT_ENDS = {
    "problem": "eproblem",
    "problemn": "eproblem",
    "answer": "eanswer",
    "hint": "ehint",
    "solution": "esolution",
    "объявление": "кобъявление",
    "важноеОбъявление": "кважноеОбъявление",
    "definition": "edefinition",
}
for name, canonical in tuple(COMMAND_ALIASES.items()):
    if canonical in ENVIRONMENT_ENDS:
        COMMAND_ALIASES["end" + name] = ENVIRONMENT_ENDS[canonical]


def normalize(
    text: str, command: scanner.CommandToken, end: int, limits: scanner.ParserLimits
) -> scanner.CommandToken:
    if command.name in {"begin", "end"}:
        group = scanner.command_group(text, command, end, limits=limits)
        if group is not None:
            name = text[group.content_start : group.content_end].strip()
            canonical = COMMAND_ALIASES.get(name, name)
            if canonical in ENVIRONMENT_ENDS:
                return replace(
                    command,
                    name=(
                        canonical
                        if command.name == "begin"
                        else ENVIRONMENT_ENDS[canonical]
                    ),
                    end=group.end,
                )
    return replace(command, name=COMMAND_ALIASES.get(command.name, command.name))


def read_command(
    text: str,
    start: int,
    end: int,
    *,
    limits: scanner.ParserLimits = scanner.ParserLimits(),
) -> scanner.CommandToken | None:
    command = scanner.read_command(text, start, end)
    return normalize(text, command, end, limits) if command else None


DECLARATIONS = {
    "newcommand",
    "newcommand*",
    "providecommand",
    "providecommand*",
    "renewcommand",
    "renewcommand*",
    "def",
}


def declaration_end(
    text: str, command: scanner.CommandToken, end: int, limits: scanner.ParserLimits
) -> int | None:
    """Skip inert declarations, including aliases in the declared name/body."""
    cursor = scanner.skip_space_and_comments(text, command.end, end)
    if command.name == "def":
        name = scanner.read_command(text, cursor, end)
        if name is None:
            return None
        cursor = text.find("{", name.end, end)
        if cursor < 0:
            return None
    else:
        name_group = scanner.read_group(
            text, cursor, end, max_depth=limits.max_group_depth
        )
        name = scanner.read_command(text, cursor, end) if name_group is None else None
        if name_group is None and name is None:
            return None
        cursor = name_group.end if name_group is not None else name.end
        for _ in range(2):
            optional = scanner.read_optional_group(
                text, cursor, end, max_depth=limits.max_group_depth
            )
            if optional is None:
                break
            cursor = optional.end
    body = scanner.read_group(text, cursor, end, max_depth=limits.max_group_depth)
    return body.end if body is not None else None


def scan_commands(
    text: str, *, start: int, end: int, limits: scanner.ParserLimits, **kwargs
) -> tuple[scanner.CommandToken, ...]:
    commands = []
    cursor = start
    for command in scanner.scan_commands(
        text, start=start, end=end, limits=limits, **kwargs
    ):
        if command.start < cursor:
            continue
        commands.append(normalize(text, command, end, limits))
        if command.name in DECLARATIONS:
            cursor = declaration_end(text, command, end, limits) or command.end
    return tuple(commands)
