"""Accounting invariants and real admin HTTP boundary; docs/teacher-work.md."""

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from models.pwa.teacher_work import (
    calculate_snapshot,
    fingerprint,
    parse_roster,
    written_estimates,
    zoom_days,
)
from models.pwa.teacher_work_report import build_report, export_tsv
from models.pwa.teacher_work_runner import calculate_course_work
from pwa_tests.integration.test_classroom_catalog_http_api import (
    ADMIN_ID,
    TEACHER_ID,
    _cookies,
    _headers,
    _seed_layout_scope,
)

pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)
BASE = "/staff/api/v1/teacher-work"


def written(teacher, offset, verdict=17, result_id=1):
    return {
        "id": result_id,
        "teacher_id": teacher,
        "problem_id": 1,
        "lesson": 2,
        "verdict": verdict,
        "ts": (
            datetime(2026, 9, 14, tzinfo=UTC) + timedelta(seconds=offset)
        ).isoformat(),
        "res_type": 2,
    }


def test_written_teacher_order_actual_verdict_and_whole_days():
    rows = [
        written(1, 0),
        written(2, 10, result_id=2),
        written(1, 40, result_id=3),
        written(2, 20, verdict=11, result_id=4),
        written(1, 86440, result_id=5),
    ]
    estimates = {r["id"]: r for r in written_estimates(rows, "Europe/Moscow")}
    assert estimates[3]["seconds"] == 40
    assert estimates[4]["seconds"] == 10
    assert estimates[5]["gapSeconds"] == 86400
    assert estimates[5]["seconds"] == 44
    assert (
        estimates[2]["seconds"] == 44
    )  # shared task/verdict sample, not teacher interleaving


def event(i, ts, action, participant="a"):
    return {
        "id": i,
        "event_ts": ts,
        "event": "meeting.participant_" + action,
        "zoom_user_name": "Принимающий Ёж",
        "zoom_user_id": participant,
    }


def facts():
    return {
        "course": {"timezone": "Europe/Moscow"},
        "teachers": [
            {
                "id": 1,
                "public_id": "u-1",
                "surname": "Ёж",
                "name": "Иван",
                "middlename": None,
            }
        ],
        "results": [],
        "aliases": [
            {"normalized_name": "принимающий еж", "teacher_id": 1, "state": "mapped"}
        ],
        "zoom": [],
        "shifts": [],
        "lessons": [
            {"number": 2, "anchor": "2026-09-14"},
            {"number": 3, "anchor": "2026-09-21"},
        ],
        "events": [],
        "windows": [],
    }


def test_zoom_union_duplicate_devices_and_cross_midnight():
    f = facts()
    f["zoom"] = [
        event(1, "2026-09-14T23:30:00", "joined"),
        event(2, "2026-09-15T01:00:00", "left"),
        event(3, "2026-09-15T00:00:00", "joined", "b"),
        event(4, "2026-09-15T01:30:00", "left", "b"),
        event(5, "2026-09-15T01:30:00", "left", "b"),
    ]
    days = zoom_days(
        f["zoom"], {a["normalized_name"]: a for a in f["aliases"]}, "Europe/Moscow"
    )
    assert days[(1, "2026-09-14")]["hours"] == 0.5
    assert days[(1, "2026-09-15")]["hours"] == 1.5
    assert not days[(1, "2026-09-15")]["anomalies"]


