"""Own PWA ledger/authorization; vmshpwa/docs/review-contribution.md."""

import pytest

from db_methods.pwa.review_contribution import contribution_rows
from pwa_tests.integration import test_review_queue_http_api as fixtures
from pwa_tests.integration.test_review_sheet_http import detail, payload, get, post

review_http = fixtures.review_http
PATH = "/staff/api/v1/review/my-contribution"


@pytest.mark.asyncio
async def test_contribution_roles_scope_and_filters(review_http):
    f = review_http
    f.factory.run_write(
        lambda c: c.execute(
            "INSERT INTO lesson_publications(group_lesson_id,kind,revision_id,state,published_at,created_at,updated_at,created_by_user_id,published_by_user_id) "
            "SELECT s.group_lesson_id,s.kind,r.id,'published',r.created_at,r.created_at,r.created_at,?,? "
            "FROM content_sources s JOIN content_revisions r ON r.source_id=s.id",
            (fixtures.ADMIN_ID, fixtures.ADMIN_ID),
        )
    )
    empty = await get(f, PATH)
    assert empty.status == 200, await empty.text()
    data = await empty.json()
    assert data["allTime"]["total"] == 0
    assert data["lesson"] is not None
    assert data["requestId"]
    assert (await get(f, PATH, "admin")).status == 200
    for query in (
        "teacher=u-1",
        "lesson=-1",
        "lesson=x",
        "course=c-1&course=c-2",
        "groupLesson=gl-1&lesson=1",
    ):
        assert (await get(f, PATH + "?" + query)).status == 422
    assert (await get(f, PATH + "?course=c-999")).status == 403
    assert (await get(f, PATH + "?groupLesson=gl-999")).status == 403
    denied = await f.client.get(PATH, headers=fixtures._headers())
    assert denied.status == 401
    for cookies in (fixtures._student_cookie(f), fixtures._family_cookie(f)):
        denied = await f.client.get(PATH, cookies=cookies, headers=fixtures._headers())
        assert denied.status in (401, 403)


@pytest.mark.asyncio
async def test_own_written_checks_replay_and_correction_chain(review_http):
    f = review_http
    d = await detail(f)
    saved = await post(f, "/staff/api/v1/review/sheet/st-1/complete", payload(d))
    assert saved.status == 200, await saved.text()
    review = (await saved.json())["review"]["reviewId"]
    replay = await post(f, "/staff/api/v1/review/sheet/st-1/complete", payload(d))
    assert replay.status == 200
    data = await (await get(f, PATH)).json()
    assert data["allTime"]["total"] == data["allTime"]["plus"] == 1
    assert (await (await get(f, PATH, "admin")).json())["allTime"]["total"] == 0
    for index, verdict in enumerate((14, 16)):
        response = await post(
            f,
            f"/staff/api/v1/reviews/{review}/correction",
            {
                "schemaVersion": 1,
                "idempotencyKey": f"contribution-correction-{index}",
                "verdict": verdict,
                "comment": "Уточнение оценки",
                "confirmWithoutComment": False,
            },
            "admin" if index == 1 else "full",
        )
        assert response.status == 200, await response.text()
        review = (await response.json())["correction"]["reviewId"]
        data = await (await get(f, PATH)).json()
        assert data["allTime"]["total"] == 1
        assert data["allTime"]["plus"] == (verdict == 16)
    assert (
        len(
            f.factory.run_read(lambda c: contribution_rows(c, fixtures.FULL_TEACHER_ID))
        )
        == 1
    )


@pytest.mark.asyncio
async def test_oral_sources_are_unioned_test_students_excluded_and_undo_not_subtracted(
    review_http,
):
    f = review_http

    def seed(c):
        problem = c.execute("SELECT * FROM problems LIMIT 1").fetchone()
        args = (
            fixtures.STUDENT_ID,
            fixtures.FULL_TEACHER_ID,
            problem["group_id"],
            problem["lesson"],
        )
        conversation = c.execute(
            "INSERT INTO zoom_conversation(student_id,teacher_id,group_id,lesson,ts,pwa_idempotency_key) VALUES(?,?,?,?,'2026-11-16T12:00:00Z','personal-pwa') RETURNING id",
            args,
        ).fetchone()["id"]
        for verdict, kind, live, pwa_conversation in [
            (17, 3, True, conversation),
            (16, 4, True, None),
            (14, 3, False, conversation),
            (-32768, 4, True, None),
            (17, 3, False, None),
        ]:
            result = c.execute(
                "INSERT INTO results(student_id,teacher_id,problem_id,lesson,ts,verdict,res_type,zoom_conversation_id) VALUES(?,?,?,?,'2026-11-16T12:00:00Z',?,?,?) RETURNING id",
                (
                    fixtures.STUDENT_ID,
                    fixtures.FULL_TEACHER_ID,
                    problem["id"],
                    problem["lesson"],
                    verdict,
                    kind,
                    pwa_conversation,
                ),
            ).fetchone()["id"]
            if live:
                c.execute(
                    "INSERT INTO live_mark_results(result_id) VALUES(?)", (result,)
                )
        # live_mark_cells is deliberately not pointed at the saved marks: an undo
        # must not subtract their contribution, per the owner's explicit decision.

    f.factory.run_write(seed)
    data = await (await get(f, PATH)).json()
    assert data["allTime"]["total"] == 3
    assert data["allTime"]["plus"] == 2
    assert data["allTime"]["byKind"]["zoom"]["total"] == 2
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE users SET type=512 WHERE id=?", (fixtures.STUDENT_ID,)
        )
    )
    assert (await (await get(f, PATH)).json())["allTime"]["total"] == 0
