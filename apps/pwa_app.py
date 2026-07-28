# -*- coding: utf-8 -*-
import asyncio
import json
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from aiohttp import WSCloseCode, WSMsgType, web

from apps.pwa_api.auth_routes import auth_routes
from apps.pwa_api.auth_service import PwaAuthService
from apps.pwa_api.content_routes import (
    PWA_CONTENT_ASSET_SERVICE,
    PWA_CONTENT_INVALIDATOR,
    PWA_CONTENT_OBJECT_STORAGE,
    PWA_CONTENT_REPOSITORY,
    content_routes,
)
from apps.pwa_api.course_routes import course_routes
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import (
    PWA_AUTH_STATE,
    PwaAuthState,
    authenticate_access_cookie,
    pwa_auth_request_security_middleware,
    pwa_authentication_middleware,
    validate_request_boundary,
)
from apps.pwa_api.realtime_control import (
    NATS_PWA_SESSION_CONTROL,
    PWA_REALTIME_SESSION_CONTROLLER,
    RealtimeSessionController,
)
from apps.pwa_api.websocket_sessions import (
    SessionRevalidationStatus,
    WebSocketSessionAlreadyClosedError,
    WebSocketSessionIdentity,
    WebSocketSessionRegistry,
)
from db_methods.pwa.auth import PwaAuthRepository
from db_methods.pwa.content import GroupLessonContentScope, PwaContentRepository
from helpers.config import logger
from helpers.nats_brocker import InProcessBroker, JsonBroker, NatsBroker
from helpers.object_storage import ObjectStorage, create_object_storage
from helpers.pwa.api_contracts import (
    build_api_error_payload,
    build_realtime_error_payload,
    build_runtime_payload,
    validate_runtime_instance,
)
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG
from helpers.pwa.auth_config import AuthRuntimeConfig, load_auth_runtime_config
from helpers.pwa.content import (
    ConfiguredContentAssetConverter,
    ContentAssetConverter,
    ContentAssetService,
)
from helpers.pwa.storage_config import load_storage_config
from models.pwa.auth import AuthAudience
from models.pwa.content import ContentKind

__all__ = ["PwaApiError", "pwa_routes"]

AUDIENCES = ("student", "family", "staff")
NATS_PWA_INVALIDATE = "pwa_invalidate"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
INVALIDATION_RESOURCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,255}$")
INVALIDATION_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ACCOUNT_PUBLIC_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
INVALIDATION_KEYS = frozenset({"resources", "reason", "audience", "accountId"})
MAX_INVALIDATION_RESOURCES = 128
WEBSOCKET_CLOSE_TIMEOUT_SECONDS = 5
CONTENT_SCHEDULER_INTERVAL_SECONDS = 5
CONTENT_SCHEDULER_BATCH_SIZE = 128
CONTENT_SCHEDULER_SHUTDOWN_TIMEOUT_SECONDS = 5
PWA_STATE = web.AppKey("pwa_state", dict)
PWA_BROKER = web.AppKey("pwa_broker", JsonBroker)
PWA_WEBSOCKET_REGISTRY = web.AppKey("pwa_websocket_registry", WebSocketSessionRegistry)
PWA_CONTENT_SCHEDULER_STOP = web.AppKey("pwa_content_scheduler_stop", asyncio.Event)
PWA_CONTENT_SCHEDULER_TASK = web.AppKey(
    "pwa_content_scheduler_task", asyncio.Task[None]
)
PWA_RESPONSE_PREPARED = web.AppKey("pwa_response_prepared", bool)
PWA_CONTENT_ASSET_CONVERTER = web.AppKey(
    "pwa_content_asset_converter",
    ContentAssetConverter | ConfiguredContentAssetConverter,
)
PWA_CONTENT_ASSETS_AUTO_WIRE = web.AppKey("pwa_content_assets_auto_wire", bool)
PWA_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
PWA_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}
REBUILT_RESPONSE_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "content-type",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "cache-control",
        "expires",
        "pragma",
        *(name.casefold() for name in PWA_SECURITY_HEADERS),
    }
)

pwa_routes = web.RouteTableDef()


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _audience(request: web.Request) -> str:
    audience = request.match_info.get("audience", "")
    if audience not in AUDIENCES:
        raise web.HTTPNotFound(text="Unknown PWA audience")
    return audience


