"""Exercise the real TikZ→SVG and raster→WebP converter chain locally."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from helpers.pwa.toolchain import resolve_executable, run_fixed_command
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment

_TIKZ_DOCUMENT = r"""\documentclass[tikz,border=2pt]{standalone}
\begin{document}
\begin{tikzpicture}
  \draw (0,0) circle (0.6);
  \node at (0,0) {$179$};
\end{tikzpicture}
\end{document}
"""


def _required_paths(runtime_config: object, path: str | None) -> dict[str, str]:
    fields = {
        "pdf2svg": "pdf2svg_path",
        "cwebp": "cwebp_path",
        "pdflatex": "pdflatex_path",
        "magick": "magick_path",
    }
    resolved: dict[str, str] = {}
    for capability, field_name in fields.items():
        configured = getattr(runtime_config, field_name)
        executable = resolve_executable(configured, path=path)
        if executable is None:
            state = "disabled" if configured is None else "missing"
            raise RuntimeError(f"{field_name} is {state}")
        resolved[capability] = executable
    return resolved


def _assert_bytes(
    path: Path, *, prefix: bytes | None = None, contains: bytes | None = None
) -> bytes:
    data = path.read_bytes()
    if not data:
        raise RuntimeError(f"{path.name} is empty")
    if prefix is not None and not data.startswith(prefix):
        raise RuntimeError(f"{path.name} has an unexpected signature")
    if contains is not None and contains not in data:
        raise RuntimeError(f"{path.name} does not contain the expected marker")
    return data


async def run_toolchain_smoke(
    runtime_config: object,
    *,
    path: str | None = None,
    timeout_seconds: float = 60.0,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Run deterministic synthetic conversions without network or user data."""

    tools = _required_paths(runtime_config, path)
    process_environment = dict(os.environ if environment is None else environment)
    # SOURCE_DATE_EPOCH reduces irrelevant PDF metadata variation. The report
    # records validity and hashes, but does not require cross-machine equality.
    process_environment.setdefault("SOURCE_DATE_EPOCH", "1767225600")

    with tempfile.TemporaryDirectory(prefix="vmshpwa-toolchain-") as directory:
        workdir = Path(directory)
        tex_path = workdir / "smoke.tex"
        pdf_path = workdir / "smoke.pdf"
        svg_path = workdir / "smoke.svg"
        ppm_path = workdir / "input.ppm"
        png_path = workdir / "normalized.png"
        webp_path = workdir / "output.webp"

        tex_path.write_text(_TIKZ_DOCUMENT, encoding="utf-8")
        ppm_path.write_bytes(b"P6\n2 1\n255\n" + bytes((20, 80, 140, 220, 180, 40)))

        latex = await run_fixed_command(
            tools["pdflatex"],
            (
                "-no-shell-escape",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                str(workdir),
                str(tex_path),
            ),
            cwd=workdir,
            environment=process_environment,
            timeout_seconds=timeout_seconds,
        )
        if latex.return_code != 0:
            raise RuntimeError(f"pdflatex smoke failed with code {latex.return_code}")
        pdf = _assert_bytes(pdf_path, prefix=b"%PDF-")

        pdf_to_svg = await run_fixed_command(
            tools["pdf2svg"],
            (str(pdf_path), str(svg_path)),
            cwd=workdir,
            environment=process_environment,
            timeout_seconds=timeout_seconds,
        )
        if pdf_to_svg.return_code != 0:
            raise RuntimeError(
                f"pdf2svg smoke failed with code {pdf_to_svg.return_code}"
            )
        svg = _assert_bytes(svg_path, contains=b"<svg")

        normalize = await run_fixed_command(
            tools["magick"],
            (str(ppm_path), "-auto-orient", str(png_path)),
            cwd=workdir,
            environment=process_environment,
            timeout_seconds=timeout_seconds,
        )
        if normalize.return_code != 0:
            raise RuntimeError(f"magick smoke failed with code {normalize.return_code}")
        _assert_bytes(png_path, prefix=b"\x89PNG\r\n\x1a\n")

        convert = await run_fixed_command(
            tools["cwebp"],
            (str(png_path), "-resize", "1920", "0", "-q", "82", "-o", str(webp_path)),
            cwd=workdir,
            environment=process_environment,
            timeout_seconds=timeout_seconds,
        )
        if convert.return_code != 0:
            raise RuntimeError(f"cwebp smoke failed with code {convert.return_code}")
        webp = _assert_bytes(webp_path, prefix=b"RIFF", contains=b"WEBP")

        formats = await run_fixed_command(
            tools["magick"],
            ("-list", "format"),
            cwd=workdir,
            environment=process_environment,
            timeout_seconds=timeout_seconds,
            output_limit=65_536,
        )
        format_listing = f"{formats.stdout}\n{formats.stderr}".casefold()
        heic_decode = any(
            marker in format_listing
            for marker in ("heic* heic", "heic  heic", "heif* heic", "heif  heic")
        )

        return {
            "profile": getattr(runtime_config, "runtime_profile"),
            "ready": True,
            "tikzSvg": {
                "pdfBytes": len(pdf),
                "svgBytes": len(svg),
                "svgSha256": hashlib.sha256(svg).hexdigest(),
            },
            "rasterWebp": {
                "webpBytes": len(webp),
                "webpSha256": hashlib.sha256(webp).hexdigest(),
                "maxWidth": 1920,
            },
            "heicDecodeAdvertised": heic_decode,
            "executables": {name: Path(value).name for name, value in tools.items()},
        }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run local synthetic TikZ/SVG and raster/WebP conversion smoke"
    )
    parser.parse_args(argv)
    require_pwa_profile_environment()
    from helpers.config import config

    report = asyncio.run(run_toolchain_smoke(config))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
