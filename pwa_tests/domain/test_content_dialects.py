"""newlistok parity: vmshpwa/docs/latex-content-pipeline.md."""

from pathlib import Path

import pytest

from helpers.pwa.content import ContentRole, compile_latex
from helpers.pwa.content.dialect import COMMAND_ALIASES, ENVIRONMENT_ENDS
from helpers.pwa.content.model import SubpartNode


def compile_body(body):
    return compile_latex(
        ("\\begin{document}\n" + body + "\n\\end{document}").encode(),
        source_name="dialects.tex",
        role=ContentRole.CONDITION,
    )


@pytest.mark.parametrize(
    "name,canonical",
    [
        (name, canonical)
        for name, canonical in COMMAND_ALIASES.items()
        if canonical in {"problem", "problemn", "пункт", "пунктн"}
    ],
)
def test_problem_and_item_aliases(name, canonical):
    argument = "{7}" if canonical in {"problemn", "пунктн"} else ""
    body = rf"\{name}{argument}[Description, with commas] Text $x^2$. "
    if canonical.startswith("problem"):
        body += r"\кзадача"
    else:
        body = r"\problem " + body + r"\eproblem"
    result = compile_body(body)
    assert not result.has_errors, result.diagnostics
    assert len(result.ast.problems) == 1
    problem = result.ast.problems[0]
    if canonical.startswith("problem"):
        assert problem.source_title == "Description, with commas"
        assert problem.source_item == ("7" if canonical == "problemn" else None)
    else:
        item = problem.statement[0]
        assert isinstance(item, SubpartNode)
        assert item.label == ("7" if canonical == "пунктн" else "а")
        assert "Description, with commas" in result.web.content


@pytest.mark.parametrize(
    "name,canonical",
    [
        (name, canonical)
        for name, canonical in COMMAND_ALIASES.items()
        if canonical in ENVIRONMENT_ENDS and not canonical.startswith("problem")
    ],
)
def test_paired_aliases_and_environment_forms(name, canonical):
    for body in (
        rf"\{name} SECRET \{ENVIRONMENT_ENDS[canonical]}",
        rf"\begin{{{name}}} SECRET \end{{{name}}}",
    ):
        result = compile_body(r"\problem Public. " + body + r"\кзадача")
        assert not result.has_errors, result.diagnostics
        if canonical in {"answer", "hint", "solution"}:
            assert getattr(result.ast.problems[0], canonical)
            assert "SECRET" not in result.web.content
            assert "SECRET" not in result.telegram.content
        else:
            assert "SECRET" in result.web.content


@pytest.mark.parametrize(
    "body,code",
    [
        (r"\problemn missing \eproblem", "latex.argument_missing"),
        (r"\problem \itmn missing \eproblem", "latex.argument_missing"),
        (
            r"\problem \announcement X \кважноеОбъявление \eproblem",
            "latex.announcement_end_mismatch",
        ),
        (
            r"\problem \definition X \endannouncement \eproblem",
            "latex.announcement_end_mismatch",
        ),
        (r"\problem \suggestion secret \крешение \eproblem", "latex.field_unclosed"),
        (r"\problem \unregistered X \eproblem", "latex.unknown_macro"),
    ],
)
def test_invalid_mixed_syntax_is_blocking(body, code):
    result = compile_body(body)
    assert result.has_errors
    assert code in {item.code for item in result.diagnostics}


def test_mixed_problem_environments_comments_and_positions():
    result = compile_body(r"""
\begin{comment}\problem Hidden \eproblem\end{comment}
\begin{hproblem}[Named] Visible \itm A \пункт B \end{задача}
\задача Next \eproblem
\endannouncement
""")
    assert len(result.ast.problems) == 2
    assert "Hidden" not in result.web.content
    diagnostic = next(
        d for d in result.diagnostics if d.code == "latex.announcement_end_unexpected"
    )
    assert diagnostic.span.start.line == 6
    assert diagnostic.span.start.column == 1


def test_style_formatting_and_layout_aliases_preserve_only_content():
    result = compile_body(r"""
\ListTitle{Hidden title}\ListNumber{42}\ListDate{date}\CreateTitle
\Sect{Section}\problem \mark{Italic} \выдж{Bold} \mark word tail.
\itmInline\IncreaseHeight{10mm}\ShowPageHeader\кзадача
""")
    assert not result.has_errors, result.diagnostics
    assert "<em>Italic</em>" in result.web.content
    assert "<strong>Bold</strong>" in result.web.content
    assert "<em>word</em>" in result.web.content
    assert "tail." in result.web.content
    for hidden in ("Hidden title", "42", "10mm"):
        assert hidden not in result.web.content


