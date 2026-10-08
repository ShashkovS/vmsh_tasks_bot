from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import pytest

from db_methods.pwa.content import MediaAssetRecord
from helpers.pwa.content.asset_service import ContentAssetService
from helpers.pwa.content.assets import ConvertedAsset
from helpers.object_storage import ObjectStorageOperationError, content_addressed_key


SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 20"/>'
WEBP = b"synthetic-webp"


class FakeConverter:
    async def tikz_to_svg(self, source: str) -> ConvertedAsset:
        return ConvertedAsset(
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            output_sha256=hashlib.sha256(SVG).hexdigest(),
            media_type="image/svg+xml",
            data=SVG,
            width=10,
            height=20,
        )

    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        return ConvertedAsset(
            source_sha256=hashlib.sha256(payload).hexdigest(),
            output_sha256=hashlib.sha256(WEBP).hexdigest(),
            media_type="image/webp",
            data=WEBP,
            width=320,
            height=240,
        )


class ContradictoryConverter(FakeConverter):
    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        converted = await super().raster_to_webp(payload)
        return ConvertedAsset(
            source_sha256=converted.source_sha256,
            output_sha256="0" * 64,
            media_type=converted.media_type,
            data=converted.data,
            width=converted.width,
            height=converted.height,
        )


@dataclass
class FakeStorage:
    puts: list[tuple[str, bytes, str]] = field(default_factory=list)
    fail: bool = False

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.puts.append((key, data, content_type))
        if self.fail:
            raise ObjectStorageOperationError(
                "put",
                provider_error_type="SyntheticProviderError",
                provider_code=None,
                http_status=None,
            )

    async def get(self, key: str) -> bytes:  # pragma: no cover - protocol stub
        raise NotImplementedError

    async def delete(self, key: str) -> None:  # pragma: no cover - protocol stub
        raise NotImplementedError

    def public_url(self, key: str) -> str:
        return f"https://assets.invalid/{key}"


@dataclass
class FakeRepository:
    registrations: list[dict[str, object]] = field(default_factory=list)
    attachments: list[dict[str, object]] = field(default_factory=list)
    fail_registration_once: bool = False
    names: dict[str, MediaAssetRecord] = field(default_factory=dict)
    tikz: MediaAssetRecord | None = None

    async def resolve_content_asset_name(
        self, logical_name: str
    ) -> MediaAssetRecord | None:
        return self.names.get(logical_name.casefold())

    async def get_content_asset_name_exact(
        self, logical_name: str
    ) -> MediaAssetRecord | None:
        return self.names.get(logical_name.casefold())

    async def bind_content_asset_name(self, **values) -> bool:
        asset = MediaAssetRecord(
            id=int(values["asset_id"]),
            public_id=str(self.registrations[-1]["public_id"]),
            sha256=str(self.registrations[-1]["sha256"]),
            storage_namespace="content",
            object_key=str(self.registrations[-1]["object_key"]),
            media_type=str(self.registrations[-1]["media_type"]),
            byte_size=int(self.registrations[-1]["byte_size"]),
            conversion_version=str(self.registrations[-1]["conversion_version"]),
        )
        self.names[str(values["logical_name"]).casefold()] = asset
        return True

    async def get_cached_tikz_asset(self, **_values) -> MediaAssetRecord | None:
        return self.tikz

    async def cache_tikz_asset(self, **values) -> MediaAssetRecord:
        if self.tikz is None:
            registration = self.registrations[-1]
            self.tikz = MediaAssetRecord(
                id=int(values["asset_id"]),
                public_id=str(registration["public_id"]),
                sha256=str(registration["sha256"]),
                storage_namespace="content",
                object_key=str(registration["object_key"]),
                media_type=str(registration["media_type"]),
                byte_size=int(registration["byte_size"]),
                conversion_version=str(registration["conversion_version"]),
            )
        return self.tikz

    async def register_media_asset(self, **values) -> MediaAssetRecord:
        self.registrations.append(values)
        if self.fail_registration_once:
            self.fail_registration_once = False
            raise RuntimeError("synthetic database failure")
        return MediaAssetRecord(
            id=17,
            public_id=str(values["public_id"]),
            sha256=str(values["sha256"]),
            storage_namespace=str(values["storage_namespace"]),
            object_key=str(values["object_key"]),
            media_type=str(values["media_type"]),
            byte_size=int(values["byte_size"]),
            conversion_version=str(values["conversion_version"]),
        )

    async def attach_asset(self, **values) -> None:
        self.attachments.append(values)


def _service(storage: FakeStorage, repository: FakeRepository) -> ContentAssetService:
    return ContentAssetService(
        converter=FakeConverter(),  # type: ignore[arg-type]
        storage=storage,
        repository=repository,  # type: ignore[arg-type]
        public_id_factory=lambda: "asset-public-id",
    )


@pytest.mark.asyncio
async def test_raster_is_persisted_by_output_hash_then_attached() -> None:
    storage = FakeStorage()
    repository = FakeRepository()

    result = await _service(storage, repository).convert_and_attach_raster(
        revision_id=41,
        logical_name="diagram.heic",
        payload=b"phone-original",
        actor_user_id=9,
        ordinal=2,
        alt_text="Диаграмма",
        source_filename=r"C:\private\photos\diagram.heic",
    )

    key = content_addressed_key("content", WEBP, "webp")
    assert storage.puts == [(key, WEBP, "image/webp")]
    assert repository.registrations == [
        {
            "public_id": "asset-public-id",
            "sha256": hashlib.sha256(WEBP).hexdigest(),
            "storage_namespace": "content",
            "object_key": key,
            "public_url": f"https://assets.invalid/{key}",
            "media_type": "image/webp",
            "byte_size": len(WEBP),
            "width": 320,
            "height": 240,
            "source_filename": "diagram.heic",
            "conversion_version": "pwa-content-assets-v1",
            "actor_user_id": 9,
        }
    ]
    assert repository.attachments == [
        {
            "revision_id": 41,
            "asset_id": 17,
            "logical_name": "diagram.heic",
            "role": "figure",
            "ordinal": 2,
            "alt_text": "Диаграмма",
        }
    ]
    assert result.record.id == 17
    assert result.source_sha256 == hashlib.sha256(b"phone-original").hexdigest()


