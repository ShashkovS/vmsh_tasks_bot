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

from db_methods.pwa.content import (
    ContentConflict,
    MediaAssetRecord,
    PwaContentRepository,
)
from helpers.object_storage import ObjectStorage, content_addressed_key
from models.pwa.content_asset_names import (
    TIKZ_NORMALIZATION_VERSION,
    tikz_source_sha256,
)

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
    reused: bool = False


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
        normalized_sha256 = tikz_source_sha256(source)
        cached = await self._repository.get_cached_tikz_asset(
            normalized_sha256=normalized_sha256,
            normalization_version=TIKZ_NORMALIZATION_VERSION,
            conversion_version=self._conversion_version,
        )
        if cached is not None:
            return await self._attach_record(
                record=cached,
                source_sha256=normalized_sha256,
                reused=True,
                revision_id=revision_id,
                logical_name=logical_name,
                role="tikz",
                expected_revision_version=expected_revision_version,
                ordinal=ordinal,
                alt_text=alt_text,
            )
        converted = await self._converter.tikz_to_svg(source)
        record = await self._persist_converted(
            converted=converted,
            extension="svg",
            actor_user_id=actor_user_id,
            source_filename=None,
        )
        winner = await self._repository.cache_tikz_asset(
            normalized_sha256=normalized_sha256,
            normalization_version=TIKZ_NORMALIZATION_VERSION,
            conversion_version=self._conversion_version,
            source_sha256=converted.source_sha256,
            asset_id=record.id,
            actor_user_id=actor_user_id,
        )
        return await self._attach_record(
            record=winner,
            source_sha256=converted.source_sha256,
            reused=winner.id != record.id,
            revision_id=revision_id,
            logical_name=logical_name,
            role="tikz",
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
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
        reused = await self._reuse_named_figure(
            revision_id=revision_id,
            logical_name=logical_name,
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
        )
        if reused is not None:
            return reused
        converted = await self._converter.raster_to_webp(payload)
        return await self._persist_bind_and_attach_figure(
            converted=converted,
            extension="webp",
            revision_id=revision_id,
            logical_name=logical_name,
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
        reused = await self._reuse_named_figure(
            revision_id=revision_id,
            logical_name=logical_name,
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
        )
        if reused is not None:
            return reused
        converted = await self._converter.svg_to_svg(payload)
        return await self._persist_bind_and_attach_figure(
            converted=converted,
            extension="svg",
            revision_id=revision_id,
            logical_name=logical_name,
            actor_user_id=actor_user_id,
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
            source_filename=_safe_filename(source_filename),
        )

    async def resolve_and_attach_figure(
        self,
        *,
        revision_id: int,
        logical_name: str,
        expected_revision_version: int,
        ordinal: int = 0,
        alt_text: str | None = None,
    ) -> PersistedContentAsset | None:
        """Attach a globally known figure without accepting upload bytes."""

        return await self._reuse_named_figure(
            revision_id=revision_id,
            logical_name=logical_name,
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
        )

    async def resolve_and_attach_tikz(
        self,
        *,
        revision_id: int,
        logical_name: str,
        source: str,
        expected_revision_version: int,
        ordinal: int = 0,
        alt_text: str | None = None,
    ) -> PersistedContentAsset | None:
        """Attach a cached TikZ SVG without invoking the TeX toolchain."""

        normalized_sha256 = tikz_source_sha256(source)
        cached = await self._repository.get_cached_tikz_asset(
            normalized_sha256=normalized_sha256,
            normalization_version=TIKZ_NORMALIZATION_VERSION,
            conversion_version=self._conversion_version,
        )
        if cached is None:
            return None
        return await self._attach_record(
            record=cached,
            source_sha256=normalized_sha256,
            reused=True,
            revision_id=revision_id,
            logical_name=logical_name,
            role="tikz",
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
        )

    async def import_named_figure(
        self,
        *,
        logical_names: tuple[str, ...],
        payload: bytes,
        source_kind: str,
        source_filename: str,
        actor_user_id: int | None,
    ) -> tuple[MediaAssetRecord, bool]:
        """Convert and bind an archive figure without creating a revision link."""

        if not logical_names:
            raise ValueError("archive import requires at least one logical name")
        existing_records = [
            record
            for name in logical_names
            if (record := await self._repository.get_content_asset_name_exact(name))
            is not None
        ]
        if existing_records:
            winner = existing_records[0]
            if any(record.id != winner.id for record in existing_records[1:]):
                raise ContentConflict("archive aliases resolve to different assets")
            reused = True
        else:
            if source_kind == "pdf":
                converted = await self._converter.pdf_to_svg(payload)
                extension = "svg"
            elif source_kind == "svg":
                converted = await self._converter.svg_to_svg(payload)
                extension = "svg"
            elif source_kind == "raster":
                converted = await self._converter.raster_to_webp(payload)
                extension = "webp"
            else:
                raise ValueError("archive source kind is invalid")
            winner = await self._persist_converted(
                converted=converted,
                extension=extension,
                actor_user_id=actor_user_id,
                source_filename=_safe_filename(source_filename),
            )
            reused = False
        for logical_name in logical_names:
            try:
                await self._repository.bind_content_asset_name(
                    logical_name=logical_name,
                    asset_id=winner.id,
                    origin="archive_import",
                    actor_user_id=actor_user_id,
                )
            except ContentConflict:
                existing = await self._repository.resolve_content_asset_name(
                    logical_name
                )
                if existing is None or existing.id != winner.id:
                    raise
        return winner, reused

    async def _reuse_named_figure(
        self,
        *,
        revision_id: int,
        logical_name: str,
        expected_revision_version: int | None,
        ordinal: int,
        alt_text: str | None,
    ) -> PersistedContentAsset | None:
        record = await self._repository.resolve_content_asset_name(logical_name)
        if record is None:
            return None
        return await self._attach_record(
            record=record,
            source_sha256=record.sha256,
            reused=True,
            revision_id=revision_id,
            logical_name=logical_name,
            role="figure",
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
        )

    async def _persist_bind_and_attach_figure(
        self,
        *,
        converted: ConvertedAsset,
        extension: str,
        revision_id: int,
        logical_name: str,
        actor_user_id: int | None,
        expected_revision_version: int | None,
        ordinal: int,
        alt_text: str | None,
        source_filename: str | None,
    ) -> PersistedContentAsset:
        record = await self._persist_converted(
            converted=converted,
            extension=extension,
            actor_user_id=actor_user_id,
            source_filename=source_filename,
        )
        winner = record
        reused = False
        try:
            await self._repository.bind_content_asset_name(
                logical_name=logical_name,
                asset_id=record.id,
                origin="upload",
                actor_user_id=actor_user_id,
            )
        except ContentConflict:
            existing = await self._repository.resolve_content_asset_name(logical_name)
            if existing is None:
                raise
            winner = existing
            reused = winner.id != record.id
        return await self._attach_record(
            record=winner,
            source_sha256=converted.source_sha256,
            reused=reused,
            revision_id=revision_id,
            logical_name=logical_name,
            role="figure",
            expected_revision_version=expected_revision_version,
            ordinal=ordinal,
            alt_text=alt_text,
        )

    async def _persist_converted(
        self,
        *,
        converted: ConvertedAsset,
        extension: str,
        actor_user_id: int | None,
        source_filename: str | None,
    ) -> MediaAssetRecord:
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
        return await self._repository.register_media_asset(
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

    async def _attach_record(
        self,
        *,
        record: MediaAssetRecord,
        source_sha256: str,
        reused: bool,
        revision_id: int,
        logical_name: str,
        role: str,
        expected_revision_version: int | None,
        ordinal: int,
        alt_text: str | None,
    ) -> PersistedContentAsset:
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
            source_sha256=source_sha256,
            output_sha256=record.sha256,
            revision_version=revision_version,
            attachment_created=attachment_created,
            reused=reused or not attachment_created,
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
