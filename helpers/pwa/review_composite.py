"""Render one immutable review annotation over its source WebP for Telegram.

The browser and Telegram must display the same normalized Phase-6 marks.  This
module intentionally does only that small derivative step: it does not read the
database, choose recipients or send Telegram messages.  See
``vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`` and
``vmshpwa/packages/product/src/review-annotation-surface.tsx``.
"""

from __future__ import annotations

import asyncio
import html
import json
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path


_COLORS = {
    "red": "#c53d35",
    "blue": "#416d9c",
    "graphite": "#25282e",
    "amber": "#e7c64a",
}


class ReviewCompositeRenderError(RuntimeError):
    """ImageMagick could not identify or render the review derivative."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"Review annotation composite {operation} failed")


def _number(value: object) -> float:
    return float(value)


def _scaled(value: object, scale: int) -> str:
    return f"{_number(value) * scale:.6f}"


def _point(value: object, *, width: int, height: int) -> tuple[str, str]:
    point = value if isinstance(value, Mapping) else {}
    return _scaled(point["x"], width), _scaled(point["y"], height)


def _path(points: object, *, width: int, height: int) -> str:
    normalized = points if isinstance(points, Sequence) else ()
    return " ".join(
        f"{'M' if index == 0 else 'L'} {x} {y}"
        for index, item in enumerate(normalized)
        for x, y in [_point(item, width=width, height=height)]
    )


def _color(value: object) -> str:
    return _COLORS[str(value)]


def annotation_overlay_svg(
    *, width: int, height: int, marks: Sequence[Mapping[str, object]]
) -> str:
    """Build the transparent SVG overlay consumed by ImageMagick."""

    scale = min(width, height)
    erasers: list[str] = []
    visible: list[str] = []
    for mark in marks:
        kind = str(mark["kind"])
        raw_data = mark["data"]
        data = raw_data if isinstance(raw_data, Mapping) else {}
        if kind == "eraser":
            erasers.append(
                '<path d="{}" fill="none" stroke="black" '
                'stroke-linecap="round" stroke-linejoin="round" stroke-width="{}"/>'.format(
                    _path(data["points"], width=width, height=height),
                    _scaled(data["width"], scale),
                )
            )
        elif kind == "pencil":
            visible.append(
                '<path d="{}" fill="none" stroke="{}" '
                'stroke-linecap="round" stroke-linejoin="round" stroke-width="{}"/>'.format(
                    _path(data["points"], width=width, height=height),
                    _color(data["color"]),
                    _scaled(data["width"], scale),
                )
            )
        elif kind == "arrow":
            start_x, start_y = _point(data["start"], width=width, height=height)
            end_x, end_y = _point(data["end"], width=width, height=height)
            visible.append(
                f'<line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" '
                f'stroke="{_color(data["color"])}" stroke-linecap="round" '
                f'stroke-width="{_scaled(data["width"], scale)}" '
                'marker-end="url(#annotation-arrow)"/>'
            )
        elif kind == "rectangle":
            visible.append(
                f'<rect x="{_scaled(data["x"], width)}" '
                f'y="{_scaled(data["y"], height)}" '
                f'width="{_scaled(data["width"], width)}" '
                f'height="{_scaled(data["height"], height)}" fill="none" '
                f'stroke="{_color(data["color"])}" '
                f'stroke-width="{_scaled(data["strokeWidth"], scale)}"/>'
            )
        elif kind == "highlight":
            visible.append(
                f'<rect x="{_scaled(data["x"], width)}" '
                f'y="{_scaled(data["y"], height)}" '
                f'width="{_scaled(data["width"], width)}" '
                f'height="{_scaled(data["height"], height)}" '
                'fill="#e7c64a" fill-opacity="0.35"/>'
            )
        elif kind == "text":
            visible.append(
                f'<text x="{_scaled(data["x"], width)}" '
                f'y="{_scaled(data["y"], height)}" '
                f'fill="{_color(data["color"])}" '
                f'font-family="Arial, sans-serif" font-weight="600" '
                f'font-size="{_scaled(data["size"], scale)}" '
                f'dominant-baseline="hanging">{html.escape(str(data["text"]))}</text>'
            )
        else:
            raise ValueError(f"unsupported review annotation mark: {kind}")

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        '<defs><mask id="annotation-eraser" maskUnits="userSpaceOnUse" '
        f'x="0" y="0" width="{width}" height="{height}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>'
        f"{''.join(erasers)}</mask>"
        '<marker id="annotation-arrow" markerWidth="4" markerHeight="4" '
        'refX="3.5" refY="2" orient="auto" markerUnits="strokeWidth" '
        'viewBox="0 0 4 4"><path d="M 0 0 L 4 2 L 0 4 z" '
        'fill="context-stroke"/></marker></defs>'
        f'<g mask="url(#annotation-eraser)">{"".join(visible)}</g></svg>'
    )


def _run(command: list[str], *, operation: str) -> bytes:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReviewCompositeRenderError(operation) from error
    if result.returncode != 0:
        # Provider paths and ImageMagick diagnostics can contain private local
        # filenames, so callers receive only the stable operation label.
        raise ReviewCompositeRenderError(operation)
    return result.stdout


def _render_sync(
    *,
    source_webp: bytes,
    rotation: int,
    marks: Sequence[Mapping[str, object]],
    magick_path: str,
) -> bytes:
    if not source_webp:
        raise ReviewCompositeRenderError("identify")
    if rotation not in {0, 90, 180, 270}:
        raise ValueError("review annotation rotation is not supported")
    with tempfile.TemporaryDirectory(prefix="vmsh-review-composite-") as directory:
        root = Path(directory)
        source_path = root / "source.webp"
        overlay_path = root / "overlay.svg"
        source_path.write_bytes(source_webp)
        dimensions = _run(
            [magick_path, "identify", "-format", "%w %h", str(source_path)],
            operation="identify",
        ).decode("ascii", errors="strict")
        try:
            width, height = (int(part) for part in dimensions.split())
        except (ValueError, TypeError) as error:
            raise ReviewCompositeRenderError("identify") from error
        if not 1 <= width <= 20_000 or not 1 <= height <= 20_000:
            raise ReviewCompositeRenderError("identify")
        overlay_path.write_text(
            annotation_overlay_svg(width=width, height=height, marks=marks),
            encoding="utf-8",
        )
        output = _run(
            [
                magick_path,
                str(source_path),
                str(overlay_path),
                "-compose",
                "over",
                "-composite",
                "-background",
                "none",
                "-rotate",
                str(rotation),
                "-strip",
                "-define",
                "png:compression-level=9",
                "png:-",
            ],
            operation="render",
        )
        if not output.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ReviewCompositeRenderError("render")
        return output


async def render_review_annotation_composite_png(
    *,
    source_webp: bytes,
    rotation: int,
    marks: Sequence[Mapping[str, object]],
    magick_path: str = "magick",
) -> bytes:
    """Rasterize a canonical annotation manifest without changing the WebP."""

    # Copy through canonical JSON so a mutable caller cannot change nested mark
    # data while the worker thread is rendering it.
    frozen_marks = json.loads(
        json.dumps(list(marks), ensure_ascii=False, separators=(",", ":"))
    )
    return await asyncio.to_thread(
        _render_sync,
        source_webp=bytes(source_webp),
        rotation=rotation,
        marks=frozen_marks,
        magick_path=magick_path,
    )


__all__ = [
    "ReviewCompositeRenderError",
    "annotation_overlay_svg",
    "render_review_annotation_composite_png",
]
