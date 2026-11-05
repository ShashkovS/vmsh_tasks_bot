"""Persist one reproducible PDF derivative for an exact content revision.

The renderer owns the isolated TeX process; this service owns the provider-first
object/SQLite boundary.  A failed database write may leave a harmless
content-addressed object, while a database derivative is never created before
the bytes exist.  See Phase 2 in
``vmshpwa/dev/development-plan/06-phase-2-content.md``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import PurePath
from typing import Protocol

from db_methods.pwa.content import (
    ContentConflict,
    ContentDerivativeRecord,
    ContentNotFound,
    MediaAssetRecord,
    PwaContentRepository,
)
from helpers.object_storage import ObjectStorage, content_addressed_key

from .pdf import PDF_RENDERER_VERSION, PdfDerivative, PdfDerivativeError


# This identifies the stored byte representation, not one render invocation.
# Exact source/tool provenance remains on the immutable content derivative.  A
# future change to the storage encoding (for example PDF normalization) must
# bump this constant so identical PDF bytes still share one media row/object.
PDF_STORAGE_CONVERSION_VERSION = "pwa-content-pdf-storage-v1"
PDF_STORAGE_NAMESPACE = "generated"
_PDF_MEDIA_TYPE = "application/pdf"


class PdfPersistenceError(RuntimeError):
    """A stable, redacted persistence diagnostic safe for an API response."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


class PdfRenderer(Protocol):
    async def render(self, payload: bytes, *, source_name: str) -> PdfDerivative: ...


@dataclass(frozen=True, slots=True)
class PersistedPdfDerivative:
    """The immutable derivative identity returned on creation and exact retry."""

    derivative: ContentDerivativeRecord
    object_key: str
    public_url: str | None
    source_sha256: str
    output_sha256: str
    conversion_version: str
    created: bool


