"""HTTP proof for the two owner-confirmed v1 provisioning batches."""

from __future__ import annotations

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
    monkeypatch,
) -> None:
    monkeypatch.setattr(account_batch_routes, "_suffixes", lambda: [17, 42])
    source = {
        "schemaVersion": 1,
        "rows": [
            {
                "name": "Семья Беловых",
                "login": "classroom-http-family",
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
    assert preview["rows"][0]["resolvedLogin"] == "classroom-http-family-17"
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
            "WHERE account.username_normalized = 'classroom-http-family-17'"
        ).fetchone()
    )
    assert stored["credential_hash"] != "qwerty-family-batch"
    assert stored["provisioning_password_plaintext"] == "qwerty-family-batch"
    assert stored["children"] == 2  # one child × two email rows in this join
    assert stored["emails"] == "parent@example.org,second@example.org"

    login = await classroom_http.client.post(
        "/family/api/v1/auth/login",
        json={
            "username": "classroom-http-family-17",
            "password": "qwerty-family-batch",
        },
        headers=_headers(unsafe=True),
    )
    assert login.status == 200, await login.text()


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
