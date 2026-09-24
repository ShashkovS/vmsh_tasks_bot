from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

import helpers.object_storage as storage_module
import helpers.pwa.storage_config as storage_config_module
import vmshpwa.scripts.storage_smoke as storage_smoke_module
from helpers.object_storage import (
    LocalObjectStorage,
    ObjectStorageOperationError,
    S3ObjectStorage,
    StoragePathError,
    canonical_object_key,
    content_addressed_key,
    create_object_storage,
)
from helpers.pwa.storage_config import (
    S3_PRODUCTION_RUNTIME_PROFILE,
    S3_TEST_RUNTIME_PROFILE,
    StorageConfig,
    StorageConfigurationError,
    load_storage_config,
)
from vmshpwa.scripts.storage_smoke import (
    LIVE_S3_OPT_IN,
    StorageSmokeError,
    require_live_opt_in,
    run_storage_smoke,
    verify_test_bucket_binding,
)


VALID_S3_DOCUMENT = {
    "s3_url": "https://fsn1.your-objectstorage.com",
    "s3_bucket_name": "vmsh-test-bucket",
    "s3_region": "fsn1",
    "s3_access_key": "synthetic-access-key",
    "s3_secret_key": "synthetic-secret-key",
    "s3_prefix": "production-media",
    "s3_public_base_url": "https://media.example.test",
}


def _write_secret_document(root: Path, source: str, document: dict) -> Path:
    directory = root / ("creds_test" if source == "test" else "creds_prod")
    directory.mkdir(parents=True)
    filename = (
        "vmsh_bot_config_test.json" if source == "test" else "vmsh_bot_config_prod.json"
    )
    path = directory / filename
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/absolute",
        "../outside",
        "a/../outside",
        "a/./b",
        "a//b",
        "a/",
        "a\\b",
        "a\x00b",
        "a\nb",
        "a\x7fb",
        "a\u0085b",
        "x" * 1025,
    ],
)
def test_object_key_rejects_noncanonical_or_unsafe_values(key):
    with pytest.raises(StoragePathError):
        canonical_object_key(key)


def test_object_key_rejects_non_utf8_surrogate():
    with pytest.raises(StoragePathError, match="UTF-8"):
        canonical_object_key("bad-\ud800-key")


def test_content_addressed_key_is_stable_and_namespaced():
    first = content_addressed_key("content", b"same bytes", ".SVG")
    second = content_addressed_key("content", b"same bytes", "svg")
    changed = content_addressed_key("content", b"other bytes", "svg")

    assert first == second
    assert first.startswith("content/sha256/")
    assert first.endswith(".svg")
    assert changed != first


@pytest.mark.parametrize("namespace", ["", "../content", "Content", "a/b"])
def test_content_addressed_key_rejects_unsafe_namespace(namespace):
    with pytest.raises(StoragePathError):
        content_addressed_key(namespace, b"bytes", "svg")


@pytest.mark.asyncio
async def test_filesystem_storage_contract_and_atomic_replace(tmp_path):
    storage = LocalObjectStorage(tmp_path / "media")
    key = "content/sha256/ab/cd/object.svg"

    await storage.put(key, b"first", "image/svg+xml")
    assert await storage.get(key) == b"first"
    await storage.put(key, b"second", "image/svg+xml")
    assert await storage.get(key) == b"second"
    assert storage.public_url(key) is None
    await storage.delete(key)
    await storage.delete(key)
    with pytest.raises(FileNotFoundError):
        await storage.get(key)


