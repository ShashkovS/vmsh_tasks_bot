"""Phase-8 proof for the 30-minute completed-review notification batch."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from models.pwa.review_notifications import record_review_notifications
from pwa_tests.integration.test_phase8_notification_core import (
    ACCOUNT_PUBLIC_ID,
    _apply,
    _migrations,
    _seed_account,
)


FIRST_REVIEW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def test_reviews_share_one_batch_for_thirty_minutes(tmp_path):
    database_path = tmp_path / "review-notifications.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _account_id, session_id = _seed_account(connection)

        assert (
            record_review_notifications(
                connection,
                account_public_ids=(ACCOUNT_PUBLIC_ID,),
                review_public_id="review-one",
                problem_public_ids=("problem-one",),
                completed_at=FIRST_REVIEW,
            )
            == 1
        )
        connection.execute(
            "UPDATE notification_events SET read_at = ?, read_by_session_id = ?",
            (_timestamp(FIRST_REVIEW + timedelta(minutes=1)), session_id),
        )
        assert (
            record_review_notifications(
                connection,
                account_public_ids=(ACCOUNT_PUBLIC_ID,),
                review_public_id="review-two",
                problem_public_ids=("problem-two", "problem-one"),
                completed_at=FIRST_REVIEW + timedelta(minutes=29),
            )
            == 0
        )
        # Repeating the same committed review must not inflate the batch.
        record_review_notifications(
            connection,
            account_public_ids=(ACCOUNT_PUBLIC_ID,),
            review_public_id="review-two",
            problem_public_ids=("problem-two",),
            completed_at=FIRST_REVIEW + timedelta(minutes=29),
        )

        row = connection.execute(
            "SELECT route, payload_json, occurred_at, deliver_after "
            "FROM notification_events"
        ).fetchone()
        assert row["route"] == "/student/notifications"
        assert (
            connection.execute("SELECT read_at FROM notification_events").fetchone()[
                "read_at"
            ]
            is None
        )
        assert json.loads(row["payload_json"]) == {
            "count": 2,
            "reviewIds": ["review-one", "review-two"],
            "problemIds": ["problem-one", "problem-two"],
        }
        assert row["occurred_at"] == _timestamp(FIRST_REVIEW + timedelta(minutes=29))
        assert row["deliver_after"] == _timestamp(FIRST_REVIEW + timedelta(minutes=30))


def test_review_after_batch_window_starts_a_new_event(tmp_path):
    database_path = tmp_path / "review-notifications-window.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_account(connection)

        for review_id, offset in (("review-one", 0), ("review-two", 30)):
            record_review_notifications(
                connection,
                account_public_ids=(ACCOUNT_PUBLIC_ID,),
                review_public_id=review_id,
                problem_public_ids=(f"problem-{review_id}",),
                completed_at=FIRST_REVIEW + timedelta(minutes=offset),
            )

        rows = connection.execute(
            "SELECT payload_json, deliver_after FROM notification_events ORDER BY id"
        ).fetchall()
        assert len(rows) == 2
        assert [json.loads(row["payload_json"])["count"] for row in rows] == [1, 1]
        assert rows[0]["deliver_after"] == _timestamp(
            FIRST_REVIEW + timedelta(minutes=30)
        )
        assert rows[1]["deliver_after"] == _timestamp(
            FIRST_REVIEW + timedelta(minutes=60)
        )


def test_review_notifications_ignore_family_and_inactive_accounts(tmp_path):
    database_path = tmp_path / "review-notifications-scope.sqlite3"
    _apply(database_path, {item.id for item in _migrations()})
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _seed_account(connection)
        connection.execute(
            "UPDATE auth_accounts SET status = 'blocked' "
            "WHERE public_id = ?",
            (ACCOUNT_PUBLIC_ID,),
        )

        created = record_review_notifications(
            connection,
            account_public_ids=(ACCOUNT_PUBLIC_ID, "missing-account"),
            review_public_id="review-one",
            problem_public_ids=("problem-one",),
            completed_at=FIRST_REVIEW,
        )
        assert created == 0
        assert (
            connection.execute("SELECT count(*) FROM notification_events").fetchone()[0]
            == 0
        )
