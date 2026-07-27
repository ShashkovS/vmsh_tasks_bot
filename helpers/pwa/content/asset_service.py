"""Persist converted Phase-2 assets through the shared storage boundary.

Conversion is deliberately separate from persistence.  This service joins the
bounded converters from :mod:`helpers.pwa.content.assets`, the existing object
storage adapter and the append-only content repository.  See Phase 2 in
``vmshpwa/dev/development-plan/06-phase-2-content.md``.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePath

from db_methods.pwa.content import MediaAssetRecord, PwaContentRepository
from helpers.object_storage import ObjectStorage, content_addressed_key

from .assets import (
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
    ConvertedAsset,
)


_CONVERSION_VERSION = "pwa-content-assets-v1"


@dataclass(frozen=True, slots=True)
class PersistedContentAsset:
    """The immutable asset record plus its source/output provenance."""

    record: MediaAssetRecord
    source_sha256: str
    output_sha256: str
    revision_version: int | None = None
    attachment_created: bool = True


class ContentAssetService:
    """Convert, deduplicate, persist and attach generated content media."""

    def __init__(
        self,
        *,
        converter: ContentAssetConverter | ConfiguredContentAssetConverter,
        storage: ObjectStorage,
        repository: PwaContentRepository,
        conversion_version: str = _CONVERSION_VERSION,
        public_id_factory: Callable[[], str] | None = None,
    ) -> None:
        normalized_version = conversion_version.strip()
        if not normalized_version:
            raise ValueError("conversion_version must not be empty")
        self._converter = converter
        self._storage = storage
        self._repository = repository
        self._conversion_version = normalized_version
        self._public_id_factory = public_id_factory or (lambda: uuid.uuid4().hex)

    @property
    def storage(self) -> ObjectStorage:
        """Expose the same adapter for the local immutable-media read route."""

        return self._storage

    async def convert_and_attach_tikz(
        self,
        *,
        revision_id: int,
        logical_name: str,
        source: str,
        actor_user_id: int | None,
        expected_revision_version: int | None = None,
        ordinal: int = 0,
        alt_text: str | None = None,
    ) -> PersistedContentAsset:
        converted = await self._converter.tikz_to_svg(source)
        return await self._persist_and_attach(
            converted=converted,
            extension="svg",
            revision_id=revision_id,
            logical_name=logical_name,
            role="tikz",
            actor_user_id=actor_user_id,
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
            source_filename=None,
        )

    async def convert_and_attach_raster(
        self,
        *,
        revision_id: int,
        logical_name: str,
        payload: bytes,
        actor_user_id: int | None,
        expected_revision_version: int | None = None,
        ordinal: int = 0,
        alt_text: str | None = None,
        source_filename: str | None = None,
    ) -> PersistedContentAsset:
        converted = await self._converter.raster_to_webp(payload)
        return await self._persist_and_attach(
            converted=converted,
            extension="webp",
            revision_id=revision_id,
            logical_name=logical_name,
            role="figure",
            actor_user_id=actor_user_id,
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
            source_filename=_safe_filename(source_filename),
        )

    async def sanitize_and_attach_svg(
        self,
        *,
        revision_id: int,
        logical_name: str,
        payload: bytes,
        actor_user_id: int | None,
        expected_revision_version: int | None = None,
        ordinal: int = 0,
        alt_text: str | None = None,
        source_filename: str | None = None,
    ) -> PersistedContentAsset:
        converted = await self._converter.svg_to_svg(payload)
        return await self._persist_and_attach(
            converted=converted,
            extension="svg",
            revision_id=revision_id,
            logical_name=logical_name,
            role="figure",
            actor_user_id=actor_user_id,
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
            source_filename=_safe_filename(source_filename),
        )

    async def _persist_and_attach(
        self,
        *,
        converted: ConvertedAsset,
        extension: str,
        revision_id: int,
        logical_name: str,
        role: str,
        actor_user_id: int | None,
        expected_revision_version: int | None,
        ordinal: int,
        alt_text: str | None,
        source_filename: str | None,
    ) -> PersistedContentAsset:
        if hashlib.sha256(converted.data).hexdigest() != converted.output_sha256:
            # The output hash identifies both the object key and SQLite row.
            # Refuse contradictory converter metadata before either side effect.
            raise ValueError("converted asset hash does not match its bytes")
        object_key = content_addressed_key("content", converted.data, extension)

        # The provider write comes first.  A database failure may leave one
        # harmless content-addressed object, while the reverse order could
        # publish a metadata row whose bytes do not exist.  Retrying converges
        # on the same key and repository deduplication row.
        await self._storage.put(object_key, converted.data, converted.media_type)
        record = await self._repository.register_media_asset(
            public_id=self._public_id_factory(),
            sha256=converted.output_sha256,
            storage_namespace="content",
            object_key=object_key,
            public_url=self._storage.public_url(object_key),
            media_type=converted.media_type,
            byte_size=len(converted.data),
            width=converted.width,
            height=converted.height,
            source_filename=source_filename,
            conversion_version=self._conversion_version,
            actor_user_id=actor_user_id,
        )
        if expected_revision_version is None:
            await self._repository.attach_asset(
                revision_id=revision_id,
                asset_id=record.id,
                logical_name=logical_name,
                role=role,
                ordinal=ordinal,
                alt_text=alt_text,
            )
            revision_version = None
            attachment_created = True
        else:
            revision_version, attachment_created = (
                await self._repository.attach_asset_to_uploaded_revision(
                    revision_id=revision_id,
                    expected_revision_version=expected_revision_version,
                    asset_id=record.id,
                    logical_name=logical_name,
                    role=role,
                    ordinal=ordinal,
                    alt_text=alt_text,
                )
            )
        return PersistedContentAsset(
            record=record,
            source_sha256=converted.source_sha256,
            output_sha256=converted.output_sha256,
            revision_version=revision_version,
            attachment_created=attachment_created,
        )


def _safe_filename(value: str | None) -> str | None:
    if value is None:
        return None
    filename = PurePath(value.replace("\\", "/")).name.strip()
    if not filename:
        return None
    # A source label is diagnostics metadata, never a filesystem path.
    return filename[:255]


__all__ = ["ContentAssetService", "PersistedContentAsset"]