def test_partial_replaces_whole_day_and_no_evidence_is_unknown():
    f = facts()
    f["zoom"] = [
        event(1, "2026-09-14T17:00:00", "joined"),
        event(2, "2026-09-14T18:00:00", "left"),
        event(3, "2026-09-14T19:00:00", "joined"),
        event(4, "2026-09-15T19:00:00", "left"),
    ]
    f["results"] = [
        {**written(1, 17 * 3600), "ts": "2026-09-14T14:00:00Z", "res_type": 3},
        {
            **written(1, 18 * 3600, result_id=2),
            "ts": "2026-09-14T15:00:00Z",
            "res_type": 3,
        },
    ]
    snapshot = calculate_snapshot(f)
    # Cross-day join/leave is complete; deliberately add a stray leave to make Monday partial.
    f["zoom"].append(event(5, "2026-09-14T20:00:00", "left", "c"))
    snapshot = calculate_snapshot(f)
    day = next(c for c in snapshot["cells"] if c["slot"] == "2026-09-14")
    assert day["hours"] == pytest.approx(1.3)
    assert day["source"] == "estimate"
    f["results"] = []
    assert (
        next(c for c in calculate_snapshot(f)["cells"] if c["slot"] == "2026-09-14")[
            "hours"
        ]
        is None
    )


def test_report_actual_extra_day_shared_window_and_tsv():
    f = facts()
    f["zoom"] = [
        event(1, "2026-09-20T17:00:00", "joined"),
        event(2, "2026-09-20T19:00:00", "left"),
    ]
    f["windows"] = [{"opens_at": "2026-09-20T14:00:00Z"}] * 2
    f["results"] = [written(1, 0), written(1, 40, result_id=2)]
    report = build_report(calculate_snapshot(f), {}, today="2026-10-01")
    assert [c["label"] for c in report["columns"][:6]] == [
        "Шк",
        "Пн",
        "Вт",
        "Ср",
        "Вс",
        "✏",
    ]
    assert report["rows"][0]["counts"] == {"school": 0, "zoom": 1, "written": 1}
    assert report["rows"][0]["totals"]["zoom"] == 2
    lines = export_tsv(report).splitlines()
    assert len({len(s.split("\t")) for s in lines}) == 1
    assert lines[0].split("\t")[:13] == [
        "1",
        "2",
        "3",
        "4",
        "6",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
    ]
    assert lines[1].split("\t")[13:19] == ["2"] * 6
    assert lines[2].split("\t")[13:19] == [
        "14-Sep",
        "14-Sep",
        "15-Sep",
        "16-Sep",
        "20-Sep",
        "20-Sep",
    ]
    assert lines[3].split("\t")[9:13] == ["0.0", "2.0", "0.0", "2.02"]


def test_roster_parser_keeps_notes_initials_and_time_groups():
    f = facts()
    preview = parse_roster(
        "5 октбября\nпредварительное распределение:\n201: Ёж (с 17:30), Ёж И. (н, п).\n308 -- резерв.",
        [],
        f["teachers"],
        "Europe/Moscow",
    )
    assert len(preview["rows"]) == 2
    assert preview["rows"][0]["startsTime"] == "17:30"
    assert preview["rows"][1]["name"] == "Ёж И"
    assert preview["preliminary"]
    assert "308 -- резерв." in preview["notes"]
    assert all(r["teacherId"] is None for r in preview["rows"])


@pytest.mark.parametrize("heading", ["14 сентября", "21 сентября", "28 сентября"])
def test_roster_date_heading_is_not_a_room(heading):
    preview = parse_roster(
        heading + "\n201: Ёж (с 18:00)\n308 -- резерв.",
        [], facts()["teachers"], "Europe/Moscow",
    )
    assert len(preview["rows"]) == 1
    assert preview["rows"][0]["room"] == "201"
    assert preview["rows"][0]["startsTime"] == "18:00"


def test_school_source_fingerprint_ignores_reimport_metadata():
    source = facts()
    shift = {
        "teacher_id": 1, "event_id": 1, "starts_at": "2026-09-14T16:50:00+03:00",
        "ends_at": "2026-09-14T19:00:00+03:00", "standard_starts_at": "2026-09-14T16:50:00+03:00",
        "standard_ends_at": "2026-09-14T19:00:00+03:00", "norm_hours": 2.3,
        "version": 1, "updated_at": "2026-09-15", "updated_by": 1,
    }
    source["shifts"] = [shift]
    before = calculate_snapshot(source)["cells"][0]["fingerprint"]
    shift.update(version=2, updated_at="2026-09-16", updated_by=2)
    assert calculate_snapshot(source)["cells"][0]["fingerprint"] == before
    shift["ends_at"] = "2026-09-14T18:00:00+03:00"
    assert calculate_snapshot(source)["cells"][0]["fingerprint"] != before


