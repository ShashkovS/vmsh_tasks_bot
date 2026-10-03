"""Durability and signature boundaries from docs/deploy/tlf-app/README.md."""

import hashlib
import hmac
import time
from types import SimpleNamespace

import pytest
from aiohttp import web

from apps.zoom_archive import configure
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from helpers.pwa.app_keys import PWA_DATABASE, RUNTIME_CONFIG, PwaDatabaseState


@pytest.fixture
async def archive(tmp_path, aiohttp_client):
    path = tmp_path / "zoom.sqlite3"
    apply_schema_migrations(path)
    factory = PwaConnectionFactory(path)
    app = web.Application(client_max_size=8 * 1024 * 1024)
    app[RUNTIME_CONFIG] = SimpleNamespace(zoom_secret_token="test-secret")
    app[PWA_DATABASE] = PwaDatabaseState(factory=factory)
    configure(app)

    async def lifecycle(app):
        factory.start_async_workers()
        yield
        await factory.aclose()

    app.cleanup_ctx.append(lifecycle)
    return await aiohttp_client(app), factory, path


def signed(raw, timestamp=None):
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    digest = hmac.new(
        b"test-secret", b"v0:" + stamp.encode() + b":" + raw, hashlib.sha256
    ).hexdigest()
    return {"x-zm-request-timestamp": stamp, "x-zm-signature": "v0=" + digest}


async def test_all_meetings_unknown_events_and_duplicates_survive_restart(archive):
    client, factory, path = archive
    bodies = [
        b'{"event":"meeting.started","payload":{"object":{"id":"new-meeting"}}}',
        b'{ "event": "future.event", "extra": [1,2] }',
    ]
    for raw in (bodies[0], bodies[1], bodies[0]):
        response = await client.post("/zoomevents", data=raw, headers=signed(raw))
        assert response.status == 200
    await client.close()
    reopened = PwaConnectionFactory(path)
    rows = reopened.run_read(
        lambda c: c.execute(
            "SELECT * FROM zoom_webhook_receipts ORDER BY id"
        ).fetchall()
    )
    assert [r["raw_body"] for r in rows] == [bodies[0], bodies[1], bodies[0]]
    assert rows[0]["meeting_id"] == "new-meeting"
    assert rows[1]["event_type"] == "future.event"
    assert rows[1]["meeting_id"] is None


@pytest.mark.parametrize("kind", ["missing", "tampered", "expired"])
async def test_rejects_invalid_signatures_without_archiving(archive, kind):
    client, factory, _ = archive
    raw = b'{"event":"meeting.ended"}'
    headers = (
        {}
        if kind == "missing"
        else signed(raw, int(time.time()) - 600 if kind == "expired" else None)
    )
    if kind == "tampered":
        raw += b" "
    assert (await client.post("/zoomevents", data=raw, headers=headers)).status == 401
    assert (
        factory.run_read(
            lambda c: c.execute(
                "SELECT COUNT(*) n FROM zoom_webhook_receipts"
            ).fetchone()["n"]
        )
        == 0
    )


async def test_crc_and_invalid_json(archive):
    client, _, _ = archive
    response = await client.post(
        "/zoomevents",
        json={
            "event": "endpoint.url_validation",
            "payload": {"plainToken": "challenge"},
        },
    )
    assert response.status == 200
    assert await response.json() == {
        "plainToken": "challenge",
        "encryptedToken": hmac.new(
            b"test-secret", b"challenge", hashlib.sha256
        ).hexdigest(),
    }
    assert (await client.post("/zoomevents", data=b"not-json")).status == 400


async def test_storage_failure_does_not_acknowledge(archive, monkeypatch):
    client, factory, _ = archive

    async def fail(write):
        raise OSError("disk unavailable")

    monkeypatch.setattr(factory, "run_write_async", fail)
    raw = b'{"event":"meeting.started"}'
    response = await client.post("/zoomevents", data=raw, headers=signed(raw))
    assert response.status == 503


async def test_full_synchronous_required(archive):
    _, factory, _ = archive
    assert (
        factory.run_read(
            lambda c: c.execute("PRAGMA synchronous").fetchone()["synchronous"]
        )
        == 2
    )