def _request_id(request: web.Request) -> str:
    return request["request_id"]


def _runtime_config(app: web.Application):
    return app[RUNTIME_CONFIG]


def _is_pwa_transport_path(path: str) -> bool:
    return any(
        path == f"/{audience}/ws"
        or path == f"/{audience}/api"
        or path.startswith(f"/{audience}/api/")
        for audience in AUDIENCES
    )


def _copy_rebuilt_response_headers(
    response: web.StreamResponse, headers: Mapping[str, str]
) -> None:
    """Preserve end-to-end exception headers while owning body/cache headers."""

    for name, value in headers.items():
        if name.casefold() not in REBUILT_RESPONSE_HEADERS:
            response.headers.add(name, value)


def _apply_pwa_response_headers(response: web.StreamResponse, request_id: str) -> None:
    response.headers["X-Request-ID"] = request_id
    for name, value in PWA_NO_STORE_HEADERS.items():
        response.headers[name] = value
    for name, value in PWA_SECURITY_HEADERS.items():
        response.headers[name] = value


async def on_pwa_response_prepare(
    request: web.Request, response: web.StreamResponse
) -> None:
    """Apply the PWA wire boundary immediately before headers are written."""

    if not _is_pwa_transport_path(request.path):
        return
    # At this point aiohttp has attached its payload writer. If the handler
    # later fails, middleware must not try to replace this response with JSON.
    # See vmshpwa/docs/runtime-isolation.md.
    request[PWA_RESPONSE_PREPARED] = True
    _apply_pwa_response_headers(response, _request_id(request))


def _create_pwa_state() -> dict[str, dict[str, object]]:
    """Create one internally consistent realtime state for an app instance."""

    return {
        "cursors": {audience: 0 for audience in AUDIENCES},
        "broadcast_locks": {audience: asyncio.Lock() for audience in AUDIENCES},
    }


@web.middleware
async def pwa_error_middleware(request: web.Request, handler):
    if not _is_pwa_transport_path(request.path):
        return await handler(request)

    incoming_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        incoming_request_id
        if REQUEST_ID_PATTERN.fullmatch(incoming_request_id)
        else uuid.uuid4().hex
    )
    request["request_id"] = request_id
    try:
        response = await handler(request)
    except Exception as exc:
        if request.get(PWA_RESPONSE_PREPARED, False):
            logger.exception(
                "PWA handler failed after response preparation, request_id=%s",
                request_id,
            )
            raise
        if isinstance(exc, PwaApiError):
            response = web.json_response(
                build_api_error_payload(
                    code=exc.code,
                    message=exc.message,
                    request_id=request_id,
                    details=exc.details,
                ),
                status=exc.status,
            )
            _copy_rebuilt_response_headers(response, exc.headers)
        elif isinstance(exc, web.HTTPException):
            response = web.json_response(
                build_api_error_payload(
                    code=exc.reason.lower().replace(" ", "_"),
                    message=exc.text,
                    request_id=request_id,
                ),
                status=exc.status,
            )
            _copy_rebuilt_response_headers(response, exc.headers)
        else:
            logger.exception("Unhandled PWA API exception, request_id=%s", request_id)
            response = web.json_response(
                build_api_error_payload(
                    code="internal_error",
                    message="Внутренняя ошибка сервера",
                    request_id=request_id,
                ),
                status=500,
            )
    if not response.prepared:
        _apply_pwa_response_headers(response, request_id)
    return response


@pwa_routes.get("/{audience:student|family|staff}/api/v1/health")
async def health(request: web.Request):
    return web.json_response(
        {"ok": True, "audience": _audience(request), "requestId": _request_id(request)}
    )


@pwa_routes.get("/{audience:student|family|staff}/api/v1/runtime")
async def runtime(request: web.Request):
    audience = _audience(request)
    runtime_config = _runtime_config(request.app)
    broker = request.app[PWA_BROKER]
    return web.json_response(
        build_runtime_payload(
            audience=audience,
            instance=runtime_config.pwa_instance or runtime_config.config_name,
            server_time=_now(),
            request_id=_request_id(request),
            telegram=bool(runtime_config.telegram_bot_token),
            google=bool(runtime_config.google_cred_json),
            nats=broker.nats_is_working,
            prototype=runtime_config.pwa_prototype,
        )
    )


