from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import pytest

from db_methods.pwa.written_submissions import (
    CreateWrittenAttachmentReceipt,
    PreparedWrittenAttachmentUpload,
    ProblemRevisionRef,
    WrittenAttachmentUploadScope,
    WrittenEntryRecord,
)
from helpers.pwa.content.assets import ConvertedAsset
from helpers.pwa.written_attachments import (
    WrittenAttachmentCleanupError,
    WrittenAttachmentService,
    WrittenAttachmentServiceError,
)


NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)
SOURCE = b"synthetic phone photo"
WEBP = b"synthetic final webp"


@dataclass
class FakeConverter:
    calls: int = 0
    contradict_hash: bool = False

    async def raster_to_webp(self, payload: bytes) -> ConvertedAsset:
        self.calls += 1
        return ConvertedAsset(
            source_sha256=(
                "0" * 64
                if self.contradict_hash
                else hashlib.sha256(payload).hexdigest()
            ),
            output_sha256=hashlib.sha256(WEBP).hexdigest(),
            media_type="image/webp",
            data=WEBP,
            width=1440,
            height=1920,
        )


@dataclass
class FakeStorage:
    puts: list[tuple[str, bytes, str]] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    fail_delete: bool = False

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.puts.append((key, data, content_type))

    async def get(self, key: str) -> bytes:  # pragma: no cover - protocol stub
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        if self.fail_delete:
            raise RuntimeError("synthetic delete failure")

    def public_url(self, key: str) -> str:
        return f"https://assets.invalid/{key}"


@dataclass
class FakeRepository:
    replay: bool = False
    fail_complete: bool = False
    concurrent_replay: bool = False
    prepared: list[object] = field(default_factory=list)
    completed: list[object] = field(default_factory=list)

    async def prepare_attachment_upload(self, command):
        self.prepared.append(command)
        if self.replay:
            return _receipt(replayed=True)
        return PreparedWrittenAttachmentUpload(
            command=command,
            payload_sha256="a" * 64,
            scope=WrittenAttachmentUploadScope(
                student_user_id=947001,
                season_year=2026,
                lesson_number=41,
                problem_public_id="problem-written-1",
            ),
        )

    async def complete_attachment_upload(self, prepared, asset):
        self.completed.append((prepared, asset))
        if self.fail_complete:
            raise RuntimeError("synthetic database failure")
        return _receipt(replayed=self.concurrent_replay)


def _receipt(*, replayed: bool) -> CreateWrittenAttachmentReceipt:
    return CreateWrittenAttachmentReceipt(
        thread_public_id="thread-written-1",
        problem_public_id="problem-written-1",
        thread_status="open",
        thread_version=2,
        entry=WrittenEntryRecord(
            public_id="entry-written-1",
            author_kind="student",
            entry_kind="submission",
            state="draft",
            text=None,
            problem_revision=ProblemRevisionRef("revision-written-1", 1),
            version=2,
            client_created_at="2026-09-20T13:00:00.000000Z",
            server_received_at="2026-09-20T13:00:00.000000Z",
            attachments=(),
        ),
        replayed=replayed,
    )


def _service(
    *,
    converter: FakeConverter | None = None,
    storage: FakeStorage | None = None,
    repository: FakeRepository | None = None,
) -> tuple[WrittenAttachmentService, FakeConverter, FakeStorage, FakeRepository]:
    converter = converter or FakeConverter()
    storage = storage or FakeStorage()
    repository = repository or FakeRepository()
    return (
        WrittenAttachmentService(
            converter=converter,  # type: ignore[arg-type]
            storage=storage,
            repository=repository,  # type: ignore[arg-type]
            clock=lambda: NOW,
            object_token_factory=lambda: "1" * 32,
        ),
        converter,
        storage,
        repository,
    )


async def _upload(service: WrittenAttachmentService):
    return await service.convert_and_attach(
        account_id=17,
        entry_public_id="entry-written-1",
        expected_entry_version=1,
        expected_thread_version=1,
        ordinal=0,
        idempotency_key="00000000-0000-4000-8000-000000000001",
        payload=SOURCE,
        source_filename=r"C:\phone\page 1.heic",
    )


async def test_written_image_uses_server_scope_and_persists_only_final_webp() -> None:
    service, converter, storage, repository = _service()

    receipt = await _upload(service)

    expected_key = (
        "sol_imgs/user_947001/2026/lesson_41/"
        "problem-written-1_20260920T130000000000Z_"
        f"{'1' * 32}.webp"
    )
    assert receipt.replayed is False
    assert converter.calls == 1
    assert storage.puts == [(expected_key, WEBP, "image/webp")]
    assert storage.deletes == []
    assert len(repository.completed) == 1
    _prepared, persisted = repository.completed[0]
    assert persisted.object_key == expected_key
    assert persisted.output_sha256 == hashlib.sha256(WEBP).hexdigest()
    assert persisted.public_url == f"https://assets.invalid/{expected_key}"
    assert repository.prepared[0].client_filename == "page 1.heic"


async def test_exact_upload_replay_stops_before_conversion_and_storage() -> None:
    service, converter, storage, repository = _service(
        repository=FakeRepository(replay=True)
    )

    receipt = await _upload(service)

    assert receipt.replayed is True
    assert converter.calls == 0
    assert storage.puts == []
    assert repository.completed == []


async def test_database_failure_deletes_the_unique_final_object() -> None:
    service, _converter, storage, _repository = _service(
        repository=FakeRepository(fail_complete=True)
    )

    with pytest.raises(RuntimeError, match="database failure"):
        await _upload(service)

    assert len(storage.puts) == 1
    assert storage.deletes == [storage.puts[0][0]]


async def test_concurrent_replay_deletes_this_requests_unreferenced_object() -> None:
    service, _converter, storage, _repository = _service(
        repository=FakeRepository(concurrent_replay=True)
    )

    receipt = await _upload(service)

    assert receipt.replayed is True
    assert storage.deletes == [storage.puts[0][0]]


async def test_contradictory_conversion_is_rejected_before_object_write() -> None:
    service, _converter, storage, repository = _service(
        converter=FakeConverter(contradict_hash=True)
    )

    with pytest.raises(WrittenAttachmentServiceError, match="source hash"):
        await _upload(service)

    assert storage.puts == []
    assert repository.completed == []


async def test_cleanup_failure_is_explicit_and_redacted() -> None:
    service, _converter, storage, _repository = _service(
        storage=FakeStorage(fail_delete=True),
        repository=FakeRepository(fail_complete=True),
    )

    with pytest.raises(WrittenAttachmentCleanupError) as caught:
        await _upload(service)

    assert "synthetic" not in str(caught.value)
    assert len(storage.deletes) == 1


def test_receipt_replay_marker_does_not_change_equality() -> None:
    assert _receipt(replayed=False) == replace(_receipt(replayed=False), replayed=True)
