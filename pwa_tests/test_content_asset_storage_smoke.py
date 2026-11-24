from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pytest

from helpers.pwa.content.assets import ConvertedAsset
from vmshpwa.scripts import content_asset_storage_smoke as smoke


def _asset(name: str, media_type: str, data: bytes) -> smoke.AssetProbe:
    digest = hashlib.sha256(data).hexdigest()
    return smoke.AssetProbe(
        name=name,
        extension="svg" if media_type == "image/svg+xml" else "webp",
        asset=ConvertedAsset(
            source_sha256="a" * 64,
            output_sha256=digest,
            media_type=media_type,
            data=data,
            width=179,
            height=97,
        ),
    )


class FakeStorage:
    def __init__(self, *, fail_get: bool = False, fail_delete: bool = False):
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_get = fail_get
        self.fail_delete = fail_delete

    async def put(self, key: str, data: bytes, _content_type: str) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        if self.fail_get:
            raise RuntimeError("secret provider URL https://bucket.example/key")
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        if self.fail_delete:
            raise RuntimeError("secret signed cleanup URL")
        self.objects.pop(key, None)

    def public_url(self, key: str) -> str:
        return f"https://public.example.invalid/{key}"


@pytest.mark.asyncio
async def test_converted_asset_roundtrip_checks_both_reads_and_always_deletes():
    storage = FakeStorage()
    probe = _asset("tikz-svg", "image/svg+xml", b"<svg>synthetic</svg>")

    async def public_get(_url: str, maximum: int) -> tuple[int, bytes]:
        assert maximum == len(probe.asset.data)
        return 200, probe.asset.data

    report = await smoke.roundtrip_asset(storage, probe, public_get=public_get)

    assert report["put"] == "passed"
    assert report["privateRead"] == "passed"
    assert report["publicGet"] == "passed"
    assert report["deleteAck"] == "passed"
    assert len(storage.deleted) == 1
    assert storage.objects == {}
    assert "https://" not in json.dumps(report)


@pytest.mark.asyncio
async def test_private_read_failure_still_cleans_and_redacts_provider_message():
    storage = FakeStorage(fail_get=True)
    probe = _asset("raster-webp", "image/webp", b"RIFFsyntheticWEBP")

    async def unused_public_get(_url: str, _maximum: int):
        raise AssertionError("public GET must not run after private read failure")

    with pytest.raises(smoke.StorageSmokeError) as captured:
        await smoke.roundtrip_asset(
            storage,
            probe,
            public_get=unused_public_get,
        )

    assert storage.objects == {}
    assert len(storage.deleted) == 1
    assert "bucket.example" not in str(captured.value)
    assert "RuntimeError" in str(captured.value)


@pytest.mark.asyncio
async def test_primary_and_cleanup_failure_are_both_visible_without_secrets():
    storage = FakeStorage(fail_get=True, fail_delete=True)
    probe = _asset("raster-webp", "image/webp", b"RIFFsyntheticWEBP")

    async def unused_public_get(_url: str, _maximum: int):
        raise AssertionError

    with pytest.raises(smoke.StorageSmokeError) as captured:
        await smoke.roundtrip_asset(
            storage,
            probe,
            public_get=unused_public_get,
        )

    message = str(captured.value)
    assert "roundtrip:RuntimeError" in message
    assert "cleanup:RuntimeError" in message
    assert "signed" not in message
    assert len(storage.deleted) == 1


@pytest.mark.asyncio
async def test_contradictory_converter_hash_is_rejected_before_s3_write():
    storage = FakeStorage()
    valid = _asset("tikz-svg", "image/svg+xml", b"<svg/>synthetic")
    probe = smoke.AssetProbe(
        name=valid.name,
        extension=valid.extension,
        asset=ConvertedAsset(
            source_sha256=valid.asset.source_sha256,
            output_sha256="0" * 64,
            media_type=valid.asset.media_type,
            data=valid.asset.data,
            width=valid.asset.width,
            height=valid.asset.height,
        ),
    )

    async def unused_public_get(_url: str, _maximum: int):
        raise AssertionError

    with pytest.raises(smoke.StorageSmokeError, match="hash"):
        await smoke.roundtrip_asset(
            storage,
            probe,
            public_get=unused_public_get,
        )
    assert storage.objects == {}
    assert storage.deleted == []


