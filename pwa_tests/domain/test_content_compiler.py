from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

import pytest

from helpers.pwa.content import (
    ContentCompileError,
    ContentRole,
    DiagnosticSeverity,
    ParserLimits,
    SourceEncoding,
    WebAssetDescriptor,
    compile_latex,
    render_web_document,
)
from helpers.pwa.content.model import FigureNode, ListNode, SubpartNode, TableNode


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_MANIFEST = REPOSITORY_ROOT / "vmshpwa/fixtures/content/golden-manifest.json"
PYTHON_COMPILER_FIXTURE = (
    REPOSITORY_ROOT
    / "vmshpwa/packages/contracts/fixtures/content/python-compiler-preview.v1.json"
)


def _document(body: str) -> bytes:
    return ("\\begin{document}\n" + body + "\n\\end{document}\n").encode("utf-8")


def _compile(body: str, *, role: ContentRole = ContentRole.CONDITION, **kwargs):
    return compile_latex(
        _document(body), source_name="fixtures/lesson.tex", role=role, **kwargs
    )


def _codes(result) -> set[str]:
    return {diagnostic.code for diagnostic in result.diagnostics}


def _published_asset(
    *,
    asset_id: str,
    content_sha256: str,
    media_type: str,
    src: str | None = None,
) -> WebAssetDescriptor:
    return WebAssetDescriptor(
        asset_id=asset_id,
        content_sha256=content_sha256,
        src=src or f"https://assets.example.test/content/{asset_id}",
        media_type=media_type,
        width=800,
        height=600,
    )


@pytest.mark.parametrize(
    ("payload", "encoding"),
    [
        (_document("\\задача UTF-8 \\кзадача"), SourceEncoding.UTF8),
        (
            b"\xef\xbb\xbf" + _document("\\задача BOM \\кзадача"),
            SourceEncoding.UTF8_BOM,
        ),
        (
            (
                "\\begin{document}\r\n\\задача Привет \\кзадача\r\n\\end{document}\r\n"
            ).encode("windows-1251"),
            SourceEncoding.WINDOWS_1251,
        ),
    ],
)
def test_decoding_keeps_raw_hash_and_explicit_encoding(
    payload: bytes, encoding
) -> None:
    result = compile_latex(
        payload,
        source_name="fixtures/encoding.tex",
        role=ContentRole.CONDITION,
    )

    assert result.source.encoding is encoding
    assert result.source.raw_sha256 == hashlib.sha256(payload).hexdigest()
    assert "\r" not in result.source.text
    assert len(result.ast.problems) == 1


def test_diagnostic_has_exact_unicode_line_and_column() -> None:
    result = _compile("Введение\n\\задача\nабв \\неизвестно{x}\n\\кзадача")

    diagnostic = next(
        item for item in result.diagnostics if item.code == "latex.unknown_macro"
    )
    assert diagnostic.span.source_name == "fixtures/lesson.tex"
    assert (diagnostic.span.start.line, diagnostic.span.start.column) == (4, 5)
    assert diagnostic.span.end.offset > diagnostic.span.start.offset


def test_comments_nested_groups_math_and_semantic_fields_are_not_confused() -> None:
    result = _compile(
        r"""
% \задача Эта задача закомментирована \кзадача
\задача[title=Скобки]
Текст {со {вложенной} группой}, \% и $\{x: x \in A\}$.
\кзадача
\ответ 42 \кответ
\подсказка Ищите инвариант. \кподсказка
\решение Готово. \крешение
""",
        role=ContentRole.CONDITION,
    )

    assert len(result.ast.problems) == 1
    problem = result.ast.problems[0]
    assert problem.source_title == "Скобки"
    assert problem.answer and problem.hint and problem.solution
    assert "42" not in result.web.content
    assert "Ищите" not in result.web.content
    assert "Готово" not in result.telegram.content
    assert "$" not in result.telegram.content
    assert "<tg-math>" in result.telegram.content


