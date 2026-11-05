"""Real HTTP/SQLite proposals never mutate grading; ai-review-assistant.md."""

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import UTC, datetime, timedelta

import pytest

from pwa_tests.integration import test_review_queue_http_api as fixtures
from pwa_tests.integration.test_review_sheet_http import get, post, detail, payload
from models.pwa import ai_review as ai

review_http = fixtures.review_http
PREFIX = "/staff/api/ai-review/v1/tools/"


async def install_image(f):
    from apps.pwa_api.content_routes import PWA_CONTENT_OBJECT_STORAGE
    from apps.pwa_api.written_submission_routes import PWA_WRITTEN_ATTACHMENT_SERVICE

    data = Path("pwa_tests/fixtures/student-results-photo.webp").read_bytes()
    app = f.client.server.app
    storage = app[PWA_CONTENT_OBJECT_STORAGE]
    await storage.put("submission/review-http-asset-1.webp", data, "image/webp")
    app[PWA_WRITTEN_ATTACHMENT_SERVICE] = SimpleNamespace(storage=storage)
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE media_assets SET byte_size=?,sha256=? WHERE object_key='submission/review-http-asset-1.webp'",
            (len(data), hashlib.sha256(data).hexdigest()),
        )
    )
    return data


async def token(f, role="full"):
    response = await post(
        f, "/staff/api/v1/ai-review/tokens", {"name": "Test model"}, role
    )
    assert response.status == 200, await response.text()
    return await response.json()


async def call(f, secret, tool, value=None):
    return await f.client.post(
        PREFIX + tool,
        json=value or {},
        headers={
            "Host": fixtures.HOST,
            "Origin": fixtures.ORIGIN,
            "Authorization": "Bearer " + secret,
        },
    )


async def context(f, secret):
    response = await call(f, secret, "get_review_context", {"caseId": "st-1"})
    assert response.status == 200, await response.text()
    return await response.json()


def suggestion(value, key="first", **changes):
    return {
        "caseId": value["caseId"],
        "snapshot": value["snapshot"],
        "idempotencyKey": key,
        "comment": "Проверьте переход ко второй строке.",
        "verdict": 14,
        "analysis": "PRIVATE teacher analysis",
        "source": "External model",
        "model": "test/model",
        **changes,
    }


async def save(f, secret, value):
    result = await call(f, secret, "submit_ai_suggestion", value)
    assert result.status == 200, await result.text()
    return await result.json()


def counts(f):
    return f.factory.run_read(
        lambda c: {
            table: c.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            for table in (
                "results",
                "submission_reviews",
                "submission_entries",
                "written_tasks_queue",
                "notification_deliveries",
            )
        }
    )


async def test_full_path_multiple_proposals_idempotency_and_no_grading_side_effects(
    review_http,
):
    f = review_http
    receipt = await token(f)
    secret = receipt["secret"]
    stored_hash = f.factory.run_read(
        lambda c: c.execute("SELECT secret_hash FROM ai_review_tokens").fetchone()[
            "secret_hash"
        ]
    )
    assert (
        stored_hash == hashlib.sha256(secret.encode()).hexdigest()
        and secret not in stored_hash
    )
    before = counts(f)
    for name in (
        "list_courses",
        "list_groups",
        "list_lessons",
        "list_problems",
        "list_pending_reviews",
    ):
        response = await call(f, secret, name)
        assert response.status == 200, await response.text()
        assert (await response.json())["items"]
    value = await context(f, secret)
    first = await save(f, secret, suggestion(value))
    second = await save(
        f, secret, suggestion(value, "second", verdict=17, comment=None)
    )
    assert first["suggestionId"] != second["suggestionId"]
    assert await save(f, secret, suggestion(value)) == {**first, "replayed": True}
    conflict = await call(
        f, secret, "submit_ai_suggestion", suggestion(value, verdict=17)
    )
    assert conflict.status == 409
    response = await get(f, "/staff/api/v1/review/ai-suggestions?caseId=st-1")
    assert response.status == 200, await response.text()
    data = await response.json()
    assert len(data["items"]) == 2 and all(s["isCurrent"] for s in data["items"])
    assert data["evidenceKey"] and data["pending"]
    assert counts(f) == before
    assert not f.telegram_calls
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM written_tasks_queue WHERE claim_token IS NOT NULL"
            ).fetchone()["n"]
        )
        == 0
    )
    # Queue IDs and student/synonym case IDs are distinct in ordinary review.
    response = await get(
        f, f"/staff/api/v1/review/ai-suggestions?queueId={f.queue_public_ids[0]}"
    )
    assert (await response.json())["caseId"] == "st-1"