@pytest.mark.asyncio
async def test_filesystem_failed_replace_preserves_previous_object(
    tmp_path, monkeypatch
):
    storage = LocalObjectStorage(tmp_path / "media")
    await storage.put("draft/photo.webp", b"previous", "image/webp")

    def fail_replace(*_args, **_kwargs):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(storage_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        await storage.put("draft/photo.webp", b"new", "image/webp")

    assert await storage.get("draft/photo.webp") == b"previous"
    assert list((tmp_path / "media" / "draft").glob(".vmsh-object-*.tmp")) == []


@pytest.mark.asyncio
async def test_filesystem_storage_rejects_parent_symlink_escape(tmp_path):
    root = tmp_path / "media"
    outside = tmp_path / "outside"
    outside.mkdir()
    storage = LocalObjectStorage(root)
    (root / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(StoragePathError):
        await storage.put("escape/object.txt", b"no", "text/plain")
    assert not (outside / "object.txt").exists()


@pytest.mark.asyncio
async def test_filesystem_storage_never_follows_object_symlink(tmp_path):
    root = tmp_path / "media"
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"private")
    storage = LocalObjectStorage(root)
    (root / "object.txt").symlink_to(outside)

    with pytest.raises(StoragePathError):
        await storage.get("object.txt")
    with pytest.raises(StoragePathError):
        await storage.put("object.txt", b"overwrite", "text/plain")
    with pytest.raises(StoragePathError):
        await storage.delete("object.txt")
    assert outside.read_bytes() == b"private"


def test_filesystem_storage_rejects_symlink_root(tmp_path):
    actual_root = tmp_path / "actual"
    actual_root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual_root, target_is_directory=True)

    with pytest.raises(StoragePathError):
        LocalObjectStorage(alias)


def test_filesystem_constructor_closes_validation_descriptor(tmp_path, monkeypatch):
    root = tmp_path / "media"
    root.mkdir()
    real_open = storage_module.os.open
    real_close = storage_module.os.close
    descriptors: set[int] = set()

    def recording_open(path, flags, *args, **kwargs):
        descriptor = real_open(path, flags, *args, **kwargs)
        if Path(path) == root:
            descriptors.add(descriptor)
        return descriptor

    def recording_close(descriptor):
        descriptors.discard(descriptor)
        return real_close(descriptor)

    monkeypatch.setattr(storage_module.os, "open", recording_open)
    monkeypatch.setattr(storage_module.os, "close", recording_close)
    LocalObjectStorage(root)
    assert descriptors == set()


@pytest.mark.asyncio
async def test_filesystem_storage_only_accepts_bytes_and_simple_mime(tmp_path):
    storage = LocalObjectStorage(tmp_path / "media")
    with pytest.raises(TypeError):
        await storage.put("a.txt", bytearray(b"value"), "text/plain")
    with pytest.raises(ValueError):
        await storage.put("a.txt", b"value", "text/plain\r\nX-Evil: yes")
    await storage.put("a.txt", b"value", "text/plain; charset=utf-8")


def test_filesystem_profiles_do_not_read_any_secret_file(tmp_path, monkeypatch):
    def fail_secret_read(*_args, **_kwargs):
        raise AssertionError("filesystem profile attempted to read credentials")

    monkeypatch.setattr(storage_config_module, "_read_secret_overlay", fail_secret_read)
    for profile in ("pwa-human", "pwa-agent", "pwa-e2e"):
        config = load_storage_config(
            runtime_profile=profile,
            media_root=tmp_path / profile,
            repository_root=tmp_path,
        )
        assert config.adapter == "filesystem"
        assert config.secret_source == "none"


def test_unknown_storage_profile_fails_closed(tmp_path):
    with pytest.raises(StorageConfigurationError, match="Unknown"):
        load_storage_config(
            runtime_profile="legacy",
            media_root=tmp_path,
            repository_root=tmp_path,
        )


def test_storage_config_direct_constructor_cannot_bypass_invariants(tmp_path):
    with pytest.raises(StorageConfigurationError, match="S3 storage"):
        StorageConfig(adapter="s3")
    with pytest.raises(StorageConfigurationError, match="cannot carry S3"):
        StorageConfig(
            adapter="filesystem",
            filesystem_root=tmp_path,
            endpoint_url="https://objects.example.test",
        )


@pytest.mark.parametrize(
    "bucket_name",
    ["vmsh.test.bucket", "192.0.2.10", "bucket..name"],
)
def test_s3_config_rejects_bucket_names_unsafe_for_virtual_host_tls(bucket_name):
    with pytest.raises(StorageConfigurationError, match="virtual-host"):
        StorageConfig.s3(
            endpoint_url="https://fsn1.your-objectstorage.com",
            bucket_name=bucket_name,
            region="fsn1",
            access_key="synthetic-access-key",
            secret_key="synthetic-secret-key",
            prefix="integration/test",
            secret_source="test",
        )