async def request(fixture, path, body=None, persona="admin"):
    kwargs = {"headers": _headers(unsafe=True), "cookies": _cookies(fixture, persona)}
    return await (
        fixture.client.post(BASE + path, json=body, **kwargs)
        if body is not None
        else fixture.client.get(BASE + path, **kwargs)
    )


async def wait_run(fixture):
    for _ in range(100):
        response = await request(fixture, "/recalculate?courseId=c-1")
        state = await response.json()
        if not state["busy"]:
            assert state["operation"]["state"] == "completed", state
            return state
        await asyncio.sleep(0.02)
    pytest.fail("worker timeout")


async def test_admin_http_settings_alias_replay_permissions_and_atomic_snapshot(
    classroom_http,
):
    f = classroom_http
    for path in (
        "/catalog",
        "/report?courseId=c-1",
        "/inputs?courseId=c-1",
        "/details?courseId=c-1&cellKey=zoom:1:2026-09-14",
        "/recalculate?courseId=c-1",
    ):
        assert (await request(f, path, persona="teacher")).status == 403
    body = {
        "courseId": "c-1",
        "action": "settings",
        "normHours": 2.3,
        "expectedVersion": 0,
        "idempotencyKey": "settings1",
    }
    response = await request(f, "/command", body)
    assert response.status == 200, await response.text()
    assert (await request(f, "/command", body)).status == 200
    assert (await request(f, "/command", {**body, "normHours": 3})).status == 409
    await wait_run(f)
    response = await request(
        f,
        "/command",
        {
            "courseId": "c-1",
            "action": "alias",
            "name": "Принимающий Мария",
            "state": "mapped",
            "teacherId": f"u-{TEACHER_ID}",
            "expectedVersion": 0,
            "idempotencyKey": "alias1",
        },
    )
    assert response.status == 200, await response.text()
    await wait_run(f)
    response = await request(f, "/report?courseId=c-1")
    report = await response.json()
    assert report["run"]["state"] == "completed"
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM teacher_work_mutations"
            ).fetchone()["n"]
        )
        == 2
    )
    assert (
        await request(
            f,
            "/recalculate",
            {"courseId": "c-1", "idempotencyKey": "admin1"},
            persona="teacher",
        )
    ).status == 403
    response = await f.client.post(
        BASE + "/command",
        json=body,
        cookies=_cookies(f, "admin"),
        headers={**_headers(), "Origin": "https://evil.example"},
    )
    assert response.status == 403


