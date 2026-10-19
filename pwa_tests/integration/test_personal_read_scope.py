"""Old/new personal result parity and Student/Family cache sharing."""

import pytest
from db_methods.pwa.progress import list_course_result_rows
from pwa_tests.integration import test_content_http_api as support
from pwa_tests.integration import test_written_result_precedence as projection

content_http = support.content_http
OLD_PROGRESS_SQL = "\n        WITH problem_scope AS (\n            SELECT DISTINCT problem_revision.problem_id,\n                            group_lesson.course_id,\n                            course_lesson.lesson_number\n            FROM problem_revisions AS problem_revision\n            JOIN content_revisions AS revision\n              ON revision.id = problem_revision.content_revision_id\n            JOIN content_sources AS source ON source.id = revision.source_id\n            JOIN group_lessons AS group_lesson ON group_lesson.id = source.group_lesson_id\n            JOIN course_lessons AS course_lesson\n              ON course_lesson.id = group_lesson.course_lesson_id\n        )\n        SELECT result.id AS result_id,\n               result.problem_id,\n               result.ts,\n               verdict.val AS verdict_weight,\n               manual.result_id IS NOT NULL AS manual_override,\n               problem_scope.lesson_number,\n               problem_group.logical_key AS logical_problem_key\n        FROM effective_results AS result\n        JOIN verdicts AS verdict ON verdict.id = result.verdict\n        LEFT JOIN live_mark_cells AS manual ON manual.result_id = result.id\n        JOIN problem_scope ON problem_scope.problem_id = result.problem_id\n        JOIN result_problem_groups AS problem_group\n          ON problem_group.problem_id = result.problem_id\n        WHERE result.student_id = ?\n          AND problem_scope.course_id = ?\n        ORDER BY result.ts, result.id\n        "


@pytest.mark.parametrize("source,verdict", [(1, 17), (2, 13), (3, 12), (4, -32768)])
async def test_progress_scoped_sql_preserves_alias_winners_and_other_students(
    content_http, source, verdict
):
    f = content_http
    pid, _ = await support._prepare_published_test_problem(f, problem_type=1)

    def compare(c):
        first = c.execute(
            "SELECT id FROM problems WHERE public_id=?", (pid,)
        ).fetchone()["id"]
        peer = c.execute(
            "INSERT INTO problems(group_id,lesson,prob,item,title,prob_text,prob_type,synonyms) SELECT group_id,lesson,2,'','Alias','',prob_type,'' FROM problems WHERE id=? RETURNING id",
            (first,),
        ).fetchone()["id"]
        c.execute(
            "UPDATE problems SET synonyms=? WHERE id IN (?,?)",
            (f"{first};{peer}", first, peer),
        )
        # Newer source on an alias without a publication still participates in
        # precedence before only this course's source rows are projected.
        projection._add(
            c,
            17,
            1,
            first,
            student=support.STUDENT_USER_ID,
            teacher=support.TEACHER_USER_ID,
        )
        rid = projection._add(
            c,
            verdict,
            source,
            peer,
            student=support.STUDENT_USER_ID,
            teacher=support.TEACHER_USER_ID,
        )
        course = c.execute("SELECT id FROM courses WHERE public_id='c-1'").fetchone()[
            "id"
        ]
        for student in (support.STUDENT_USER_ID, support.TEACHER_USER_ID):
            expected = [
                dict(row) for row in c.execute(OLD_PROGRESS_SQL, (student, course))
            ]
            assert (
                list_course_result_rows(c, student_user_id=student, course_id=course)
                == expected
            )
            assert (
                list_course_result_rows(c, student_user_id=student, course_id=-1) == []
            )
        plan = [
            r["detail"]
            for r in c.execute(
                "EXPLAIN QUERY PLAN "
                + __import__(
                    "db_methods.pwa.progress", fromlist=["COURSE_RESULTS_SQL"]
                ).COURSE_RESULTS_SQL,
                {"student_user_id": support.STUDENT_USER_ID, "course_id": course},
            )
        ]
        assert not any("MATERIALIZE choices" in text for text in plan)

    f.factory.run_write(compare)


async def test_student_and_family_share_progress_but_check_access_each_time(
    content_http, monkeypatch
):
    from apps.pwa_api import personal_reads

    f = content_http
    calls = []
    original = personal_reads.list_course_result_rows

    def counted(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(personal_reads, "list_course_result_rows", counted)
    for audience, url in [
        ("student", "/student/api/v1/courses/c-1/progress"),
        ("family", "/family/api/v1/children/u-903101/home"),
    ]:
        response = await f.client.get(
            url, headers=support._headers(), cookies=support._cookie(f, audience)
        )
        assert response.status == 200, await response.text()
    assert len(calls) == 1
    denied = await f.client.get(
        "/family/api/v1/children/unlinked/home",
        headers=support._headers(),
        cookies=support._cookie(f, "family"),
    )
    assert denied.status == 403
    assert len(calls) == 1
