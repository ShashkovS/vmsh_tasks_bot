"""Read-only calibration and cohort exports; ai-review-assistant.md."""

from pwa_tests.integration import test_review_queue_http_api as fixtures
from pwa_tests.integration.test_ai_review_http import token, call, install_image, counts
from pwa_tests.integration.test_review_sheet_http import post, detail, payload

review_http = fixtures.review_http


async def export(f, secret, tool, data):
    response = await call(f, secret, tool, data)
    assert response.status == 200, await response.text()
    return await response.json()


def add_student_work(connection, student_id, *, existing=False):
    if not existing:
        connection.execute(
            "INSERT INTO users(id,type,name,surname) VALUES(?,1,'Новый','Ученик')",
            (student_id,),
        )
    thread = connection.execute(
        """INSERT INTO submission_threads(student_user_id,problem_id,condition_revision_id,
        status,created_at,updated_at,latest_entry_at,version)
        SELECT ?,problem_id,condition_revision_id,'awaiting_review',created_at,updated_at,latest_entry_at,1
        FROM submission_threads WHERE public_id='st-1' RETURNING id""",
        (student_id,),
    ).fetchone()["id"]
    connection.execute(
        """INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,
        author_user_id,channel,entry_kind,state,text,server_received_at,version)
        SELECT ?,problem_revision_id,'student',?,'pwa','submission','submitted','Ещё решение',server_received_at,1
        FROM submission_entries WHERE public_id='se-1'""",
        (thread, student_id),
    )


async def test_bulk_reads_entries_not_latest_student_result_and_includes_full_dialogue(
    review_http,
):
    f = review_http
    secret = (await token(f))["secret"]
    before = await export(
        f, secret, "get_problem_submissions", {"problemId": "p-1", "status": "pending"}
    )
    assert before["submissionCounts"] == {
        "pending": 1,
        "reviewed": 0,
        "superseded": 0,
        "unknown": 0,
    }
    assert before["items"][0]["suggestionCaseId"] == "st-1"
    response = await post(
        f, "/staff/api/v1/review/sheet/st-1/complete", payload(await detail(f))
    )
    assert response.status == 200, await response.text()

    def resubmit(c):
        add_student_work(c, fixtures.STUDENT_ID, existing=True)
        c.execute(
            "UPDATE submission_entries SET text='Новая попытка',version=version+1 WHERE id=(SELECT max(id) FROM submission_entries)"
        )
        c.execute(
            """INSERT INTO written_tasks_queue(student_id,problem_id,ts,cur_status,updated_at)
            SELECT student_user_id,problem_id,'2026-10-18T18:00:00Z',0,'2026-10-18T18:00:00Z'
            FROM submission_threads ORDER BY id DESC LIMIT 1"""
        )
        add_student_work(c, fixtures.STUDENT_ID + 100)

    f.factory.run_write(resubmit)
    unchanged = counts(f)
    for status, count in [("pending", 2), ("reviewed", 1), ("all", 3)]:
        data = await export(
            f, secret, "get_problem_submissions", {"problemId": "p-1", "status": status}
        )
        assert data["selectedSubmissionCount"] == count
        assert data["submissionCounts"]["pending"] == 2
        assert data["submissionCounts"]["reviewed"] == 1
        for work in data["items"]:
            assert all(e["problemId"] == "p-1" for e in work["submissions"])
            if status != "all":
                assert all(e["status"] == status for e in work["submissions"])
        first = data["items"][0]
        assert any(e["text"] == "Простыня: принято" for e in first["dialogue"])
        assert any(e["text"] == "Новая попытка" for e in first["dialogue"])
    assert counts(f) == unchanged


