"""The copyable external client keeps the same roster across print stages."""

import json

import pytest

from docs.printing import legacy_print_client as client


def test_snapshot_reuse_and_a13_identity_adapter(tmp_path, monkeypatch):
    supplied_tokens = []
    requested_paths = []
    rows = [
        {
            "ID": "student.login",
            "IDd": "student.login",
            "UserID": 42,
            "Фамилия": "Иванов",
            "Имя": "Иван",
            "ФИО": "Иванов Иван",
            "Клс": "7",
            "GroupID": "н",
            "Аудитория": "201",
        }
    ]
    history = {
        "lesson": 3,
        "problems": [
            {
                "id": 91,
                "lesson": 3,
                "group_id": "н",
                "prob": 1,
                "item": "",
                "full_prob": "1<br>",
                "prob_type": 2,
            },
            {
                "id": 92,
                "lesson": 3,
                "group_id": "п",
                "prob": 1,
                "item": "",
                "full_prob": "1<br>",
                "prob_type": 2,
            },
        ],
        "results": [
            {"student_id": 42, "syn_problem_id": 91, "max_verdict": 0.7},
            {"student_id": 42, "syn_problem_id": 92, "max_verdict": 1.0},
        ],
    }

    def fake_get(path, token=None):
        requested_paths.append(path)
        supplied_tokens.append(token)
        if path == "/events":
            return {
                "events": [
                    {
                        "event_id": "event-one",
                        "starts_at": "2026-09-14T13:50:00Z",
                        "status": "scheduled",
                        "plan_id": "plan-one",
                        "lesson_numbers": [4],
                    }
                ]
            }, {}
        if path == "/events/event-one/previous-results?lesson=4":
            return history, {
                "ETag": '"history-digest"',
                "X-Print-Event": "event-one",
                "X-Print-Lesson": "4",
                "X-Print-Previous-Lesson": "3",
                "X-Print-Plan": "plan-one",
                "X-Print-Plan-Version": "2",
            }
        return rows, {
            "ETag": '"digest"',
            "X-Print-Event": "event-one",
            "X-Print-Lesson": "4",
            "X-Print-Plan": "plan-one",
            "X-Print-Plan-Version": "2",
        }

    monkeypatch.setattr(client, "_get", fake_get)
    filename = tmp_path / "portal-print.json"
    assert (
        client.refresh_portal_conduit(4, filename, token="explicit-test-token") == rows
    )
    assert requested_paths == [
        "/events",
        "/events/event-one/pupils?lesson=4",
        "/events/event-one/previous-results?lesson=4",
    ]
    assert supplied_tokens == ["explicit-test-token"] * 3
    first = client.load_portal_conduit(4, filename)
    first[0]["Аудитория"] = "202"
    assert client.load_portal_conduit(4, filename)[0]["Аудитория"] == "201"
    assert client.get_portal_pupils_for_results(["student.login"], 4, filename) == [
        {
            "id": 42,
            "token": "student.login",
            "surname": "Иванов",
            "name": "Иван",
            "group_id": "н",
            "grade": "7",
        }
    ]
    assert client.get_portal_problems(3, "н", filename) == [history["problems"][0]]
    assert client.get_portal_results([42], 3, "н", filename) == {(42, 91): 0.7}
    with pytest.raises(RuntimeError, match="результатов относится к другому"):
        client.get_portal_problems(2, "н", filename)
    with pytest.raises(RuntimeError, match="другому занятию"):
        client.load_portal_conduit(5, filename)
    assert json.loads(filename.read_text())["planId"] == "plan-one"
    monkeypatch.setattr(client, "_get", lambda path, token=None: ([], {}))
    with pytest.raises(RuntimeError, match="Некорректный ответ"):
        client.download_portal_conduit("event-one", 4, filename)
    assert len(client.load_portal_conduit(4, filename)) == 1


