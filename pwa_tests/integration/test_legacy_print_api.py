"""Real SQLite/HTTP compatibility proof for docs/printing/legacy-api.md."""

import sqlite3

import pytest
from aiohttp import web

from apps import pwa_app
from apps.pwa_api.legacy_print_routes import PREFIX
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from helpers.config import Config
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState
from helpers.pwa.auth_config import COOKIE_POLICY
from models.pwa.auth import AuthAudience
from models.pwa.classroom_assignments import confirm_assignment_plan
from pwa_tests.integration.test_classroom_catalog_http_api import (
    _auth_config,
    HOST,
    TEST_HASHER,
)
from pwa_tests.integration.test_phase7_classroom_assignment_migration import (
    _insert_parents,
    NOW,
)


TOKEN = "synthetic-legacy-print-token-for-tests-only"


@pytest.fixture
async def print_api(tmp_path, aiohttp_client):
    path = tmp_path / "print.sqlite3"
    apply_schema_migrations(path)
    factory = PwaConnectionFactory(path)

    def seed(connection):
        original_factory = connection.row_factory
        connection.row_factory = sqlite3.Row
        _insert_parents(connection)
        connection.row_factory = original_factory
        connection.execute("UPDATE groups SET short_code='н'")
        connection.execute("UPDATE users SET token='old-token', grade='7' WHERE id=1")
        connection.execute(
            "INSERT INTO auth_accounts (audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES ('student','ivanov.ivan','ivanov.ivan',1,'synthetic-test',"
            "'telegram_token','not-a-real-hash',1,'active',?,?)",
            (NOW, NOW),
        )
        connection.execute(
            "INSERT INTO auth_accounts(audience,username,username_normalized,provisioning_source,"
            "credential_kind,credential_hash,linked_user_id,status,created_at,updated_at) "
            "VALUES('staff','admin','admin','synthetic-test','password',?,2,'active',?,?)",
            (TEST_HASHER.hash("synthetic-admin-only"), NOW, NOW),
        )
        event_id = connection.execute(
            "SELECT public_id FROM in_person_events"
        ).fetchone()["public_id"]
        plan = connection.execute(
            "SELECT public_id,version FROM classroom_assignment_plans"
        ).fetchone()
        confirm_assignment_plan(
            connection,
            event_public_id=event_id,
            plan_public_id=plan["public_id"],
            expected_version=plan["version"],
            actor_user_id=2,
            now=NOW,
        )
        connection.execute(
            "INSERT INTO seasons "
            "(code,title,starts_on,ends_on,session_expires_on,status,created_at,updated_at) "
            "VALUES('archived-print-test','Archived','2029-01-01','2029-12-31',"
            "'2030-01-31','archived',?,?)",
            (NOW, NOW),
        )
        connection.execute(
            "INSERT INTO in_person_events "
            "(season_id,name,starts_at,ends_at,status,created_by_user_id,"
            "updated_by_user_id,created_at,updated_at) "
            "VALUES((SELECT id FROM seasons WHERE code='archived-print-test'),"
            "'Старое событие','2029-09-14T13:50:00Z','2029-09-14T16:00:00Z',"
            "'scheduled',2,2,?,?)",
            (NOW, NOW),
        )
        return event_id

    event_id = factory.run_write(seed)
    config = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="legacy-print-test",
        config_name="legacy_print_test",
        pwa_prototype=True,
        nats_server=None,
        legacy_print_api_token=TOKEN,
        first_admin_password="synthetic-admin-only",
    )
    app = web.Application()
    app[RUNTIME_CONFIG] = config
    pwa_app.configure(
        app,
        broker=InProcessBroker("legacy_print_test"),
        auth_runtime_config=_auth_config(),
    )
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    client = await aiohttp_client(app)
    return client, factory, config, f"{PREFIX}/events/{event_id}/pupils?lesson=41"


def headers(**extra):
    return {"Host": HOST, "Authorization": f"Bearer {TOKEN}", **extra}


async def test_round_trip_uses_login_not_secret_and_is_read_only(print_api):
    client, factory, _, url = print_api
    before = factory.run_read(
        lambda c: (
            c.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
            c.execute("SELECT version FROM classroom_assignment_plans").fetchone()[
                "version"
            ],
        )
    )
    response = await client.get(url, headers=headers())
    assert response.status == 200, await response.text()
    rows = await response.json()
    assert rows == [
        {
            "Фамилия": "Иванов",
            "Имя": "Иван",
            "ID": "ivanov.ivan",
            "IDd": "ivanov.ivan",
            "Клс": "7",
            "Скрыть": None,
            "Уровень": "н",
            "Аудитория": "201",
            "Посещаемость": None,
            "Ср3": "",
            "ФИО": "Иванов Иван",
            "ФИ.": "Иванов И.",
            "UserID": 1,
            "GroupID": "assignment-n",
            "Строчка": 5,
        }
    ]
    assert "old-token" not in await response.text()
    assert "no-store" in response.headers["Cache-Control"]
    etag = response.headers["ETag"]
    assert response.headers["X-Print-Lesson"] == "41"
    same = await client.get(url, headers=headers(**{"If-Match": etag}))
    assert same.status == 200
    listing = await client.get(PREFIX + "/events", headers=headers())
    assert listing.status == 200
    listed_events = (await listing.json())["events"]
    assert len(listed_events) == 1
    listed_event = listed_events[0]
    assert listed_event["plan_id"] == response.headers["X-Print-Plan"]
    assert listed_event["lesson_numbers"] == [41]
    after = factory.run_read(
        lambda c: (
            c.execute("SELECT count(*) AS n FROM results").fetchone()["n"],
            c.execute("SELECT version FROM classroom_assignment_plans").fetchone()[
                "version"
            ],
        )
    )
    assert before == after
    factory.run_write(lambda c: c.execute("UPDATE users SET name='Пётр' WHERE id=1"))
    changed = await client.get(url, headers=headers(**{"If-Match": etag}))
    assert changed.status == 412


