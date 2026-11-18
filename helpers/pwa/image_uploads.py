"""Checksum-bound image intents; docs/performance/browser-image-uploads.md.

Direct finalization deliberately uses HEAD only. Browser dimensions/format are
trusted; proxy bytes receive bounded WebP container validation, never re-encoding.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from db_methods.pwa import image_uploads as db
from helpers.object_storage import SignedWriteStorage, ObjectStorageOperationError
from helpers.pwa.content.assets import (
    ConvertedAsset,
    AssetConversionError,
    _webp_dimensions,
)
from helpers.pwa.media_observability import media_stage

MAX_PREPARED_BYTES = 20 * 1024 * 1024
UPLOAD_TTL = 600
CLAIM_TTL = 300
logger = logging.getLogger(__name__)


class ImageUploadRejected(ValueError):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def timestamp(value):
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def prepared_webp(data: bytes) -> ConvertedAsset:
    """Validate bounded static WebP/container metadata without decoding pixels."""
    if not data or len(data) > MAX_PREPARED_BYTES:
        raise ImageUploadRejected("image_upload_invalid", 422)
    try:
        width, height = _webp_dimensions(data)
    except AssetConversionError as error:
        raise ImageUploadRejected("image_upload_invalid", 422) from error
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ImageUploadRejected("image_upload_invalid", 422)
    offset, images = 12, 0
    while offset < len(data):
        if offset + 8 > len(data):
            raise ImageUploadRejected("image_upload_invalid", 422)
        kind = data[offset : offset + 4]
        length = int.from_bytes(data[offset + 4 : offset + 8], "little")
        end = offset + 8 + length + (length & 1)
        if end > len(data) or kind in {b"EXIF", b"XMP ", b"ANIM", b"ANMF"}:
            raise ImageUploadRejected("image_upload_invalid", 422)
        if kind == b"VP8X" and (length != 10 or data[offset + 8] & 0x0E):
            raise ImageUploadRejected("image_upload_invalid", 422)
        images += kind in {b"VP8 ", b"VP8L"}
        offset = end
    if images != 1:
        raise ImageUploadRejected("image_upload_invalid", 422)
    digest = hashlib.sha256(data).hexdigest()
    return ConvertedAsset(
        source_sha256=digest,
        output_sha256=digest,
        media_type="image/webp",
        data=data,
        width=width,
        height=height,
    )


class ImageUploadService:
    def __init__(self, factory, storage, *, clock=lambda: datetime.now(UTC)):
        self.factory, self.storage, self.clock = factory, storage, clock

    async def owned(self, upload_id, account_id, audience, purpose=None, context=None):
        try:
            if not isinstance(upload_id, str) or str(uuid.UUID(upload_id)) != upload_id:
                raise ValueError()
        except ValueError as error:
            raise ImageUploadRejected("image_upload_invalid", 422) from error
        record = await self.factory.run_read_async(lambda c: db.get(c, upload_id))
        if (
            record is None
            or record["account_id"] != account_id
            or record["audience"] != audience
        ):
            raise ImageUploadRejected("image_upload_not_found", 404)
        if purpose is not None and (
            record["purpose"] != purpose or record["context"] != canonical(context)
        ):
            raise ImageUploadRejected("image_upload_context_mismatch", 409)
        if record["state"] in {"deleting", "deleted"}:
            raise ImageUploadRejected("image_upload_expired", 410)
        return record

    async def prepare(self, account_id, audience, payload):
        expected = {
            "schemaVersion",
            "clientId",
            "purpose",
            "context",
            "filename",
            "sha256",
            "byteSize",
            "width",
            "height",
        }
        if (
            not isinstance(payload, dict)
            or set(payload) != expected
            or type(payload["schemaVersion"]) is not int
            or payload["schemaVersion"] != 1
        ):
            raise ImageUploadRejected("image_upload_invalid", 422)
        try:
            if str(uuid.UUID(payload["clientId"])) != payload["clientId"]:
                raise ValueError()
            if not re.fullmatch(r"[0-9a-f]{64}", payload["sha256"]):
                raise ValueError()
            if (
                not isinstance(payload["filename"], str)
                or not 1 <= len(payload["filename"]) <= 512
            ):
                raise ValueError()
            if (
                any(ord(ch) < 32 for ch in payload["filename"])
                or "/" in payload["filename"]
                or "\\" in payload["filename"]
            ):
                raise ValueError()
            for key, maximum in [
                ("byteSize", MAX_PREPARED_BYTES),
                ("width", 1920),
                ("height", 1920),
            ]:
                if type(payload[key]) is not int or not 1 <= payload[key] <= maximum:
                    raise ValueError()
        except (ValueError, TypeError, AttributeError) as error:
            raise ImageUploadRejected("image_upload_invalid", 422) from error
        now = self.clock()
        upload_id = str(uuid.uuid4())
        record = dict(
            id=upload_id,
            account_id=account_id,
            audience=audience,
            client_id=payload["clientId"],
            purpose=payload["purpose"],
            context=canonical(payload["context"]),
            fingerprint=hashlib.sha256(canonical(payload).encode()).hexdigest(),
            filename=payload["filename"],
            sha256=payload["sha256"],
            byte_size=payload["byteSize"],
            width=payload["width"],
            height=payload["height"],
            object_key=f"image-uploads/{payload['purpose']}/{uuid.uuid4().hex}.webp",
            expires_at=timestamp(now + timedelta(seconds=UPLOAD_TTL)),
            created_at=timestamp(now),
        )
        try:
            record = await self.factory.run_write_async(lambda c: db.prepare(c, record))
        except db.ImageUploadConflict as error:
            raise ImageUploadRejected("image_upload_payload_mismatch") from error
        return await self.grant(record)

    async def grant(self, record):
        if record["state"] in {"deleting", "deleted"}:
            raise ImageUploadRejected("image_upload_expired", 410)
        if record["state"] == "completed":
            return {
                "schemaVersion": 1,
                "uploadId": record["id"],
                "transport": "completed",
            }
        expires = timestamp(self.clock() + timedelta(seconds=UPLOAD_TTL))
        try:
            record = await self.factory.run_write_async(
                lambda c: db.renew(c, record["id"], expires)
            )
        except db.ImageUploadConflict as error:
            raise ImageUploadRejected("image_upload_busy") from error
        response = {
            "schemaVersion": 1,
            "uploadId": record["id"],
            "transport": "proxy",
            "expiresAt": record["expires_at"],
        }
        if (
            isinstance(self.storage, SignedWriteStorage)
            and self.storage.supports_signed_uploads
        ):
            try:
                with media_stage("upload.sign"):
                    url = await self.storage.signed_write_url(
                        record["object_key"],
                        byte_size=record["byte_size"],
                        sha256=record["sha256"],
                        expires_in=UPLOAD_TTL,
                    )
                response.update(
                    transport="s3",
                    url=url,
                    method="PUT",
                    headers={
                        "Content-Type": "image/webp",
                        "x-amz-checksum-sha256": base64.b64encode(
                            bytes.fromhex(record["sha256"])
                        ).decode("ascii"),
                    },
                )
            except ObjectStorageOperationError:
                logger.warning("Image upload signing unavailable; using proxy")
        return response

    async def finalize(
        self,
        *,
        upload_id,
        account_id,
        audience,
        purpose,
        context,
        binding,
        persist,
        payload=None,
    ):
        record = await self.owned(upload_id, account_id, audience, purpose, context)
        bound = canonical(binding)
        token = uuid.uuid4().hex
        now = self.clock()
        try:
            record = await self.factory.run_write_async(
                lambda c: db.claim(
                    c,
                    upload_id,
                    token,
                    timestamp(now + timedelta(seconds=CLAIM_TTL)),
                    timestamp(now),
                )
            )
        except db.ImageUploadConflict as error:
            raise ImageUploadRejected("image_upload_busy") from error
        if record["state"] == "completed":
            if record["binding"] != bound:
                raise ImageUploadRejected("image_upload_payload_mismatch")
            return json.loads(record["response"])
        try:
            with media_stage("upload.finalize"):
                if payload is not None:
                    verified = prepared_webp(payload)
                    if (
                        len(payload),
                        verified.output_sha256,
                        verified.width,
                        verified.height,
                    ) != (
                        record["byte_size"],
                        record["sha256"],
                        record["width"],
                        record["height"],
                    ):
                        raise ImageUploadRejected("image_upload_payload_mismatch")
                    with media_stage("storage.put"):
                        await self.storage.put(
                            record["object_key"], payload, "image/webp"
                        )
                else:
                    if not isinstance(self.storage, SignedWriteStorage):
                        raise ImageUploadRejected("image_upload_not_uploaded", 409)
                    try:
                        with media_stage("storage.head"):
                            metadata = await self.storage.head(record["object_key"])
                    except FileNotFoundError as error:
                        raise ImageUploadRejected(
                            "image_upload_not_uploaded", 409
                        ) from error
                    expected_checksum = base64.b64encode(
                        bytes.fromhex(record["sha256"])
                    ).decode("ascii")
                    if (
                        metadata.get("byteSize"),
                        metadata.get("mimeType"),
                        metadata.get("checksumSHA256"),
                    ) != (record["byte_size"], "image/webp", expected_checksum):
                        raise ImageUploadRejected(
                            "image_upload_integrity_mismatch", 422
                        )

                def saved(connection, result):
                    db.complete(connection, upload_id, token, result, bound)

                return await persist(record, saved)
        finally:
            # A committed domain callback already cleared the claim. Cancellation must
            # not strand it; failed provider cleanup remains observable in SQLite.
            await asyncio.shield(
                self.factory.run_write_async(lambda c: db.release(c, upload_id, token))
            )

    async def cleanup(self, *, limit=100):
        for _ in range(limit):
            now, token = self.clock(), uuid.uuid4().hex
            record = await self.factory.run_write_async(
                lambda c: db.claim_cleanup(
                    c,
                    timestamp(now - timedelta(hours=24)),
                    timestamp(now),
                    token,
                    timestamp(now + timedelta(seconds=CLAIM_TTL)),
                )
            )
            if record is None:
                break
            try:
                await self.storage.delete(record["object_key"])
                await self.factory.run_write_async(
                    lambda c: db.deleted(c, record["id"], token)
                )
            except ObjectStorageOperationError:
                logger.warning(
                    "Unfinished image cleanup failed; claim retained for retry"
                )
                break