def test_each_material_role_projects_only_its_approved_branch() -> None:
    body = (
        "\\задача УСЛОВИЕ \\кзадача\n"
        "\\ответ ОТВЕТ \\кответ\n"
        "\\подсказка ПОДСКАЗКА \\кподсказка\n"
        "\\решение РЕШЕНИЕ \\крешение"
    )

    condition = _compile(body, role=ContentRole.CONDITION)
    hint = _compile(body, role=ContentRole.HINT)
    solution = _compile(body, role=ContentRole.SOLUTION)

    assert "УСЛОВИЕ" in condition.web.content
    assert not any(
        word in condition.web.content for word in ("ОТВЕТ", "ПОДСКАЗКА", "РЕШЕНИЕ")
    )
    assert "ПОДСКАЗКА" in hint.web.content
    assert not any(word in hint.web.content for word in ("УСЛОВИЕ", "ОТВЕТ", "РЕШЕНИЕ"))
    assert all(word in solution.web.content for word in ("УСЛОВИЕ", "ОТВЕТ", "РЕШЕНИЕ"))
    assert "ПОДСКАЗКА" not in solution.web.content
    assert condition.web_document is not None
    document = json.loads(condition.web_document.content)
    assert document["materialKind"] == "condition"
    assert set(document["problems"][0]) == {"ordinal", "sourceItem", "title", "blocks"}
    assert "answer" not in condition.web_document.content
    assert "solution" not in condition.web_document.content


def test_print_header_whitespace_does_not_create_empty_web_or_telegram_paragraphs() -> (
    None
):
    result = _compile(
        """
\\Заголовок{Математический кружок}
\\НомерЛистка{41н}
\\ДатаЛистка{03.08.2026}
\\СоздатьЗаголовок

\\раздел{Тест-задачи}
\\задача Условие. \\кзадача
"""
    )

    assert "<p><br" not in result.web.content
    assert not result.telegram.content.startswith("<p><br")
    assert result.telegram.content.startswith("<h2>Тест-задачи</h2>")


def test_lists_tables_subparts_assets_and_tikz_have_typed_nodes() -> None:
    known_hash = "a" * 64
    tikz_source = r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
    tikz_hash = hashlib.sha256(tikz_source.encode()).hexdigest()
    result = _compile(
        r"""
\задача
\пункт Первый подпункт.
\begin{itemize}\item Один.\item Два.\end{itemize}
\begin{tabular}{cc}a&b\\c&d\end{tabular}
\includegraphics[width=4cm]{figures/schema.svg}
\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}
\кзадача
""",
        known_assets={
            "figures/schema.svg": _published_asset(
                asset_id="asset:schema",
                content_sha256=known_hash,
                media_type="image/svg+xml",
            ),
            f"tikz-{tikz_hash[:16]}": _published_asset(
                asset_id="asset:tikz",
                content_sha256="b" * 64,
                media_type="image/svg+xml",
            ),
        },
    )

    blocks = result.ast.problems[0].statement

    def nested(block):
        yield block
        if isinstance(block, SubpartNode):
            for child in block.children:
                yield from nested(child)

    all_blocks = [child for block in blocks for child in nested(block)]
    assert any(isinstance(block, SubpartNode) for block in blocks)
    assert any(isinstance(block, ListNode) for block in all_blocks)
    assert any(isinstance(block, TableNode) for block in all_blocks)
    figures = [block for block in all_blocks if isinstance(block, FigureNode)]
    assert len(figures) == 2
    assert figures[0].content_sha256 == known_hash
    assert figures[1].tikz_source is not None
    assert "\\draw" in figures[1].tikz_source


@pytest.mark.parametrize(
    ("body", "logical_name", "descriptor"),
    [
        (
            r"\задача \includegraphics{photos/page.heic} \кзадача",
            "photos/page.heic",
            _published_asset(
                asset_id="asset:raster",
                content_sha256="1" * 64,
                media_type="image/webp",
            ),
        ),
        (
            r"\задача \includegraphics{figures/geometry.svg} \кзадача",
            "figures/geometry.svg",
            _published_asset(
                asset_id="asset:svg",
                content_sha256="2" * 64,
                media_type="image/svg+xml",
            ),
        ),
        (
            (
                r"\задача \begin{tikzpicture}\draw (0,0)--(1,1);"
                r"\end{tikzpicture} \кзадача"
            ),
            "tikz-1435a39e5123382b",
            _published_asset(
                asset_id="asset:tikz-svg",
                content_sha256="3" * 64,
                media_type="image/svg+xml",
            ),
        ),
    ],
)
def test_compile_uses_one_published_asset_descriptor_in_every_derivative(
    body: str,
    logical_name: str,
    descriptor: WebAssetDescriptor,
) -> None:
    result = _compile(
        body,
        known_assets={logical_name: descriptor},
        revision_id="revision:assets",
    )

    assert "asset.missing" not in _codes(result)
    assert result.web_document is not None
    document = json.loads(result.web_document.content)
    figure = document["problems"][0]["blocks"][0]
    assert figure["asset"] == {
        "status": "available",
        "assetId": descriptor.asset_id,
        "contentSha256": descriptor.content_sha256,
        "src": descriptor.src,
        "mediaType": descriptor.media_type,
        "width": descriptor.width,
        "height": descriptor.height,
    }
    assert descriptor.src in result.web.content
    assert descriptor.src in result.telegram.content


