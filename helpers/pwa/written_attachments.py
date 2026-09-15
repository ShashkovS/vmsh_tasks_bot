"""Phase-5 image conversion and durable attachment orchestration.

The browser always uploads through aiohttp.  This service deliberately keeps
the raw source only in memory and delegates bounded re-encoding to the shared
Phase-2 converter.  The final object is written before SQLite metadata; every
controlled database failure compensates that unique object immediately.
See ``vmshpwa/dev/development-plan/09-phase-5-written-submissions.md``.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePath

from db_methods.pwa.written_submissions import (
    CreateWrittenAttachmentCommand,
    CreateWrittenAttachmentReceipt,
    PersistWrittenAttachment,
    PreparedWrittenAttachmentUpload,
    PwaWrittenSubmissionRepository,
)
from helpers.object_storage import ObjectStorage, canonical_object_key
from helpers.pwa.content.assets import (
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
)


MAX_WRITTEN_SOURCE_BYTES = 25 * 1024 * 1024
WRITTEN_IMAGE_CONVERSION_VERSION = "pwa-written-image-v1"
_OBJECT_TOKEN = re.compile(r"[0-9a-f]{32}\Z")
logger = logging.getLogger(__name__)


class WrittenAttachmentServiceError(RuntimeError):
    """A redacted orchestration failure safe for the HTTP adapter."""


class WrittenAttachmentCleanupError(WrittenAttachmentServiceError):
    """The DB operation failed and the compensating object delete also failed."""


class WrittenAttachmentService:
    """Convert one source image and attach its final WebP to a Student draft."""

    def __init__(
        self,
        *,
        converter: ContentAssetConverter | ConfiguredContentAssetConverter,
        storage: ObjectStorage,
        repository: PwaWrittenSubmissionRepository,
        clock: Callable[[], datetime] | None = None,
        object_token_factory: Callable[[], str] | None = None,
    ) -> None:
        self._converter = converter
        self._storage = storage
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._object_token_factory = object_token_factory or (lambda: uuid.uuid4().hex)

    @property
    def storage(self) -> ObjectStorage:
        return self._storage

    async def convert_and_attach(
        self,
        *,
        account_id: int,
        entry_public_id: str,
        expected_entry_version: int,
        expected_thread_version: int,
        ordinal: int,
        idempotency_key: str,
        payload: bytes,
        source_filename: str,
    ) -> CreateWrittenAttachmentReceipt:
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("attachment source must not be empty")
        if len(payload) > MAX_WRITTEN_SOURCE_BYTES:
            raise ValueError("attachment source is too large")
        filename = _safe_filename(source_filename)
        source_sha256 = hashlib.sha256(payload).hexdigest()
        command = CreateWrittenAttachmentCommand(
            account_id=account_id,
            entry_public_id=entry_public_id,
            expected_entry_version=expected_entry_version,
            expected_thread_version=expected_thread_version,
            ordinal=ordinal,
            client_filename=filename,
            source_sha256=source_sha256,
            idempotency_key=idempotency_key,
        )
        prepared = await self._repository.prepare_attachment_upload(command)
        if isinstance(prepared, CreateWrittenAttachmentReceipt):
            # Exact retries stop before conversion and object storage.
            return prepared

        converted = await self._converter.raster_to_webp(payload)
        _validate_converted(payload, source_sha256=source_sha256, converted=converted)
        object_key = self._object_key(prepared)
        await self._storage.put(object_key, converted.data, "image/webp")
        try:
            persisted = PersistWrittenAttachment(
                object_key=object_key,
                public_url=self._storage.public_url(object_key),
                output_sha256=converted.output_sha256,
                byte_size=len(converted.data),
                width=converted.width,
                height=converted.height,
            )
            receipt = await self._repository.complete_attachment_upload(
                prepared, persisted
            )
            if receipt.replayed:
                # A concurrent identical request committed another unique
                # object first. Its ledger response is authoritative; this
                # request's unreferenced object must not survive.
                await self._storage.delete(object_key)
            return receipt
        except BaseException as primary_error:
            await self._compensate(object_key, primary_error=primary_error)
            raise

    def _object_key(self, prepared: PreparedWrittenAttachmentUpload) -> str:
        token = self._object_token_factory()
        if not _OBJECT_TOKEN.fullmatch(token):
            raise WrittenAttachmentServiceError(
                "object token factory returned an invalid value"
            )
        scope = prepared.scope
        created_at = self._clock().astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return canonical_object_key(
            "sol_imgs/"
            f"user_{scope.student_user_id}/"
            f"{scope.season_year}/"
            f"lesson_{scope.lesson_number}/"
            f"{scope.problem_public_id}_{created_at}_{token}.webp"
        )

    async def _compensate(
        self, object_key: str, *, primary_error: BaseException
    ) -> None:
        try:
            # Cleanup must finish even if the request task was cancelled after
            # the provider accepted the object. The child task is bounded by
            # the storage adapter's own timeouts/retry policy.
            await asyncio.shield(self._storage.delete(object_key))
        except BaseException as cleanup_error:
            logger.error(
                "Written attachment compensation failed: primary=%s cleanup=%s",
                type(primary_error).__name__,
                type(cleanup_error).__name__,
            )
            if isinstance(primary_error, asyncio.CancelledError):
                return
            raise WrittenAttachmentCleanupError(
                "written attachment failed and object cleanup was incomplete"
            ) from primary_error


def _safe_filename(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("source filename is invalid")
    filename = PurePath(value.replace("\\", "/")).name.strip()
    if (
        not filename
        or len(filename) > 512
        or any(ord(character) < 32 for character in filename)
    ):
        raise ValueError("source filename is invalid")
    return filename


def _validate_converted(payload: bytes, *, source_sha256: str, converted) -> None:
    if converted.source_sha256 != source_sha256:
        raise WrittenAttachmentServiceError(
            "converter source hash contradicts uploaded bytes"
        )
    if converted.media_type != "image/webp":
        raise WrittenAttachmentServiceError("converter did not produce WebP")
    if (
        not converted.data
        or hashlib.sha256(converted.data).hexdigest() != converted.output_sha256
        or not 1 <= converted.width <= 1920
        or not 1 <= converted.height <= 1920
    ):
        raise WrittenAttachmentServiceError(
            "converter returned invalid final WebP metadata"
        )
    # Keep the argument in this low-level validation signature explicit: the
    # source bytes are intentionally not returned, stored, or logged.
    del payload


__all__ = [
    "MAX_WRITTEN_SOURCE_BYTES",
    "WRITTEN_IMAGE_CONVERSION_VERSION",
    "WrittenAttachmentCleanupError",
    "WrittenAttachmentService",
    "WrittenAttachmentServiceError",
]
