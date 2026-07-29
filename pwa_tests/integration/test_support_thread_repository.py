"""Repository contracts for private, unassigned Student support threads."""

from __future__ import annotations

import asyncio
import itertools
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.support import (
    AppendStaffSupportEntryCommand,
    AppendStudentSupportEntryCommand,
    CreateSupportThreadCommand,
    PwaSupportThreadRepository,
    SupportForbidden,
    SupportIdempotencyConflict,
    SupportNotFound,
    SupportStaffScope,
)


NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
STUDENT_ID = -956_001
OTHER_STUDENT_ID = -956_002
TEACHER_ID = -956_003
ADMIN_ID = -956_004


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


@dataclass(slots=True)
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


@dataclass(frozen=True, slots=True)
class SupportFixture:
    factory: PwaConnectionFactory
    repository: PwaSupportThreadRepository
    clock: MutableClock


GROUP_A_SCOPE = SupportStaffScope(group_public_ids=frozenset({"support-group-a"}))
GROUP_B_SCOPE = SupportStaffScope(group_public_ids=frozenset({"support-group-b"}))


@pytest.fixture()
def support_fixture(tmp_path) -> SupportFixture:
    database_path = tmp_path / "support.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    clock = MutableClock(NOW)
    thread_ids = (f"support-thread-test-{index}" for index in itertools.count(1))
    entry_ids = (f"support-entry-test-{index}" for index in itertools.count(1))
    repository = PwaSupportThreadRepository(
        factory,
        clock=clock,
        thread_public_id_factory=lambda: next(thread_ids),
        entry_public_id_factory=lambda: next(entry_ids),
    )
    now = _timestamp(NOW)
    access_from = _timestamp(NOW - timedelta(days=30))

    def seed(connection: sqlite3.Connection) -> None:
        connection.executemany(
            "INSERT INTO users (id, public_id, type, name, surname) VALUES (?, ?, ?, ?, ?)",
            (
                (STUDENT_ID, "support-student", 1, "Анна", "Белова"),
                (OTHER_STUDENT_ID, "support-other-student", 1, "Борис", "Ветров"),
                (TEACHER_ID, "support-teacher", 2, "Мария", "Учитель"),
                (ADMIN_ID, "support-admin", 2, "Иван", "Администратор"),
            ),
        )
        season_id = int(
            connection.execute(
                "INSERT INTO seasons "
                "(public_id, code, title, starts_on, ends_on, session_expires_on, "
                "status, created_at, updated_at) VALUES "
                "('support-season', 'support', 'Support', '2026-09-01', "
                "'2027-05-31', '2027-08-10', 'active', ?, ?) RETURNING id",
                (now, now),
            ).fetchone()["id"]
        )
        course_id = int(
            connection.execute(
                "INSERT INTO courses "
                "(public_id, season_id, code, name, subject_code, status, sort_order, "
                "accent_key, created_at, updated_at) VALUES "
                "('support-course', ?, 'math', 'Математика', 'math', 'active', 1, "
                "'math', ?, ?) RETURNING id",
                (season_id, now, now),
            ).fetchone()["id"]
        )
        for group_id, public_id, short_code, title, order in (
            ("support-a", "support-group-a", "a", "Начинающие", 1),
            ("support-b", "support-group-b", "b", "Продолжающие", 2),
        ):
            connection.execute(
                "INSERT INTO groups "
                "(group_id, short_code, public_name, sort_order, is_active, is_default, "
                "allow_self_switch, is_system, score_weight, public_id, course_id, "
                "status, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, ?, 'active', ?, ?)",
                (group_id, short_code, title, order, public_id, course_id, now, now),
            )
        enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(public_id, student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) VALUES "
                "('support-enrollment', ?, ?, 'support-a', 'online', 'active', ?, ?) "
                "RETURNING id",
                (STUDENT_ID, course_id, now, now),
            ).fetchone()["id"]
        )
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, 'support-b', ?, ?, ?)",
            (enrollment_id, course_id, access_from, now, now),
        )
        course_lesson_id = int(
            connection.execute(
                "INSERT INTO course_lessons "
                "(public_id, course_id, lesson_number, created_at, updated_at) "
                "VALUES ('support-course-lesson', ?, 41, ?, ?) RETURNING id",
                (course_id, now, now),
            ).fetchone()["id"]
        )
        for index, group_id in enumerate(("support-a", "support-b"), start=1):
            group_lesson_id = int(
                connection.execute(
                    "INSERT INTO group_lessons "
                    "(public_id, course_lesson_id, course_id, group_id, "
                    "cycle_anchor_date, business_timezone, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, '2026-09-28', 'Europe/Moscow', 'active', ?, ?) "
                    "RETURNING id",
                    (
                        f"support-group-lesson-{index}",
                        course_lesson_id,
                        course_id,
                        group_id,
                        now,
                        now,
                    ),
                ).fetchone()["id"]
            )
            source_id = int(
                connection.execute(
                    "INSERT INTO content_sources "
                    "(public_id, group_lesson_id, kind, logical_filename, "
                    "source_encoding, created_at) VALUES (?, ?, 'condition', ?, 'utf-8', ?) "
                    "RETURNING id",
                    (
                        f"support-source-{index}",
                        group_lesson_id,
                        f"support-{index}.tex",
                        now,
                    ),
                ).fetchone()["id"]
            )
            revision_id = int(
                connection.execute(
                    "INSERT INTO content_revisions "
                    "(public_id, source_id, revision_number, source_sha256, latex_text, "
                    "parser_version, status, canonical_json, diagnostics_json, "
                    "provenance_json, created_at) VALUES "
                    "(?, ?, 1, ?, 'problem', 'support-test', 'ready', '{}', '[]', '{}', ?) "
                    "RETURNING id",
                    (
                        f"support-revision-{index}",
                        source_id,
                        str(index) * 64,
                        now,
                    ),
                ).fetchone()["id"]
            )
            problem_id = int(
                connection.execute(
                    "INSERT INTO problems "
                    "(public_id, group_id, lesson, prob, item, title, prob_text, prob_type, "
                    "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                    "congrat, synonyms) VALUES (?, ?, 41, 1, '', ?, '', 2, 0, '', '', "
                    "'', '', '', '') RETURNING id",
                    (f"support-problem-{index}", group_id, f"Задача {index}"),
                ).fetchone()["id"]
            )
            connection.execute(
                "INSERT INTO content_problem_matches "
                "(content_revision_id, source_ordinal, source_item, problem_id, decision, "
                "resolved_by_user_id, resolved_at, diagnostics_json, created_at) "
                "VALUES (?, 1, '1', ?, 'manual_match', ?, ?, '[]', ?)",
                (revision_id, problem_id, ADMIN_ID, now, now),
            )
            connection.execute(
                "INSERT INTO problem_revisions "
                "(problem_id, content_revision_id, source_ordinal, source_item, "
                "display_number, title, normalized_title, problem_type, answer_type, "
                "answer_config_json, attempt_policy_json, config_version, created_at, "
                "created_by_user_id) VALUES "
                "(?, ?, 1, '1', ?, ?, ?, 2, 0, '{}', '{}', 1, ?, ?)",
                (
                    problem_id,
                    revision_id,
                    f"41.{index}",
                    f"Задача {index}",
                    f"задача {index}",
                    now,
                    ADMIN_ID,
                ),
            )

    factory.run_write(seed)
    return SupportFixture(factory=factory, repository=repository, clock=clock)


