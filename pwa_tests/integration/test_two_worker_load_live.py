"""Small two-worker write smoke sized from the observed club workload."""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import math
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aiohttp import ClientSession, DummyCookieJar, TCPConnector

from db_methods.pwa import PwaConnectionFactory
from db_methods.pwa.written_submissions import (
    CreateWrittenAttachmentCommand,
    CreateWrittenEntryCommand,
    PersistWrittenAttachment,
    PreparedWrittenAttachmentUpload,
    ProblemRevisionRef,
    PwaWrittenSubmissionRepository,
    SubmitWrittenEntryCommand,
)
from pwa_tests.fixtures.seed import load_baseline_v1
from pwa_tests.integration.test_submission_repository import (
    SubmissionFixture,
    build_submission_fixture,
)
from pwa_tests.integration.test_two_worker_live import (
    REPOSITORY_ROOT,
    _stop_worker,
    _unused_port,
    _wait_until_ready,
    _worker_environment,
)
from vmshpwa.scripts.seed_runtime import _seed_runtime_under_lock


RUN_LIVE_SMOKE = os.environ.get("VMSH_RUN_TWO_WORKER_SMOKE") == "1"
CONCURRENT_LOGINS = 40
SUBMISSIONS_PER_WORKER = 8
PHOTOS_PER_SUBMISSION = 2
PHOTO_BYTES = 512 * 1024
WRITTEN_PROBLEM_PUBLIC_ID = "problem-submission-written"
WORKLOAD_NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)

pytestmark = pytest.mark.skipif(
    not RUN_LIVE_SMOKE,
    reason="set VMSH_RUN_TWO_WORKER_SMOKE=1 for the local two-worker smoke",
)


def _count(database: Path, sql: str) -> int:
    with sqlite3.connect(database) as connection:
        return int(connection.execute(sql).fetchone()[0])


def _journal_mode(database: Path) -> str:
    with sqlite3.connect(database) as connection:
        return str(connection.execute("PRAGMA journal_mode").fetchone()[0])


