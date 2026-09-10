"""Owner acceptance: vmshpwa/docs/live-marking.md, real authenticated aiohttp."""

import sqlite3
from uuid import uuid4


from pwa_tests.integration import test_content_http_api as support
from pwa_tests.integration.test_phase8_notification_core import (
    _apply,
    _rollback,
    _migrations,
)

content_http = support.content_http


def test_migration_up_down_up(tmp_path):
    path = tmp_path / "live.sqlite3"
    ids = {m.id for m in _migrations()}
    _apply(path, ids)
    with sqlite3.connect(path) as c:
        assert c.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert c.execute("SELECT count(*) FROM effective_results").fetchone() == (0,)
    _rollback(path, {"0087.pwa_live_marking"})
    _apply(path, {"0087.pwa_live_marking"})


async def call(fixture, method, path, body=None, role="teacher"):
    response = await getattr(fixture.client, method)(
        "/staff/api/v1/live-marking/" + path,
        **({} if body is None else {"json": body}),
        headers=support._headers(unsafe=method != "get"),
        cookies=support._cookie(fixture, role),
    )
    return response, await response.json()


async def setup(fixture):
    problem_id, _ = await support._prepare_published_test_problem(
        fixture, problem_type=3
    )
    response, catalog = await call(fixture, "get", "catalog")
    assert response.status == 200, catalog
    course_id = catalog["courses"][0]["courseId"]
    response, session = await call(
        fixture, "post", "sessions", dict(courseId=course_id, sessionId=uuid4().hex)
    )
    assert response.status == 200, session
    spec = dict(
        mode="zoom",
        contextId=session["sessionId"],
        studentId="u-903101",
        lessonId=fixture.group_lesson_a,
    )
    return problem_id, spec


async def operation(fixture, spec, problem_id, version, value="plus", **kwargs):
    payload = dict(
        kind="mark",
        operationId=uuid4().hex,
        context=spec,
        studentId="u-903101",
        problemId=problem_id,
        expectedVersion=version,
        value=value,
    )
    payload.update(kwargs)
    response, data = await call(fixture, "post", "operations", payload)
    return response, data, payload


async def test_live_mark_replay_conflict_and_multistep_undo(content_http):
    f = content_http
    problem_id, spec = await setup(f)
    response, first, payload = await operation(f, spec, problem_id, 0)
    assert response.status == 200, first
    assert first["state"]["symbol"] == "+"
    version = first["state"]["version"]
    response, replay = await call(f, "post", "operations", payload)
    assert response.status == 200, replay
    assert replay["replayed"]
    response, conflict, _ = await operation(f, spec, problem_id, 0, "minus")
    assert response.status == 409, conflict
    response, second, _ = await operation(f, spec, problem_id, version, "minus")
    assert response.status == 200, second
    assert second["state"]["symbol"] == "−"
    for op in (second, first):
        response, undone = await call(
            f,
            "post",
            "operations",
            dict(
                kind="undo",
                operationId=uuid4().hex,
                context=spec,
                targetOperationId=op["operationId"],
            ),
        )
        assert response.status == 200, undone
    from urllib.parse import urlencode

    response, cells = await call(f, "get", "cells?" + urlencode(spec))
    assert response.status == 200, cells
    assert cells["cells"][0]["verdict"] is None
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS value FROM results WHERE student_id=?",
                (support.STUDENT_USER_ID,),
            ).fetchone()["value"]
        )
        == 2
    )


async def test_live_mark_legacy_write_blocks_undo(content_http):
    f = content_http
    problem_id, spec = await setup(f)
    _, first, _ = await operation(f, spec, problem_id, 0)
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE results SET teacher_id=? WHERE student_id=?",
            (support.ADMIN_USER_ID, support.STUDENT_USER_ID),
        )
    )
    response, body = await call(
        f,
        "post",
        "operations",
        dict(
            kind="undo",
            operationId=uuid4().hex,
            context=spec,
            targetOperationId=first["operationId"],
        ),
    )
    assert response.status == 409, body