def _create_problem_command(**changes) -> CreateSupportThreadCommand:
    values = {
        "student_user_id": STUDENT_ID,
        "kind": "problem_question",
        "group_lesson_public_id": "support-group-lesson-1",
        "problem_public_id": "support-problem-1",
        "text": "Почему здесь можно считать эти случаи одинаковыми?",
        "client_created_at": NOW - timedelta(minutes=1),
        "idempotency_key": "support-create-problem",
    }
    values.update(changes)
    return CreateSupportThreadCommand(**values)


@pytest.mark.asyncio
async def test_private_thread_is_idempotent_and_keeps_one_chronological_dialogue(
    support_fixture,
):
    fixture = support_fixture
    created = await fixture.repository.create_student_thread(_create_problem_command())
    replay = await fixture.repository.create_student_thread(_create_problem_command())

    assert replay == created
    assert created.thread_public_id == "support-thread-test-1"
    assert created.student_public_id == "support-student"
    assert created.course_public_id == "support-course"
    assert created.group_public_id == "support-group-a"
    assert created.problem_public_id == "support-problem-1"
    assert created.version == 1
    assert [entry.author_kind for entry in created.entries] == ["student"]

    fixture.clock.value += timedelta(minutes=1)
    student_reply = await fixture.repository.append_student_entry(
        AppendStudentSupportEntryCommand(
            student_user_id=STUDENT_ID,
            thread_public_id=created.thread_public_id,
            text="Я попробовал расписать подробнее.",
            client_created_at=fixture.clock.value,
            idempotency_key="support-student-reply",
        )
    )
    fixture.clock.value += timedelta(minutes=1)
    teacher_reply = await fixture.repository.append_staff_entry(
        AppendStaffSupportEntryCommand(
            staff_user_id=TEACHER_ID,
            author_kind="teacher",
            thread_public_id=created.thread_public_id,
            text="Посмотрите, что происходит после перестановки двух случаев.",
            client_created_at=fixture.clock.value,
            idempotency_key="support-teacher-reply",
            scope=GROUP_A_SCOPE,
        )
    )
    exact_replay = await fixture.repository.append_staff_entry(
        AppendStaffSupportEntryCommand(
            staff_user_id=TEACHER_ID,
            author_kind="teacher",
            thread_public_id=created.thread_public_id,
            text="Посмотрите, что происходит после перестановки двух случаев.",
            client_created_at=fixture.clock.value,
            idempotency_key="support-teacher-reply",
            scope=GROUP_A_SCOPE,
        )
    )

    assert student_reply.version == 2
    assert teacher_reply.version == 3
    assert exact_replay == teacher_reply
    assert [entry.author_kind for entry in teacher_reply.entries] == [
        "student",
        "student",
        "teacher",
    ]
    assert teacher_reply.entries[-1].author_public_id == "support-teacher"
    assert teacher_reply.entries[-1].channel == "staff"
    stored = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT (SELECT count(*) FROM support_threads) AS threads, "
            "(SELECT count(*) FROM support_entries) AS entries"
        ).fetchone()
    )
    assert stored == {"threads": 1, "entries": 3}


