"""Source material presence; docs/hint-preview-empty-materials-20261004.md.

Both the typed compiler AST and immutable stored canonical JSON use these
fields. Statement illustrations alone never constitute a hint or solution.
"""

from collections.abc import Mapping

from .model import ContentRole


def _field(node, name, default=None):
    return node.get(name, default) if isinstance(node, Mapping) else getattr(node, name, default)


def material_blocks(problem, role):
    if role == ContentRole.HINT:
        return tuple(_field(problem, "hint", ()))
    if role == ContentRole.SOLUTION:
        return tuple(_field(problem, "answer", ())) + tuple(_field(problem, "solution", ()))
    return tuple(_field(problem, "statement", ()))


def _has_content(nodes, part=None):
    for node in nodes:
        label = _field(node, "label")
        if part is not None and label is not None and label != part:
            continue
        if _field(node, "kind") in {"asset", "tikz"}:
            return True
        if any(str(_field(node, name, "") or "").strip() for name in ("text", "latex")):
            return True
        for name in ("children", "items", "rows", "cells"):
            if _has_content(_field(node, name, ()), part):
                return True
    return False


def has_material(problem, role, part=None):
    """A common section applies to every part; an empty labelled part does not."""
    return _has_content(material_blocks(problem, role), part)


def _figures(nodes):
    result = []
    for node in nodes:
        if _field(node, "kind") in {"asset", "tikz"}:
            result.append(node)
        else:
            for name in ("children", "items"):
                result.extend(_figures(_field(node, name, ())))
    return result


def selected_material_nodes(document, role):
    """The renderer/inventory share detached condition figures and role selection."""
    introduction = tuple(_field(document, "introduction", ()))
    problems = tuple(_field(document, "problems", ()))
    if role in {ContentRole.CONDITION, ContentRole.FULL_PREVIEW}:
        result = list(introduction)
        for problem in problems:
            for name in ("statement", "trailing", "hint", "answer", "solution"):
                if role == ContentRole.FULL_PREVIEW or name in {"statement", "trailing"}:
                    result.extend(_field(problem, name, ()))
        return tuple(result)
    pending = _figures(introduction)
    result = []
    for index, problem in enumerate(problems):
        illustrations = pending + _figures(_field(problem, "statement", ()))
        pending = _figures(_field(problem, "trailing", ()))
        if index == len(problems) - 1:
            illustrations += pending
        if has_material(problem, role):
            result.extend(illustrations)
            result.extend(material_blocks(problem, role))
    return tuple(result)


def annotate_material_availability(document, canonical, role):
    """Read projection for old derivatives too; never mutate canonical history."""
    if role not in {ContentRole.HINT, ContentRole.SOLUTION} or not isinstance(canonical, dict):
        return document
    source = canonical.get("problems")
    if not isinstance(source, list):
        return document
    by_ordinal = {
        problem.get("ordinal"): problem for problem in source
        if isinstance(problem, dict) and all(name in problem for name in ("hint", "answer", "solution"))
    }
    for problem in document.get("problems", []):
        original = by_ordinal.get(problem.get("ordinal"))
        if original is None:
            continue  # Compatibility with derivatives lacking a compiler AST.
        problem["materialAvailable"] = has_material(original, role)
        labels = problem.get("partLabels") or [
            _field(node, "label") for node in original.get("statement", [])
            if _field(node, "label") is not None
        ]
        if labels:
            problem["materialPartLabels"] = [label for label in labels if has_material(original, role, label)]
    return document


def web_problem_has_material(problem, part=None):
    """Fallback for pre-metadata derivatives, after selecting one source part."""
    if problem.get("materialAvailable") is False:
        return False
    labels = problem.get("materialPartLabels")
    if part is not None and isinstance(labels, list) and part not in labels:
        return False
    from .figure_layout import select_material_part

    blocks = select_material_part(problem, part)["blocks"] if part is not None else problem.get("blocks", [])

    def has_body(nodes):
        for node in nodes:
            if isinstance(node, list):
                if has_body(node):
                    return True
                continue
            kind = node.get("type")
            if kind == "heading":
                continue
            if kind in {"text", "code"}:
                if str(node.get("value", "")).strip():
                    return True
            elif kind == "math":
                if str(node.get("latex", "")).strip():
                    return True
            elif kind == "figure":
                return True
            for field in ("children", "blocks", "rows"):
                if has_body(node.get(field, [])):
                    return True
            for item in node.get("items", []) + node.get("cells", []):
                if has_body(item):
                    return True
        return False

    return has_body(blocks)
