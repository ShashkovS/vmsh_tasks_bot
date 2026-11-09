from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers.pwa.content.pdf import PdfDerivativeRenderer


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "content"
    / "phase2-derivative-document.tex"
)


@pytest.mark.skipif(
    os.environ.get("VMSH_RUN_CONTENT_PDF_SMOKE") != "1",
    reason="requires an explicit local LaTeX toolchain opt-in",
)
@pytest.mark.asyncio
async def test_real_complete_latex_pdf_derivative_is_reproducible():
    """Local/staging proof only; the hermetic suite uses fake executables."""

    config = SimpleNamespace(
        pdflatex_path=os.environ.get("VMSH_PDFLATEX_PATH", "pdflatex")
    )
    renderer = await PdfDerivativeRenderer.from_config(
        config,
        probe_timeout_seconds=10,
        timeout_seconds=60,
    )

    first = await renderer.render(FIXTURE.read_bytes(), source_name=FIXTURE.name)
    second = await renderer.render(FIXTURE.read_bytes(), source_name=FIXTURE.name)

    assert first.data.startswith(b"%PDF-")
    assert b"%%EOF" in first.data[-2048:]
    assert first.output_sha256 == second.output_sha256
    assert first.data == second.data
    assert first.provenance == second.provenance
