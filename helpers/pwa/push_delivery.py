"""Concrete notification-event to Web Push delivery workflow."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from db_methods.pwa.connection import PwaConnectionFactory
from db_methods.pwa.notification_deliveries import (
    claim_deliveries,
    finish_delivery,
    insert_delivery,
    list_due_candidates,
    suppress_unavailable,
)
from db_methods.pwa.push_subscriptions import delete_subscription_by_id
from helpers.pwa.web_push import WebPushTransportError


PushSender = Callable[[dict[str, object], dict[str, object]], Awaitable[None]]
RETRY_DELAYS_SECONDS = (60, 300, 1_800, 7_200)
PUSH_COPY = {
    "lesson_published": (
        "Опубликован новый урок",
        "В кабинете появились новые условия.",
    ),
    "hint_published": ("Опубликована подсказка", "Подсказки уже доступны в кабинете."),
    "solution_published": ("Опубликованы решения", "Решения занятия уже доступны."),
    "review_completed": (
        "Проверка завершена",
        "Откройте кабинет, чтобы увидеть результат.",
    ),
    "thread_updated": ("Новое сообщение", "В обсуждении решения появился ответ."),
    "oral_window": ("Открыт устный приём", "Можно подключиться к устной сдаче."),
    "classroom_assignment": (
        "Назначена аудитория",
        "Аудитория опубликована в кабинете.",
    ),
    "deadline": ("Скоро дедлайн", "Проверьте срок сдачи задач."),
    "news": ("Новая публикация", "В новостях кружка появилась запись."),
    "group_announcement": ("Новое объявление", "В кабинете появилось объявление."),
}


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _preference_enabled(value: object, category: str) -> bool:
    return category != "oral_window" if value is None else bool(value)


def _quiet_now(item: dict[str, object], now: datetime) -> bool:
    timezone = str(item.get("timezone") or "Europe/Moscow")
    starts = str(item.get("quiet_starts_local") or "21:00")
    ends = str(item.get("quiet_ends_local") or "09:00")
    local = now.astimezone(ZoneInfo(timezone))
    minute = local.hour * 60 + local.minute
    start_hour, start_minute = map(int, starts.split(":"))
    end_hour, end_minute = map(int, ends.split(":"))
    start = start_hour * 60 + start_minute
    end = end_hour * 60 + end_minute
    return start <= minute < end if start < end else minute >= start or minute < end


def _payload(item: dict[str, object], now: datetime) -> dict[str, object]:
    category = str(item["category"])
    title, default_body = PUSH_COPY[category]
    values = json.loads(str(item["payload_json"]))
    if not isinstance(values, dict):
        raise ValueError("notification payload must be an object")
    body = default_body
    if category == "classroom_assignment":
        parts = [
            values.get(key) for key in ("courseName", "groupName", "classroomName")
        ]
        names = [str(value) for value in parts if isinstance(value, str) and value]
        if len(names) == 3:
            names[-1] = f"аудитория {names[-1]}"
        if names:
            body = " · ".join(names)
    elif category == "review_completed":
        if values.get("kind") == "family_lesson_digest":
            title = "Итоги занятия готовы"
            lesson_number = values.get("lessonNumber")
            group_name = values.get("groupName")
            if isinstance(lesson_number, int) and isinstance(group_name, str):
                body = f"{group_name} · занятие {lesson_number}. Результаты уже в кабинете."
            else:
                body = "Результаты занятия уже доступны в семейном кабинете."
        else:
            count = values.get("count")
            if isinstance(count, int) and not isinstance(count, bool) and count > 1:
                body = f"Проверено задач: {count}. Результаты уже в кабинете."
    elif category == "group_announcement":
        text = values.get("text")
        if isinstance(text, str) and text.strip():
            body = text.strip()
    audience = str(item["audience"])
    route = str(item["route"])
    if not route.startswith(f"/{audience}/"):
        raise ValueError("notification route escaped its audience")
    sound_enabled = _preference_enabled(item.get("sound_enabled"), category)
    return {
        "schemaVersion": 1,
        "eventId": item["event_public_id"],
        "category": category,
        "title": title,
        "body": body[:500],
        "route": route,
        "silent": not sound_enabled or _quiet_now(item, now),
        "occurredAt": item["occurred_at"],
    }


def _prepare(
    connection,
    *,
    now: datetime,
    claim_token: str,
    limit: int,
) -> list[dict[str, object]]:
    timestamp = _timestamp(now)
    candidates = list_due_candidates(
        connection,
        now=timestamp,
        now_milliseconds=int(now.timestamp() * 1_000),
        limit=limit * 4,
    )
    for candidate in candidates:
        enabled = _preference_enabled(
            candidate["push_enabled"], str(candidate["category"])
        )
        insert_delivery(
            connection,
            event_id=int(candidate["event_id"]),
            subscription_id=int(candidate["subscription_id"]),
            state="pending" if enabled else "suppressed",
            error_code=None if enabled else "preference_disabled",
            now=timestamp,
        )
    suppress_unavailable(connection, now=timestamp)
    return claim_deliveries(
        connection,
        claim_token=claim_token,
        claim_until=_timestamp(now + timedelta(minutes=2)),
        now=timestamp,
        limit=limit,
    )


async def deliver_web_push_once(
    factory: PwaConnectionFactory,
    sender: PushSender,
    *,
    now: datetime | None = None,
    limit: int = 50,
) -> dict[str, int]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    claim_token = uuid.uuid4().hex
    claimed = await factory.run_write_async(
        lambda connection: _prepare(
            connection, now=current, claim_token=claim_token, limit=limit
        )
    )
    result = {
        "claimed": len(claimed),
        "sent": 0,
        "retried": 0,
        "failed": 0,
        "suppressed": 0,
    }

    for item in claimed:
        state = "sent"
        error_code = None
        delivered_at = _timestamp(current)
        next_attempt_at = delivered_at
        try:
            if not _preference_enabled(item["push_enabled"], str(item["category"])):
                state = "suppressed"
                error_code = "preference_disabled"
                delivered_at = None
            else:
                await sender(
                    {
                        "endpoint": item["endpoint"],
                        "keys": {
                            "p256dh": item["p256dh"],
                            "auth": item["auth_secret"],
                        },
                    },
                    _payload(item, current),
                )
        except WebPushTransportError as error:
            delivered_at = None
            error_code = (
                "subscription_gone"
                if error.stale_subscription
                else f"provider_{error.status_code or 'network'}"
            )
            attempt_count = int(item["attempt_count"])
            if error.retryable and attempt_count <= len(RETRY_DELAYS_SECONDS):
                state = "retry"
                next_attempt_at = _timestamp(
                    current + timedelta(seconds=RETRY_DELAYS_SECONDS[attempt_count - 1])
                )
            else:
                state = "failed"
            if error.stale_subscription:
                await factory.run_write_async(
                    lambda connection, subscription_id=int(item["subscription_id"]): (
                        delete_subscription_by_id(
                            connection, subscription_id=subscription_id
                        )
                    )
                )
        except KeyError, TypeError, ValueError, ZoneInfoNotFoundError:
            state = "failed"
            error_code = "invalid_notification"
            delivered_at = None

        await factory.run_write_async(
            lambda connection, delivery_id=int(item["id"]), final_state=state, retry_at=next_attempt_at, delivered=delivered_at, code=error_code: (
                finish_delivery(
                    connection,
                    delivery_id=delivery_id,
                    state=final_state,
                    next_attempt_at=retry_at,
                    delivered_at=delivered,
                    error_code=code,
                    now=_timestamp(current),
                )
            )
        )
        if state == "sent":
            result["sent"] += 1
        elif state == "retry":
            result["retried"] += 1
        elif state == "failed":
            result["failed"] += 1
        elif state == "suppressed":
            result["suppressed"] += 1
    return result


__all__ = ["PushSender", "deliver_web_push_once"]
