from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import db_methods as db
from apps import zoom_events_parser
from helpers.trace import get_trace_context

from .http_harness import FakeRequest


def _zoom_payload(event: str, *, zoom_id: str = "87196763644", name: str = "Student Zoom", event_ts: int | None = None):
    if event_ts is None:
        event_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "event": event,
        "event_ts": event_ts,
        "payload": {
            "object": {
                "id": zoom_id,
                "participant": {
                    "user_name": name,
                    "user_id": "zoom-user-1",
                },
            }
        },
    }


def test_zoom_validation_handshake_returns_encrypted_token(live_seed_db, monkeypatch):
    monkeypatch.setattr(zoom_events_parser.config, "zoom_secret_token", "secret-token")
    response = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(
            FakeRequest(
                method="POST",
                path="/zoomevents",
                json_data={
                    "event": "endpoint.url_validation",
                    "event_ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "payload": {"plainToken": "plain-token"},
                },
            )
        )
    )

    assert response.status == 200
    body = json.loads(response.text)
    assert body["plainToken"] == "plain-token"
    assert body["encryptedToken"]



def test_zoom_events_ignore_non_circle_meetings(live_seed_db):
    response = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(
            FakeRequest(method="POST", path="/zoomevents", json_data=_zoom_payload("meeting.participant_joined_waiting_room", zoom_id="non-circle-id"))
        )
    )

    assert response.status == 200
    assert db.zoom_queue.get_queue_count() == 0



def test_zoom_events_update_queue_statuses_and_cleanup_old_rows(live_seed_db):
    name = "Student Zoom"

    waiting = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(FakeRequest(method="POST", path="/zoomevents", json_data=_zoom_payload("meeting.participant_joined_waiting_room", name=name)))
    )
    assert waiting.status == 200
    queue_row = db.sql.conn.execute(
        "select * from zoom_queue where zoom_user_name = :name",
        {"name": name},
    ).fetchone()
    assert queue_row is not None
    assert queue_row["status"] == 0

    joined = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(FakeRequest(method="POST", path="/zoomevents", json_data=_zoom_payload("meeting.participant_joined", name=name)))
    )
    assert joined.status == 200
    queue_row = db.sql.conn.execute(
        "select * from zoom_queue where zoom_user_name = :name",
        {"name": name},
    ).fetchone()
    assert queue_row["status"] == 1

    breakout = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(FakeRequest(method="POST", path="/zoomevents", json_data=_zoom_payload("meeting.participant_joined_breakout_room", name=name)))
    )
    assert breakout.status == 200
    assert db.sql.conn.execute(
        "select * from zoom_queue where zoom_user_name = :name",
        {"name": name},
    ).fetchone() is None

    old_ts = (
        datetime.now(timezone.utc).replace(tzinfo=None) + zoom_events_parser.TIMEZONE - timedelta(days=1)
    ).isoformat()
    db.sql.conn.execute(
        "insert into zoom_queue (zoom_user_name, enter_ts, status) values (:name, :enter_ts, 0)",
        {"name": "Old Zoom User", "enter_ts": old_ts},
    )
    db.sql.conn.commit()

    started = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(FakeRequest(method="POST", path="/zoomevents", json_data=_zoom_payload("meeting.started", name="Teacher Zoom")))
    )
    assert started.status == 200
    assert db.sql.conn.execute(
        "select * from zoom_queue where zoom_user_name = 'Old Zoom User'"
    ).fetchone() is None



def test_zoom_events_bad_payload_returns_400_and_trace_context_does_not_leak(live_seed_db):
    ok_response = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(FakeRequest(method="POST", path="/zoomevents", json_data=_zoom_payload("meeting.participant_joined_waiting_room", name="Trace User")))
    )
    assert ok_response.status == 200
    assert get_trace_context() == {}

    bad_response = __import__("asyncio").run(
        zoom_events_parser.post_zoomevents(FakeRequest(method="POST", path="/zoomevents", json_data={"event": "broken"}))
    )
    assert bad_response.status == 400
    assert get_trace_context() == {}
