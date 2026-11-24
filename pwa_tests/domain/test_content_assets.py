from __future__ import annotations

import stat
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers.pwa.content.assets import (
    AssetConversionError,
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
    ContentAssetTools,
    _safe_environment,
    sanitize_svg,
)


def _executable(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _safe_svg(*, extra: str = "") -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'width="640pt" height="480pt" viewBox="0 0 640 480">'
        '<defs><g id="glyph"><path style="fill:rgb(0%,0%,0%);stroke:none" '
        'd="M 0 0 L 10 10"/></g></defs>'
        '<g id="surface1"><use xlink:href="#glyph" x="2" y="3"/></g>'
        f"{extra}</svg>"
    ).encode()


def _vp8x(width: int, height: int) -> bytes:
    return (
        b"RIFF"
        + (22).to_bytes(4, "little")
        + b"WEBPVP8X"
        + (10).to_bytes(4, "little")
        + b"\x00" * 4
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )


def test_converter_environment_keeps_tex_caches_inside_the_job(tmp_path: Path) -> None:
    environment = _safe_environment(tmp_path)

    assert environment["HOME"] == str(tmp_path)
    assert environment["TEXMFVAR"] == str(tmp_path / "texmf-var")
    assert environment["TEXMFCONFIG"] == str(tmp_path / "texmf-config")


def test_tool_resolution_is_explicit_and_reports_only_capability(
    tmp_path: Path,
) -> None:
    executable = _executable(tmp_path, "converter", "raise SystemExit(0)")
    tools = ContentAssetTools.from_config(
        SimpleNamespace(
            pdflatex_path=executable.name,
            pdf2svg_path=executable.name,
            magick_path=executable.name,
            cwebp_path=executable.name,
        ),
        path=str(tmp_path),
    )

    assert tools.pdflatex == str(executable)
    with pytest.raises(AssetConversionError) as captured:
        ContentAssetTools.from_config(
            SimpleNamespace(
                pdflatex_path="missing",
                pdf2svg_path=executable.name,
                magick_path=executable.name,
                cwebp_path=executable.name,
            ),
            path=str(tmp_path),
        )
    assert captured.value.capability == "pdflatex_path"
    assert str(tmp_path) not in str(captured.value)


