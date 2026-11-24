"""Owner's roster shapes and save latency boundary; docs/teacher-work.md."""

import sqlite3

import pytest

from db_methods.pwa import teacher_work as records
from models.pwa.teacher_work import TeacherNameMatcher, parse_roster
from pwa_tests.integration.test_teacher_work import request, TEACHER_ID
from pwa_tests.integration.test_classroom_catalog_http_api import _seed_layout_scope, ADMIN_ID

pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def teacher(number, surname, name):
    return {"id": number, "public_id": f"u-{number}", "surname": surname,
            "name": name, "middlename": None}


def test_unique_names_initials_legacy_order_and_typo_choices():
    teachers = [teacher(1, "Агеев", "Юрий"), teacher(2, "Агеев", "Николай"),
                teacher(3, "Шварёва", "Виктория"), teacher(4, "Михаил", "Панов"),
                teacher(5, "Злоказов", "Иван"), teacher(6, "Сайенко", "Анна")]
    matcher = TeacherNameMatcher(teachers)
    for text, expected in [("Агеев Ю.", "u-1"), ("Агеев Н", "u-2"),
                           ("шварева", "u-3"), ("Панов М.", "u-4"),
                           ("Принимающий Юрий Агеев", "u-1")]:
        selected, kind, candidates = matcher.roster_match(text)
        assert (selected, kind) == (expected, "exact")
        assert [c["teacherId"] for c in candidates] == [expected]
    selected, kind, candidates = matcher.roster_match("Агеев")
    assert selected is None and kind == "ambiguous"
    assert {c["teacherId"] for c in candidates} == {"u-1", "u-2"}
    for text, expected in [("Зооказов", "u-5"), ("Саенко", "u-6")]:
        selected, kind, candidates = matcher.roster_match(text)
        assert selected is None and kind == "suggested"
        assert candidates[0]["teacherId"] == expected
    assert matcher.roster_match("Левчук") == (None, "unresolved", [])
    assert matcher.roster_match("Принимающий") == (None, "unresolved", [])


def test_duplicate_initials_are_never_selected():
    matcher = TeacherNameMatcher([teacher(1, "Панов", "Михаил"), teacher(2, "Панов", "Максим")])
    assert matcher.roster_match("Панов М.")[:2] == (None, "ambiguous")


@pytest.mark.parametrize("heading,room_separator", [
    ("Распределение:", ":"),
    ("Пока не очень понятно, кто из школьников придёт, публикую то что есть:", ":"),
    ("Текущее распределение:", ""),
    ("Фактическое распределение:", ""),
    ("предварительное распределение:", ""),
])
def test_bulk_roster_prefills_all_unique_teachers_with_only_exceptions_unselected(heading, room_separator):
    surnames = "Ероховец Медведева Жданова Соколова Хацкевич Гусева Шубина Миронова Березин Фёдоров Васильева Кормиленко Панфилов Загуменных Чернышева Давыдов Павлова Казибекова Ефремова Подыряка Фетисова Рыжков Усова Субботина Зиненко Литвак Шавалгина Масло Симонова Вахрина Белоусов Вишнякова Годунин Вербицкая Загаринский".split()
    teachers = [teacher(i, surname, f"Имя{i}") for i, surname in enumerate(surnames, 10)]
    teachers += [teacher(1, "Агеев", "Юрий"), teacher(2, "Агеев", "Николай"), teacher(3, "Панов", "Михаил")]
    # Same room/name/initial/time/comment/reserve shapes as the five owner examples.
    text = heading + "\n" + "\n".join(
        f"{201 + i}{room_separator} " + ", ".join(surnames[i * 4:i * 4 + 4])
        for i in range(9)
    ) + "\n316 Агеев Ю., Агеев Н., Панов М. (с 17:30), Левчук\n308 -- резерв."
    preview = parse_roster(text, [], teachers, "Europe/Moscow")
    assert len(preview["rows"]) == len(surnames) + 4
    assert sum(bool(row["teacherId"]) for row in preview["rows"]) == len(surnames) + 3
    assert next(r for r in preview["rows"] if r["name"] == "Панов М")["startsTime"] == "17:30"
    assert preview["rows"][-1]["teacherId"] is None
    assert "308 -- резерв." in preview["notes"]


