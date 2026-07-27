from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers.pwa.content.pdf import (
    PDF_RENDERER_VERSION,
    PdfDerivativeError,
    PdfDerivativeRenderer,
    probe_pdf_tool,
)
from helpers.pwa.toolchain import ToolStatus


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "content"
    / "phase2-derivative-document.tex"
)


def _executable(tmp_path: Path, name: str, body: str) -> Path:
    executable = tmp_path / name
    executable.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def _config(executable: Path):
    return SimpleNamespace(pdflatex_path=str(executable))


@pytest.mark.asyncio
async def test_pdf_probe_and_renderer_use_fixed_argv_and_redacted_provenance(
    tmp_path,
):
    capture = tmp_path / "argv.json"
    executable = _executable(
        tmp_path,
        "safe-pdflatex",
        f"""import json, os, pathlib, sys
if '-version' in sys.argv:
    print('Synthetic pdfTeX 1.0 at /private/operator/toolchain')
    raise SystemExit(0)
pathlib.Path({str(capture)!r}).write_text(json.dumps({{
    'argv': sys.argv[1:],
    'shell_escape': os.environ.get('shell_escape'),
    'source_date_epoch': os.environ.get('SOURCE_DATE_EPOCH'),
    'tz': os.environ.get('TZ'),
}}))
pathlib.Path('content.pdf').write_bytes(b'%PDF-1.7\\nsynthetic derivative\\n%%EOF\\n')""",
    )

    probe = await probe_pdf_tool(_config(executable), timeout_seconds=1)
    renderer = await PdfDerivativeRenderer.from_config(
        _config(executable),
        temp_root=tmp_path,
        probe_timeout_seconds=1,
        timeout_seconds=1,
    )
    first = await renderer.render(FIXTURE.read_bytes(), source_name=FIXTURE.name)
    second = await renderer.render(FIXTURE.read_bytes(), source_name=FIXTURE.name)

    invocation = json.loads(capture.read_text())
    assert probe.status is ToolStatus.READY
    assert "/private/operator" not in json.dumps(probe.public_dict())
    assert str(tmp_path) not in repr(probe)
    assert invocation["argv"] == [
        "-no-shell-escape",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-recorder",
        "-jobname=content",
        "-output-directory=.",
        "content.tex",
    ]
    assert invocation["shell_escape"] == "f"
    assert invocation["source_date_epoch"] == "1767225600"
    assert invocation["tz"] == "UTC"
    assert first == second
    assert first.media_type == "application/pdf"
    assert first.data.startswith(b"%PDF-")
    assert first.provenance["rendererVersion"] == PDF_RENDERER_VERSION
    assert first.provenance["tool"]["executable"] == "safe-pdflatex"
    assert "/private/operator" not in json.dumps(first.provenance)
    assert str(tmp_path) not in json.dumps(first.provenance)


@pytest.mark.asyncio
async def test_pdf_probe_reports_missing_without_attempting_render(tmp_path):
    probe = await probe_pdf_tool(
        SimpleNamespace(pdflatex_path="missing-pdf-tool"),
        path=str(tmp_path),
        timeout_seconds=1,
    )

    assert probe.status is ToolStatus.MISSING
    with pytest.raises(PdfDerivativeError) as captured:
        await PdfDerivativeRenderer.from_config(
            SimpleNamespace(pdflatex_path="missing-pdf-tool"),
            path=str(tmp_path),
            probe_timeout_seconds=1,
        )
    assert captured.value.code == "pdf.tool_missing"
    assert str(tmp_path) not in str(captured.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        (
            """import sys
if '-version' in sys.argv:
    print('Synthetic pdfTeX 1.0')
else:
    print('/private/secret/source.tex and message content', file=sys.stderr)
    raise SystemExit(7)""",
            "pdf.converter_failed",
        ),
        (
            """import sys, time
if '-version' in sys.argv:
    print('Synthetic pdfTeX 1.0')
else:
    time.sleep(5)""",
            "pdf.converter_timeout",
        ),
        (
            """import sys
if '-version' in sys.argv:
    print('Synthetic pdfTeX 1.0')""",
            "pdf.output_missing",
        ),
    ],
)
async def test_pdf_converter_failures_are_bounded_and_redacted(
    tmp_path,
    body,
    expected_code,
):
    executable = _executable(tmp_path, "pdflatex", body)
    renderer = await PdfDerivativeRenderer.from_config(
        _config(executable),
        temp_root=tmp_path,
        probe_timeout_seconds=1,
        timeout_seconds=0.05,
    )

    with pytest.raises(PdfDerivativeError) as captured:
        await renderer.render(FIXTURE.read_bytes(), source_name=FIXTURE.name)

    assert captured.value.code == expected_code
    assert "/private/secret" not in str(captured.value)
    assert "message content" not in str(captured.value)


@pytest.mark.asyncio
async def test_invalid_source_is_rejected_before_external_process(tmp_path):
    marker = tmp_path / "converter-ran"
    executable = _executable(
        tmp_path,
        "pdflatex",
        f"""import pathlib, sys
if '-version' in sys.argv:
    print('Synthetic pdfTeX 1.0')
else:
    pathlib.Path({str(marker)!r}).write_text('unexpected')""",
    )
    renderer = await PdfDerivativeRenderer.from_config(
        _config(executable),
        temp_root=tmp_path,
        probe_timeout_seconds=1,
        timeout_seconds=1,
    )
    unsafe = (
        r"\documentclass{article}\begin{document}"
        r"\задача text\input{/etc/passwd}\кзадача\end{document}"
    ).encode()

    with pytest.raises(PdfDerivativeError) as captured:
        await renderer.render(unsafe, source_name="unsafe.tex")

    assert captured.value.code == "pdf.source_invalid"
    assert not marker.exists()
