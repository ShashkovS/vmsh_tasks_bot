from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from helpers.pwa.content import metadata_generation as metadata_generation_module
from helpers.pwa.content.metadata_generation import (
    GENERATION_TIMEOUT_SECONDS,
    GeneratedMetadata,
    MetadataGenerationError,
    MetadataGenerationRequest,
    MetadataGenerationTarget,
    MetadataGenerationUnavailable,
    OpenRouterMetadataGenerator,
    _contract_latex,
    _normalize_generated_rows,
    _normalize_reference_markup,
    _upstream_generation_error,
    _user_prompt,
)
from vmsh_openrouter_tools_fixed_v2 import vmsh_openrouter_contract as markup_contract


def _request() -> MetadataGenerationRequest:
    return MetadataGenerationRequest(
        revision_public_id="content-revision-1",
        source_filename="usl-00-n.tex",
        latex_text="\\задача Найдите 7. \\кзадача",
        targets=(
            MetadataGenerationTarget(
                source_ordinal=1,
                source_item="1",
                display_number="1",
                source_title=None,
                problem_id=101,
            ),
        ),
    )


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_metadata_generation_keeps_only_server_identities_and_test_fields(locale):
    result = _normalize_generated_rows(
        replace(_request(), locale=locale),
        GeneratedMetadata.model_validate(
            {
                "rows": [
                    {
                        "sourceOrdinal": 1,
                        "sourceItem": "1",
                        "title": "Найдите число",
                        "problemType": 2,
                        "answerType": 3,
                        "answerValidation": None,
                        "validationError": None,
                        "correctAnswer": "7",
                        "wrongAnswer": None,
                        "congratulation": None,
                        "reviewNote": "Проверьте способ сдачи",
                    }
                ],
                "warnings": [],
            }
        ),
    )

    assert result.rows == (
        {
            "problemId": 101,
            "sourceOrdinal": 1,
            "sourceItem": "1",
            "displayNumber": "1",
            "title": "Найдите число",
            "problemType": 2,
            "answerType": None,
            "answerValidation": None,
            "validationError": None,
            "correctAnswer": None,
            "correctAnswerChecker": None,
            "wrongAnswer": None,
            "congratulation": None,
        },
    )
    assert result.warnings == ("1: Проверьте способ сдачи",)


def test_metadata_generation_rejects_missing_or_extra_model_rows():
    with pytest.raises(MetadataGenerationError, match="do not match"):
        _normalize_generated_rows(
            _request(),
            GeneratedMetadata.model_validate(
                {
                    "rows": [
                        {
                            "sourceOrdinal": 2,
                            "sourceItem": "1",
                            "title": "Лишняя",
                            "problemType": 2,
                            "answerType": None,
                            "answerValidation": None,
                            "validationError": None,
                            "correctAnswer": None,
                            "wrongAnswer": None,
                            "congratulation": None,
                            "reviewNote": None,
                        }
                    ],
                    "warnings": [],
                }
            ),
        )


def test_metadata_generation_sends_latex_before_small_target_table():
    prompt = _user_prompt(_request())

    assert prompt.index("\\задача") < prompt.index("canonical строк")


class _UpstreamError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_metadata_generation_explains_openrouter_access_denial_safely():
    error = _upstream_generation_error(_UpstreamError(403))

    assert str(error) == "OpenRouter denied metadata generation with HTTP 403"
    assert error.public_params == {"status_code": 403}
    assert error.public_message == (
        "OpenRouter отклонил запрос ({status_code}: доступ запрещён). Проверьте настоящий "
        "OPENROUTER_API_KEY в production-конфиге и ограничения этого ключа."
    )


