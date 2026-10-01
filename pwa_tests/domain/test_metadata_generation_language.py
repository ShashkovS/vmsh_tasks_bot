"""English two-pass generation; see vmshpwa/docs/metadata-generation.md."""

import json
import re
from dataclasses import replace

import pytest

from helpers.pwa.content import metadata_generation as adapter
from pwa_tests.domain.test_metadata_generation import _request
from vmsh_openrouter_tools_fixed_v2 import vmsh_openrouter_contract as contract


SOURCE = r"""
\раздел{Тест}
\задача Найдите число карточек.
\btitle{Число карточек}\bvalerr{Введите число.}\bwrong{Неверно.}\bcongrat{Верно!}
\bans{6}\кзадача
"""


def _row(**changes):
    return {
        "row_id": "0н.1",
        "prob": 1,
        "item": "",
        "source_title": "",
        "title": "Number of cards",
        "prob_text": "",
        "prob_type": "Тест",
        "ans_type": "Натуральное",
        "validation": {"mode": "builtin", "regex": "", "choices": []},
        "input_prompt": "Enter the number of cards.",
        "correct_answers": ["6"],
        "needs_checker": False,
        "checker_reason": "",
        "wrong_ans": "Try again.",
        "congrat": "All cards counted!",
        "answer_source": "embedded_metadata",
        "status": "ready",
        "image_dependency": {"required_for": [], "references": []},
        "notes": [],
        **changes,
    }


def _markup(**changes):
    return contract.LessonMarkup(
        schema_version="vmsh-lesson-json-v3",
        lesson_number=0,
        lesson_group="н",
        rows=[contract.LessonRow.model_validate(_row(**changes))],
        warnings=[],
    )


def _descriptions(value):
    if isinstance(value, dict):
        if "description" in value:
            yield value["description"]
        for child in value.values():
            yield from _descriptions(child)
    elif isinstance(value, list):
        for child in value:
            yield from _descriptions(child)


@pytest.mark.parametrize("locale", ["ru", "en"])
async def test_generation_and_fact_review_use_selected_model_and_language(
    monkeypatch, locale
):
    calls = []

    async def chat(**kwargs):
        calls.append(kwargs)
        if kwargs["schema_name"] == contract.LESSON_SCHEMA_NAME:
            return _markup().model_dump(mode="json")
        row = contract._factual_fields(_markup().rows[0])
        return {
            "schema_version": "vmsh-lesson-fact-review-v1",
            "rows": [{**row, "verdict": "confirmed", "reason": ""}],
            "warnings": [],
        }

    monkeypatch.setattr(contract, "_openrouter_chat", chat)
    result = await adapter.OpenRouterMetadataGenerator(api_key="test-key").generate(
        replace(
            _request(),
            latex_text=SOURCE,
            content_locale=locale,
            locale="ru" if locale == "en" else "en",
            model="openai/gpt-6-luna",
        )
    )
    assert len(calls) == 2
    assert all(call["model"] == "openai/gpt-6-luna" for call in calls)
    if locale == "en":
        assert result.rows[0]["title"] == "Number of cards"
        assert result.rows[0]["validationError"] == "Enter the number of cards."
        assert result.rows[0]["wrongAnswer"] == "Try again."
        assert result.rows[0]["congratulation"] == "All cards counted!"
        assert calls[0]["messages"][0]["content"] == contract.LESSON_SYSTEM_PROMPT_EN
        assert (
            calls[1]["messages"][0]["content"] == contract.FACT_REVIEW_SYSTEM_PROMPT_EN
        )
        for call in calls:
            assert all(
                not re.search(r"[А-Яа-яЁё]", text)
                for text in _descriptions(call["response_schema"])
            )
    else:
        assert result.rows[0]["title"] == "Число карточек"
        assert result.rows[0]["validationError"] == "Введите число."
        assert result.rows[0]["wrongAnswer"] == "Неверно."
        assert result.rows[0]["congratulation"] == "Верно!"
        assert calls[0]["messages"][0]["content"] == contract.LESSON_SYSTEM_PROMPT
        assert calls[1]["messages"][0]["content"] == contract.FACT_REVIEW_SYSTEM_PROMPT
    assert result.rows[0]["correctAnswer"] == "6"