def test_test_s3_loader_uses_allowlist_and_forced_disposable_prefix(tmp_path):
    document = {
        **VALID_S3_DOCUMENT,
        "telegram_bot_token": "must-not-enter-storage-config",
        "google_sheets_key": "must-not-enter-storage-config-either",
    }
    _write_secret_document(tmp_path, "test", document)

    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root="unused",
        repository_root=tmp_path,
        integration_run_id="phase0-123",
    )

    assert config.adapter == "s3"
    assert config.prefix == "integration/phase0-123"
    assert config.secret_source == "test"
    rendered = repr(config)
    for hidden in (
        document["s3_access_key"],
        document["s3_secret_key"],
        document["s3_bucket_name"],
        document["s3_prefix"],
        document["s3_public_base_url"],
        document["telegram_bot_token"],
        document["google_sheets_key"],
    ):
        assert hidden not in rendered
    assert "telegram_bot_token" not in config.__dict__
    assert "google_sheets_key" not in config.__dict__


def test_s3_loader_defaults_region_for_existing_four_field_overlay(tmp_path):
    document = {
        name: value
        for name, value in VALID_S3_DOCUMENT.items()
        if name in {"s3_url", "s3_bucket_name", "s3_access_key", "s3_secret_key"}
    }
    _write_secret_document(tmp_path, "test", document)
    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root="unused",
        repository_root=tmp_path,
        integration_run_id="legacy-four-fields",
    )
    assert config.region == "fsn1"


def test_s3_loader_infers_beget_region_from_existing_four_field_overlay(tmp_path):
    document = {
        "s3_url": "https://s3.ru1.storage.beget.cloud",
        "s3_bucket_name": "vmsh-test-bucket",
        "s3_access_key": "synthetic-access-key",
        "s3_secret_key": "synthetic-secret-key",
    }
    _write_secret_document(tmp_path, "test", document)

    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root="unused",
        repository_root=tmp_path,
        integration_run_id="beget-region",
    )

    assert config.region == "ru1"


def test_s3_loader_keeps_generic_legacy_region_default(tmp_path):
    document = {
        "s3_url": "https://objects.example.test",
        "s3_bucket_name": "vmsh-test-bucket",
        "s3_access_key": "synthetic-access-key",
        "s3_secret_key": "synthetic-secret-key",
    }
    _write_secret_document(tmp_path, "test", document)

    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root="unused",
        repository_root=tmp_path,
        integration_run_id="generic-region",
    )

    assert config.region == "us-east-1"


def test_partial_s3_config_fails_before_adapter_and_does_not_echo_secrets(tmp_path):
    partial = {
        "s3_url": VALID_S3_DOCUMENT["s3_url"],
        "s3_access_key": "do-not-echo-this-access",
        "s3_secret_key": "do-not-echo-this-secret",
    }
    _write_secret_document(tmp_path, "test", partial)

    with pytest.raises(StorageConfigurationError) as captured:
        load_storage_config(
            runtime_profile=S3_TEST_RUNTIME_PROFILE,
            media_root="unused",
            repository_root=tmp_path,
            integration_run_id="partial",
        )
    message = str(captured.value)
    assert "s3_bucket_name" in message
    assert partial["s3_access_key"] not in message
    assert partial["s3_secret_key"] not in message


@pytest.mark.parametrize("run_id", ["", "UPPER", "../escape", "two/parts", " spaced "])
def test_test_s3_profile_rejects_unsafe_run_id_before_read(tmp_path, run_id):
    with pytest.raises(StorageConfigurationError, match="run id"):
        load_storage_config(
            runtime_profile=S3_TEST_RUNTIME_PROFILE,
            media_root="unused",
            repository_root=tmp_path,
            integration_run_id=run_id,
        )