async def test_tokens_are_personal_revocable_and_follow_current_grants(review_http):
    f = review_http
    full = await token(f)
    partial = await token(f, "partial")
    assert (
        await call(f, partial["secret"], "get_review_context", {"caseId": "st-1"})
    ).status == 403
    assert (
        await get(f, "/staff/api/v1/review/ai-suggestions?caseId=st-1", "partial")
    ).status == 403
    # MCP tokens cannot impersonate a browser session or issue other tokens.
    denied = await f.client.post(
        "/staff/api/v1/ai-review/tokens",
        json={"name": "bypass"},
        headers={
            **fixtures._headers(unsafe=True),
            "Authorization": "Bearer " + full["secret"],
        },
    )
    assert denied.status == 401
    foreign = await f.client.delete(
        "/staff/api/v1/ai-review/tokens/" + full["tokenId"],
        headers=fixtures._headers(unsafe=True),
        cookies=fixtures._cookie(f, "partial"),
    )
    assert foreign.status == 404
    await context(f, full["secret"])
    # Removing a scope must take effect without waiting for the auth read cache.
    f.factory.run_write(
        lambda c: c.execute(
            "DELETE FROM staff_scopes WHERE staff_user_id=?",
            (fixtures.FULL_TEACHER_ID,),
        )
    )
    assert (
        await call(f, full["secret"], "get_review_context", {"caseId": "st-1"})
    ).status == 403
    revoked = await f.client.delete(
        "/staff/api/v1/ai-review/tokens/" + full["tokenId"],
        headers=fixtures._headers(unsafe=True),
        cookies=fixtures._cookie(f, "full"),
    )
    assert revoked.status == 200
    assert (await call(f, full["secret"], "list_courses")).status == 401


async def test_stale_context_completion_replays_and_private_projection(review_http):
    f = review_http
    secret = (await token(f))["secret"]
    old = await context(f, secret)
    await save(f, secret, suggestion(old))
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE submission_threads SET version=version+1 WHERE public_id='st-1'"
        )
    )
    stale = await call(f, secret, "submit_ai_suggestion", suggestion(old, "stale"))
    assert stale.status == 409
    stale_dialogue = await call(
        f,
        secret,
        "get_review_dialogue",
        {"caseId": "st-1", "snapshot": old["snapshot"]},
    )
    assert stale_dialogue.status == 409
    current = await context(f, secret)
    await save(f, secret, suggestion(current, "current"))
    listing = await get(f, "/staff/api/v1/review/ai-suggestions?caseId=st-1")
    assert [s["isCurrent"] for s in (await listing.json())["items"]] == [True, False]
    d = await detail(f)
    completed = await post(f, "/staff/api/v1/review/sheet/st-1/complete", payload(d))
    assert completed.status == 200, await completed.text()
    rejected = await call(
        f, secret, "submit_ai_suggestion", suggestion(current, "late")
    )
    assert rejected.status == 409
    # A lost successful reply is safe to retry even after human completion.
    assert (await save(f, secret, suggestion(current, "current")))["replayed"]
    history = await get(f, "/staff/api/v1/review/sheet/st-1/conversation")
    assert "PRIVATE teacher analysis" not in await history.text()
    for audience, cookie in (
        ("student", f.student_cookie),
        ("family", f.family_cookie),
    ):
        from helpers.pwa.auth_config import COOKIE_POLICY
        from models.pwa.auth import AuthAudience

        protected = await f.client.get(
            "/staff/api/v1/review/ai-suggestions?caseId=st-1",
            headers=fixtures._headers(),
            cookies={COOKIE_POLICY[AuthAudience(audience)].access_name: cookie},
        )
        assert protected.status == 401


async def test_token_expiry_blocking_and_credential_change(review_http):
    f = review_http
    receipt = await token(f)
    secret = receipt["secret"]

    def check(c):
        ai.authenticate(c, secret, now=datetime.now(UTC) + timedelta(days=91))

    with pytest.raises(ai.AssistantError, match="invalid_mcp_token"):
        f.factory.run_read(check)
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE auth_accounts SET credential_version=credential_version+1 WHERE linked_user_id=?",
            (fixtures.FULL_TEACHER_ID,),
        )
    )
    assert (await call(f, secret, "list_courses")).status == 401


