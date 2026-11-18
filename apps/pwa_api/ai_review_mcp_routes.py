"""Streamable HTTP in aiohttp; vmshpwa/docs/ai-review-assistant.md.

The official SDK owns MCP negotiation and dispatch. Each HTTP request has its
own stateless SDK transport and credential, so multiple workers need no sticky
sessions and a revoked token cannot retain access through an initialized session.
"""

import asyncio
import base64
import json

from aiohttp import web
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ImageContent

from ai_review_mcp.server import MAX_RESPONSE, create_server
from apps.pwa_api.ai_review_routes import (
    ERRORS,
    bearer_secret,
    execute_tool,
    factory,
    translate,
)
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import validate_request_boundary
from models.pwa import ai_review as ai
from models.pwa.auth import AuthAudience

routes = web.RouteTableDef()
MCP_PATH = "/staff/api/ai-review/v1/mcp"
MAX_REQUEST = 512 * 1024


class RequestClient:
    def __init__(self, request, secret):
        self.request = request
        self.secret = secret

    async def call(self, name, payload):
        try:
            response = await execute_tool(self.request, self.secret, name, payload)
        except PwaApiError as error:
            # SDK tool errors must not disclose DB diagnostics or credentials.
            raise ValueError(error.code) from None
        if name in {"get_review_image", "get_lesson_material_image"}:
            return CallToolResult(
                content=[
                    ImageContent(
                        type="image",
                        data=base64.b64encode(response.body).decode(),
                        mimeType=response.content_type,
                    )
                ]
            )
        return json.loads(response.body)


@routes.route("*", MCP_PATH)
async def remote_mcp(request):
    # Token-only native clients may omit Origin. Validate the exact configured
    # target/proxy first; browser-sourced requests still use the full Origin
    # policy. No cookies can authenticate this endpoint, and no CORS is enabled.
    boundary = validate_request_boundary(
        request.clone(method="GET"), audience=AuthAudience.STAFF, expects_json=False
    )
    if any(name in request.headers for name in ("Origin", "Referer", "Sec-Fetch-Site")):
        validate_request_boundary(
            request,
            audience=AuthAudience.STAFF,
            expects_json=False,
            require_browser_source=True,
        )
    secret = bearer_secret(request)
    try:
        await factory(request).run_read_async(lambda c: ai.authenticate(c, secret))
    except ERRORS as error:
        raise translate(error) from error

    data = bytearray()
    async for chunk in request.content.iter_chunked(64 * 1024):
        data.extend(chunk)
        if len(data) > MAX_REQUEST:
            raise web.HTTPRequestEntityTooLarge(
                max_size=MAX_REQUEST, actual_size=len(data)
            )
    server = create_server(RequestClient(request, secret))
    server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        max_request_body_size=MAX_REQUEST,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[request.host], allowed_origins=[boundary.external_origin]
        ),
    )
    # A bounded JSON-only ASGI bridge, not another listening server. SDK lifespan
    # enter/exit stays in this request task, including cancellation/disconnect.
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": f"{request.version.major}.{request.version.minor}",
        "method": request.method,
        "scheme": request.scheme,
        "path": MCP_PATH,
        "raw_path": MCP_PATH.encode(),
        "query_string": request.query_string.encode(),
        "root_path": "",
        "headers": list(request.raw_headers),
        "server": (request.url.host, request.url.port),
        "client": None,
    }
    # ASGI requires lowercase header names; aiohttp preserves the wire casing.
    scope["headers"] = [(key.lower(), value) for key, value in request.raw_headers]
    disconnected = asyncio.Event()
    received = False
    status, headers, output = 500, [], bytearray()

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": bytes(data), "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status, headers
        if message["type"] == "http.response.start":
            status, headers = message["status"], message.get("headers", [])
        elif message["type"] == "http.response.body":
            output.extend(message.get("body", b""))
            if len(output) > MAX_RESPONSE:
                raise ValueError("assistant_response_too_large")
            if not message.get("more_body", False):
                disconnected.set()

    async with server.session_manager.run():
        await server.session_manager.asgi_app(scope, receive, send)
    return web.Response(
        status=status,
        body=bytes(output),
        headers={
            **{k.decode(): v.decode() for k, v in headers},
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
