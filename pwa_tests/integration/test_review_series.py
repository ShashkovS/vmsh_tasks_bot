"""Series history uses evidence identities, not individual corrections."""

from datetime import timedelta
import json
import pytest

from pwa_tests.integration import test_review_queue_repository as fixtures
from db_methods.pwa import review_series
from models.pwa.review_corrections import (
    ReviewCorrectionCommand,
    correct_written_review,
)
from helpers.consts import USER_TYPE

review_queue_fixture = fixtures.review_queue_fixture


@pytest.mark.asyncio
async def test_history_own_only_deduplicates_corrections_and_follows_current(
    review_queue_fixture,
):
    f = review_queue_fixture
    lease = await f.repository.claim(
        queue_public_id=f.queue_public_ids[0],
        teacher_user_id=fixtures.TEACHER_ONE_ID,
        scope=fixtures.ALL_GROUPS_SCOPE,
    )
    original = await f.repository.complete(fixtures._complete_command(lease))
    corrected = await correct_written_review(
        f.factory,
        ReviewCorrectionCommand(
            source_review_public_id=original.review_public_id,
            reviewer_user_id=fixtures.TEACHER_ONE_ID,
            reviewer_type=int(USER_TYPE.TEACHER),
            scope=fixtures.ALL_GROUPS_SCOPE,
            idempotency_key="series-correction",
            verdict=14,
            comment="Исправлено",
            confirm_without_comment=False,
        ),
        now=fixtures.NOW + timedelta(minutes=1),
    )

    def read(c):
        page = review_series.history(
            c, fixtures.ALL_GROUPS_SCOPE, fixtures.TEACHER_ONE_ID, "p-1"
        )
        assert len(page["items"]) == 1 and page["nextCursor"] is None
        assert page["items"][0]["materialKey"] == "se-2,se-3"
        detail = review_series.current_detail(
            c,
            fixtures.ALL_GROUPS_SCOPE,
            fixtures.TEACHER_ONE_ID,
            page["items"][0]["reviewId"],
        )
        assert detail["review"]["reviewId"] == corrected.review_public_id
        assert detail["comment"] == "Исправлено"
        assert (
            review_series.history(
                c, fixtures.ALL_GROUPS_SCOPE, fixtures.TEACHER_TWO_ID, "p-1"
            )["items"]
            == []
        )
        assert (
            review_series.current_detail(
                c,
                fixtures.ALL_GROUPS_SCOPE,
                fixtures.TEACHER_TWO_ID,
                original.review_public_id,
            )
            is None
        )
        assert (
            review_series.history(
                c, fixtures.ALL_GROUPS_SCOPE, fixtures.TEACHER_ONE_ID, "p-999"
            )["items"]
            == []
        )

    f.factory.run_read(read)


def test_condition_preserves_context_and_selects_evidence_revision(
    review_queue_fixture,
):
    f = review_queue_fixture
    document = {
        "materialKind": "condition",
        "introduction": [{"text": "Общий контекст"}],
        "problems": [
            {"ordinal": 1, "blocks": [{"text": "Условие"}]},
            {"ordinal": 2, "blocks": [{"text": "Другая задача"}]},
        ],
    }
    f.factory.run_write(
        lambda c: c.execute(
            """INSERT INTO content_derivatives
      (revision_id,kind,renderer_version,content_text,sha256,provenance_json,created_at)
      VALUES(1,'web_ast','series-test',?,?,'{}',?)""",
            (json.dumps(document), "a" * 64, fixtures._timestamp(fixtures.NOW)),
        )
    )

    def read(c):
        result = review_series.condition(c, fixtures.ALL_GROUPS_SCOPE, "p-1", "se-2")[
            "document"
        ]
        assert result["introduction"] == document["introduction"]
        assert result["problems"][0]["blocks"] == document["problems"][0]["blocks"]
        assert result["problems"][0]["taskReference"] == "41а.411"
        assert len(result["problems"]) == 1
        assert (
            review_series.condition(c, fixtures.ALL_GROUPS_SCOPE, "p-1", "se-3")[
                "document"
            ]
            is None
        )

    f.factory.run_read(read)


