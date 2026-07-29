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
STUDENT_ID = 958_003
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
                (
                    STUDENT_ID,
                    "classroom-layout-student",
                    int(USER_TYPE.STUDENT),
                    "Анна",
                    "Белова",
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, "
            "username_algorithm_version, provisioning_source, credential_kind, "
            "credential_hash, linked_user_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'synthetic-test', ?, ?, ?, "
            "'active', ?, ?)",
            (
                (
                    "classroom-http-account-admin",
                    "staff",
                    "classroom-http-admin",
                    "classroom-http-admin",
                    None,
                    "password",
                    TEST_HASHER.hash("admin-password"),
                    ADMIN_ID,
                    now,
                    now,
                ),
                (
                    "classroom-http-account-teacher",
                    "staff",
                    "classroom-http-teacher",
                    "classroom-http-teacher",
                    None,
                    "password",
                    TEST_HASHER.hash("teacher-password"),
                    TEACHER_ID,
                    now,
                    now,
                ),
                (
                    "classroom-http-account-student",
                    "student",
                    "classroom-http-student",
                    "classroom-http-student",
                    1,
                    "telegram_token",
                    TEST_HASHER.hash("student-password"),
                    STUDENT_ID,
                    now,
                    now,
                ),
            ),
        )
        family_account_id = connection.execute(
            "INSERT INTO auth_accounts "
            "(public_id, audience, username, username_normalized, display_name, "
            "provisioning_source, credential_kind, credential_hash, status, "
            "created_at, updated_at) VALUES "
            "('classroom-http-account-family', 'family', 'classroom-http-family', "
            "'classroom-http-family', 'Семья Беловой', 'synthetic-test', "
            "'password', ?, 'active', ?, ?) RETURNING id",
            (TEST_HASHER.hash("family-password"), now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO family_student_links "
            "(family_account_id, student_user_id, relationship_label, is_primary, "
            "created_at, updated_at) VALUES (?, ?, 'родитель', 1, ?, ?)",
            (family_account_id, STUDENT_ID, now, now),
        )
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
        enrollment_id = connection.execute(
            "INSERT INTO course_enrollments "
            "(public_id, student_user_id, course_id, active_group_id, "
            "attendance_mode, status, created_at, updated_at) VALUES "
            "('classroom-layout-enrollment', ?, ?, 'layout-beginner', "
            "'in_person', 'active', ?, ?) RETURNING id",
            (STUDENT_ID, course_id, now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO course_group_access "
            "(enrollment_id, course_id, group_id, valid_from, created_at, updated_at) "
            "VALUES (?, ?, 'layout-beginner', ?, ?, ?)",
            (enrollment_id, course_id, now, now, now),
        )

    factory.run_write(seed)


@dataclass(frozen=True, slots=True)
class ClassroomHttpFixture:
    client: object
    factory: PwaConnectionFactory
    cookies: MappingProxyType
    student_cookie: str
    family_cookie: str
    telegram_messages: list[tuple[int, str]]


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

    telegram_messages: list[tuple[int, str]] = []

    async def send_classroom_telegram(chat_id: int, text: str) -> int:
        telegram_messages.append((chat_id, text))
        return len(telegram_messages)

    pwa_app.configure(
        app,
        broker=InProcessBroker("classroom_http_test"),
        auth_runtime_config=auth_config,
        auth_service=auth_service,
        classroom_telegram_sender=send_classroom_telegram,
    )
    # The route reads the same verified connection boundary as production.
    # Setting it after composition keeps unrelated content/review routes out of
    # this focused HTTP fixture.
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    client = await aiohttp_client(app)

    async def login(audience: AuthAudience, username: str, password: str) -> str:
        credential_field = (
            "telegramToken" if audience is AuthAudience.STUDENT else "password"
        )
        response = await client.post(
            f"/{audience.value}/api/v1/auth/login",
            json={"username": username, credential_field: password},
            headers=_headers(unsafe=True),
        )
        assert response.status == 200, await response.text()
        cookie = response.cookies[COOKIE_POLICY[audience].access_name].value
        client.session.cookie_jar.clear()
        return cookie

    return ClassroomHttpFixture(
        client=client,
        factory=factory,
        cookies=MappingProxyType(
            {
                "admin": await login(
                    AuthAudience.STAFF, "classroom-http-admin", "admin-password"
                ),
                "teacher": await login(
                    AuthAudience.STAFF, "classroom-http-teacher", "teacher-password"
                ),
            }
        ),
        student_cookie=await login(
            AuthAudience.STUDENT,
            "classroom-http-student",
            "student-password",
        ),
        family_cookie=await login(
            AuthAudience.FAMILY,
            "classroom-http-family",
            "family-password",
        ),
        telegram_messages=telegram_messages,
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
    now = "2026-07-01T12:00:00.000000Z"

    def seed(connection) -> None:
        season_id = connection.execute(
            "SELECT id FROM seasons WHERE public_id = 'classroom-layout-season'"
        ).fetchone()["id"]
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()["id"]
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

    manually_moved = await classroom_http.client.put(
        f"{assignment_path}/{plan['publicId']}/assignments",
        json={
            "schemaVersion": 1,
            "assignments": [
                {
                    "enrollmentPublicId": "classroom-layout-enrollment",
                    "classroomPublicId": "classroom-layout-202",
                    "confirmGroupChange": False,
                }
            ],
        },
        headers=_headers(unsafe=True, if_match=plan_etag),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert manually_moved.status == 200, await manually_moved.text()
    moved_payload = (await manually_moved.json())["assignmentPlan"]
    assert moved_payload["students"][0]["classroomName"] == "202"
    assert moved_payload["students"][0]["source"] == "manual"
    assert moved_payload["plan"]["version"] == 2

    cursors_before_confirm = dict(
        classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]
    )
    confirmed_plan = await classroom_http.client.post(
        f"{assignment_path}/{plan['publicId']}/confirm",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match=manually_moved.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert confirmed_plan.status == 200, await confirmed_plan.text()
    confirmed_assignment = (await confirmed_plan.json())["assignmentPlan"]
    assert confirmed_assignment["plan"]["state"] == "confirmed"
    assert confirmed_assignment["plan"]["version"] == 3
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        **cursors_before_confirm,
        "student": cursors_before_confirm["student"] + 1,
        "family": cursors_before_confirm["family"] + 1,
    }

    history = await classroom_http.client.get(
        f"{assignment_path}/{plan['publicId']}/students/"
        "classroom-layout-enrollment/history",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert history.status == 200, await history.text()
    history_items = (await history.json())["items"]
    assert len(history_items) == 1
    assert (
        history_items[0]["eventName"],
        history_items[0]["classroomName"],
        history_items[0]["groupName"],
    ) == ("Очное занятие", "202", "Начинающие")

    student_response = await classroom_http.client.get(
        "/student/api/v1/classroom-assignments",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.STUDENT].access_name: (
                classroom_http.student_cookie
            )
        },
    )
    assert student_response.status == 200, await student_response.text()
    student_item = (await student_response.json())["items"][0]
    assert (
        student_item["status"],
        student_item["classroomName"],
        student_item["announcedAt"],
    ) == ("assigned", "202", None)

    family_response = await classroom_http.client.get(
        "/family/api/v1/children/classroom-layout-student/classroom-assignments",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.FAMILY].access_name: classroom_http.family_cookie
        },
    )
    assert family_response.status == 200, await family_response.text()
    family_item = (await family_response.json())["items"][0]
    assert family_item == student_item

    forbidden_child = await classroom_http.client.get(
        "/family/api/v1/children/someone-else/classroom-assignments",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.FAMILY].access_name: classroom_http.family_cookie
        },
    )
    assert forbidden_child.status == 403

    delivery_preview_path = (
        f"/staff/api/v1/classroom-assignment-plans/{plan['publicId']}/delivery-preview"
    )
    teacher_delivery = await classroom_http.client.post(
        delivery_preview_path,
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher_delivery.status == 403

    classroom_http.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE users SET chat_id = 179179 WHERE id = ?", (STUDENT_ID,)
        )
    )
    preview_response = await classroom_http.client.post(
        delivery_preview_path,
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = (await preview_response.json())["preview"]
    assert (
        preview["recipientCount"],
        preview["changedCount"],
        preview["telegramUnavailableCount"],
    ) == (1, 1, 0)
    assert preview["recipients"][0]["telegramAvailable"] is True
    assert "chatId" not in preview["recipients"][0]

    cursors_before_delivery = dict(
        classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]
    )
    delivery_response = await classroom_http.client.post(
        delivery_preview_path.removesuffix("/delivery-preview") + "/delivery-batches",
        json={
            "schemaVersion": 1,
            "channels": ["pwa", "telegram"],
            "expectedPlanVersion": preview["planVersion"],
            "previewHash": preview["previewHash"],
            "idempotencyKey": "classroom-http-delivery-1",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert delivery_response.status == 201, await delivery_response.text()
    delivery = (await delivery_response.json())["batch"]
    assert delivery["state"] == "completed"
    assert delivery["channelCounts"] == {
        "pwa": {"sent": 1},
        "telegram": {"sent": 1},
    }
    assert classroom_http.telegram_messages == [
        (
            179179,
            "Очное занятие\nМатематика · Начинающие\n\n"
            "Ваша аудитория: 202.\n\n"
            "Если вы не планируете прийти очно, пожалуйста, заранее измените "
            "режим занятия в личном кабинете.",
        )
    ]
    assert "chatId" not in delivery["recipients"][0]
    latest_delivery_response = await classroom_http.client.get(
        delivery_preview_path.removesuffix("/delivery-preview") + "/delivery-latest",
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert latest_delivery_response.status == 200
    assert (await latest_delivery_response.json())["batch"]["publicId"] == delivery[
        "publicId"
    ]
    assert dict(classroom_http.client.app[pwa_app.PWA_STATE]["cursors"]) == {
        **cursors_before_delivery,
        "student": cursors_before_delivery["student"] + 1,
    }

    announced_student = await classroom_http.client.get(
        "/student/api/v1/classroom-assignments",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.STUDENT].access_name: (
                classroom_http.student_cookie
            )
        },
    )
    announced_at = (await announced_student.json())["items"][0]["announcedAt"]
    assert announced_at is not None
    announced_family = await classroom_http.client.get(
        "/family/api/v1/children/classroom-layout-student/classroom-assignments",
        headers=_headers(),
        cookies={
            COOKIE_POLICY[AuthAudience.FAMILY].access_name: (
                classroom_http.family_cookie
            )
        },
    )
    assert (await announced_family.json())["items"][0]["announcedAt"] == announced_at

    stale_delivery = await classroom_http.client.post(
        delivery_preview_path.removesuffix("/delivery-preview") + "/delivery-batches",
        json={
            "schemaVersion": 1,
            "channels": ["pwa"],
            "expectedPlanVersion": preview["planVersion"],
            "previewHash": "0" * 64,
            "idempotencyKey": "classroom-http-delivery-stale",
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert stale_delivery.status == 409

    archived_room = await classroom_http.client.post(
        "/staff/api/v1/classrooms/classroom-layout-202/archive",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match='"classroom-layout-202:v1"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert archived_room.status == 200, await archived_room.text()
    unavailable = await classroom_http.client.get(
        assignment_path,
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    unavailable_plan = (await unavailable.json())["assignmentPlan"]
    assert unavailable_plan["plan"]["state"] == "confirmed"
    assert unavailable_plan["students"][0]["status"] == "reassigning"
    assert unavailable_plan["students"][0]["classroomName"] is None

    recalculated_after_archive = await classroom_http.client.post(
        f"{assignment_path}/recalculate",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert recalculated_after_archive.status == 200
    recalculated_payload = (await recalculated_after_archive.json())["assignmentPlan"]
    assert recalculated_payload["students"][0]["classroomName"] == "201"

    restored_room = await classroom_http.client.post(
        "/staff/api/v1/classrooms/classroom-layout-202/restore",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True, if_match='"classroom-layout-202:v2"'),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert restored_room.status == 200
    after_restore = await classroom_http.client.get(
        assignment_path,
        headers=_headers(),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert (await after_restore.json())["assignmentPlan"]["students"][0][
        "classroomName"
    ] == "201"


@pytest.mark.asyncio
async def test_admin_confirms_group_change_with_classroom_move(classroom_http):
    _seed_layout_scope(classroom_http.factory)
    now = NOW.isoformat(timespec="microseconds").replace("+00:00", "Z")

    def seed_second_group(connection):
        course = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'classroom-layout-course'"
        ).fetchone()
        course_lesson = connection.execute(
            "SELECT id FROM course_lessons "
            "WHERE public_id = 'classroom-layout-course-lesson'"
        ).fetchone()
        event = connection.execute(
            "SELECT id FROM in_person_events WHERE public_id = 'classroom-layout-event'"
        ).fetchone()
        connection.execute(
            "UPDATE users SET group_id = 'layout-beginner' "
            "WHERE public_id = 'classroom-layout-student'"
        )
        connection.execute(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, public_id, course_id, "
            "status, color_key, created_at, updated_at) VALUES "
            "('layout-advanced', 'п', 'Продолжающие', 2, 1, 0, 0, 0, 1.0, "
            "'classroom-layout-group-advanced', ?, 'active', 'advanced', ?, ?)",
            (course["id"], now, now),
        )
        group_lesson_id = connection.execute(
            "INSERT INTO group_lessons "
            "(public_id, course_lesson_id, course_id, group_id, cycle_anchor_date, "
            "business_timezone, status, created_at, updated_at) VALUES "
            "('classroom-layout-group-lesson-advanced', ?, ?, 'layout-advanced', "
            "'2026-10-01', 'Europe/Moscow', 'active', ?, ?) RETURNING id",
            (course_lesson["id"], course["id"], now, now),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO in_person_event_group_lessons "
            "(in_person_event_id, group_lesson_id, added_by_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (event["id"], group_lesson_id, ADMIN_ID, now),
        )
        room_id = connection.execute(
            "INSERT INTO classrooms "
            "(public_id, name, normalized_name, status, created_by_user_id, "
            "updated_by_user_id, created_at, updated_at) VALUES "
            "('classroom-layout-301', '301', '301', 'active', ?, ?, ?, ?) "
            "RETURNING id",
            (ADMIN_ID, ADMIN_ID, now, now),
        ).fetchone()["id"]
        first_group_lesson = connection.execute(
            "SELECT id FROM group_lessons "
            "WHERE public_id = 'classroom-layout-group-lesson'"
        ).fetchone()["id"]
        first_rooms = connection.execute(
            "SELECT id FROM classrooms WHERE public_id IN "
            "('classroom-layout-201', 'classroom-layout-202') ORDER BY public_id"
        ).fetchall()
        layout_id = connection.execute(
            "INSERT INTO classroom_layout_versions "
            "(public_id, in_person_event_id, state, created_by_user_id, "
            "created_at, updated_at) VALUES "
            "('classroom-layout-cross-group', ?, 'draft', ?, ?, ?) RETURNING id",
            (event["id"], ADMIN_ID, now, now),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO classroom_layout_rooms "
            "(layout_version_id, classroom_id, group_lesson_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (layout_id, first_rooms[0]["id"], first_group_lesson, now, now),
                (layout_id, first_rooms[1]["id"], first_group_lesson, now, now),
                (layout_id, room_id, group_lesson_id, now, now),
            ),
        )
        connection.execute(
            "UPDATE classroom_layout_versions SET state = 'confirmed', "
            "confirmed_by_user_id = ?, confirmed_at = ?, updated_at = ? "
            "WHERE id = ?",
            (ADMIN_ID, now, now, layout_id),
        )

    classroom_http.factory.run_write(seed_second_group)
    path = (
        "/staff/api/v1/in-person-events/classroom-layout-event/"
        "classroom-assignment-plan"
    )
    recalculated = await classroom_http.client.post(
        f"{path}/recalculate",
        json={"schemaVersion": 1},
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert recalculated.status == 200, await recalculated.text()
    plan = (await recalculated.json())["assignmentPlan"]["plan"]
    assignment_path = f"{path}/{plan['publicId']}/assignments"

    rejected = await classroom_http.client.put(
        assignment_path,
        json={
            "schemaVersion": 1,
            "assignments": [
                {
                    "enrollmentPublicId": "classroom-layout-enrollment",
                    "classroomPublicId": "classroom-layout-301",
                    "confirmGroupChange": False,
                }
            ],
        },
        headers=_headers(unsafe=True, if_match=recalculated.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert rejected.status == 422

    moved = await classroom_http.client.put(
        assignment_path,
        json={
            "schemaVersion": 1,
            "assignments": [
                {
                    "enrollmentPublicId": "classroom-layout-enrollment",
                    "classroomPublicId": "classroom-layout-301",
                    "confirmGroupChange": True,
                }
            ],
        },
        headers=_headers(unsafe=True, if_match=recalculated.headers["ETag"]),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert moved.status == 200, await moved.text()
    student = (await moved.json())["assignmentPlan"]["students"][0]
    assert (student["groupPublicId"], student["classroomName"], student["source"]) == (
        "classroom-layout-group-advanced",
        "301",
        "group-change",
    )

    def changed_rows(connection):
        enrollment = connection.execute(
            "SELECT active_group_id FROM course_enrollments "
            "WHERE public_id = 'classroom-layout-enrollment'"
        ).fetchone()["active_group_id"]
        access = connection.execute(
            "SELECT group_id FROM course_group_access WHERE valid_to IS NULL"
        ).fetchall()
        event = connection.execute(
            "SELECT previous_group_id, new_group_id, source "
            "FROM course_enrollment_events"
        ).fetchone()
        user_group = connection.execute(
            "SELECT group_id FROM users WHERE public_id = 'classroom-layout-student'"
        ).fetchone()["group_id"]
        legacy_event = connection.execute(
            "SELECT change_type, new_value FROM user_changes_log"
        ).fetchone()
        return enrollment, access, event, user_group, legacy_event

    enrollment, access, event, user_group, legacy_event = (
        classroom_http.factory.run_read(changed_rows)
    )
    assert enrollment == "layout-advanced"
    assert {row["group_id"] for row in access} == {
        "layout-beginner",
        "layout-advanced",
    }
    assert tuple(event.values()) == (
        "layout-beginner",
        "layout-advanced",
        "staff",
    )
    assert user_group == "layout-advanced"
    assert tuple(legacy_event.values()) == ("G", "layout-advanced")
