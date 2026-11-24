"""Bounded MCP raster previews; vmshpwa/docs/ai-review-assistant.md."""

import asyncio
import subprocess
import tempfile
from pathlib import Path

from helpers.pwa.content import sanitize_svg

MAX_IMAGE_BYTES = 20 * 1024 * 1024


def _rasterize_svg(body, executable):
    sanitized = sanitize_svg(body)
    # Only server-owned sanitized bytes enter MSVG; no external URLs or paths.
    with tempfile.TemporaryDirectory(prefix="ai-review-image-") as directory:
        source = Path(directory) / "source.svg"
        source.write_bytes(
            sanitized if isinstance(sanitized, bytes) else sanitized.encode()
        )
        result = subprocess.run(
            [
                executable,
                "-limit",
                "memory",
                "128MiB",
                "-limit",
                "map",
                "256MiB",
                "-background",
                "white",
                f"msvg:{source}",
                "-resize",
                "2048x2048>",
                "png:-",
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if (
            result.returncode
            or not result.stdout.startswith(b"\x89PNG\r\n\x1a\n")
            or len(result.stdout) > MAX_IMAGE_BYTES
        ):
            raise ValueError("image_preview_unavailable")
        return result.stdout


async def rasterize_svg(body, executable):
    return await asyncio.to_thread(_rasterize_svg, body, executable)
