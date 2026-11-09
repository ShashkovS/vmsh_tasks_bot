"""Absent materials are normal; hint-preview-empty-materials-20261004.md."""

import json

import pytest

from helpers.pwa.content.compiler import compile_latex
from helpers.pwa.content.material_selection import (
    annotate_material_availability, web_problem_has_material,
)
from helpers.pwa.content.model import ContentRole, canonical_json


SOURCE = r"""
\задача Первая. \кзадача
\подсказка Совет. \кподсказка
\ответ 42 \кответ
\задача Вторая. \includegraphics{no-material-image} \кзадача
\подсказка % пусто
\кподсказка
\решение % пусто
\крешение
\задача Третья. \кзадача
\решение Доказательство. \крешение
\задача \пунктн{а} Первая часть. \пунктн{б} Вторая часть. \кзадача
\подсказка \пунктн{а} Совет для а. \пунктн{б} \кподсказка
\ответ \пунктн{а} \пунктн{б} 17 \кответ
"""


@pytest.mark.parametrize("role,ordinals,parts", [
    (ContentRole.HINT, [1, 4], ["а"]),
    (ContentRole.SOLUTION, [1, 3, 4], ["б"]),
])
def test_empty_sections_omit_buttons_and_do_not_require_statement_assets(role, ordinals, parts):
    result = compile_latex(SOURCE.encode(), source_name="materials.tex", role=role,
                           known_assets={}, revision_id="cr-123")
    assert not result.has_errors, result.diagnostics
    document = json.loads(result.web_document.content)
    assert [problem["ordinal"] for problem in document["problems"]] == ordinals
    assert document["problems"][-1]["materialPartLabels"] == parts
    assert "no-material-image" not in result.telegram.content
    assert "data-problem-ordinal=\"2\"" not in result.web.content
    assert web_problem_has_material(document["problems"][-1], parts[0])
    assert not web_problem_has_material(document["problems"][-1], "б" if parts == ["а"] else "а")


@pytest.mark.parametrize("role", [ContentRole.HINT, ContentRole.SOLUTION])
def test_old_figure_only_material_is_unavailable_without_rewriting_snapshot(role):
    result = compile_latex(SOURCE.encode(), source_name="materials.tex", role=role,
                           known_assets={}, revision_id="cr-123")
    canonical = json.loads(canonical_json(result.ast))
    before = canonical_json(canonical)
    old_document = {"problems": [{
        "ordinal": 2, "blocks": [{"type": "figure", "asset": {"status": "missing"}}],
    }]}
    annotate_material_availability(old_document, canonical, role)
    assert old_document["problems"][0]["materialAvailable"] is False
    assert not web_problem_has_material(old_document["problems"][0])
    assert canonical_json(canonical) == before


def test_shared_hint_remains_available_for_both_independent_parts():
    result = compile_latex(
        r"\задача \пунктн{а} Первая. \пунктн{б} Вторая. \кзадача \подсказка Общий совет. \кподсказка".encode(),
        source_name="common.tex", role=ContentRole.HINT, known_assets={}, revision_id="cr-123",
    )
    assert not result.has_errors
    problem = json.loads(result.web_document.content)["problems"][0]
    assert problem["materialPartLabels"] == ["а", "б"]
    assert all(web_problem_has_material(problem, part) for part in ["а", "б"])