async def test_live_mark_prior_written_plus_reactions_praise_and_finish(content_http):
    f = content_http
    problem_id, spec = await setup(f)
    f.factory.run_write(
        lambda c: c.execute(
            """INSERT INTO results(student_id,problem_id,lesson,group_id,teacher_id,ts,verdict,res_type)
       SELECT ?,id,lesson,group_id,?,'2026-09-01',18,2 FROM problems WHERE public_id=?""",
            (support.STUDENT_USER_ID, support.ADMIN_USER_ID, problem_id),
        )
    )
    response, minus, _ = await operation(f, spec, problem_id, 1, "minus")
    assert response.status == 200, minus
    assert f.factory.run_read(
        lambda c: [
            r["verdict"]
            for r in c.execute(
                "SELECT verdict FROM effective_results WHERE student_id=?",
                (support.STUDENT_USER_ID,),
            )
        ]
    ) == [-1]
    response, visit = await call(f, "post", "visits", spec)
    assert response.status == 200, visit
    response, reaction = await call(
        f,
        "post",
        "operations",
        dict(
            kind="reaction",
            operationId=uuid4().hex,
            context=spec,
            studentId="u-903101",
            expectedVersion=visit["version"],
            reactions=[300, 304, 305],
        ),
    )
    assert response.status == 200, reaction
    praise = dict(
        kind="praise",
        operationId=uuid4().hex,
        context=spec,
        studentId="u-903101",
        expectedVersion=reaction["state"]["version"],
    )
    response, body = await call(f, "post", "operations", praise)
    assert response.status == 200, body
    response, body = await call(f, "post", "operations", praise)
    assert response.status == 200, body
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS value FROM notification_events WHERE dedupe_key LIKE 'oral-praise:%'"
            ).fetchone()["value"]
        )
        == 1
    )
    response, body = await call(
        f, "post", "sessions/" + spec["contextId"] + "/finish", {}
    )
    assert response.status == 200, body
    response, body, _ = await operation(f, spec, problem_id, minus["state"]["version"])
    assert response.status == 409, body


async def test_live_mark_cannot_use_another_teachers_session_or_bad_payload(
    content_http,
):
    f = content_http
    problem_id, spec = await setup(f)
    response, body = await call(f, "post", "visits", spec, role="admin")
    assert response.status == 403, body
    response, body, _ = await operation(f, spec, problem_id, True)
    assert response.status == 422, body


def seed_room(f):
    def seed(c):
        now = "2026-08-01T12:00:00Z"
        teacher = support.ADMIN_USER_ID
        season = c.execute("SELECT season_id FROM courses WHERE id=1").fetchone()[
            "season_id"
        ]
        event = c.execute(
            """INSERT INTO in_person_events(season_id,name,starts_at,ends_at,status,created_by_user_id,updated_by_user_id,created_at,updated_at)
            VALUES(?,'Очное занятие','2026-09-20T09:00:00Z','2026-09-20T12:00:00Z','scheduled',?,?,?,?) RETURNING id,public_id""",
            (season, teacher, teacher, now, now),
        ).fetchone()
        room = c.execute(
            """INSERT INTO classrooms(name,normalized_name,created_by_user_id,updated_by_user_id,created_at,updated_at)
            VALUES('101','101',?,?,?,?) RETURNING id,public_id""",
            (teacher, teacher, now, now),
        ).fetchone()
        gl = c.execute(
            "SELECT id FROM group_lessons WHERE public_id=?", (f.group_lesson_a,)
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO in_person_event_group_lessons(in_person_event_id,group_lesson_id,added_by_user_id,created_at) VALUES(?,?,?,?)",
            (event["id"], gl, teacher, now),
        )
        layout = c.execute(
            """INSERT INTO classroom_layout_versions(in_person_event_id,state,created_by_user_id,created_at,updated_at)
            VALUES(?,'draft',?,?,?) RETURNING id""",
            (event["id"], teacher, now, now),
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO classroom_layout_rooms(layout_version_id,classroom_id,group_lesson_id,created_at,updated_at) VALUES(?,?,?,?,?)",
            (layout, room["id"], gl, now, now),
        )
        c.execute(
            "UPDATE classroom_layout_versions SET state='confirmed',confirmed_by_user_id=?,confirmed_at=? WHERE id=?",
            (teacher, now, layout),
        )
        from db_methods.pwa.classroom_assignments import insert_plan, confirm_plan

        plan_id, plan_public_id = insert_plan(
            c,
            event_id=event["id"],
            layout_id=layout,
            base_plan_id=None,
            actor_user_id=teacher,
            now=now,
        )
        confirm_plan(
            c, plan_id=plan_id, expected_version=1, actor_user_id=teacher, now=now
        )
        c.execute(
            "UPDATE course_enrollments SET active_group_id='content-b' WHERE student_user_id=?",
            (support.STUDENT_USER_ID,),
        )
        return dict(
            mode="school",
            contextId=event["public_id"],
            roomId=room["public_id"],
            lessonId=f.group_lesson_a,
        ), plan_public_id

    return f.factory.run_write(seed)


