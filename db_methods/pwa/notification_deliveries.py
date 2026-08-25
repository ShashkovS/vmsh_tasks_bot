"""Direct SQLite operations for the concrete Web Push outbox."""

from __future__ import annotations

import sqlite3


def list_due_candidates(
    connection: sqlite3.Connection, *, now: str, now_milliseconds: int, limit: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT e.id AS event_id, e.category, e.deliver_after, "
        "s.id AS subscription_id, "
        "coalesce(cp.push_enabled, p.push_enabled) AS push_enabled "
        "FROM notification_events e "
        "JOIN auth_accounts a ON a.id = e.account_id AND a.status = 'active' "
        "JOIN push_subscriptions s ON s.account_id = e.account_id "
        "JOIN auth_sessions ses ON ses.id = s.session_id "
        "AND ses.revoked_at IS NULL AND ses.expires_at > ? "
        "LEFT JOIN notification_preferences p "
        "ON p.account_id = e.account_id AND p.category = e.category "
        "LEFT JOIN courses c ON c.public_id = json_extract(e.payload_json, '$.courseId') "
        "LEFT JOIN notification_course_preferences cp "
        "ON cp.account_id = e.account_id AND cp.course_id = c.id "
        "AND cp.category = e.category "
        "WHERE e.deliver_after <= ? AND e.read_at IS NULL "
        "AND (s.expiration_time IS NULL OR s.expiration_time > ?) "
        "AND NOT EXISTS (SELECT 1 FROM notification_deliveries d "
        "WHERE d.event_id = e.id AND d.subscription_id = s.id) "
        "ORDER BY e.deliver_after, e.id, s.id LIMIT ?",
        (now, now, now_milliseconds, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_delivery(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    subscription_id: int,
    state: str,
    error_code: str | None,
    now: str,
) -> bool:
    cursor = connection.execute(
        "INSERT INTO notification_deliveries "
        "(event_id, subscription_id, state, next_attempt_at, "
        "last_error_code, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(event_id, subscription_id) DO NOTHING",
        (
            event_id,
            subscription_id,
            state,
            now,
            error_code,
            now,
            now,
        ),
    )
    return cursor.rowcount == 1


def suppress_unavailable(connection: sqlite3.Connection, *, now: str) -> int:
    cursor = connection.execute(
        "UPDATE notification_deliveries SET state = 'suppressed', "
        "last_error_code = 'subscription_unavailable', updated_at = ?, "
        "claim_token = NULL, claim_until = NULL "
        "WHERE state IN ('pending', 'retry', 'sending') AND ("
        "EXISTS (SELECT 1 FROM notification_events e "
        "WHERE e.id = notification_deliveries.event_id AND e.read_at IS NOT NULL) "
        "OR NOT EXISTS (SELECT 1 FROM push_subscriptions s "
        "JOIN auth_sessions ses ON ses.id = s.session_id "
        "WHERE s.id = notification_deliveries.subscription_id "
        "AND ses.revoked_at IS NULL AND ses.expires_at > ?))",
        (now, now),
    )
    return cursor.rowcount


def claim_deliveries(
    connection: sqlite3.Connection,
    *,
    claim_token: str,
    claim_until: str,
    now: str,
    limit: int,
) -> list[dict[str, object]]:
    connection.execute(
        "UPDATE notification_deliveries SET state = 'sending', claim_token = ?, "
        "claim_until = ?, attempt_count = attempt_count + 1, updated_at = ? "
        "WHERE id IN (SELECT d.id FROM notification_deliveries d "
        "WHERE ((d.state IN ('pending', 'retry') AND d.next_attempt_at <= ?) "
        "OR (d.state = 'sending' AND d.claim_until < ?)) "
        "ORDER BY d.next_attempt_at, d.id LIMIT ?)",
        (claim_token, claim_until, now, now, now, limit),
    )
    rows = connection.execute(
        "SELECT d.id, d.public_id, d.attempt_count, e.public_id AS event_public_id, "
        "e.category, e.route, e.payload_json, e.occurred_at, a.audience, "
        "s.id AS subscription_id, s.endpoint, s.p256dh, s.auth_secret, "
        "coalesce(cp.push_enabled, p.push_enabled) AS push_enabled, "
        "p.sound_enabled, p.quiet_starts_local, "
        "p.quiet_ends_local, p.timezone "
        "FROM notification_deliveries d "
        "JOIN notification_events e ON e.id = d.event_id "
        "JOIN auth_accounts a ON a.id = e.account_id "
        "JOIN push_subscriptions s ON s.id = d.subscription_id "
        "JOIN auth_sessions ses ON ses.id = s.session_id "
        "LEFT JOIN notification_preferences p "
        "ON p.account_id = e.account_id AND p.category = e.category "
        "LEFT JOIN courses c ON c.public_id = json_extract(e.payload_json, '$.courseId') "
        "LEFT JOIN notification_course_preferences cp "
        "ON cp.account_id = e.account_id AND cp.course_id = c.id "
        "AND cp.category = e.category "
        "WHERE d.claim_token = ? AND ses.revoked_at IS NULL AND ses.expires_at > ? "
        "ORDER BY d.id",
        (claim_token, now),
    ).fetchall()
    return [dict(row) for row in rows]


def finish_delivery(
    connection: sqlite3.Connection,
    *,
    delivery_id: int,
    state: str,
    next_attempt_at: str,
    delivered_at: str | None,
    error_code: str | None,
    now: str,
) -> None:
    connection.execute(
        "UPDATE notification_deliveries SET state = ?, next_attempt_at = ?, "
        "delivered_at = ?, last_error_code = ?, claim_token = NULL, "
        "claim_until = NULL, updated_at = ? WHERE id = ? AND state = 'sending'",
        (
            state,
            next_attempt_at,
            delivered_at,
            error_code,
            now,
            delivery_id,
        ),
    )


__all__ = [
    "claim_deliveries",
    "finish_delivery",
    "insert_delivery",
    "list_due_candidates",
    "suppress_unavailable",
]