class PdfPersistenceService:
    """Render, content-address, deduplicate and persist a revision PDF."""

    def __init__(
        self,
        *,
        renderer: PdfRenderer,
        storage: ObjectStorage,
        repository: PwaContentRepository,
        public_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._renderer = renderer
        self._storage = storage
        self._repository = repository
        self._public_id_factory = public_id_factory or (lambda: uuid.uuid4().hex)

    async def persist(
        self,
        *,
        revision_id: int,
        source: bytes,
        expected_source_sha256: str,
        source_name: str,
        actor_user_id: int | None,
    ) -> PersistedPdfDerivative:
        """Persist the PDF for exactly the immutable source hash supplied by SQLite."""

        if revision_id < 1:
            raise ValueError("revision_id must be positive")
        if not isinstance(source, bytes):
            raise TypeError("source must be bytes")
        source_sha256 = hashlib.sha256(source).hexdigest()
        if not _is_sha256(expected_source_sha256) or not hmac.compare_digest(
            expected_source_sha256,
            source_sha256,
        ):
            raise PdfPersistenceError(
                "pdf.source_changed",
                "The PDF source no longer matches the selected revision",
            )

        try:
            rendered = await self._renderer.render(
                source,
                source_name=_safe_source_name(source_name),
            )
        except PdfDerivativeError:
            raise
        except Exception as error:
            raise PdfPersistenceError(
                "pdf.render_failed",
                "The PDF derivative could not be rendered",
            ) from error

        conversion_version = _validate_rendered_pdf(
            rendered,
            expected_source_sha256=source_sha256,
        )
        object_key = content_addressed_key(
            PDF_STORAGE_NAMESPACE,
            rendered.data,
            "pdf",
        )
        public_url = self._public_url(object_key)

        existing = await self._get_existing(revision_id)
        if existing is not None:
            _require_exact_derivative(existing, rendered.output_sha256)
            return PersistedPdfDerivative(
                derivative=existing,
                object_key=object_key,
                public_url=public_url,
                source_sha256=source_sha256,
                output_sha256=rendered.output_sha256,
                conversion_version=conversion_version,
                created=False,
            )

        try:
            # Provider-first is deliberate.  A later database failure leaves a
            # retry-safe content-addressed orphan; database-first could expose a
            # derivative whose immutable bytes do not exist.
            await self._storage.put(object_key, rendered.data, _PDF_MEDIA_TYPE)
        except Exception as error:
            raise PdfPersistenceError(
                "pdf.storage_failed",
                "The PDF derivative could not be stored",
            ) from error

        try:
            asset = await self._repository.register_media_asset(
                public_id=self._public_id_factory(),
                sha256=rendered.output_sha256,
                storage_namespace=PDF_STORAGE_NAMESPACE,
                object_key=object_key,
                public_url=public_url,
                media_type=_PDF_MEDIA_TYPE,
                byte_size=len(rendered.data),
                width=None,
                height=None,
                source_filename=_safe_source_name(source_name),
                conversion_version=conversion_version,
                actor_user_id=actor_user_id,
            )
            _require_exact_asset(
                asset,
                output_sha256=rendered.output_sha256,
                object_key=object_key,
                byte_size=len(rendered.data),
                conversion_version=conversion_version,
            )
            derivative = await self._repository.add_derivative(
                revision_id=revision_id,
                kind="pdf",
                renderer_version=PDF_RENDERER_VERSION,
                asset_id=asset.id,
                sha256=rendered.output_sha256,
                provenance=rendered.provenance,
            )
        except ContentConflict as error:
            # A concurrent identical request can win the unique derivative
            # insert.  It is idempotent only after reading and checking the row.
            existing = await self._get_existing(revision_id)
            if existing is not None:
                _require_exact_derivative(existing, rendered.output_sha256)
                return PersistedPdfDerivative(
                    derivative=existing,
                    object_key=object_key,
                    public_url=public_url,
                    source_sha256=source_sha256,
                    output_sha256=rendered.output_sha256,
                    conversion_version=conversion_version,
                    created=False,
                )
            raise PdfPersistenceError(
                "pdf.persistence_conflict",
                "The stored PDF derivative contradicts this render",
            ) from error
        except PdfPersistenceError:
            raise
        except Exception as error:
            raise PdfPersistenceError(
                "pdf.persistence_failed",
                "The PDF derivative metadata could not be stored",
            ) from error

        _require_exact_derivative(derivative, rendered.output_sha256)
        return PersistedPdfDerivative(
            derivative=derivative,
            object_key=object_key,
            public_url=public_url,
            source_sha256=source_sha256,
            output_sha256=rendered.output_sha256,
            conversion_version=conversion_version,
            created=True,
        )

    async def _get_existing(
        self, revision_id: int
    ) -> ContentDerivativeRecord | None:
        try:
            return await self._repository.get_active_derivative(
                revision_id=revision_id,
                kind="pdf",
            )
        except ContentNotFound:
            return None
        except Exception as error:
            raise PdfPersistenceError(
                "pdf.persistence_failed",
                "The PDF derivative metadata could not be read",
            ) from error

    def _public_url(self, object_key: str) -> str | None:
        try:
            return self._storage.public_url(object_key)
        except Exception as error:
            raise PdfPersistenceError(
                "pdf.storage_failed",
                "The PDF derivative storage address could not be resolved",
            ) from error


def _validate_rendered_pdf(
    rendered: PdfDerivative,
    *,
    expected_source_sha256: str,
) -> str:
    if (
        rendered.media_type != _PDF_MEDIA_TYPE
        or not isinstance(rendered.data, bytes)
        or not rendered.data.startswith(b"%PDF-")
        or b"%%EOF" not in rendered.data[-2048:]
    ):
        raise PdfPersistenceError(
            "pdf.render_invalid",
            "The renderer returned an invalid PDF derivative",
        )
    output_sha256 = hashlib.sha256(rendered.data).hexdigest()
    if not _is_sha256(rendered.source_sha256) or not hmac.compare_digest(
        rendered.source_sha256,
        expected_source_sha256,
    ):
        raise PdfPersistenceError(
            "pdf.source_changed",
            "The renderer used bytes from a different source revision",
        )
    if not _is_sha256(rendered.output_sha256) or not hmac.compare_digest(
        rendered.output_sha256,
        output_sha256,
    ):
        raise PdfPersistenceError(
            "pdf.render_invalid",
            "The renderer returned a contradictory PDF hash",
        )
    if (
        not isinstance(rendered.provenance, Mapping)
        or rendered.provenance.get("rendererVersion") != PDF_RENDERER_VERSION
    ):
        raise PdfPersistenceError(
            "pdf.render_invalid",
            "The renderer returned incompatible PDF provenance",
        )
    try:
        json.dumps(
            rendered.provenance,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise PdfPersistenceError(
            "pdf.render_invalid",
            "The renderer returned invalid PDF provenance",
        ) from error
    return PDF_STORAGE_CONVERSION_VERSION


def _require_exact_derivative(
    derivative: ContentDerivativeRecord,
    output_sha256: str,
) -> None:
    if (
        derivative.kind != "pdf"
        or derivative.renderer_version != PDF_RENDERER_VERSION
        or not hmac.compare_digest(derivative.sha256, output_sha256)
        or derivative.content_text is not None
        or derivative.asset_id is None
    ):
        raise PdfPersistenceError(
            "pdf.derivative_conflict",
            "The selected revision already has a different PDF derivative",
        )


def _require_exact_asset(
    asset: MediaAssetRecord,
    *,
    output_sha256: str,
    object_key: str,
    byte_size: int,
    conversion_version: str,
) -> None:
    if (
        asset.storage_namespace != PDF_STORAGE_NAMESPACE
        or not hmac.compare_digest(asset.sha256, output_sha256)
        or asset.object_key != object_key
        or asset.media_type != _PDF_MEDIA_TYPE
        or asset.byte_size != byte_size
        or asset.width is not None
        or asset.height is not None
        or asset.conversion_version != conversion_version
    ):
        raise PdfPersistenceError(
            "pdf.asset_conflict",
            "The stored PDF asset contradicts the rendered bytes",
        )


def _safe_source_name(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name.strip()
    return (name or "source.tex")[:255]


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = [
    "PDF_STORAGE_NAMESPACE",
    "PDF_STORAGE_CONVERSION_VERSION",
    "PdfPersistenceError",
    "PdfPersistenceService",
    "PersistedPdfDerivative",
]
