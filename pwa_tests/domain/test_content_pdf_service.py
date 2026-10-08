from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import pytest

from db_methods.pwa.content import (
    ContentConflict,
    ContentDerivativeRecord,
    ContentNotFound,
    MediaAssetRecord,
)
from helpers.object_storage import content_addressed_key
from helpers.pwa.content.pdf import PDF_RENDERER_VERSION, PdfDerivative
from helpers.pwa.content.pdf_service import (
    PDF_STORAGE_CONVERSION_VERSION,
    PDF_STORAGE_NAMESPACE,
    PdfPersistenceError,
    PdfPersistenceService,
)


SOURCE = b"\\documentclass{article}\\begin{document}x\\end{document}"
PDF = b"%PDF-1.7\nsynthetic exact derivative\n%%EOF\n"
SOURCE_SHA256 = hashlib.sha256(SOURCE).hexdigest()
PDF_SHA256 = hashlib.sha256(PDF).hexdigest()


@dataclass
class FakeRenderer:
    calls: list[tuple[bytes, str]] = field(default_factory=list)

    async def render(self, payload: bytes, *, source_name: str) -> PdfDerivative:
        self.calls.append((payload, source_name))
        return PdfDerivative(
            source_sha256=hashlib.sha256(payload).hexdigest(),
            output_sha256=PDF_SHA256,
            media_type="application/pdf",
            data=PDF,
            provenance={
                "compilerVersion": "fixture-compiler/1",
                "rendererVersion": PDF_RENDERER_VERSION,
                "sourceSha256": hashlib.sha256(payload).hexdigest(),
                "tool": {"executable": "synthetic-pdflatex", "version": "1"},
            },
        )


@dataclass
class FakeStorage:
    puts: list[tuple[str, bytes, str]] = field(default_factory=list)
    failure: Exception | None = None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.puts.append((key, data, content_type))
        if self.failure is not None:
            raise self.failure

    async def get(self, key: str) -> bytes:  # pragma: no cover - protocol stub
        raise NotImplementedError

    async def delete(self, key: str) -> None:  # pragma: no cover - protocol stub
        raise NotImplementedError

    def public_url(self, key: str) -> str:
        return f"https://assets.invalid/{key}"


@dataclass
class FakeRepository:
    active: ContentDerivativeRecord | None = None
    registrations: list[dict[str, object]] = field(default_factory=list)
    derivatives: list[dict[str, object]] = field(default_factory=list)
    read_failure: Exception | None = None
    registration_failure: Exception | None = None
    derivative_failure: Exception | None = None
    concurrent_winner: ContentDerivativeRecord | None = None

    async def get_active_derivative(self, **values) -> ContentDerivativeRecord:
        if self.read_failure is not None:
            raise self.read_failure
        if self.active is None:
            raise ContentNotFound("fixture has no derivative")
        return self.active

    async def register_media_asset(self, **values) -> MediaAssetRecord:
        self.registrations.append(values)
        if self.registration_failure is not None:
            raise self.registration_failure
        return MediaAssetRecord(
            id=17,
            public_id=str(values["public_id"]),
            sha256=str(values["sha256"]),
            storage_namespace=str(values["storage_namespace"]),
            object_key=str(values["object_key"]),
            media_type=str(values["media_type"]),
            byte_size=int(values["byte_size"]),
            conversion_version=str(values["conversion_version"]),
            public_url=values["public_url"],
            width=values["width"],
            height=values["height"],
            source_filename=values["source_filename"],
        )

    async def add_derivative(self, **values) -> ContentDerivativeRecord:
        self.derivatives.append(values)
        if self.concurrent_winner is not None:
            self.active = self.concurrent_winner
            raise ContentConflict("synthetic unique race")
        if self.derivative_failure is not None:
            raise self.derivative_failure
        self.active = ContentDerivativeRecord(
            id=23,
            revision_id=int(values["revision_id"]),
            kind=str(values["kind"]),
            renderer_version=str(values["renderer_version"]),
            sha256=str(values["sha256"]),
            content_text=None,
            asset_id=int(values["asset_id"]),
        )
        return self.active


def _service(
    *,
    renderer: FakeRenderer | None = None,
    storage: FakeStorage | None = None,
    repository: FakeRepository | None = None,
) -> tuple[PdfPersistenceService, FakeRenderer, FakeStorage, FakeRepository]:
    selected_renderer = renderer or FakeRenderer()
    selected_storage = storage or FakeStorage()
    selected_repository = repository or FakeRepository()
    return (
        PdfPersistenceService(
            renderer=selected_renderer,
            storage=selected_storage,
            repository=selected_repository,  # type: ignore[arg-type]
            public_id_factory=lambda: "pdf-asset-public-id",
        ),
        selected_renderer,
        selected_storage,
        selected_repository,
    )


async def _persist(service: PdfPersistenceService):
    return await service.persist(
        revision_id=41,
        source=SOURCE,
        expected_source_sha256=SOURCE_SHA256,
        source_name=r"C:\private\lessons\lesson.tex",
        actor_user_id=9,
    )


