"""Portal-specific ChatGPT registration and PKCE consent. See docs/admin-mcp/oauth.md."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import parse_qsl, urlencode

from aiohttp import web
from multidict import MultiDict

from apps.pwa_api.oauth_consent import consent_page, return_page
from apps.pwa_api.ai_review_routes import factory
from apps.pwa_api.middleware import (
    auth_service,
    authenticate_access_cookie,
    validate_request_boundary,
)
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience

routes = web.RouteTableDef()
BASE = "/staff/api/admin/v1"
PATH = BASE + "/mcp"
SCOPE = "lessons.admin"
ISSUER_PATH = BASE + "/oauth"
METADATA = "/.well-known/oauth-protected-resource" + PATH
PRIVACY = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
VERIFIER = re.compile(r"[A-Za-z0-9._~-]{43,128}")


def boundary(request):
    # Non-browser OAuth token exchange has no Origin. Validate trusted Host/proxy;
    # the consent POST below independently enforces the browser Origin policy.
    probe = request.clone(method="GET")
    return validate_request_boundary(
        probe, audience=AuthAudience.STAFF, expects_json=False
    )


def client():
    return os.environ.get("VMSH_ADMIN_MCP_CLIENT_ID", "chatgpt-staff")


def callback():
    return os.environ.get(
        "VMSH_ADMIN_MCP_REDIRECT_URI",
        "https://chatgpt.com/connector_platform_oauth_redirect",
    )


def token_auth(data):
    if data.get("client_id") != client():
        return False
    secret = os.environ.get("VMSH_ADMIN_MCP_CLIENT_SECRET")
    if secret:
        provided = data.get("client_secret")
        return isinstance(provided, str) and hmac.compare_digest(
            secret.encode(), provided.encode()
        )
    return "client_secret" not in data


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def challenge(verifier):
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )


async def form(request):
    if request.content_type != "application/x-www-form-urlencoded":
        raise web.HTTPBadRequest(headers=PRIVACY)
    payload = bytearray()
    async for chunk in request.content.iter_chunked(4096):
        payload.extend(chunk)
        if len(payload) > 8192:
            raise web.HTTPRequestEntityTooLarge(max_size=8192, actual_size=len(payload))
    try:
        values = MultiDict(
            parse_qsl(
                payload.decode(),
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=16,
            )
        )
    except ValueError:
        raise web.HTTPBadRequest(headers=PRIVACY) from None
    if any(len(values.getall(k)) != 1 for k in values):
        raise web.HTTPBadRequest(headers=PRIVACY)
    return values


def bad(code="invalid_request"):
    return web.json_response({"error": code}, status=400, headers=PRIVACY)


@routes.get(METADATA)
async def resource_metadata(request):
    origin = boundary(request).external_origin
    return web.json_response(
        {
            "resource": origin + PATH,
            "authorization_servers": [origin + ISSUER_PATH],
            "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"],
        }
    )


@routes.post(ISSUER_PATH + "/register")
async def register(request):
    """RFC 7591: instances of the same public ChatGPT client share its registration."""
    boundary(request)
    if os.environ.get("VMSH_ADMIN_MCP_CLIENT_SECRET"):
        raise web.HTTPNotFound()
    if request.content_type != "application/json":
        return bad("invalid_client_metadata")
    # The application also accepts large lesson uploads. Bound this public route separately.
    body = bytearray()
    async for chunk in request.content.iter_chunked(4096):
        body.extend(chunk)
        if len(body) > 8192:
            raise web.HTTPRequestEntityTooLarge(max_size=8192, actual_size=len(body))
    try:
        metadata = json.loads(body)
    except (ValueError, RecursionError):
        return bad("invalid_client_metadata")
    if not isinstance(metadata, dict):
        return bad("invalid_client_metadata")
    if metadata.get("redirect_uris") != [callback()]:
        return bad("invalid_redirect_uri")
    if metadata.get("scope", SCOPE) != SCOPE:
        return bad("invalid_client_metadata")
    return web.json_response({
        "client_id": client(),
        "client_name": "ChatGPT",
        "redirect_uris": [callback()],
        "scope": SCOPE,
        "response_types": ["code"],
        "grant_types": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_method": "none",
    }, status=201, headers=PRIVACY)


@routes.get("/.well-known/oauth-authorization-server" + ISSUER_PATH)
async def authorization_metadata(request):
    issuer = boundary(request).external_origin + ISSUER_PATH
    return web.json_response(
        {
            "issuer": issuer,
            **({} if os.environ.get("VMSH_ADMIN_MCP_CLIENT_SECRET") else {
                "registration_endpoint": issuer + "/register"
            }),
            "authorization_endpoint": issuer + "/authorize",
            "token_endpoint": issuer + "/token",
            "revocation_endpoint": issuer + "/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": [SCOPE],
            "authorization_response_iss_parameter_supported": True,
            "token_endpoint_auth_methods_supported": [
                "client_secret_post"
                if os.environ.get("VMSH_ADMIN_MCP_CLIENT_SECRET")
                else "none"
            ],
        }
    )


@routes.get(ISSUER_PATH + "/authorize")
@routes.post(ISSUER_PATH + "/authorize")
async def authorize(request):
    checked = validate_request_boundary(
        request,
        audience=AuthAudience.STAFF,
        expects_json=False,
        require_browser_source=request.method == "POST",
    )
    origin = checked.external_origin
    q = request.query
    if (
        len(request.raw_path) > 2048
        or any(len(q.getall(k)) != 1 for k in q)
        or q.get("client_id") != client()
        or q.get("redirect_uri") != callback()
        or q.get("resource") != origin + PATH
        or q.get("scope", SCOPE) != SCOPE
        or q.get("response_type") != "code"
        or q.get("code_challenge_method") != "S256"
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", q.get("code_challenge", ""))
    ):
        return bad()
    session = await authenticate_access_cookie(
        request, audience=AuthAudience.STAFF, required=False
    )
    if session is None:
        raise web.HTTPFound(
            "/staff/login?"
            + urlencode({"returnTo": request.raw_path.removeprefix("/staff")}),
            headers=PRIVACY,
        )
    principal = session.principal
    if not principal.has_capability(Capability.CONTENT_MANAGE):
        raise web.HTTPForbidden()
    if request.method == "GET":
        return await consent_page(
            request, session.current.display_name or principal.account_public_id
        )
    reply = {"iss": origin + ISSUER_PATH}
    if "state" in q:
        reply["state"] = q["state"]
    if (await form(request)).get("decision") == "allow":
        code = secrets.token_urlsafe(32)
        await factory(request).run_write_async(
            lambda c: (
                c.execute(
                    """INSERT INTO admin_mcp_grants(account_id,account,session,credential_version,session_version,
            resource,client,redirect,challenge,code_hash,code_expires) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        session.current.session.account_id,
                        principal.account_public_id,
                        principal.session_public_id,
                        principal.credential_version,
                        principal.session_version,
                        origin + PATH,
                        client(),
                        callback(),
                        q["code_challenge"],
                        digest(code),
                        int(time.time()) + 120,
                    ),
                ).rowcount
            )
        )
        reply["code"] = code
    else:
        reply["error"] = "access_denied"
    destination = callback() + "?" + urlencode(reply)
    if "text/html" in request.headers.get("Accept", ""):
        return await return_page(request, destination)
    raise web.HTTPFound(destination, headers=PRIVACY)


