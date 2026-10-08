"""Current credit vs review workload; docs/lesson-statistics.md."""

import pytest
from pwa_tests.integration import test_review_queue_http_api as review_support
from db_methods.pwa.statistics_reports import report_facts
from pwa_tests.integration import test_content_http_api as support

content_http = support.content_http


async def test_reports_without_model_repeat_reviews_and_pending(content_http):
    fixture = content_http
    public_id, _ = await support._prepare_published_test_problem(
        fixture, problem_type=2
    )

    def seed(db):
        p = db.execute(
            "SELECT * FROM problems WHERE public_id=?", (public_id,)
        ).fetchone()
        for verdict in (0, 14, 14):
            db.execute(
                "INSERT INTO results(student_id,problem_id,group_id,lesson,ts,verdict,res_type) VALUES(?,?,?,?,?, ?,2)",
                (
                    support.STUDENT_USER_ID,
                    p["id"],
                    p["group_id"],
                    p["lesson"],
                    "2026-09-28T10:00:00",
                    verdict,
                ),
            )
        db.execute(
            "INSERT INTO written_tasks_queue(student_id,problem_id,ts,cur_status) VALUES(?,?,?,0)",
            (support.STUDENT_USER_ID, p["id"], "2026-09-28T11:00:00"),
        )

    fixture.factory.run_write(seed)

    async def get(path):
        response = await fixture.client.get(
            path, cookies=support._cookie(fixture, "admin"), headers=support._headers()
        )
        assert response.status == 200, await response.text()
        assert response.headers["Cache-Control"] == "no-store"
        return await response.json()

    summary = await get("/staff/api/v1/statistics/summary?courseId=c-1")
    row = next(r for r in summary["lessons"] if r["lessonNumber"] == 41)
    assert (row["writtenChecked"], row["writtenPending"], row["writtenTotal"]) == (
        3,
        1,
        4,
    )
    assert row["allPlus"] == row["writtenPlus"] == 0.5
    matrix = await get(
        "/staff/api/v1/statistics/plus-table?courseId=c-1&groupId=g-1&lessonNumber=41"
    )
    assert len(matrix["rows"]) == 1
    assert matrix["rows"][0]["total"] == 0.5
    assert matrix["rows"][0]["cells"][0]["pending"] is True
    assert matrix["rows"][0]["cells"][0]["source"] == "written"
    default = await get("/staff/api/v1/statistics/plus-table?courseId=c-1")
    assert default["lessonNumber"] == 41
    assert default["selectedGroupId"] == "g-1"


@pytest.mark.parametrize(
    "path,status",
    [
        ("summary?courseId=c-999", 403),
        ("plus-table?groupId=g-999", 403),
        ("plus-table?lessonNumber=-1", 422),
        ("summary?lessonNumber=1", 422),
    ],
)
async def test_report_validation_and_scope(content_http, path, status):
    response = await content_http.client.get(
        "/staff/api/v1/statistics/" + path,
        cookies=support._cookie(content_http, "admin"),
        headers=support._headers(),
    )
    assert response.status == status


async def test_report_corrected_test_does_not_resurrect_credit(content_http):
    await support.test_staff_rechecks_all_attempts_after_published_metadata_correction(
        content_http
    )
    response = await content_http.client.get(
        "/staff/api/v1/statistics/summary?courseId=c-1",
        cookies=support._cookie(content_http, "admin"),
        headers=support._headers(),
    )
    assert response.status == 200
    row = next(r for r in (await response.json())["lessons"] if r["lessonNumber"] == 41)
    assert row["students"] == 1
    assert row["allPlus"] == 0


review_http = review_support.review_http


async def test_completed_review_evidence_is_not_pending_and_ledger_is_not_doubled(
    review_http,
):
    f = review_http
    queue = f.queue_public_ids[0]
    claim = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/claim",
        json={"schemaVersion": 1},
        cookies=review_support._cookie(f, "full"),
        headers=review_support._headers(unsafe=True),
    )
    assert claim.status == 200
    payload = review_support._complete_payload((await claim.json())["lease"])
    response = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/complete",
        json=payload,
        cookies=review_support._cookie(f, "full"),
        headers=review_support._headers(unsafe=True),
    )
    assert response.status == 200, await response.text()
    response = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/complete",
        json=payload,
        cookies=review_support._cookie(f, "full"),
        headers=review_support._headers(unsafe=True),
    )
    assert response.status == 200
    facts = f.factory.run_read(lambda c: report_facts(c, 1))
    assert len(facts[3]) == 1
    assert facts[4] == []


@pytest.mark.parametrize("kind", ["summary", "plus-table"])
async def test_report_requires_staff_and_scopes_teacher(content_http, kind):
    f = content_http
    endpoint = "/staff/api/v1/statistics/" + kind
    anonymous = await f.client.get(endpoint, headers=support._headers())
    assert anonymous.status == 401
    student = await f.client.get(
        endpoint, headers=support._headers(), cookies=support._cookie(f, "student")
    )
    assert student.status == 401
    teacher = await f.client.get(
        endpoint + "?courseId=c-1&groupId=g-1",
        headers=support._headers(),
        cookies=support._cookie(f, "teacher"),
    )
    assert teacher.status == 200
    forbidden = await f.client.get(
        endpoint + "?courseId=c-1&groupId=g-2",
        headers=support._headers(),
        cookies=support._cookie(f, "teacher"),
    )
    assert forbidden.status == 403