@pytest.mark.asyncio
async def test_tikz_uses_svg_key_and_tikz_role() -> None:
    storage = FakeStorage()
    repository = FakeRepository()

    await _service(storage, repository).convert_and_attach_tikz(
        revision_id=5,
        logical_name="figure-1",
        source=r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}",
        actor_user_id=None,
    )

    expected_key = content_addressed_key("content", SVG, "svg")
    assert storage.puts == [(expected_key, SVG, "image/svg+xml")]
    assert repository.attachments[0]["role"] == "tikz"
    assert repository.registrations[0]["source_filename"] is None


@pytest.mark.asyncio
async def test_storage_failure_never_creates_database_metadata() -> None:
    storage = FakeStorage(fail=True)
    repository = FakeRepository()

    with pytest.raises(ObjectStorageOperationError):
        await _service(storage, repository).convert_and_attach_raster(
            revision_id=1,
            logical_name="page",
            payload=b"original",
            actor_user_id=1,
        )

    assert repository.registrations == []
    assert repository.attachments == []


@pytest.mark.asyncio
async def test_retry_after_database_failure_reuses_the_same_object_key() -> None:
    storage = FakeStorage()
    repository = FakeRepository(fail_registration_once=True)
    service = _service(storage, repository)

    with pytest.raises(RuntimeError, match="synthetic database failure"):
        await service.convert_and_attach_raster(
            revision_id=1,
            logical_name="page",
            payload=b"original",
            actor_user_id=1,
        )
    await service.convert_and_attach_raster(
        revision_id=1,
        logical_name="page",
        payload=b"original",
        actor_user_id=1,
    )

    assert len(storage.puts) == 2
    assert storage.puts[0][0] == storage.puts[1][0]
    assert len(repository.attachments) == 1


@pytest.mark.asyncio
async def test_global_name_reuses_asset_without_converting_new_bytes() -> None:
    storage = FakeStorage()
    repository = FakeRepository()
    service = _service(storage, repository)

    first = await service.convert_and_attach_raster(
        revision_id=1,
        logical_name="Figures/Shared.PNG",
        payload=b"first",
        actor_user_id=1,
    )
    second = await service.convert_and_attach_raster(
        revision_id=2,
        logical_name="figures/shared.png",
        payload=b"different bytes are deliberately ignored",
        actor_user_id=1,
    )

    assert first.record.id == second.record.id
    assert second.reused is True
    assert len(storage.puts) == 1
    assert len(repository.registrations) == 1


@pytest.mark.asyncio
async def test_normalized_tikz_reuses_cached_svg() -> None:
    storage = FakeStorage()
    repository = FakeRepository()
    service = _service(storage, repository)

    await service.convert_and_attach_tikz(
        revision_id=1,
        logical_name="tikz-a",
        source=r"\begin{tikzpicture} \draw (0,0)--(1,1); \end{tikzpicture}",
        actor_user_id=1,
    )
    reused = await service.convert_and_attach_tikz(
        revision_id=2,
        logical_name="tikz-b",
        source="""\\begin{tikzpicture}% same picture
        \\draw (0,0)--(1,1);   \\end{tikzpicture}""",
        actor_user_id=1,
    )

    assert reused.reused is True
    assert len(storage.puts) == 1


@pytest.mark.asyncio
async def test_archive_import_resumes_a_partially_bound_alias_set() -> None:
    storage = FakeStorage()
    repository = FakeRepository()
    service = _service(storage, repository)
    await service.convert_and_attach_raster(
        revision_id=1,
        logical_name="shared.png",
        payload=b"first",
        actor_user_id=1,
    )

    record, reused = await service.import_named_figure(
        logical_names=("shared.png", "pictures/shared.png"),
        payload=b"first",
        source_kind="raster",
        source_filename="shared.png",
        actor_user_id=1,
    )

    assert reused is True
    assert repository.names["pictures/shared.png"].id == record.id
    assert len(storage.puts) == 1


@pytest.mark.asyncio
async def test_contradictory_converter_hash_is_rejected_before_side_effects() -> None:
    storage = FakeStorage()
    repository = FakeRepository()
    service = ContentAssetService(
        converter=ContradictoryConverter(),  # type: ignore[arg-type]
        storage=storage,
        repository=repository,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="hash"):
        await service.convert_and_attach_raster(
            revision_id=1,
            logical_name="page",
            payload=b"original",
            actor_user_id=1,
        )

    assert storage.puts == []
    assert repository.registrations == []
    assert repository.attachments == []


def test_conversion_version_must_be_nonempty() -> None:
    with pytest.raises(ValueError, match="conversion_version"):
        ContentAssetService(
            converter=FakeConverter(),  # type: ignore[arg-type]
            storage=FakeStorage(),
            repository=FakeRepository(),  # type: ignore[arg-type]
            conversion_version=" ",
        )
