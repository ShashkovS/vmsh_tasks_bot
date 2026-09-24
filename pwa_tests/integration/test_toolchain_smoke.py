import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from vmshpwa.scripts.toolchain_smoke import run_toolchain_smoke


def _executable(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.mark.asyncio
async def test_toolchain_smoke_validates_both_derivative_chains(tmp_path):
    pdflatex = _executable(
        tmp_path,
        "pdflatex",
        """import pathlib, sys
args = sys.argv[1:]
output_dir = pathlib.Path(args[args.index('-output-directory') + 1])
(output_dir / 'smoke.pdf').write_bytes(b'%PDF-1.7 synthetic')""",
    )
    pdf2svg = _executable(
        tmp_path,
        "pdf2svg",
        """import pathlib, sys
pathlib.Path(sys.argv[2]).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')""",
    )
    magick = _executable(
        tmp_path,
        "magick",
        """import pathlib, sys
if sys.argv[1:3] == ['-list', 'format']:
    print('HEIC* HEIC rw+ High Efficiency Image Format')
else:
    pathlib.Path(sys.argv[-1]).write_bytes(b'\\x89PNG\\r\\n\\x1a\\nsynthetic')""",
    )
    cwebp = _executable(
        tmp_path,
        "cwebp",
        """import pathlib, sys
target = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
target.write_bytes(b'RIFF0000WEBPsynthetic')""",
    )
    config = SimpleNamespace(
        runtime_profile="pwa-agent",
        pdf2svg_path=str(pdf2svg),
        cwebp_path=str(cwebp),
        pdflatex_path=str(pdflatex),
        magick_path=str(magick),
    )

    # Eight xdist workers may cold-start several Python subprocesses together
    # on a developer laptop. Keep this success-path allowance above scheduler
    # noise; dedicated timeout tests cover the production kill path separately.
    report = await run_toolchain_smoke(config, timeout_seconds=5)

    assert report["ready"] is True
    assert report["tikzSvg"]["pdfBytes"] > 0
    assert report["tikzSvg"]["svgBytes"] > 0
    assert report["rasterWebp"]["webpBytes"] > 0
    assert report["rasterWebp"]["maxWidth"] == 1920
    assert report["heicDecodeAdvertised"] is True
    assert str(tmp_path) not in str(report)


@pytest.mark.asyncio
async def test_toolchain_smoke_fails_before_writes_when_a_tool_is_missing(tmp_path):
    missing = tmp_path / "missing"
    config = SimpleNamespace(
        runtime_profile="pwa-agent",
        pdf2svg_path=str(missing),
        cwebp_path=str(missing),
        pdflatex_path=str(missing),
        magick_path=str(missing),
    )

    with pytest.raises(RuntimeError, match="pdf2svg_path is missing"):
        await run_toolchain_smoke(config, timeout_seconds=1)
