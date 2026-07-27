from __future__ import annotations

import shutil
import os
from pathlib import Path

import pytest

from helpers.pwa.content.assets import ContentAssetConverter, ContentAssetTools


def _local_tools() -> ContentAssetTools:
    configured = {
        "pdflatex": os.environ.get("VMSH_PDFLATEX_PATH", "pdflatex"),
        "pdf2svg": os.environ.get("VMSH_PDF2SVG_PATH", "pdf2svg"),
        "magick": os.environ.get("VMSH_MAGICK_PATH", "magick"),
        "cwebp": os.environ.get("VMSH_CWEBP_PATH", "cwebp"),
    }
    resolved = {name: shutil.which(value) for name, value in configured.items()}
    missing = [name for name, path in resolved.items() if path is None]
    if missing:
        pytest.skip(
            f"local content converter tools are unavailable: {', '.join(missing)}"
        )
    return ContentAssetTools(
        pdflatex=resolved["pdflatex"] or "",
        pdf2svg=resolved["pdf2svg"] or "",
        magick=resolved["magick"] or "",
        cwebp=resolved["cwebp"] or "",
    )


@pytest.mark.asyncio
async def test_real_content_asset_toolchain_produces_safe_svg_and_bounded_webp(
    tmp_path: Path,
) -> None:
    converter = ContentAssetConverter(
        _local_tools(), temp_root=tmp_path, timeout_seconds=30
    )

    tikz = await converter.tikz_to_svg(
        r"\begin{tikzpicture}\draw (0,0) circle (1);\node at (0,0) {179};\end{tikzpicture}"
    )
    raster = await converter.raster_to_webp(
        b"P6\n4 2\n255\n" + bytes((index * 17) % 256 for index in range(4 * 2 * 3))
    )

    assert tikz.media_type == "image/svg+xml"
    assert tikz.data.startswith(b"<?xml")
    assert tikz.width > 0 and tikz.height > 0
    assert raster.media_type == "image/webp"
    assert raster.data[:4] == b"RIFF" and raster.data[8:12] == b"WEBP"
    assert (raster.width, raster.height) == (4, 2)
    assert list(tmp_path.iterdir()) == []
