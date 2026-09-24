# ruff: noqa: F811 -- pytest fixtures imported for registration
import pytest
from aiohttp import FormData

from db_methods.pwa.lesson_statistics import course_facts
from db_methods.pwa import course_catalog
from db_methods.pwa.auth import PwaAuthRepository
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from pwa_tests.integration.test_content_http_api import (
    content_http,  # noqa: F401 -- shared real-HTTP fixture
    _cookie,
    _headers,
    _prepare_published_test_problem,
    _timestamp,
    TEACHER_USER_ID,
)


async def enter(fixture, who="teacher"):
    response = await fixture.client.post(
        "/staff/api/v1/testing/session",
        cookies=_cookie(fixture, who),
        headers=_headers(unsafe=True),
    )
    assert response.status == 200, await response.text()
    cookie = {
        COOKIE_POLICY[AuthAudience.STUDENT].access_name: response.cookies[
            COOKIE_POLICY[AuthAudience.STUDENT].access_name
        ].value
    }
    fixture.client.session.cookie_jar.clear()
    return cookie


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["teacher", "admin"])
async def test_staff_testing_identity_reuse_and_scope_revocation(content_http, who):
    f = content_http
    before = f.factory.run_read(
        lambda c: course_catalog.list_groups(
            c,
            course_ids=tuple(
                r["id"] for r in c.execute("SELECT id FROM courses").fetchall()
            ),
        )
    )
    cookie = await enter(f, who)
    after = f.factory.run_read(
        lambda c: course_catalog.list_groups(
            c,
            course_ids=tuple(
                r["id"] for r in c.execute("SELECT id FROM courses").fetchall()
            ),
        )
    )
    assert before == after
    login = f.factory.run_read(
        lambda c: c.execute(
            "SELECT username FROM auth_accounts WHERE provisioning_source='staff_testing'"
        ).fetchone()["username"]
    )
    assert (
        await PwaAuthRepository(f.factory).find_account_for_login(
            audience=AuthAudience.STUDENT, login=login
        )
        is None
    )
    me = await f.client.get(
        "/student/api/v1/auth/me", cookies=cookie, headers=_headers()
    )
    assert me.status == 200, await me.text()
    assert (await me.json())["principal"]["isStaffTesting"] is True
    news = await f.client.get(
        "/student/api/v1/news", cookies=cookie, headers=_headers()
    )
    assert news.status == 200, await news.text()
    account = (await me.json())["principal"]["accountId"]
    again = await enter(f, who)
    me2 = await f.client.get(
        "/student/api/v1/auth/me", cookies=again, headers=_headers()
    )
    assert (await me2.json())["principal"]["accountId"] == account
    if who == "teacher":
        f.factory.run_write(
            lambda c: c.execute(
                "DELETE FROM staff_scopes WHERE staff_user_id=?", (TEACHER_USER_ID,)
            )
        )
        revoked = await f.client.get(
            "/student/api/v1/auth/me", cookies=cookie, headers=_headers()
        )
        assert revoked.status == 401


@pytest.mark.asyncio
async def test_student_cannot_create_testing_identity(content_http):
    f = content_http
    response = await f.client.post(
        "/staff/api/v1/testing/session",
        cookies=_cookie(f, "student"),
        headers=_headers(unsafe=True),
    )
    assert response.status in (401, 403)
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) n FROM staff_test_students"
            ).fetchone()["n"]
        )
        == 0
    )


@pytest.mark.asyncio
async def test_teacher_test_answer_is_real_and_excluded_from_statistics(content_http):
    f = content_http
    problem, revision = await _prepare_published_test_problem(f)
    cookie = await enter(f)
    response = await f.client.post(
        f"/student/api/v1/problems/{problem}/test-attempts",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "05b22616-0c18-49a4-8363-6d0a18ae49fd",
            "displayAnswer": "7",
            "clientCreatedAt": _timestamp(),
            "problemRevision": {"conditionRevisionId": revision, "configVersion": 1},
        },
        cookies=cookie,
        headers=_headers(unsafe=True),
    )
    assert response.status == 201, await response.text()
    assert (await response.json())["verdict"] is not None
    course_id = f.factory.run_read(
        lambda c: c.execute(
            "SELECT course_id FROM group_lessons WHERE public_id=?", (f.group_lesson_a,)
        ).fetchone()["course_id"]
    )
    _, results, pending = f.factory.run_read(lambda c: course_facts(c, course_id))
    assert results == [] and pending == []