async def test_history_comments_filters_legacy_dedup_and_no_ai_or_internal_notes(
    review_http,
):
    f = review_http
    secret = (await token(f))["secret"]
    d = await detail(f)
    response = await post(
        f,
        "/staff/api/v1/review/sheet/st-1/complete",
        payload(d, internalReactionId=100),
    )
    assert response.status == 200, await response.text()
    f.factory.run_write(
        lambda c: c.execute(
            """INSERT INTO written_tasks_discussions(student_id,problem_id,teacher_id,ts,text)
        VALUES(?,1,?,'2026-10-04 11:59:00','Старый комментарий преподавателя')""",
            (fixtures.STUDENT_ID, fixtures.FULL_TEACHER_ID),
        )
    )
    lesson = f.factory.run_read(
        lambda c: c.execute(
            "SELECT public_id FROM group_lessons ORDER BY id LIMIT 1"
        ).fetchone()["public_id"]
    )
    task = await export(f, secret, "list_review_comments", {"problemId": "p-1"})
    texts = [e["text"] for e in task["items"]]
    assert "Простыня: принято" in texts and "Старый комментарий преподавателя" in texts
    whole = await export(f, secret, "list_review_comments", {"lessonId": lesson})
    assert len([e for e in whole["items"] if e["text"] == "Простыня: принято"]) == 1
    assert (
        whole["items"]
        == (
            await export(
                f,
                secret,
                "list_review_comments",
                {"lessonId": lesson, "problemId": "p-1"},
            )
        )["items"]
    )
    assert all(e["authorKind"] in {"teacher", "admin"} for e in whole["items"])
    assert not any(e["kind"] in {"reaction", "ai"} for e in whole["items"])
    assert (await call(f, secret, "list_review_comments", {})).status == 422


async def test_export_pagination_detects_changes_and_scope_is_checked_on_every_read(
    review_http,
):
    f = review_http
    secret = (await token(f))["secret"]
    f.factory.run_write(lambda c: add_student_work(c, fixtures.STUDENT_ID + 100))
    query = {"problemId": "p-1", "status": "pending", "pageSize": 1}
    first = await export(f, secret, "get_problem_submissions", query)
    assert first["total"] == 2 and first["nextCursor"]
    next_query = {**query, "cursor": first["nextCursor"]}
    second = await export(f, secret, "get_problem_submissions", next_query)
    assert second["nextCursor"] is None
    assert first["items"][0]["caseId"] != second["items"][0]["caseId"]
    assert first["selectionSnapshot"] == second["selectionSnapshot"]
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE submission_entries SET text='Изменён ответ',version=version+1 WHERE public_id='se-1'"
        )
    )
    assert (await call(f, secret, "get_problem_submissions", next_query)).status == 409
    partial = (await token(f, "partial"))["secret"]
    assert (
        await call(f, partial, "get_problem_submissions", {"problemId": "p-2"})
    ).status == 403
    empty = await export(f, partial, "list_review_comments", {"problemId": "p-1"})
    assert empty["total"] == 0
    for changes in [
        {"status": "wrong"},
        {"pageSize": 0},
        {"pageSize": 21},
        {"pageSize": True},
    ]:
        assert (
            await call(f, secret, "get_problem_submissions", {**query, **changes})
        ).status == 422


async def test_history_images_share_snapshot_guards_and_history_cases_cannot_upload(
    review_http,
):
    f = review_http
    image = await install_image(f)
    secret = (await token(f))["secret"]
    data = await export(f, secret, "get_problem_submissions", {"problemId": "p-1"})
    work = data["items"][0]
    request = {
        "caseId": work["caseId"],
        "snapshot": work["snapshot"],
        "imageId": "attachment:sa-1",
    }
    result = await call(f, secret, "get_review_image", request)
    assert result.status == 200, await result.text()
    assert await result.read() == image
    assert (
        await call(
            f, secret, "get_review_image", {**request, "imageId": "attachment:sa-999"}
        )
    ).status == 404
    context = await export(f, secret, "get_review_context", {"caseId": work["caseId"]})
    assert context["snapshot"] == work["snapshot"]
    response = await call(
        f,
        secret,
        "submit_ai_suggestion",
        {
            "caseId": work["caseId"],
            "snapshot": work["snapshot"],
            "idempotencyKey": "forbidden-history",
            "source": "test",
            "comment": "text",
        },
    )
    assert response.status == 404
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE submission_entries SET text='Изменён',version=version+1 WHERE public_id='se-1'"
        )
    )
    assert (await call(f, secret, "get_review_image", request)).status == 409