@routes.post(ISSUER_PATH + "/token")
async def token(request):
    resource = boundary(request).external_origin + PATH
    data = await form(request)
    if (
        data.get("scope", SCOPE) != SCOPE
        or data.get("resource") != resource
        or not token_auth(data)
    ):
        return bad()
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    now = int(time.time())

    def exchange(c):
        if data.get("grant_type") == "authorization_code":
            verifier = data.get("code_verifier", "")
            if (
                not VERIFIER.fullmatch(verifier)
                or data.get("redirect_uri") != callback()
            ):
                return False
            row = c.execute(
                "SELECT * FROM admin_mcp_grants WHERE code_hash=? AND code_expires>?",
                (digest(data.get("code", "")), now),
            ).fetchone()
            if (
                not row
                or row["redirect"] != data["redirect_uri"]
                or not hmac.compare_digest(challenge(verifier), row["challenge"])
            ):
                return False
        elif data.get("grant_type") == "refresh_token":
            row = c.execute(
                "SELECT * FROM admin_mcp_grants WHERE refresh_hash=? AND refresh_expires>?",
                (digest(data.get("refresh_token", "")), now),
            ).fetchone()
        else:
            return False
        if (
            not row
            or row["revoked"]
            or row["resource"] != resource
            or row["client"] != client()
        ):
            return False
        c.execute(
            """UPDATE admin_mcp_grants SET code_hash=NULL,access_hash=?,access_expires=?,
                  refresh_hash=?,refresh_expires=? WHERE id=?""",
            (digest(access), now + 900, digest(refresh), now + 30 * 86400, row["id"]),
        )
        return dict(row)

    grant = await factory(request).run_write_async(exchange)
    session = (
        await auth_service(request).delegated_staff_session(grant) if grant else None
    )
    if not session or not session.principal.has_capability(Capability.CONTENT_MANAGE):
        return bad("invalid_grant")
    return web.json_response(
        {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": 900,
            "scope": SCOPE,
            "refresh_token": refresh,
        },
        headers=PRIVACY,
    )


@routes.post(ISSUER_PATH + "/revoke")
async def revoke(request):
    resource = boundary(request).external_origin + PATH
    data = await form(request)
    if not token_auth(data):
        return bad()
    value = digest(data.get("token", ""))
    await factory(request).run_write_async(
        lambda c: (
            c.execute(
                """UPDATE admin_mcp_grants SET revoked=1 WHERE client=? AND resource=?
        AND (access_hash=? OR refresh_hash=?)""",
                (client(), resource, value, value),
            ).rowcount
        )
    )
    return web.Response(headers=PRIVACY)


async def delegated(request, origin):
    scheme, _, secret = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and re.fullmatch(r"[A-Za-z0-9_-]{43}", secret):
        row = await factory(request).run_read_async(
            lambda c: c.execute(
                """SELECT * FROM admin_mcp_grants WHERE access_hash=? AND resource=? AND client=?
            AND access_expires>? AND revoked=0""",
                (digest(secret), origin + PATH, client(), int(time.time())),
            ).fetchone()
        )
        if row:
            session = await auth_service(request).delegated_staff_session(row)
            if session and session.principal.has_capability(Capability.CONTENT_MANAGE):
                return session
    raise web.HTTPUnauthorized(
        headers={
            **PRIVACY,
            "WWW-Authenticate": f'Bearer resource_metadata="{origin}{METADATA}", scope="{SCOPE}"',
        }
    )
