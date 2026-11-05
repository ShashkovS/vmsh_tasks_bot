"""Real Streamable HTTP client without a repository-side launcher; ai-review-assistant.md."""

import asyncio
import base64
import json
from contextlib import asynccontextmanager

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from pwa_tests.integration.test_ai_review_http import (
    counts,
    install_image,
    token,
)
from pwa_tests.integration import test_review_queue_http_api as fixtures

review_http = fixtures.review_http

PATH = "/staff/api/ai-review/v1/mcp"


@asynccontextmanager
async def connect(f, secret):
    async with httpx2.AsyncClient(
        headers={
            "Host": fixtures.HOST,
            "Authorization": "Bearer " + secret,
        },
        timeout=20,
    ) as http:
        async with streamable_http_client(
            str(f.client.make_url(PATH)), http_client=http
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


def value(result):
    assert not result.is_error, result
    return json.loads(next(c.text for c in result.content if c.type == "text"))


async def test_remote_sdk_roundtrip_images_proposals_and_no_grading(review_http):
    f = review_http
    secret = (await token(f))["secret"]
    pixels = await install_image(f)
    before = counts(f)
    async with connect(f, secret) as session:
        tools = await session.list_tools()
        assert len(tools.tools) == 15
        assert value(await session.call_tool("list_courses", {}))["items"]
        batch = value(
            await session.call_tool(
                "get_problem_submissions", {"problem_id": "p-1", "status": "pending"}
            )
        )
        assert batch["selectedSubmissionCount"] == 1
        assert "items" in value(
            await session.call_tool("list_review_comments", {"problem_id": "p-1"})
        )
        previous = value(
            await session.call_tool(
                "get_previous_lesson_materials", {"lesson_id": "gl-1", "count": 5}
            )
        )
        assert "lessons" in previous
        context = value(
            await session.call_tool("get_review_context", {"case_id": "st-1"})
        )
        dialogue = value(
            await session.call_tool(
                "get_review_dialogue",
                {"case_id": "st-1", "snapshot": context["snapshot"]},
            )
        )
        assert dialogue["items"]
        # Same actual image path as the existing stdio transport.
        image_id = "attachment:sa-1"
        image = await session.call_tool(
            "get_review_image",
            {"case_id": "st-1", "snapshot": context["snapshot"], "image_id": image_id},
        )
        assert not image.is_error, image
        assert (
            base64.b64decode(next(c.data for c in image.content if c.type == "image"))
            == pixels
        )
        args = {
            "case_id": "st-1",
            "snapshot": context["snapshot"],
            "idempotency_key": "remote-first",
            "source": "remote-test",
            "comment": "Черновик",
            "verdict": 14,
        }
        receipt = value(await session.call_tool("submit_ai_suggestion", args))
        assert receipt["suggestionId"]
        assert value(await session.call_tool("submit_ai_suggestion", args))["replayed"]
        assert counts(f) == before
        f.factory.run_write(
            lambda c: c.execute(
                "DELETE FROM staff_scopes WHERE staff_user_id=?",
                (fixtures.FULL_TEACHER_ID,),
            )
        )
        denied = await session.call_tool("get_review_context", {"case_id": "st-1"})
        assert denied.is_error


async def rpc(f, secret=None, *, headers=None, cookies=None, data=None):
    request_headers = {
        "Host": fixtures.HOST,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if secret is not None:
        request_headers["Authorization"] = "Bearer " + secret
    request_headers.update(headers or {})
    return await f.client.post(
        PATH,
        headers=request_headers,
        cookies=cookies,
        data=data
        or json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        ),
    )


async def test_remote_auth_boundary_revoke_and_bounded_body(review_http):
    f = review_http
    receipt = await token(f)
    secret = receipt["secret"]
    for kwargs in (
        {},
        {"secret": "air_" + "x" * 43},
        {"cookies": fixtures._cookie(f, "full")},
    ):
        assert (await rpc(f, **kwargs)).status == 401
    for headers in (
        {"Origin": "https://attacker.example"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Host": "attacker.example"},
    ):
        assert (await rpc(f, secret, headers=headers)).status == 403
    assert (await rpc(f, secret)).status == 200
    assert (await rpc(f, secret, headers={"Origin": fixtures.ORIGIN})).status == 200
    assert (await rpc(f, secret, data="x" * (513 * 1024))).status == 413
    malformed = await rpc(f, secret, data="{oops")
    assert malformed.status == 400
    duplicate = await f.client.post(
        PATH,
        data="{}",
        headers=[
            ("Host", fixtures.HOST),
            ("Authorization", "Bearer " + secret),
            ("Authorization", "Bearer " + secret),
        ],
    )
    assert duplicate.status == 401
    f.factory.run_write(
        lambda c: c.execute("UPDATE ai_review_tokens SET revoked_at=created_at")
    )
    assert (await rpc(f, secret)).status == 401


async def test_remote_concurrent_credentials_do_not_share_scope(review_http):
    f = review_http
    full = (await token(f))["secret"]
    partial = (await token(f, "partial"))["secret"]

    async def read(secret):
        async with connect(f, secret) as session:
            return await session.call_tool("get_review_context", {"case_id": "st-1"})

    full_result, partial_result = await asyncio.gather(read(full), read(partial))
    assert not full_result.is_error
    assert partial_result.is_error
