from __future__ import annotations

import pytest

from models.pwa.content_asset_names import (
    figure_lookup_names,
    normalize_content_asset_name,
    normalize_tikz_source,
    tikz_source_sha256,
)


def test_asset_names_preserve_paths_and_compare_case_insensitively() -> None:
    display, identity = normalize_content_asset_name(" Pictures/Ёж.PNG ")

    assert display == "Pictures/Ёж.PNG"
    assert identity == "pictures/ёж.png"


def test_extensionless_lookup_uses_vector_then_raster_priority() -> None:
    assert [display for display, _key in figure_lookup_names("diagram")][:4] == [
        "diagram",
        "diagram.pdf",
        "diagram.svg",
        "diagram.png",
    ]


@pytest.mark.parametrize("name", ("../secret.png", "/absolute.png", "a/./b.png"))
def test_asset_names_reject_unsafe_paths(name: str) -> None:
    with pytest.raises(ValueError):
        normalize_content_asset_name(name)


def test_tikz_normalization_removes_comments_and_whitespace() -> None:
    left = """
      \\begin{tikzpicture} % comment
        \\draw (0,0) -- (1,1);\x20\x20
      \\end{tikzpicture}
    """
    right = r"\begin{tikzpicture} \draw (0,0) -- (1,1); \end{tikzpicture}"

    assert normalize_tikz_source(left) == normalize_tikz_source(right)
    assert tikz_source_sha256(left) == tikz_source_sha256(right)


def test_tikz_normalization_keeps_escaped_percent() -> None:
    assert r"50\%" in normalize_tikz_source(r"\node {50\%}; % comment")
