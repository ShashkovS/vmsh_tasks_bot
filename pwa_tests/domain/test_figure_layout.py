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


def presentation_document():
    return json.loads(
        compile_latex(
            r"\задача До.\includegraphics{same.png}После.\includegraphics{same.png}\кзадача\задача Соседняя.\кзадача".encode(),
            source_name="presentation.tex",
            role=ContentRole.CONDITION,
        ).web_document.content
    )


def source_entry(doc, index=0, **changes):
    row = figure_catalog(doc)[index]
    return dict(
        occurrenceId=row["occurrenceId"],
        targetOrdinal=row["sourceOrdinal"],
        targetPart=row["sourcePart"],
        section=row["sourceSection"],
        order=index,
        side="right",
        hidden=False,
        placement="source",
        **changes,
    )


def test_width_draft_preserves_source_position_and_other_asset_occurrences():
    doc = presentation_document()
    changed = apply_figure_layout(doc, [source_entry(doc, widthRem=0.5)])
    assert [b["type"] for b in changed["problems"][0]["blocks"]] == [
        b["type"] for b in doc["problems"][0]["blocks"]
    ]
    figures = figure_catalog(changed)
    assert figures[0]["figure"]["widthRem"] == 0.5
    assert "widthRem" not in figures[1]["figure"]
    assert "widthRem" not in figure_catalog(doc)[0]["figure"]


@pytest.mark.parametrize("placement", ["center-before", "center-after", "float-left", "float-right"])
def test_explicit_placement_at_target_boundaries(placement):
    doc = presentation_document()
    entry = {
        **source_entry(doc, widthRem=12),
        "targetOrdinal": 2,
        "placement": placement,
    }
    result = apply_figure_layout(doc, [entry])
    blocks = result["problems"][1]["blocks"]
    figure = blocks[-1] if placement == "center-after" else blocks[0]
    assert figure["type"] == "figure" and figure["widthRem"] == 12
    assert figure["placement"] == placement
    assert figure.get("floatHint") == (
        placement.removeprefix("float-") if placement.startswith("float-") else None
    )


@pytest.mark.parametrize("value", [0, 0.4, 80.5, 2.25, True, "12", float("nan"), float("inf")])
def test_invalid_editor_width(value):
    with pytest.raises(FigureLayoutError):
        apply_figure_layout(
            presentation_document(),
            [source_entry(presentation_document(), widthRem=value)],
        )


def test_hide_only_figure_in_part_and_restore_source():
    doc = json.loads(
        compile_latex(
            r"\задача\пункт\includegraphics{x.png}\кзадача".encode(),
            source_name="part.tex",
            role=ContentRole.CONDITION,
        ).web_document.content
    )
    hidden = apply_figure_layout(doc, [{**source_entry(doc), "hidden": True}])
    assert figure_catalog(hidden) == []
    assert apply_figure_layout(doc, []) == doc


def test_center_source_preserves_original_paragraphs_without_float():
    document = presentation_document()
    original = document["problems"][0]["blocks"]
    figure = next(b for b in original if b["type"] == "figure")
    figure["floatHint"] = "right"
    entry = {**source_entry(document, widthRem=12), "placement": "center-source"}
    result = apply_figure_layout(document, [entry])
    blocks = result["problems"][0]["blocks"]
    assert [b["type"] for b in blocks] == [b["type"] for b in original]
    edited = next(b for b in blocks if b["type"] == "figure")
    assert edited["placement"] == "center-source" and edited["widthRem"] == 12
    assert "floatHint" not in edited