@pytest.mark.asyncio
async def test_owner_and_staff_scope_are_enforced_without_closing_or_assignment(
    support_fixture,
):
    fixture = support_fixture
    created = await fixture.repository.create_student_thread(_create_problem_command())

    with pytest.raises(SupportForbidden):
        await fixture.repository.get_student_thread(
            student_user_id=OTHER_STUDENT_ID,
            thread_public_id=created.thread_public_id,
        )
    with pytest.raises(SupportForbidden):
        await fixture.repository.get_staff_thread(
            thread_public_id=created.thread_public_id,
            scope=GROUP_B_SCOPE,
        )
    with pytest.raises(SupportForbidden):
        await fixture.repository.append_staff_entry(
            AppendStaffSupportEntryCommand(
                staff_user_id=TEACHER_ID,
                author_kind="teacher",
                thread_public_id=created.thread_public_id,
                text="Ответ вне разрешённой группы",
                client_created_at=NOW,
                idempotency_key="support-wrong-scope",
                scope=GROUP_B_SCOPE,
            )
        )

    visible = await fixture.repository.get_staff_thread(
        thread_public_id=created.thread_public_id,
        scope=SupportStaffScope(course_public_ids=frozenset({"support-course"})),
    )
    assert visible == created

    fixture.clock.value += timedelta(minutes=1)
    allowed_reply = AppendStaffSupportEntryCommand(
        staff_user_id=TEACHER_ID,
        author_kind="teacher",
        thread_public_id=created.thread_public_id,
        text="Ответ до отзыва доступа",
        client_created_at=fixture.clock.value,
        idempotency_key="support-before-scope-revoke",
        scope=GROUP_A_SCOPE,
    )
    await fixture.repository.append_staff_entry(allowed_reply)
    with pytest.raises(SupportForbidden):
        await fixture.repository.append_staff_entry(
            AppendStaffSupportEntryCommand(
                staff_user_id=allowed_reply.staff_user_id,
                author_kind=allowed_reply.author_kind,
                thread_public_id=allowed_reply.thread_public_id,
                text=allowed_reply.text,
                client_created_at=allowed_reply.client_created_at,
                idempotency_key=allowed_reply.idempotency_key,
                scope=GROUP_B_SCOPE,
            )
        )


