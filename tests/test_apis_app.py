from __future__ import annotations

import json

import db_methods as db
from apps import apis_app
from models import Problem

from .http_harness import FakeRequest


def _body(response):
    return json.loads(response.text)


def test_conduit_import_requires_bearer_token(live_seed_db, monkeypatch):
    monkeypatch.setattr(apis_app.config, "conduit_import_api_token", "secret-token")

    response = __import__("asyncio").run(apis_app.conduit_import(FakeRequest(json_data={"lesson": 1, "verdict": 17, "res_type": 4, "rows": []})))

    assert response.status == 401
    assert _body(response) == {"ok": False, "error": "missing_bearer_token"}


def test_conduit_import_rejects_wrong_token(live_seed_db, monkeypatch):
    monkeypatch.setattr(apis_app.config, "conduit_import_api_token", "secret-token")

    response = __import__("asyncio").run(
        apis_app.conduit_import(
            FakeRequest(
                headers={"Authorization": "Bearer wrong-token"},
                json_data={"lesson": 1, "verdict": 17, "res_type": 4, "rows": []},
            )
        )
    )

    assert response.status == 403
    assert _body(response) == {"ok": False, "error": "invalid_token"}


def test_conduit_import_validates_json_and_root_payload(live_seed_db, monkeypatch):
    monkeypatch.setattr(apis_app.config, "conduit_import_api_token", "secret-token")
    headers = {"Authorization": "Bearer secret-token"}

    invalid_json = __import__("asyncio").run(
        apis_app.conduit_import(FakeRequest(headers=headers, json_exc=ValueError("bad json")))
    )
    assert invalid_json.status == 400
    assert _body(invalid_json)["error"] == "invalid_json"

    invalid_payload = __import__("asyncio").run(
        apis_app.conduit_import(
            FakeRequest(headers=headers, json_data={"lesson": "1", "verdict": 17, "res_type": 4, "rows": []})
        )
    )
    assert invalid_payload.status == 400
    assert _body(invalid_payload)["error"] == "lesson_must_be_int"


def test_conduit_import_dry_run_reports_invalid_and_duplicate_rows(live_seed_db, monkeypatch):
    monkeypatch.setattr(apis_app.config, "conduit_import_api_token", "secret-token")
    headers = {"Authorization": "Bearer secret-token"}
    problem = Problem.get_by_key("i27c", 1, 1, "")
    assert problem is not None

    payload = {
        "lesson": 1,
        "verdict": 17,
        "res_type": 4,
        "dry_run": True,
        "rows": [
            {"token": "qwerty1", "problem_id": problem.id, "group_id": "i27c"},
            {"token": "qwerty1", "problem_id": problem.id, "group_id": "i27c"},
            {"token": "teacher_seed", "problem_id": problem.id, "group_id": "i27c"},
            {"token": "missing", "problem_id": problem.id, "group_id": "i27c"},
            {"token": "qwerty1", "problem_id": 999999, "group_id": "i27c"},
            {"token": "qwerty1", "problem_id": problem.id, "group_id": ""},
        ],
    }

    response = __import__("asyncio").run(apis_app.conduit_import(FakeRequest(headers=headers, json_data=payload)))

    assert response.status == 200
    body = _body(response)
    assert body["ok"] is True
    assert body["dry_run"] is True
    assert body["received_rows"] == 6
    assert body["valid_rows"] == 2
    assert body["insert_candidates"] == 1
    assert body["already_exists"] == 1
    assert body["inserted"] == 0
    assert body["skipped_invalid"] == 4
    assert {error["code"] for error in body["errors"]} == {
        "student_not_student",
        "student_not_found",
        "problem_not_found",
        "invalid_group_id",
    }
    inserted_rows = db.sql.conn.execute("select count(*) as cnt from results").fetchone()["cnt"]
    assert inserted_rows == 0


def test_conduit_import_inserts_rows_and_deduplicates_existing_records(live_seed_db, monkeypatch):
    monkeypatch.setattr(apis_app.config, "conduit_import_api_token", "secret-token")
    headers = {"Authorization": "Bearer secret-token"}
    problem = Problem.get_by_key("i27c", 1, 2, "")
    assert problem is not None
    payload = {
        "lesson": 1,
        "verdict": 17,
        "res_type": 4,
        "rows": [
            {"token": "qwerty1", "problem_id": problem.id, "group_id": "i27c"},
        ],
    }

    first = __import__("asyncio").run(apis_app.conduit_import(FakeRequest(headers=headers, json_data=payload)))
    first_body = _body(first)
    assert first.status == 200
    assert first_body["inserted"] == 1
    row = db.sql.conn.execute(
        "select * from results where student_id = 1 and problem_id = :problem_id",
        {"problem_id": problem.id},
    ).fetchone()
    assert row is not None
    assert row["verdict"] == 17
    assert row["res_type"] == 4
    assert row["teacher_id"] is None

    second = __import__("asyncio").run(apis_app.conduit_import(FakeRequest(headers=headers, json_data=payload)))
    second_body = _body(second)
    assert second.status == 200
    assert second_body["inserted"] == 0
    assert second_body["already_exists"] == 1
