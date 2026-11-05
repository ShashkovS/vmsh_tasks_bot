"""Acceptance and migration proof for vmshpwa/docs/written-result-precedence.md."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from db_methods.db_results import DB_RESULT
from pwa_tests.sqlite_template import create_test_database
from db_methods.pwa.live_marking import cell, restore_cell
from db_methods.pwa.student_results import current_results
from db_methods.pwa.effective_results import STUDENT_EFFECTIVE_RESULTS_CTES
from pwa_tests.integration import test_review_queue_repository as review_support
from pwa_tests.integration import test_live_marking as live_support
from pwa_tests.integration import test_content_http_api as content_support


GRADES = [-32768, -2, -1, 11, 12, 13, 14, 15, 16, 17, 18]
STUDENT = 1001
TEACHER = 1002
FIRST = 1001
SECOND = 1002
review_queue_fixture = review_support.review_queue_fixture
content_http = content_support.content_http


@pytest.fixture(scope="module")
def projection_template(tmp_path_factory):
    path = tmp_path_factory.mktemp("written-projection-template") / "template.sqlite3"
    create_test_database(path)
    return path


def _seed(c):
    c.executescript("""
      INSERT INTO users(id,type,name,surname) VALUES
        (1001,1,'Student','Projection'),(1002,2,'First','Teacher'),
        (1003,2,'Second','Teacher'),(1004,1,'Other','Student');
      INSERT INTO problems(id,group_id,lesson,prob,item,title,prob_text,prob_type,synonyms)
        VALUES (1001,'н',1,1,'','Written A','',2,'1001;1002'),
               (1002,'н',1,2,'','Written B','',2,'1001;1002'),
               (1003,'н',2,1,'','Other lesson','',2,'1001;1002');
    """)


@pytest.fixture()
def projection_db(projection_template, tmp_path):
    path = tmp_path / "projection.sqlite3"
    with (
        sqlite3.connect(projection_template) as source,
        sqlite3.connect(path) as target,
    ):
        source.backup(target)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    _seed(c)
    yield c
    c.close()


def _add(
    c, verdict, source, problem=FIRST, *, student=STUDENT, teacher=TEACHER, at=None
):
    row = c.execute(
        """INSERT INTO results(student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type)
        SELECT ?,id,group_id,lesson,?,?,?,? FROM problems WHERE id=? RETURNING id""",
        (student, teacher, at or "2026-10-03T12:00:00Z", verdict, source, problem),
    ).fetchone()
    rid = row["id"] if isinstance(row, dict) else row[0]
    if source in (3, 4):
        c.execute("INSERT INTO live_mark_results VALUES(?)", (rid,))
    return rid


def _current(c, problem=FIRST, student=STUDENT):
    return cell(c, student, problem)


def _scoped_results(c, student=STUDENT):
    return [tuple(row) for row in c.execute(
        f"WITH {STUDENT_EFFECTIVE_RESULTS_CTES} "
        "SELECT * FROM student_effective_results ORDER BY id",
        {"student_user_id": student},
    )]


def _assert_scoped_parity(c, student=STUDENT):
    expected = [tuple(row) for row in c.execute(
        "SELECT * FROM effective_results WHERE student_id = ? ORDER BY id",
        (student,),
    )]
    assert _scoped_results(c, student) == expected


@pytest.mark.parametrize("manual", GRADES)
@pytest.mark.parametrize("written", GRADES)
def test_older_manual_is_retained_only_when_strictly_higher(
    projection_db, manual, written
):
    c = projection_db
    mid = _add(c, manual, 3, teacher=1003)
    wid = _add(c, written, 2, SECOND)
    weights = dict(c.execute("SELECT id,val FROM verdicts"))
    manual_wins = weights[manual] > weights[written]
    expected = manual if manual_wins else written
    for pid in (FIRST, SECOND):
        assert _current(c, pid)["verdict"] == expected
    # Higher written results never erase the manual candidate or its author.
    assert _current(c)["result_id"] == mid
    selected = c.execute("SELECT id,teacher_id FROM effective_results").fetchall()
    assert [(r[0], r[1]) for r in selected] == [
        (mid, 1003) if manual_wins else (wid, TEACHER)
    ]
    _assert_scoped_parity(c)


@pytest.mark.parametrize("manual", GRADES)
def test_newer_manual_always_wins_over_written_plus(projection_db, manual):
    c = projection_db
    _add(c, 18, 2)
    mid = _add(c, manual, 4, SECOND, teacher=1003)
    assert _current(c)["verdict"] == manual
    assert _current(c)["teacher_id"] == 1003
    assert c.execute("SELECT id FROM effective_results").fetchall()[0][0] == mid
    _assert_scoped_parity(c)


def test_resubmission_correction_undo_and_all_current_readers(projection_db):
    c = projection_db
    original = _add(c, -1, 3)
    old_version = _current(c)["version"]
    for grade in (11, 13, 18):
        _add(c, grade, 2, SECOND)
    assert _current(c)["verdict"] == 18
    assert _current(c)["version"] > old_version
    solved = DB_RESULT(SimpleNamespace(conn=c)).check_student_solved(STUDENT, 1)
    assert solved == {FIRST: 18, SECOND: 18}
    archive = current_results(c, STUDENT)
    assert {r["projected_problem_id"]: r["verdict"] for r in archive} == {
        FIRST: 18,
        SECOND: 18,
    }
    _add(c, 16, 3, FIRST)
    _add(c, 18, 2, SECOND)
    assert _current(c)["verdict"] == 18
    _add(c, 14, 2, SECOND)
    assert _current(c)["verdict"] == 16
    _add(c, -1, 4, SECOND)
    assert _current(c)["verdict"] == -1
    before = _current(c)["version"]
    restore_cell(c, STUDENT, SECOND, None)
    assert _current(c)["verdict"] == 16
    assert _current(c)["version"] > before
    # Editing an old result changes its value, not the chronological position.
    pinned = _current(c)["result_id"]
    c.execute("UPDATE results SET verdict=13 WHERE id=?", (pinned,))
    assert _current(c)["verdict"] == 14
    assert (
        c.execute("SELECT verdict FROM results WHERE id=?", (original,)).fetchone()[0]
        == -1
    )
    _assert_scoped_parity(c)


def test_latest_written_replaces_higher_history_without_a_manual_mark(projection_db):
    c = projection_db
    _add(c, 18, 2, at="2026-10-04T12:00:00Z")
    latest = _add(c, 13, 2, SECOND, at="2026-10-02T12:00:00Z")
    assert _current(c)["verdict"] == 13
    assert [r[0] for r in c.execute("SELECT id FROM effective_results")] == [latest]


def test_comparison_uses_database_weights_not_verdict_numbers(projection_db):
    c = projection_db
    c.execute("UPDATE verdicts SET val=0.9 WHERE id=12")
    _add(c, 12, 3)
    _add(c, 15, 2, SECOND)
    assert _current(c)["verdict"] == 12


def test_legacy_synonyms_across_levels(projection_db):
    c = projection_db
    c.execute("UPDATE problems SET group_id='п' WHERE id=?", (SECOND,))
    _add(c, -1, 3)
    _add(c, 17, 2, SECOND)
    assert _current(c)["verdict"] == 17
    telegram = DB_RESULT(SimpleNamespace(conn=c))
    assert telegram.check_student_solved(STUDENT, 1, group_id="н") == {FIRST: 17}
    assert telegram.check_student_solved(STUDENT, 1, group_id="п") == {SECOND: 17}


def test_latest_active_manual_not_the_best_or_another_students_grade(projection_db):
    c = projection_db
    _add(c, 18, 3)
    _add(c, -1, 3, SECOND)
    _add(c, 13, 2)
    _add(c, 18, 3, FIRST, student=1004)
    _add(c, 18, 3, 1003)
    assert _current(c)["verdict"] == 13
    assert _current(c, 1003)["verdict"] == 18
    _assert_scoped_parity(c)
    _assert_scoped_parity(c, 1004)
    assert _scoped_results(c, 1002) == []


def test_automatic_acceptance_and_wrong_attempt_keep_existing_rules(projection_db):
    c = projection_db
    _add(c, -1, 3)
    _add(c, -1, 1)
    assert _current(c)["verdict"] == -1
    _assert_scoped_parity(c)
    _add(c, 18, 1)
    assert _current(c)["verdict"] == 18
    assert _current(c)["result_id"] is None
    _assert_scoped_parity(c)
    _add(c, -1, 4)
    assert _current(c)["verdict"] == -1
    _assert_scoped_parity(c)


def test_student_problem_query_does_not_scan_all_results_or_manual_cells(projection_db):
    from db_methods.pwa.content import _STUDENT_PROBLEM_LIST_SELECT

    params = {
        "student_user_id": STUDENT,
        "course_public_id": "c-1",
        "group_public_id": "g-1",
        "group_lesson_public_id": "gl-1",
    }
    plan = [row[3] for row in projection_db.execute(
        "EXPLAIN QUERY PLAN " + _STUDENT_PROBLEM_LIST_SELECT, params,
    )]
    assert not any(detail.startswith(("SCAN r ", "SCAN c ")) for detail in plan)
    assert any("results_by_student_problem (student_id=?)" in detail for detail in plan)
    assert "MATERIALIZE visible_problem" in plan
    assert "MATERIALIZE logical_member" in plan


async def test_modern_synonym_review_and_correction_use_the_shared_winner(
    review_queue_fixture,
):
    f = review_queue_fixture
    ids = f.factory.run_read(
        lambda c: [r["id"] for r in c.execute("SELECT id FROM problems ORDER BY id")]
    )
    f.factory.run_write(
        lambda c: _add(
            c,
            -1,
            3,
            ids[0],
            student=review_support.STUDENT_ID,
            teacher=review_support.TEACHER_TWO_ID,
        )
    )
    lease = await f.repository.claim(
        queue_public_id=f.queue_public_ids[0],
        teacher_user_id=review_support.TEACHER_ONE_ID,
        scope=review_support.ALL_GROUPS_SCOPE,
    )
    command = review_support._complete_command(lease, verdict=17)
    receipt = await f.repository.complete(command)
    replay = await f.repository.complete(command)
    assert replay.replayed and replay.review_public_id == receipt.review_public_id
    assert f.factory.run_read(
        lambda c: [cell(c, review_support.STUDENT_ID, pid)["verdict"] for pid in ids]
    ) == [17, 17]
    correction = review_support.ReviewCorrectionCommand(
        source_review_public_id=receipt.review_public_id,
        reviewer_user_id=review_support.TEACHER_ONE_ID,
        reviewer_type=2,
        scope=review_support.ALL_GROUPS_SCOPE,
        idempotency_key="written-precedence-correction",
        verdict=13,
        comment="Проверка уточнена.",
        confirm_without_comment=False,
    )
    await review_support.correct_written_review(
        f.factory, correction, now=review_support.NOW
    )
    assert f.factory.run_read(
        lambda c: [cell(c, review_support.STUDENT_ID, pid)["verdict"] for pid in ids]
    ) == [13, 13]


async def test_synonym_write_blocks_stale_mark_and_undo_but_replay_is_safe(
    content_http,
    monkeypatch,
):
    from apps.pwa_api import live_marking_routes

    # written-result-precedence.md: activity covers two distinct event days.
    monkeypatch.setattr(live_marking_routes, "_now", lambda: "2026-10-03T12:00:00Z")
    f = content_http
    pid, spec = await live_support.setup(f)

    def aliases(c):
        first = c.execute(
            "SELECT id FROM problems WHERE public_id=?", (pid,)
        ).fetchone()["id"]
        second = c.execute(
            """INSERT INTO problems(group_id,lesson,prob,item,title,prob_text,prob_type,synonyms)
            SELECT group_id,lesson,2,'',title,prob_text,prob_type,'' FROM problems WHERE id=? RETURNING id""",
            (first,),
        ).fetchone()["id"]
        c.execute(
            "UPDATE problems SET synonyms=? WHERE id IN (?,?)",
            (f"{first};{second}", first, second),
        )
        c.execute(
            """INSERT INTO content_problem_matches(content_revision_id,source_ordinal,
            source_item,problem_id,decision,resolved_by_user_id,resolved_at,diagnostics_json,created_at)
            SELECT content_revision_id,2,'2',?,'manual_match',resolved_by_user_id,
            resolved_at,diagnostics_json,created_at FROM content_problem_matches WHERE problem_id=?""",
            (second, first),
        )
        c.execute(
            """INSERT INTO problem_revisions(problem_id,content_revision_id,source_ordinal,
            source_item,display_number,title,normalized_title,problem_type,answer_type,
            answer_config_json,attempt_policy_json,config_version,created_at)
            SELECT ?,content_revision_id,2,'2','2',title,normalized_title,problem_type,
            answer_type,answer_config_json,attempt_policy_json,config_version,created_at
            FROM problem_revisions WHERE problem_id=?""",
            (second, first),
        )
        return first, second

    first, second = f.factory.run_write(aliases)
    response, mark, payload = await live_support.operation(f, spec, pid, 0, "minus")
    assert response.status == 200, mark
    f.factory.run_write(
        lambda c: _add(
            c,
            17,
            2,
            second,
            student=content_support.STUDENT_USER_ID,
            teacher=content_support.ADMIN_USER_ID,
            at="2026-10-04T12:00:00Z",
        )
    )
    response, conflict, _ = await live_support.operation(
        f, spec, pid, mark["state"]["version"], "minus"
    )
    assert response.status == 409, conflict
    response, undo = await live_support.call(
        f,
        "post",
        "operations",
        dict(
            kind="undo",
            operationId="stale-synonym-undo",
            context=spec,
            targetOperationId=mark["operationId"],
        ),
    )
    assert response.status == 409, undo
    response, replay = await live_support.call(f, "post", "operations", payload)
    assert response.status == 200 and replay["replayed"]
    assert (
        f.factory.run_read(
            lambda c: cell(c, content_support.STUDENT_USER_ID, first)["verdict"]
        )
        == 17
    )
    for audience, prefix, role in [
        ("student", "", "student"),
        ("family", "/children/u-903101", "family"),
    ]:
        path = (
            f"/student/api/v1/courses/c-1/lessons/{f.group_lesson_a}/problems"
            if audience == "student"
            else f"/family/api/v1{prefix}/courses/c-1/lessons/41?group=g-1"
        )
        response = await f.client.get(
            path,
            headers=content_support._headers(),
            cookies=content_support._cookie(f, role),
        )
        assert response.status == 200, await response.text()
        body = await response.json()
        problems = (
            body["problems"] if audience == "student" else body["problems"]["problems"]
        )
        assert problems[0]["status"] == "accepted"
    response = await f.client.get(
        "/student/api/v1/courses/c-1/progress",
        headers=content_support._headers(),
        cookies=content_support._cookie(f, "student"),
    )
    assert response.status == 200
    progress = await response.json()
    assert progress["summary"]["accepted"] == 1
    assert (
        len(progress["activity"]) == 2
    )  # Hidden manual event still counts as activity.
