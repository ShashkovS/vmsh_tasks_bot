"""Question photos: atomic ownership, HTTP access and existing text compatibility."""

from pathlib import Path

from pwa_tests.integration import test_content_http_api as support

content_http = support.content_http


async def request(f, role, method, path, **kwargs):
    audience = "staff" if role in ("teacher", "admin") else role
    headers = support._headers(unsafe=method != "get")
    if "data" in kwargs:
        headers["Content-Type"] = "image/webp"
    return await getattr(f.client, method)(
        f"/{audience}/api/v1/questions{path}",
        cookies=support._cookie(f, role),
        headers=headers,
        **kwargs,
    )


async def test_question_photos_send_replay_and_private_read(content_http):
    f = content_http
    pid, _ = await support._prepare_published_test_problem(f, problem_type=2)
    image = Path("pwa_tests/fixtures/student-results-photo.webp").read_bytes()
    r = await request(f, "student", "post", "/photos", data=image)
    assert r.status == 200, await r.text()
    photo = (await r.json())["photoId"]
    r = await request(f, "admin", "get", f"/photos/{photo}")
    assert r.status == 403
    payload = dict(
        schemaVersion=1,
        kind="problem_question",
        groupLessonId=f.group_lesson_a,
        problemId=pid,
        text="Где ошибка?",
        photoIds=[photo],
        idempotencyKey="question-photo",
        clientCreatedAt="2026-09-13T12:00:00Z",
    )
    f.factory.run_write(
        lambda db: db.execute(
            "UPDATE support_photos SET uploader_user_id = ? WHERE public_id = ?",
            (support.TEACHER_USER_ID, photo),
        )
    )
    r = await request(f, "student", "post", "", json=payload)
    assert r.status == 403
    assert (
        f.factory.run_read(
            lambda db: db.execute("SELECT count(*) n FROM support_entries").fetchone()[
                "n"
            ]
        )
        == 0
    )
    f.factory.run_write(
        lambda db: db.execute(
            "UPDATE support_photos SET uploader_user_id = ? WHERE public_id = ?",
            (support.STUDENT_USER_ID, photo),
        )
    )
    r = await request(f, "student", "post", "", json=payload)
    assert r.status == 200, await r.text()
    thread = (await r.json())["thread"]
    assert thread["entries"][0]["photoIds"] == [photo]
    r = await request(f, "student", "post", "", json=payload)
    assert r.status == 200, await r.text()
    assert len((await r.json())["thread"]["entries"]) == 1
    for role in ("student", "admin", "teacher"):
        r = await request(f, role, "get", f"/photos/{photo}")
        assert r.status == 200, await r.text()
        assert r.content_type == "image/webp"
        assert "no-store" in r.headers["Cache-Control"]
    r = await request(f, "family", "get", f"/photos/{photo}")
    assert r.status in (401, 403, 404)
    # Cannot reuse a photo in another message or partially insert a bad batch.
    for ids in ([photo], ["sup-999999"]):
        r = await request(
            f,
            "student",
            "post",
            f"/{thread['threadId']}/entries",
            json={
                "schemaVersion": 1,
                "idempotencyKey": "different",
                "text": "Ещё вопрос",
                "photoIds": ids,
                "clientCreatedAt": "2026-09-13T12:01:00Z",
            },
        )
        assert r.status == 403, await r.text()
    r = await request(f, "student", "get", f"/{thread['threadId']}")
    assert len((await r.json())["thread"]["entries"]) == 1
    r = await request(f, "student", "post", "/photos", data=b"not a photo")
    assert r.status == 422
    r = await request(f, "teacher", "post", "/photos", data=image)
    assert r.status in (403, 404, 405)
