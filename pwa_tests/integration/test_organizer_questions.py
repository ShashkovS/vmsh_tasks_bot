"""Organizer acceptance; vmshpwa/docs/organizer-questions.md."""

from pathlib import Path

from pwa_tests.integration import test_content_http_api as support

content_http = support.content_http


async def call(f, role="student", method="get", path="", payload=None, data=None):
    audience = "staff" if role in ("admin", "teacher") else role
    headers = support._headers(unsafe=method != "get")
    kwargs = {}
    if data is not None:
        headers["Content-Type"] = "image/webp"
        kwargs["data"] = data
    elif payload is not None:
        kwargs["json"] = payload
    r = await getattr(f.client, method)(
        f"/{audience}/api/v1/organizer-questions{path}",
        headers=headers,
        cookies=support._cookie(f, role),
        **kwargs,
    )
    return r, await r.json() if r.content_type == "application/json" else await r.read()


def message(key="first", text="Когда начинаются занятия?", child=None, photos=()):
    return dict(text=text, photoIds=list(photos), idempotencyKey=key, childId=child)


async def test_owner_admin_and_family_privacy(content_http):
    f = content_http
    for role in ("student", "family"):
        r, created = await call(f, role, "post", payload=message())
        assert r.status == 200, created
        tid = created["threadId"]
        r, same = await call(f, role, "post", payload=message())
        assert r.status == 200 and same["threadId"] == tid
        r, _ = await call(f, role, "post", payload=message(text="Другой текст"))
        assert r.status == 409
        r, _ = await call(
            f, "family" if role == "student" else "student", path=f"/{tid}"
        )
        assert r.status == 404
        r, _ = await call(f, "teacher", path=f"/{tid}")
        assert r.status == 403
        r, reply = await call(
            f,
            "admin",
            "post",
            f"/{tid}/entries",
            message(key=f"answer-{role}", text="В воскресенье"),
        )
        assert r.status == 200, reply
        r, inbox = await call(f, role)
        assert inbox["unreadCount"] == 1
        r, thread = await call(f, role, path=f"/{tid}")
        assert len(thread["entries"]) == 2
        assert thread["thread"]["state"] == "answered"
        r, result = await call(
            f,
            role,
            "post",
            f"/{tid}/read",
            dict(sequence=thread["entries"][-1]["sequence"]),
        )
        assert r.status == 200, result
        _, inbox = await call(f, role)
        assert inbox["unreadCount"] == 0
    r, _ = await call(f, "admin", "post", payload=message("admin-new"))
    assert r.status == 403
    events = f.factory.run_read(
        lambda c: list(
            c.execute(
                "SELECT route,read_at FROM notification_events WHERE dedupe_key LIKE 'organizer-%'"
            )
        )
    )
    assert {row["route"].split("/")[1] for row in events} == {"student", "family"}
    assert all(
        row["read_at"] is not None and row["read_at"].endswith("Z") for row in events
    )


async def test_optional_child_and_revoked_link(content_http):
    f = content_http
    r, data = await call(
        f, "family", "post", payload=message(child=f"u-{support.STUDENT_USER_ID}")
    )
    assert r.status == 200, data
    tid = data["threadId"]
    f.factory.run_write(
        lambda c: c.execute("UPDATE family_student_links SET revoked_at=updated_at")
    )
    r, data = await call(f, "family", path=f"/{tid}")
    assert (
        r.status == 200
        and data["thread"]["child"]["studentId"] == f"u-{support.STUDENT_USER_ID}"
    )
    r, _ = await call(
        f,
        "family",
        "post",
        payload=message("new-child", child=f"u-{support.STUDENT_USER_ID}"),
    )
    assert r.status == 403
    r, _ = await call(f, "family", "post", payload=message("no-child"))
    assert r.status == 200


async def test_photos_atomic_send_and_authorization(content_http):
    f = content_http
    image = Path("pwa_tests/fixtures/student-results-photo.webp").read_bytes()
    r, data = await call(f, "student", "post", "/photos", data=image)
    assert r.status == 200, data
    photo = data["photo"]["photoId"]
    r, _ = await call(f, "family", path=f"/photos/{photo}")
    assert r.status == 404
    r, _ = await call(f, "family", "post", payload=message(photos=[photo]))
    assert r.status == 403
    r, data = await call(f, "student", "post", payload=message(text="", photos=[photo]))
    assert r.status == 200, data
    for role in ("student", "admin"):
        r, data = await call(f, role, path=f"/photos/{photo}")
        assert r.status == 200 and data.startswith(b"synthetic-webp:")
    r, _ = await call(f, "teacher", path=f"/photos/{photo}")
    assert r.status == 403
    r, _ = await call(f, "student", "post", payload=message("reuse", photos=[photo]))
    assert r.status == 403
    r, _ = await call(f, "student", "post", "/photos", data=b"not image")
    assert r.status == 422
    r, _ = await call(f, "student", "post", payload=message("empty", text=""))
    assert r.status == 422
    r, _ = await call(
        f,
        "student",
        "post",
        payload=message("many", photos=[f"oqp-{n}" for n in range(11)]),
    )
    assert r.status == 422


