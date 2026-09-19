from __future__ import annotations

from vmshpwa.scripts.content_picture_bank import decode_tex, extract_references


def test_cp1251_source_comments_and_document_tail_are_ignored() -> None:
    payload = (
        "\\includegraphics{живой}\n"
        "% \\includegraphics{commented}\n"
        "\\end{document}\n"
        "\\includegraphics{dead}\n"
    ).encode("cp1251")
    text, encoding = decode_tex(payload)

    references, dynamic = extract_references(text, "lesson.tex")

    assert encoding == "cp1251"
    assert [reference.logical_name for reference in references] == ["живой"]
    assert dynamic == []


def test_picture_commands_wrappers_variables_and_animation_are_expanded() -> None:
    text = r"""
    \newcommand{\ChessPiece}[3]{\includegraphics{pictures/#1.png}}
    \ChessPiece{KnightWhite}{3}{2}
    \def\tmpPIC{ant}
    \def\tmpPIC{beetle}
    \includegraphics{emoji_\tmpPIC}
    \rightpicture{0}{0}{30mm}{plain}
    \animategraphics[loop]{1}{frames/frame-}{0}{2}
    """

    references, dynamic = extract_references(text, "lesson.tex")
    names = {reference.logical_name for reference in references}

    assert {
        "pictures/KnightWhite.png",
        "emoji_ant",
        "emoji_beetle",
        "plain",
        "frames/frame-0",
        "frames/frame-1",
        "frames/frame-2",
    } <= names
    assert dynamic == []
