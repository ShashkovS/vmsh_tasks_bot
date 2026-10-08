"""Admin profile selection and public bootstrap/manifest. See docs/branding.md."""

import json
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.branding import get_branding, update_branding
from db_methods.pwa.audit import insert_audit_event
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.branding import PROFILES, brand_manifest
from models.pwa.auth import AuthAudience

branding_routes = web.RouteTableDef()


def _factory(request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="branding_unavailable",
            message="Настройки оформления временно недоступны",
        )
    return state.factory


async def selected_branding(request):
    if "branding_selection" not in request:
        request["branding_selection"] = await _factory(request).run_read_async(get_branding)
    return request["branding_selection"]


def _payload(row):
    return {"profileId": row["profile_id"], "version": row["version"]}


@branding_routes.get("/{audience:student|family|staff}/api/v1/branding")
async def branding(request):
    return web.json_response(
        _payload(await selected_branding(request)),
        headers={"Cache-Control": "no-store"},
    )


@branding_routes.get("/{audience:student|family}/manifest.webmanifest")
@branding_routes.get("/{audience:student|family}/api/v1/branding/manifest.webmanifest")
async def manifest(request):
    row = await selected_branding(request)
    return web.json_response(
        brand_manifest(row["profile_id"], request.match_info["audience"]),
        content_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@branding_routes.put("/staff/api/v1/branding")
async def change_branding(request):
    principal = authenticated_session(request).principal
    if principal.audience is not AuthAudience.STAFF or not principal.is_global_admin:
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Изменять оформление может только администратор",
        )
    try:
        payload = await request.json()
        if (
            not isinstance(payload, dict)
            or set(payload) != {"profileId", "version"}
            or not isinstance(payload["profileId"], str)
            or payload["profileId"] not in PROFILES
            or type(payload["version"]) is not int
            or payload["version"] < 1
        ):
            raise ValueError
    except ValueError, TypeError:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Выберите доступный профиль оформления",
        ) from None
    profile = PROFILES[payload["profileId"]]

    def write(connection):
        before = get_branding(connection)
        if not update_branding(
            connection,
            profile_id=profile["id"],
            default_locale=profile["defaultLocale"],
            expected_version=payload["version"],
        ):
            return None
        after = get_branding(connection)
        insert_audit_event(
            connection,
            actor_user_id=principal.linked_user_id,
            actor_account_public_id=principal.account_public_id,
            audience="staff",
            action="branding.updated",
            object_type="branding",
            object_id="instance",
            request_id=request["request_id"],
            before_json=json.dumps(before),
            after_json=json.dumps(after),
            occurred_at=datetime.now(UTC).isoformat(),
        )
        return after

    row = await _factory(request).run_write_async(write)
    if row is None:
        raise PwaApiError(
            status=409,
            code="version_conflict",
            message="Оформление уже изменено. Обновите страницу.",
        )
    return web.json_response(_payload(row), headers={"Cache-Control": "no-store"})