def _run_written_photo_batch(
    database: Path,
    media_root: Path,
    account_id: int,
    worker_index: int,
) -> dict[str, object]:
    """Persist one outbox-shaped photo batch from a separate process."""

    async def run() -> dict[str, object]:
        sequence = itertools.count(1)

        def public_id(kind: str) -> str:
            return f"load-{kind}-{worker_index}-{next(sequence)}"

        # Keep the synthetic clock inside the published fixture lesson window;
        # this smoke measures contention, not deadline behavior.
        repository = PwaWrittenSubmissionRepository(
            PwaConnectionFactory(database),
            clock=lambda: WORKLOAD_NOW,
            thread_public_id_factory=lambda: public_id("thread"),
            entry_public_id_factory=lambda: public_id("entry"),
            attachment_public_id_factory=lambda: public_id("attachment"),
            media_public_id_factory=lambda: public_id("media"),
        )
        media_root.mkdir(parents=True, exist_ok=True)
        latencies: list[float] = []
        stored_bytes = 0
        for submission_index in range(SUBMISSIONS_PER_WORKER):
            started = time.monotonic()
            created = await repository.create_entry(
                CreateWrittenEntryCommand(
                    account_id=account_id,
                    problem_public_id=WRITTEN_PROBLEM_PUBLIC_ID,
                    problem_revision=ProblemRevisionRef(
                        condition_revision_public_id="revision-submission-condition",
                        config_version=1,
                    ),
                    text=f"Синтетическое решение {worker_index}-{submission_index}",
                    client_created_at=WORKLOAD_NOW,
                    idempotency_key=(f"load-create-{worker_index}-{submission_index}"),
                )
            )
            entry_version = created.entry.version
            thread_version = created.thread_version
            attachment_ids: list[str] = []
            for ordinal in range(PHOTOS_PER_SUBMISSION):
                # Opaque bytes are intentional here: real HEIC/JPEG/WebP
                # conversion is covered by the media corpus. This test isolates
                # concurrent SQLite metadata writes plus representative file IO.
                payload = bytes(
                    [65 + worker_index, 48 + submission_index, 48 + ordinal]
                ) * (PHOTO_BYTES // 3)
                output_sha256 = hashlib.sha256(payload).hexdigest()
                object_name = f"load-{worker_index}-{submission_index}-{ordinal}.webp"
                object_path = media_root / object_name
                object_path.write_bytes(payload)
                stored_bytes += len(payload)
                prepared = await repository.prepare_attachment_upload(
                    CreateWrittenAttachmentCommand(
                        account_id=account_id,
                        entry_public_id=created.entry.public_id,
                        expected_entry_version=entry_version,
                        expected_thread_version=thread_version,
                        ordinal=ordinal,
                        client_filename=f"page-{ordinal + 1}.webp",
                        source_sha256=output_sha256,
                        idempotency_key=(
                            f"load-photo-{worker_index}-{submission_index}-{ordinal}"
                        ),
                    )
                )
                if not isinstance(prepared, PreparedWrittenAttachmentUpload):
                    raise AssertionError("Fresh workload upload unexpectedly replayed")
                uploaded = await repository.complete_attachment_upload(
                    prepared,
                    PersistWrittenAttachment(
                        object_key=f"integration/load/{object_name}",
                        public_url=f"https://assets.invalid/{object_name}",
                        output_sha256=output_sha256,
                        byte_size=len(payload),
                        width=1440,
                        height=1920,
                    ),
                )
                entry_version = uploaded.entry.version
                thread_version = uploaded.thread_version
                attachment_ids.append(uploaded.entry.attachments[-1].public_id)
            await repository.submit_entry(
                SubmitWrittenEntryCommand(
                    account_id=account_id,
                    entry_public_id=created.entry.public_id,
                    expected_entry_version=entry_version,
                    expected_thread_version=thread_version,
                    attachment_public_ids=tuple(attachment_ids),
                    idempotency_key=(f"load-submit-{worker_index}-{submission_index}"),
                )
            )
            latencies.append(time.monotonic() - started)
        return {
            "latencies": latencies,
            "storedBytes": stored_bytes,
            "submissions": SUBMISSIONS_PER_WORKER,
            "photos": SUBMISSIONS_PER_WORKER * PHOTOS_PER_SUBMISSION,
        }

    try:
        return asyncio.run(run())
    except (
        Exception
    ) as error:  # returned explicitly because domain errors are not IPC values
        return {"errorType": type(error).__name__, "error": str(error)}


def _grant_second_student_course_access(fixture: SubmissionFixture) -> None:
    """Give the existing second synthetic account its own independent thread."""

    now = WORKLOAD_NOW.isoformat()

    def write(connection: sqlite3.Connection) -> None:
        course_id = int(
            connection.execute(
                "SELECT id FROM courses WHERE public_id = 'course-submission'"
            ).fetchone()["id"]
        )
        student_user_id = int(
            connection.execute(
                "SELECT linked_user_id FROM auth_accounts WHERE id = ?",
                (fixture.other_account_id,),
            ).fetchone()["linked_user_id"]
        )
        enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(public_id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) VALUES "
                "('enrollment-submission-load-other', ?, ?, 'submission-a', "
                "'online', 'active', ?, ?) RETURNING id",
                (student_user_id, course_id, now, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, "
            "updated_at) VALUES (?, ?, 'submission-a', ?, ?, ?)",
            (enrollment_id, course_id, now, now, now),
        )

    fixture.factory.run_write(write)


@pytest.mark.asyncio
async def test_two_workers_complete_small_concurrent_write_burst(
    tmp_path: Path,
) -> None:
    """Exceed the observed minute peak without turning this into a load lab."""

    database = tmp_path / "shared-load.sqlite3"
    _seed_runtime_under_lock(database, tmp_path / "media", load_baseline_v1())
    sessions_before = _count(database, "SELECT count(*) FROM auth_sessions")
    events_before = _count(
        database,
        "SELECT count(*) FROM auth_events WHERE event_type = 'session.created'",
    )

    ports = [_unused_port(), _unused_port()]
    origins = [f"http://127.0.0.1:{port}" for port in ports]
    prefix = f"vmshpwa_agent_phase11_load_{uuid.uuid4().hex[:12]}"
    processes: list[subprocess.Popen[bytes]] = []
    log_paths = [tmp_path / "worker-0.log", tmp_path / "worker-1.log"]
    log_files = []
    session = ClientSession(
        cookie_jar=DummyCookieJar(), connector=TCPConnector(limit=CONCURRENT_LOGINS)
    )
    try:
        for index, port in enumerate(ports):
            log_file = log_paths[index].open("wb")
            log_files.append(log_file)
            processes.append(
                subprocess.Popen(
                    [sys.executable, "main.py"],
                    cwd=REPOSITORY_ROOT,
                    env=_worker_environment(
                        database=database,
                        media_root=tmp_path / f"media-{index}",
                        port=port,
                        origins=origins,
                        prefix=prefix,
                    ),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
            )

        await asyncio.gather(
            *(_wait_until_ready(session, origin) for origin in origins)
        )

        async def login(index: int) -> float:
            started = time.monotonic()
            origin = origins[index % len(origins)]
            async with session.post(
                f"{origin}/student/api/v1/auth/login",
                headers={"Origin": origin, "X-Request-ID": f"phase11-load-{index}"},
                json={
                    "username": "testovyy-onlayn-14",
                    "telegramToken": "synthetic-telegram-token-not-a-secret",
                },
            ) as response:
                assert response.status == 200, await response.text()
                await response.read()
            return time.monotonic() - started

        burst_started = time.monotonic()
        latencies = await asyncio.gather(
            *(login(index) for index in range(CONCURRENT_LOGINS))
        )
        elapsed = time.monotonic() - burst_started

        ordered = sorted(latencies)
        p95 = ordered[math.ceil(len(ordered) * 0.95) - 1]
        # These are generous smoke bounds, not production latency SLOs. They
        # catch a stuck writer/timeout while remaining stable on a developer Mac.
        assert elapsed < 30
        assert p95 < 20
    finally:
        await session.close()
        for process in processes:
            _stop_worker(process)
        for log_file in log_files:
            log_file.close()

    assert _count(database, "SELECT count(*) FROM auth_sessions") == (
        sessions_before + CONCURRENT_LOGINS
    )
    assert (
        _count(
            database,
            "SELECT count(*) FROM auth_events WHERE event_type = 'session.created'",
        )
        == events_before + CONCURRENT_LOGINS
    )
    assert _journal_mode(database).casefold() == "wal"

    combined_logs = b"\n".join(path.read_bytes().lower() for path in log_paths)
    assert b"database is locked" not in combined_logs
    assert b"write lock was busy" not in combined_logs


@pytest.mark.asyncio
async def test_two_processes_persist_written_photo_batches_without_busy_exhaustion(
    tmp_path: Path,
) -> None:
    """Flush slightly more than the observed peak of 13 submissions/minute."""

    fixture = build_submission_fixture(tmp_path)
    _grant_second_student_course_access(fixture)
    counts_before = fixture.factory.run_read(
        lambda connection: {
            table: int(
                connection.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            )
            for table in (
                "submission_threads",
                "submission_entries",
                "submission_attachments",
                "media_assets",
                "idempotency_records",
                "written_tasks_queue",
            )
        }
    )
    account_ids = (fixture.student_account_id, fixture.other_account_id)
    loop = asyncio.get_running_loop()
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=2) as executor:
        results = await asyncio.wait_for(
            asyncio.gather(
                *(
                    loop.run_in_executor(
                        executor,
                        _run_written_photo_batch,
                        fixture.factory.database_path,
                        tmp_path / f"written-media-{worker_index}",
                        account_id,
                        worker_index,
                    )
                    for worker_index, account_id in enumerate(account_ids)
                )
            ),
            timeout=60,
        )
    elapsed = time.monotonic() - started

    assert all("error" not in result for result in results), results

    latencies = sorted(
        float(latency)
        for result in results
        for latency in result["latencies"]  # type: ignore[index]
    )
    total_submissions = sum(int(result["submissions"]) for result in results)
    total_photos = sum(int(result["photos"]) for result in results)
    total_bytes = sum(int(result["storedBytes"]) for result in results)
    p95 = latencies[math.ceil(len(latencies) * 0.95) - 1]
    print(
        "written-outbox workload: "
        f"submissions={total_submissions} photos={total_photos} "
        f"bytes={total_bytes} elapsed={elapsed:.3f}s p95={p95:.3f}s"
    )

    # This is a developer-machine smoke budget, not a production SLO. User-
    # visible SQLITE_BUSY exhaustion is never acceptable at this small club
    # workload; bounded internal retries remain an implementation detail.
    assert total_submissions == 16
    assert total_photos == 32
    assert total_bytes >= 16 * 1024 * 1024 - 64
    assert elapsed < 30
    assert p95 < 10

    counts_after = fixture.factory.run_read(
        lambda connection: {
            table: int(
                connection.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            )
            for table in counts_before
        }
    )
    assert counts_after == {
        "submission_threads": counts_before["submission_threads"] + 2,
        "submission_entries": counts_before["submission_entries"] + total_submissions,
        "submission_attachments": counts_before["submission_attachments"]
        + total_photos,
        "media_assets": counts_before["media_assets"] + total_photos,
        "idempotency_records": counts_before["idempotency_records"]
        + total_submissions * (2 + PHOTOS_PER_SUBMISSION),
        "written_tasks_queue": counts_before["written_tasks_queue"] + 2,
    }
    assert _journal_mode(fixture.factory.database_path).casefold() == "wal"