async def test_pagination_and_reply_queue(content_http):
    f = content_http
    _, data = await call(f, "student", "post", payload=message())
    tid = data["threadId"]
    for i in range(52):
        r, data = await call(
            f,
            "student",
            "post",
            f"/{tid}/entries",
            message(f"entry-{i}", text=f"Уточнение {i}"),
        )
        assert r.status == 200, data
    _, page = await call(f, "student", path=f"/{tid}")
    assert len(page["entries"]) == 50 and page["nextCursor"]
    _, tail = await call(f, "student", path=f"/{tid}?cursor={page['nextCursor']}")
    assert len(tail["entries"]) == 3 and tail["nextCursor"] is None
    _, queue = await call(f, "admin", path="?state=awaiting_staff")
    assert len(queue["items"]) == 1 and queue["unreadCount"] == 1
    r, _ = await call(f, "student", path=f"/{tid}?cursor=-1")
    assert r.status == 422


async def test_no_enrollment_parent_peer_and_list_pagination(content_http):
    from dataclasses import replace
    from types import MappingProxyType
    from apps.pwa_api.auth_routes import COOKIE_POLICY
    from models.pwa.auth import AuthAudience

    f = content_http

    def seed(c):
        c.execute("UPDATE course_enrollments SET status='archived'")
        c.execute("""INSERT INTO auth_accounts(audience,username,username_normalized,
          provisioning_source,display_name,credential_kind,credential_hash,status,created_at,updated_at)
          SELECT audience,'other-parent','other-parent',provisioning_source,'Второй родитель',
          credential_kind,credential_hash,status,created_at,updated_at FROM auth_accounts
          WHERE username='content-family'""")
        c.execute("""INSERT INTO family_student_links(family_account_id,student_user_id,created_at,updated_at)
          SELECT a.id,l.student_user_id,l.created_at,l.updated_at FROM family_student_links l
          JOIN auth_accounts a ON a.username='other-parent'""")

    f.factory.run_write(seed)
    r, created = await call(f, "family", "post", payload=message())
    assert r.status == 200, created
    login = await f.client.post(
        "/family/api/v1/auth/login",
        json=dict(username="other-parent", password="family-password"),
        headers=support._headers(unsafe=True),
    )
    assert login.status == 200, await login.text()
    token = login.cookies[COOKIE_POLICY[AuthAudience.FAMILY].access_name].value
    f.client.session.cookie_jar.clear()
    other = replace(f, cookies=MappingProxyType({**f.cookies, "family": token}))
    r, _ = await call(other, "family", path=f"/{created['threadId']}")
    assert r.status == 404
    r, _ = await call(
        other,
        "family",
        "post",
        f"/{created['threadId']}/entries",
        message("peer-reply"),
    )
    assert r.status == 404
    for n in range(51):
        r, data = await call(f, "student", "post", payload=message(f"question-{n}"))
        assert r.status == 200, data
    r, first = await call(f)
    assert r.status == 200 and len(first["items"]) == 50 and first["nextCursor"]
    _, last = await call(f, path=f"?cursor={first['nextCursor']}")
    assert len(last["items"]) == 1 and last["nextCursor"] is None
    assert not {v["threadId"] for v in first["items"]} & {
        v["threadId"] for v in last["items"]
    }


async def test_missing_photo_and_size_limit(content_http):
    f = content_http
    source = Path("pwa_tests/fixtures/student-results-photo.webp").read_bytes()
    r, uploaded = await call(f, "student", "post", "/photos", data=source)
    assert r.status == 200, uploaded
    photo = uploaded["photo"]["photoId"]
    key = f.factory.run_read(
        lambda c: c.execute(
            "SELECT object_key FROM organizer_question_photos WHERE public_id=?",
            (photo,),
        ).fetchone()["object_key"]
    )
    f.asset_storage.objects[key] = b"damaged"
    r, _ = await call(f, "student", path=f"/photos/{photo}")
    assert r.status == 404
    r, _ = await call(
        f, "student", "post", "/photos", data=source + b"0" * (25 * 1024 * 1024)
    )
    assert r.status == 413


async def test_migration_preserves_populated_existing_tables(content_http, tmp_path):
    import sqlite3

    # Rehearse on a disposable copy of the populated auth/course fixture.
    target = sqlite3.connect(tmp_path / "migration.sqlite3")
    try:
        content_http.factory.run_read(lambda c: c.backup(target))
        target.executescript(
            Path("migrations/0088.pwa_organizer_questions.rollback.sql").read_text()
        )
        tables = [
            "users",
            "auth_accounts",
            "family_student_links",
            "course_enrollments",
            "support_threads",
            "support_entries",
        ]
        before = {
            table: target.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in tables
        }
        assert before["auth_accounts"] and before["course_enrollments"]
        target.executescript(
            Path("migrations/0088.pwa_organizer_questions.sql").read_text()
        )
        after = {
            table: target.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in tables
        }
        assert after == before
        assert target.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            target.execute("SELECT count(*) FROM organizer_questions").fetchone()[0]
            == 0
        )
    finally:
        target.close()
