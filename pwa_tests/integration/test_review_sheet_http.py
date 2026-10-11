"""Staff sheet HTTP and audience boundaries; vmshpwa/docs/review-sheet.md."""

import pytest
import hashlib
import asyncio
from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
from apps.pwa_api.written_submission_routes import PWA_WRITTEN_ATTACHMENT_SERVICE
from db_methods.pwa.written_submissions import PwaWrittenSubmissionRepository
from helpers.pwa.app_keys import RUNTIME_CONFIG
from helpers.pwa.content.assets import ConfiguredContentAssetConverter
from helpers.pwa.written_attachments import WrittenAttachmentService
from pwa_tests.integration import test_review_queue_http_api as fixtures
from pwa_tests.integration.test_review_entry_transfers import add_target

review_http = fixtures.review_http


async def get(f, path, role="full"):
    return await f.client.get(
        path, cookies=fixtures._cookie(f, role), headers=fixtures._headers()
    )


async def post(f, path, payload, role="full"):
    return await f.client.post(
        path,
        json=payload,
        cookies=fixtures._cookie(f, role),
        headers=fixtures._headers(unsafe=True),
    )


async def detail(f):
    response = await get(f, "/staff/api/v1/review/sheet/st-1")
    assert response.status == 200, await response.text()
    return await response.json()


def payload(d, key="sheet-http", **changes):
    return {
        "schemaVersion": 1,
        "snapshot": d["snapshot"],
        "idempotencyKey": key,
        "verdict": 17,
        "comment": "Простыня: принято",
        "confirmWithoutComment": False,
        "annotations": [],
        "internalReactionId": None,
        **changes,
    }


@pytest.mark.asyncio
async def test_sheet_roles_scopes_validation_and_no_claim(review_http):
    f = review_http
    options = await get(f, "/staff/api/v1/review/sheet/options")
    assert options.status == 200 and (await options.json())["lessons"]
    collection = await get(f, "/staff/api/v1/review/sheet?problem=p-1&mode=pending")
    assert collection.status == 200, await collection.text()
    assert (await collection.json())["total"] == 1
    d = await detail(f)
    assert d["canReview"] and "claimToken" not in d["workspace"]
    assert (await get(f, "/staff/api/v1/review/sheet/st-1", "admin")).status == 200
    assert (await get(f, "/staff/api/v1/review/sheet/st-1", "partial")).status == 403
    assert (
        await get(f, "/staff/api/v1/review/sheet?lesson=gl-1&mode=invalid")
    ).status == 422
    assert (await get(f, "/staff/api/v1/review/sheet/st-999")).status == 404
    unauthorized = await f.client.get(
        "/staff/api/v1/review/sheet/options", headers=fixtures._headers()
    )
    assert unauthorized.status == 401
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM written_tasks_queue WHERE claim_token IS NOT NULL"
            ).fetchone()["n"]
        )
        == 0
    )


@pytest.mark.asyncio
async def test_sheet_conflict_refresh_resend_replay_and_student_projection(review_http):
    f = review_http
    d = await detail(f)
    stale = payload(
        d, "teacher-draft", verdict=14, comment="Мой сохранённый комментарий"
    )
    foreign = await post(
        f,
        "/staff/api/v1/review/sheet/st-1/complete",
        payload(d, "admin-first"),
        "admin",
    )
    assert foreign.status == 200, await foreign.text()
    first = (await foreign.json())["review"]["reviewId"]
    conflict = await post(f, "/staff/api/v1/review/sheet/st-1/complete", stale)
    assert (
        conflict.status == 409
        and (await conflict.json())["error"]["code"] == "review_sheet_changed"
    )
    latest = await detail(f)
    assert latest["currentReview"]["reviewId"] == first
    confirmed = {
        **stale,
        "snapshot": latest["snapshot"],
        "idempotencyKey": "teacher-confirmed",
    }
    result = await post(f, "/staff/api/v1/review/sheet/st-1/complete", confirmed)
    assert result.status == 200, await result.text()
    stored = (await result.json())["review"]
    assert stored["verdict"] == 14
    replay = await post(f, "/staff/api/v1/review/sheet/st-1/complete", confirmed)
    assert replay.status == 200 and (await replay.json())["review"]["replayed"]
    denied = await post(
        f, "/staff/api/v1/review/sheet/st-1/complete", confirmed, "partial"
    )
    assert denied.status == 403
    pending = await get(f, "/staff/api/v1/review/sheet?problem=p-1")
    all_works = await get(f, "/staff/api/v1/review/sheet?problem=p-1&mode=all")
    assert (await pending.json())["total"] == 0
    assert (await all_works.json())["total"] == 1
    conversation = await get(f, "/staff/api/v1/review/sheet/st-1/conversation")
    assert conversation.status == 200, await conversation.text()
    events = (await conversation.json())["events"]
    assert {e["reviewId"] for e in events if e["kind"] == "review"} == {
        first,
        stored["reviewId"],
    }
    assert any(e["text"] == "Мой сохранённый комментарий" for e in events)
    assert len(f.telegram_calls) == 2
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT verdict FROM results ORDER BY id DESC LIMIT 1"
            ).fetchone()["verdict"]
        )
        == 14
    )


