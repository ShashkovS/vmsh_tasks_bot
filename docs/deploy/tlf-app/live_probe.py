"""Synthetic live deployment checks; credentials are read only on the server.

README.md defines the scope. Leaves three clearly named archive smoke receipts.
No real participant payload, auth token or password enters the report.
"""

import asyncio
import hashlib
import hmac
import json
import sqlite3
import time
from pathlib import Path

import aiohttp

ORIGIN = "https://prep.leaders.tech"
CONFIG = json.loads(Path("creds_prod/vmsh_bot_config_prod.json").read_text())


async def main():
    passed = []
    headers = {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            ORIGIN + "/staff/api/v1/auth/login",
            json={
                "username": "admin",
                "password": CONFIG["first_admin_password"],
                "deviceLabel": "Deployment smoke",
            },
            headers=headers,
        )
        assert response.status == 200, f"admin login HTTP {response.status}"
        assert all(
            "Secure" in c and "HttpOnly" in c
            for c in response.headers.getall("Set-Cookie")
        )
        passed.append("admin login and secure cookies")
        response = await session.get(ORIGIN + "/staff/api/v1/auth/me")
        assert response.status == 200
        passed.append("authenticated admin session")
        for audience in ("student", "family", "staff"):
            response = await session.get(ORIGIN + f"/{audience}/api/v1/branding")
            assert response.status == 200
            brand = await response.json()
            assert brand["profileId"] == "tlf-prep-clubs"
        passed.append("TLF branding and English across audiences")
        for audience in ("student", "family"):
            response = await session.get(ORIGIN + f"/{audience}/manifest.webmanifest")
            manifest = await response.json()
            assert manifest["lang"] == "en" and manifest["name"].startswith(
                "TLF Prep Clubs"
            )
            for icon in manifest["icons"]:
                icon_response = await session.get(ORIGIN + icon["src"])
                assert icon_response.status == 200
        passed.append("branded manifests and public icons")
        response = await session.post(
            ORIGIN + "/staff/api/v1/auth/logout", json={}, headers=headers
        )
        assert response.status == 204
        passed.append("probe session logged out")
        bodies = [
            b'{"event":"deployment.smoke","payload":{"object":{"id":"deployment-smoke-all-meetings"}}}',
            b'{"event":"deployment.smoke.unknown","payload":{"synthetic":true}}',
        ]
        for body in (bodies[0], bodies[1], bodies[0]):
            stamp = str(int(time.time()))
            signature = (
                "v0="
                + hmac.new(
                    CONFIG["zoom_secret_token"].encode(),
                    b"v0:" + stamp.encode() + b":" + body,
                    hashlib.sha256,
                ).hexdigest()
            )
            response = await session.post(
                ORIGIN + "/zoomevents",
                data=body,
                headers={"x-zm-request-timestamp": stamp, "x-zm-signature": signature},
            )
            assert response.status == 200, f"Zoom ingress HTTP {response.status}"
        response = await session.post(ORIGIN + "/zoomevents", data=bodies[0])
        assert response.status == 401
        response = await session.post(
            ORIGIN + "/zoomevents",
            json={
                "event": "endpoint.url_validation",
                "payload": {"plainToken": "deployment-smoke"},
            },
        )
        assert response.status == 200
        crc = await response.json()
        assert (
            crc["encryptedToken"]
            == hmac.new(
                CONFIG["zoom_secret_token"].encode(),
                b"deployment-smoke",
                hashlib.sha256,
            ).hexdigest()
        )
        passed.append("signed Zoom ingress, invalid signature rejection and CRC")
    path = Path(CONFIG["db_filename"]).resolve()
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT raw_body FROM zoom_webhook_receipts "
            "WHERE event_type LIKE 'deployment.smoke%' ORDER BY id"
        ).fetchall()
        assert [row[0] for row in rows][-3:] == [bodies[0], bodies[1], bodies[0]]
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    passed.append("exact bodies, duplicates, unknown meeting and DB integrity")
    print(
        json.dumps({"ok": True, "passed": passed, "zoomSyntheticReceipts": len(rows)})
    )


if __name__ == "__main__":
    asyncio.run(main())
