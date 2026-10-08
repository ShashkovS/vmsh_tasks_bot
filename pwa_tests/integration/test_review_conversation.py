"""Full Teacher/Admin dialogue regression; vmshpwa/docs/review-history.md."""

import hashlib

from apps.pwa_api.student_results_routes import LEGACY_SOLUTIONS_ROOT
from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
from apps.pwa_api.written_submission_routes import PWA_WRITTEN_ATTACHMENT_SERVICE
from db_methods.pwa.written_submissions import PwaWrittenSubmissionRepository
from helpers.pwa.app_keys import RUNTIME_CONFIG
from helpers.pwa.content.assets import ConfiguredContentAssetConverter
from helpers.pwa.written_attachments import WrittenAttachmentService
from pwa_tests.integration import test_review_queue_http_api as support

review_http = support.review_http


async def complete(f):
    queue = f.queue_public_ids[0]
    response = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/claim",
        json={"schemaVersion": 1},
        cookies=support._cookie(f, "full"),
        headers=support._headers(unsafe=True),
    )
    lease = (await response.json())["lease"]
    payload = support._complete_payload(lease)
    payload["annotations"] = [support._annotation_payload()]
    payload["internalReactionId"] = 100
    response = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/complete",
        json=payload,
        cookies=support._cookie(f, "full"),
        headers=support._headers(unsafe=True),
    )
    assert response.status == 200, await response.text()
    return (await response.json())["review"]["reviewId"]


async def get(f, path, role="full"):
    response = await f.client.get(
        path, cookies=support._cookie(f, role), headers=support._headers()
    )
    return response, await response.json()


async def test_full_dialogue_legacy_files_dedup_paging_and_late_answers(
    review_http, tmp_path
):
    f = review_http
    review = await complete(f)
    root = tmp_path / "solutions"
    root.mkdir()
    (root / "secret-student-token.txt").write_text(
        "Решение из старого текстового файла", encoding="utf-8"
    )
    (root / "photo.png").write_bytes(b"archived-photo")
    (tmp_path / "outside.png").write_bytes(b"private")
    (root / "escape.png").symlink_to(tmp_path / "outside.png")
    f.client.server.app[LEGACY_SOLUTIONS_ROOT] = root

    def seed(c):
        threads = c.execute("SELECT * FROM submission_threads ORDER BY id").fetchall()
        ids = {}
        for n in range(55):
            ids[n] = str(
                c.execute(
                    "INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text,attach_path) VALUES(?,?,?,?,?) RETURNING id",
                    (
                        support.STUDENT_ID,
                        threads[n % 2]["problem_id"],
                        f"2026-10-05 12:{n:02}:00",
                        f"Поздний ответ {n}",
                        {
                            0: "solutions/secret-student-token.txt",
                            1: "photo.png",
                            2: "missing.png",
                            3: "escape.png",
                        }.get(n),
                    ),
                ).fetchone()["id"]
            )
        first = c.execute(
            "SELECT problem_revision_id FROM submission_entries WHERE thread_id=? LIMIT 1",
            (threads[0]["id"],),
        ).fetchone()
        c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at,legacy_discussion_id) VALUES(?,?,'student',?,'telegram','text','submitted','Поздний ответ 4','2026-10-05 12:04:00',?)",
            (
                threads[0]["id"],
                first["problem_revision_id"],
                support.STUDENT_ID,
                ids[4],
            ),
        )
        c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at) VALUES(?,?,'student',?,'pwa','text','draft','СЕКРЕТНЫЙ ЧЕРНОВИК','2026-10-05 12:05:00')",
            (threads[0]["id"], first["problem_revision_id"], support.STUDENT_ID),
        )
        return ids

    ids = f.factory.run_write(seed)
    path = f"/staff/api/v1/review/history/{review}/conversation"
    response, first = await get(f, path)
    assert response.status == 200, first
    assert len(first["events"]) == 50 and first["total"] == 58
    response, last = await get(f, path + "?cursor=" + first["nextCursor"])
    assert response.status == 200 and last["nextCursor"] is None
    events = first["events"] + last["events"]
    assert len({e["id"] for e in events}) == 58
    assert sum(e["text"] == "Поздний ответ 4" for e in events) == 1
    assert events[-1]["text"] == "Поздний ответ 54"
    assert {e["problemNumber"] for e in events} == {"41a.1", "41b.2"}
    assert all(not e["internal"] for e in events)
    assert all(
        e["kind"] not in ("reaction", "student_reaction", "legacy_reaction")
        for e in events
    )
    assert "СЕКРЕТНЫЙ ЧЕРНОВИК" not in str(events)
    assert "secret-student-token" not in str(events)
    archived = next(e for e in events if e["id"] == "discussion:" + ids[0])
    assert "Решение из старого текстового файла" in archived["text"]
    photo = next(e for e in events if e["id"] == "discussion:" + ids[1])["attachments"][
        0
    ]
    response = await f.client.get(
        photo["url"], cookies=support._cookie(f, "full"), headers=support._headers()
    )
    assert response.status == 200 and await response.read() == b"archived-photo"
    for n in (2, 3):
        attachment = next(e for e in events if e["id"] == "discussion:" + ids[n])[
            "attachments"
        ][0]
        assert attachment["available"] is False
        response, _ = await get(f, attachment["url"])
        assert response.status == 404
    response, admin = await get(f, path, "admin")
    assert response.status == 200 and admin["events"] == first["events"]
    response, detail = await get(f, f"/staff/api/v1/review/history?review={review}")
    assert response.status == 200
    assert {e["entryId"] for e in detail["detail"]["entries"]} == set(
        support.ENTRY_PUBLIC_IDS
    )
    response, _ = await get(f, path + "?cursor=discussion:999999")
    assert response.status == 404