@pytest.mark.asyncio
async def test_teacher_photo_full_review_cycle(content_http):
    f = content_http
    problem, revision = await _prepare_published_test_problem(f, problem_type=2)
    cookie = await enter(f)
    draft = await f.client.post(
        f"/student/api/v1/problems/{problem}/thread/entries",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "05b22616-0c18-49a4-8363-6d0a18ae49fa",
            "text": "Тестовая работа",
            "clientCreatedAt": _timestamp(),
            "pasteEvidence": {
                "pasteCount": 0,
                "pastedCharacterCount": 0,
                "lastPastedAt": None,
            },
            "problemRevision": {"conditionRevisionId": revision, "configVersion": 1},
        },
        cookies=cookie,
        headers=_headers(unsafe=True),
    )
    assert draft.status == 201, await draft.text()
    entry = (await draft.json())["entry"]["entryId"]
    form = FormData()
    for key, value in {
        "schemaVersion": "1",
        "idempotencyKey": "05b22616-0c18-49a4-8363-6d0a18ae49fb",
        "expectedEntryVersion": "1",
        "expectedThreadVersion": "1",
        "ordinal": "0",
    }.items():
        form.add_field(key, value)
    form.add_field(
        "asset",
        b"synthetic-heic-source",
        filename="test.heic",
        content_type="image/heic",
    )
    upload = await f.client.post(
        f"/student/api/v1/thread-entries/{entry}/attachments",
        data=form,
        cookies=cookie,
        headers=_headers(unsafe=True),
    )
    assert upload.status == 201, await upload.text()
    attachment = (await upload.json())["entry"]["attachments"][0]["attachmentId"]
    submitted = await f.client.post(
        f"/student/api/v1/thread-entries/{entry}/submit",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "05b22616-0c18-49a4-8363-6d0a18ae49fc",
            "expectedEntryVersion": 2,
            "expectedThreadVersion": 2,
            "attachmentIds": [attachment],
        },
        cookies=cookie,
        headers=_headers(unsafe=True),
    )
    assert submitted.status == 200, await submitted.text()
    queue = f.factory.run_read(
        lambda c: c.execute(
            "SELECT q.public_id FROM written_tasks_queue q JOIN users u ON u.id=q.student_id WHERE u.type=512"
        ).fetchone()["public_id"]
    )
    claim = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/claim",
        json={"schemaVersion": 1},
        cookies=_cookie(f, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert claim.status == 200, await claim.text()
    lease = (await claim.json())["lease"]
    evidence = {b["queueId"]: b for b in lease["evidenceBranches"]}
    branches = [
        {
            "queueId": b["queueId"],
            "leaseVersion": b["leaseVersion"],
            "threadId": evidence[b["queueId"]]["thread"]["threadId"],
            "threadVersion": evidence[b["queueId"]]["thread"]["threadVersion"],
            "evidence": [
                {"entryId": e["entryId"], "entryVersion": e["entryVersion"]}
                for e in evidence[b["queueId"]]["thread"]["entries"]
            ],
        }
        for b in lease["branches"]
    ]
    complete = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/complete",
        json={
            "schemaVersion": 1,
            "claimToken": lease["claimToken"],
            "idempotencyKey": "staff-testing-complete",
            "verdict": 15,
            "comment": "Проверено",
            "confirmWithoutComment": False,
            "branches": branches,
            "annotations": [],
            "internalReactionId": None,
        },
        cookies=_cookie(f, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert complete.status == 200, await complete.text()
    history = await f.client.get(
        f"/student/api/v1/problems/{problem}/thread", cookies=cookie, headers=_headers()
    )
    assert history.status == 200, await history.text()
    assert (await history.json())["thread"]["reviews"][0]["verdict"] == 15
    review = (await history.json())["thread"]["reviews"][0]
    corrected = await f.client.post(
        f"/staff/api/v1/reviews/{review['reviewId']}/correction",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "staff-testing-correction",
            "verdict": 11,
            "comment": "Исправлено",
            "confirmWithoutComment": False,
        },
        cookies=_cookie(f, "teacher"),
        headers=_headers(unsafe=True),
    )
    assert corrected.status == 200, await corrected.text()
    course_id = f.factory.run_read(
        lambda c: c.execute(
            "SELECT course_id FROM group_lessons WHERE public_id=?", (f.group_lesson_a,)
        ).fetchone()["course_id"]
    )
    _, results, pending = f.factory.run_read(lambda c: course_facts(c, course_id))
    assert results == [] and pending == []


@pytest.mark.asyncio
async def test_testing_catalog_group_scope_and_owner_deactivation(content_http):
    f = content_http
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE staff_scopes SET group_id='content-a' WHERE staff_user_id=?",
            (TEACHER_USER_ID,),
        )
    )
    catalog = await f.client.get(
        "/staff/api/v1/testing/courses",
        cookies=_cookie(f, "teacher"),
        headers=_headers(),
    )
    assert catalog.status == 200, await catalog.text()
    assert len((await catalog.json())["courses"]) == 1
    assert len((await catalog.json())["courses"][0]["groups"]) == 1
    cookie = await enter(f)
    grants = f.factory.run_read(
        lambda c: c.execute(
            "SELECT a.group_id FROM course_group_access a JOIN course_enrollments e ON e.id=a.enrollment_id "
            "JOIN staff_test_students t ON t.student_user_id=e.student_user_id"
        ).fetchall()
    )
    assert [g["group_id"] for g in grants] == ["content-a"]
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE auth_accounts SET status='disabled' WHERE audience='staff' AND linked_user_id=?",
            (TEACHER_USER_ID,),
        )
    )
    denied = await f.client.get(
        "/student/api/v1/auth/me", cookies=cookie, headers=_headers()
    )
    assert denied.status == 401