async def test_save_receipts_replay_canonical_aliases_without_starting_calculation(classroom_http, monkeypatch):
    from models.pwa.teacher_work_runner import TeacherWorkRunner

    def unexpected_calculation(*args, **kwargs):
        pytest.fail("Saving an input must not start calculation")
    monkeypatch.setattr(TeacherWorkRunner, "start", unexpected_calculation)
    f = classroom_http
    body = {"courseId": "c-1", "action": "alias", "name": "  Принимающий Ёж  ",
            "state": "mapped", "teacherId": f"u-{TEACHER_ID}", "expectedVersion": 0,
            "idempotencyKey": "quick-alias"}
    response = await request(f, "/command", body)
    assert response.status == 200, await response.text()
    receipt = await response.json()
    assert receipt["alias"] == {"normalized_name": "принимающий еж", "teacher_id": TEACHER_ID,
                                "state": "mapped", "version": 1}
    assert await (await request(f, "/command", body)).json() == receipt
    response = await request(f, "/command", {**body, "name": "принимающий еж", "expectedVersion": 1,
                                             "state": "ignored", "teacherId": None, "idempotencyKey": "quick-ignore"})
    assert response.status == 200, await response.text()
    assert (await response.json())["alias"]["version"] == 2
    assert (await (await request(f, "/recalculate?courseId=c-1")).json())["operation"] is None


def test_inputs_and_preview_do_not_read_results_ledger(classroom_http):
    def read(connection):
        connection.set_authorizer(lambda action, table, *_:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table in ("results", "submission_reviews")
            else sqlite3.SQLITE_OK)
        try:
            assert records.roster_facts(connection, 1)["teachers"]
            assert records.input_facts(connection, 1)["teachers"]
        finally:
            connection.set_authorizer(None)
    classroom_http.factory.run_read(read)


async def test_preview_prefills_and_remembers_only_unambiguous_confirmed_choices(classroom_http):
    f = classroom_http
    _seed_layout_scope(f.factory)
    f.factory.run_write(lambda c: c.execute("UPDATE users SET surname='Ероховец',name='Елена' WHERE id=?", (TEACHER_ID,)))
    response = await request(f, "/roster-preview", {"courseId": "c-1", "rawText": "201: ероховец (с 9:00)"})
    assert response.status == 200, await response.text()
    row = (await response.json())["rows"][0]
    assert row["teacherId"] == f"u-{TEACHER_ID}" and row["matchKind"] == "exact"
    assert row["startsTime"] == "09:00"
    assert f.factory.run_read(lambda c: c.execute("SELECT count(*) AS n FROM teacher_work_shifts").fetchone()["n"]) == 0
    event = f.factory.run_read(lambda c: dict(c.execute("SELECT * FROM in_person_events").fetchone()))
    row = {k: v for k, v in row.items() if k not in ("candidates", "matchKind")}
    row.update(name="Левчук", startsTime=None)
    body = {"courseId": "c-1", "action": "roster", "eventId": event["public_id"],
            "eventVersion": event["version"], "expectedVersion": 0, "idempotencyKey": "remember-one",
            "rawText": "201 Левчук", "rows": [row], "state": "confirmed", "replace": False}
    response = await request(f, "/command", body)
    assert response.status == 200, await response.text()
    preview = await (await request(f, "/roster-preview", {"courseId": "c-1", "rawText": "202: левчук"})).json()
    assert preview["rows"][0]["teacherId"] == f"u-{TEACHER_ID}"
    assert preview["rows"][0]["matchKind"] == "remembered"
    response = await request(f, "/command", {**body, "expectedVersion": 1, "idempotencyKey": "remember-two",
        "rows": [row, {**row, "rowId": "2", "teacherId": f"u-{ADMIN_ID}"}]})
    assert response.status == 200, await response.text()
    preview = await (await request(f, "/roster-preview", {"courseId": "c-1", "rawText": "202 Левчук"})).json()
    assert preview["rows"][0]["teacherId"] is None and preview["rows"][0]["matchKind"] == "ambiguous"
    assert {c["teacherId"] for c in preview["rows"][0]["candidates"]} == {f"u-{TEACHER_ID}", f"u-{ADMIN_ID}"}
