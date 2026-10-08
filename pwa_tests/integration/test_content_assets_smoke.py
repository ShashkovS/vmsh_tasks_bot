from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from helpers.pwa.content.assets import (
    AssetConversionError,
    ContentAssetConverter,
    ContentAssetTools,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_CHANNEL_PHOTO_ROOT = (
    REPOSITORY_ROOT / "_external_pipelines/ChatExport_2026-07-25/photos"
)
PUBLIC_CHANNEL_PHOTO_CORPUS = (
    (
        "photo_586@01-04-2026_10-55-35.jpg",
        "e268e366d641d9dca4ff4cccf5761f1b918c04db42a3a7e84bab396d8432f511",
        (1241, 1754),
    ),
    (
        "photo_601@01-04-2026_10-59-35.jpg",
        "f4722372def94f50c1b0216fc5faf4ce59239182a53f7c9bb905b3c4f7f20e3f",
        (521, 385),
    ),
    (
        "photo_618@01-04-2026_23-01-01.jpg",
        "1790587dfb8d45d3a3081405b0f5c31c1b21d3f078dd4b1d8bb7ee40fe519d33",
        (905, 1280),
    ),
    (
        "photo_721@03-05-2026_21-51-57.jpg",
        "fb561ef81fc2b687761efea895065fca0d6d0e4b1b50e07084c7547428007293",
        (1236, 1264),
    ),
    (
        "photo_742@12-05-2026_20-15-33.jpg",
        "d41afa7fa68593d8bb7805972978b8980780fb2f73f6a7b5bd36190695847c5a",
        (1201, 588),
    ),
)

# Small synthetic JPEG with harmless EXIF GPS coordinates and a comment.  It is
# embedded so the production converter test does not acquire an exiftool/Pillow
# dependency.  Phase 5 requires proof that decoded re-encode removes location
# metadata, not a new metadata-processing subsystem.
EXIF_GPS_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/4QDURXhpZgAATU0AKgAAAAgABQEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAEAAAITAAMAAAABAAEAAIglAAQAAAABAAAAWgAAAAAAAAABAAAAAQAAAAEAAAABAAUAAAABAAAABAIDAAAAAQACAAAAAk4AAAAAAgAFAAAAAwAAAJwAAwACAAAAAkUAAAAABAAFAAAAAwAAALQAAAAAAAAANwAAAAEAAAAtAAAAAQAAAAAAAAABAAAAJQAAAAEAAAAkAAAAAQAAACQAAAAB//4AGXZtc2ggc3ludGhldGljIHRlc3QgR1BT/9sAQwADAgICAgIDAgICAwMDAwQGBAQEBAQIBgYFBgkICgoJCAkJCgwPDAoLDgsJCQ0RDQ4PEBAREAoMEhMSEBMPEBAQ/8AACwgAIABAAQERAP/EABYAAQEBAAAAAAAAAAAAAAAAAAAICf/EABoQAAICAwAAAAAAAAAAAAAAAAAXAWNkkaH/2gAIAQEAAD8A0GZeRGwy8iNhl5EbDLyI2GXkRsMvIjYZeRGwy8iNkoMu/oZd/Qy7+hl39DLv6GXf0Mu/oZd/ST2Xf0Mu/oZd/Qy7+hl39DLv6GXf0Mu/pJ7LyJ2GXkTsMvInYZeROwy8idhl5E7DLyJ2GXkTs//Z"
)


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


def _local_raster_tools() -> ContentAssetTools:
    configured = {
        "magick": os.environ.get("VMSH_MAGICK_PATH", "magick"),
        "cwebp": os.environ.get("VMSH_CWEBP_PATH", "cwebp"),
    }
    resolved = {name: shutil.which(value) for name, value in configured.items()}
    missing = [name for name, path in resolved.items() if path is None]
    if missing:
        pytest.skip(
            f"local raster converter tools are unavailable: {', '.join(missing)}"
        )
    return ContentAssetTools(
        pdflatex="unused-by-raster-corpus",
        pdf2svg="unused-by-raster-corpus",
        magick=resolved["magick"] or "",
        cwebp=resolved["cwebp"] or "",
    )