def test_event_selection_requires_unique_match_and_allows_override(
    tmp_path, monkeypatch
):
    candidates = {
        "events": [
            {
                "event_id": event_id,
                "starts_at": starts_at,
                "status": "scheduled",
                "plan_id": "plan-" + event_id,
                "lesson_numbers": [4],
            }
            for event_id, starts_at in (
                ("event-one", "2026-09-14T13:50:00Z"),
                ("event-two", "2026-09-21T13:50:00Z"),
            )
        ]
    }
    monkeypatch.setattr(client, "_get", lambda path, token=None: (candidates, {}))
    with pytest.raises(RuntimeError, match="event-one.*event-two.*event_id явно"):
        client.resolve_portal_print_event(4, token="test-token")

    rows = [{"ID": "student.login"}]

    def fake_pupils(path, token=None):
        metadata = {
            "ETag": '"digest"',
            "X-Print-Event": "event-two",
            "X-Print-Lesson": "4",
            "X-Print-Plan": "plan-event-two",
            "X-Print-Plan-Version": "1",
        }
        if path == "/events/event-two/pupils?lesson=4":
            return rows, metadata
        assert path == "/events/event-two/previous-results?lesson=4"
        return {"lesson": 3, "problems": [], "results": []}, {
            **metadata,
            "X-Print-Previous-Lesson": "3",
        }

    monkeypatch.setattr(client, "_get", fake_pupils)
    filename = tmp_path / "portal-print.json"
    assert client.refresh_portal_conduit(
        4, filename, token="test-token", event_id="event-two"
    ) == [{"ID": "student.login"}]
    assert json.loads(filename.read_text())["eventId"] == "event-two"


def test_after_lesson_snapshot_adapts_mail_and_site_statistics(tmp_path, monkeypatch):
    payload = {
        "schemaVersion": 1,
        "courseId": "c-1",
        "lesson": 3,
        "pupils": [
            {
                "id": 42,
                "login": "student.login",
                "surname": "Иванов",
                "name": "Иван",
                "group_id": "group-n",
                "level": "н",
            }
        ],
        "problems": [
            {
                "id": 91,
                "lesson": 3,
                "group_id": "group-n",
                "level": "н",
                "prob": 1,
                "item": "а",
                "prob_type": 2,
            },
            {
                "id": 92,
                "lesson": 3,
                "group_id": "group-n",
                "level": "н",
                "prob": 2,
                "item": "",
                "prob_type": 1,
            },
        ],
        "results": [
            {
                "student_id": 42,
                "problem_id": 91,
                "max_verdict": 0.7,
                "score": 0.7,
            },
            {
                "student_id": 42,
                "problem_id": 92,
                "max_verdict": None,
                "score": 0.0,
            },
        ],
        "recentStudentIds": [42],
    }

    def fake_get(path, token=None):
        assert token == "test-token"
        assert path == "/events/event-one/lesson-results?lesson=3"
        return payload, {
            "ETag": '"lesson-digest"',
            "X-Print-Event": "event-one",
            "X-Print-Lesson": "3",
            "X-Print-Plan": "plan-one",
            "X-Print-Plan-Version": "2",
        }

    monkeypatch.setattr(client, "_get", fake_get)
    filename = tmp_path / "portal-after-lesson.json"
    snapshot = client.refresh_portal_lesson_results(
        3,
        filename,
        token="test-token",
        event_id="event-one",
    )
    assert snapshot["eventId"] == "event-one"
    assert client.get_portal_mail_pupils(3, filename) == {
        42: {
            "id": 42,
            "token": "student.login",
            "surname": "Иванов",
            "name": "Иван",
            "group_id": "н",
            "key": "student.login\tИванов\tИван\tн",
        }
    }
    assert client.get_portal_mail_problems(3, "н", filename)[91]["formatted"] == (
        "03н.01а"
    )
    assert client.get_portal_mail_results(3, "н", filename) == {(42, 91): 0.7}
    assert client.get_portal_recent_student_ids(3, filename) == {42}
    assert client.get_portal_problem_statistics(3, filename) == {
        "3н.1а": (1, 1),
        "3н.2": (0, 1),
    }


def test_absent_snapshot_is_not_a_silent_excel_fallback(tmp_path):
    with pytest.raises(RuntimeError, match="сначала запустите a11"):
        client.load_portal_conduit(4, tmp_path / "missing.json")
    with pytest.raises(RuntimeError, match="portal-after-lesson"):
        client.load_portal_lesson_results(4, tmp_path / "missing-after.json")