def test_production_loader_cannot_use_test_file_or_integration_prefix(tmp_path):
    _write_secret_document(tmp_path, "test", VALID_S3_DOCUMENT)
    with pytest.raises(
        StorageConfigurationError, match="production storage credential"
    ):
        load_storage_config(
            runtime_profile=S3_PRODUCTION_RUNTIME_PROFILE,
            media_root="unused",
            repository_root=tmp_path,
        )

    production = {**VALID_S3_DOCUMENT, "s3_prefix": "integration/not-production"}
    _write_secret_document(tmp_path, "production", production)
    with pytest.raises(StorageConfigurationError, match="integration prefix"):
        load_storage_config(
            runtime_profile=S3_PRODUCTION_RUNTIME_PROFILE,
            media_root="unused",
            repository_root=tmp_path,
        )


def test_secret_loader_rejects_symlink(tmp_path):
    external = tmp_path / "external.json"
    external.write_text(json.dumps(VALID_S3_DOCUMENT), encoding="utf-8")
    credential_dir = tmp_path / "creds_test"
    credential_dir.mkdir()
    (credential_dir / "vmsh_bot_config_test.json").symlink_to(external)

    with pytest.raises(StorageConfigurationError, match="symlink"):
        load_storage_config(
            runtime_profile=S3_TEST_RUNTIME_PROFILE,
            media_root="unused",
            repository_root=tmp_path,
            integration_run_id="symlink",
        )


def test_secret_loader_rejects_symlinked_parent_directory(tmp_path):
    external_directory = tmp_path / "external-creds"
    external_directory.mkdir()
    (external_directory / "vmsh_bot_config_test.json").write_text(
        json.dumps(VALID_S3_DOCUMENT), encoding="utf-8"
    )
    (tmp_path / "creds_test").symlink_to(external_directory, target_is_directory=True)

    with pytest.raises(StorageConfigurationError, match="symlink"):
        load_storage_config(
            runtime_profile=S3_TEST_RUNTIME_PROFILE,
            media_root="unused",
            repository_root=tmp_path,
            integration_run_id="symlink-parent",
        )


def test_secret_loader_rejects_file_swapped_to_symlink_at_open(tmp_path, monkeypatch):
    credential_path = _write_secret_document(tmp_path, "test", VALID_S3_DOCUMENT)
    external = tmp_path / "external.json"
    external.write_text(json.dumps(VALID_S3_DOCUMENT), encoding="utf-8")
    real_open = storage_config_module.os.open
    swapped = False

    def swap_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == credential_path.name and kwargs.get("dir_fd") is not None:
            credential_path.unlink()
            credential_path.symlink_to(external)
            swapped = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(storage_config_module.os, "open", swap_before_open)

    with pytest.raises(StorageConfigurationError, match="Cannot load"):
        load_storage_config(
            runtime_profile=S3_TEST_RUNTIME_PROFILE,
            media_root="unused",
            repository_root=tmp_path,
            integration_run_id="swap-race",
        )
    assert swapped is True


@pytest.mark.parametrize(
    "prefix", ["/media", "media/", "media//asset", "media/../x", "media\nasset"]
)
def test_s3_config_rejects_noncanonical_prefix(prefix):
    with pytest.raises(StorageConfigurationError, match="s3_prefix"):
        StorageConfig.s3(
            endpoint_url=VALID_S3_DOCUMENT["s3_url"],
            bucket_name=VALID_S3_DOCUMENT["s3_bucket_name"],
            region=VALID_S3_DOCUMENT["s3_region"],
            access_key=VALID_S3_DOCUMENT["s3_access_key"],
            secret_key=VALID_S3_DOCUMENT["s3_secret_key"],
            prefix=prefix,
            secret_source="test",
        )


class FakeBody:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.closed = False

    async def read(self):
        return self.payload

    def close(self):
        self.closed = True


class FakeS3Client:
    def __init__(self, objects: dict[tuple[str, str], tuple[bytes, str]]):
        self.objects = objects
        self.calls: list[tuple[str, dict]] = []
        self.last_body: FakeBody | None = None

    async def put_object(self, **kwargs):
        self.calls.append(("put", kwargs))
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = (
            kwargs["Body"],
            kwargs["ContentType"],
        )

    async def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        payload, _content_type = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        self.last_body = FakeBody(payload)
        return {"Body": self.last_body}

    async def delete_object(self, **kwargs):
        self.calls.append(("delete", kwargs))
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)


class FakeClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, *_args):
        return False


class FakeSession:
    def __init__(self):
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.clients: list[FakeS3Client] = []
        self.client_kwargs: list[dict] = []

    def client(self, service_name: str, **kwargs):
        assert service_name == "s3"
        self.client_kwargs.append(kwargs)
        client = FakeS3Client(self.objects)
        self.clients.append(client)
        return FakeClientContext(client)


def _synthetic_s3_config() -> StorageConfig:
    return StorageConfig.s3(
        endpoint_url=VALID_S3_DOCUMENT["s3_url"],
        bucket_name=VALID_S3_DOCUMENT["s3_bucket_name"],
        region=VALID_S3_DOCUMENT["s3_region"],
        access_key=VALID_S3_DOCUMENT["s3_access_key"],
        secret_key=VALID_S3_DOCUMENT["s3_secret_key"],
        prefix="integration/unit-test",
        public_base_url=VALID_S3_DOCUMENT["s3_public_base_url"],
        secret_source="test",
    )


@pytest.mark.asyncio
async def test_s3_adapter_contract_explicit_client_config_and_public_url():
    session = FakeSession()
    config = _synthetic_s3_config()
    storage = S3ObjectStorage(config, session=session)

    await storage.put("folder/рисунок 1.svg", b"svg", "image/svg+xml")
    assert await storage.get("folder/рисунок 1.svg") == b"svg"
    assert session.clients[-1].last_body.closed is True
    url = storage.public_url("folder/рисунок 1.svg")
    assert url == (
        "https://media.example.test/integration/unit-test/folder/"
        "%D1%80%D0%B8%D1%81%D1%83%D0%BD%D0%BE%D0%BA%201.svg"
    )
    await storage.delete("folder/рисунок 1.svg")
    assert session.objects == {}

    kwargs = session.client_kwargs[0]
    assert kwargs["endpoint_url"] == config.endpoint_url
    assert kwargs["region_name"] == "fsn1"
    assert kwargs["aws_access_key_id"] == VALID_S3_DOCUMENT["s3_access_key"]
    assert kwargs["aws_secret_access_key"] == VALID_S3_DOCUMENT["s3_secret_key"]
    assert kwargs["config"].request_checksum_calculation == "when_required"
    assert kwargs["config"].response_checksum_validation == "when_required"
    assert VALID_S3_DOCUMENT["s3_secret_key"] not in repr(storage)


def test_s3_public_url_uses_hetzner_virtual_host_when_no_override():
    config = StorageConfig.s3(
        endpoint_url="https://fsn1.your-objectstorage.com",
        bucket_name="vmsh-public-media",
        region="fsn1",
        access_key="synthetic-access",
        secret_key="synthetic-secret",
        prefix="media",
        secret_source="test",
    )
    storage = S3ObjectStorage(config, session=FakeSession())
    assert storage.public_url("a b.webp") == (
        "https://vmsh-public-media.fsn1.your-objectstorage.com/media/a%20b.webp"
    )


def test_unknown_s3_provider_public_url_requires_explicit_origin():
    config = StorageConfig.s3(
        endpoint_url="https://objects.example.test",
        bucket_name="vmsh-public-media",
        region="us-east-1",
        access_key="synthetic-access",
        secret_key="synthetic-secret",
        prefix="media",
        secret_source="test",
    )
    storage = S3ObjectStorage(config, session=FakeSession())
    with pytest.raises(StorageConfigurationError, match="s3_public_base_url"):
        storage.public_url("probe.txt")


def test_beget_public_url_uses_documented_virtual_host_without_override():
    config = StorageConfig.s3(
        endpoint_url="https://s3.ru1.storage.beget.cloud",
        bucket_name="vmsh-public-media",
        region="ru1",
        access_key="synthetic-access",
        secret_key="synthetic-secret",
        prefix="integration/unit-test",
        secret_source="test",
    )
    storage = S3ObjectStorage(config, session=FakeSession())

    assert storage.public_url("a b.webp") == (
        "https://vmsh-public-media.s3.ru1.storage.beget.cloud/"
        "integration/unit-test/a%20b.webp"
    )


