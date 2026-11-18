"""HTTP proof for the three owner-confirmed v1 provisioning batches."""

from __future__ import annotations

import sqlite3

from apps.pwa_api import account_batch_routes
from pwa_tests.integration.test_classroom_catalog_http_api import (
    ClassroomHttpFixture,
    _cookies,
    _headers,
)


pytest_plugins = ("pwa_tests.integration.test_classroom_catalog_http_api",)


def _apply_payload(
    source: dict[str, object], preview: dict[str, object]
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "rows": source["rows"],
        "resolvedLogins": [row["resolvedLogin"] for row in preview["rows"]],
        "previewHash": preview["previewHash"],
    }


async def test_admin_previews_and_applies_student_batch(
    classroom_http: ClassroomHttpFixture,
    monkeypatch,
) -> None:
    monkeypatch.setattr(account_batch_routes, "_suffixes", lambda: [17, 42])
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "surname": "Новый",
                "name": "Лев",
                "patronymic": "Ильич",
                "birthDate": "2013-04-05",
                "grade": 7,
                "login": "classroom-http-student",
                "password": "TelegramTokenBatchOne",
            },
            {
                "surname": "Вторая",
                "name": "Анна",
                "login": "new-student",
                "password": "TelegramTokenBatchTwo",
            },
        ],
    }
    path = "/staff/api/v1/imports/student-accounts/preview"

    teacher = await classroom_http.client.post(
        path,
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403

    preview_response = await classroom_http.client.post(
        path,
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = await preview_response.json()
    assert preview["counts"] == {"total": 2, "ready": 2, "invalid": 0}
    assert [row["resolvedLogin"] for row in preview["rows"]] == [
        "classroom-http-student-17",
        "new-student",
    ]
    assert "TelegramToken" not in str(preview)

    apply_response = await classroom_http.client.post(
        "/staff/api/v1/imports/student-accounts/apply",
        json=_apply_payload(source, preview),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert apply_response.status == 201, await apply_response.text()
    receipt = await apply_response.json()
    assert receipt["counts"] == {"total": 2, "created": 2, "skipped": 0}
    assert "TelegramToken" not in str(receipt)

    stored = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.username, account.credential_hash, "
            "account.provisioning_password_plaintext, user.surname, user.name, "
            "user.middlename, user.grade, user.birthday, user.online "
            "FROM auth_accounts AS account JOIN users AS user "
            "ON user.id = account.linked_user_id "
            "WHERE account.username_normalized = 'classroom-http-student-17'"
        ).fetchone()
    )
    assert stored["username"] == "classroom-http-student-17"
    assert stored["credential_hash"] != "telegramtokenbatchone"
    assert stored["provisioning_password_plaintext"] == "telegramtokenbatchone"
    assert tuple(stored[key] for key in ("surname", "name", "middlename")) == (
        "Новый",
        "Лев",
        "Ильич",
    )
    assert (stored["grade"], stored["birthday"], stored["online"]) == (
        7,
        "2013-04-05",
        1,
    )

    login = await classroom_http.client.post(
        "/student/api/v1/auth/login",
        json={
            "username": "CLASSROOM-HTTP-STUDENT-17",
            "telegramToken": "TelegramTokenBatchOne",
        },
        headers=_headers(unsafe=True),
    )
    assert login.status == 200, await login.text()


async def test_admin_previews_and_applies_family_batch(
    classroom_http: ClassroomHttpFixture,
) -> None:
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "name": "Семья Беловых",
                "login": "classroom-http-family-imported",
                "password": "qwerty-family-batch",
                "emails": "parent@example.org, second@example.org",
                "childLogins": ["classroom-http-student"],
            }
        ],
    }
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = await preview_response.json()
    assert preview["rows"][0]["resolvedLogin"] == "classroom-http-family-imported"
    assert preview["rows"][0]["loginAdjusted"] is False
    assert "qwerty-family-batch" not in str(preview)
    assert "parent@example.org" not in str(preview)

    response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/apply",
        json=_apply_payload(source, preview),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 201, await response.text()
    receipt = await response.json()
    assert receipt["counts"] == {"total": 1, "created": 1, "skipped": 0}
    assert "qwerty-family-batch" not in str(receipt)
    assert "parent@example.org" not in str(receipt)

    stored = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT account.id, account.credential_hash, "
            "account.provisioning_password_plaintext, count(link.student_user_id) "
            "AS children, group_concat(email.email, ',') AS emails "
            "FROM auth_accounts AS account "
            "JOIN family_student_links AS link ON link.family_account_id = account.id "
            "JOIN family_account_emails AS email ON email.family_account_id = account.id "
            "WHERE account.username_normalized = 'classroom-http-family-imported'"
        ).fetchone()
    )
    assert stored["credential_hash"] != "qwerty-family-batch"
    assert stored["provisioning_password_plaintext"] == "qwerty-family-batch"
    assert stored["children"] == 2  # one child × two email rows in this join
    assert stored["emails"] == "parent@example.org,second@example.org"

    retry_preview_response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    retry_preview = await retry_preview_response.json()
    assert retry_preview["counts"] == {"total": 1, "ready": 0, "invalid": 1}
    assert retry_preview["rows"][0]["code"] == "family_login_email_duplicate"
    retry_apply_response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/apply",
        json=_apply_payload(source, retry_preview),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert retry_apply_response.status == 200, await retry_apply_response.text()
    retry_receipt = await retry_apply_response.json()
    assert retry_receipt["counts"] == {"total": 1, "created": 0, "skipped": 1}
    assert retry_receipt["rows"][0]["code"] == "family_login_email_duplicate"

    email_retry = {
        "schemaVersion": 1,
        "rows": [
            {
                **source["rows"][0],
                "login": "classroom-http-family-other-login",
            }
        ],
    }
    email_retry_response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/preview",
        json=email_retry,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    email_retry_preview = await email_retry_response.json()
    assert email_retry_preview["rows"][0]["code"] == "family_email_duplicate"

    login_retry = {
        "schemaVersion": 1,
        "rows": [
            {
                **source["rows"][0],
                "emails": "unused-family-email@example.org",
            }
        ],
    }
    login_retry_response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/preview",
        json=login_retry,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    login_retry_preview = await login_retry_response.json()
    assert login_retry_preview["rows"][0]["code"] == "family_login_duplicate"

    login = await classroom_http.client.post(
        "/family/api/v1/auth/login",
        json={
            "username": "classroom-http-family-imported",
            "password": "qwerty-family-batch",
        },
        headers=_headers(unsafe=True),
    )
    assert login.status == 200, await login.text()