def test_root_relative_local_asset_is_shared_by_web_and_telegram_previews() -> None:
    descriptor = _published_asset(
        asset_id="asset:local-preview",
        content_sha256="d" * 64,
        media_type="image/svg+xml",
        src="/pwa-content-assets/asset:local-preview",
    )
    result = _compile(
        r"\задача \includegraphics{figure.svg} \кзадача",
        known_assets={"figure.svg": descriptor},
    )

    assert "asset.url_unsafe" not in _codes(result)
    assert "telegram.derivative_invalid" not in _codes(result)
    assert descriptor.src in result.web.content
    assert descriptor.src in result.telegram.content


def test_published_descriptor_wins_over_conflicting_legacy_url_for_all_renderers() -> (
    None
):
    descriptor = _published_asset(
        asset_id="asset:single-source",
        content_sha256="4" * 64,
        media_type="image/svg+xml",
        src="https://assets.example.test/canonical.svg",
    )
    result = _compile(
        r"\задача \includegraphics{figure.svg} \кзадача",
        known_assets={"figure.svg": descriptor},
        asset_urls={"figure.svg": "https://other.example.test/conflict.svg"},
    )

    assert "asset.url_conflict" in _codes(result)
    assert descriptor.src in result.web.content
    assert descriptor.src in result.telegram.content
    assert "other.example.test" not in result.web.content
    assert "other.example.test" not in result.telegram.content


@pytest.mark.parametrize(
    ("body", "logical_name"),
    [
        (
            r"\задача \includegraphics{missing.svg} \кзадача",
            "missing.svg",
        ),
        (
            (
                r"\задача \begin{tikzpicture}\draw (0,0)--(1,1);"
                r"\end{tikzpicture} \кзадача"
            ),
            "tikz-1435a39e5123382b",
        ),
    ],
)
def test_missing_asset_remains_an_explicit_diagnostic_and_wire_state(
    body: str, logical_name: str
) -> None:
    result = _compile(
        body,
        known_assets={},
    )

    assert "asset.missing" in _codes(result)
    assert result.web_document is not None
    document = json.loads(result.web_document.content)
    figure = document["problems"][0]["blocks"][0]
    assert figure["asset"] == {"status": "missing", "logicalName": logical_name}
    assert "<img" not in result.web.content
    assert "<img" not in result.telegram.content


@pytest.mark.parametrize(
    "descriptor",
    [
        {
            "asset_id": "asset:raw-dict",
            "content_sha256": "5" * 64,
            "src": "file:///private/server/secret.svg?token=do-not-leak",
            "media_type": "image/svg+xml",
            "width": 10,
            "height": 10,
            "data": "do-not-leak",
        },
        WebAssetDescriptor(
            asset_id="asset:unsafe-url",
            content_sha256="5" * 64,
            src="file:///private/server/secret.svg?token=do-not-leak",
            media_type="image/svg+xml",
            width=10,
            height=10,
        ),
        WebAssetDescriptor(
            asset_id="asset:bad-dimension",
            content_sha256="5" * 64,
            src="https://assets.example.test/figure.svg",
            media_type="image/svg+xml",
            width=True,
            height=10,
        ),
    ],
)
def test_compile_rejects_untrusted_asset_descriptors_without_leaking_values(
    descriptor: object,
) -> None:
    with pytest.raises(ContentCompileError) as captured:
        _compile(
            r"\задача \includegraphics{figure.svg} \кзадача",
            known_assets={"figure.svg": descriptor},  # type: ignore[dict-item]
        )

    message = str(captured.value)
    assert "/private/server" not in message
    assert "do-not-leak" not in message


