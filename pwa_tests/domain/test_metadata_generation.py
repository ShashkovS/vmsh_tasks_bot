from __future__ import annotations

import pytest

from helpers.pwa.content import metadata_generation as metadata_generation_module
from helpers.pwa.content.metadata_generation import (
    GeneratedMetadata,
    MetadataGenerationError,
    MetadataGenerationRequest,
    MetadataGenerationTarget,
    MetadataGenerationUnavailable,
    OpenRouterMetadataGenerator,
    _normalize_generated_rows,
    _normalize_reference_markup,
    _upstream_generation_error,
    _user_prompt,
)


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


def test_metadata_generation_keeps_only_server_identities_and_test_fields():
    result = _normalize_generated_rows(
        _request(),
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
    assert error.public_message == (
        "OpenRouter отклонил запрос (403: доступ запрещён). Проверьте настоящий "
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
async def test_metadata_generation_uses_an_async_client_for_configured_proxy(
    monkeypatch: pytest.MonkeyPatch,
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
    ).generate(_request())

    assert len(result.rows) == 1
    assert calls[0]["kwargs"]["proxy"] == "http://127.0.0.1:1080"
    assert calls[0]["kwargs"]["reasoning_effort"] == "medium"
    assert calls[0]["kwargs"]["prompt_cache"] is True


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


def test_metadata_generation_never_uses_a_provisional_answer_that_needs_checker():
    result = _normalize_reference_markup(
        _request(),
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
        "1: эквивалентность выражений; добавьте checker вручную перед публикацией",
        "1: needs_checker",
    )
