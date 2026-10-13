"""Opt-in disposable S3 integration smoke for the dedicated test bucket.

This command is intentionally absent from ordinary test targets. It accepts
only the test S3 profile, forces ``integration/<run-id>/`` and cleans its probe
object in ``finally``. Full object/public URLs and credentials are never
printed. See ``vmshpwa/docs/object-storage.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from urllib.parse import urlsplit

from helpers.object_storage import (
    ObjectStorage,
    ObjectStorageOperationError,
    create_object_storage,
)
from helpers.pwa.storage_config import (
    S3_TEST_RUNTIME_PROFILE,
    StorageConfig,
    StorageConfigurationError,
    load_storage_config,
)


LIVE_S3_OPT_IN = "VMSH_ENABLE_LIVE_S3_TEST"
TEST_BINDING_PATH = (
    Path(__file__).resolve().parents[2]
    / "vmshpwa/fixtures/integration/s3-test-binding-v1.json"
)
_SAFE_S3_ERROR_CODE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{0,63}")


class StorageSmokeError(RuntimeError):
    """The disposable live sequence failed or could not be cleaned up."""


def _safe_provider_failure(step: str, error: Exception) -> StorageSmokeError:
    """Keep a useful S3 status/code while discarding provider message and URLs."""

    if isinstance(error, ObjectStorageOperationError):
        return StorageSmokeError(f"{step} failed ({error.safe_detail})")

    response = getattr(error, "response", None)
    code: str | None = None
    status: int | None = None
    if isinstance(response, Mapping):
        error_payload = response.get("Error")
        if isinstance(error_payload, Mapping):
            candidate = error_payload.get("Code")
            if isinstance(candidate, str) and _SAFE_S3_ERROR_CODE_RE.fullmatch(
                candidate
            ):
                code = candidate
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, Mapping):
            candidate = metadata.get("HTTPStatusCode")
            if isinstance(candidate, int) and 100 <= candidate <= 599:
                status = candidate

    details = [type(error).__name__]
    if code is not None:
        details.append(code)
    if status is not None:
        details.append(f"HTTP-{status}")
    return StorageSmokeError(f"{step} failed ({'/'.join(details)})")


async def _public_get(url: str) -> tuple[int, bytes]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=False) as response:
            return response.status, await response.content.read(4097)


async def run_storage_smoke(
    storage: ObjectStorage,
    *,
    run_id: str,
    public_get: Callable[[str], Awaitable[tuple[int, bytes]]] = _public_get,
    probe_nonce: str | None = None,
) -> dict[str, object]:
    """Exercise put/private read/public read/delete for one synthetic object."""

    payload = f"vmsh-pwa-s3-smoke:{run_id}:{secrets.token_hex(16)}".encode()
    # ``run_id`` scopes cleanup and audit, but operators may intentionally
    # replay it. A per-invocation nonce prevents one smoke from overwriting and
    # deleting another invocation's probe inside that shared prefix.
    nonce = probe_nonce or secrets.token_hex(16)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", nonce):
        raise StorageSmokeError("Generated S3 probe nonce is invalid")
    key = f"probe-{nonce}.txt"
    public_url = storage.public_url(key)
    if public_url is None:
        raise StorageSmokeError("Selected storage profile has no public GET URL")

    put_attempted = False
    cleanup_error: Exception | None = None
    primary_error: Exception | None = None
    result: dict[str, object] = {
        "ok": False,
        "runId": run_id,
        "put": "pending",
        "privateRead": "pending",
        "publicGet": "pending",
        "deleteAck": "pending",
    }
    try:
        # A timeout can happen after the provider has committed PutObject, so
        # cleanup is attempted even when the await itself raises.
        put_attempted = True
        try:
            await storage.put(key, payload, "text/plain")
        except Exception as exc:
            raise _safe_provider_failure("S3 put", exc) from None
        result["put"] = "passed"
        try:
            private_payload = await storage.get(key)
        except Exception as exc:
            raise _safe_provider_failure("Private S3 read", exc) from None
        if private_payload != payload:
            raise StorageSmokeError("Private S3 read did not match the uploaded probe")
        result["privateRead"] = "passed"
        try:
            public_status, public_payload = await public_get(public_url)
        except Exception as exc:
            raise StorageSmokeError(
                f"Public S3 GET failed ({type(exc).__name__})"
            ) from None
        if public_status != 200 or public_payload != payload:
            raise StorageSmokeError("Public S3 GET did not return the uploaded probe")
        result["publicGet"] = "passed"
        result["ok"] = True
    except Exception as exc:
        primary_error = exc
        raise
    finally:
        if put_attempted:
            try:
                await storage.delete(key)
                # ObjectStorage.delete has ack semantics. The phase-0 protocol
                # does not claim a separate HEAD/not-found observation.
                result["deleteAck"] = "passed"
            except Exception as exc:  # cleanup must remain visible to the operator
                cleanup_error = _safe_provider_failure("S3 delete", exc)
        if cleanup_error is not None:
            if primary_error is not None:
                raise ExceptionGroup(
                    "S3 smoke operation and cleanup both failed",
                    [primary_error, cleanup_error],
                ) from None
            raise cleanup_error from None
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-id",
        default=None,
        help="lowercase disposable run id; generated when omitted",
    )
    return parser


def require_live_opt_in(environ: Mapping[str, str] | None = None) -> None:
    source = os.environ if environ is None else environ
    if source.get(LIVE_S3_OPT_IN) != "true":
        raise StorageConfigurationError(
            f"Live S3 smoke requires explicit {LIVE_S3_OPT_IN}=true"
        )


def verify_test_bucket_binding(
    config: StorageConfig, *, binding_path: Path = TEST_BINDING_PATH
) -> None:
    """Pin live writes to the owner-approved test endpoint and bucket identity."""

    if (
        config.adapter != "s3"
        or config.secret_source != "test"
        or not config.prefix.startswith("integration/")
        or config.bucket_name is None
        or config.endpoint_url is None
    ):
        raise StorageConfigurationError(
            "Live S3 smoke requires the isolated test profile and prefix"
        )
    if binding_path.is_symlink():
        raise StorageConfigurationError("Test S3 binding must not be a symlink")
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageConfigurationError("Cannot load pinned test S3 binding") from exc
    if not isinstance(binding, dict) or binding.get("format") != "vmsh.s3-binding/v1":
        raise StorageConfigurationError("Pinned test S3 binding format is invalid")

    endpoint_host = urlsplit(config.endpoint_url).hostname
    bucket_sha256 = hashlib.sha256(config.bucket_name.encode("utf-8")).hexdigest()
    if (
        binding.get("endpointHost") != endpoint_host
        or binding.get("bucketNameSha256") != bucket_sha256
    ):
        raise StorageConfigurationError(
            "Configured S3 target does not match the pinned disposable test bucket"
        )


async def _main_async(run_id: str) -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root="unused",
        repository_root=repository_root,
        integration_run_id=run_id,
    )
    verify_test_bucket_binding(config, binding_path=TEST_BINDING_PATH)
    storage = create_object_storage(config)
    result = await run_storage_smoke(storage, run_id=run_id)
    result["storage"] = config.safe_report()
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        require_live_opt_in()
        arguments = _parser().parse_args(argv)
        run_id = arguments.run_id or f"local-{secrets.token_hex(8)}"
        report = asyncio.run(_main_async(run_id))
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (StorageConfigurationError, StorageSmokeError, ExceptionGroup) as exc:
        # Provider exceptions may embed bucket/object URLs. Emit only the
        # stable, redacted step messages assembled above. ExceptionGroup's
        # default text hides its children, so expose their safe summaries.
        report: dict[str, object] = {"ok": False}
        if isinstance(exc, ExceptionGroup):
            report["error"] = exc.message
            report["causes"] = [
                str(child)
                if isinstance(child, (StorageConfigurationError, StorageSmokeError))
                else f"Unexpected storage smoke failure ({type(child).__name__})"
                for child in exc.exceptions
            ]
        else:
            report["error"] = str(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Unexpected storage smoke failure ({type(exc).__name__})",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
