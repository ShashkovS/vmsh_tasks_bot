import json
from pathlib import Path

import pytest

from helpers.pwa.content import compile_latex, ContentRole
from helpers.pwa.content.figure_layout import (
    apply_figure_layout,
    figure_catalog,
    select_material_part,
    FigureLayoutError,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "figure-layout"


def document(name):
    result = compile_latex(
        (FIXTURES / name).read_bytes(), source_name=name, role=ContentRole.SOLUTION
    )
    assert result.web_document
    return json.loads(result.web_document.content)


def test_source_side_solution_figures_survive():
    doc = document("usl-01-n-sol.tex")
    catalog = figure_catalog(doc)
    assert len([f for f in catalog if f["sourceOrdinal"] == 9]) == 2
    assert len([f for f in catalog if f["sourceOrdinal"] == 11]) == 1
    assert len([f for f in catalog if f["sourceOrdinal"] == 12]) == 1


def test_answers_and_explanations_are_selected_per_part():
    doc = document("usl-01-p-sol.tex")
    problem = next(p for p in doc["problems"] if p["ordinal"] == 1)
    first = json.dumps(select_material_part(problem, "а"), ensure_ascii=False)
    second = json.dumps(select_material_part(problem, "б"), ensure_ascii=False)
    assert "48 треугольников" in first and "243 треугольника" not in first
    assert "243 треугольника" in second and "48 треугольников" not in second


def test_moves_hide_restore_and_preserve_original():
    doc = document("usl-01-n-sol.tex")
    before = json.dumps(doc)
    original = next(f for f in figure_catalog(doc) if f["sourceOrdinal"] == 9)
    entry = dict(
        occurrenceId=original["occurrenceId"],
        targetOrdinal=11,
        targetPart=None,
        section="solution",
        order=0,
        side="left",
        hidden=False,
    )
    moved = apply_figure_layout(doc, [entry])
    assert (
        next(
            f
            for f in figure_catalog(moved)
            if f["occurrenceId"] == entry["occurrenceId"]
        )["sourceOrdinal"]
        == 11
    )
    assert all(
        f["occurrenceId"] != entry["occurrenceId"]
        for f in figure_catalog(apply_figure_layout(doc, [{**entry, "hidden": True}]))
    )
    assert apply_figure_layout(doc, []) == doc
    assert json.dumps(doc) == before
    with pytest.raises(FigureLayoutError):
        apply_figure_layout(doc, [{**entry, "targetOrdinal": 999}])


def test_incompatible_material_parts_are_diagnostic():
    result = compile_latex(
        r"\задача\пункт Один.\пункт Два.\кзадача\ответ\пункт Только один.\кответ".encode(),
        source_name="parts.tex",
        role=ContentRole.SOLUTION,
    )
    assert any(
        d.code == "material.parts_mismatch" and d.severity.value == "error"
        for d in result.diagnostics
    )


def test_repeated_asset_occurrences_and_telegram_projection():
    from helpers.pwa.content.figure_layout import render_layout_telegram

    result = compile_latex(
        r"\задача СЕКРЕТ УСЛОВИЯ.\includegraphics{x.png}\includegraphics{x.png}\кзадача\ответ Да.\кответ".encode(),
        source_name="repeat.tex",
        role=ContentRole.SOLUTION,
    )
    doc = json.loads(result.web_document.content)
    catalog = figure_catalog(doc)
    assert (
        len(catalog) == 2 and catalog[0]["occurrenceId"] != catalog[1]["occurrenceId"]
    )
    entry = dict(
        occurrenceId=catalog[0]["occurrenceId"],
        targetOrdinal=1,
        targetPart=None,
        section="common",
        order=0,
        side="right",
        hidden=True,
    )
    html = render_layout_telegram(apply_figure_layout(doc, [entry]))
    assert "СЕКРЕТ" not in html and "Да." in html
    assert html.count("Рисунок пока недоступен") == 1
    with pytest.raises(FigureLayoutError):
        apply_figure_layout(doc, [{**entry, "targetOrdinal": []}])