async def test_family_batch_treats_repeated_login_or_email_as_duplicates(
    classroom_http: ClassroomHttpFixture,
) -> None:
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "name": "Первая семья",
                "login": "within-batch-family",
                "password": "within-batch-password-one",
                "emails": "within-batch@example.org",
                "childLogins": ["classroom-http-student"],
            },
            {
                "name": "Повтор логина",
                "login": "WITHIN-BATCH-FAMILY",
                "password": "within-batch-password-two",
                "emails": "different-email@example.org",
                "childLogins": ["classroom-http-student"],
            },
            {
                "name": "Повтор почты",
                "login": "within-batch-family-other",
                "password": "within-batch-password-three",
                "emails": "WITHIN-BATCH@example.org",
                "childLogins": ["classroom-http-student"],
            },
        ],
    }

    response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 200, await response.text()
    preview = await response.json()
    assert preview["counts"] == {"total": 3, "ready": 1, "invalid": 2}
    assert [row["code"] for row in preview["rows"]] == [
        None,
        "family_login_duplicate",
        "family_email_duplicate",
    ]


async def test_family_batch_keeps_valid_rows_when_one_row_fails_during_write(
    classroom_http: ClassroomHttpFixture,
    monkeypatch,
) -> None:
    """A row-local constraint must not roll back unrelated parents."""

    original_insert = account_batch_routes.insert_family_emails

    def fail_one_email(connection, *, family_account_id, emails, now):
        if emails == ("broken-row@example.org",):
            raise sqlite3.IntegrityError(
                "UNIQUE constraint failed: "
                "family_account_emails.family_account_id, "
                "family_account_emails.email_normalized"
            )
        return original_insert(
            connection,
            family_account_id=family_account_id,
            emails=emails,
            now=now,
        )

    monkeypatch.setattr(account_batch_routes, "insert_family_emails", fail_one_email)
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "name": "Первый родитель",
                "login": "partial-family-one",
                "password": "partial-family-password-one",
                "emails": "first-row@example.org",
                "childLogins": ["classroom-http-student"],
            },
            {
                "name": "Проблемный родитель",
                "login": "partial-family-broken",
                "password": "partial-family-password-broken",
                "emails": "broken-row@example.org",
                "childLogins": ["classroom-http-student"],
            },
            {
                "name": "Последний родитель",
                "login": "partial-family-three",
                "password": "partial-family-password-three",
                "emails": "third-row@example.org",
                "childLogins": ["classroom-http-student"],
            },
        ],
    }
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    preview = await preview_response.json()
    assert preview["counts"] == {"total": 3, "ready": 3, "invalid": 0}

    response = await classroom_http.client.post(
        "/staff/api/v1/imports/family-accounts/apply",
        json=_apply_payload(source, preview),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 201, await response.text()
    receipt = await response.json()
    assert receipt["counts"] == {"total": 3, "created": 2, "skipped": 1}
    assert [row["state"] for row in receipt["rows"]] == [
        "created",
        "skipped",
        "created",
    ]
    assert receipt["rows"][1] == {
        "rowNumber": 2,
        "state": "skipped",
        "code": "invalid_emails",
    }

    stored = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT username_normalized FROM auth_accounts "
            "WHERE username_normalized LIKE 'partial-family-%' "
            "ORDER BY username_normalized"
        ).fetchall()
    )
    assert [row["username_normalized"] for row in stored] == [
        "partial-family-one",
        "partial-family-three",
    ]