def test_condition_requires_current_scope_and_has_explicit_empty_state(
    review_queue_fixture,
):
    f = review_queue_fixture

    def read(c):
        result = review_series.condition(c, fixtures.ALL_GROUPS_SCOPE, "p-1", "se-2")
        assert result["label"] == "41а.1 · Задача 1"
        assert result["document"] is None
        assert review_series.condition(c, fixtures.ReviewStaffScope(), "p-1") is None

    f.factory.run_read(read)


@pytest.mark.asyncio
async def test_history_twenty_item_cursor_is_stable_across_corrections(
    review_queue_fixture,
):
    f = review_queue_fixture
    for index in range(23):
        if index == 0:
            queue = f.queue_public_ids[0]
        else:

            def enqueue(c):
                active = c.execute(
                    "SELECT id FROM submission_threads WHERE problem_id=1 AND student_user_id=? AND status<>'closed'",
                    (fixtures.STUDENT_ID,),
                ).fetchone()
                if active:
                    thread = active["id"]
                    c.execute(
                        "UPDATE submission_threads SET status='awaiting_review',version=version+1 WHERE id=?",
                        (thread,),
                    )
                else:
                    thread = c.execute(
                        """INSERT INTO submission_threads
                  (student_user_id,problem_id,condition_revision_id,status,latest_entry_at,created_at,updated_at)
                  SELECT student_user_id,problem_id,condition_revision_id,'awaiting_review',?,?,?
                  FROM submission_threads WHERE public_id='st-1' RETURNING id""",
                        (fixtures._timestamp(fixtures.NOW),) * 3,
                    ).fetchone()["id"]
                c.execute(
                    """INSERT INTO submission_entries
                  (thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at)
                  SELECT ?,problem_revision_id,'student',author_user_id,'pwa','submission','submitted',?,?
                  FROM submission_entries WHERE public_id='se-2'""",
                    (
                        thread,
                        f"Новая посылка {index}",
                        fixtures._timestamp(fixtures.NOW),
                    ),
                )
                return c.execute(
                    """INSERT INTO written_tasks_queue(ts,student_id,problem_id,cur_status,updated_at)
                  SELECT ?,student_user_id,problem_id,0,? FROM submission_threads WHERE public_id='st-1' RETURNING public_id""",
                    (
                        fixtures._timestamp(fixtures.NOW),
                        fixtures._timestamp(fixtures.NOW),
                    ),
                ).fetchone()["public_id"]

            queue = f.factory.run_write(enqueue)
        lease = await f.repository.claim(
            queue_public_id=queue,
            teacher_user_id=fixtures.TEACHER_ONE_ID,
            scope=fixtures.ALL_GROUPS_SCOPE,
        )
        await f.repository.complete(
            fixtures._complete_command(lease, idempotency_key=f"page-{index}")
        )
    first = f.factory.run_read(
        lambda c: review_series.history(
            c, fixtures.ALL_GROUPS_SCOPE, fixtures.TEACHER_ONE_ID, "p-1"
        )
    )
    assert len(first["items"]) == 20 and first["nextCursor"] is not None
    # Correct the oldest material after page one: its anchor must not jump to
    # the front and disappear from the next page.
    await correct_written_review(
        f.factory,
        ReviewCorrectionCommand(
            source_review_public_id="r-1",
            reviewer_user_id=fixtures.TEACHER_ONE_ID,
            reviewer_type=int(USER_TYPE.TEACHER),
            scope=fixtures.ALL_GROUPS_SCOPE,
            idempotency_key="late-correction",
            verdict=17,
            comment="Поправлено",
            confirm_without_comment=False,
        ),
        now=fixtures.NOW + timedelta(minutes=1),
    )
    second = f.factory.run_read(
        lambda c: review_series.history(
            c,
            fixtures.ALL_GROUPS_SCOPE,
            fixtures.TEACHER_ONE_ID,
            "p-1",
            first["nextCursor"],
        )
    )
    assert len(second["items"]) == 3 and second["nextCursor"] is None
    assert len({i["materialKey"] for i in first["items"] + second["items"]}) == 23