@pytest.mark.parametrize("name,count", [("class-ex-9.tex", 11), ("prep-10.tex", 6)])
def test_owner_examples(name, count):
    payload = (
        Path(__file__).parents[1] / "fixtures/content/newlistok" / name
    ).read_bytes()
    result = compile_latex(payload, source_name=name, role=ContentRole.CONDITION)
    assert not result.diagnostics
    assert len(result.ast.problems) == count
    if name == "class-ex-9.tex":
        assert "Basic properties" in result.web.content
        assert "Must these points" not in result.web.content
    else:
        assert "Definition." in result.web.content
        assert "It is called" in result.web.content


def test_local_definitions_are_inert_and_math_is_not_rewritten():
    result = compile_body(r"""
\newcommand{\hproblem}{\itm Not visible \eproblem}
\def\custom{\begin{problem} Hidden \end{problem}}
\problem Actual $\itm + \пункт$ \eproblem
""")
    assert not result.has_errors, result.diagnostics
    assert len(result.ast.problems) == 1
    assert "Not visible" not in result.web.content
    assert "Hidden" not in result.web.content
    assert r"\itm + \пункт" in result.web.content


@pytest.mark.parametrize(
    "name,canonical",
    [
        (name, canonical)
        for name, canonical in COMMAND_ALIASES.items()
        if canonical in set(ENVIRONMENT_ENDS.values())
    ],
)
def test_all_registered_closers_accept_equivalent_openers(name, canonical):
    opener = next(key for key, value in ENVIRONMENT_ENDS.items() if value == canonical)
    body = rf"\{opener} Text \{name}"
    if opener != "problem":
        body = r"\задача Public. " + body + r"\eproblem"
    result = compile_body(body)
    assert not result.has_errors, result.diagnostics


@pytest.mark.parametrize(
    "heading,expected",
    [
        ("Test problems", 1),
        ("TEST TASKS", 1),
        ("Tests", 1),
        ("Test-style exercises", 1),
        ("Quiz questions", 1),
        ("Quizzes", 1),
        ("Written problems", 2),
        ("Written tasks", 2),
        ("Writing exercises", 2),
        ("Oral problems", 3),
        ("Oral questions", 3),
        ("Spoken exercises", 3),
        ("Verbal tasks", 3),
        (r"\textbf{Test} problems", 1),
    ],
)
@pytest.mark.parametrize(
    "command",
    [
        "Sect",
        "section",
        "section*",
        "subsection",
        "subsection*",
        "subsubsection",
        "subsubsection*",
    ],
)
def test_english_heading_variants_set_problem_type(command, heading, expected):
    result = compile_body(rf"\{command}{{{heading}}}\problem Task.\eproblem")
    assert not result.has_errors, result.diagnostics
    assert result.ast.problems[0].problem_type == expected


@pytest.mark.parametrize(
    "heading",
    [
        "Contest problems",
        "Latest exercises",
        "Testament",
        "Untested ideas",
        "Coral geometry",
        "Unwritten rules",
        "Examples",
    ],
)
def test_unrelated_heading_does_not_change_current_type(heading):
    result = compile_body(
        rf"\Sect{{Oral tasks}}\problem First.\eproblem"
        rf"\Sect{{{heading}}}\problem Second.\eproblem"
    )
    assert not result.has_errors, result.diagnostics
    assert [p.problem_type for p in result.ast.problems] == [3, 3]


def test_heading_types_switch_and_persist_across_mixed_languages():
    result = compile_body(r"""
\problem Default.\eproblem
\Sect{Test problems}\problem Test one.\eproblem\problem Test two.\eproblem
\subsection*{Examples}\problem Still test.\eproblem
\Sect{Oral exercises}\problem Oral.\eproblem
\раздел{Письменные задачи}\problem Written.\eproblem
\Sect{Quiz}\задача Test again.\кзадача
% \Sect{Oral problems}
\begin{comment}\Sect{Written problems}\end{comment}
\newcommand{\unused}{\Sect{Oral problems}}
\problem Still test.\eproblem
""")
    assert not result.has_errors, result.diagnostics
    assert [p.problem_type for p in result.ast.problems] == [2, 1, 1, 1, 3, 2, 1, 1]


@pytest.mark.parametrize(
    "heading,expected",
    [
        ("Тест-задачи", 1),
        ("Письменные задачи", 2),
        ("Устные задачи", 3),
        ("Test and oral problems", 1),
        ("Written and oral problems", 3),
    ],
)
def test_heading_precedence_preserves_legacy_behavior(heading, expected):
    result = compile_body(rf"\Sect{{{heading}}}\problem Task.\eproblem")
    assert not result.has_errors, result.diagnostics
    assert result.ast.problems[0].problem_type == expected
