from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pytest

from helpers.pwa.content.assets import ConvertedAsset
from vmshpwa.scripts import written_attachment_storage_smoke as smoke


class FakeStorage:
    def __init__(self, *, fail_delete: bool = False):
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_delete = fail_delete

    async def put(self, key: str, data: bytes, _content_type: str) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        if self.fail_delete:
            raise RuntimeError("secret signed cleanup URL")
        self.objects.pop(key, None)

    def public_url(self, key: str) -> str:
        return f"https://public.example.invalid/{key}"


@dataclass(frozen=True)
class FakeConfig:
    def safe_report(self):
        return {"adapter": "s3", "profile": "pwa-s3-integration"}


class FakeConverter:
    def __init__(self, _tools, *, timeout_seconds: float):
        assert timeout_seconds == 60

    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        assert payload.startswith(b"P6")
        output = b"RIFFsynthetic-written-WEBP"
        return ConvertedAsset(
            source_sha256=hashlib.sha256(payload).hexdigest(),
            output_sha256=hashlib.sha256(output).hexdigest(),
            media_type="image/webp",
            data=output,
            width=4,
            height=2,
        )


def _wire(monkeypatch, storage: FakeStorage, captured: dict[str, object]) -> None:
    config = FakeConfig()

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


@pytest.mark.asyncio
async def test_written_service_roundtrip_uses_safe_key_and_always_cleans(
    tmp_path,
    monkeypatch,
):
    storage = FakeStorage()
    captured: dict[str, object] = {}
    _wire(monkeypatch, storage, captured)

    async def public_get(url: str, maximum_bytes: int):
        key = url.removeprefix("https://public.example.invalid/")
        payload = storage.objects[key]
        assert len(payload) == maximum_bytes
        return 200, payload

    report = await smoke.run_written_attachment_storage_smoke(
        run_id="phase5-written-179",
        repository_root=tmp_path,
        environ={},
        public_get=public_get,
    )

    assert captured["runtime_profile"] == smoke.S3_TEST_RUNTIME_PROFILE
    assert captured["integration_run_id"] == "phase5-written-179"
    assert captured["verified"] == FakeConfig()
    assert report["writtenPhoto"] == {
        "put": "passed",
        "privateRead": "passed",
        "publicGet": "passed",
        "deleteAck": "passed",
        "mediaType": "image/webp",
        "byteSize": len(b"RIFFsynthetic-written-WEBP"),
        "width": 4,
        "height": 2,
        "outputSha256": hashlib.sha256(b"RIFFsynthetic-written-WEBP").hexdigest(),
        "keyShape": "sol_imgs/user_{id}/{year}/lesson_{n}/{problem}_{time}_{uuid}.webp",
    }
    assert len(storage.deleted) == 1
    assert storage.deleted[0].startswith(
        "sol_imgs/user_101/2026/lesson_41/problem-written-live_"
    )
    assert storage.objects == {}
    assert "https://" not in json.dumps(report)
    assert "sol_imgs/user_101" not in json.dumps(report)


@pytest.mark.asyncio
async def test_public_read_and_cleanup_failures_are_redacted(
    tmp_path,
    monkeypatch,
):
    storage = FakeStorage(fail_delete=True)
    captured: dict[str, object] = {}
    _wire(monkeypatch, storage, captured)

    async def fail_public_get(_url: str, _maximum_bytes: int):
        raise RuntimeError("https://private.example.invalid/key?signature=secret")

    with pytest.raises(smoke.WrittenAttachmentStorageSmokeError) as captured_error:
        await smoke.run_written_attachment_storage_smoke(
            run_id="phase5-written-failure",
            repository_root=tmp_path,
            environ={},
            public_get=fail_public_get,
        )

    message = str(captured_error.value)
    assert "roundtrip:RuntimeError" in message
    assert "cleanup:RuntimeError" in message
    assert "private.example" not in message
    assert "secret" not in message
    assert len(storage.deleted) == 1


def test_main_fails_closed_before_work_without_live_opt_in(monkeypatch, capsys):
    monkeypatch.delenv(smoke.LIVE_S3_OPT_IN, raising=False)

    async def must_not_run(**_kwargs):
        raise AssertionError("side effects must not start")

    monkeypatch.setattr(smoke, "run_written_attachment_storage_smoke", must_not_run)
    assert smoke.main(["--run-id", "phase5-written-179"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report["errorCode"].endswith("StorageConfigurationError")


def test_main_never_serializes_provider_exception_messages(monkeypatch, capsys):
    monkeypatch.setenv(smoke.LIVE_S3_OPT_IN, "true")

    async def fail(**_kwargs):
        raise RuntimeError(
            "https://private.example.invalid/integration/run/key?signature=secret"
        )

    monkeypatch.setattr(smoke, "run_written_attachment_storage_smoke", fail)
    assert smoke.main(["--run-id", "phase5-written-179"]) == 1
    serialized = capsys.readouterr().out
    assert json.loads(serialized) == {
        "errorCode": "written_attachment_smoke_RuntimeError",
        "ok": False,
    }
    assert "private.example" not in serialized
    assert "secret" not in serialized