@pytest.mark.asyncio
async def test_metadata_generation_rejects_the_checked_in_example_key():
    generator = OpenRouterMetadataGenerator(api_key="sk-or-v1-XXX_HERE")

    with pytest.raises(MetadataGenerationUnavailable, match="usable API key") as raised:
        await generator.generate(_request())

    assert raised.value.public_message == (
        "Генерация metadata не настроена: укажите настоящий OPENROUTER_API_KEY "
        "в production-конфиге."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,source,expected_identity",
    [
        ("usl-00-n.tex", r"\задача Найдите 7. \кзадача", (0, "н")),
        (
            "number-theory.tex",
            r"\Sect{Written problems}\problem Find 7.\eproblem\answer 7\eanswer",
            (0, "н"),
        ),
        (
            "worksheet.tex",
            r"\ListNumber{12п}\раздел{Written problems}\problem Find 7.\eproblem",
            (12, "п"),
        ),
        (
            "worksheet.tex",
            r"\Sect{Written problems}\begin{problem}Find 7.\end{problem}\begin{answer}7\end{answer}",
            (0, "н"),
        ),
    ],
)
async def test_metadata_generation_uses_an_async_client_for_configured_proxy(
    monkeypatch: pytest.MonkeyPatch,
    filename,
    source,
    expected_identity,
):
    calls: list[dict[str, object]] = []

    async def fake_generate_lesson_json(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return {
            "rows": [
                {
                    "prob": 1,
                    "item": "",
                    "title": "Черновик",
                    "prob_type": "Письменно",
                    "ans_type": "",
                    "validation": {"mode": "none", "regex": "", "choices": []},
                    "input_prompt": "",
                    "correct_answers": [],
                    "wrong_ans": "",
                    "congrat": "",
                    "needs_checker": False,
                    "status": "ready",
                    "notes": [],
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(
        metadata_generation_module, "generate_lesson_json", fake_generate_lesson_json
    )

    result = await OpenRouterMetadataGenerator(
        api_key="sk-or-v1-live-key",
        proxy="http://127.0.0.1:1080",
    ).generate(replace(_request(), source_filename=filename, latex_text=source))

    assert len(result.rows) == 1
    assert calls[0]["kwargs"]["proxy"] == "http://127.0.0.1:1080"
    assert calls[0]["kwargs"]["reasoning_effort"] == "medium"
    assert calls[0]["kwargs"]["timeout_seconds"] == GENERATION_TIMEOUT_SECONDS
    assert calls[0]["kwargs"]["prompt_cache"] is True
    assert calls[0]["args"][1:3] == expected_identity
    parsed = markup_contract.parse_lesson_structure(
        markup_contract.clean_latex_document(calls[0]["args"][0]),
        *expected_identity,
        locale="en",
    )
    assert len(parsed.rows) == 1
    assert parsed.rows[0].prob_type == "Письменно"
    if "answer" in source:
        assert parsed.tasks[0].answer == "7"


def test_metadata_contract_dialect_preserves_math_comments_macros_and_drawings():
    untouched = r"""% \problem commented out
\renewcommand{\problem}{A macro body with \answer}
$\problem + \answer$
\begin{tikzpicture}\node {\problem};\end{tikzpicture}
\begin{verbatim}\problem example\end{verbatim}
"""
    assert _contract_latex(untouched) == untouched


@pytest.mark.parametrize(
    "heading,expected",
    [
        ("Test problems", "Тест"),
        ("Written problems", "Письменно"),
        ("Oral problems", "Письменно<-Устно"),
    ],
)
@pytest.mark.parametrize("fields_inside", [False, True])
def test_metadata_contract_uses_english_section_types_and_subitems(
    heading, expected, fields_inside
):
    teacher_fields = r"\answer\itm 1\itm 2\eanswer\suggestion Hint.\esuggestion\solution Explanation.\esolution"
    source = rf"\Sect{{{heading}}}\problem\itm First.\itm Second."
    source += (
        teacher_fields + r"\eproblem"
        if fields_inside
        else r"\eproblem" + teacher_fields
    )
    parsed = markup_contract.parse_lesson_structure(
        _contract_latex(source), 0, "н", locale="en"
    )
    assert [row.prob_type for row in parsed.rows] == [expected, expected]
    assert parsed.tasks[0].answer_parts == ["1", "2"]
    assert parsed.tasks[0].hint == "Hint."
    assert parsed.tasks[0].solution == "Explanation."
    assert parsed.tasks[0].statement_parts == ["First.", "Second."]


@pytest.mark.asyncio
async def test_metadata_generation_reports_its_local_deadline(
    monkeypatch: pytest.MonkeyPatch,
):
    async def stalled_generate_lesson_json(*_args, **_kwargs):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(
        metadata_generation_module, "generate_lesson_json", stalled_generate_lesson_json
    )

    with pytest.raises(
        MetadataGenerationError, match="local request deadline"
    ) as raised:
        await OpenRouterMetadataGenerator(
            api_key="sk-or-v1-live-key", timeout_ms=1
        ).generate(_request())

    assert raised.value.public_message == (
        "OpenRouter не ответил за отведённое время. Черновик не был сохранён; "
        "повторите генерацию позже."
    )


def test_metadata_generation_maps_verified_choice_contract_to_pwa_fields():
    result = _normalize_reference_markup(
        _request(),
        {
            "rows": [
                {
                    "prob": 1,
                    "item": "",
                    "title": "Выберите ответ",
                    "prob_type": "Тест",
                    "ans_type": "Выбор",
                    "validation": {
                        "mode": "choices",
                        "regex": "",
                        "choices": ["да", "нет"],
                    },
                    "input_prompt": "Выберите верный вариант.",
                    "correct_answers": ["да"],
                    "wrong_ans": "Нет.",
                    "congrat": "Верно!",
                    "needs_checker": False,
                    "status": "ready",
                    "notes": [],
                }
            ],
            "warnings": ["Проверьте выбор."],
        },
    )

    assert result.rows[0]["answerType"] == 98
    assert result.rows[0]["answerValidation"] == "да;нет"
    assert result.rows[0]["correctAnswer"] == "да"
    assert result.warnings == ("Проверьте выбор.",)


def test_source_markup_turns_named_closed_question_into_complete_choice():
    source = r"""
\begin{document}
\раздел{<<Тест>> задачи}
\задача
Петя взял числа, а Вася взял другие числа.
\пункт У кого сумма получилась больше?
\пункт На сколько?
\кзадача
\ответ
\пункт У Васи.
\пункт На 34.
\кответ
\end{document}
"""
    parsed = markup_contract.parse_lesson_structure(source, 0, "п")
    rows = [
        markup_contract.LessonRow(
            row_id=expected.row_id,
            prob=expected.prob,
            item=expected.item,
            source_title="",
            title=f"Черновик {expected.item}",
            prob_text="",
            prob_type="Тест",
            ans_type="Строка",
            validation={
                "mode": "regex",
                "regex": "(?i:(?:У Васи))",
                "choices": [],
            },
            input_prompt="Введите ответ.",
            correct_answers=["У Васи" if expected.item == "а" else "34"],
            needs_checker=False,
            checker_reason="",
            wrong_ans="Нет.",
            congrat="Верно!",
            answer_source="explicit_answer",
            status="ready",
            image_dependency={"required_for": [], "references": []},
            notes=[],
        )
        for expected in parsed.rows
    ]
    markup = markup_contract.LessonMarkup(
        schema_version="vmsh-lesson-json-v3",
        lesson_number=0,
        lesson_group="п",
        rows=rows,
        warnings=[],
    )

    fixed = markup_contract.canonicalize_with_source(markup, parsed)

    selected = fixed.rows[0]
    assert selected.ans_type == "Выбор"
    assert selected.validation.mode == "choices"
    assert selected.validation.choices == ["Петя", "Вася"]
    assert selected.correct_answers == ["Вася"]
    assert all(name in selected.input_prompt for name in ("Петя", "Вася"))
    assert markup_contract.audit_lesson_markup(fixed, parsed)[0] == []


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_metadata_generation_never_uses_a_provisional_answer_that_needs_checker(locale):
    result = _normalize_reference_markup(
        replace(_request(), locale=locale),
        {
            "rows": [
                {
                    "prob": 1,
                    "item": "",
                    "title": "Нестандартная проверка",
                    "prob_type": "Тест",
                    "ans_type": "Строка",
                    "validation": {"mode": "builtin", "regex": "", "choices": []},
                    "input_prompt": "Введите ответ.",
                    "correct_answers": ["только для проверки модели"],
                    "wrong_ans": "Неверно.",
                    "congrat": "Верно!",
                    "needs_checker": True,
                    "checker_reason": "эквивалентность выражений",
                    "status": "needs_checker",
                    "notes": [],
                }
            ],
            "warnings": [],
        },
    )

    assert result.rows[0]["correctAnswer"] is None
    assert result.warnings == (
        (
            "1: эквивалентность выражений; добавьте checker вручную перед публикацией"
            if locale == "ru"
            else "1: эквивалентность выражений; add a checker manually before publishing"
        ),
        "1: needs_checker",
    )