@pytest.mark.asyncio
async def test_s3_adapter_rejects_escape_before_opening_client():
    session = FakeSession()
    storage = S3ObjectStorage(_synthetic_s3_config(), session=session)
    with pytest.raises(StoragePathError):
        await storage.put("../outside", b"no", "text/plain")
    assert session.clients == []


@pytest.mark.asyncio
async def test_s3_adapter_applies_key_limit_after_runtime_prefix():
    session = FakeSession()
    config = StorageConfig.s3(
        endpoint_url="https://fsn1.your-objectstorage.com",
        bucket_name="vmsh-public-media",
        region="fsn1",
        access_key="synthetic-access",
        secret_key="synthetic-secret",
        prefix="p" * 900,
        secret_source="test",
    )
    storage = S3ObjectStorage(config, session=session)

    with pytest.raises(StoragePathError, match="1024-byte"):
        await storage.put("x" * 124, b"no", "text/plain")

    assert session.clients == []


@pytest.mark.asyncio
async def test_s3_adapter_redacts_provider_exception_and_drops_context():
    class LeakyClientError(RuntimeError):
        response = {
            "Error": {
                "Code": "XAmzContentSHA256Mismatch",
                "Message": "https://private-bucket.example/secret/object-key",
            },
            "ResponseMetadata": {"HTTPStatusCode": 400},
        }

    class LeakyClient(FakeS3Client):
        async def put_object(self, **_kwargs):
            raise LeakyClientError("https://private-bucket.example/secret/object-key")

    class LeakySession(FakeSession):
        def client(self, service_name: str, **kwargs):
            assert service_name == "s3"
            self.client_kwargs.append(kwargs)
            return FakeClientContext(LeakyClient(self.objects))

    storage = S3ObjectStorage(_synthetic_s3_config(), session=LeakySession())

    with pytest.raises(ObjectStorageOperationError) as captured:
        await storage.put("secret/object-key", b"value", "text/plain")

    assert str(captured.value) == (
        "Object storage put failed "
        "(LeakyClientError/XAmzContentSHA256Mismatch/HTTP-400)"
    )
    assert "private-bucket" not in str(captured.value)
    assert captured.value.__context__ is None


def test_storage_factory_returns_profile_adapter(tmp_path):
    local = create_object_storage(StorageConfig.filesystem(tmp_path / "media"))
    remote = create_object_storage(_synthetic_s3_config(), session=FakeSession())
    assert isinstance(local, LocalObjectStorage)
    assert isinstance(remote, S3ObjectStorage)


class RecordingSmokeStorage:
    def __init__(self, *, fail_delete=False):
        self.payload: bytes | None = None
        self.deleted = False
        self.fail_delete = fail_delete
        self.put_keys: list[str] = []
        self.deleted_keys: list[str] = []

    async def put(self, key, data, content_type):
        assert key.startswith("probe-") and key.endswith(".txt")
        assert content_type == "text/plain"
        self.put_keys.append(key)
        self.payload = data

    async def get(self, key):
        assert key == self.put_keys[-1]
        return self.payload

    async def delete(self, key):
        assert key == self.put_keys[-1]
        self.deleted_keys.append(key)
        if self.fail_delete:
            raise RuntimeError("synthetic cleanup failure")
        self.deleted = True
        self.payload = None

    def public_url(self, key):
        assert key.startswith("probe-") and key.endswith(".txt")
        return f"https://public.example.test/integration/test/{key}"


@pytest.mark.asyncio
async def test_live_smoke_sequence_cleans_probe_after_success():
    storage = RecordingSmokeStorage()

    async def public_get(_url):
        return 200, storage.payload

    result = await run_storage_smoke(
        storage,
        run_id="unit-success",
        public_get=public_get,
        probe_nonce="first-probe",
    )
    assert result["ok"] is True
    assert storage.deleted is True
    assert storage.put_keys == ["probe-first-probe.txt"]
    assert storage.deleted_keys == storage.put_keys