async def test_legacy_only_history_is_readable_and_unknown_state_is_explicit(
    review_http,
):
    f = review_http
    secret = (await token(f))["secret"]

    def seed(c):
        c.execute(
            "INSERT INTO users(id,type,name,surname) VALUES(999111,1,'Архив','Ученик')"
        )
        c.executemany(
            """INSERT INTO written_tasks_discussions(student_id,problem_id,teacher_id,ts,text)
            VALUES(999111,1,?,'2026-10-04 11:59:00',?)""",
            [(None, "Старое решение"), (fixtures.FULL_TEACHER_ID, "Старый разбор")],
        )

    f.factory.run_write(seed)
    data = await export(f, secret, "get_problem_submissions", {"problemId": "p-1"})
    legacy = next(w for w in data["items"] if w["student"]["studentId"] == "u-999111")
    assert legacy["suggestionCaseId"] is None
    assert legacy["submissions"][0]["status"] == "unknown"
    assert data["submissionCounts"]["unknown"] == 1
    comments = await export(f, secret, "list_review_comments", {"problemId": "p-1"})
    assert any(e["text"] == "Старый разбор" for e in comments["items"])
    assert (
        await export(
            f,
            secret,
            "get_problem_submissions",
            {"problemId": "p-1", "status": "reviewed"},
        )
    )["total"] == 0


async def test_comments_all_pages_legacy_image_and_current_scope(review_http, tmp_path):
    from apps.pwa_api.student_results_routes import LEGACY_SOLUTIONS_ROOT

    f = review_http
    secret = (await token(f))["secret"]
    from pathlib import Path

    image = Path("pwa_tests/fixtures/student-results-photo.webp").read_bytes()
    (tmp_path / "teacher.webp").write_bytes(image)
    f.client.server.app[LEGACY_SOLUTIONS_ROOT] = tmp_path

    def seed(c):
        for number in range(51):
            c.execute(
                """INSERT INTO written_tasks_discussions(student_id,problem_id,teacher_id,ts,text,attach_path)
                VALUES(?,1,?,'2026-10-04 11:59:00',?,?)""",
                (
                    fixtures.STUDENT_ID,
                    fixtures.FULL_TEACHER_ID,
                    f"Комментарий {number}",
                    "teacher.webp" if number == 0 else None,
                ),
            )

    f.factory.run_write(seed)
    query = {"problemId": "p-1"}
    first = await export(f, secret, "list_review_comments", query)
    assert first["total"] == 51 and len(first["items"]) == 50
    second = await export(
        f, secret, "list_review_comments", {**query, "cursor": first["nextCursor"]}
    )
    assert len(second["items"]) == 1 and second["nextCursor"] is None
    assert len({e["id"] for e in first["items"] + second["items"]}) == 51
    comment = next(e for e in first["items"] if e["images"])
    result = await call(
        f,
        secret,
        "get_review_image",
        {
            "caseId": comment["caseId"],
            "snapshot": comment["snapshot"],
            "imageId": comment["images"][0]["imageId"],
        },
    )
    assert result.status == 200 and await result.read() == image
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE written_tasks_discussions SET text='Исправлено' WHERE text='Комментарий 0'"
        )
    )
    assert (
        await call(
            f, secret, "list_review_comments", {**query, "cursor": first["nextCursor"]}
        )
    ).status == 409
    f.factory.run_write(lambda c: c.execute("DELETE FROM staff_scopes"))
    assert (
        await call(f, secret, "get_review_context", {"caseId": comment["caseId"]})
    ).status == 403