@pytest.mark.asyncio
async def test_pdf_bytes_are_stored_then_registered_and_bound_to_revision() -> None:
    service, renderer, storage, repository = _service()

    result = await _persist(service)

    object_key = content_addressed_key(PDF_STORAGE_NAMESPACE, PDF, "pdf")
    assert renderer.calls == [(SOURCE, "lesson.tex")]
    assert storage.puts == [(object_key, PDF, "application/pdf")]
    assert repository.registrations[0] == {
        "public_id": "pdf-asset-public-id",
        "sha256": PDF_SHA256,
        "storage_namespace": "generated",
        "object_key": object_key,
        "public_url": f"https://assets.invalid/{object_key}",
        "media_type": "application/pdf",
        "byte_size": len(PDF),
        "width": None,
        "height": None,
        "source_filename": "lesson.tex",
        "conversion_version": result.conversion_version,
        "actor_user_id": 9,
    }
    # Storage conversion version describes the reusable byte representation;
    # source/tool provenance is retained on the revision derivative below.
    assert result.conversion_version == PDF_STORAGE_CONVERSION_VERSION
    assert repository.derivatives == [
        {
            "revision_id": 41,
            "kind": "pdf",
            "renderer_version": PDF_RENDERER_VERSION,
            "asset_id": 17,
            "sha256": PDF_SHA256,
            "provenance": {
                "compilerVersion": "fixture-compiler/1",
                "rendererVersion": PDF_RENDERER_VERSION,
                "sourceSha256": SOURCE_SHA256,
                "tool": {"executable": "synthetic-pdflatex", "version": "1"},
            },
        }
    ]
    assert result.created is True
    assert result.derivative.asset_id == 17


@pytest.mark.asyncio
async def test_exact_retry_reads_and_verifies_without_duplicate_side_effects() -> None:
    service, renderer, storage, repository = _service()

    first = await _persist(service)
    second = await _persist(service)

    assert first.created is True
    assert second.created is False
    assert second.derivative == first.derivative
    assert len(renderer.calls) == 2
    assert len(storage.puts) == 1
    assert len(repository.registrations) == 1
    assert len(repository.derivatives) == 1


@pytest.mark.asyncio
async def test_storage_failure_creates_no_database_metadata_and_is_redacted() -> None:
    storage = FakeStorage(failure=RuntimeError("secret provider URL and key"))
    service, _, _, repository = _service(storage=storage)

    with pytest.raises(PdfPersistenceError) as captured:
        await _persist(service)

    assert captured.value.code == "pdf.storage_failed"
    assert "secret" not in str(captured.value)
    assert repository.registrations == []
    assert repository.derivatives == []
    assert repository.active is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["registration", "derivative"])
async def test_database_failure_leaves_no_false_derivative_and_is_redacted(
    failure_point: str,
) -> None:
    repository = FakeRepository()
    failure = RuntimeError("secret sqlite payload and local path")
    if failure_point == "registration":
        repository.registration_failure = failure
    else:
        repository.derivative_failure = failure
    service, _, storage, _ = _service(repository=repository)

    with pytest.raises(PdfPersistenceError) as captured:
        await _persist(service)

    assert captured.value.code == "pdf.persistence_failed"
    assert "secret" not in str(captured.value)
    assert len(storage.puts) == 1
    assert repository.active is None
    assert len(repository.derivatives) == (
        0 if failure_point == "registration" else 1
    )


@pytest.mark.asyncio
async def test_retry_after_database_failure_converges_on_same_object_key() -> None:
    repository = FakeRepository(
        derivative_failure=RuntimeError("synthetic interrupted transaction")
    )
    service, _, storage, _ = _service(repository=repository)

    with pytest.raises(PdfPersistenceError):
        await _persist(service)
    repository.derivative_failure = None
    result = await _persist(service)

    assert result.created is True
    assert len(storage.puts) == 2
    assert storage.puts[0][0] == storage.puts[1][0]
    assert len(repository.registrations) == 2
    assert repository.registrations[0]["object_key"] == (
        repository.registrations[1]["object_key"]
    )
    assert repository.active == result.derivative


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("renderer_version", "sha256"),
    [
        ("older-renderer/9", PDF_SHA256),
        (PDF_RENDERER_VERSION, "0" * 64),
    ],
)
async def test_contradictory_existing_derivative_fails_before_storage(
    renderer_version: str,
    sha256: str,
) -> None:
    repository = FakeRepository(
        active=ContentDerivativeRecord(
            id=2,
            revision_id=41,
            kind="pdf",
            renderer_version=renderer_version,
            sha256=sha256,
            content_text=None,
            asset_id=3,
        )
    )
    service, _, storage, _ = _service(repository=repository)

    with pytest.raises(PdfPersistenceError) as captured:
        await _persist(service)

    assert captured.value.code == "pdf.derivative_conflict"
    assert storage.puts == []
    assert repository.registrations == []
    assert repository.derivatives == []


@pytest.mark.asyncio
async def test_concurrent_identical_insert_is_verified_as_an_exact_retry() -> None:
    winner = ContentDerivativeRecord(
        id=99,
        revision_id=41,
        kind="pdf",
        renderer_version=PDF_RENDERER_VERSION,
        sha256=PDF_SHA256,
        content_text=None,
        asset_id=17,
    )
    repository = FakeRepository(concurrent_winner=winner)
    service, _, storage, _ = _service(repository=repository)

    result = await _persist(service)

    assert result.created is False
    assert result.derivative == winner
    assert len(storage.puts) == 1
    assert len(repository.registrations) == 1
    assert len(repository.derivatives) == 1


@pytest.mark.asyncio
async def test_source_hash_mismatch_fails_before_render_and_side_effects() -> None:
    service, renderer, storage, repository = _service()

    with pytest.raises(PdfPersistenceError) as captured:
        await service.persist(
            revision_id=41,
            source=SOURCE,
            expected_source_sha256="0" * 64,
            source_name="lesson.tex",
            actor_user_id=9,
        )

    assert captured.value.code == "pdf.source_changed"
    assert renderer.calls == []
    assert storage.puts == []
    assert repository.registrations == []
    assert repository.derivatives == []
