"""Repository contracts for private, unassigned Student support threads."""

from __future__ import annotations

import asyncio
import json
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
from helpers.consts import USER_TYPE


def test_question_document_is_focused_and_only_published_condition():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE lesson_publications(group_lesson_id, revision_id, kind, state);
        CREATE TABLE content_revisions(id, status);
        CREATE TABLE problem_revisions(problem_id, content_revision_id, source_ordinal);
        CREATE TABLE content_derivatives(id, revision_id, kind, invalidated_at, content_text);
        INSERT INTO lesson_publications VALUES (1, 1, 'condition', 'published');
        INSERT INTO content_revisions VALUES (1, 'ready');
        INSERT INTO problem_revisions VALUES (7, 1, 2);
    """)
    document = {"introduction": [], "problems": [{"ordinal": 1}, {"ordinal": 2}]}
    connection.execute(
        "INSERT INTO content_derivatives VALUES (1, 1, ?, NULL, ?)",
        ("web_ast", json.dumps(document)),
    )
    target = {"problem_id": 7, "group_lesson_id": 1}
    result = PwaSupportThreadRepository._problem_document(connection, target)
    assert result["problems"] == [{"ordinal": 2}]
    connection.execute("UPDATE lesson_publications SET kind = 'solution'")
    assert PwaSupportThreadRepository._problem_document(connection, target) is None
    connection.execute(
        "UPDATE lesson_publications SET kind = 'condition', state = 'hidden'"
    )
    assert PwaSupportThreadRepository._problem_document(connection, target) is None
    connection.close()


NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
STUDENT_ID = -956_001
OTHER_STUDENT_ID = -956_002
TEACHER_ID = -956_003
ADMIN_ID = -956_004
GLOBAL_ADMIN_ID = -956_005


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


GROUP_A_SCOPE = SupportStaffScope(group_public_ids=frozenset({"g-5"}))
GROUP_B_SCOPE = SupportStaffScope(group_public_ids=frozenset({"g-6"}))


@pytest.fixture()
def support_fixture(tmp_path) -> SupportFixture:
    database_path = tmp_path / "support.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    clock = MutableClock(NOW)
    repository = PwaSupportThreadRepository(factory, clock=clock)
    now = _timestamp(NOW)
    access_from = _timestamp(NOW - timedelta(days=30))

    def seed(connection: sqlite3.Connection) -> None:
        connection.executemany(
            "INSERT INTO users (id, type, name, surname) VALUES (?, ?, ?, ?)",
            (
                (STUDENT_ID, 1, "Анна", "Белова"),
                (OTHER_STUDENT_ID, 1, "Борис", "Ветров"),
                (TEACHER_ID, 2, "Мария", "Учитель"),
                (ADMIN_ID, 2, "Иван", "Администратор"),
            ),
        )
        season_id = int(
            connection.execute(
                "INSERT INTO seasons "
                "(code, title, starts_on, ends_on, session_expires_on, "
                "status, created_at, updated_at) VALUES "
                "('support', 'Support', '2026-09-01', "
                "'2027-05-31', '2027-08-10', 'active', ?, ?) RETURNING id",
                (now, now),
            ).fetchone()["id"]
        )
        course_id = int(
            connection.execute(
                "INSERT INTO courses "
                "(season_id, code, name, subject_code, status, sort_order, "
                "accent_key, created_at, updated_at) VALUES "
                "(?, 'math', 'Математика', 'math', 'active', 1, "
                "'math', ?, ?) RETURNING id",
                (season_id, now, now),
            ).fetchone()["id"]
        )
        for group_id, short_code, title, order in (
            ("support-a", "a", "Начинающие", 1),
            ("support-b", "b", "Продолжающие", 2),
        ):
            connection.execute(
                "INSERT INTO groups "
                "(group_id, short_code, public_name, sort_order, is_active, is_default, "
                "allow_self_switch, is_system, score_weight, course_id, "
                "status, created_at, updated_at) VALUES "
                "(?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, 'active', ?, ?)",
                (group_id, short_code, title, order, course_id, now, now),
            )
        enrollment_id = int(
            connection.execute(
                "INSERT INTO course_enrollments "
                "(student_user_id, course_id, active_group_id, "
                "attendance_mode, status, created_at, updated_at) VALUES "
                "(?, ?, 'support-a', 'online', 'active', ?, ?) "
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
                "(course_id, lesson_number, created_at, updated_at) "
                "VALUES (?, 41, ?, ?) RETURNING id",
                (course_id, now, now),
            ).fetchone()["id"]
        )
        for index, group_id in enumerate(("support-a", "support-b"), start=1):
            group_lesson_id = int(
                connection.execute(
                    "INSERT INTO group_lessons "
                    "(course_lesson_id, course_id, group_id, "
                    "cycle_anchor_date, business_timezone, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, '2026-09-28', 'Europe/Moscow', 'active', ?, ?) "
                    "RETURNING id",
                    (
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
                    "(group_lesson_id, kind, logical_filename, "
                    "source_encoding, created_at) VALUES (?, 'condition', ?, 'utf-8', ?) "
                    "RETURNING id",
                    (
                        group_lesson_id,
                        f"support-{index}.tex",
                        now,
                    ),
                ).fetchone()["id"]
            )
            revision_id = int(
                connection.execute(
                    "INSERT INTO content_revisions "
                    "(source_id, revision_number, source_sha256, latex_text, "
                    "parser_version, status, canonical_json, diagnostics_json, "
                    "provenance_json, created_at) VALUES "
                    "(?, 1, ?, 'problem', 'support-test', 'ready', '{}', '[]', '{}', ?) "
                    "RETURNING id",
                    (
                        source_id,
                        str(index) * 64,
                        now,
                    ),
                ).fetchone()["id"]
            )
            problem_id = int(
                connection.execute(
                    "INSERT INTO problems "
                    "(group_id, lesson, prob, item, title, prob_text, prob_type, "
                    "ans_type, ans_validation, validation_error, cor_ans, wrong_ans, "
                    "congrat, synonyms) VALUES (?, 41, 1, '', ?, '', 2, 0, '', '', "
                    "'', '', '', '') RETURNING id",
                    (group_id, f"Задача {index}"),
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
        "group_lesson_public_id": "gl-1",
        "problem_public_id": "p-1",
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
    assert created.thread_public_id == "sup-1"
    assert created.student_public_id == "u--956001"
    assert created.course_public_id == "c-1"
    assert created.group_public_id == "g-5"
    assert created.problem_public_id == "p-1"
    assert created.problem_number == "41a.1"
    assert created.problem_document is None
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
    assert teacher_reply.entries[-1].author_public_id == "u--956003"
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
        scope=SupportStaffScope(course_public_ids=frozenset({"c-1"})),
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
            group_lesson_public_id="gl-2",
            problem_public_id=None,
            text="Где посмотреть время следующего разбора?",
            client_created_at=NOW,
            idempotency_key="support-create-general",
        )
    )
    assert general.kind == "general"
    assert general.group_public_id == "g-6"
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
                group_lesson_public_id="gl-2",
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
                group_lesson_public_id="gl-1",
                problem_public_id="p-2",
                idempotency_key="support-cross-lesson-problem",
            )
        )


@pytest.mark.asyncio
async def test_student_thread_list_is_newest_first_cursor_backed_and_historical(
    support_fixture,
):
    fixture = support_fixture
    problem = await fixture.repository.create_student_thread(_create_problem_command())
    fixture.clock.value += timedelta(minutes=1)
    general = await fixture.repository.create_student_thread(
        CreateSupportThreadCommand(
            student_user_id=STUDENT_ID,
            kind="general",
            group_lesson_public_id="gl-2",
            problem_public_id=None,
            text="Когда следующий разбор?",
            client_created_at=fixture.clock.value,
            idempotency_key="support-list-general",
        )
    )
    fixture.clock.value += timedelta(minutes=1)
    await fixture.repository.append_staff_entry(
        AppendStaffSupportEntryCommand(
            staff_user_id=TEACHER_ID,
            author_kind="teacher",
            thread_public_id=general.thread_public_id,
            text="В воскресенье в 17:00.",
            client_created_at=fixture.clock.value,
            idempotency_key="support-list-answer",
            scope=GROUP_B_SCOPE,
        )
    )

    first = await fixture.repository.list_student_threads(
        student_user_id=STUDENT_ID, page_size=1
    )
    assert [item.thread_public_id for item in first.items] == [general.thread_public_id]
    assert first.items[0].reply_state == "awaiting_student"
    assert first.items[0].entry_count == 2
    assert first.items[0].latest_text_excerpt == "В воскресенье в 17:00."
    assert first.next_cursor == general.thread_public_id

    second = await fixture.repository.list_student_threads(
        student_user_id=STUDENT_ID,
        cursor=first.next_cursor,
        page_size=1,
    )
    assert [item.thread_public_id for item in second.items] == [
        problem.thread_public_id
    ]
    assert second.items[0].reply_state == "awaiting_staff"
    assert second.next_cursor is None

    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE course_group_access SET valid_to = ?, updated_at = ?, version = version + 1 "
            "WHERE group_id = 'support-b' AND valid_to IS NULL",
            (_timestamp(fixture.clock.value), _timestamp(fixture.clock.value)),
        )
    )
    historical = await fixture.repository.list_student_threads(
        student_user_id=STUDENT_ID
    )
    assert [item.thread_public_id for item in historical.items] == [
        general.thread_public_id,
        problem.thread_public_id,
    ]
    with pytest.raises(SupportNotFound):
        await fixture.repository.list_student_threads(
            student_user_id=OTHER_STUDENT_ID,
            cursor=general.thread_public_id,
        )


@pytest.mark.asyncio
async def test_staff_inbox_derives_reply_state_and_enforces_scope_and_filters(
    support_fixture,
):
    fixture = support_fixture
    problem = await fixture.repository.create_student_thread(_create_problem_command())
    fixture.clock.value += timedelta(minutes=1)
    general = await fixture.repository.create_student_thread(
        CreateSupportThreadCommand(
            student_user_id=STUDENT_ID,
            kind="general",
            group_lesson_public_id="gl-2",
            problem_public_id=None,
            text="Когда следующий разбор?",
            client_created_at=fixture.clock.value,
            idempotency_key="support-inbox-general",
        )
    )
    fixture.clock.value += timedelta(minutes=1)
    await fixture.repository.append_staff_entry(
        AppendStaffSupportEntryCommand(
            staff_user_id=TEACHER_ID,
            author_kind="teacher",
            thread_public_id=general.thread_public_id,
            text="В воскресенье в 17:00.",
            client_created_at=fixture.clock.value,
            idempotency_key="support-inbox-answer",
            scope=GROUP_B_SCOPE,
        )
    )

    group_a_inbox = await fixture.repository.list_staff_threads(scope=GROUP_A_SCOPE)
    assert [item.thread_public_id for item in group_a_inbox.items] == [
        problem.thread_public_id
    ]
    assert group_a_inbox.items[0].reply_state == "awaiting_staff"

    course_scope = SupportStaffScope(course_public_ids=frozenset({"c-1"}))
    all_threads = await fixture.repository.list_staff_threads(
        scope=course_scope, state="all"
    )
    assert [item.thread_public_id for item in all_threads.items] == [
        general.thread_public_id,
        problem.thread_public_id,
    ]
    awaiting_student = await fixture.repository.list_staff_threads(
        scope=course_scope,
        state="awaiting_student",
        kind="general",
        group_public_id="g-6",
    )
    assert [item.thread_public_id for item in awaiting_student.items] == [
        general.thread_public_id
    ]
    assert (
        await fixture.repository.list_staff_threads(
            scope=GROUP_B_SCOPE, state="awaiting_staff"
        )
    ).items == ()


@pytest.mark.asyncio
async def test_invalidation_targets_use_active_owner_accounts_and_current_staff_scope(
    support_fixture,
):
    fixture = support_fixture
    created = await fixture.repository.create_student_thread(_create_problem_command())
    now = _timestamp(fixture.clock.value)
    valid_from = _timestamp(fixture.clock.value - timedelta(days=1))

    def seed_accounts(connection: sqlite3.Connection) -> None:
        connection.execute(
            "INSERT INTO users (id, type, name, surname) "
            "VALUES (?, ?, 'Галина', 'Администратор')",
            (GLOBAL_ADMIN_ID, int(USER_TYPE.ADMIN)),
        )
        connection.executemany(
            "INSERT INTO auth_accounts "
            "(audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'synthetic-test', ?, 'test-hash', ?, 'active', ?, ?)",
            (
                (
                    "student",
                    "support-student",
                    "support-student",
                    1,
                    "telegram_token",
                    STUDENT_ID,
                    now,
                    now,
                ),
                (
                    "staff",
                    "support-teacher",
                    "support-teacher",
                    None,
                    "password",
                    TEACHER_ID,
                    now,
                    now,
                ),
                (
                    "staff",
                    "support-admin",
                    "support-admin",
                    None,
                    "password",
                    ADMIN_ID,
                    now,
                    now,
                ),
                (
                    "staff",
                    "support-global-admin",
                    "support-global-admin",
                    None,
                    "password",
                    GLOBAL_ADMIN_ID,
                    now,
                    now,
                ),
            ),
        )
        course_id = int(
            connection.execute(
                "SELECT id FROM courses WHERE public_id = 'c-1'"
            ).fetchone()["id"]
        )
        connection.executemany(
            "INSERT INTO staff_scopes "
            "(staff_user_id, course_id, group_id, role, valid_from, created_at, updated_at) "
            "VALUES (?, ?, ?, 'teacher', ?, ?, ?)",
            (
                (TEACHER_ID, course_id, "support-a", valid_from, now, now),
                (ADMIN_ID, course_id, "support-b", valid_from, now, now),
            ),
        )

    fixture.factory.run_write(seed_accounts)
    targets = await fixture.repository.invalidation_targets(
        thread_public_id=created.thread_public_id
    )
    assert targets.student_account_public_ids == ("a-1",)
    assert targets.staff_account_public_ids == (
        "a-2",
        "a-4",
    )

    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE staff_scopes SET valid_to = ?, updated_at = ?, version = version + 1 "
            "WHERE staff_user_id = ? AND valid_to IS NULL",
            (now, now, TEACHER_ID),
        )
    )
    after_revoke = await fixture.repository.invalidation_targets(
        thread_public_id=created.thread_public_id
    )
    assert after_revoke.staff_account_public_ids == ("a-4",)


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
                "(thread_id, author_kind, author_user_id, text, channel, "
                "server_received_at, created_at) VALUES "
                "(?, 'student', ?, 'Чужой вопрос', "
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