async def test_teacher_transfer_across_scope_attendance_and_composite_undo(
    content_http,
):
    from urllib.parse import urlencode

    f = content_http
    await support._prepare_published_test_problem(f, problem_type=3)
    spec, plan_id = seed_room(f)
    response, body = await call(f, "get", "directory?courseId=c-1")
    assert response.status == 200, body
    assert body["students"][0]["groupName"] == "B"
    transfer = dict(
        kind="transfer",
        operationId=uuid4().hex,
        context=spec,
        studentId="u-903101",
        enrollmentVersion=body["students"][0]["enrollmentVersion"],
        planId=plan_id,
    )
    response, receipt = await call(f, "post", "operations", transfer)
    assert response.status == 200, receipt
    response, board = await call(f, "get", "board?" + urlencode(spec))
    assert response.status == 200, board
    assert board["students"][0]["attendance"] == "present"
    assert board["students"][0]["attendanceMode"] == "in_person"
    assert board["students"][0]["groupName"] == "A"
    response, replay = await call(f, "post", "operations", transfer)
    assert response.status == 200 and replay["replayed"], replay
    response, body = await call(
        f,
        "post",
        "operations",
        dict(
            kind="attendance",
            operationId=uuid4().hex,
            context=spec,
            studentId="u-903101",
            expectedVersion=1,
            value="absent",
        ),
    )
    assert response.status == 200, body
    undo = dict(
        kind="undo",
        operationId=uuid4().hex,
        context=spec,
        targetOperationId=receipt["operationId"],
    )
    response, conflict = await call(f, "post", "operations", undo)
    assert response.status == 409, conflict
    # Attendance changed subsequently: transfer undo must not partly restore enrollment.
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT attendance_mode FROM course_enrollments WHERE student_user_id=?",
                (support.STUDENT_USER_ID,),
            ).fetchone()["attendance_mode"]
        )
        == "in_person"
    )


async def test_transfer_undo_restores_online_group_and_preserves_admin_draft(
    content_http,
):
    f = content_http
    await support._prepare_published_test_problem(f, problem_type=3)
    spec, plan_id = seed_room(f)

    def draft(c):
        from db_methods.pwa.classroom_assignments import insert_plan

        p = c.execute(
            "SELECT * FROM classroom_assignment_plans WHERE public_id=?", (plan_id,)
        ).fetchone()
        return insert_plan(
            c,
            event_id=p["in_person_event_id"],
            layout_id=p["layout_version_id"],
            base_plan_id=p["id"],
            actor_user_id=support.ADMIN_USER_ID,
            now="2026-08-01T12:00:00Z",
        )[0]

    draft_id = f.factory.run_write(draft)
    response, body = await call(
        f,
        "post",
        "operations",
        dict(
            kind="transfer",
            operationId=uuid4().hex,
            context=spec,
            studentId="u-903101",
            enrollmentVersion=1,
            planId=plan_id,
        ),
    )
    assert response.status == 200, body
    response, undone = await call(
        f,
        "post",
        "operations",
        dict(
            kind="undo",
            operationId=uuid4().hex,
            context=spec,
            targetOperationId=body["operationId"],
        ),
    )
    assert response.status == 200, undone
    row = f.factory.run_read(
        lambda c: c.execute(
            "SELECT active_group_id,attendance_mode FROM course_enrollments WHERE student_user_id=?",
            (support.STUDENT_USER_ID,),
        ).fetchone()
    )
    assert row == {"active_group_id": "content-b", "attendance_mode": "online"}
    row = f.factory.run_read(
        lambda c: c.execute(
            "SELECT state,confirmed_at FROM classroom_assignment_plans WHERE id=?",
            (draft_id,),
        ).fetchone()
    )
    assert row == {"state": "stale", "confirmed_at": None}


async def test_live_cell_delta_scope_reset_and_tombstone(content_http):
    from urllib.parse import urlencode

    f = content_http
    problem_id, spec = await setup(f)
    _, initial = await call(f, "get", "cells?" + urlencode(spec))
    assert initial["reset"] and initial["cells"] == []
    _, first, payload = await operation(f, spec, problem_id, 0)
    query = dict(spec, after=initial["cursor"], scope=initial["scope"])
    response, delta = await call(f, "get", "cells?" + urlencode(query))
    assert response.status == 200 and not delta["reset"]
    assert delta["cells"][0]["symbol"] == "+"
    assert delta["cursor"] > initial["cursor"]
    query["after"] = delta["cursor"]
    _, unchanged = await call(f, "get", "cells?" + urlencode(query))
    assert not unchanged["cells"]
    _, undone = await call(
        f,
        "post",
        "operations",
        dict(
            kind="undo",
            operationId=uuid4().hex,
            context=spec,
            targetOperationId=first["operationId"],
        ),
    )
    assert undone["state"]["verdict"] is None
    _, cleared = await call(f, "get", "cells?" + urlencode(query))
    assert cleared["cells"][0]["verdict"] is None
    query["scope"] = "0" * 64
    _, reset = await call(f, "get", "cells?" + urlencode(query))
    assert reset["reset"] and len(reset["cells"]) == 1
    await call(f, "post", "sessions/" + spec["contextId"] + "/finish", {})
    response, replay = await call(f, "post", "operations", payload)
    assert response.status == 200 and replay["replayed"]


