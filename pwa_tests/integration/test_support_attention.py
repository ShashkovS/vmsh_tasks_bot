"""Per-answer receipts and navigation from vmshpwa/docs/question-attention.md."""

from dataclasses import replace
from datetime import timedelta

import pytest

from db_methods.pwa.support import (
    AppendStaffSupportEntryCommand,
    SupportForbidden,
    SupportNotFound,
)
from models.pwa import support_attention as domain
from pwa_tests.integration import test_support_thread_repository as support
from pwa_tests.integration.test_phase6_support_thread_migration import _apply, _rollback

support_fixture = support.support_fixture


async def reply(fixture, thread, key="reply", scope=support.GROUP_A_SCOPE):
    fixture.clock.value += timedelta(seconds=1)
    return await fixture.repository.append_staff_entry(
        AppendStaffSupportEntryCommand(
            staff_user_id=support.TEACHER_ID,
            author_kind="teacher",
            thread_public_id=thread.thread_public_id,
            text="Ответ",
            client_created_at=fixture.clock.value,
            idempotency_key=key,
            scope=scope,
        )
    )


def acknowledge(fixture, thread, ids, student_id=support.STUDENT_ID):
    return fixture.factory.run_write(
        lambda c: domain.acknowledge(
            c,
            student_user_id=student_id,
            thread_public_id=thread.thread_public_id,
            entry_ids=tuple(ids),
            session_id=None,
            now=support._timestamp(fixture.clock.value),
        )
    )


async def test_receipts_are_individual_idempotent_and_do_not_read_a_racing_reply(
    support_fixture,
):
    f = support_fixture
    thread = await f.repository.create_student_thread(support._create_problem_command())
    assert domain.thread_attention(thread.entries)["attentionState"] == "awaiting_reply"
    first = await reply(f, thread)
    first_id = first.entries[-1].entry_public_id
    second = await reply(f, thread, "reply-two")
    assert domain.thread_attention(second.entries)["unreadReplyCount"] == 2
    receipt = acknowledge(f, thread, [first_id])
    assert acknowledge(f, thread, [first_id]) == receipt
    loaded = await f.repository.get_student_thread(
        student_user_id=support.STUDENT_ID, thread_public_id=thread.thread_public_id
    )
    assert loaded.version == second.version
    assert domain.thread_attention(loaded.entries) == {
        "attentionState": "unread_reply",
        "unreadReplyCount": 1,
        "firstUnreadEntryId": second.entries[-1].entry_public_id,
    }
    summary = (
        await f.repository.list_student_threads(student_user_id=support.STUDENT_ID)
    ).items[0]
    assert summary.unread_reply_count == 1
    assert summary.first_unread_entry_id == second.entries[-1].entry_public_id


async def test_read_validation_is_atomic_and_owner_bound(support_fixture):
    f = support_fixture
    thread = await f.repository.create_student_thread(support._create_problem_command())
    answered = await reply(f, thread)
    staff_id = answered.entries[-1].entry_public_id
    for ids, owner, exception in (
        ([staff_id], support.OTHER_STUDENT_ID, SupportForbidden),
        ([staff_id, "sue-missing"], support.STUDENT_ID, SupportNotFound),
        ([staff_id, thread.entries[0].entry_public_id], support.STUDENT_ID, ValueError),
    ):
        with pytest.raises(exception):
            acknowledge(f, thread, ids, owner)
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) n FROM support_entry_reads"
            ).fetchone()["n"]
        )
        == 0
    )
    other = await f.repository.create_student_thread(
        support._create_problem_command(
            kind="general", problem_public_id=None, idempotency_key="general"
        )
    )
    with pytest.raises(SupportNotFound):
        acknowledge(f, other, [staff_id])


async def test_system_entries_do_not_override_human_waiting_state(support_fixture):
    thread = await support_fixture.repository.create_student_thread(
        support._create_problem_command()
    )
    system = replace(thread.entries[0], author_kind="system", author_public_id=None)
    assert (
        domain.thread_attention((*thread.entries, system))["attentionState"]
        == "awaiting_reply"
    )


