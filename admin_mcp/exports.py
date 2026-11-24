"""Short-lived account-bound downloads. Recheck lesson access on every download."""

import secrets
import time

from aiohttp import web

from admin_mcp import oauth, operations
from apps.pwa_api import content_routes
from apps.pwa_api.ai_review_routes import factory
from apps.pwa_api.middleware import authenticate_access_cookie
from models.pwa.auth import AuthAudience

routes = web.RouteTableDef()


async def save(api, lesson, revision, filename, mime, data):
    now = int(time.time())
    public_id = secrets.token_urlsafe(24)

    def write(c):
        c.execute("DELETE FROM admin_mcp_exports WHERE expires<=?", (now,))
        c.execute(
            "INSERT INTO admin_mcp_exports VALUES(?,?,?,?,?,?,?,?,?)",
            (
                public_id,
                api.session.principal.account_public_id,
                api.origin,
                lesson,
                revision,
                filename,
                mime,
                data,
                now + 600,
            ),
        )

    await api.factory.run_write_async(write)
    return {
        "exportId": public_id,
        "url": api.origin + oauth.BASE + "/exports/" + public_id,
        "filename": filename,
        "expiresAtUnix": now + 600,
    }


@routes.get(oauth.BASE + "/exports/{export_id}")
async def fetch(request):
    origin = oauth.validate_request_boundary(
        request, audience=AuthAudience.STAFF, expects_json=False
    ).external_origin
    if "Authorization" in request.headers:
        session = await oauth.delegated(request, origin)
    else:
        session = await authenticate_access_cookie(
            request, audience=AuthAudience.STAFF, required=True
        )
    row = await read(request, session, origin, request.match_info["export_id"])
    return web.Response(
        body=row["content"],
        content_type=row["mime"],
        headers={
            **oauth.PRIVACY,
            "Content-Disposition": 'attachment; filename="' + row["filename"] + '"',
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def read(request, session, origin, export_id):
    row = await factory(request).run_read_async(
        lambda c: c.execute(
            "SELECT * FROM admin_mcp_exports WHERE public_id=? AND resource=? AND account=? AND expires>?",
            (export_id, origin, session.principal.account_public_id, int(time.time())),
        ).fetchone()
    )
    if not row:
        raise web.HTTPNotFound()
    command = operations.StaffCommand(
        request, session, path={"group_lesson_id": row["lesson"]}
    )
    await content_routes._authorized_lesson_window_scope(command)
    return row