@pwa_routes.post("/api/pwa/health")
async def legacy_health(_request: web.Request):
    return web.json_response({"ok": True})


async def _close_failed_websocket(websocket) -> None:
    """Bound post-upgrade cleanup without logging transport exception data."""

    if websocket.closed:
        return
    try:
        async with asyncio.timeout(WEBSOCKET_CLOSE_TIMEOUT_SECONDS):
            await websocket.close(
                code=WSCloseCode.INTERNAL_ERROR,
                message=b"Realtime transport failure",
            )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("Failed to close an authenticated PWA websocket")


async def _broadcast(
    app: web.Application,
    resources: list[str],
    reason: str,
    audience: str | None = None,
    account_public_id: str | None = None,
):
    if audience is not None and audience not in AUDIENCES:
        raise ValueError(f"Unknown PWA audience: {audience}")
    if account_public_id is not None:
        if audience is None:
            raise ValueError("Owner-scoped invalidation requires an audience")
        if ACCOUNT_PUBLIC_ID_PATTERN.fullmatch(account_public_id) is None:
            raise ValueError("Invalid account public ID")

    async def broadcast_to_audience(target_audience: str) -> None:
        state = app[PWA_STATE]
        # NATS happens to dispatch one subscription sequentially today, but
        # the broker interface and direct domain callers do not promise that.
        # Serialize cursor allocation and socket writes per audience while
        # allowing Student/Family/Staff fan-out to proceed independently.
        async with state["broadcast_locks"][target_audience]:
            state["cursors"][target_audience] += 1
            event = {
                "type": "invalidate",
                "cursor": state["cursors"][target_audience],
                "serverTime": _now(),
                "resources": resources,
                "reason": reason,
                "audience": target_audience,
            }
            registry = app[PWA_WEBSOCKET_REGISTRY]
            if account_public_id is None:
                await registry.send_to_audience(
                    audience=target_audience,
                    payload=event,
                )
            else:
                # The routing target is server-side broker metadata and must
                # not be echoed to browser clients or logs.
                await registry.send_to_account(
                    audience=target_audience,
                    account_public_id=account_public_id,
                    payload=event,
                )

    target_audiences = (audience,) if audience is not None else AUDIENCES
    await asyncio.gather(
        *(
            broadcast_to_audience(target_audience)
            for target_audience in target_audiences
        )
    )


