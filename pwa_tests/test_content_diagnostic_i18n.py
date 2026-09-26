"""P6: localized diagnostic projections preserve compiler output and user content."""

import json
from copy import deepcopy

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
