"""Stable identities for reusable lesson-content pictures and TikZ sources."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import PurePosixPath


TIKZ_NORMALIZATION_VERSION = "tikz-c14n-v1"
FIGURE_EXTENSION_PRIORITY = ("pdf", "svg", "png", "jpg", "jpeg", "gif", "webp")


def normalize_content_asset_name(value: str) -> tuple[str, str]:
    """Return a display path and its case-insensitive global identity key."""

    if not isinstance(value, str):
        raise TypeError("content asset name must be text")
    display_name = unicodedata.normalize("NFC", value.strip().replace("\\", "/"))
    if not display_name or len(display_name) > 2_000:
        raise ValueError("content asset name must contain 1..2000 characters")
    raw_parts = display_name.split("/")
    path = PurePosixPath(display_name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("content asset name must be a safe relative path")
    if any(ord(character) < 32 for character in display_name):
        raise ValueError("content asset name contains control characters")
    normalized = path.as_posix()
    return normalized, normalized.casefold()


def figure_lookup_names(value: str) -> tuple[tuple[str, str], ...]:
    """Return exact identity followed by LaTeX-style extension candidates."""

    display_name, normalized_name = normalize_content_asset_name(value)
    result = [(display_name, normalized_name)]
    if PurePosixPath(display_name).suffix:
        return tuple(result)
    for extension in FIGURE_EXTENSION_PRIORITY:
        candidate = f"{display_name}.{extension}"
        result.append((candidate, candidate.casefold()))
    return tuple(result)


def normalize_tikz_source(source: str) -> str:
    """Conservatively remove comments and insignificant TeX whitespace."""

    if not isinstance(source, str):
        raise TypeError("TikZ source must be text")
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    uncommented: list[str] = []
    for line in source.split("\n"):
        output: list[str] = []
        for index, character in enumerate(line):
            if character == "%":
                preceding = 0
                cursor = index - 1
                while cursor >= 0 and line[cursor] == "\\":
                    preceding += 1
                    cursor -= 1
                if preceding % 2 == 0:
                    break
            output.append(character)
        uncommented.append("".join(output).rstrip())
    return re.sub(r"\s+", " ", "\n".join(uncommented).strip())


def tikz_source_sha256(source: str) -> str:
    normalized = normalize_tikz_source(source)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


__all__ = [
    "FIGURE_EXTENSION_PRIORITY",
    "TIKZ_NORMALIZATION_VERSION",
    "figure_lookup_names",
    "normalize_content_asset_name",
    "normalize_tikz_source",
    "tikz_source_sha256",
]
