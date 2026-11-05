"""P6: localized diagnostic projections preserve compiler output and user content."""

import json
from copy import deepcopy

import pytest

from helpers.pwa.content.compiler import compile_latex
from helpers.pwa.content.diagnostic_i18n import localize_diagnostics
from helpers.pwa.content.model import ContentRole, canonical_json
from helpers.pwa.i18n import current_locale


def test_english_compiler_diagnostics_preserve_source_and_stored_values():
    # A command name in Russian and braces in source must survive interpolation.
    result = compile_latex(
        r"\задача Текст \неизвестная{авторский текст}\кзадача".encode(),
        source_name="условия.tex",
        role=ContentRole.CONDITION,
    )
    stored = json.loads(canonical_json(result.diagnostics))
    before = deepcopy(stored)
    token = current_locale.set("en")
    try:
        localized = localize_diagnostics(stored)
    finally:
        current_locale.reset(token)
    assert stored == before
    assert localize_diagnostics(stored) == stored
    unknown = next(item for item in localized if item["code"] == "latex.unknown_macro")
    assert (
        unknown["message"]
        == r"Command \неизвестная is not part of the supported LaTeX subset."
    )
    assert unknown["span"]["source_name"] == "условия.tex"
    for original, translated in zip(stored, localized, strict=True):
        assert {
            k: v for k, v in original.items() if k not in ("message", "recovery")
        } == {k: v for k, v in translated.items() if k not in ("message", "recovery")}


def test_unknown_diagnostics_remain_unchanged():
    items = [
        {"code": "custom", "message": "Авторский текст"},
        {"code": "latex.unknown_macro", "message": "Авторский текст"},
    ]
    token = current_locale.set("en")
    try:
        assert localize_diagnostics(items) == items
    finally:
        current_locale.reset(token)


@pytest.mark.parametrize(
    "section, english",
    [("подсказках", "hints"), ("ответе", "answer"), ("решении", "solution")],
)
@pytest.mark.parametrize("labelled", [False, True])
def test_part_mismatch_localizes_lists_and_preserves_labels(section, english, labelled):
    condition = "пункты а), б), в)" if labelled else "нет пунктов"
    original = [
        {
            "code": "material.parts_mismatch",
            "message": f"Задача 8: в условиях {condition}, а в {section} — а), б).",
        }
    ]
    token = current_locale.set("en")
    try:
        translated = localize_diagnostics(original)[0]["message"]
    finally:
        current_locale.reset(token)
    assert english in translated and "8" in translated
    assert "а), б)" in translated
    assert ("а), б), в)" in translated) == labelled


def test_old_part_mismatch_diagnostics_still_localize():
    token = current_locale.set("en")
    try:
        result = localize_diagnostics(
            [
                {
                    "code": "material.parts_mismatch",
                    "message": "Задача 8: пункты материала не совпадают с условием.",
                }
            ]
        )
    finally:
        current_locale.reset(token)
    assert result[0]["message"] != "Задача 8: пункты материала не совпадают с условием."