async def test_manual_mark_stays_current_after_later_written_result_and_pending(
    content_http,
):
    f = content_http
    problem_id, spec = await setup(f)
    response, manual, _ = await operation(f, spec, problem_id, 0, "minus")
    assert response.status == 200

    def later(c):
        c.execute(
            """INSERT INTO results(student_id,problem_id,lesson,group_id,teacher_id,ts,verdict,res_type)
            SELECT ?,id,lesson,group_id,?,'2099-01-01T12:00:00Z',18,2 FROM problems WHERE public_id=?""",
            (support.STUDENT_USER_ID, support.ADMIN_USER_ID, problem_id),
        )
        c.execute(
            """INSERT INTO written_tasks_queue(ts,student_id,problem_id,cur_status)
            SELECT '2099-01-02T12:00:00Z',?,id,0 FROM problems WHERE public_id=?""",
            (support.STUDENT_USER_ID, problem_id),
        )

    f.factory.run_write(later)
    response = await f.client.get(
        f"/student/api/v1/courses/c-1/lessons/{f.group_lesson_a}/problems",
        cookies=support._cookie(f, "student"),
        headers=support._headers(),
    )
    body = await response.json()
    assert response.status == 200, body
    assert body["problems"][0]["status"] == "needs-work", body
    response = await f.client.get(
        "/student/api/v1/courses/c-1/progress",
        cookies=support._cookie(f, "student"),
        headers=support._headers(),
    )
    body = await response.json()
    assert response.status == 200, body
    assert body["summary"]["accepted"] == 0, body
    assert body["summary"]["needsWork"] == 1, body
    assert body["summary"]["awaitingReview"] == 0, body


async def test_legacy_oral_writer_is_a_new_manual_decision_and_recheck_skips_oral(
    content_http,
):
    from types import SimpleNamespace
    from urllib.parse import urlencode
    from db_methods.db_results import DB_RESULT

    f = content_http
    problem_id, spec = await setup(f)
    _, first, _ = await operation(f, spec, problem_id, 0, "minus")
    f.factory.run_write(
        lambda c: c.execute(
            """INSERT INTO results(student_id,problem_id,lesson,group_id,teacher_id,ts,verdict,res_type)
        SELECT ?,id,lesson,group_id,?,'2099-01-01T12:00:00Z',18,3 FROM problems WHERE public_id=?""",
            (support.STUDENT_USER_ID, support.ADMIN_USER_ID, problem_id),
        )
    )
    _, cells = await call(f, "get", "cells?" + urlencode(spec))
    assert cells["cells"][0]["symbol"] == "+"
    assert cells["cells"][0]["teacherId"] != first["state"]["teacherId"]
    rows = f.factory.run_read(
        lambda c: DB_RESULT(SimpleNamespace(conn=c)).get_for_recheck_by_problem_id(
            c.execute(
                "SELECT id FROM problems WHERE public_id=?", (problem_id,)
            ).fetchone()["id"],
        )
    )
    assert rows == []
    response, _ = await call(
        f,
        "post",
        "operations",
        dict(
            kind="undo",
            operationId=uuid4().hex,
            context=spec,
            targetOperationId=first["operationId"],
        ),
    )
    assert response.status == 409


async def test_live_condition_published_scope_and_read_only(content_http):
    from urllib.parse import urlencode

    f = content_http
    problem_id, spec = await setup(f)
    path = "condition?" + urlencode(dict(spec, problemId=problem_id))
    response, data = await call(f, "get", path)
    assert response.status == 200, data
    assert data["document"]["materialKind"] == "condition"
    assert len(data["document"]["problems"]) == 1
    _, cells = await call(f, "get", "cells?" + urlencode(spec))
    assert cells["cells"] == []
    # A different staff member cannot read another teacher's session.
    response, _ = await call(f, "get", path, role="admin")
    assert response.status == 403
    response, _ = await call(
        f, "get", "condition?" + urlencode(dict(spec, problemId="p-missing"))
    )
    assert response.status == 404
    # Removing the publication must not fall back to a draft/latest revision.
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE lesson_publications SET state='hidden',version=version+1,hidden_at='2027-01-01',terminal_at='2027-01-01',updated_at='2027-01-01',terminal_by_user_id=created_by_user_id WHERE group_lesson_id=(SELECT id FROM group_lessons WHERE public_id=?) AND kind='condition'",
            (spec["lessonId"],),
        )
    )
    response, _ = await call(f, "get", path)
    assert response.status == 404
