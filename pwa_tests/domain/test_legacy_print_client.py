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
    assert requested_paths == ["/events", "/events/event-one/pupils?lesson=4"]
    assert supplied_tokens == ["explicit-test-token", "explicit-test-token"]
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
        assert path == "/events/event-two/pupils?lesson=4"
        return rows, {
            "ETag": '"digest"',
            "X-Print-Event": "event-two",
            "X-Print-Lesson": "4",
            "X-Print-Plan": "plan-event-two",
            "X-Print-Plan-Version": "1",
        }

    monkeypatch.setattr(client, "_get", fake_pupils)
    filename = tmp_path / "portal-print.json"
    assert client.refresh_portal_conduit(
        4, filename, token="test-token", event_id="event-two"
    ) == [{"ID": "student.login"}]
    assert json.loads(filename.read_text())["eventId"] == "event-two"


def test_absent_snapshot_is_not_a_silent_excel_fallback(tmp_path):
    with pytest.raises(RuntimeError, match="сначала запустите a11"):
        client.load_portal_conduit(4, tmp_path / "missing.json")