@pwa_routes.get("/{audience:student|family|staff}/ws")
async def realtime(request: web.Request):
    audience = _audience(request)
    auth_audience = AuthAudience(audience)
    validate_request_boundary(
        request,
        audience=auth_audience,
        expects_json=False,
        require_browser_source=True,
    )
    authenticated = await authenticate_access_cookie(
        request,
        audience=auth_audience,
        required=True,
    )
    assert authenticated is not None
    cursor_value = request.query.get("cursor")
    if cursor_value is not None:
        try:
            requested_cursor = int(cursor_value)
        except ValueError as exc:
            raise web.HTTPBadRequest(
                text="cursor must be a non-negative integer"
            ) from exc
        if requested_cursor < 0:
            raise web.HTTPBadRequest(text="cursor must be a non-negative integer")

    websocket = web.WebSocketResponse(heartbeat=25, max_msg_size=64 * 1024)
    _apply_pwa_response_headers(websocket, _request_id(request))
    await websocket.prepare(request)
    state = request.app[PWA_STATE]
    registry = request.app[PWA_WEBSOCKET_REGISTRY]
    registered = False

    try:
        await registry.register_pending(
            websocket,
            audience=audience,
            account_public_id=authenticated.principal.account_public_id,
            session_public_id=authenticated.principal.session_public_id,
        )
        registered = True

        activation_status = await registry.revalidate_pending(
            websocket,
            revalidate=lambda candidate: _revalidate_websocket_identity(
                request.app,
                candidate,
            ),
        )
        if activation_status is not SessionRevalidationStatus.VALID:
            return websocket

        # Keep a pending transport out of invalidation fan-out until SQLite
        # has revalidated it and the initial cursor frame is on the wire.
        # Authoritative DB I/O is complete before taking the audience-wide
        # lock; any invalidation in that interval advances the cursor and is
        # absorbed by the initial full state fetch.  Cursor capture + activation
        # itself remains one operation with respect to _broadcast().
        async with state["broadcast_locks"][audience]:
            current_cursor = state["cursors"][audience]
            initial_payload = (
                {
                    "type": "resync-required",
                    "cursor": current_cursor,
                    "serverTime": _now(),
                    "reason": "reconnect-full-refetch-required",
                }
                if cursor_value is not None
                else {
                    "type": "connected",
                    "cursor": current_cursor,
                    "serverTime": _now(),
                    "audience": audience,
                }
            )
            activation_status = await registry.activate_with_initial(
                websocket,
                payload=initial_payload,
            )
        if activation_status is not SessionRevalidationStatus.VALID:
            return websocket

        async def send(payload: Mapping[str, object]) -> bool:
            report = await registry.send_to_connection(
                websocket,
                payload=payload,
            )
            return report.succeeded == 1

        async for message in websocket:
            if message.type == WSMsgType.TEXT:
                try:
                    payload = json.loads(message.data)
                except json.JSONDecodeError, RecursionError:
                    # HTTP middleware can no longer replace the response after
                    # WebSocket upgrade. Keep protocol errors on the versioned
                    # realtime wire contract instead. See Phase 0 contracts.
                    if not await send(
                        build_realtime_error_payload(
                            cursor=state["cursors"][audience],
                            server_time=_now(),
                            code="invalid_json",
                            message="Сообщение WebSocket должно быть корректным JSON",
                            request_id=_request_id(request),
                        )
                    ):
                        break
                    continue
                if isinstance(payload, dict) and payload.get("type") == "ping":
                    if not await send(
                        {
                            "type": "pong",
                            "cursor": state["cursors"][audience],
                            "serverTime": _now(),
                        }
                    ):
                        break
            elif message.type == WSMsgType.ERROR:
                logger.warning("Authenticated PWA websocket transport error")
    except asyncio.CancelledError:
        raise
    except WebSocketSessionAlreadyClosedError:
        # A same-worker/session control command won the gap between cookie
        # authentication and process-local registration.  It is an expected
        # fail-closed outcome, not a transport failure and never gets a
        # ``connected`` frame.
        await _close_failed_websocket(websocket)
    except Exception:
        # Once prepare() succeeds the HTTP error middleware cannot replace the
        # upgraded response. Contain transport/serialization failures here,
        # close with a bounded wait, and return the original WebSocket object.
        logger.warning("Authenticated PWA websocket failed after upgrade")
        if registered:
            await registry.close_connection(
                websocket,
                code=WSCloseCode.INTERNAL_ERROR,
                message=b"Realtime transport failure",
            )
        else:
            await _close_failed_websocket(websocket)
    finally:
        # Failed close operations intentionally remain registered for the
        # next authoritative revalidation or shutdown attempt.  Successful
        # and peer-driven closes are removed immediately.
        if websocket.closed:
            await registry.unregister(websocket)
    return websocket


async def _revalidate_websocket_identity(
    app: web.Application,
    identity: WebSocketSessionIdentity,
) -> SessionRevalidationStatus:
    """Map current SQLite session authority to the registry's close policy."""

    auth_state = app.get(PWA_AUTH_STATE)
    service = None if auth_state is None else auth_state.service
    if service is None:
        return SessionRevalidationStatus.CORRUPT
    try:
        audience = AuthAudience(identity.audience)
    except ValueError:
        return SessionRevalidationStatus.CORRUPT
    active = await service.is_websocket_session_active(
        audience=audience,
        account_public_id=identity.account_public_id,
        session_public_id=identity.session_public_id,
    )
    return (
        SessionRevalidationStatus.VALID if active else SessionRevalidationStatus.REVOKED
    )


