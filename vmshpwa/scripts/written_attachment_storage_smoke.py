"""Guarded Phase-5 written-photo roundtrip in the disposable test S3.

The command composes the real written attachment service, raster converter and
S3 adapter around a synthetic in-memory repository boundary. It proves the
``sol_imgs`` key, final WebP, private/public reads and cleanup without touching
SQLite, Telegram, Google or a real Student submission.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from db_methods.pwa.written_submissions import (
    CreateWrittenAttachmentReceipt,
    PersistWrittenAttachment,
    PreparedWrittenAttachmentUpload,
    ProblemRevisionRef,
    WrittenAttachmentRecord,
    WrittenAttachmentUploadScope,
    WrittenEntryRecord,
)
from helpers.object_storage import ObjectStorage, create_object_storage
from helpers.pwa.content.assets import ContentAssetConverter, ContentAssetTools
from helpers.pwa.storage_config import S3_TEST_RUNTIME_PROFILE, load_storage_config
from helpers.pwa.written_attachments import WrittenAttachmentService
from vmshpwa.scripts.storage_smoke import (
    LIVE_S3_OPT_IN,
    TEST_BINDING_PATH,
    require_live_opt_in,
    verify_test_bucket_binding,
)

_RASTER_SOURCE = b"P6\n4 2\n255\n" + bytes(
    (index * 29) % 256 for index in range(4 * 2 * 3)
)
_CLOCK = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


class WrittenAttachmentStorageSmokeError(RuntimeError):
    """A redacted live-smoke failure safe to serialize by exception type."""


class _SmokeRepository:
    """Minimal repository witness around the real conversion/storage service."""

    def __init__(self) -> None:
        self.persisted: PersistWrittenAttachment | None = None

    async def prepare_attachment_upload(self, command):
        return PreparedWrittenAttachmentUpload(
            command=command,
            payload_sha256=hashlib.sha256(
                json.dumps(
                    command.request_payload(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            scope=WrittenAttachmentUploadScope(
                student_user_id=101,
                season_year=2026,
                lesson_number=41,
                problem_public_id="problem-written-live",
            ),
        )

    async def complete_attachment_upload(
        self,
        prepared: PreparedWrittenAttachmentUpload,
        asset: PersistWrittenAttachment,
    ) -> CreateWrittenAttachmentReceipt:
        self.persisted = asset
        attachment = WrittenAttachmentRecord(
            public_id="written-attachment-live",
            ordinal=prepared.command.ordinal,
            upload_status="stored",
            media_public_id="written-media-live",
            public_url=asset.public_url,
            media_path=(
                "/student/api/v1/thread-entries/written-entry-live/"
                "attachments/written-attachment-live/media"
            ),
            media_type="image/webp",
            width=asset.width,
            height=asset.height,
        )
        return CreateWrittenAttachmentReceipt(
            thread_public_id="written-thread-live",
            problem_public_id="problem-written-live",
            thread_status="open",
            thread_version=2,
            entry=WrittenEntryRecord(
                public_id="written-entry-live",
                author_kind="student",
                entry_kind="submission",
                state="draft",
                text=None,
                problem_revision=ProblemRevisionRef(
                    condition_revision_public_id="condition-revision-live",
                    config_version=1,
                ),
                version=2,
                client_created_at="2026-07-28T12:00:00Z",
                server_received_at="2026-07-28T12:00:00Z",
                attachments=(attachment,),
            ),
        )


async def _public_get(url: str, maximum_bytes: int) -> tuple[int, bytes]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=False) as response:
            return response.status, await response.content.read(maximum_bytes + 1)


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


async def _verify_and_cleanup(
    storage: ObjectStorage,
    asset: PersistWrittenAttachment,
    *,
    public_get: Callable[[str, int], Awaitable[tuple[int, bytes]]],
) -> dict[str, object]:
    primary_error: Exception | None = None
    cleanup_error: Exception | None = None
    private_payload = b""
    result: dict[str, object] = {
        "put": "passed",
        "privateRead": "pending",
        "publicGet": "pending",
        "deleteAck": "pending",
        "mediaType": "image/webp",
        "byteSize": asset.byte_size,
        "width": asset.width,
        "height": asset.height,
        "outputSha256": asset.output_sha256,
        "keyShape": "sol_imgs/user_{id}/{year}/lesson_{n}/{problem}_{time}_{uuid}.webp",
    }
    try:
        private_payload = await storage.get(asset.object_key)
        if (
            len(private_payload) != asset.byte_size
            or hashlib.sha256(private_payload).hexdigest() != asset.output_sha256
        ):
            raise WrittenAttachmentStorageSmokeError(
                "Private written-photo read did not match persisted metadata"
            )
        result["privateRead"] = "passed"
        if asset.public_url is None:
            raise WrittenAttachmentStorageSmokeError(
                "Written-photo test storage has no public GET URL"
            )
        status, public_payload = await public_get(asset.public_url, asset.byte_size)
        if status != 200 or public_payload != private_payload:
            raise WrittenAttachmentStorageSmokeError(
                "Public written-photo GET did not match private bytes"
            )
        result["publicGet"] = "passed"
    except Exception as error:
        primary_error = error
    finally:
        try:
            await storage.delete(asset.object_key)
            result["deleteAck"] = "passed"
        except Exception as error:
            cleanup_error = error
    if primary_error is not None or cleanup_error is not None:
        failures: list[str] = []
        if primary_error is not None:
            failures.append(f"roundtrip:{type(primary_error).__name__}")
        if cleanup_error is not None:
            failures.append(f"cleanup:{type(cleanup_error).__name__}")
        raise WrittenAttachmentStorageSmokeError(
            f"Synthetic written-photo S3 lifecycle failed ({','.join(failures)})"
        ) from None
    return result


async def run_written_attachment_storage_smoke(
    *,
    run_id: str,
    repository_root: Path,
    environ: Mapping[str, str],
    public_get: Callable[[str, int], Awaitable[tuple[int, bytes]]] = _public_get,
) -> dict[str, object]:
    """Exercise the real written-photo service against the pinned test bucket."""

    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root="unused",
        repository_root=repository_root,
        integration_run_id=run_id,
    )
    verify_test_bucket_binding(config, binding_path=TEST_BINDING_PATH)
    storage = create_object_storage(config)
    tools = ContentAssetTools.from_config(_tool_config(environ))
    repository = _SmokeRepository()
    service = WrittenAttachmentService(
        converter=ContentAssetConverter(tools, timeout_seconds=60),
        storage=storage,
        repository=repository,  # type: ignore[arg-type]
        clock=lambda: _CLOCK,
        object_token_factory=lambda: hashlib.sha256(run_id.encode("utf-8")).hexdigest()[
            :32
        ],
    )
    receipt = await service.convert_and_attach(
        account_id=1,
        entry_public_id="written-entry-live",
        expected_entry_version=1,
        expected_thread_version=1,
        ordinal=0,
        idempotency_key="00000000-0000-4000-8000-000000000179",
        payload=_RASTER_SOURCE,
        source_filename="synthetic-written.ppm",
    )
    asset = repository.persisted
    if asset is None or receipt.entry.attachments[0].public_url != asset.public_url:
        raise WrittenAttachmentStorageSmokeError(
            "Written attachment service did not preserve persisted identity"
        )
    expected_prefix = "sol_imgs/user_101/2026/lesson_41/problem-written-live_"
    if not asset.object_key.startswith(
        expected_prefix
    ) or not asset.object_key.endswith(".webp"):
        await storage.delete(asset.object_key)
        raise WrittenAttachmentStorageSmokeError(
            "Written attachment service produced an unexpected object key"
        )
    result = await _verify_and_cleanup(storage, asset, public_get=public_get)
    return {
        "schemaVersion": 1,
        "ok": True,
        "syntheticOnly": True,
        "runId": run_id,
        "storage": config.safe_report(),
        "writtenPhoto": result,
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
            f"written-{secrets.token_hex(8)}"
        )
        report = asyncio.run(
            run_written_attachment_storage_smoke(
                run_id=run_id,
                repository_root=Path(__file__).resolve().parents[2],
                environ=os.environ,
            )
        )
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errorCode": f"written_attachment_smoke_{type(error).__name__}",
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
    "LIVE_S3_OPT_IN",
    "WrittenAttachmentStorageSmokeError",
    "main",
    "run_written_attachment_storage_smoke",
]