@pytest.mark.asyncio
async def test_sheet_single_claim_annotations_media_and_old_api_are_preserved(
    review_http,
):
    f = review_http
    queue = f.queue_public_ids[0]
    app = f.client.server.app
    app[PWA_WRITTEN_ATTACHMENT_SERVICE] = WrittenAttachmentService(
        converter=ConfiguredContentAssetConverter(app[RUNTIME_CONFIG]),
        storage=app[PWA_CONTENT_OBJECT_STORAGE],
        repository=PwaWrittenSubmissionRepository(
            f.factory, clock=lambda: fixtures.NOW
        ),
    )
    body = b"sheet-http-source-webp"
    await app[PWA_CONTENT_OBJECT_STORAGE].put(
        "submission/sheet-http.webp", body, "image/webp"
    )

    def add_photo(c):
        asset = c.execute(
            """INSERT INTO media_assets
        (sha256,storage_namespace,object_key,media_type,byte_size,width,height,conversion_version,created_by_user_id,created_at)
        VALUES(?,'submission','submission/sheet-http.webp','image/webp',?,1,1,'test',?,'2026-10-04') RETURNING id""",
            (hashlib.sha256(body).hexdigest(), len(body), fixtures.STUDENT_ID),
        ).fetchone()["id"]
        return c.execute(
            """INSERT INTO submission_attachments(entry_id,asset_id,ordinal,upload_status,created_at)
        SELECT id,?,1,'stored','2026-10-04' FROM submission_entries WHERE public_id='se-1' RETURNING public_id""",
            (asset,),
        ).fetchone()["public_id"]

    photo = f.factory.run_write(add_photo)
    claim = await post(
        f, f"/staff/api/v1/review/items/{queue}/claim", {"schemaVersion": 1}, "admin"
    )
    assert claim.status == 200
    lease = (await claim.json())["lease"]
    d = await detail(f)
    value = payload(
        d, annotations=[fixtures._annotation_payload()], internalReactionId=100
    )
    result = await post(f, "/staff/api/v1/review/sheet/st-1/complete", value)
    assert result.status == 200, await result.text()
    assert (await result.json())["review"]["annotations"]
    image = await get(f, f"/staff/api/v1/review/sheet/st-1/attachments/{photo}")
    assert image.status == 200, await image.text()
    assert (
        await get(f, "/staff/api/v1/review/sheet/st-1/attachments/sa-1", "partial")
    ).status == 403
    assert (
        await get(f, "/staff/api/v1/review/sheet/st-1/attachments/sa-999")
    ).status == 404
    stale = await post(
        f,
        f"/staff/api/v1/review/items/{queue}/complete",
        fixtures._complete_payload(lease),
        "admin",
    )
    assert stale.status in (404, 409)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"schemaVersion": True},
        {"verdict": True},
        {"confirmWithoutComment": 1},
        {"snapshot": "wrong"},
        {"internalReactionId": True},
        {"comment": 5},
        {"claimToken": "forbidden"},
    ],
)
async def test_sheet_strict_request_validation(review_http, change):
    f = review_http
    response = await post(
        f,
        "/staff/api/v1/review/sheet/st-1/complete",
        payload(await detail(f), **change),
    )
    assert response.status == 422, await response.text()


@pytest.mark.asyncio
async def test_sheet_transfer_uses_source_cas_without_claim_and_replays(review_http):
    f = review_http
    target = f.factory.run_write(add_target)
    d = await detail(f)
    response = await post(
        f,
        "/staff/api/v1/review/sheet/st-1/transfer-preview",
        {"schemaVersion": 1, "entryId": "se-1", "snapshot": d["snapshot"]},
    )
    assert response.status == 200, await response.text()
    preview = await response.json()
    value = {
        "schemaVersion": 1,
        "entryId": "se-1",
        "snapshot": d["snapshot"],
        "targetProblemId": target,
        "sourceVersion": preview["sourceVersion"],
        "entryVersion": preview["entryVersion"],
        "targetVersion": 0,
        "targetThreadId": None,
        "mode": "clone",
        "idempotencyKey": "sheet-http-clone",
    }
    response = await post(f, "/staff/api/v1/review/sheet/st-1/transfer", value)
    assert response.status == 200, await response.text()
    first = await response.json()
    replay = await post(f, "/staff/api/v1/review/sheet/st-1/transfer", value)
    assert (
        replay.status == 200
        and (await replay.json())["targetEntryId"] == first["targetEntryId"]
    )
    stale = await post(
        f,
        "/staff/api/v1/review/sheet/st-1/transfer-preview",
        {"schemaVersion": 1, "entryId": "se-1", "snapshot": d["snapshot"]},
    )
    assert stale.status == 409
    denied = await post(f, "/staff/api/v1/review/sheet/st-1/transfer", value, "partial")
    assert denied.status == 403


@pytest.mark.asyncio
async def test_simultaneous_sheet_sends_have_exactly_one_winner(review_http):
    f = review_http
    opened = await detail(f)
    one, two = await asyncio.gather(
        post(
            f,
            "/staff/api/v1/review/sheet/st-1/complete",
            payload(opened, "parallel-teacher"),
        ),
        post(
            f,
            "/staff/api/v1/review/sheet/st-1/complete",
            payload(opened, "parallel-admin", verdict=14),
            "admin",
        ),
    )
    assert sorted([one.status, two.status]) == [200, 409]
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM submission_reviews"
            ).fetchone()["n"]
        )
        == 1
    )