async def test_confirm_merge_norm_snapshot_override_stale(classroom_http):
    f = classroom_http
    _seed_layout_scope(f.factory)
    event_row = f.factory.run_read(
        lambda c: dict(c.execute("SELECT * FROM in_person_events").fetchone())
    )
    row = {
        "rowId": "1-0",
        "teacherId": f"u-{TEACHER_ID}",
        "name": "Учитель",
        "room": "201",
        "source": "201 Учитель",
        "startsTime": "14:00",
        "endsTime": None,
    }
    body = {
        "courseId": "c-1",
        "action": "roster",
        "eventId": event_row["public_id"],
        "eventVersion": 1,
        "expectedVersion": 0,
        "idempotencyKey": "roster1",
        "rawText": "11 октября\n201 Учитель (с 14:00)",
        "rows": [row, {**row, "rowId": "2-0", "room": "202"}],
        "state": "confirmed",
        "replace": False,
    }
    response = await request(f, "/command", body)
    assert response.status == 200, await response.text()
    await wait_run(f)
    shifts = f.factory.run_read(
        lambda c: [dict(r) for r in c.execute("SELECT * FROM teacher_work_shifts")]
    )
    assert len(shifts) == 1 and json.loads(shifts[0]["rooms_json"]) == ["201", "202"]
    snapshot = f.factory.run_read(
        lambda c: json.loads(
            c.execute(
                "SELECT snapshot_json FROM teacher_work_runs WHERE state='completed' ORDER BY id DESC LIMIT 1"
            ).fetchone()["snapshot_json"]
        )
    )
    cell = snapshot["cells"][0]
    assert cell["hours"] == pytest.approx(
        1.3
    )  # actual 14–16 local, normal 13–16 =2.3 minus 1
    override = {
        "courseId": "c-1",
        "action": "override",
        "cellKey": cell["key"],
        "hours": 2,
        "comment": "Фактическое время",
        "sourceFingerprint": cell["fingerprint"],
        "expectedVersion": 0,
        "idempotencyKey": "manual1",
    }
    response = await request(f, "/command", override)
    assert response.status == 200, await response.text()
    response = await request(
        f,
        "/command",
        {
            "courseId": "c-1",
            "action": "settings",
            "normHours": 3,
            "expectedVersion": 0,
            "idempotencyKey": "norm1",
        },
    )
    assert response.status == 200
    await wait_run(f)
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT norm_hours FROM teacher_work_shifts"
            ).fetchone()["norm_hours"]
        )
        == 2.3
    )
    response = await request(
        f,
        "/command",
        {**body, "rows": [row], "expectedVersion": 1, "idempotencyKey": "roster2"},
    )
    assert response.status == 200
    await wait_run(f)
    response = await request(f, "/details?courseId=c-1&cellKey=" + cell["key"])
    detail = await response.json()
    assert detail["override"]["hours"] == 2
    assert detail["override"]["source_fingerprint"] != detail["cell"]["fingerprint"]
    assert (
        await request(f, "/command", {**body, "idempotencyKey": "conflict"})
    ).status == 409


def test_failed_snapshot_preserves_last_good(classroom_http, monkeypatch):
    f = classroom_http

    def run():
        with sqlite3.connect(f.factory.database_path) as connection:
            connection.row_factory = sqlite3.Row
            calculate_course_work(connection, 1)

    run()

    def fail(_):
        raise RuntimeError("injected")

    monkeypatch.setattr("models.pwa.teacher_work_runner.calculate_snapshot", fail)
    with pytest.raises(RuntimeError):
        run()
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM teacher_work_runs WHERE state='completed'"
            ).fetchone()["n"]
        )
        == 1
    )


def test_skipped_calendar_week_keeps_actual_zoom_date():
    f = facts()
    f["lessons"] = [
        {"number": 0, "anchor": "2026-08-24"},
        {"number": 1, "anchor": "2026-09-07"},
    ]
    f["zoom"] = [
        event(1, "2026-08-31T17:00:00", "joined"),
        event(2, "2026-08-31T18:00:00", "left"),
    ]
    report = build_report(calculate_snapshot(f), {}, today="2026-10-01")
    assert report["rows"][0]["totals"]["zoom"] == 1
    assert any(
        c["date"] == "2026-08-31" and c["lesson"] == 0 for c in report["columns"]
    )


