"""Native vector chess context; vmshpwa/docs/tikz-chess.md."""

from helpers.pwa.content.tikz import scan_tikz_sources


def test_all_twelve_pieces_are_native_tikz_paths():
    source = (
        scan_tikz_sources(
            r"\begin{tikzpicture}\ChessPiece{RookWhite}{1}{2}\end{tikzpicture}"
        )
        .sources[0]
        .source
    )
    for piece in ["King", "Queen", "Rook", "Bishop", "Knight", "Pawn"]:
        for color in ["White", "Black"]:
            assert f"vmsh chess {piece}{color}/.pic=" in source
    assert r"\path[fill=white" in source
    assert r"\path[fill=black" in source
    assert "x=9mm,y=9mm" in source
    assert r"\includegraphics" not in source
    assert r"\input" not in source
    assert ".png" not in source
    assert len(source) < 250_000


def test_explicit_author_piece_definition_is_preserved():
    text = r"\newcommand{\ChessPiece}[3]{\draw (#2,#3) circle (0.1);}\begin{tikzpicture}\ChessPiece{RookWhite}{1}{1}\end{tikzpicture}"
    source = scan_tikz_sources(text).sources[0].source
    assert "vmsh chess RookWhite" not in source
    assert r"\draw (#2,#3)" in source


def test_legacy_chess_graphics_are_replaced_selectively():
    raw = r"""\begin{tikzpicture}
% \includegraphics{QueenWhite}
\node {\includegraphics[width=10mm]{QueenWhite}};
\node {\includegraphics[height=8mm]{pictures/BishopWhite.png}};
\node {\includegraphics{other.png}};
\end{tikzpicture}"""
    source = scan_tikz_sources(raw).sources[0].source
    assert r"\vmshChessGraphic[width=10mm]{QueenWhite}" in source
    assert r"\vmshChessGraphic[height=8mm]{BishopWhite}" in source
    assert r"\includegraphics{other.png}" in source
    assert r"% \includegraphics{QueenWhite}" in source
    assert "vmsh chess QueenWhite/.pic=" in source


def test_mixed_chess_commands_share_one_vector_definition():
    raw = r"\begin{tikzpicture}\ChessPiece{RookWhite}{1}{1}\node {\includegraphics{QueenWhite}};\end{tikzpicture}"
    source = scan_tikz_sources(raw).sources[0].source
    assert source.count("vmsh chess QueenWhite/.pic=") == 1
    assert r"\newcommand{\ChessPiece}" in source
    assert r"\vmshChessGraphic{QueenWhite}" in source