def test_missing_invalid_assets_and_unsafe_derivative_url_are_diagnostics() -> None:
    missing = _compile(
        r"\задача \includegraphics{missing.svg} \кзадача",
        known_assets={},
        asset_urls={"missing.svg": "file:///etc/passwd"},
    )
    invalid = _compile(r"\задача \includegraphics{../secret.svg} \кзадача")

    assert {"asset.missing", "asset.url_unsafe"} <= _codes(missing)
    assert "asset.reference_invalid" in _codes(invalid)
    assert "file:" not in missing.web.content
    assert "file:" not in missing.telegram.content


@pytest.mark.parametrize(
    "command", ["input", "write", "openout", "directlua", "catcode"]
)
def test_tex_io_and_dynamic_commands_are_never_executed(command: str) -> None:
    result = _compile(
        rf"\задача \begin{{tikzpicture}}\{command}{{secret}}\end{{tikzpicture}} \кзадача"
    )

    assert "latex.command_forbidden" in _codes(result)
    assert result.has_errors


def test_unknown_macro_and_environment_are_explicit_errors() -> None:
    macro = _compile(r"\задача x \ownerMagic{y} \кзадача")
    environment = _compile(r"\задача \begin{ownerbox}x\end{ownerbox} \кзадача")

    assert "latex.unknown_macro" in _codes(macro)
    assert "latex.environment_unsupported" in _codes(environment)


def test_compilation_and_all_derivative_hashes_are_deterministic() -> None:
    payload = _document(r"\задача Текст $x^2$. \кзадача")
    first = compile_latex(
        payload,
        source_name="fixtures/deterministic.tex",
        role=ContentRole.CONDITION,
        revision_id="revision:test-v1",
        title="Занятие",
    )
    second = compile_latex(
        payload,
        source_name="fixtures/deterministic.tex",
        role=ContentRole.CONDITION,
        revision_id="revision:test-v1",
        title="Занятие",
    )

    assert first.ast_sha256 == second.ast_sha256
    assert first.web == second.web
    assert first.web_document == second.web_document
    assert first.telegram == second.telegram
    assert first.web_document is not None
    assert json.loads(first.web_document.content)["revisionId"] == "revision:test-v1"


@pytest.mark.parametrize(
    "source_name",
    [
        "",
        "/absolute.tex",
        "../escape.tex",
        "a/../escape.tex",
        "a//b.tex",
        "a/./b.tex",
        "a/b.tex/",
        "a\\b.tex",
        "a\x00b.tex",
        "a\nfile.tex",
        "Ａ.tex",
        "x" * 241,
    ],
)
def test_source_name_must_be_canonical_bounded_relative_path(source_name: str) -> None:
    with pytest.raises(ContentCompileError):
        compile_latex(
            _document(r"\задача x \кзадача"),
            source_name=source_name,
            role=ContentRole.CONDITION,
        )


def test_source_size_group_node_and_tikz_limits_fail_closed() -> None:
    with pytest.raises(ContentCompileError):
        compile_latex(
            b"x" * 9,
            source_name="x.tex",
            role=ContentRole.CONDITION,
            limits=ParserLimits(max_source_bytes=8),
        )

    group = _compile(
        r"\задача {{{deep}}} \кзадача",
        limits=ParserLimits(max_group_depth=2),
    )
    nodes = _compile(
        r"\задача one two \кзадача",
        limits=ParserLimits(max_nodes=1),
    )
    tikz = _compile(
        r"\задача \begin{tikzpicture}123456\end{tikzpicture} \кзадача",
        limits=ParserLimits(max_tikz_chars=5),
    )

    assert "latex.group_unclosed" in _codes(group)
    assert "latex.node_limit" in _codes(nodes)
    assert "tikz.size_limit" in _codes(tikz)


