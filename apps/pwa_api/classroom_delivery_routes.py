"""Admin endpoints for explicitly announcing confirmed classroom assignments."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from aiohttp import web

from apps.pwa_api.classroom_assignment_routes import (
    PWA_CLASSROOM_ASSIGNMENT_INVALIDATOR,
)
from apps.pwa_api.classroom_delivery_transport import (
    TelegramClassroomSender,
    deliver_classroom_telegram_batch,
)
from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.middleware import authenticated_session
from db_methods.pwa.classroom_assignments import list_assignment_owner_accounts
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.permissions import Capability
from models.pwa.auth import AuthAudience
from models.pwa.classroom_delivery import (
    ClassroomDeliveryConflict,
    ClassroomDeliveryNotFound,
    InvalidClassroomDelivery,
    create_classroom_delivery_batch,
    preview_classroom_delivery,
    read_classroom_delivery_batch,
    read_latest_classroom_delivery_batch,
    retry_failed_classroom_delivery,
)


classroom_delivery_routes = web.RouteTableDef()
PWA_CLASSROOM_TELEGRAM_SENDER = web.AppKey(
    "pwa_classroom_telegram_sender", TelegramClassroomSender
)
_PUBLIC_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$")
_HASH = re.compile(r"^[a-f0-9]{64}$")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _factory(request: web.Request):
    state = request.app.get(PWA_DATABASE)
    if state is None or state.factory is None:
        raise PwaApiError(
            status=503,
            code="classroom_delivery_unavailable",
            message="Рассылка аудиторий временно недоступна",
        )
    return state.factory


def _admin_user_id(request: web.Request) -> int:
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or principal.linked_user_id is None
        or not principal.is_global_admin
        or not principal.has_capability(Capability.CLASSROOM_MANAGE)
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Рассылать аудитории может только администратор",
        )
    return principal.linked_user_id


def _public_id(request: web.Request, name: str) -> str:
    value = request.match_info[name]
    if _PUBLIC_ID.fullmatch(value) is None:
        raise PwaApiError(
            status=404,
            code="classroom_delivery_not_found",
            message="Рассылка аудиторий не найдена",
        )
    return value


async def _json(request: web.Request) -> dict[str, object]:
    if request.content_type != "application/json":
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть JSON",
        )
    try:
        payload = json.loads(await request.read())
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Тело запроса должно быть корректным JSON-объектом",
        ) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры рассылки",
        )
    return payload


def _raise_domain_error(error: Exception) -> None:
    if isinstance(error, ClassroomDeliveryNotFound):
        raise PwaApiError(
            status=404,
            code="classroom_delivery_not_found",
            message="План или рассылка аудиторий не найдены",
        ) from error
    if isinstance(error, ClassroomDeliveryConflict):
        raise PwaApiError(
            status=409,
            code="classroom_delivery_conflict",
            message="План изменился. Обновите предпросмотр рассылки.",
        ) from error
    if isinstance(error, InvalidClassroomDelivery):
        raise PwaApiError(
            status=422,
            code="invalid_classroom_delivery",
            message="Сначала подтвердите корректное распределение аудиторий",
        ) from error
    raise error


def _preview_payload(result: dict[str, object]) -> dict[str, object]:
    return {
        "planPublicId": result["plan_public_id"],
        "planVersion": result["plan_version"],
        "previewHash": result["snapshot_hash"],
        "recipientCount": result["recipient_count"],
        "changedCount": result["changed_count"],
        "pwaUnavailableCount": result["pwa_unavailable_count"],
        "telegramUnavailableCount": result["telegram_unavailable_count"],
        "recipients": [
            {
                "studentPublicId": item["student_public_id"],
                "studentName": item["student_display_name"],
                "coursePublicId": item["course_public_id"],
                "courseName": item["course_name"],
                "groupPublicId": item["group_public_id"],
                "groupName": item["group_name"],
                "classroomPublicId": item["classroom_public_id"],
                "classroomName": item["classroom_name"],
                "changed": item["changed"],
                "pwaAvailable": item["pwa_available"],
                "telegramAvailable": item["telegram_available"],
            }
            for item in result["recipients"]
        ],
    }


def _batch_payload(result: dict[str, object]) -> dict[str, object]:
    batch = result["batch"]
    recipients = result["recipients"]

    def counts(channel: str) -> dict[str, int]:
        values = [str(item[f"{channel}_state"]) for item in recipients]
        return {
            state: values.count(state)
            for state in (
                "not_requested",
                "queued",
                "sent",
                "suppressed",
                "failed",
            )
            if state in values
        }

    selected_channels = [
        channel
        for channel, selected in (
            ("pwa", batch["pwa_selected"]),
            ("telegram", batch["telegram_selected"]),
        )
        if selected
    ]

    # Phase 8 reports are derived from immutable recipient rows, not from a
    # second mutable counter store. See development-plan/12-phase-8-news-and-notifications.md.
    def report_counts(channel: str) -> dict[str, int]:
        selected = channel in selected_channels
        states = (
            [str(item[f"{channel}_state"]) for item in recipients] if selected else []
        )
        succeeded = states.count("sent")
        failed = states.count("failed")
        queued = states.count("queued")
        suppressed = states.count("suppressed")
        return {
            "selected": len(states),
            "eligible": queued + succeeded + failed,
            "suppressed": suppressed,
            "queued": queued,
            "attempted": succeeded + failed,
            "succeeded": succeeded,
            "failed": failed,
        }

    delivered_any = 0
    delivered_all = 0
    for recipient in recipients:
        states = [str(recipient[f"{channel}_state"]) for channel in selected_channels]
        succeeded = sum(state == "sent" for state in states)
        delivered_any += succeeded > 0
        delivered_all += bool(states) and succeeded == len(states)

    return {
        "publicId": batch["public_id"],
        "planPublicId": batch["plan_public_id"],
        "planVersion": batch["assignment_plan_version"],
        "previewHash": batch["recipient_snapshot_hash"],
        "channels": selected_channels,
        "recipientCount": batch["recipient_count"],
        "changedCount": batch["changed_since_previous_count"],
        "state": batch["state"],
        "createdAt": batch["created_at"],
        "completedAt": batch["completed_at"],
        "version": batch["version"],
        "channelCounts": {"pwa": counts("pwa"), "telegram": counts("telegram")},
        "deliveryReport": {
            "channels": {
                "pwa": report_counts("pwa"),
                "telegram": report_counts("telegram"),
            },
            "deliveredAny": delivered_any,
            "deliveredAll": delivered_all,
            "partial": delivered_any - delivered_all,
        },
        "recipients": [
            {
                "studentPublicId": item["student_public_id"],
                "studentName": item["student_display_name"],
                "coursePublicId": item["course_public_id"],
                "courseName": item["course_name"],
                "groupPublicId": item["group_public_id"],
                "groupName": item["group_name"],
                "classroomPublicId": item["classroom_public_id"],
                "classroomName": item["classroom_name"],
                "pwa": {
                    "state": item["pwa_state"],
                    "errorCode": item["pwa_error_code"],
                    "sentAt": item["pwa_sent_at"],
                },
                "telegram": {
                    "state": item["telegram_state"],
                    "errorCode": item["telegram_error_code"],
                    "sentAt": item["telegram_sent_at"],
                },
            }
            for item in recipients
        ],
    }


@classroom_delivery_routes.post(
    "/staff/api/v1/classroom-assignment-plans/{plan_public_id}/delivery-preview"
)
async def post_classroom_delivery_preview(request: web.Request) -> web.Response:
    _admin_user_id(request)
    plan_public_id = _public_id(request, "plan_public_id")
    payload = await _json(request)
    if set(payload) != {"schemaVersion"}:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры предпросмотра",
        )
    try:
        result = await _factory(request).run_read_async(
            lambda connection: preview_classroom_delivery(
                connection, plan_public_id=plan_public_id
            )
        )
    except (
        ClassroomDeliveryNotFound,
        ClassroomDeliveryConflict,
        InvalidClassroomDelivery,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError("unreachable")
    return web.json_response(
        {
            "schemaVersion": 1,
            "preview": _preview_payload(result),
            "requestId": request["request_id"],
        }
    )


@classroom_delivery_routes.post(
    "/staff/api/v1/classroom-assignment-plans/{plan_public_id}/delivery-batches"
)
async def post_classroom_delivery_batch(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    plan_public_id = _public_id(request, "plan_public_id")
    payload = await _json(request)
    if set(payload) != {
        "schemaVersion",
        "channels",
        "expectedPlanVersion",
        "previewHash",
        "idempotencyKey",
    }:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры рассылки",
        )
    channels = payload["channels"]
    version = payload["expectedPlanVersion"]
    preview_hash = payload["previewHash"]
    idempotency_key = payload["idempotencyKey"]
    if (
        not isinstance(channels, list)
        or not channels
        or len(channels) != len(set(channels))
        or any(channel not in {"pwa", "telegram"} for channel in channels)
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version < 1
        or not isinstance(preview_hash, str)
        or _HASH.fullmatch(preview_hash) is None
        or not isinstance(idempotency_key, str)
        or not 1 <= len(idempotency_key) <= 128
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры рассылки",
        )
    try:
        result = await _factory(request).run_write_async(
            lambda connection: create_classroom_delivery_batch(
                connection,
                plan_public_id=plan_public_id,
                expected_plan_version=version,
                expected_snapshot_hash=preview_hash,
                actor_user_id=actor_user_id,
                pwa_selected="pwa" in channels,
                telegram_selected="telegram" in channels,
                idempotency_key=idempotency_key,
                now=_now(),
            )
        )
    except (
        ClassroomDeliveryNotFound,
        ClassroomDeliveryConflict,
        InvalidClassroomDelivery,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError("unreachable")

    student_user_ids = tuple(result.get("student_user_ids", ()))
    sender = request.app.get(PWA_CLASSROOM_TELEGRAM_SENDER)
    if sender is not None and result["batch"]["state"] == "queued":
        result = await deliver_classroom_telegram_batch(
            _factory(request),
            batch_public_id=str(result["batch"]["public_id"]),
            sender=sender,
            now=_now,
        )

    if student_user_ids:
        owners = await _factory(request).run_read_async(
            lambda connection: list_assignment_owner_accounts(
                connection, student_user_ids
            )
        )
        invalidator = request.app.get(PWA_CLASSROOM_ASSIGNMENT_INVALIDATOR)
        if invalidator is not None:
            await invalidator(
                tuple(
                    str(owner["public_id"])
                    for owner in owners
                    if owner["audience"] == AuthAudience.STUDENT.value
                ),
                (),
                "classroom-assignment-announced",
            )
    return web.json_response(
        {
            "schemaVersion": 1,
            "batch": _batch_payload(result),
            "requestId": request["request_id"],
        },
        status=201,
    )


@classroom_delivery_routes.get(
    "/staff/api/v1/classroom-assignment-plans/{plan_public_id}/delivery-latest"
)
async def get_latest_classroom_delivery_batch(request: web.Request) -> web.Response:
    _admin_user_id(request)
    plan_public_id = _public_id(request, "plan_public_id")
    result = await _factory(request).run_read_async(
        lambda connection: read_latest_classroom_delivery_batch(
            connection, plan_public_id
        )
    )
    return web.json_response(
        {
            "schemaVersion": 1,
            "batch": None if result is None else _batch_payload(result),
            "requestId": request["request_id"],
        }
    )


@classroom_delivery_routes.post(
    "/staff/api/v1/classroom-assignment-delivery-batches/{batch_public_id}/retry-failed"
)
async def post_classroom_delivery_retry(request: web.Request) -> web.Response:
    actor_user_id = _admin_user_id(request)
    batch_public_id = _public_id(request, "batch_public_id")
    payload = await _json(request)
    if set(payload) != {
        "schemaVersion",
        "expectedBatchVersion",
        "idempotencyKey",
    }:
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры повтора рассылки",
        )
    version = payload["expectedBatchVersion"]
    idempotency_key = payload["idempotencyKey"]
    if (
        not isinstance(version, int)
        or isinstance(version, bool)
        or version < 1
        or not isinstance(idempotency_key, str)
        or not 1 <= len(idempotency_key) <= 128
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Проверьте параметры повтора рассылки",
        )
    try:
        result = await _factory(request).run_write_async(
            lambda connection: retry_failed_classroom_delivery(
                connection,
                batch_public_id=batch_public_id,
                expected_batch_version=version,
                actor_user_id=actor_user_id,
                idempotency_key=idempotency_key,
                now=_now(),
            )
        )
    except (
        ClassroomDeliveryNotFound,
        ClassroomDeliveryConflict,
        InvalidClassroomDelivery,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError("unreachable")

    sender = request.app.get(PWA_CLASSROOM_TELEGRAM_SENDER)
    if sender is not None and result["batch"]["state"] == "queued":
        result = await deliver_classroom_telegram_batch(
            _factory(request),
            batch_public_id=batch_public_id,
            sender=sender,
            now=_now,
        )
    return web.json_response(
        {
            "schemaVersion": 1,
            "batch": _batch_payload(result),
            "requestId": request["request_id"],
        }
    )


@classroom_delivery_routes.get(
    "/staff/api/v1/classroom-assignment-delivery-batches/{batch_public_id}"
)
async def get_classroom_delivery_batch(request: web.Request) -> web.Response:
    _admin_user_id(request)
    batch_public_id = _public_id(request, "batch_public_id")
    try:
        result = await _factory(request).run_read_async(
            lambda connection: read_classroom_delivery_batch(
                connection, batch_public_id
            )
        )
    except ClassroomDeliveryNotFound as error:
        _raise_domain_error(error)
        raise AssertionError("unreachable")
    return web.json_response(
        {
            "schemaVersion": 1,
            "batch": _batch_payload(result),
            "requestId": request["request_id"],
        }
    )


__all__ = ["PWA_CLASSROOM_TELEGRAM_SENDER", "classroom_delivery_routes"]
