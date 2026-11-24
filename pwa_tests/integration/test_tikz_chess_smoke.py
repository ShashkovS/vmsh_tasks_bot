"""Real pdfLaTeX → pdf2svg, including all twelve native vector pieces."""

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from helpers.pwa.content.assets import ContentAssetConverter, ContentAssetTools
from helpers.pwa.content.tikz import scan_tikz_sources


@pytest.mark.parametrize(
    "board",
    [
        r"\fill[brown] (0,0) rectangle (5,2);\fill[yellow] (1,2) rectangle (3,3);\node at (1.5,2.5) {\includegraphics[width=10mm]{QueenWhite}};\node at (0.5,0.5) {\includegraphics[width=10mm]{QueenWhite}};\node at (3.5,1.5) {\includegraphics[width=10mm]{BishopWhite}};\node at (4.5,1.5) {\includegraphics[width=10mm]{KnightWhite}};",
        r"\node {\includegraphics[width=10mm,height=6mm,keepaspectratio,scale=0.8,angle=15]{pictures/QueenWhite.png}};",
        r"\ChessBoard{6}{6}\foreach \x/\y in {1/6,2/6,1/5,3/5,2/4,3/4}{\ChessPiece{RookWhite}{\x}{\y}}",
        r"\ChessBoard{6}{2}\foreach \piece [count=\x] in {King,Queen,Rook,Bishop,Knight,Pawn}{\ChessPiece{\piece White}{\x}{1}\ChessPiece{\piece Black}{\x}{2}}",
    ],
)
async def test_real_chess_tikz_is_vector_and_cleans_workspace(tmp_path, board):
    latex = shutil.which("pdflatex") or (
        "/Library/TeX/texbin/pdflatex"
        if Path("/Library/TeX/texbin/pdflatex").exists()
        else None
    )
    svg = shutil.which("pdf2svg")
    if not latex or not svg:
        pytest.skip("pdfLaTeX and pdf2svg required")
    converter = ContentAssetConverter(
        ContentAssetTools(pdflatex=latex, pdf2svg=svg, magick="", cwebp=""),
        temp_root=tmp_path,
    )
    source = (
        scan_tikz_sources(
            r"\begin{tikzpicture}[scale=0.8]" + board + r"\end{tikzpicture}"
        )
        .sources[0]
        .source
    )
    result = await converter.tikz_to_svg(source)
    root = ET.fromstring(result.data)
    assert not root.findall(".//{http://www.w3.org/2000/svg}image")
    assert len(root.findall(".//{http://www.w3.org/2000/svg}path")) >= 2
    assert b"data:image" not in result.data
    assert result.width > 10 and result.height > 10
    assert list(tmp_path.iterdir()) == []


async def test_piece_scales_with_tikz_picture(tmp_path):
    latex = shutil.which("pdflatex") or (
        "/Library/TeX/texbin/pdflatex"
        if Path("/Library/TeX/texbin/pdflatex").exists()
        else None
    )
    svg = shutil.which("pdf2svg")
    if not latex or not svg:
        pytest.skip("pdfLaTeX and pdf2svg required")
    converter = ContentAssetConverter(
        ContentAssetTools(pdflatex=latex, pdf2svg=svg, magick="", cwebp=""),
        temp_root=tmp_path,
    )
    sizes = []
    for scale in [1, 2]:
        raw = (
            r"\begin{tikzpicture}[scale="
            + str(scale)
            + r"]\ChessPiece{KnightWhite}{1}{1}\end{tikzpicture}"
        )
        result = await converter.tikz_to_svg(scan_tikz_sources(raw).sources[0].source)
        sizes.append((result.width, result.height))
    # Standalone adds a fixed 5pt border on each side, independent of scale.
    for small, large in zip(sizes[0], sizes[1], strict=True):
        assert abs(large - (2 * small - 10)) <= 2