def test_svg_sanitizer_accepts_pdf2svg_shape_and_is_deterministic() -> None:
    first = sanitize_svg(_safe_svg())
    second = sanitize_svg(_safe_svg())

    assert first == second
    assert b"<script" not in first
    assert b'xlink:href="#glyph"' in first
    assert b'viewBox="0 0 640 480"' in first


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AA=="/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><use href="https://example.test/a"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><path style="fill:url(https://example.test/a)"/></svg>',
    ],
)
def test_svg_sanitizer_fails_closed_for_active_or_external_content(
    payload: bytes,
) -> None:
    with pytest.raises(AssetConversionError):
        sanitize_svg(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("source_kind", ["tikz", "pdf"])
async def test_generated_svg_preserves_bitmap_glyphs_and_cleans_tempdir(
    tmp_path: Path, source_kind: str,
) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    temp_root = tmp_path / "work"
    temp_root.mkdir()
    pdflatex = _executable(
        tools_dir,
        "pdflatex",
        """import pathlib, sys
output = next(arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('-output-directory='))
pathlib.Path(output, 'content.pdf').write_bytes(b'%PDF-1.7 synthetic')""",
    )
    pdf2svg = _executable(
        tools_dir,
        "pdf2svg",
        """import pathlib, sys
pathlib.Path(sys.argv[2]).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="640pt" height="480pt" viewBox="0 0 640 480"><image href="data:image/png;base64,AA==" width="1" height="1"/></svg>')""",
    )
    unused = _executable(tools_dir, "unused", "raise SystemExit(99)")
    converter = ContentAssetConverter(
        ContentAssetTools(
            pdflatex=str(pdflatex),
            pdf2svg=str(pdf2svg),
            magick=str(unused),
            cwebp=str(unused),
        ),
        temp_root=temp_root,
        timeout_seconds=5,
    )

    if source_kind == "tikz":
        result = await converter.tikz_to_svg(
            r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
        )
    else:
        result = await converter.pdf_to_svg(b"%PDF-1.7 synthetic")

    assert result.media_type == "image/svg+xml"
    assert (result.width, result.height) == (640, 480)
    assert result.output_sha256 != result.source_sha256
    assert b"<svg" in result.data
    assert b'<image href="data:image/png;base64,AA=="' in result.data
    assert list(temp_root.iterdir()) == []


@pytest.mark.asyncio
async def test_tikz_latex_failure_exposes_generated_tex_and_redacted_tool_output(
    tmp_path: Path,
) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    temp_root = tmp_path / "work"
    temp_root.mkdir()
    pdflatex = _executable(
        tools_dir,
        "pdflatex",
        "import sys\n"
        "print(f'{sys.argv[-1]}:7: Undefined control sequence.', file=sys.stderr)\n"
        "raise SystemExit(1)",
    )
    unused = _executable(tools_dir, "unused", "raise SystemExit(99)")
    converter = ContentAssetConverter(
        ContentAssetTools(
            pdflatex=str(pdflatex),
            pdf2svg=str(unused),
            magick=str(unused),
            cwebp=str(unused),
        ),
        temp_root=temp_root,
        timeout_seconds=5,
    )

    with pytest.raises(AssetConversionError) as captured:
        await converter.tikz_to_svg(
            r"\begin{tikzpicture}\badcommand\end{tikzpicture}"
        )

    error = captured.value
    assert error.capability == "latex-to-pdf"
    assert error.debug["generatedTex"].startswith(r"\documentclass[border=5pt]")
    assert r"\badcommand" in error.debug["generatedTex"]
    assert "content.tex:7: Undefined control sequence." in error.debug["toolOutput"]
    assert str(temp_root) not in error.debug["toolOutput"]
    assert list(temp_root.iterdir()) == []


@pytest.mark.asyncio
async def test_tikz_forbidden_primitive_is_rejected_before_process_start(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "started"
    executable = _executable(
        tmp_path,
        "must-not-start",
        f"import pathlib\npathlib.Path({str(marker)!r}).write_text('bad')",
    )
    converter = ContentAssetConverter(
        ContentAssetTools(*(str(executable) for _ in range(4))), timeout_seconds=1
    )

    with pytest.raises(AssetConversionError, match="file, dynamic or output primitive"):
        await converter.tikz_to_svg(r"\write18{touch bad}")
    assert not marker.exists()


@pytest.mark.asyncio
async def test_raster_pipeline_discards_original_bounds_dimensions_and_strips_metadata(
    tmp_path: Path,
) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    args_record = tmp_path / "magick-args.txt"
    webp_literal = repr(_vp8x(640, 480))
    magick = _executable(
        tools_dir,
        "magick",
        f"""import pathlib, sys
pathlib.Path({str(args_record)!r}).write_text('\\n'.join(sys.argv[1:]))
pathlib.Path(sys.argv[-1]).write_bytes({webp_literal})""",
    )
    cwebp = _executable(
        tools_dir,
        "cwebp",
        "raise AssertionError('Separate cwebp must not run')",
    )
    unused = _executable(tools_dir, "unused", "raise SystemExit(99)")
    converter = ContentAssetConverter(
        ContentAssetTools(
            pdflatex=str(unused),
            pdf2svg=str(unused),
            magick=str(magick),
            cwebp=str(cwebp),
        ),
        temp_root=tmp_path,
        timeout_seconds=5,
    )
    original = b"synthetic HEIC bytes with fake EXIF GPS"

    result = await converter.raster_to_webp(original)

    assert result.media_type == "image/webp"
    assert (result.width, result.height) == (640, 480)
    assert original not in result.data
    arguments = args_record.read_text()
    assert "-strip" in arguments and "-auto-orient" in arguments
    assert "-quality\n82" in arguments
    assert "input.bin[0]" in arguments
    assert "output.webp" in arguments and "normalized.png" not in arguments


@pytest.mark.asyncio
async def test_configured_raster_conversion_does_not_require_latex_or_cwebp(
    tmp_path: Path,
) -> None:
    webp_literal = repr(_vp8x(640, 480))
    magick = _executable(
        tmp_path,
        "magick",
        f"""import pathlib, sys
pathlib.Path(sys.argv[-1]).write_bytes({webp_literal})""",
    )
    converter = ConfiguredContentAssetConverter(
        SimpleNamespace(
            pdflatex_path=None,
            pdf2svg_path=None,
            magick_path=str(magick),
            cwebp_path=None,
        )
    )

    result = await converter.raster_to_webp(b"synthetic jpeg")

    assert result.media_type == "image/webp"
    assert (result.width, result.height) == (640, 480)


@pytest.mark.asyncio
async def test_configured_svg_sanitization_does_not_require_external_tools() -> None:
    converter = ConfiguredContentAssetConverter(
        SimpleNamespace(
            pdflatex_path=None,
            pdf2svg_path=None,
            magick_path=None,
            cwebp_path=None,
        )
    )

    result = await converter.svg_to_svg(_safe_svg())

    assert result.media_type == "image/svg+xml"
    assert (result.width, result.height) == (640, 480)


@pytest.mark.asyncio
async def test_converter_failure_does_not_echo_stderr_or_server_path(
    tmp_path: Path,
) -> None:
    failing = _executable(
        tmp_path,
        "failing",
        "import sys\nprint('/private/secret/path token=secret', file=sys.stderr)\nraise SystemExit(9)",
    )
    converter = ContentAssetConverter(
        ContentAssetTools(*(str(failing) for _ in range(4))),
        temp_root=tmp_path,
        timeout_seconds=1,
    )

    with pytest.raises(AssetConversionError) as captured:
        await converter.tikz_to_svg(
            r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
        )
    assert "code 9" in str(captured.value)
    assert "secret" not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)


@pytest.mark.asyncio
async def test_raster_failure_has_bounded_private_diagnostics_and_removes_input(
    tmp_path: Path,
) -> None:
    failing = _executable(
        tmp_path, "failing",
        "import os,sys\n"
        "print('x' * 5000, file=sys.stderr)\n"
        "print(os.getcwd() + '/input.bin: decoder failure /private/service/config "
        "token=hidden-value https://example.test/?secret=hidden-value', file=sys.stderr)\n"
        "raise SystemExit(7)",
    )
    work = tmp_path / "work"
    work.mkdir()
    converter = ContentAssetConverter(
        ContentAssetTools("", "", str(failing), ""),
        temp_root=work, timeout_seconds=5,
    )
    source = b"\x89PNG\r\n\x1a\nprivate-image-pixels"

    with pytest.raises(AssetConversionError) as captured:
        await converter.raster_to_webp(source)

    error = captured.value
    details = error.server_diagnostics
    assert error.capability == "image-normalization"
    assert details["return_code"] == 7
    assert details["source_format"] == "png"
    assert details["source_bytes"] == len(source)
    assert details["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert details["tool"] == "failing"
    output = details["converter_output"]
    assert len(output) <= 2048
    assert "decoder failure" in output
    assert "<workdir>" in output
    assert all(value not in output for value in (str(tmp_path), "/private/service", "hidden-value", "https://"))
    assert "private-image-pixels" not in str(details)
    assert error.debug == {}
    assert list(work.iterdir()) == []


@pytest.mark.asyncio
async def test_converter_timeout_is_redacted_and_cleans_tempdir(tmp_path: Path) -> None:
    executable = _executable(
        tmp_path,
        "slow",
        "import time\ntime.sleep(2)",
    )
    temp_root = tmp_path / "work"
    temp_root.mkdir()
    converter = ContentAssetConverter(
        ContentAssetTools(*(str(executable) for _ in range(4))),
        temp_root=temp_root,
        timeout_seconds=0.01,
    )

    with pytest.raises(AssetConversionError) as captured:
        await converter.tikz_to_svg(
            r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
        )

    assert captured.value.code == "asset.converter_timeout"
    assert captured.value.capability == "latex-to-pdf"
    assert str(tmp_path) not in str(captured.value)
    assert list(temp_root.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["tikz", "raster"])
async def test_converter_start_failure_is_redacted_for_both_paths(
    tmp_path: Path, operation: str
) -> None:
    missing = str(tmp_path / "does-not-exist")
    converter = ContentAssetConverter(
        ContentAssetTools(*(missing for _ in range(4))),
        temp_root=tmp_path,
        timeout_seconds=1,
    )

    with pytest.raises(AssetConversionError) as captured:
        if operation == "tikz":
            await converter.tikz_to_svg(
                r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}"
            )
        else:
            await converter.raster_to_webp(b"synthetic raster")

    assert captured.value.code == "asset.converter_start_failed"
    assert captured.value.capability == (
        "latex-to-pdf" if operation == "tikz" else "image-normalization"
    )
    assert str(tmp_path) not in str(captured.value)