@dataclass(frozen=True)
class FakeConfig:
    def safe_report(self):
        return {"adapter": "s3", "profile": "pwa-s3-integration"}


class FakeConverter:
    def __init__(self, _tools, *, timeout_seconds: float):
        assert timeout_seconds == 60

    async def tikz_to_svg(self, source: str) -> ConvertedAsset:
        assert "tikzpicture" in source
        return _asset("tikz-svg", "image/svg+xml", b"<svg/>synthetic").asset

    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        assert payload.startswith(b"P6")
        return _asset("raster-webp", "image/webp", b"RIFFsyntheticWEBP").asset


@pytest.mark.asyncio
async def test_orchestrator_uses_pinned_profile_and_two_synthetic_assets(
    tmp_path,
    monkeypatch,
):
    config = FakeConfig()
    storage = FakeStorage()
    captured: dict[str, object] = {}

    def fake_load_storage_config(**kwargs):
        captured.update(kwargs)
        return config

    monkeypatch.setattr(smoke, "load_storage_config", fake_load_storage_config)
    monkeypatch.setattr(
        smoke,
        "verify_test_bucket_binding",
        lambda selected, **_kwargs: captured.setdefault("verified", selected),
    )
    monkeypatch.setattr(
        smoke.ContentAssetTools, "from_config", lambda _config: object()
    )
    monkeypatch.setattr(smoke, "ContentAssetConverter", FakeConverter)
    monkeypatch.setattr(smoke, "create_object_storage", lambda selected: storage)

    async def public_get(url: str, maximum_bytes: int):
        key = url.removeprefix("https://public.example.invalid/")
        payload = storage.objects[key]
        assert len(payload) == maximum_bytes
        return 200, payload

    report = await smoke.run_content_asset_storage_smoke(
        run_id="phase2-assets-179",
        repository_root=tmp_path,
        environ={},
        public_get=public_get,
    )

    assert captured["runtime_profile"] == smoke.S3_TEST_RUNTIME_PROFILE
    assert captured["integration_run_id"] == "phase2-assets-179"
    assert captured["verified"] is config
    assert [asset["name"] for asset in report["assets"]] == [
        "tikz-svg",
        "raster-webp",
    ]
    assert all(asset["deleteAck"] == "passed" for asset in report["assets"])
    assert storage.objects == {}


def test_main_fails_closed_before_work_without_live_opt_in(monkeypatch, capsys):
    monkeypatch.delenv(smoke.LIVE_S3_OPT_IN, raising=False)

    async def must_not_run(**_kwargs):
        raise AssertionError("side effects must not start")

    monkeypatch.setattr(smoke, "run_content_asset_storage_smoke", must_not_run)
    assert smoke.main(["--run-id", "phase2-assets-179"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report["errorCode"].endswith("StorageConfigurationError")


def test_main_does_not_serialize_exception_messages(monkeypatch, capsys):
    monkeypatch.setenv(smoke.LIVE_S3_OPT_IN, "true")

    async def fail(**_kwargs):
        raise RuntimeError(
            "https://private.example.invalid/integration/run/key?signature=secret"
        )

    monkeypatch.setattr(smoke, "run_content_asset_storage_smoke", fail)
    assert smoke.main(["--run-id", "phase2-assets-179"]) == 1
    serialized = capsys.readouterr().out
    report = json.loads(serialized)
    assert report == {
        "errorCode": "content_asset_smoke_RuntimeError",
        "ok": False,
    }
    assert "private.example" not in serialized
    assert "secret" not in serialized
