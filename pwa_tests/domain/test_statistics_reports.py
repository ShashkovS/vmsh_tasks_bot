"""Report acceptance rules: vmshpwa/docs/lesson-statistics.md."""

from models.pwa.statistics_reports import build_reports
from pwa_tests.domain.test_lesson_statistics import problem, result


def facts():
    problems = [
        problem(1, 0),
        problem(2, 0),
        problem(3, 0, "p"),
        problem(4, 0),
        problem(5, 1),
    ]
    rows = []
    for pid, source, score in [(1, 1, 1), (2, 2, 0.5), (3, 3, 1), (4, 4, 1)]:
        rows.append(dict(result(pid, score=score), res_type=source))
    students = {
        1: dict(public_id="u-1", surname="А", name="Б", display_name="А Б"),
        2: dict(public_id="u-2", surname="В", name="Г", display_name="В Г"),
    }
    reviews = [dict(result_id=i, student_user_id=1, problem_id=2) for i in (10, 11)]
    pending = [
        dict(student_user_id=1, problem_id=2),
        dict(student_user_id=1, problem_id=2),
        dict(student_user_id=2, problem_id=2),
    ]
    return problems, rows, pending, reviews, pending, students


def test_workload_repeats_and_pending_pairs_current_channels():
    report = build_reports(facts(), {"n", "p"}, 0)
    row = report["lessons"][0]
    assert row["students"] == 2
    assert row["writtenChecked"] == 2
    assert row["writtenPending"] == 2
    assert row["writtenTotal"] == 4
    assert row["allPlus"] == 3.5
    assert [row[k + "Plus"] for k in ("bot", "written", "zoom", "school")] == [
        1,
        0.5,
        1,
        1,
    ]
    assert row["writtenStudents"] == row["zoomStudents"] == row["schoolStudents"] == 1
    assert len(report["rows"]) == 2
    assert report["rows"][0]["total"] == 3.5
    assert report["rows"][0]["cells"][1]["pending"] is True
    assert report["rows"][1]["total"] == 0
    assert report["rows"][1]["cells"][0]["attempted"] is False


def test_tie_source_scope_empty_and_default_lesson():
    data = facts()
    data[1].append(dict(result(1, index=2), res_type=4))
    report = build_reports(data, {"n"}, 0)
    assert report["rows"][0]["cells"][0]["source"] == "school"
    assert len(report["problems"]) == 3
    assert report["lessons"][0]["allPlus"] == 2.5
    assert build_reports(data, {"n"})["lessonNumber"] == 1
    assert build_reports(data, {"n"}, 99)["rows"] == []
    assert build_reports(data, set())["lessons"] == []


def test_test_recheck_attribution_uses_verdict_event_not_attempt_timestamp():
    data = facts()
    data[1].append(dict(result(1, index=2), res_type=2))
    data[1][0].update(source_ts="2026-09-03T12:00:00", source_result_id=99)
    report = build_reports(data, {"n"}, 0)
    assert report["rows"][0]["cells"][0]["source"] == "bot"