async def on_startup(app: web.Application):
    runtime_config = _runtime_config(app)
    broker = app[PWA_BROKER]
    logger.info(
        "PWA app startup: instance=%s",
        runtime_config.pwa_instance or runtime_config.config_name,
    )

    async def handle_invalidation(payload):
        if not isinstance(payload, dict):
            logger.warning("Ignoring non-object PWA invalidation")
            return
        if not set(payload).issubset(INVALIDATION_KEYS):
            logger.warning("Ignoring invalid PWA invalidation fields")
            return
        raw_resources = payload.get("resources")
        if (
            not isinstance(raw_resources, list)
            or not 1 <= len(raw_resources) <= MAX_INVALIDATION_RESOURCES
            or not all(
                isinstance(item, str) and INVALIDATION_RESOURCE_PATTERN.fullmatch(item)
                for item in raw_resources
            )
        ):
            logger.warning("Ignoring invalid PWA invalidation resources")
            return
        resources = list(dict.fromkeys(raw_resources))
        audience = payload.get("audience")
        if audience is not None and audience not in AUDIENCES:
            logger.warning("Ignoring invalid PWA invalidation audience")
            return
        account_public_id = payload.get("accountId")
        if account_public_id is not None:
            if (
                audience is None
                or not isinstance(account_public_id, str)
                or ACCOUNT_PUBLIC_ID_PATTERN.fullmatch(account_public_id) is None
            ):
                logger.warning("Ignoring invalid PWA invalidation owner scope")
                return
        reason = payload.get("reason", "nats")
        if not isinstance(reason, str) or not INVALIDATION_REASON_PATTERN.fullmatch(
            reason
        ):
            logger.warning("Ignoring invalid PWA invalidation reason")
            return
        await _broadcast(
            app,
            resources,
            reason,
            audience=audience,
            account_public_id=account_public_id,
        )

    try:
        await broker.setup(runtime_config.nats_server)
        await broker.subscribe(NATS_PWA_INVALIDATE, handle_invalidation)
        await broker.subscribe(
            NATS_PWA_SESSION_CONTROL,
            app[PWA_REALTIME_SESSION_CONTROLLER].handle_broker_payload,
        )
        await broker.ready()
        if app.get(PWA_AUTH_STATE) is not None:
            app[PWA_WEBSOCKET_REGISTRY].start_revalidation(
                lambda identity: _revalidate_websocket_identity(app, identity)
            )
    except BaseException as startup_error:
        # aiohttp does not promise to run an adapter's shutdown hook after that
        # adapter's startup callback fails. Setup itself may allocate a client
        # before raising, so the whole adapter startup belongs inside this guard.
        cleanup_errors: list[BaseException] = []
        try:
            await app[PWA_WEBSOCKET_REGISTRY].shutdown()
        except BaseException as cleanup_error:
            cleanup_errors.append(cleanup_error)
        try:
            await broker.disconnect()
        except BaseException as cleanup_error:
            cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            raise BaseExceptionGroup(
                "PWA realtime startup and cleanup failed",
                [startup_error, *cleanup_errors],
            ) from None
        raise


async def on_auth_startup(app: web.Application) -> None:
    """Create auth dependencies after the shared DB cleanup context is ready."""

    state = app[PWA_AUTH_STATE]
    if state.service is not None:
        return
    if PWA_DATABASE not in app:
        # Small broker/protocol unit tests compose the adapter directly without
        # the application factory. They do not expose auth routes/middleware.
        return
    factory = app[PWA_DATABASE].factory
    if factory is None:
        raise RuntimeError("PWA auth startup requires a verified database factory")
    state.service = await PwaAuthService.create(
        PwaAuthRepository(factory),
        state.runtime_config,
    )


async def on_content_startup(app: web.Application) -> None:
    """Bind Phase-2 content routes to the verified shared SQLite factory."""

    if PWA_CONTENT_REPOSITORY not in app:
        factory = app[PWA_DATABASE].factory
        if factory is None:
            raise RuntimeError(
                "PWA content startup requires a verified database factory"
            )
        app[PWA_CONTENT_REPOSITORY] = PwaContentRepository(factory)
    if (
        PWA_CONTENT_ASSET_SERVICE in app
        or not app.get(PWA_CONTENT_ASSETS_AUTO_WIRE, False)
    ):
        return

    runtime_config = _runtime_config(app)
    storage = app.get(PWA_CONTENT_OBJECT_STORAGE)
    if storage is None:
        storage_config = load_storage_config(
            runtime_profile=runtime_config.runtime_profile,
            media_root=runtime_config.pwa_media_root,
            repository_root=Path(__file__).resolve().parents[1],
        )
        storage = create_object_storage(storage_config)
        app[PWA_CONTENT_OBJECT_STORAGE] = storage
    converter = app.get(PWA_CONTENT_ASSET_CONVERTER)
    if converter is None:
        converter = ConfiguredContentAssetConverter(runtime_config)
        app[PWA_CONTENT_ASSET_CONVERTER] = converter
    app[PWA_CONTENT_ASSET_SERVICE] = ContentAssetService(
        converter=converter,
        storage=storage,
        repository=app[PWA_CONTENT_REPOSITORY],
    )