@pytest.mark.asyncio
async def test_general_and_problem_targets_require_current_access_and_exact_scope(
    support_fixture,
):
    fixture = support_fixture
    general = await fixture.repository.create_student_thread(
        CreateSupportThreadCommand(
            student_user_id=STUDENT_ID,
            kind="general",
            group_lesson_public_id="support-group-lesson-2",
            problem_public_id=None,
            text="Где посмотреть время следующего разбора?",
            client_created_at=NOW,
            idempotency_key="support-create-general",
        )
    )
    assert general.kind == "general"
    assert general.group_public_id == "support-group-b"
    assert general.problem_public_id is None

    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE course_group_access SET valid_to = ?, updated_at = ?, version = version + 1 "
            "WHERE group_id = 'support-b' AND valid_to IS NULL",
            (
                _timestamp(NOW),
                _timestamp(NOW),
            ),
        )
    )
    fixture.clock.value += timedelta(minutes=1)
    with pytest.raises(SupportForbidden):
        await fixture.repository.create_student_thread(
            CreateSupportThreadCommand(
                student_user_id=STUDENT_ID,
                kind="general",
                group_lesson_public_id="support-group-lesson-2",
                problem_public_id=None,
                text="Новый вопрос после отзыва доступа",
                client_created_at=fixture.clock.value,
                idempotency_key="support-after-revoke",
            )
        )

    historical = await fixture.repository.get_student_thread(
        student_user_id=STUDENT_ID,
        thread_public_id=general.thread_public_id,
    )
    assert historical == general
    with pytest.raises(SupportNotFound):
        await fixture.repository.create_student_thread(
            _create_problem_command(
                group_lesson_public_id="support-group-lesson-1",
                problem_public_id="support-problem-2",
                idempotency_key="support-cross-lesson-problem",
            )
        )


@pytest.mark.asyncio
async def test_idempotency_key_rejects_changed_payload_and_concurrent_replay(
    support_fixture,
):
    fixture = support_fixture
    created = await fixture.repository.create_student_thread(_create_problem_command())
    with pytest.raises(SupportIdempotencyConflict):
        await fixture.repository.create_student_thread(
            _create_problem_command(text="Другой вопрос с тем же ключом")
        )

    command = AppendStudentSupportEntryCommand(
        student_user_id=STUDENT_ID,
        thread_public_id=created.thread_public_id,
        text="Один и тот же повторяемый ответ",
        client_created_at=NOW,
        idempotency_key="support-concurrent-reply",
    )
    first, second = await asyncio.gather(
        fixture.repository.append_student_entry(command),
        fixture.repository.append_student_entry(command),
    )
    assert first == second
    assert first.version == 2
    assert len(first.entries) == 2


def test_sqlite_guards_reject_cross_owner_entries_and_mutation(support_fixture):
    fixture = support_fixture
    created = asyncio.run(
        fixture.repository.create_student_thread(_create_problem_command())
    )

    def violate(connection: sqlite3.Connection) -> None:
        thread_id = int(
            connection.execute(
                "SELECT id FROM support_threads WHERE public_id = ?",
                (created.thread_public_id,),
            ).fetchone()["id"]
        )
        with pytest.raises(sqlite3.IntegrityError, match="outside thread scope"):
            connection.execute(
                "INSERT INTO support_entries "
                "(public_id, thread_id, author_kind, author_user_id, text, channel, "
                "server_received_at, created_at) VALUES "
                "('support-entry-wrong-owner', ?, 'student', ?, 'Чужой вопрос', "
                "'pwa', ?, ?)",
                (thread_id, OTHER_STUDENT_ID, _timestamp(NOW), _timestamp(NOW)),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE support_entries SET text = 'Переписано' WHERE thread_id = ?",
                (thread_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
            connection.execute("DELETE FROM support_threads WHERE id = ?", (thread_id,))

    fixture.factory.run_write(violate)