@pytest.mark.asyncio
async def test_live_smoke_reusing_run_id_uses_distinct_probe_keys():
    first = RecordingSmokeStorage()
    second = RecordingSmokeStorage()

    async def first_public_get(_url):
        return 200, first.payload

    async def second_public_get(_url):
        return 200, second.payload

    await run_storage_smoke(first, run_id="replayed", public_get=first_public_get)
    await run_storage_smoke(second, run_id="replayed", public_get=second_public_get)

    assert first.put_keys[0] != second.put_keys[0]


@pytest.mark.asyncio
async def test_live_smoke_preserves_primary_and_cleanup_failures():
    storage = RecordingSmokeStorage(fail_delete=True)

    async def public_get(_url):
        return 403, b""

    with pytest.raises(ExceptionGroup) as captured:
        await run_storage_smoke(
            storage,
            run_id="unit-double-failure",
            public_get=public_get,
            probe_nonce="double-failure",
        )
    assert len(captured.value.exceptions) == 2
    assert isinstance(captured.value.exceptions[0], StorageSmokeError)
    assert isinstance(captured.value.exceptions[1], StorageSmokeError)
    assert "Public S3 GET" in str(captured.value.exceptions[0])
    assert "S3 delete failed (RuntimeError)" in str(captured.value.exceptions[1])


@pytest.mark.asyncio
async def test_live_smoke_sequence_cleans_probe_after_public_get_failure():
    storage = RecordingSmokeStorage()

    async def public_get(_url):
        return 403, b""

    with pytest.raises(StorageSmokeError, match="Public S3 GET"):
        await run_storage_smoke(
            storage,
            run_id="unit-failure",
            public_get=public_get,
            probe_nonce="public-failure",
        )
    assert storage.deleted is True


def test_live_smoke_requires_exact_opt_in():
    for value in (None, "1", "TRUE", "yes"):
        environment = {} if value is None else {LIVE_S3_OPT_IN: value}
        with pytest.raises(StorageConfigurationError, match=LIVE_S3_OPT_IN):
            require_live_opt_in(environment)
    require_live_opt_in({LIVE_S3_OPT_IN: "true"})


