"""Authenticated HTTP proof for the Phase-7 classroom catalog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

import pytest
from aiohttp import web
from argon2 import PasswordHasher

from apps import pwa_app
from apps.pwa_api.auth_service import PwaAuthService
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.auth import PwaAuthRepository
from helpers.config import Config
from helpers.consts import USER_TYPE
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState
from helpers.pwa.auth_config import AuthRuntimeConfig, COOKIE_POLICY
from models.pwa.auth import AuthAudience, CredentialHasher


ORIGIN = "http://127.0.0.1:5380"
HOST = "127.0.0.1:5380"
NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
ADMIN_ID = 958_001
TEACHER_ID = 958_002
TEST_HASHER = PasswordHasher(
    time_cost=1,
    memory_cost=8,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)


def _auth_config() -> AuthRuntimeConfig:
    return AuthRuntimeConfig(
        origins_by_audience=MappingProxyType(
            {audience: frozenset({ORIGIN}) for audience in AuthAudience}
        ),
        trusted_proxy_networks=(),
        trusted_proxy_hops=0,
        access_ttl_seconds=900,
        secure_cookies=False,
        signing_keys=("s" * 32,),
        refresh_pepper=b"r" * 32,
        throttle_pepper=b"t" * 32,
        test_only_defaults=True,
    )


def _seed_auth(factory: PwaConnectionFactory) -> None:
    now = NOW.isoformat(timespec="microseconds").replace("+00:00", "Z")

    def seed(connection) -> None:
        connection.executemany(
            "INSERT INTO users (id, public_id, type, name, surname) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (
                    ADMIN_ID,
                    "classroom-http-admin",
                    int(USER_TYPE.ADMIN),
                    "Иван",
                    "Администратор",
                ),
                (
                    TEACHER_ID,
                    "classroom-http-teacher",
                    int(USER_TYPE.TEACHER),
                    "Мария",
                    "Учитель",
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES (?, 'staff', ?, ?, NULL, 'synthetic-test', 'password', ?, ?, "
            "'active', ?, ?)",
            (
                (
                    "classroom-http-account-admin",
                    "classroom-http-admin",
                    "classroom-http-admin",
                    TEST_HASHER.hash("admin-password"),
                    ADMIN_ID,
                    now,
                    now,
                ),
                (
                    "classroom-http-account-teacher",
                    "classroom-http-teacher",
                    "classroom-http-teacher",
                    TEST_HASHER.hash("teacher-password"),
                    TEACHER_ID,
                    now,
                    now,
                ),
            ),
        )

    factory.run_write(seed)


@dataclass(frozen=True, slots=True)
class ClassroomHttpFixture:
    client: object
    factory: PwaConnectionFactory
    cookies: MappingProxyType


@pytest.fixture()
async def classroom_http(tmp_path, aiohttp_client) -> ClassroomHttpFixture:
    database_path = tmp_path / "classroom-http.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    _seed_auth(factory)
    auth_config = _auth_config()
    auth_service = await PwaAuthService.create(
        PwaAuthRepository(
            factory,
            clock=lambda: NOW,
            credential_hasher=TEST_HASHER,
        ),
        auth_config,
        credential_hasher=CredentialHasher(TEST_HASHER),
        clock=lambda: NOW,
    )
    app = web.Application()
    app[RUNTIME_CONFIG] = Config(
        runtime_profile="pwa-e2e",
        pwa_instance="classroom-http-test",
        config_name="classroom_http_test",
        pwa_prototype=True,
        nats_server=None,
    )
    pwa_app.configure(
        app,
        broker=InProcessBroker("classroom_http_test"),
        auth_runtime_config=auth_config,
        auth_service=auth_service,
    )
    # The route reads the same verified connection boundary as production.
    # Setting it after composition keeps unrelated content/review routes out of
    # this focused HTTP fixture.
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    client = await aiohttp_client(app)

    async def login(username: str, password: str) -> str:
        response = await client.post(
            "/staff/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=_headers(unsafe=True),
        )
        assert response.status == 200, await response.text()
        cookie = response.cookies[COOKIE_POLICY[AuthAudience.STAFF].access_name].value
        client.session.cookie_jar.clear()
        return cookie

    return ClassroomHttpFixture(
        client=client,
        factory=factory,
        cookies=MappingProxyType(
            {
                "admin": await login("classroom-http-admin", "admin-password"),
                "teacher": await login("classroom-http-teacher", "teacher-password"),
            }
        ),
    )


def _headers(*, unsafe: bool = False, if_match: str | None = None):
    headers = {"Host": HOST, "X-Request-ID": "classroom.http.test"}
    if unsafe:
        headers.update({"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"})
    if if_match is not None:
        headers["If-Match"] = if_match
    return headers


def _cookies(fixture: ClassroomHttpFixture, identity: str):
    return {COOKIE_POLICY[AuthAudience.STAFF].access_name: fixture.cookies[identity]}


def _seed_layout_scope(factory: PwaConnectionFactory) -> None:
    now = NOW.isoformat(timespec="microseconds").replace("+00:00", "Z")

    def seed(connection) -> None:
        student_id = connection.execute(
            "INSERT INTO users (public_id, type, name, surname) "
            "VALUES ('classroom-layout-student', 0, 'Анна', 'Белова') RETURNING id"
        ).fetchone()["id"]
        season_id = connection.execute(
            "INSERT INTO seasons "
            "(public_id, code, title, starts_on, ends_on, session_expires_on, "
            "status, created_at, updated_at) VALUES "
            "('classroom-layout-season', 'layout-season', 'Layout season', "
            "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) RETURNING id",
            (now, now),
        ).fetchone()["id"]
        course_id = connection.execute(
            "INSERT INTO courses "
            "(public_id, season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "('classroom-layout-course', ?, 'math-layout', 'Математика', 'math', "
            "'active', 1, 'math', ?, ?) RETURNING id",
            (season_id, now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, public_id, course_id, "
            "status, color_key, created_at, updated_at) VALUES "
            "('layout-beginner', 'н', 'Начинающие', 1, 1, 0, 0, 0, 1.0, "
            "'classroom-layout-group', ?, 'active', 'beginner', ?, ?)",
            (course_id, now, now),
        )
        connection.execute(
            "INSERT INTO course_enrollments "
            "(public_id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) VALUES "
            "('classroom-layout-enrollment', ?, ?, 'layout-beginner', "
            "'in_person', 'active', ?, ?)",
            (student_id, course_id, now, now),
        )
        course_lesson_id = connection.execute(
            "INSERT INTO course_lessons "
            "(public_id, course_id, lesson_number, created_at, updated_at) "
            "VALUES ('classroom-layout-course-lesson', ?, 41, ?, ?) RETURNING id",
            (course_id, now, now),
        ).fetchone()["id"]
        group_lesson_id = connection.execute(
            "INSERT INTO group_lessons "
            "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) VALUES "
            "('classroom-layout-group-lesson', ?, ?, 'layout-beginner', "
            "'2026-10-01', 'Europe/Moscow', 'active', ?, ?) RETURNING id",
            (course_lesson_id, course_id, now, now),
        ).fetchone()["id"]
        event_id = connection.execute(
            "INSERT INTO in_person_events "
            "(public_id, season_id, name, starts_at, ends_at, status, "
            "created_by_user_id, updated_by_user_id, created_at, updated_at) VALUES "
            "('classroom-layout-event', ?, 'Очное занятие', "
            "'2026-10-11T10:00:00Z', '2026-10-11T13:00:00Z', 'scheduled', "
            "?, ?, ?, ?) RETURNING id",
            (season_id, ADMIN_ID, ADMIN_ID, now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO in_person_event_group_lessons "
            "(in_person_event_id, group_lesson_id, added_by_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (event_id, group_lesson_id, ADMIN_ID, now),
        )
        connection.executemany(
            "INSERT INTO classrooms "
            "(public_id, name, normalized_name, status, created_by_user_id, "
            "updated_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, ?, 'active', ?, ?, ?, ?)",
            (
                ("classroom-layout-201", "201", "201", ADMIN_ID, ADMIN_ID, now, now),
                ("classroom-layout-202", "202", "202", ADMIN_ID, ADMIN_ID, now, now),
            ),
        )

    factory.run_write(seed)


@pytest.mark.asyncio
async def test_only_admin_can_manage_classroom_catalog(classroom_http):
    unauthenticated = await classroom_http.client.get(
        "/staff/api/v1/classrooms", headers=_headers()
    )
    assert unauthenticated.status == 401

    teacher = await classroom_http.client.get(
        "/staff/api/v1/classrooms",
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403
    assert (await teacher.json())["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_admin_catalog_round_trip_duplicate_search_and_stale_version(
    classroom_http,
):
    created = await classroom_http.client.post(
        "/staff/api/v1/classrooms",
        json={"schemaVersion": 1, "name": "  Актовый зал  "},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert created.status == 201, await created.text()
    created_payload = await created.json()
    assert created_payload["requestId"] == "classroom.http.test"
    room = created_payload["classroom"]
    assert room["name"] == "Актовый зал"
    assert room["status"] == "active"
    assert room["version"] == 1
    assert created.headers["ETag"] == f'"{room["publicId"]}:v1"'

    duplicate = await classroom_http.client.post(
        "/staff/api/v1/classrooms",
        json={"schemaVersion": 1, "name": "АКТОВЫЙ ЗАЛ"},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert duplicate.status == 409
    duplicate_payload = await duplicate.json()
    assert duplicate_payload["error"]["code"] == "classroom_name_conflict"
    assert duplicate_payload["error"]["details"] == {
        "existingPublicId": room["publicId"],
        "existingName": "Актовый зал",
    }

    searched = await classroom_http.client.get(
        "/staff/api/v1/classrooms?status=all&search=АКТОВЫЙ",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert searched.status == 200
    searched_payload = await searched.json()
    assert searched_payload["requestId"] == "classroom.http.test"
    assert [item["publicId"] for item in searched_payload["items"]] == [
        room["publicId"]
    ]

    stale = await classroom_http.client.patch(
        f"/staff/api/v1/classrooms/{room['publicId']}",
        json={"schemaVersion": 1, "name": "Большой зал"},
        headers=_headers(unsafe=True, if_match=f'"{room["publicId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "version_conflict"

    renamed = await classroom_http.client.patch(
        f"/staff/api/v1/classrooms/{room['publicId']}",
        json={"schemaVersion": 1, "name": "Большой зал"},
        headers=_headers(unsafe=True, if_match=f'"{room["publicId"]}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert renamed.status == 200, await renamed.text()
    renamed_room = (await renamed.json())["classroom"]
    assert (renamed_room["name"], renamed_room["version"]) == ("Большой зал", 2)

    archived = await classroom_http.client.post(
        f"/staff/api/v1/classrooms/{room['publicId']}/archive",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{room["publicId"]}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert archived.status == 200
    assert (await archived.json())["classroom"]["status"] == "archived"

    active = await classroom_http.client.get(
        "/staff/api/v1/classrooms",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert (await active.json())["items"] == []

    restored = await classroom_http.client.post(
        f"/staff/api/v1/classrooms/{room['publicId']}/restore",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{room["publicId"]}:v3"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert restored.status == 200
    assert (await restored.json())["classroom"]["version"] == 4

    def audit(connection):
        return connection.execute(
            "SELECT action, request_id FROM classroom_events ORDER BY id"
        ).fetchall()

    assert [tuple(row.values()) for row in classroom_http.factory.run_read(audit)] == [
        ("created", "classroom.http.test"),
        ("renamed", "classroom.http.test"),
        ("archived", "classroom.http.test"),
        ("restored", "classroom.http.test"),
    ]


@pytest.mark.asyncio
async def test_admin_materializes_updates_and_confirms_classroom_layout(classroom_http):
    _seed_layout_scope(classroom_http.factory)
    path = "/staff/api/v1/in-person-events/classroom-layout-event/classroom-layout"

    teacher = await classroom_http.client.get(
        path,
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    inherited = await classroom_http.client.get(
        path,
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert inherited.status == 200
    inherited_layout = (await inherited.json())["layout"]
    assert inherited_layout["state"] == "inherited"
    assert inherited_layout["publicId"] is None
    assert inherited_layout["groups"][0]["inPersonCount"] == 1

    materialized = await classroom_http.client.post(
        f"{path}/materialize",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert materialized.status == 200, await materialized.text()
    draft = (await materialized.json())["layout"]
    assert (draft["state"], draft["version"]) == ("draft", 1)
    layout_id = draft["publicId"]

    updated = await classroom_http.client.put(
        f"{path}/{layout_id}/rooms",
        json={
            "schemaVersion": 1,
            "mappings": [
                {
                    "classroomPublicId": "classroom-layout-201",
                    "groupLessonPublicId": "classroom-layout-group-lesson",
                },
                {
                    "classroomPublicId": "classroom-layout-202",
                    "groupLessonPublicId": "classroom-layout-group-lesson",
                },
            ],
        },
        headers=_headers(unsafe=True, if_match=f'"{layout_id}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert updated.status == 200, await updated.text()
    updated_layout = (await updated.json())["layout"]
    assert updated_layout["version"] == 2
    assert [room["classroomName"] for room in updated_layout["rooms"]] == [
        "201",
        "202",
    ]

    stale = await classroom_http.client.put(
        f"{path}/{layout_id}/rooms",
        json={"schemaVersion": 1, "mappings": []},
        headers=_headers(unsafe=True, if_match=f'"{layout_id}:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "version_conflict"

    confirmed = await classroom_http.client.post(
        f"{path}/{layout_id}/confirm",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=f'"{layout_id}:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert confirmed.status == 200, await confirmed.text()
    confirmed_payload = await confirmed.json()
    assert confirmed_payload["layout"]["state"] == "confirmed"
    assert confirmed_payload["layout"]["version"] == 3
    assert confirmed.headers["ETag"] == f'"{layout_id}:v3"'

    assignment_path = (
        "/staff/api/v1/in-person-events/classroom-layout-event/"
        "classroom-assignment-plan"
    )
    teacher_assignment = await classroom_http.client.get(
        assignment_path,
        headers=_headers(),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher_assignment.status == 403

    empty_plan = await classroom_http.client.get(
        assignment_path,
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert empty_plan.status == 200
    empty_payload = (await empty_plan.json())["assignmentPlan"]
    assert empty_payload["plan"] is None
    assert [room["name"] for room in empty_payload["rooms"]] == ["201", "202"]

    recalculated = await classroom_http.client.post(
        f"{assignment_path}/recalculate",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert recalculated.status == 200, await recalculated.text()
    plan_payload = (await recalculated.json())["assignmentPlan"]
    plan = plan_payload["plan"]
    assert (plan["state"], plan["version"]) == ("draft", 1)
    assert plan_payload["students"][0]["classroomName"] == "201"
    assert plan_payload["students"][0]["status"] == "assigned"
    plan_etag = recalculated.headers["ETag"]

    stale = await classroom_http.client.post(
        f"{assignment_path}/recalculate",
        json={"schemaVersion": 1},
        headers=_headers(
            unsafe=True,
            if_match=f'"{plan["publicId"]}:v99"',
        ),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale.status == 409
    assert (await stale.json())["error"]["code"] == "version_conflict"

    confirmed_plan = await classroom_http.client.post(
        f"{assignment_path}/{plan['publicId']}/confirm",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=plan_etag),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert confirmed_plan.status == 200, await confirmed_plan.text()
    confirmed_assignment = (await confirmed_plan.json())["assignmentPlan"]
    assert confirmed_assignment["plan"]["state"] == "confirmed"
    assert confirmed_assignment["plan"]["version"] == 2