@pytest.mark.parametrize(
    "authorization", [None, "Bearer wrong", "Bearer токен", "Basic abc"]
)
async def test_no_cookie_or_query_token_bypass(print_api, authorization):
    client, _, _, url = print_api
    request_headers = {"Host": HOST}
    if authorization is not None:
        request_headers["Authorization"] = authorization
    response = await client.get(url + "&token=" + TOKEN, headers=request_headers)
    assert response.status == 401
    assert "no-store" in response.headers["Cache-Control"]
    assert "Иванов" not in await response.text()


@pytest.mark.parametrize("token", ["", "short", None, 123])
async def test_unconfigured_token_fails_closed(print_api, token):
    client, _, config, url = print_api
    config.legacy_print_api_token = token
    response = await client.get(url, headers=headers())
    assert response.status == 503


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("UPDATE course_enrollments SET attendance_mode='online'", "roster_changed"),
        (
            "DELETE FROM auth_accounts WHERE audience='student'",
            "missing_or_duplicate_login",
        ),
        ("UPDATE classrooms SET status='archived'", "roster_changed"),
        ("UPDATE groups SET short_code='other'", "unsupported_level"),
        ("UPDATE users SET name='' WHERE id=1", "missing_name"),
    ],
)
async def test_inconsistent_state_does_not_silently_drop_pupils(
    print_api, mutation, code
):
    client, factory, _, url = print_api
    factory.run_write(lambda c: c.execute(mutation))
    response = await client.get(url, headers=headers())
    assert response.status == 409, await response.text()
    assert (await response.json())["error"]["code"] == "legacy_print_" + code


async def test_lesson_event_validation_and_browser_auth_stays_private(print_api):
    client, _, _, url = print_api
    for query, status in [("lesson=42", 409), ("", 422), ("lesson=41&lesson=41", 422)]:
        response = await client.get(url.split("?")[0] + "?" + query, headers=headers())
        assert response.status == status
    missing = await client.get(
        PREFIX + "/events/missing/pupils?lesson=41", headers=headers()
    )
    assert missing.status == 404
    wrong_host = await client.get(url, headers=headers(Host="untrusted.invalid"))
    assert wrong_host.status == 403
    browser = await client.get("/staff/api/v1/classrooms", headers=headers())
    assert browser.status == 401
    write = await client.post(url, headers=headers())
    assert write.status == 405


async def test_working_draft_blocks_export(print_api):
    from models.pwa.classroom_assignments import recalculate_assignment_plan

    client, factory, _, url = print_api
    event_id = url.split("/events/")[1].split("/")[0]
    factory.run_write(
        lambda c: recalculate_assignment_plan(
            c,
            event_public_id=event_id,
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now=NOW,
        )
    )
    response = await client.get(url, headers=headers())
    assert response.status == 409
    assert (await response.json())["error"]["code"] == "legacy_print_plan_not_confirmed"


async def test_real_admin_cookie_does_not_replace_print_token(print_api):
    client, _, _, url = print_api
    login = await client.post(
        "/staff/api/v1/auth/login",
        json={"username": "admin", "password": "synthetic-admin-only"},
        headers={"Host": HOST, "Origin": "http://" + HOST},
    )
    assert login.status == 200, await login.text()
    cookie_name = COOKIE_POLICY[AuthAudience.STAFF].access_name
    cookie = login.cookies[cookie_name].value
    response = await client.get(
        url,
        headers={
            "Host": HOST,
            "Cookie": f"{cookie_name}={cookie}",
        },
    )
    assert response.status == 401


async def test_new_enrollment_requires_new_plan_and_sorts_yo_like_e(print_api):
    from models.pwa.classroom_assignments import recalculate_assignment_plan

    client, factory, _, url = print_api
    event_id = url.split("/events/")[1].split("/")[0]

    def add_student(connection):
        connection.execute(
            "INSERT INTO users(id,type,name,surname) VALUES(99,1,'ПЁТР','Ёлкин')"
        )
        connection.execute(
            "INSERT INTO course_enrollments(student_user_id,course_id,active_group_id,"
            "attendance_mode,status,created_at,updated_at) "
            "VALUES(99,1,'assignment-n','in_person','active',?,?)",
            (NOW, NOW),
        )
        connection.execute(
            "INSERT INTO auth_accounts(audience,username,username_normalized,username_algorithm_version,"
            "provisioning_source,credential_kind,credential_hash,linked_user_id,status,created_at,updated_at) "
            "VALUES('student','elkin.petr','elkin.petr',1,'synthetic-test','telegram_token',"
            "'not-a-real-hash',99,'active',?,?)",
            (NOW, NOW),
        )

    factory.run_write(add_student)
    response = await client.get(url, headers=headers())
    assert response.status == 409

    def reconfirm(connection):
        data = recalculate_assignment_plan(
            connection,
            event_public_id=event_id,
            plan_public_id=None,
            expected_version=None,
            actor_user_id=2,
            now=NOW,
        )
        confirm_assignment_plan(
            connection,
            event_public_id=event_id,
            plan_public_id=data["plan"]["public_id"],
            expected_version=data["plan"]["version"],
            actor_user_id=2,
            now=NOW,
        )

    factory.run_write(reconfirm)
    response = await client.get(url, headers=headers())
    assert response.status == 200, await response.text()
    rows = await response.json()
    assert [row["ФИО"] for row in rows] == ["Ёлкин ПЁТР", "Иванов Иван"]
    assert [row["Строчка"] for row in rows] == [5, 6]