def _run_magick(magick: str, *arguments: str) -> None:
    subprocess.run(
        [magick, *arguments],
        check=True,
        capture_output=True,
        timeout=30,
    )


def _identify(magick: str, image: Path, expression: str) -> str:
    completed = subprocess.run(
        [magick, "identify", "-quiet", "-format", expression, str(image)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout


def _ssim_distortion(magick: str, reference: Path, candidate: Path) -> float:
    completed = subprocess.run(
        [
            magick,
            str(reference),
            str(candidate),
            "-metric",
            "SSIM",
            "-compare",
            "-format",
            "%[distortion]",
            "info:",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode not in {0, 1}:
        raise AssertionError(
            f"ImageMagick comparison failed with {completed.returncode}"
        )
    return float(completed.stdout)


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


@pytest.mark.asyncio
async def test_real_raster_corpus_normalizes_jpeg_and_heic_without_metadata(
    tmp_path: Path,
) -> None:
    """Exercise the Phase-5 photo boundary with real decoder input formats."""

    tools = _local_raster_tools()
    source_root = tmp_path / "sources"
    source_root.mkdir()
    jpeg_path = source_root / "oriented-with-comment.jpg"
    heic_path = source_root / "iphone-like.heic"
    metadata_marker = "vmsh-test-gps-55.75-37.61"
    exiftool = shutil.which("exiftool")
    if exiftool is None:
        pytest.skip("local EXIF corpus tool is unavailable: exiftool")
    _run_magick(
        tools.magick,
        "-size",
        "2600x1300",
        "gradient:#f8fafc-#1f2937",
        str(jpeg_path),
    )
    subprocess.run(
        [
            exiftool,
            "-overwrite_original",
            "-Orientation#=6",
            "-GPSLatitude=55.75",
            "-GPSLatitudeRef=N",
            "-GPSLongitude=37.61",
            "-GPSLongitudeRef=E",
            f"-UserComment={metadata_marker}",
            str(jpeg_path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    _run_magick(
        tools.magick,
        "-size",
        "640x480",
        "gradient:#fef3c7-#1d4ed8",
        "-set",
        "comment",
        metadata_marker,
        str(heic_path),
    )
    assert _identify(tools.magick, jpeg_path, "%[orientation]") == "RightTop"
    source_exif = subprocess.run(
        [
            exiftool,
            "-s",
            "-GPSLatitude",
            "-GPSLongitude",
            "-UserComment",
            str(jpeg_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    assert metadata_marker in source_exif
    assert "GPSLatitude" in source_exif and "GPSLongitude" in source_exif

    converter = ContentAssetConverter(tools, temp_root=tmp_path, timeout_seconds=30)
    jpeg_result = await converter.raster_to_webp(jpeg_path.read_bytes())
    heic_result = await converter.raster_to_webp(heic_path.read_bytes())

    assert (jpeg_result.width, jpeg_result.height) == (960, 1920)
    assert (heic_result.width, heic_result.height) == (640, 480)
    for index, result in enumerate((jpeg_result, heic_result), start=1):
        assert result.media_type == "image/webp"
        assert max(result.width, result.height) <= 1920
        assert metadata_marker.encode() not in result.data
        output_path = source_root / f"normalized-{index}.webp"
        output_path.write_bytes(result.data)
        assert _identify(tools.magick, output_path, "%c") == ""
        output_exif = subprocess.run(
            [
                exiftool,
                "-s",
                "-GPSLatitude",
                "-GPSLongitude",
                "-UserComment",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
        assert output_exif == ""


@pytest.mark.asyncio
async def test_real_raster_corpus_accepts_png_and_existing_webp(
    tmp_path: Path,
) -> None:
    tools = _local_raster_tools()
    source_root = tmp_path / "png-webp-sources"
    source_root.mkdir()
    png_path = source_root / "transparent-figure.png"
    webp_path = source_root / "already-webp.webp"
    _run_magick(
        tools.magick,
        "-size",
        "320x240",
        "xc:none",
        "-fill",
        "#ffffff",
        "-draw",
        "rectangle 0,0 319,239",
        "-fill",
        "#111827",
        "-draw",
        "line 20,200 300,40",
        str(png_path),
    )
    _run_magick(
        tools.magick,
        "-size",
        "480x320",
        "gradient:#f8fafc-#1e3a8a",
        str(webp_path),
    )

    converter = ContentAssetConverter(tools, temp_root=tmp_path, timeout_seconds=30)
    png_result = await converter.raster_to_webp(png_path.read_bytes())
    webp_result = await converter.raster_to_webp(webp_path.read_bytes())

    assert (png_result.width, png_result.height) == (320, 240)
    assert (webp_result.width, webp_result.height) == (480, 320)
    assert png_result.media_type == webp_result.media_type == "image/webp"


@pytest.mark.asyncio
async def test_real_public_math_photo_corpus_keeps_text_quality_and_bounds(
    tmp_path: Path,
) -> None:
    """Guard quality 82 against representative public ВМШ math materials."""

    if not PUBLIC_CHANNEL_PHOTO_ROOT.is_dir():
        pytest.skip("owner-local public Telegram photo export is unavailable")
    tools = _local_raster_tools()
    converter = ContentAssetConverter(tools, temp_root=tmp_path, timeout_seconds=30)
    results_root = tmp_path / "corpus-results"
    results_root.mkdir()

    for filename, expected_sha256, expected_dimensions in PUBLIC_CHANNEL_PHOTO_CORPUS:
        source = PUBLIC_CHANNEL_PHOTO_ROOT / filename
        if not source.is_file():
            pytest.skip(f"owner-local corpus member is unavailable: {filename}")
        payload = source.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected_sha256

        converted = await converter.raster_to_webp(payload)
        assert converted.source_sha256 == expected_sha256
        assert (converted.width, converted.height) == expected_dimensions
        assert max(converted.width, converted.height) <= 1920
        assert converted.data[:4] == b"RIFF" and converted.data[8:12] == b"WEBP"

        candidate = results_root / f"{source.stem}.webp"
        candidate.write_bytes(converted.data)
        # ImageMagick documents %[distortion] as the normalized compare metric.
        # This deliberately loose regression bound catches a broken encoder or
        # accidental low-quality setting without pretending SSIM proves human
        # readability; owner visual review remains a separate gate.
        assert _ssim_distortion(tools.magick, source, candidate) < 0.01
        assert _identify(tools.magick, candidate, "%c") == ""


@pytest.mark.asyncio
async def test_real_converter_strips_exif_gps_profile(tmp_path: Path) -> None:
    tools = _local_raster_tools()
    source = tmp_path / "source-with-gps.jpg"
    source.write_bytes(EXIF_GPS_JPEG)
    assert _identify(tools.magick, source, "%[EXIF:GPSLatitude]") == "55/1,45/1,0/1"
    assert _identify(tools.magick, source, "%[EXIF:GPSLongitude]") == "37/1,36/1,36/1"

    converter = ContentAssetConverter(tools, temp_root=tmp_path, timeout_seconds=30)
    converted = await converter.raster_to_webp(EXIF_GPS_JPEG)
    output = tmp_path / "gps-stripped.webp"
    output.write_bytes(converted.data)

    assert b"EXIF" not in converted.data.upper()
    assert b"vmsh synthetic test GPS" not in converted.data
    assert _identify(tools.magick, output, "%[EXIF:GPSLatitude]") == ""
    assert _identify(tools.magick, output, "%[EXIF:GPSLongitude]") == ""


@pytest.mark.asyncio
async def test_real_raster_corpus_rejects_corrupt_and_oversized_inputs(
    tmp_path: Path,
) -> None:
    converter = ContentAssetConverter(
        _local_raster_tools(), temp_root=tmp_path, timeout_seconds=30
    )

    with pytest.raises(AssetConversionError) as corrupt:
        await converter.raster_to_webp(b"not a jpeg, heic, png or other image")
    assert corrupt.value.capability == "image-normalization"

    with pytest.raises(AssetConversionError) as oversized:
        await converter.raster_to_webp(b"x" * (25 * 1024 * 1024 + 1))
    assert oversized.value.code == "asset.raster_size"
