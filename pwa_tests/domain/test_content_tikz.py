from __future__ import annotations

from pathlib import Path

import pytest

from helpers.pwa.content import (
    AssetConversionError,
    ContentRole,
    compile_latex,
    prepare_tikz_standalone_document,
    scan_tikz_sources,
)
from helpers.pwa.content.model import FigureNode
from models.pwa.content_asset_names import tikz_source_sha256
from vmshpwa.scripts.content_tikz_corpus import build_report


def _document(body: str) -> bytes:
    return ("\\begin{document}\n" + body + "\n\\end{document}\n").encode()


def test_tikz_scan_attaches_explicit_scoped_and_dependency_context() -> None:
    source = r"""
% addToTikz
\definecolor{global}{rgb}{1,0,0}
% addToTikz
\usetikzlibrary{positioning}
\newcommand{\unused}{99}
\newcommand{\side}{2}
Text between the declaration and its use.
\tikzset{edge/.style={very thick}}
\begin{tikzpicture}\draw[edge,global] (0,0)--(\side,0);\end{tikzpicture}
"""

    scan = scan_tikz_sources(source)

    assert not scan.issues
    assert len(scan.sources) == 1
    tikz = scan.sources[0]
    assert "\\definecolor{global}" in tikz.source
    assert "\\usetikzlibrary{positioning}" in tikz.source
    assert "\\newcommand{\\side}{2}" in tikz.source
    assert "\\tikzset{edge/.style" in tikz.source
    assert "\\unused" not in tikz.source
    assert set(tikz.context_kinds) >= {
        "addToTikz",
        "usetikzlibrary",
        "newcommand",
        "tikzset",
    }


def test_tikz_scan_supports_braced_and_semicolon_inline_forms() -> None:
    scan = scan_tikz_sources(
        r"\tikz[scale=.5]{\draw (0,0)--(1,1);} "
        r"\tikz\node at (0,0){A; B};"
    )

    assert not scan.issues
    assert [source.kind for source in scan.sources] == ["inline", "inline"]
    assert "[scale=.5]" in scan.sources[0].source
    assert "{A; B};\\end{tikzpicture}" in scan.sources[1].source


def test_tikz_scan_supplies_legacy_part_label_used_by_real_lessons() -> None:
    scan = scan_tikz_sources(
        r"""
\begin{tikzpicture}
  \draw (0, 0) node {\пункт};
\end{tikzpicture}
"""
    )

    assert not scan.issues
    assert len(scan.sources) == 1
    source = scan.sources[0]
    assert r"\newcommand{\vmshPartLabel}" in source.source
    assert r"\пункт" not in source.source
    assert r"\vmshPartLabel" in source.source
    assert r"\alph{vmshpart})" in source.source


def test_tikz_scan_excludes_comment_environment_and_groups_layout_wrapper() -> None:
    scan = scan_tikz_sources(
        r"""
\begin{comment}
\begin{tikzpicture}\draw (0,0)--(9,9);\end{tikzpicture}
\end{comment}
\righttikzw{0mm}{0mm}{4cm}{
\begin{tikzpicture}\draw (0,0)--(1,0);\end{tikzpicture}
\begin{tikzpicture}\draw (0,0)--(0,1);\end{tikzpicture}}
"""
    )

    assert not scan.issues
    assert len(scan.sources) == 1
    assert scan.sources[0].kind == "wrapper"
    assert scan.sources[0].source.count(r"\begin{tikzpicture}") == 2


def test_production_parser_hashes_effective_tikz_context() -> None:
    result = compile_latex(
        _document(
            r"""
\newcommand{\side}{2}
\задача
\begin{tikzpicture}\draw (0,0)--(\side,0);\end{tikzpicture}
\кзадача
"""
        ),
        source_name="usl-01-n.tex",
        role=ContentRole.CONDITION,
    )

    figure = next(
        node
        for node in result.ast.problems[0].statement
        if isinstance(node, FigureNode)
    )
    assert figure.tikz_source is not None
    assert figure.tikz_source.startswith(r"\newcommand{\side}{2}")
    assert figure.logical_name == f"tikz-{figure.content_sha256[:16]}"

    changed = figure.tikz_source.replace(r"\side}{2}", r"\side}{3}")
    assert tikz_source_sha256(changed) != tikz_source_sha256(figure.tikz_source)


def test_parser_flattens_tikz_nested_in_resizebox_table_cells() -> None:
    result = compile_latex(
        _document(
            r"""
\задача
\begin{tabular}{cc}
\resizebox{2cm}{!}{\begin{tikzpicture}\draw(0,0)--(1,0);\end{tikzpicture}}
&
\resizebox{2cm}{!}{\begin{tikzpicture}\draw(0,0)--(0,1);\end{tikzpicture}}
\end{tabular}
\кзадача
"""
        ),
        source_name="usl-01-n.tex",
        role=ContentRole.CONDITION,
    )

    figures = [
        node
        for node in result.ast.problems[0].statement
        if isinstance(node, FigureNode)
    ]
    assert len(figures) == 2
    assert not result.has_errors


def test_parser_recovers_tikz_from_unclosed_print_center() -> None:
    result = compile_latex(
        _document(
            r"""
\задача
\begin{center}
\begin{tikzpicture}\draw(0,0)--(1,0);\end{tikzpicture}
\кзадача
"""
        ),
        source_name="usl-01-n.tex",
        role=ContentRole.CONDITION,
    )

    assert any(
        isinstance(node, FigureNode) for node in result.ast.problems[0].statement
    )
    assert not result.has_errors


def test_standalone_preparation_is_pure_and_keeps_security_boundary() -> None:
    document = prepare_tikz_standalone_document(
        r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
    )
    assert document.startswith(r"\documentclass")
    assert r"\usepackage[utf8]{inputenc}" in document
    assert r"\usepackage[russian,english]{babel}" in document
    assert document.endswith("\\end{document}\n")

    with pytest.raises(AssetConversionError) as captured:
        prepare_tikz_standalone_document(
            r"\begin{tikzpicture}\csname input\endcsname secret\end{tikzpicture}"
        )
    assert captured.value.code == "asset.tikz_forbidden_command"


def test_corpus_report_uses_exact_masks_and_excludes_commented_tikz(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    bank = tmp_path / "pictures"
    archive.mkdir()
    bank.mkdir()
    (bank / "piece.png").write_bytes(b"not decoded during static scan")
    (archive / "usl-01-n.tex").write_bytes(
        _document(
            r"""
% \begin{tikzpicture}\draw (0,0)--(9,9);\end{tikzpicture}
\задача
\begin{tikzpicture}\node {\includegraphics{piece}};\end{tikzpicture}
\кзадача
"""
        )
    )
    (archive / "ignored.tex").write_bytes(
        _document(
            r"\задача \begin{tikzpicture}\draw(0,0)--(1,1);\end{tikzpicture}\кзадача"
        )
    )

    report = build_report((archive,), bank=bank)

    assert report["scope"]["sourceCount"] == 1
    assert report["summary"]["rawTikzEnvironmentCount"] == 2
    assert report["summary"]["activeTikzCount"] == 1
    assert report["summary"]["commentedTikzEnvironmentCount"] == 1
    assert report["summary"]["inactiveTikzEnvironmentCount"] == 0
    assert report["summary"]["parserUnrepresentedTikzCount"] == 0
    assert report["summary"]["matchedExternalReferenceCount"] == 1
    assert report["summary"]["missingExternalReferenceCount"] == 0