async def publish_content_invalidation(
    app: web.Application,
    scope: GroupLessonContentScope,
    kind: ContentKind,
    reason: str,
) -> None:
    """Best-effort realtime fan-out after an authoritative content commit."""

    resource = f"group-lessons/{scope.group_lesson_public_id}/content/{kind.value}"
    try:
        await app[PWA_BROKER].publish(
            NATS_PWA_INVALIDATE,
            {"resources": [resource], "reason": reason},
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        # The SQLite transition is already authoritative.  NATS is transient
        # fan-out, so a delivery failure must not turn a successful mutation
        # into an HTTP error or invite an unsafe client retry.
        logger.warning(
            "Content invalidation failed after commit: resource=%s reason=%s",
            resource,
            reason,
            exc_info=True,
        )


async def activate_due_content_publications(
    app: web.Application,
    *,
    batch_size: int = CONTENT_SCHEDULER_BATCH_SIZE,
) -> int:
    """Activate at most one bounded batch of due publication rows."""

    if batch_size < 1:
        raise ValueError("content scheduler batch size must be positive")
    repository = app[PWA_CONTENT_REPOSITORY]
    invalidator = app[PWA_CONTENT_INVALIDATOR]
    activated = 0
    while activated < batch_size:
        context = await repository.activate_next_due_publication(
            published_public_id=f"publication-scheduled-{uuid.uuid4().hex}"
        )
        if context is None:
            break
        activated += 1
        await invalidator(
            context.scope,
            context.publication.kind,
            "content-schedule-activated",
        )
    return activated


async def _content_scheduler_loop(app: web.Application) -> None:
    stop = app[PWA_CONTENT_SCHEDULER_STOP]
    while not stop.is_set():
        try:
            activated = await activate_due_content_publications(app)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A corrupt row or temporary SQLite failure must not silently kill
            # scheduled publication for every other material in this worker.
            logger.exception("PWA content scheduler iteration failed")
            activated = 0

        if stop.is_set():
            break
        if activated == CONTENT_SCHEDULER_BATCH_SIZE:
            # A full batch may mean more rows are already due.  Yield to the
            # event loop, then continue without an arbitrary five-second gap.
            await asyncio.sleep(0)
            continue
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=CONTENT_SCHEDULER_INTERVAL_SECONDS
            )
        except TimeoutError:
            pass


async def on_content_scheduler_startup(app: web.Application) -> None:
    """Start the scheduler only after both SQLite and broker are ready."""

    if PWA_CONTENT_REPOSITORY not in app:
        return
    stop = asyncio.Event()
    app[PWA_CONTENT_SCHEDULER_STOP] = stop
    app[PWA_CONTENT_SCHEDULER_TASK] = asyncio.create_task(
        _content_scheduler_loop(app),
        name="pwa-content-publication-scheduler",
    )


async def on_content_scheduler_shutdown(app: web.Application) -> None:
    """Let the active transaction finish before realtime is disconnected."""

    task = app.get(PWA_CONTENT_SCHEDULER_TASK)
    stop = app.get(PWA_CONTENT_SCHEDULER_STOP)
    if task is None or stop is None:
        return
    stop.set()
    try:
        async with asyncio.timeout(CONTENT_SCHEDULER_SHUTDOWN_TIMEOUT_SECONDS):
            await asyncio.shield(task)
    except TimeoutError:
        logger.warning("PWA content scheduler did not stop before the deadline")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise


async def on_shutdown(app: web.Application):
    shutdown_errors: list[BaseException] = []
    try:
        await on_content_scheduler_shutdown(app)
    except BaseException as error:
        shutdown_errors.append(error)
    try:
        await app[PWA_WEBSOCKET_REGISTRY].shutdown()
    except BaseException as error:
        shutdown_errors.append(error)
    try:
        await app[PWA_BROKER].disconnect()
    except BaseException as error:
        shutdown_errors.append(error)
    if shutdown_errors:
        raise BaseExceptionGroup("PWA realtime shutdown failed", shutdown_errors)
    logger.info("PWA app shutdown")


