"""Figure occurrences and material selection; vmshpwa/docs/figure-layout.md."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Iterable

from .model import ContentRole, DocumentAst, FigureNode


def occurrence_id(figure: FigureNode) -> str:
    value = (
        f"{figure.span.source_name}:{figure.span.start.offset}:{figure.span.end.offset}"
    )
    return "figure-" + hashlib.sha256(value.encode()).hexdigest()[:24]


def figures(blocks: Iterable) -> tuple[FigureNode, ...]:
    result = []
    for node in blocks:
        if isinstance(node, FigureNode):
            result.append(node)
        else:
            result.extend(figures(getattr(node, "children", ())))
            for item in getattr(node, "items", ()):
                result.extend(figures(item.children))
    return tuple(result)


def material_figures(document: DocumentAst) -> dict[int, tuple[FigureNode, ...]]:
    """Keep source-side illustrations without leaking statement text."""
    pending = figures(document.introduction)
    result = {}
    for problem in document.problems:
        result[problem.ordinal] = pending + figures(problem.statement)
        pending = figures(problem.trailing)
    if pending and document.problems:
        last = document.problems[-1].ordinal
        result[last] += pending
    return result


def selected_material_figures(
    document: DocumentAst, role: ContentRole
) -> tuple[FigureNode, ...]:
    """Shared inventory/compiler selection; content-recovery-20261004.md.

    Condition illustrations also appear in hint/solution renderers through
    material_figures. Keep their source spans, including repeated occurrences.
    """
    result = list(figures(document.introduction))
    for problem in document.problems:
        blocks = problem.statement + problem.trailing
        if role in {ContentRole.HINT, ContentRole.FULL_PREVIEW}:
            blocks += problem.hint
        if role in {ContentRole.SOLUTION, ContentRole.FULL_PREVIEW}:
            blocks += problem.answer + problem.solution
        result.extend(figures(blocks))
    return tuple(result)


def select_material_part(problem: dict, label: str) -> dict:
    """Keep shared blocks and only the selected labelled subpart."""
    result = copy.deepcopy(problem)

    def select(blocks):
        selected = []
        for block in blocks:
            if block.get("type") == "subpart":
                if block.get("label") == label:
                    selected.extend(select(block.get("blocks", [])))
            else:
                if isinstance(block.get("blocks"), list):
                    block["blocks"] = select(block["blocks"])
                if isinstance(block.get("items"), list):
                    block["items"] = [select(item) for item in block["items"]]
                selected.append(block)
        # Do not leave empty Answer/Solution headings after filtering.
        return [
            block
            for i, block in enumerate(selected)
            if not (
                block.get("type") == "heading"
                and (i + 1 == len(selected) or selected[i + 1].get("type") == "heading")
            )
        ]

    result["blocks"] = select(result.get("blocks", []))
    return result


class FigureLayoutError(ValueError):
    pass


def walk_figures(blocks):
    for block in blocks:
        if block.get("type") == "figure":
            yield block
        yield from walk_figures(block.get("blocks", []))
        for item in block.get("items", []):
            yield from walk_figures(item)


def figure_catalog(document: dict) -> list[dict]:
    """Every occurrence is editable independently of its storage asset."""
    result = []

    def collect(blocks, ordinal, part=None, section="common"):
        for block in blocks:
            if block.get("type") == "heading":
                label = block.get("children")
                if label == [{"type": "text", "value": "Ответ"}]:
                    section = "answer"
                elif label == [{"type": "text", "value": "Решение"}]:
                    section = "solution"
            if block.get("type") == "figure":
                if not block.get("occurrenceId"):
                    raise FigureLayoutError("recompile_required")
                result.append(
                    {
                        "occurrenceId": block["occurrenceId"],
                        "sourceOrdinal": ordinal,
                        "sourcePart": part,
                        "sourceSection": section,
                        "figure": copy.deepcopy(block),
                    }
                )
            collect(
                block.get("blocks", []),
                ordinal,
                block.get("label") if block.get("type") == "subpart" else part,
                section,
            )
            for item in block.get("items", []):
                collect(item, ordinal, part, section)

    collect(document.get("introduction", []), 0)
    for problem in document["problems"]:
        for field in ("preambleBlocks", "blocks", "trailingBlocks"):
            collect(problem.get(field, []), problem["ordinal"])
    ids = [row["occurrenceId"] for row in result]
    if len(ids) != len(set(ids)):
        raise FigureLayoutError("duplicate_occurrence")
    return result


def apply_figure_layout(document: dict, entries: list[dict]) -> dict:
    """Compose occurrence-scoped drafts; see vmshpwa/docs/figure-layout.md.

    ``source`` updates presentation in place. Entries without placement retain
    the previous side-based insertion semantics for saved legacy drafts.
    """
    import math

    result = copy.deepcopy(document)
    if not isinstance(entries, list) or len(entries) > 2000:
        raise FigureLayoutError("invalid_entries")
    if not entries:
        return result
    rows = {row["occurrenceId"]: row for row in figure_catalog(document)}
    problems = {p["ordinal"]: p for p in result["problems"]}
    by_id = {}
    required = {
        "occurrenceId",
        "targetOrdinal",
        "targetPart",
        "section",
        "order",
        "hidden",
    }
    optional = {"side", "placement", "widthRem", "scale"}
    placements = {
        "source",
        "center-source",
        "center-before",
        "center-after",
        "float-left",
        "float-right",
    }
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not required <= set(entry)
            or set(entry) - required - optional
        ):
            raise FigureLayoutError("invalid_entry")
        identity = entry["occurrenceId"]
        if not isinstance(identity, str) or identity not in rows or identity in by_id:
            raise FigureLayoutError("invalid_occurrence")
        if (
            type(entry["targetOrdinal"]) is not int
            or type(entry["hidden"]) is not bool
            or type(entry["order"]) is not int
            or not 0 <= entry["order"] <= 2000
            or not isinstance(entry["section"], str)
            or not isinstance(entry.get("side", "right"), str)
            or not isinstance(entry.get("placement", "float-right"), str)
            or entry.get("side", "right") not in {"left", "right"}
            or entry.get("placement", "float-right") not in placements
            or (
                entry["targetPart"] is not None
                and not isinstance(entry["targetPart"], str)
            )
        ):
            raise FigureLayoutError("invalid_placement")
        for field, lower, upper in (("widthRem", 0.5, 80), ("scale", 0.25, 2.5)):
            if field in entry:
                value = entry[field]
                if (
                    type(value) not in {int, float}
                    or not math.isfinite(value)
                    or not lower <= value <= upper
                ):
                    raise FigureLayoutError("invalid_size")
        if "widthRem" in entry and entry["widthRem"] * 2 != round(
            entry["widthRem"] * 2
        ):
            raise FigureLayoutError("invalid_size")
        source = rows[identity]
        if entry.get("placement") in {"source", "center-source"}:
            if (entry["targetOrdinal"], entry["targetPart"], entry["section"]) != (
                source["sourceOrdinal"],
                source["sourcePart"],
                source["sourceSection"],
            ):
                raise FigureLayoutError("invalid_target")
        else:
            target = problems.get(entry["targetOrdinal"])
            if target is None and not (
                entry["targetOrdinal"] == 0
                and source["sourceOrdinal"] == 0
                and entry["targetPart"] is None
            ):
                raise FigureLayoutError("invalid_target")
            if entry["targetPart"] is not None and entry[
                "targetPart"
            ] not in target.get("partLabels", []):
                raise FigureLayoutError("invalid_part")
        if entry["section"] not in (
            {"common", "answer", "solution"}
            if document["materialKind"] == "solution"
            else {"common"}
        ):
            raise FigureLayoutError("invalid_section")
        by_id[identity] = entry

    def presentation(figure, entry):
        for field in ("widthRem", "scale"):
            if field in entry:
                figure[field] = entry[field]
        placement = entry.get("placement")
        if placement and placement != "source":
            figure["placement"] = placement
            if placement.startswith("float-"):
                figure["floatHint"] = placement.removeprefix("float-")
            else:
                figure.pop("floatHint", None)
        elif placement is None:
            figure["floatHint"] = entry.get("side", "right")
        return figure

    def remove(blocks):
        kept = []
        for block in blocks:
            entry = by_id.get(block.get("occurrenceId"))
            if entry:
                if entry["hidden"] or entry.get("placement") not in {
                    "source",
                    "center-source",
                }:
                    continue
                presentation(block, entry)
            if "blocks" in block:
                block["blocks"] = remove(block["blocks"])
                if not block["blocks"]:
                    continue
            if "items" in block:
                block["items"] = [
                    value for item in block["items"] if (value := remove(item))
                ]
                if not block["items"]:
                    continue
            kept.append(block)
        return kept

    result["introduction"] = remove(result.get("introduction", []))
    for problem in result["problems"]:
        for field in ("preambleBlocks", "blocks", "trailingBlocks"):
            if field in problem:
                problem[field] = remove(problem[field])

    # Group each destination so appending and prepending share stable ordering.
    groups = {}
    for entry in entries:
        if not entry["hidden"] and entry.get("placement") not in {
            "source",
            "center-source",
        }:
            key = (
                entry["targetOrdinal"],
                entry["section"],
                entry["targetPart"],
                entry.get("placement") == "center-after",
            )
            groups.setdefault(key, []).append(entry)
    for (ordinal, section, part_label, after), values in groups.items():
        target = problems[ordinal]["blocks"] if ordinal else result["introduction"]
        label = {"answer": "Ответ", "solution": "Решение"}.get(section)
        start = 0
        if label:
            start = next(
                (
                    i + 1
                    for i, b in enumerate(target)
                    if b.get("type") == "heading"
                    and b.get("children") == [{"type": "text", "value": label}]
                ),
                -1,
            )
            if start < 0:
                target.append(
                    {
                        "type": "heading",
                        "level": 3,
                        "children": [{"type": "text", "value": label}],
                    }
                )
                start = len(target)
        end = next(
            (
                i
                for i in range(start, len(target))
                if target[i].get("type") == "heading"
            ),
            len(target),
        )
        if part_label is not None:
            part = next(
                (
                    b
                    for b in target[start:end]
                    if b.get("type") == "subpart" and b["label"] == part_label
                ),
                None,
            )
            if part is None:
                part = {"type": "subpart", "label": part_label, "blocks": []}
                target.insert(end, part)
            target = part["blocks"]
            start, end = 0, len(target)
        figures = [
            presentation(copy.deepcopy(rows[e["occurrenceId"]]["figure"]), e)
            for e in sorted(values, key=lambda e: (e["order"], e["occurrenceId"]))
        ]
        at = end if after else start
        target[at:at] = figures
    return result


def figure_presentation(document: dict) -> list[dict]:
    """Compare figure composition, ignoring titles and other editorial text."""
    output = []

    def visit(blocks, path):
        for index, block in enumerate(blocks):
            here = [*path, index]
            if block.get("type") == "figure":
                output.append(
                    {
                        "path": here,
                        **{
                            key: block[key]
                            for key in (
                                "occurrenceId",
                                "asset",
                                "widthHint",
                                "widthRem",
                                "scale",
                                "floatHint",
                                "placement",
                            )
                            if key in block
                        },
                    }
                )
            visit(block.get("blocks", []), [*here, "blocks"])
            for item_index, item in enumerate(block.get("items", [])):
                visit(item, [*here, "items", item_index])

    visit(document.get("introduction", []), ["introduction"])
    for problem in document["problems"]:
        for field in ("preambleBlocks", "blocks", "trailingBlocks"):
            visit(problem.get(field, []), [problem["ordinal"], field])
    return output


def render_layout_telegram(document: dict) -> str:
    """Render the same selected composition using the existing Telegram dialect."""
    import html
    from .telegram import sanitize_telegram_rich_html

    def inline(nodes):
        output = []
        for node in nodes:
            kind = node["type"]
            if kind == "text":
                output.append(html.escape(node["value"]))
            elif kind in {"math", "code"}:
                tag = "tg-math" if kind == "math" else "code"
                value = node["latex"] if kind == "math" else node["value"]
                output.append(f"<{tag}>{html.escape(value)}</{tag}>")
            else:
                tag = {"strong": "b", "emphasis": "i", "link": "a"}[kind]
                attr = (
                    f' href="{html.escape(node["href"], quote=True)}"'
                    if kind == "link"
                    else ""
                )
                output.append(f"<{tag}{attr}>{inline(node['children'])}</{tag}>")
        return "".join(output)

    def blocks(nodes):
        output = []
        for node in nodes:
            kind = node["type"]
            if kind in {"paragraph", "heading"}:
                tag = "p" if kind == "paragraph" else f"h{node['level']}"
                output.append(f"<{tag}>{inline(node['children'])}</{tag}>")
            elif kind == "formula":
                output.append(
                    f"<tg-math-block>{html.escape(node['latex'])}</tg-math-block>"
                )
            elif kind == "figure":
                asset = node["asset"]
                if asset["status"] == "available":
                    output.append(
                        f'<figure><img src="{html.escape(asset["src"], quote=True)}" alt="{html.escape(node["alt"], quote=True)}"/>'
                        + (
                            f"<figcaption>{inline(node['caption'])}</figcaption>"
                            if node.get("caption")
                            else ""
                        )
                        + "</figure>"
                    )
                else:
                    output.append("<aside>Рисунок пока недоступен.</aside>")
            elif kind == "subpart":
                output.append(
                    f"<p><b>{html.escape(node['label'])})</b></p>{blocks(node['blocks'])}"
                )
            elif kind == "callout":
                output.append(f"<aside>{blocks(node['blocks'])}</aside>")
            elif kind == "list":
                tag = "ol" if node["ordered"] else "ul"
                output.append(
                    f"<{tag}>"
                    + "".join(f"<li>{blocks(item)}</li>" for item in node["items"])
                    + f"</{tag}>"
                )
            elif kind == "table":
                output.append(
                    "<table>"
                    + "".join(
                        "<tr>"
                        + "".join(
                            f"<td>{inline(cell['children'])}</td>" for cell in row
                        )
                        + "</tr>"
                        for row in node["rows"]
                    )
                    + "</table>"
                )
        return "".join(output)

    result = blocks(document.get("introduction", []))
    for problem in document["problems"]:
        title = "Задача " + str(problem.get("taskReference") or problem["ordinal"])
        if problem.get("title"):
            title += ". «" + problem["title"] + "»"
        result += f"<h3>{html.escape(title)}</h3>" + blocks(
            problem.get("preambleBlocks", [])
            + problem["blocks"]
            + problem.get("trailingBlocks", [])
        )
    return sanitize_telegram_rich_html(result)