async def test_migration_backfills_existing_replies_without_touching_dialogue(
    support_fixture,
):
    f = support_fixture
    thread = await f.repository.create_student_thread(support._create_problem_command())
    answered = await reply(f, thread)
    path = f.factory.database_path
    migration = {"0107.pwa_support_entry_reads"}
    _rollback(path, migration)
    _apply(path, migration)
    loaded = await f.repository.get_student_thread(
        student_user_id=support.STUDENT_ID, thread_public_id=thread.thread_public_id
    )
    assert loaded.version == answered.version
    assert loaded.entries[-1].read_at is not None
    assert loaded.entries[0].read_at is None
    _rollback(path, migration)
    _apply(path, migration)
    assert (
        f.factory.run_read(
            lambda c: c.execute("PRAGMA integrity_check").fetchone()["integrity_check"]
        )
        == "ok"
    )
    fresh = await reply(f, thread, "post-migration")
    assert fresh.entries[-1].read_at is None


def publish(c, lesson_id=1, revision_id=1):
    now = support._timestamp(support.NOW)
    c.execute(
        "INSERT INTO content_derivatives(revision_id,kind,renderer_version,content_text,sha256,provenance_json,created_at) VALUES(?,'web_ast','test','{}',?,'{}',?)",
        (revision_id, "a" * 64, now),
    )
    c.execute(
        "INSERT INTO lesson_publications(group_lesson_id,kind,revision_id,state,published_at,created_by_user_id,published_by_user_id,created_at,updated_at) VALUES(?,'condition',?,'published',?,?,?,?,?)",
        (lesson_id, revision_id, now, support.ADMIN_ID, support.ADMIN_ID, now, now),
    )


async def test_global_attention_requires_current_access_and_published_problem(
    support_fixture,
):
    f = support_fixture
    thread = await f.repository.create_student_thread(support._create_problem_command())
    answered = await reply(f, thread)

    def attention():
        return f.factory.run_read(
            lambda c: domain.next_attention(
                c,
                student_user_id=support.STUDENT_ID,
                now=support._timestamp(f.clock.value),
                after_thread_id=thread.thread_public_id,
            )
        )

    assert attention()["unreadTaskCount"] == 0

    f.factory.run_write(publish)
    assert attention() == {
        "unreadTaskCount": 1,
        "nextTarget": {
            "threadId": thread.thread_public_id,
            "courseId": "c-1",
            "groupId": "g-5",
            "groupLessonId": "gl-1",
            "problemId": "p-1",
            "firstUnreadEntryId": answered.entries[-1].entry_public_id,
        },
    }
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE course_enrollments SET status='paused', version=version+1 WHERE student_user_id=?",
            (support.STUDENT_ID,),
        )
    )
    assert attention()["unreadTaskCount"] == 0


async def test_attention_cycles_by_oldest_unread_reply_across_groups(support_fixture):
    f = support_fixture
    first = await f.repository.create_student_thread(support._create_problem_command())
    second = await f.repository.create_student_thread(
        support._create_problem_command(
            group_lesson_public_id="gl-2",
            problem_public_id="p-2",
            idempotency_key="other-group",
        )
    )
    await reply(f, second, "earliest", scope=support.GROUP_B_SCOPE)
    await reply(f, first, "later")
    f.factory.run_write(lambda c: (publish(c), publish(c, 2, 2)))

    def attention(after=None):
        return f.factory.run_read(
            lambda c: domain.next_attention(
                c,
                student_user_id=support.STUDENT_ID,
                now=support._timestamp(f.clock.value),
                after_thread_id=after,
            )
        )

    assert attention()["unreadTaskCount"] == 2
    assert attention()["nextTarget"]["threadId"] == second.thread_public_id
    assert (
        attention(second.thread_public_id)["nextTarget"]["threadId"]
        == first.thread_public_id
    )
    assert (
        attention(first.thread_public_id)["nextTarget"]["threadId"]
        == second.thread_public_id
    )
    assert attention("sup-missing")["nextTarget"]["threadId"] == second.thread_public_id
    # A group grant expires independently of the active group.
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE course_group_access SET valid_to=?, version=version+1",
            (support._timestamp(f.clock.value),),
        )
    )
    assert attention()["unreadTaskCount"] == 1
    assert attention()["nextTarget"]["threadId"] == first.thread_public_id