def test_live_smoke_cli_refuses_before_loading_config(monkeypatch, capsys):
    monkeypatch.delenv(LIVE_S3_OPT_IN, raising=False)

    async def must_not_run(_run_id):
        raise AssertionError("storage config was loaded without opt-in")

    monkeypatch.setattr(storage_smoke_module, "_main_async", must_not_run)
    assert storage_smoke_module.main([]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert LIVE_S3_OPT_IN in report["error"]


def test_live_smoke_cli_redacts_unexpected_provider_error(monkeypatch, capsys):
    monkeypatch.setenv(LIVE_S3_OPT_IN, "true")

    async def fail_with_url(_run_id):
        raise RuntimeError(
            "provider failed at https://bucket.example.test/integration/run/probe.txt"
        )

    monkeypatch.setattr(storage_smoke_module, "_main_async", fail_with_url)
    assert storage_smoke_module.main(["--run-id", "redaction-test"]) == 1
    output = capsys.readouterr().out
    assert "bucket.example.test" not in output
    report = json.loads(output)
    assert report == {
        "error": "Unexpected storage smoke failure (RuntimeError)",
        "ok": False,
    }


def test_live_smoke_cli_reports_both_sanitized_group_causes(monkeypatch, capsys):
    monkeypatch.setenv(LIVE_S3_OPT_IN, "true")

    async def fail_twice(_run_id):
        raise ExceptionGroup(
            "S3 smoke operation and cleanup both failed",
            [
                StorageSmokeError("Public S3 GET did not return the uploaded probe"),
                StorageSmokeError("S3 delete failed (SyntheticError/HTTP-503)"),
            ],
        )

    monkeypatch.setattr(storage_smoke_module, "_main_async", fail_twice)
    assert storage_smoke_module.main(["--run-id", "double-failure"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "causes": [
            "Public S3 GET did not return the uploaded probe",
            "S3 delete failed (SyntheticError/HTTP-503)",
        ],
        "error": "S3 smoke operation and cleanup both failed",
        "ok": False,
    }


def test_live_smoke_cli_redacts_unknown_group_child(monkeypatch, capsys):
    monkeypatch.setenv(LIVE_S3_OPT_IN, "true")

    async def fail_with_leaky_child(_run_id):
        raise ExceptionGroup(
            "S3 smoke operation and cleanup both failed",
            [RuntimeError("https://private-bucket.example/secret")],
        )

    monkeypatch.setattr(storage_smoke_module, "_main_async", fail_with_leaky_child)
    assert storage_smoke_module.main(["--run-id", "redacted-group"]) == 1
    output = capsys.readouterr().out
    assert "private-bucket" not in output
    report = json.loads(output)
    assert report["causes"] == ["Unexpected storage smoke failure (RuntimeError)"]


def test_live_smoke_provider_error_keeps_only_sanitized_code_and_status():
    class SyntheticClientError(RuntimeError):
        response = {
            "Error": {
                "Code": "SignatureDoesNotMatch",
                "Message": "private bucket URL and signed request",
            },
            "ResponseMetadata": {"HTTPStatusCode": 403},
        }

    error = storage_smoke_module._safe_provider_failure(
        "S3 put", SyntheticClientError("private provider message")
    )

    assert str(error) == (
        "S3 put failed (SyntheticClientError/SignatureDoesNotMatch/HTTP-403)"
    )
    assert "private" not in str(error)


def _write_test_binding(path: Path, config: StorageConfig) -> None:
    assert config.endpoint_url is not None
    assert config.bucket_name is not None
    path.write_text(
        json.dumps(
            {
                "format": "vmsh.s3-binding/v1",
                "endpointHost": "fsn1.your-objectstorage.com",
                "bucketNameSha256": hashlib.sha256(
                    config.bucket_name.encode()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


def test_live_smoke_verifies_pinned_test_bucket_before_network(tmp_path):
    config = _synthetic_s3_config()
    binding = tmp_path / "binding.json"
    _write_test_binding(binding, config)

    verify_test_bucket_binding(config, binding_path=binding)

    binding.write_text(
        json.dumps(
            {
                "format": "vmsh.s3-binding/v1",
                "endpointHost": "fsn1.your-objectstorage.com",
                "bucketNameSha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StorageConfigurationError, match="pinned disposable"):
        verify_test_bucket_binding(config, binding_path=binding)


@pytest.mark.asyncio
async def test_live_smoke_binding_mismatch_stops_before_storage_factory(
    tmp_path, monkeypatch
):
    binding = tmp_path / "binding.json"
    binding.write_text(
        json.dumps(
            {
                "format": "vmsh.s3-binding/v1",
                "endpointHost": "wrong.example.test",
                "bucketNameSha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(storage_smoke_module, "TEST_BINDING_PATH", binding)
    monkeypatch.setattr(
        storage_smoke_module,
        "load_storage_config",
        lambda **_kwargs: _synthetic_s3_config(),
    )

    def must_not_create(_config):
        raise AssertionError("storage client created before binding verification")

    monkeypatch.setattr(storage_smoke_module, "create_object_storage", must_not_create)

    with pytest.raises(StorageConfigurationError, match="pinned disposable"):
        await storage_smoke_module._main_async("binding-mismatch")


@pytest.mark.asyncio
async def test_local_reads_during_replacement_never_observe_partial_bytes(tmp_path):
    storage = LocalObjectStorage(tmp_path / "media")
    key = "atomic/blob.bin"
    old = b"a" * (256 * 1024)
    new = b"b" * (256 * 1024)
    await storage.put(key, old, "application/octet-stream")

    reads = []

    async def reader():
        for _ in range(20):
            reads.append(await storage.get(key))
            await asyncio.sleep(0)

    await asyncio.gather(reader(), storage.put(key, new, "application/octet-stream"))
    assert set(reads) <= {old, new}