async def test_conversation_media_and_ownership_are_review_scoped(
    review_http, tmp_path
):
    f = review_http
    review = await complete(f)
    body = b"review-http-source-webp"
    app = f.client.server.app
    app[PWA_WRITTEN_ATTACHMENT_SERVICE] = WrittenAttachmentService(
        converter=ConfiguredContentAssetConverter(app[RUNTIME_CONFIG]),
        storage=app[PWA_CONTENT_OBJECT_STORAGE],
        repository=PwaWrittenSubmissionRepository(f.factory, clock=lambda: support.NOW),
    )
    # The shared fixture deliberately contains a corrupt size/hash for renderer tests.
    # Seed valid immutable media independently for this HTTP proof.
    await f.client.server.app[PWA_CONTENT_OBJECT_STORAGE].put(
        "submission/conversation.webp", body, "image/webp"
    )
    root = tmp_path / "solutions"
    root.mkdir()
    (root / "private.png").write_bytes(b"private")
    f.client.server.app[LEGACY_SOLUTIONS_ROOT] = root

    def seed(c):
        source = c.execute(
            "SELECT * FROM submission_entries WHERE public_id='se-1'"
        ).fetchone()
        entry_id = c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at) VALUES(?,?,'student',?,'pwa','submission','submitted','Поздняя фотография','2026-10-05') RETURNING id",
            (source["thread_id"], source["problem_revision_id"], support.STUDENT_ID),
        ).fetchone()["id"]
        asset = c.execute(
            "INSERT INTO media_assets(sha256,storage_namespace,object_key,media_type,byte_size,width,height,conversion_version,created_by_user_id,created_at) VALUES(?,'submission','submission/conversation.webp','image/webp',?,1,1,'test',?,'2026-10-05') RETURNING id",
            (hashlib.sha256(body).hexdigest(), len(body), support.STUDENT_ID),
        ).fetchone()["id"]
        attachment = c.execute(
            "INSERT INTO submission_attachments(entry_id,asset_id,ordinal,upload_status,created_at) VALUES(?,?,1,'stored','2026-10-05') RETURNING public_id",
            (entry_id, asset),
        ).fetchone()["public_id"]
        c.execute(
            "INSERT INTO users(id,type,name,surname) VALUES(999001,1,'Чужой','Ученик')"
        )
        foreign = c.execute(
            "INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text,attach_path) VALUES(999001,(SELECT problem_id FROM submission_threads LIMIT 1),'2026-10-05','Чужой ответ','private.png') RETURNING id",
        ).fetchone()["id"]
        return attachment, foreign

    attachment, foreign = f.factory.run_write(seed)
    base = f"/staff/api/v1/review/history/{review}"
    response = await f.client.get(
        base + "/attachments/" + attachment,
        cookies=support._cookie(f, "full"),
        headers=support._headers(),
    )
    assert response.status == 200 and await response.read() == body
    for path in (
        "/conversation",
        "/attachments/" + attachment,
        f"/legacy-attachments/{foreign}",
    ):
        response, _ = await get(f, base + path, "partial")
        assert response.status == 404
    response, _ = await get(f, base + f"/legacy-attachments/{foreign}")
    assert response.status == 404
    response, _ = await get(f, base + "/attachments/sa-999999")
    assert response.status == 404

    def revoke(c):
        c.execute(
            "UPDATE staff_scopes SET group_id='review-http-a' WHERE staff_user_id=?",
            (support.FULL_TEACHER_ID,),
        )

    f.factory.run_write(revoke)
    for path in ("/conversation", "/attachments/" + attachment):
        response, _ = await get(f, base + path)
        assert response.status == 404
    response, _ = await get(f, base + "/conversation", "admin")
    assert response.status == 200
