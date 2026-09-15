"""Figure occurrences and material selection; vmshpwa/docs/figure-layout.md."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Iterable

from .model import DocumentAst, FigureNode


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
    """Move/remove whole occurrences without changing the original document."""
    result = copy.deepcopy(document)
    if not isinstance(entries, list) or len(entries) > 2000:
        raise FigureLayoutError("invalid_entries")
    if not entries:
        return result
    catalog = {row["occurrenceId"]: row["figure"] for row in figure_catalog(document)}
    problems = {p["ordinal"]: p for p in result["problems"]}
    ids = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "occurrenceId",
            "targetOrdinal",
            "targetPart",
            "section",
            "order",
            "side",
            "hidden",
        }:
            raise FigureLayoutError("invalid_entry")
        if (
            not isinstance(entry["occurrenceId"], str)
            or type(entry["targetOrdinal"]) is not int
            or not isinstance(entry["side"], str)
            or not isinstance(entry["section"], str)
            or (
                entry["targetPart"] is not None
                and not isinstance(entry["targetPart"], str)
            )
        ):
            raise FigureLayoutError("invalid_entry")
        identity = entry["occurrenceId"]
        if identity not in catalog or identity in ids:
            raise FigureLayoutError("invalid_occurrence")
        ids.add(identity)
        target = problems.get(entry["targetOrdinal"])
        if target is None:
            raise FigureLayoutError("invalid_target")
        if (
            entry["side"] not in {"left", "right"}
            or type(entry["hidden"]) is not bool
            or type(entry["order"]) is not int
            or not 0 <= entry["order"] <= 2000
        ):
            raise FigureLayoutError("invalid_placement")
        if entry["section"] not in (
            {"common", "answer", "solution"}
            if document["materialKind"] == "solution"
            else {"common"}
        ):
            raise FigureLayoutError("invalid_section")
        part = entry["targetPart"]
        # Allowed labels are supplied by the compiler, including empty parts.
        labels = target.get("partLabels", [])
        if part is not None and part not in labels:
            raise FigureLayoutError("invalid_part")

    def remove(blocks):
        kept = []
        for block in blocks:
            if block.get("occurrenceId") in ids:
                continue
            if "blocks" in block:
                block["blocks"] = remove(block["blocks"])
            if "items" in block:
                block["items"] = [remove(item) for item in block["items"]]
            kept.append(block)
        return kept

    result["introduction"] = remove(result.get("introduction", []))
    for problem in result["problems"]:
        for field in ("preambleBlocks", "blocks", "trailingBlocks"):
            if field in problem:
                problem[field] = remove(problem[field])
    for entry in sorted(
        entries, key=lambda e: (e["order"], e["occurrenceId"]), reverse=True
    ):
        if entry["hidden"]:
            continue
        target = problems[entry["targetOrdinal"]]["blocks"]
        figure = copy.deepcopy(catalog[entry["occurrenceId"]])
        figure["floatHint"] = entry["side"]
        label = {"answer": "Ответ", "solution": "Решение"}.get(entry["section"])
        start = 0
        end = next(
            (i for i, b in enumerate(target) if b.get("type") == "heading"), len(target)
        )
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
                target.extend(
                    [
                        {
                            "type": "heading",
                            "level": 3,
                            "children": [{"type": "text", "value": label}],
                        }
                    ]
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
        if entry["targetPart"] is not None:
            part = next(
                (
                    b
                    for b in target[start:end]
                    if b.get("type") == "subpart" and b["label"] == entry["targetPart"]
                ),
                None,
            )
            if part is None:
                part = {"type": "subpart", "label": entry["targetPart"], "blocks": []}
                target.insert(start, part)
            part["blocks"].insert(0, figure)
        else:
            target.insert(start, figure)
    return result


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
