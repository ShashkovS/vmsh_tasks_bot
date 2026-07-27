"""Deterministic web and Telegram Rich renderers for the canonical AST."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

from .model import (
    BlockNode,
    CodeNode,
    ContentRole,
    DocumentAst,
    EmphasisNode,
    FigureNode,
    HeadingNode,
    InlineNode,
    LinkNode,
    ListNode,
    MathNode,
    ParagraphNode,
    ProblemNode,
    StrongNode,
    SubpartNode,
    TableNode,
    TextNode,
)
from .telegram import TELEGRAM_BOT_API_DIALECT, sanitize_telegram_rich_html


WEB_RENDERER_VERSION = "vmsh-web-ast-html/1"
TELEGRAM_RENDERER_VERSION = (
    f"vmsh-telegram-rich/1;telegram-bot-api={TELEGRAM_BOT_API_DIALECT}"
)


def is_safe_media_url(value: str) -> bool:
    if not value or any(character in value for character in "\x00\r\n\t"):
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )


def _text(value: str) -> str:
    if value == "\n":
        return "<br/>"
    return html.escape(re.sub(r"[ \t\n\f\v]+", " ", value), quote=False)


def _inline(nodes: Sequence[InlineNode], *, target: str) -> str:
    output: list[str] = []
    for node in nodes:
        if isinstance(node, TextNode):
            output.append(_text(node.text))
        elif isinstance(node, MathNode):
            latex = html.escape(node.latex.strip(), quote=False)
            if target == "web":
                delimiter = ("\\[", "\\]") if node.display else ("\\(", "\\)")
                output.append(f"{delimiter[0]}{latex}{delimiter[1]}")
            elif node.display:
                output.append(f"<tg-math-block>{latex}</tg-math-block>")
            else:
                output.append(f"<tg-math>{latex}</tg-math>")
        elif isinstance(node, StrongNode):
            tag = "strong" if target == "web" else "b"
            output.append(f"<{tag}>{_inline(node.children, target=target)}</{tag}>")
        elif isinstance(node, EmphasisNode):
            tag = "em" if target == "web" else "i"
            output.append(f"<{tag}>{_inline(node.children, target=target)}</{tag}>")
        elif isinstance(node, CodeNode):
            output.append(f"<code>{html.escape(node.text, quote=False)}</code>")
        elif isinstance(node, LinkNode):
            output.append(
                f'<a href="{html.escape(node.href, quote=True)}">'
                f"{_inline(node.children, target=target)}</a>"
            )
    return "".join(output)


def _inline_has_visible_content(nodes: Sequence[InlineNode]) -> bool:
    """Ignore layout-only whitespace left by print header macros.

    The canonical AST intentionally retains source newlines for diagnostics,
    but they must not become a tall run of ``<br>`` before the first heading in
    PWA or Telegram derivatives.  This keeps both renderers aligned with the
    typed web-document projection; see the real-corpus gate in
    ``vmshpwa/docs/testing-strategy.md``.
    """

    for node in nodes:
        if isinstance(node, TextNode):
            if node.text.strip():
                return True
        elif isinstance(node, (StrongNode, EmphasisNode, LinkNode)):
            if _inline_has_visible_content(node.children):
                return True
        else:
            # Math and code remain meaningful even when their source happens
            # to contain leading/trailing whitespace.
            return True
    return False


def _figure(
    node: FigureNode,
    *,
    target: str,
    asset_urls: Mapping[str, str],
) -> str:
    url = asset_urls.get(node.logical_name)
    caption = html.escape(node.alt_text, quote=False)
    if url is None:
        if target == "telegram":
            return f"<aside>Рисунок: {caption}</aside>"
        reference = html.escape(node.logical_name, quote=True)
        return (
            f'<figure data-asset-ref="{reference}">'
            f"<figcaption>{caption}</figcaption></figure>"
        )
    if not is_safe_media_url(url):
        raise ValueError(f"Unsafe media URL for asset {node.logical_name!r}")
    source = html.escape(url, quote=True)
    alt = html.escape(node.alt_text, quote=True)
    if target == "telegram":
        return f'<figure><img src="{source}" alt="{alt}"/><figcaption>{caption}</figcaption></figure>'
    attributes = [f'src="{source}"', f'alt="{alt}"', 'loading="lazy"']
    if node.width_hint:
        attributes.append(
            f'data-width-hint="{html.escape(node.width_hint, quote=True)}"'
        )
    if node.float_hint:
        attributes.append(
            f'data-float-hint="{html.escape(node.float_hint, quote=True)}"'
        )
    return f"<figure><img {' '.join(attributes)}/><figcaption>{caption}</figcaption></figure>"


def _blocks(
    nodes: Sequence[BlockNode],
    *,
    target: str,
    asset_urls: Mapping[str, str],
) -> str:
    output: list[str] = []
    for node in nodes:
        if isinstance(node, ParagraphNode):
            if not _inline_has_visible_content(node.children):
                continue
            if target == "telegram":
                buffered: list[InlineNode] = []
                for child in node.children:
                    if isinstance(child, MathNode) and child.display:
                        if _inline_has_visible_content(buffered):
                            output.append(f"<p>{_inline(buffered, target=target)}</p>")
                        buffered = []
                        output.append(_inline((child,), target=target))
                    else:
                        buffered.append(child)
                if _inline_has_visible_content(buffered):
                    output.append(f"<p>{_inline(buffered, target=target)}</p>")
            else:
                output.append(f"<p>{_inline(node.children, target=target)}</p>")
        elif isinstance(node, HeadingNode):
            level = max(1, min(node.level, 6))
            output.append(
                f"<h{level}>{_inline(node.children, target=target)}</h{level}>"
            )
        elif isinstance(node, ListNode):
            tag = "ol" if node.ordered else "ul"
            items = "".join(
                f"<li>{_blocks(item.children, target=target, asset_urls=asset_urls)}</li>"
                for item in node.items
            )
            output.append(f"<{tag}>{items}</{tag}>")
        elif isinstance(node, TableNode):
            rows = "".join(
                "<tr>"
                + "".join(
                    f"<td>{_inline(cell.children, target=target)}</td>"
                    for cell in row.cells
                )
                + "</tr>"
                for row in node.rows
            )
            output.append(f"<table>{rows}</table>")
        elif isinstance(node, FigureNode):
            output.append(_figure(node, target=target, asset_urls=asset_urls))
        elif isinstance(node, SubpartNode):
            label = html.escape(node.label, quote=False)
            if target == "web":
                output.append(
                    f'<section data-subpart="{html.escape(node.label, quote=True)}">'
                    f"<strong>{label})</strong>"
                    f"{_blocks(node.children, target=target, asset_urls=asset_urls)}</section>"
                )
            else:
                output.append(
                    f"<p><b>{label})</b></p>"
                    f"{_blocks(node.children, target=target, asset_urls=asset_urls)}"
                )
    return "".join(output)


def _selected_problem_parts(
    problem: ProblemNode, role: ContentRole
) -> tuple[tuple[str, tuple[BlockNode, ...]], ...]:
    if role is ContentRole.CONDITION:
        return (("statement", problem.statement + problem.trailing),)
    if role is ContentRole.HINT:
        return (("hint", problem.hint),)
    if role is ContentRole.SOLUTION:
        return (
            ("statement", problem.statement + problem.trailing),
            ("answer", problem.answer),
            ("solution", problem.solution),
        )
    return (
        ("statement", problem.statement + problem.trailing),
        ("hint", problem.hint),
        ("answer", problem.answer),
        ("solution", problem.solution),
    )


def _problem(
    problem: ProblemNode,
    *,
    role: ContentRole,
    target: str,
    asset_urls: Mapping[str, str],
) -> str:
    title = f"Задача {problem.ordinal}"
    if problem.source_title:
        title = f"{title}. {problem.source_title}"
    heading = html.escape(title, quote=False)
    parts: list[str] = []
    labels = {"answer": "Ответ", "hint": "Подсказка", "solution": "Решение"}
    for kind, nodes in _selected_problem_parts(problem, role):
        if not nodes:
            continue
        rendered = _blocks(nodes, target=target, asset_urls=asset_urls)
        if kind == "statement":
            parts.append(rendered)
        elif target == "web":
            parts.append(
                f'<section data-content-kind="{kind}"><h4>{labels[kind]}</h4>{rendered}</section>'
            )
        else:
            parts.append(f"<h4>{labels[kind]}</h4>{rendered}")
    if target == "web":
        return (
            f'<section data-problem-ordinal="{problem.ordinal}">'
            f"<h3>{heading}</h3>{''.join(parts)}</section>"
        )
    return f"<h3>{heading}</h3>{''.join(parts)}"


def render_web_html(
    document: DocumentAst,
    *,
    role: ContentRole,
    asset_urls: Mapping[str, str] | None = None,
) -> str:
    urls = asset_urls or {}
    return (
        '<article data-content-source="latex">'
        + _blocks(document.introduction, target="web", asset_urls=urls)
        + "".join(
            _problem(problem, role=role, target="web", asset_urls=urls)
            for problem in document.problems
        )
        + "</article>"
    )


def render_telegram_rich_html(
    document: DocumentAst,
    *,
    role: ContentRole,
    asset_urls: Mapping[str, str] | None = None,
) -> str:
    urls = asset_urls or {}
    generated = _blocks(document.introduction, target="telegram", asset_urls=urls)
    generated += "".join(
        _problem(problem, role=role, target="telegram", asset_urls=urls)
        for problem in document.problems
    )
    return sanitize_telegram_rich_html(generated)