async def test_apply_rejects_changed_preview(
    classroom_http: ClassroomHttpFixture,
) -> None:
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "surname": "Новый",
                "name": "Лев",
                "login": "new-student",
                "password": "token-one",
            }
        ],
    }
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/imports/student-accounts/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    preview = await preview_response.json()
    source["rows"][0]["name"] = "Другое имя"

    response = await classroom_http.client.post(
        "/staff/api/v1/imports/student-accounts/apply",
        json=_apply_payload(source, preview),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 409
    assert (await response.json())["error"]["code"] == "preview_changed"


async def test_admin_enrolls_students_and_uses_first_allowed_group_by_order(
    classroom_http: ClassroomHttpFixture,
) -> None:
    student_source = {
        "schemaVersion": 1,
        "rows": [
            {
                "surname": "Порядков",
                "name": "Лев",
                "login": "ordered-student",
                "password": "ordered-student-token",
            }
        ],
    }
    student_preview_response = await classroom_http.client.post(
        "/staff/api/v1/imports/student-accounts/preview",
        json=student_source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    student_preview = await student_preview_response.json()
    student_apply = await classroom_http.client.post(
        "/staff/api/v1/imports/student-accounts/apply",
        json=_apply_payload(student_source, student_preview),
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert student_apply.status == 201, await student_apply.text()

    def add_groups(connection):
        course_id = connection.execute(
            "SELECT id FROM courses WHERE code = 'math-layout'"
        ).fetchone()["id"]
        now = "2026-08-03T10:00:00Z"
        connection.executemany(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, course_id, "
            "status, color_key, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, 0, 0, 0, 1.0, ?, 'active', ?, ?, ?)",
            (
                (
                    "layout-continuing",
                    "п",
                    "Продолжающие",
                    2,
                    course_id,
                    "continuing",
                    now,
                    now,
                ),
                (
                    "layout-expert",
                    "э",
                    "Эксперты",
                    3,
                    course_id,
                    "expert",
                    now,
                    now,
                ),
            ),
        )

    classroom_http.factory.run_write(add_groups)
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "login": "ORDERED-STUDENT",
                "courseCode": "MATH-LAYOUT",
                "allowedGroupCodes": ["э", "п", "н"],
            }
        ],
    }
    teacher = await classroom_http.client.post(
        "/staff/api/v1/imports/course-enrollments/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "teacher"),
    )
    assert teacher.status == 403
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/imports/course-enrollments/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = await preview_response.json()
    assert preview["counts"] == {"total": 1, "ready": 1, "invalid": 0}
    assert preview["rows"] == [
        {
            "rowNumber": 1,
            "state": "ready",
            "login": "ordered-student",
            "courseCode": "math-layout",
            "activeGroupCode": "н",
            "allowedGroupCodes": ["н", "п", "э"],
            "code": None,
        }
    ]

    apply_response = await classroom_http.client.post(
        "/staff/api/v1/imports/course-enrollments/apply",
        json={
            "schemaVersion": 1,
            "rows": source["rows"],
            "previewHash": preview["previewHash"],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert apply_response.status == 201, await apply_response.text()
    receipt = await apply_response.json()
    assert receipt["counts"] == {"total": 1, "created": 1, "skipped": 0}
    assert receipt["rows"][0]["activeGroupCode"] == "н"

    stored = classroom_http.factory.run_read(
        lambda connection: connection.execute(
            "SELECT enrollment.active_group_id, enrollment.attendance_mode, "
            "student.group_id, student.allowed_groups, "
            "group_concat(access.group_id, ',') AS allowed, "
            "event.event_type, event.source "
            "FROM auth_accounts account "
            "JOIN users student ON student.id = account.linked_user_id "
            "JOIN course_enrollments enrollment "
            "ON enrollment.student_user_id = student.id "
            "JOIN course_group_access access ON access.enrollment_id = enrollment.id "
            "JOIN course_enrollment_events event "
            "ON event.enrollment_id = enrollment.id "
            "WHERE account.username_normalized = 'ordered-student'"
        ).fetchone()
    )
    assert stored == {
        "active_group_id": "layout-beginner",
        "attendance_mode": "online",
        "group_id": "layout-beginner",
        "allowed_groups": "layout-beginner;layout-continuing;layout-expert",
        "allowed": "layout-beginner,layout-continuing,layout-expert",
        "event_type": "created",
        "source": "import",
    }


async def test_course_enrollment_apply_rejects_group_order_changed_after_preview(
    classroom_http: ClassroomHttpFixture,
) -> None:
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "login": "classroom-http-student",
                "courseCode": "math-layout",
                "allowedGroupCodes": ["н"],
            }
        ],
    }

    # The seeded Student is already enrolled, so first create an independent
    # course whose group order can change between preview and apply.
    def add_course(connection):
        season_id = connection.execute("SELECT id FROM seasons").fetchone()["id"]
        now = "2026-08-03T10:00:00Z"
        course_id = connection.execute(
            "INSERT INTO courses "
            "(season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "(?, 'physics', 'Физика', 'physics', 'active', "
            "2, 'physics', ?, ?) RETURNING id",
            (season_id, now, now),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, course_id, "
            "status, color_key, created_at, updated_at) VALUES "
            "(?, ?, ?, ?, 1, 0, 0, 0, 1.0, ?, 'active', 'physics', ?, ?)",
            (
                (
                    "physics-first",
                    "ф1",
                    "Физика 1",
                    1,
                    course_id,
                    now,
                    now,
                ),
                (
                    "physics-second",
                    "ф2",
                    "Физика 2",
                    2,
                    course_id,
                    now,
                    now,
                ),
            ),
        )

    classroom_http.factory.run_write(add_course)
    source["rows"][0] = {
        "login": "classroom-http-student",
        "courseCode": "physics",
        "allowedGroupCodes": ["ф2", "ф1"],
    }
    preview_response = await classroom_http.client.post(
        "/staff/api/v1/imports/course-enrollments/preview",
        json=source,
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    preview = await preview_response.json()
    assert preview["rows"][0]["activeGroupCode"] == "ф1"

    def swap_group_order(connection):
        connection.execute(
            "UPDATE groups SET sort_order = 2 WHERE group_id = 'physics-first'"
        )
        connection.execute(
            "UPDATE groups SET sort_order = 1 WHERE group_id = 'physics-second'"
        )

    classroom_http.factory.run_write(swap_group_order)

    response = await classroom_http.client.post(
        "/staff/api/v1/imports/course-enrollments/apply",
        json={
            "schemaVersion": 1,
            "rows": source["rows"],
            "previewHash": preview["previewHash"],
        },
        headers=_headers(unsafe=True),
        cookies=_cookies(classroom_http, "admin"),
    )
    assert response.status == 409
    assert (await response.json())["error"]["code"] == "preview_changed"
