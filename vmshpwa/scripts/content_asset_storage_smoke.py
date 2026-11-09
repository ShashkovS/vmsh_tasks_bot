"""Guarded TikZ/SVG and raster/WebP roundtrip in the disposable test S3.

This command is deliberately outside ordinary unit/E2E targets.  It converts
only fixed synthetic inputs, uses the pinned ``pwa-s3-integration`` profile,
and deletes every object whose upload was attempted.  See Phase 2 in
``vmshpwa/dev/development-plan/06-phase-2-content.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from helpers.object_storage import (
    ObjectStorage,
    content_addressed_key,
    create_object_storage,
)
from helpers.pwa.content.assets import (
    ContentAssetConverter,
    ContentAssetTools,
    ConvertedAsset,
)
from helpers.pwa.storage_config import S3_TEST_RUNTIME_PROFILE, load_storage_config
from vmshpwa.scripts.storage_smoke import (
    LIVE_S3_OPT_IN,
    TEST_BINDING_PATH,
    StorageSmokeError,
    require_live_opt_in,
    verify_test_bucket_binding,
)

_TIKZ_SOURCE = (
    r"\begin{tikzpicture}"
    r"\draw (0,0) circle (1);"
    r"\node at (0,0) {$179$};"
    r"\end{tikzpicture}"
)
_RASTER_SOURCE = b"P6\n4 2\n255\n" + bytes(
    (index * 17) % 256 for index in range(4 * 2 * 3)
)


@dataclass(frozen=True, slots=True)
class AssetProbe:
    """One synthetic immutable object and its safe expected metadata."""

    name: str
    extension: str
    asset: ConvertedAsset


async def _public_get(url: str, maximum_bytes: int) -> tuple[int, bytes]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=False) as response:
            return response.status, await response.content.read(maximum_bytes + 1)


async def roundtrip_asset(
    storage: ObjectStorage,
    probe: AssetProbe,
    *,
    public_get: Callable[[str, int], Awaitable[tuple[int, bytes]]],
) -> dict[str, object]:
    """Put/read/public-read/delete one converted asset with cleanup on failure."""

    if hashlib.sha256(probe.asset.data).hexdigest() != probe.asset.output_sha256:
        raise StorageSmokeError(
            f"Synthetic {probe.name} converter hash does not match its bytes"
        )
    key = content_addressed_key("content", probe.asset.data, probe.extension)
    public_url = storage.public_url(key)
    if public_url is None:
        raise StorageSmokeError("Content-asset test storage has no public GET URL")

    put_attempted = False
    primary_error: Exception | None = None
    cleanup_error: Exception | None = None
    result: dict[str, object] = {
        "name": probe.name,
        "mediaType": probe.asset.media_type,
        "byteSize": len(probe.asset.data),
        "width": probe.asset.width,
        "height": probe.asset.height,
        "sourceSha256": probe.asset.source_sha256,
        "outputSha256": probe.asset.output_sha256,
        "put": "pending",
        "privateRead": "pending",
        "publicGet": "pending",
        "deleteAck": "pending",
    }
    try:
        put_attempted = True
        await storage.put(key, probe.asset.data, probe.asset.media_type)
        result["put"] = "passed"
        private_payload = await storage.get(key)
        if private_payload != probe.asset.data:
            raise StorageSmokeError(
                f"Private S3 read did not match synthetic {probe.name} bytes"
            )
        result["privateRead"] = "passed"
        status, public_payload = await public_get(public_url, len(probe.asset.data))
        if status != 200 or public_payload != probe.asset.data:
            raise StorageSmokeError(
                f"Public S3 GET did not match synthetic {probe.name} bytes"
            )
        result["publicGet"] = "passed"
    except Exception as error:
        primary_error = error
    finally:
        if put_attempted:
            try:
                await storage.delete(key)
                result["deleteAck"] = "passed"
            except Exception as error:
                cleanup_error = error

    if primary_error is not None or cleanup_error is not None:
        # Provider messages may contain endpoints, keys or signed values.  The
        # live report therefore records only stable stages and exception types.
        failures: list[str] = []
        if primary_error is not None:
            failures.append(f"roundtrip:{type(primary_error).__name__}")
        if cleanup_error is not None:
            failures.append(f"cleanup:{type(cleanup_error).__name__}")
        raise StorageSmokeError(
            f"Synthetic {probe.name} S3 lifecycle failed ({','.join(failures)})"
        ) from None
    return result


def _tool_config(environ: Mapping[str, str]) -> object:
    def value(name: str, default: str) -> str | None:
        raw = environ.get(name)
        if raw is None:
            return default
        normalized = raw.strip()
        if not normalized or normalized.casefold() in {"disabled", "none"}:
            return None
        return normalized

    return SimpleNamespace(
        pdflatex_path=value("VMSH_PDFLATEX_PATH", "pdflatex"),
        pdf2svg_path=value("VMSH_PDF2SVG_PATH", "pdf2svg"),
        magick_path=value("VMSH_MAGICK_PATH", "magick"),
        cwebp_path=value("VMSH_CWEBP_PATH", "cwebp"),
    )


async def run_content_asset_storage_smoke(
    *,
    run_id: str,
    repository_root: Path,
    environ: Mapping[str, str],
    public_get: Callable[[str, int], Awaitable[tuple[int, bytes]]] = _public_get,
) -> dict[str, object]:
    """Convert fixed sources and exercise the pinned test bucket only."""

    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root="unused",
        repository_root=repository_root,
        integration_run_id=run_id,
    )
    verify_test_bucket_binding(config, binding_path=TEST_BINDING_PATH)
    tools = ContentAssetTools.from_config(_tool_config(environ))
    converter = ContentAssetConverter(tools, timeout_seconds=60)
    tikz, raster = await asyncio.gather(
        converter.tikz_to_svg(_TIKZ_SOURCE),
        converter.raster_to_webp(_RASTER_SOURCE),
    )
    storage = create_object_storage(config)
    results = []
    for probe in (
        AssetProbe("tikz-svg", "svg", tikz),
        AssetProbe("raster-webp", "webp", raster),
    ):
        results.append(
            await roundtrip_asset(
                storage,
                probe,
                public_get=public_get,
            )
        )
    return {
        "schemaVersion": 1,
        "ok": True,
        "syntheticOnly": True,
        "runId": run_id,
        "storage": config.safe_report(),
        "assets": results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-id",
        default=None,
        help="lowercase disposable run id; generated when omitted",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        require_live_opt_in()
        run_id = _parser().parse_args(argv).run_id or (
            f"content-{secrets.token_hex(8)}"
        )
        report = asyncio.run(
            run_content_asset_storage_smoke(
                run_id=run_id,
                repository_root=Path(__file__).resolve().parents[2],
                environ=os.environ,
            )
        )
    except Exception as error:
        # Never serialize the exception message: provider/tool failures may
        # echo a URL, path or request payload.  Unit tests cover this boundary.
        print(
            json.dumps(
                {
                    "ok": False,
                    "errorCode": f"content_asset_smoke_{type(error).__name__}",
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AssetProbe",
    "LIVE_S3_OPT_IN",
    "main",
    "roundtrip_asset",
    "run_content_asset_storage_smoke",
]
