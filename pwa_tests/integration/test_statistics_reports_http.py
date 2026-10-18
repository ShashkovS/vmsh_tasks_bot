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


@pytest.mark.parametrize("kind", ["", "/summary", "/plus-table"])
async def test_statistics_cache_hit_and_forced_fresh_read(
    content_http, monkeypatch, kind
):
    from apps.pwa_api import staff_statistics_routes as routes

    f = content_http
    public_id, _ = await support._prepare_published_test_problem(f, problem_type=2)
    calls = []
    original = routes.main_snapshot if not kind else routes.report_snapshot

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        routes, "main_snapshot" if not kind else "report_snapshot", counted
    )
    url = "/staff/api/v1/statistics" + kind + "?courseId=c-1"

    async def get(refresh=False, request_id="cache.first"):
        response = await f.client.get(
            url + ("&refresh=1" if refresh else ""),
            cookies=support._cookie(f, "admin"),
            headers={**support._headers(), "X-Request-ID": request_id},
        )
        assert response.status == 200, await response.text()
        assert response.headers["Cache-Control"] == "no-store"
        return await response.json()

    first = await get()

    def seed(db):
        p = db.execute(
            "SELECT * FROM problems WHERE public_id=?", (public_id,)
        ).fetchone()
        db.execute(
            "INSERT INTO results(student_id,problem_id,group_id,lesson,ts,verdict,res_type) VALUES(?,?,?,?,?,17,2)",
            (
                support.STUDENT_USER_ID,
                p["id"],
                p["group_id"],
                p["lesson"],
                "2026-10-13T12:00:00",
            ),
        )

    f.factory.run_write(seed)  # Legacy writes are allowed to age out by TTL.
    cached = await get(request_id="cache.second")
    assert len(calls) == 1
    assert {k: v for k, v in first.items() if k != "requestId"} == {
        k: v for k, v in cached.items() if k != "requestId"
    }
    assert first["requestId"] != cached["requestId"]
    fresh = await get(refresh=True)
    assert len(calls) == 2
    if not kind:
        assert fresh["basicLesson"]["groups"][0]["problems"][0]["points"] == 1
    elif kind == "/summary":
        assert fresh["lessons"][0]["allPlus"] == 1
    else:
        assert fresh["rows"][0]["total"] == 1
    denied = await f.client.get(
        url + "&groupId=g-999",
        cookies=support._cookie(f, "admin"),
        headers=support._headers(),
    )
    assert denied.status == 403
    assert len(calls) == 2


async def test_owner_work_selectors_are_restricted_to_changed_children_and_recipient(
    content_http,
):
    from apps.pwa_app import owner_work_resources

    f = content_http

    def sibling(db):
        user_id = support.STUDENT_USER_ID + 1000
        db.execute(
            "INSERT INTO users(id,name,surname,type) VALUES (?,'Sibling','Test',1)",
            (user_id,),
        )
        db.execute(
            """INSERT INTO auth_accounts
            (id,audience,username,username_normalized,username_algorithm_version,
             provisioning_source,credential_kind,credential_hash,linked_user_id,status,created_at,updated_at)
            SELECT 5,'student','sibling','sibling',1,'synthetic-test',credential_kind,
                   credential_hash,?,'active',created_at,updated_at FROM auth_accounts WHERE id=1""",
            (user_id,),
        )
        db.execute(
            """INSERT INTO family_student_links(family_account_id,student_user_id,created_at,updated_at)
            SELECT 2,?,created_at,updated_at FROM auth_accounts WHERE id=2""",
            (user_id,),
        )

    f.factory.run_write(sibling)
    own, _ = await owner_work_resources(f.client.app, ("a-1",), recipient="a-2")
    assert own == [f"students/u-{support.STUDENT_USER_ID}/work"]
    both, _ = await owner_work_resources(f.client.app, ("a-1", "a-5"), recipient="a-2")
    assert set(both) == {
        f"students/u-{support.STUDENT_USER_ID}/work",
        f"students/u-{support.STUDENT_USER_ID + 1000}/work",
    }
    first, _ = await owner_work_resources(f.client.app, ("a-1", "a-5"), recipient="a-1")
    assert first == own
    unrelated, _ = await owner_work_resources(f.client.app, ("a-5",), recipient="a-1")
    assert unrelated == []
