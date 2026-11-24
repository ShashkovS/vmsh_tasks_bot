"""Durable request receipts for expensive Staff commands. See docs/admin-mcp/reference.md."""

import asyncio
import hashlib
import json
import secrets
import time

from aiohttp import web

from admin_mcp.operations import OPERATIONS
from apps.pwa_api import content_routes as content
from apps.pwa_api.errors import PwaApiError

TASKS = web.AppKey("admin_mcp_workers", set)


async def lifecycle(app):
    app[TASKS] = set()
    yield
    for task in list(app[TASKS]):
        task.cancel()
    await asyncio.gather(*list(app[TASKS]), return_exceptions=True)


async def authorize(api, name, ids, body):
    if name not in OPERATIONS or OPERATIONS[name][1] == "GET":
        raise ValueError("unsupported_background_operation")
    if name == "create_lesson":
        from apps.pwa_api.admin_course_routes import _admin_user_id

        _admin_user_id(api.command())
    elif name == "generate_metadata":
        await api.operation(
            "metadata_grid", {**ids, "revisionId": body["revisionId"]}, {}, None
        )
    elif name == "recheck_problem":
        # The write checks checker.manage and the authoritative problem scope again.
        from apps.pwa_api.submission_routes import _repository, _staff_recheck_actor

        request = api.command(path=ids)
        _staff_recheck_actor(request)
        context = await _repository(request).get_test_attempt_recheck_preview(
            problem_public_id=ids["problem_public_id"]
        )
        _staff_recheck_actor(request, context)
    else:
        request = api.command(path=ids)
        if "revision_id" in ids:
            context = await content._repository(request).get_revision_context(
                ids["revision_id"]
            )
            content._staff_actor(request, context.scope)
        elif "publication_id" in ids:
            context = await content._repository(request).get_publication_context(
                ids["publication_id"]
            )
            content._staff_actor(request, context.scope)
        else:
            lesson = ids.get("group_lesson_id") or body.get("groupLessonId")
            await content._authorized_lesson_window_scope(
                api.command(path={"group_lesson_id": lesson})
            )


async def start(api, name, ids, body, etag, key):
    if not 1 <= len(key) <= 128:
        raise ValueError("invalid_request_key")
    await authorize(api, name, ids, body)
    args = json.dumps([name, ids, body, etag], ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(args.encode()).hexdigest()
    owner = api.session.principal.account_public_id
    job = secrets.token_hex(16)
    now = int(time.time())

    def reserve(c):
        prior = c.execute(
            "SELECT * FROM admin_mcp_jobs WHERE owner=? AND portal=? AND request_key=?",
            (owner, api.origin, key),
        ).fetchone()
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise ValueError("idempotency_conflict")
            return prior["job"]
        c.execute(
            "INSERT INTO admin_mcp_jobs VALUES(?,?,?,?,?,?,?,?,?,NULL)",
            (job, owner, api.origin, key, fingerprint, args, "running", now, now + 900),
        )
        return job

    reserved = await api.factory.run_write_async(reserve)
    if reserved == job:

        async def execute():
            try:
                async with asyncio.timeout(840):
                    from admin_mcp.oauth import delegated

                    api.session = await delegated(api.request, api.origin)
                    result = await api.operation(name, ids, body, etag)
                state = "completed"
            except PwaApiError as error:
                state, result = "failed", {"code": error.code, "details": error.details}
            except Exception, asyncio.CancelledError:
                state, result = (
                    "interrupted",
                    {
                        "next": "Read current revision and effective state before retrying."
                    },
                )
            await api.factory.run_write_async(
                lambda c: (
                    c.execute(
                        "UPDATE admin_mcp_jobs SET state=?,result=? WHERE job=?",
                        (state, json.dumps(result), job),
                    ).rowcount
                )
            )
            await api.audit(name, {"identifiers": ids}, state)

        task = asyncio.create_task(execute())
        api.request.app[TASKS].add(task)
        task.add_done_callback(api.request.app[TASKS].discard)
    return {"operationId": reserved}


async def status(api, job):
    row = await api.factory.run_read_async(
        lambda c: c.execute(
            "SELECT * FROM admin_mcp_jobs WHERE owner=? AND portal=? AND job=?",
            (api.session.principal.account_public_id, api.origin, job),
        ).fetchone()
    )
    if not row:
        raise ValueError("operation_unavailable")
    name, ids, body, _ = json.loads(row["args"])
    await authorize(api, name, ids, body)
    state = row["state"]
    if state == "running" and int(time.time()) > row["deadline"]:
        state = "interrupted"
    return {
        "operationId": job,
        "operation": name,
        "state": state,
        "result": json.loads(row["result"]) if row["result"] else None,
    }