def test_seeded_fuzz_like_fragments_are_deterministic_and_bounded() -> None:
    randomizer = random.Random(179)
    atoms = [
        "текст ",
        "$x+1$ ",
        "{вложение} ",
        "% комментарий с \\задача\n",
        "\\textbf{важно} ",
        "\\% ",
        "$$a^2+b^2$$ ",
    ]
    for index in range(100):
        body = "".join(randomizer.choice(atoms) for _ in range(30))
        payload = _document(f"\\задача {body} \\кзадача")
        first = compile_latex(
            payload,
            source_name=f"fuzz/case-{index}.tex",
            role=ContentRole.CONDITION,
        )
        second = compile_latex(
            payload,
            source_name=f"fuzz/case-{index}.tex",
            role=ContentRole.CONDITION,
        )
        assert first.ast_sha256 == second.ast_sha256
        assert first.web_document == second.web_document


def test_web_document_available_asset_requires_explicit_published_metadata() -> None:
    result = _compile(r"\задача \includegraphics{figure.svg} \кзадача")
    document = render_web_document(
        result.ast,
        role=ContentRole.CONDITION,
        revision_id="revision:1",
        assets={
            "figure.svg": WebAssetDescriptor(
                asset_id="asset:1",
                content_sha256="b" * 64,
                src="/student/api/v1/content/assets/asset:1",
                media_type="image/svg+xml",
                width=800,
                height=600,
            )
        },
    )

    figure = document["problems"][0]["blocks"][0]
    assert figure["asset"] == {
        "status": "available",
        "assetId": "asset:1",
        "contentSha256": "b" * 64,
        "src": "/student/api/v1/content/assets/asset:1",
        "mediaType": "image/svg+xml",
        "width": 800,
        "height": 600,
    }


def test_web_document_rejects_oversized_table_instead_of_truncating_content() -> None:
    cells = "&".join(str(index) for index in range(21))
    result = _compile(
        rf"\задача \begin{{tabular}}{{*{{21}}{{c}}}}{cells}\end{{tabular}} \кзадача"
    )

    assert result.web_document is None
    assert "web.derivative_invalid" in _codes(result)
    diagnostic = next(
        item for item in result.diagnostics if item.code == "web.derivative_invalid"
    )
    assert "20 columns" in diagnostic.message


def test_python_compiler_preview_matches_shared_zod_fixture_without_secret_branches() -> (
    None
):
    payload = r"""\begin{document}
Введение с $n$.
\задача[name=demo.1,title=Синтетическая задача]
Текст \textbf{жирный и \emph{выделенный}}; \href{https://example.test/material}{ссылка}.
$$x^2+y^2=z^2$$
\пункт Подпункт.
\begin{itemize}\item Первый.\item Второй.\end{itemize}
\begin{tabular}{cc}a&b\\c&d\end{tabular}
\includegraphics{figures/missing.svg}
\кзадача
\подсказка СЕКРЕТНАЯ ПОДСКАЗКА \кподсказка
\решение СЕКРЕТНОЕ РЕШЕНИЕ \крешение
\end{document}
""".encode()
    result = compile_latex(
        payload,
        source_name="synthetic/python-compiler-preview.tex",
        role=ContentRole.CONDITION,
    )
    fixture = json.loads(PYTHON_COMPILER_FIXTURE.read_text(encoding="utf-8"))

    assert result.web_document is not None
    assert json.loads(result.web_document.content) == fixture["document"]
    assert all(
        forbidden not in result.web_document.content
        for forbidden in ('"answer"', '"hint"', '"solution"')
    )


def test_all_golden_tex_sources_compile_without_content_copies() -> None:
    manifest = json.loads(GOLDEN_MANIFEST.read_text(encoding="utf-8"))
    counters: Counter[str] = Counter()
    diagnostics: Counter[str] = Counter()
    for entry in manifest["entries"]:
        if entry["format"] != "tex":
            continue
        payload = (REPOSITORY_ROOT / entry["path"]).read_bytes()
        result = compile_latex(
            payload,
            source_name=entry["path"],
            role=ContentRole(entry["role"]),
        )
        assert result.source.raw_sha256 == entry["sha256"]
        assert result.source.encoding.value == entry["encoding"]
        assert result.web_document is not None
        counters["files"] += 1
        counters["problems"] += len(result.ast.problems)
        for diagnostic in result.diagnostics:
            diagnostics[f"{diagnostic.severity.value}:{diagnostic.code}"] += 1

    assert counters == {"files": 30, "problems": 334}
    assert diagnostics == {"warning:latex.layout_crosses_semantic_boundary": 1}
    assert not any(
        key.startswith(f"{DiagnosticSeverity.ERROR.value}:") for key in diagnostics
    )
