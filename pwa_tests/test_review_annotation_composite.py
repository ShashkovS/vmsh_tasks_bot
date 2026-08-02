"""Phase-6 Telegram derivative tests against the real ImageMagick binary."""

from __future__ import annotations

import hashlib
import shutil
import subprocess

import pytest

from helpers.pwa.review_composite import (
    ReviewCompositeRenderError,
    annotation_overlay_svg,
    render_review_annotation_composite_png,
)


MARKS = [
    {
        "markId": "mark-pencil",
        "kind": "pencil",
        "data": {
            "points": [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.9}],
            "width": 0.02,
            "color": "red",
        },
    },
    {
        "markId": "mark-eraser",
        "kind": "eraser",
        "data": {
            "points": [{"x": 0.45, "y": 0.45}, {"x": 0.55, "y": 0.55}],
            "width": 0.04,
        },
    },
    {
        "markId": "mark-arrow",
        "kind": "arrow",
        "data": {
            "start": {"x": 0.15, "y": 0.8},
            "end": {"x": 0.75, "y": 0.2},
            "width": 0.01,
            "color": "blue",
        },
    },
    {
        "markId": "mark-rectangle",
        "kind": "rectangle",
        "data": {
            "x": 0.1,
            "y": 0.15,
            "width": 0.3,
            "height": 0.2,
            "strokeWidth": 0.01,
            "color": "graphite",
        },
    },
    {
        "markId": "mark-highlight",
        "kind": "highlight",
        "data": {"x": 0.5, "y": 0.6, "width": 0.35, "height": 0.15},
    },
    {
        "markId": "mark-text",
        "kind": "text",
        "data": {
            "x": 0.08,
            "y": 0.5,
            "text": "a < b & b > 0",
            "size": 0.08,
            "color": "amber",
        },
    },
]


def test_overlay_svg_uses_normalized_canvas_and_escapes_text() -> None:
    svg = annotation_overlay_svg(width=120, height=80, marks=MARKS)

    assert 'viewBox="0 0 120 80"' in svg
    assert 'preserveAspectRatio="none"' in svg
    assert "a &lt; b &amp; b &gt; 0" in svg
    assert 'mask="url(#annotation-eraser)"' in svg
    assert "#c53d35" in svg
    assert "#416d9c" in svg


@pytest.mark.asyncio
async def test_real_magick_renders_rotated_png_without_mutating_source(
    tmp_path,
) -> None:
    magick = shutil.which("magick")
    if magick is None:
        pytest.skip("ImageMagick is not installed")
    ppm = tmp_path / "source.ppm"
    webp = tmp_path / "source.webp"
    ppm.write_bytes(b"P6\n120 80\n255\n" + (b"\xff\xff\xff" * 120 * 80))
    subprocess.run([magick, str(ppm), str(webp)], check=True, capture_output=True)
    source = webp.read_bytes()
    original_digest = hashlib.sha256(source).hexdigest()

    rendered = await render_review_annotation_composite_png(
        source_webp=source,
        rotation=90,
        marks=MARKS,
        magick_path=magick,
    )

    output = tmp_path / "composite.png"
    output.write_bytes(rendered)
    dimensions = subprocess.run(
        [magick, "identify", "-format", "%w %h", str(output)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert rendered.startswith(b"\x89PNG\r\n\x1a\n")
    assert dimensions == "80 120"
    assert hashlib.sha256(source).hexdigest() == original_digest


@pytest.mark.asyncio
async def test_corrupt_source_has_stable_redacted_error() -> None:
    magick = shutil.which("magick")
    if magick is None:
        pytest.skip("ImageMagick is not installed")

    with pytest.raises(ReviewCompositeRenderError) as captured:
        await render_review_annotation_composite_png(
            source_webp=b"not a private student image",
            rotation=0,
            marks=MARKS,
            magick_path=magick,
        )

    assert captured.value.operation == "identify"
    assert "private student image" not in str(captured.value)