async def test_cleared_override_has_monotone_version_and_rejects_stale_writer(
    classroom_http,
):
    f = classroom_http
    body = {
        "courseId": "c-1",
        "action": "override",
        "cellKey": f"zoom:{TEACHER_ID}:2026-09-14",
        "hours": 1,
        "comment": "Факт",
        "sourceFingerprint": fingerprint([]),
        "expectedVersion": 0,
        "idempotencyKey": "v1",
    }
    assert (await request(f, "/command", body)).status == 200
    response = await request(
        f,
        "/command",
        {**body, "hours": None, "expectedVersion": 1, "idempotencyKey": "clear"},
    )
    assert response.status == 200
    assert (await response.json())["version"] == 2
    assert (
        await request(f, "/command", {**body, "idempotencyKey": "stale"})
    ).status == 409
    detail = await (
        await request(f, "/details?courseId=c-1&cellKey=" + body["cellKey"])
    ).json()
    assert detail["override"]["hours"] is None and detail["override"]["version"] == 2
    audit = json.loads(detail["audit"][0]["after_json"])
    assert audit["state"]["hours"] is None and audit["receipt"]["version"] == 2
    assert (
        await request(
            f,
            "/command",
            {
                **body,
                "cellKey": f"written:{TEACHER_ID}:2026-00-01",
                "idempotencyKey": "bad",
            },
        )
    ).status == 422


async def test_conflicting_roster_time_does_not_partially_write(classroom_http):
    f = classroom_http
    _seed_layout_scope(f.factory)
    event_row = f.factory.run_read(
        lambda c: dict(c.execute("SELECT * FROM in_person_events").fetchone())
    )
    row = {
        "rowId": "a",
        "teacherId": f"u-{TEACHER_ID}",
        "name": "Учитель",
        "room": "201",
        "source": "201 Учитель",
        "startsTime": "14:00",
        "endsTime": None,
    }
    body = {
        "courseId": "c-1",
        "action": "roster",
        "eventId": event_row["public_id"],
        "eventVersion": 1,
        "expectedVersion": 0,
        "idempotencyKey": "conflict-time",
        "rawText": "test",
        "rows": [row, {**row, "rowId": "b", "startsTime": "15:00"}],
        "state": "confirmed",
        "replace": False,
    }
    assert (await request(f, "/command", body)).status == 422
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM teacher_work_shifts"
            ).fetchone()["n"]
        )
        == 0
    )
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM teacher_work_rosters"
            ).fetchone()["n"]
        )
        == 0
    )


def test_coalesced_replay_recovery_and_bounded_payloads(classroom_http):
    import fcntl
    import time
    from db_methods.pwa import teacher_work as records
    from models.pwa.teacher_work_runner import TeacherWorkRunner, timestamp

    f = classroom_http
    runner = TeacherWorkRunner(f.factory.database_path)

    def complete():
        for _ in range(200):
            state = runner.status(1)
            if not state["busy"]:
                assert state["operation"]["state"] == "completed", state
                return
            time.sleep(0.01)
        pytest.fail("worker timeout")

    try:
        with open(str(f.factory.database_path) + ".analytics.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            first = runner.start(1, ADMIN_ID, "coalesce-a")
            second = runner.start(1, ADMIN_ID, "coalesce-b")
            assert first["operation"]["id"] == second["operation"]["id"]
        complete()
        replay = runner.start(1, ADMIN_ID, "coalesce-b")
        assert (
            replay["operation"]["id"] == first["operation"]["id"] and not replay["busy"]
        )
        with sqlite3.connect(f.factory.database_path) as c:
            c.row_factory = sqlite3.Row
            queued = records.create_run(
                c, 1, ADMIN_ID, "interrupted-queue", timestamp()
            )
        runner.recover()
        complete()
        assert runner.status(1)["operation"]["id"] == queued
        for _ in range(3):
            with sqlite3.connect(f.factory.database_path) as c:
                c.row_factory = sqlite3.Row
                calculate_course_work(c, 1)
        with sqlite3.connect(f.factory.database_path) as c:
            assert (
                c.execute(
                    "SELECT count(*) FROM teacher_work_runs WHERE state='completed'"
                ).fetchone()[0]
                == 5
            )
            assert (
                c.execute(
                    "SELECT count(*) FROM teacher_work_runs WHERE snapshot_json IS NOT NULL"
                ).fetchone()[0]
                == 2
            )
        assert (
            runner.start(1, ADMIN_ID, "coalesce-a")["operation"]["id"]
            == first["operation"]["id"]
        )
    finally:
        runner.close()
