"""Opt-in checksum/HEAD/CORS proof in the pinned disposable S3 test contour.

See docs/performance/browser-image-uploads.md. Never changes bucket configuration.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp

from helpers.object_storage import S3ObjectStorage
from helpers.pwa.storage_config import load_storage_config, S3_TEST_RUNTIME_PROFILE
from vmshpwa.scripts.storage_smoke import (
    require_live_opt_in,
    verify_test_bucket_binding,
)


async def probe(run_id, origin):
    require_live_opt_in()
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use an exact browser origin")
    if parsed.scheme == "http" and parsed.hostname != "127.0.0.1":
        raise ValueError("HTTP is limited to the literal loopback test origin")
    config = load_storage_config(
        runtime_profile=S3_TEST_RUNTIME_PROFILE,
        media_root=Path(".runtime/vmshpwa/s3-integration/media"),
        repository_root=Path.cwd(),
        integration_run_id=run_id,
    )
    verify_test_bucket_binding(config)
    storage = S3ObjectStorage(config)
    # Synthetic image-shaped probe bytes are sufficient for transport/checksum proof.
    payload = b"RIFF\x04\x00\x00\x00WEBP"
    digest = hashlib.sha256(payload).hexdigest()
    checksum = base64.b64encode(bytes.fromhex(digest)).decode()
    key = f"image-upload-probe/{uuid.uuid4().hex}.webp"
    report = {
        "runId": run_id,
        "ok": False,
        "deleteAck": "not-attempted",
        "browserProof": "not-run",
    }
    try:
        url = await storage.signed_write_url(
            key, byte_size=len(payload), sha256=digest, expires_in=600
        )
        headers = {
            "Content-Type": "image/webp",
            "x-amz-checksum-sha256": checksum,
            "Origin": origin,
        }
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30), trust_env=False
        ) as client:
            async with client.options(
                url,
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "PUT",
                    "Access-Control-Request-Headers": "content-type,x-amz-checksum-sha256",
                },
                allow_redirects=False,
            ) as response:
                allow_origin = response.headers.get("Access-Control-Allow-Origin")
                methods = (
                    response.headers.get("Access-Control-Allow-Methods", "")
                    .upper()
                    .split(",")
                )
                allowed = {
                    header.strip().lower()
                    for header in response.headers.get(
                        "Access-Control-Allow-Headers", ""
                    ).split(",")
                }
                report["corsPreflight"] = (
                    response.status < 300
                    and allow_origin in {origin, "*"}
                    and any(value.strip() in {"PUT", "*"} for value in methods)
                    and (
                        "*" in allowed
                        or {"content-type", "x-amz-checksum-sha256"} <= allowed
                    )
                )
            # A provider must reject changed bytes even when every signed header matches.
            async with client.put(
                url, data=payload[:-1] + b"X", headers=headers, allow_redirects=False
            ) as response:
                report["badChecksumRejected"] = response.status in {400, 422}
            async with client.put(
                url, data=payload, headers=headers, allow_redirects=False
            ) as response:
                report["put"] = response.status in {200, 201, 204}
                report["corsPut"] = response.headers.get(
                    "Access-Control-Allow-Origin"
                ) in {origin, "*"}
            async with client.put(
                url, data=payload + b"X", headers=headers, allow_redirects=False
            ) as response:
                report["wrongLengthRejected"] = response.status in {400, 403, 422}
        metadata = await storage.head(key)
        report["headChecksum"] = metadata == {
            "byteSize": len(payload),
            "mimeType": "image/webp",
            "checksumSHA256": checksum,
        }
        report["ok"] = all(
            report.get(key) is True
            for key in (
                "corsPreflight",
                "corsPut",
                "put",
                "badChecksumRejected",
                "wrongLengthRejected",
                "headChecksum",
            )
        )
    finally:
        await storage.delete(key)
        report["deleteAck"] = "passed"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(probe(args.run_id, args.origin))
        print(json.dumps(report, sort_keys=True))
        return 0 if report["ok"] else 1
    except Exception as error:
        # SDK/network errors may contain a signed URL; never print message/cause.
        print(json.dumps({"ok": False, "failureType": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