async def test_actual_stdio_mcp_roundtrip_to_http_backend(review_http):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    import json

    f = review_http
    secret = (await token(f))["secret"]
    image_bytes = await install_image(f)
    from pwa_tests.integration.test_ai_review_curriculum_http import (
        add_lesson,
        add_material,
    )

    def prior_lesson(c):
        lesson = add_lesson(c, 40)
        material = add_material(c, lesson, "condition", published=True)
        c.execute(
            """INSERT INTO content_revision_assets(revision_id,asset_id,logical_name,role,ordinal,created_at)
            SELECT ?,id,'figure.webp','figure',0,? FROM media_assets ORDER BY id LIMIT 1""",
            (material["id"], fixtures._timestamp()),
        )

    f.factory.run_write(prior_lesson)
    # The test backend enforces its configured Host. A small test-only proxy
    # preserves that boundary while giving the subprocess a real loopback URL.
    from aiohttp import web, ClientSession as HttpSession

    async def forward(request):
        async with HttpSession() as client:
            async with client.post(
                str(f.client.make_url(request.path)),
                data=await request.read(),
                headers={
                    "Host": fixtures.HOST,
                    "Origin": fixtures.ORIGIN,
                    "Authorization": request.headers["Authorization"],
                    "Content-Type": "application/json",
                },
            ) as response:
                return web.Response(
                    body=await response.read(),
                    status=response.status,
                    content_type=response.content_type,
                )

    proxy = web.Application()
    proxy.router.add_post("/{path:.*}", forward)
    runner = web.AppRunner(proxy)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ai_review_mcp"],
            env={
                "VMSH_AI_REVIEW_URL": f"http://127.0.0.1:{port}",
                "VMSH_AI_REVIEW_TOKEN": secret,
            },
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 15
                curriculum = await session.call_tool(
                    "get_previous_lesson_materials", {"lesson_id": "gl-1", "count": 5}
                )
                assert not curriculum.is_error, curriculum
                previous = json.loads(
                    next(c.text for c in curriculum.content if c.type == "text")
                )
                assert previous["returnedCount"] == 1
                lesson = previous["lessons"][0]
                pixels = await session.call_tool(
                    "get_lesson_material_image",
                    {
                        "lesson_id": lesson["lessonId"],
                        "snapshot": lesson["snapshot"],
                        "image_id": lesson["materials"][0]["images"][0]["imageId"],
                    },
                )
                assert not pixels.is_error, pixels
                import base64

                assert (
                    base64.b64decode(
                        next(c.data for c in pixels.content if c.type == "image")
                    )
                    == image_bytes
                )
                batch = await session.call_tool(
                    "get_problem_submissions",
                    {"problem_id": "p-1", "status": "pending"},
                )
                assert not batch.is_error, batch
                exported = json.loads(
                    next(c.text for c in batch.content if c.type == "text")
                )
                assert exported["selectedSubmissionCount"] == 1
                comments = await session.call_tool(
                    "list_review_comments", {"problem_id": "p-1"}
                )
                assert not comments.is_error, comments
                result = await session.call_tool(
                    "get_review_context", {"case_id": "st-1"}
                )
                assert not result.is_error, result
                value = json.loads(
                    next(c.text for c in result.content if c.type == "text")
                )
                image_result = await session.call_tool(
                    "get_review_image",
                    {
                        "case_id": "st-1",
                        "snapshot": value["snapshot"],
                        "image_id": "attachment:sa-1",
                    },
                )
                assert not image_result.is_error, image_result
                import base64

                image = next(c for c in image_result.content if c.type == "image")
                assert base64.b64decode(image.data) == image_bytes
                result = await session.call_tool(
                    "submit_ai_suggestion",
                    {
                        "case_id": "st-1",
                        "snapshot": value["snapshot"],
                        "idempotency_key": "stdio",
                        "source": "Protocol test",
                        "comment": "Suggestion",
                    },
                )
                assert not result.is_error, result
    finally:
        await runner.cleanup()


async def test_dialogue_images_snapshot_boundary_and_no_arbitrary_media(review_http):
    f = review_http
    secret = (await token(f))["secret"]
    data = await install_image(f)
    value = await context(f, secret)
    response = await call(
        f,
        secret,
        "get_review_dialogue",
        {"caseId": "st-1", "snapshot": value["snapshot"]},
    )
    assert response.status == 200, await response.text()
    dialogue = await response.json()
    assert dialogue["items"][0]["authorKind"] == "student"
    assert dialogue["items"][0]["images"][0]["imageId"] == "attachment:sa-1"
    response = await call(
        f,
        secret,
        "get_review_image",
        {"caseId": "st-1", "snapshot": value["snapshot"], "imageId": "attachment:sa-1"},
    )
    assert response.status == 200 and response.content_type == "image/webp"
    assert await response.read() == data
    response = await call(
        f,
        secret,
        "get_review_image",
        {
            "caseId": "st-1",
            "snapshot": value["snapshot"],
            "imageId": "../../creds_prod/secret",
        },
    )
    assert response.status == 404
    # Bad origin and a browser cookie alone cannot call the token-only API.
    response = await f.client.post(
        PREFIX + "list_courses",
        json={},
        cookies=fixtures._cookie(f, "full"),
        headers=fixtures._headers(unsafe=True),
    )
    assert response.status == 401
    response = await f.client.post(
        PREFIX + "list_courses",
        json={},
        headers={
            "Host": fixtures.HOST,
            "Origin": "https://foreign.example",
            "Authorization": "Bearer " + secret,
        },
    )
    assert response.status == 403