def configure(
    app: web.Application,
    *,
    broker: JsonBroker | None = None,
    auth_runtime_config: AuthRuntimeConfig | None = None,
    auth_service: PwaAuthService | None = None,
    content_repository: PwaContentRepository | None = None,
    content_asset_service: ContentAssetService | None = None,
    object_storage: ObjectStorage | None = None,
    content_asset_converter: (
        ContentAssetConverter | ConfiguredContentAssetConverter | None
    ) = None,
):
    runtime_config = _runtime_config(app)
    # Browser storage uses this server-owned value verbatim. Rejecting an
    # unsafe namespace during composition prevents a partially working process
    # whose frontend would fail closed only after the first request.
    validate_runtime_instance(runtime_config.pwa_instance or runtime_config.config_name)
    if broker is None:
        if runtime_config.nats_server:
            broker = NatsBroker(runtime_config.config_name)
        else:
            broker = InProcessBroker(runtime_config.config_name)
    app.middlewares.append(pwa_error_middleware)
    app.on_response_prepare.append(on_pwa_response_prepare)
    app[PWA_BROKER] = broker
    app[PWA_STATE] = _create_pwa_state()
    registry = WebSocketSessionRegistry()
    app[PWA_WEBSOCKET_REGISTRY] = registry
    app[PWA_REALTIME_SESSION_CONTROLLER] = RealtimeSessionController(
        registry,
        broker,
    )
    content_enabled = False
    auth_enabled = (
        auth_runtime_config is not None
        or auth_service is not None
        or PWA_DATABASE in app
    )
    if auth_enabled:
        resolved_auth_config = auth_runtime_config or (
            auth_service.runtime_config
            if auth_service is not None
            else load_auth_runtime_config(runtime_config)
        )
        if (
            auth_service is not None
            and auth_service.runtime_config is not resolved_auth_config
            and auth_service.runtime_config != resolved_auth_config
        ):
            raise ValueError("Injected auth service and runtime config disagree")
        app[PWA_AUTH_STATE] = PwaAuthState(
            runtime_config=resolved_auth_config,
            service=auth_service,
        )
        app.middlewares.append(pwa_auth_request_security_middleware)
        app.middlewares.append(pwa_authentication_middleware)
        app.add_routes(auth_routes)
        app.add_routes(course_routes)
        app.on_startup.append(on_auth_startup)
        content_enabled = content_repository is not None or PWA_DATABASE in app
        if content_enabled:
            if content_repository is not None:
                app[PWA_CONTENT_REPOSITORY] = content_repository
            if content_asset_service is not None:
                app[PWA_CONTENT_ASSET_SERVICE] = content_asset_service
                app[PWA_CONTENT_OBJECT_STORAGE] = content_asset_service.storage
            elif object_storage is not None:
                app[PWA_CONTENT_OBJECT_STORAGE] = object_storage
            if content_asset_converter is not None:
                app[PWA_CONTENT_ASSET_CONVERTER] = content_asset_converter
            app[PWA_CONTENT_ASSETS_AUTO_WIRE] = bool(
                content_asset_service is not None
                or (
                    object_storage is not None
                    and content_asset_converter is not None
                )
                or content_repository is None
            )

            async def invalidate_content(
                scope: GroupLessonContentScope,
                kind: ContentKind,
                reason: str,
            ) -> None:
                await publish_content_invalidation(app, scope, kind, reason)

            app[PWA_CONTENT_INVALIDATOR] = invalidate_content
            app.add_routes(content_routes)
            app.on_startup.append(on_content_startup)
    app.add_routes(pwa_routes)
    app.on_startup.append(on_startup)
    if content_enabled:
        # Registration order is deliberate: SQLite binding happens first,
        # realtime/NATS second, and only then can the scheduler commit and fan
        # out its first due activation.
        app.on_startup.append(on_content_scheduler_startup)
    app.on_shutdown.append(on_shutdown)


# Compatibility alias for older launchers; new code uses the correctly named API.
configue = configure


if __name__ == "__main__":
    raise SystemExit(
        "Use the explicit PWA runtime entry point; this module is an adapter"
    )
