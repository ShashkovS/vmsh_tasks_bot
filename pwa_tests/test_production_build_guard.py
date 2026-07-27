from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPOSITORY_ROOT / "vmshpwa"
VITE_BINARY = WORKSPACE / "node_modules" / ".bin" / "vite"


@pytest.mark.parametrize("audience", ["student", "family", "staff"])
@pytest.mark.parametrize("unsafe_flag", ["VITE_ENABLE_MSW", "VITE_PROTOTYPE"])
def test_production_build_fails_closed_before_touching_output(
    tmp_path: Path,
    audience: str,
    unsafe_flag: str,
):
    """An unsafe flag must fail before Vite empties or creates a usable bundle."""

    output = tmp_path / f"{audience}-{unsafe_flag.lower()}"
    output.mkdir()
    marker = output / "do-not-overwrite.txt"
    marker.write_text("unchanged", encoding="utf-8")
    environment = os.environ.copy()
    environment.update({"CI": "true", unsafe_flag: "true"})
    for other_flag in {"VITE_ENABLE_MSW", "VITE_PROTOTYPE"} - {unsafe_flag}:
        environment.pop(other_flag, None)

    result = subprocess.run(
        [
            str(VITE_BINARY),
            "build",
            "--outDir",
            str(output),
        ],
        cwd=WORKSPACE / "apps" / audience,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "MSW and prototype mode must never be enabled" in (
        result.stdout + result.stderr
    )
    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert list(output.iterdir()) == [marker]