async def test_reference_material_and_answer_changes_invalidate_context(review_http):
    f = review_http
    secret = (await token(f))["secret"]

    def seed(c):
        for row in c.execute("SELECT * FROM problem_revisions").fetchall():
            document = json.dumps(
                {
                    "problems": [
                        {
                            "ordinal": row["source_ordinal"],
                            "blocks": [
                                {"type": "paragraph", "text": "Reference condition"}
                            ],
                        }
                    ]
                }
            )
            c.execute(
                "INSERT INTO content_derivatives(revision_id,kind,renderer_version,content_text,sha256,provenance_json,created_at) VALUES(?,'web_ast','ai-test',?,?,'{}',?)",
                (
                    row["content_revision_id"],
                    document,
                    hashlib.sha256(document.encode()).hexdigest(),
                    fixtures._timestamp(),
                ),
            )
            c.execute(
                "UPDATE problem_revisions SET answer_config_json=? WHERE id=?",
                ('{"answer":"42"}', row["id"]),
            )

    f.factory.run_write(seed)
    old = await context(f, secret)
    assert old["problems"][0]["materials"]["condition"]["answer"] == {"answer": "42"}
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE problem_revisions SET answer_config_json=? WHERE id=1",
            ('{"answer":"43"}',),
        )
    )
    fresh = await context(f, secret)
    assert fresh["snapshot"] != old["snapshot"]
    rejected = await call(f, secret, "submit_ai_suggestion", suggestion(old))
    assert rejected.status == 409


async def test_validation_and_two_simultaneous_uploads(review_http):
    import asyncio

    f = review_http
    secret = (await token(f))["secret"]
    value = await context(f, secret)
    results = await asyncio.gather(
        save(f, secret, suggestion(value)), save(f, secret, suggestion(value))
    )
    assert {r["suggestionId"] for r in results} == {results[0]["suggestionId"]}
    assert {r["replayed"] for r in results} == {False, True}
    for changes in (
        {"verdict": 100},
        {"verdict": True},
        {"source": " "},
        {"comment": None, "analysis": None, "verdict": None},
        {"comment": "x" * 100_001},
    ):
        response = await call(
            f, secret, "submit_ai_suggestion", suggestion(value, "invalid", **changes)
        )
        assert response.status == 422, await response.text()
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE auth_accounts SET status='disabled' WHERE linked_user_id=?",
            (fixtures.FULL_TEACHER_ID,),
        )
    )
    assert (await call(f, secret, "list_courses")).status == 401


@pytest.mark.parametrize("mode", ["clone", "move"])
async def test_transfer_invalidates_proposal_without_changing_verdict(
    review_http, mode
):
    from pwa_tests.integration.test_review_entry_transfers import add_target

    f = review_http
    secret = (await token(f))["secret"]
    target = f.factory.run_write(add_target)
    old = await context(f, secret)
    await save(f, secret, suggestion(old))
    d = await detail(f)
    response = await post(
        f,
        "/staff/api/v1/review/sheet/st-1/transfer-preview",
        {
            "schemaVersion": 1,
            "entryId": "se-1",
            "snapshot": d["snapshot"],
        },
    )
    assert response.status == 200, await response.text()
    preview = await response.json()
    response = await post(
        f,
        "/staff/api/v1/review/sheet/st-1/transfer",
        {
            "schemaVersion": 1,
            "entryId": "se-1",
            "snapshot": d["snapshot"],
            "targetProblemId": target,
            "sourceVersion": preview["sourceVersion"],
            "entryVersion": preview["entryVersion"],
            "targetVersion": 0,
            "targetThreadId": None,
            "mode": mode,
            "idempotencyKey": "ai-transfer",
        },
    )
    assert response.status == 200, await response.text()
    rejected = await call(
        f, secret, "submit_ai_suggestion", suggestion(old, "after-transfer")
    )
    assert rejected.status == 409
    exported = await call(f, secret, "get_problem_submissions", {"problemId": "p-1"})
    assert exported.status == 200, await exported.text()
    states = (await exported.json())["submissionCounts"]
    assert states["superseded"] == (1 if mode == "move" else 0)
    assert states["pending"] == (0 if mode == "move" else 1)
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM submission_reviews"
            ).fetchone()["n"]
        )
        == 0
    )