async def test_english_retries_and_verification_failure_are_english(monkeypatch):
    calls = []

    async def chat(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _markup(title="").model_dump(mode="json")
        if kwargs["schema_name"] == contract.LESSON_SCHEMA_NAME:
            return _markup().model_dump(mode="json")
        return {}

    monkeypatch.setattr(contract, "_openrouter_chat", chat)
    result = await contract.generate_lesson_json(
        SOURCE, 0, "н", api_key="test-key", locale="en", verification_attempts=2
    )
    assert calls[1]["messages"][-1]["content"].startswith("The previous JSON failed")
    assert calls[3]["messages"][-1]["content"].startswith("The previous JSON failed")
    assert result["warnings"][0].startswith(
        "Fact review was not applied after 2 attempts"
    )


def test_english_normalization_preserves_answer_data_and_localizes_choice_suffix():
    parsed = contract.parse_lesson_structure(SOURCE, 0, "н", locale="en")
    markup = _markup(
        ans_type="Выбор",
        validation={"mode": "choices", "regex": "", "choices": ["6", "7"]},
        input_prompt="Choose an option.",
    )
    fixed = contract.canonicalize_with_source(markup, parsed, locale="en")
    assert fixed.rows[0].input_prompt == "Choose an option. Options: 6 or 7."
    assert fixed.rows[0].correct_answers == ["6"]
    assert contract.audit_lesson_markup(fixed, parsed, locale="en")[0] == []


def test_english_complex_format_accepts_an_english_example():
    parsed = contract.parse_lesson_structure(
        r"\раздел{Тест}\задача Enter two integers.\кзадача", 0, "н"
    )
    markup = _markup(
        ans_type="ДваЦелых",
        correct_answers=["1, 2"],
        input_prompt="Enter two integers. For example: 3, 4",
    )
    assert contract.audit_lesson_markup(markup, parsed, locale="en")[0] == []


def test_english_missing_image_and_custom_checker_messages():
    parsed = contract.parse_lesson_structure(
        r"\раздел{Тест}\задача\includegraphics{missing.png}\кзадача",
        0,
        "н",
        locale="en",
    )
    markup = _markup(
        status="needs_image",
        answer_source="image_missing",
        image_dependency={
            "required_for": ["title", "answer", "answer_format"],
            "references": ["missing.png"],
        },
    )
    fixed = contract.canonicalize_with_source(markup, parsed, locale="en")
    assert fixed.rows[0].title == "[IMAGE NEEDED FOR TITLE: 0н.1]"
    assert fixed.rows[0].input_prompt == "[IMAGE NEEDED FOR ANSWER FORMAT: 0н.1]"
    assert fixed.rows[0].correct_answers == ["[IMAGE NEEDED FOR ANSWER: 0н.1]"]
    assert contract.audit_lesson_markup(fixed, parsed, locale="en")[0] == []
    parsed = contract.parse_lesson_structure(
        r"\раздел{Тест}\задача\bchecker{check_answer}\кзадача", 0, "н", locale="en"
    )
    fixed = contract.canonicalize_with_source(_markup(), parsed, locale="en")
    assert fixed.rows[0].checker_reason == "The LaTeX specifies a custom checker."
    assert fixed.rows[0].correct_answers == []


def test_english_request_preview_and_parser_warnings():
    preview = contract.build_lesson_request_preview(
        r"\задача Find a number.\кзадача",
        0,
        "н",
        locale="en",
        model="provider/new-model:free",
    )
    assert preview["model"] == "provider/new-model:free"
    assert "Prepare lesson metadata in English" in json.dumps(preview["messages"])
    assert "has no section; using written submission" in json.dumps(preview["messages"])
