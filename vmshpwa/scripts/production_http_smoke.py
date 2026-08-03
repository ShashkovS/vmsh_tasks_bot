"""Read-only smoke for an already deployed public PWA release."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, TypeAlias
from urllib.parse import urlsplit

import aiohttp

from helpers.pwa.api_contracts import AUDIENCE_BOUNDARIES, RUNTIME_CONTRACT_VERSION


AUDIENCES = ("student", "family", "staff")
PWA_AUDIENCES = ("student", "family")
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PUBLIC_HOST = re.compile(
    r"(?=.{4,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
Response: TypeAlias = tuple[int, dict[str, str], bytes]


class ProductionSmokeFailure(RuntimeError):
    """A deployed response did not satisfy the production boundary."""


def validate_public_origin(value: str) -> str:
    """Return the canonical HTTPS origin or reject an ambiguous target."""

    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.hostname is None
        or PUBLIC_HOST.fullmatch(parsed.hostname) is None
        # urlsplit normalizes hostname to lowercase; compare netloc too so a
        # mixed-case operator typo is not silently accepted as another target.
        or parsed.netloc != parsed.hostname
    ):
        raise ValueError(
            "public origin must be an exact https:// lowercase ASCII FQDN "
            "without credentials, port, path, query or fragment"
        )
    return f"https://{parsed.hostname}"


def _require(condition: bool, label: str, message: str) -> None:
    if not condition:
        raise ProductionSmokeFailure(f"{label}: {message}")


async def _read_response(
    session: aiohttp.ClientSession,
    origin: str,
    path: str,
    *,
    label: str,
    headers: Mapping[str, str] | None = None,
    expected_status: int = 200,
) -> Response:
    async with session.get(
        f"{origin}{path}", headers=headers, allow_redirects=False
    ) as response:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.content.iter_chunked(64 * 1024):
            size += len(chunk)
            _require(
                size <= MAX_RESPONSE_BYTES,
                label,
                f"response exceeds {MAX_RESPONSE_BYTES} bytes",
            )
            chunks.append(chunk)
        _require(
            response.status == expected_status,
            label,
            f"expected HTTP {expected_status}, got {response.status}",
        )
        normalized_headers = {
            name.casefold(): value for name, value in response.headers.items()
        }
        return response.status, normalized_headers, b"".join(chunks)


def _header(response: Response, name: str) -> str:
    return response[1].get(name.casefold(), "")


def _json(response: Response, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(response[2])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProductionSmokeFailure(f"{label}: response is not valid JSON") from error
    _require(isinstance(payload, dict), label, "JSON root is not an object")
    return payload


def _require_cache(response: Response, label: str, directive: str) -> None:
    directives = {
        item.strip().casefold()
        for item in _header(response, "cache-control").split(",")
    }
    _require(directive in directives, label, f"Cache-Control lacks {directive}")


def _require_security(response: Response, label: str) -> None:
    csp = _header(response, "content-security-policy")
    _require("default-src 'none'" in csp, label, "CSP default-src is not closed")
    _require("frame-ancestors 'none'" in csp, label, "CSP allows framing")
    _require("unsafe-eval" not in csp, label, "CSP contains unsafe-eval")
    required = {
        "strict-transport-security": "max-age=",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "no-referrer",
        "permissions-policy": "geolocation=()",
    }
    for name, fragment in required.items():
        _require(fragment in _header(response, name), label, f"invalid {name}")


async def _check_api(
    session: aiohttp.ClientSession,
    origin: str,
    audience: str,
    expected_instance: str,
) -> list[str]:
    passed: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}

    for kind in ("health", "runtime"):
        label = f"{audience} {kind}"
        request_id = f"production-smoke.{audience}.{kind}"
        response = await _read_response(
            session,
            origin,
            f"/{audience}/api/v1/{kind}",
            label=label,
            headers={"Accept": "application/json", "X-Request-ID": request_id},
        )
        _require_cache(response, label, "no-store")
        _require_security(response, label)
        _require(
            _header(response, "x-request-id") == request_id, label, "wrong request ID"
        )
        _require(
            "application/json" in _header(response, "content-type"), label, "not JSON"
        )
        payloads[kind] = _json(response, label)
        passed.append(label)

    health_id = f"production-smoke.{audience}.health"
    _require(
        payloads["health"]
        == {"ok": True, "audience": audience, "requestId": health_id},
        f"{audience} health",
        "payload does not match the audience contract",
    )

    label = f"{audience} runtime"
    runtime = payloads["runtime"]
    _require(
        runtime.get("contractVersion") == RUNTIME_CONTRACT_VERSION,
        label,
        "wrong version",
    )
    _require(runtime.get("audience") == audience, label, "wrong audience")
    _require(runtime.get("instance") == expected_instance, label, "wrong instance")
    for name, expected in AUDIENCE_BOUNDARIES[audience].items():
        _require(runtime.get(name) == expected, label, f"wrong {name}")
    features = runtime.get("features")
    _require(isinstance(features, dict), label, "features is not an object")
    _require(features.get("prototype") is False, label, "prototype is enabled")
    _require(features.get("google") is False, label, "Google is loaded")
    _require(features.get("nats") is True, label, "NATS is not ready")
    _require(
        isinstance(features.get("telegram"), bool), label, "Telegram is not boolean"
    )
    server_time = runtime.get("serverTime")
    _require(isinstance(server_time, str), label, "serverTime is missing")
    try:
        parsed_time = datetime.fromisoformat(server_time.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProductionSmokeFailure(f"{label}: serverTime is not ISO-8601") from error
    _require(parsed_time.tzinfo is not None, label, "serverTime has no timezone")

    label = f"{audience} missing API"
    request_id = f"production-smoke.{audience}.missing"
    response = await _read_response(
        session,
        origin,
        f"/{audience}/api/v1/production-smoke-missing",
        label=label,
        headers={"Accept": "text/html", "X-Request-ID": request_id},
        expected_status=404,
    )
    _require_cache(response, label, "no-store")
    _require(
        "application/json" in _header(response, "content-type"),
        label,
        "SPA swallowed API",
    )
    error = _json(response, label).get("error")
    _require(isinstance(error, dict), label, "error envelope is missing")
    _require(error.get("requestId") == request_id, label, "wrong request ID")
    passed.append(label)
    return passed


async def _check_static(
    session: aiohttp.ClientSession, origin: str, audience: str
) -> list[str]:
    label = f"{audience} SPA fallback"
    response = await _read_response(
        session,
        origin,
        f"/{audience}/production-smoke/deep-link",
        label=label,
        headers={"Accept": "text/html"},
    )
    _require_security(response, label)
    _require_cache(response, label, "no-cache")
    _require("text/html" in _header(response, "content-type"), label, "not HTML")
    html = response[2].decode("utf-8")
    _require('<div id="root"></div>' in html, label, "application root is missing")
    manifest_href = f'href="/{audience}/manifest.webmanifest"'
    if audience not in PWA_AUDIENCES:
        _require('rel="manifest"' not in html, label, "Staff has a PWA manifest")
        return [label]
    _require(manifest_href in html, label, "PWA manifest link is missing")

    manifest_label = f"{audience} manifest"
    manifest_response = await _read_response(
        session,
        origin,
        f"/{audience}/manifest.webmanifest",
        label=manifest_label,
    )
    _require_security(manifest_response, manifest_label)
    _require(
        "application/manifest+json" in _header(manifest_response, "content-type"),
        manifest_label,
        "wrong Content-Type",
    )
    manifest = _json(manifest_response, manifest_label)
    root = f"/{audience}/"
    for name in ("id", "start_url", "scope"):
        _require(manifest.get(name) == root, manifest_label, f"wrong {name}")
    _require(manifest.get("display") == "standalone", manifest_label, "wrong display")
    icons = manifest.get("icons")
    _require(
        isinstance(icons, list) and bool(icons), manifest_label, "icons are missing"
    )

    passed = [label, manifest_label]
    for position, icon in enumerate(icons):
        icon_label = f"{audience} icon {position + 1}"
        _require(isinstance(icon, dict), icon_label, "descriptor is not an object")
        source, media_type = icon.get("src"), icon.get("type")
        _require(
            isinstance(source, str) and source.startswith(root),
            icon_label,
            "icon escapes audience scope",
        )
        _require(
            isinstance(media_type, str) and bool(media_type),
            icon_label,
            "type is missing",
        )
        icon_response = await _read_response(session, origin, source, label=icon_label)
        _require_security(icon_response, icon_label)
        _require(bool(icon_response[2]), icon_label, "body is empty")
        _require(
            media_type in _header(icon_response, "content-type"),
            icon_label,
            "wrong type",
        )
        passed.append(icon_label)

    worker_label = f"{audience} service worker"
    worker = await _read_response(
        session, origin, f"/{audience}/sw.js", label=worker_label
    )
    _require_security(worker, worker_label)
    _require_cache(worker, worker_label, "no-store")
    _require(
        _header(worker, "service-worker-allowed") == root,
        worker_label,
        "wrong scope",
    )
    _require(bool(worker[2]), worker_label, "body is empty")
    _require(
        "javascript" in _header(worker, "content-type"), worker_label, "not JavaScript"
    )
    passed.append(worker_label)
    return passed


async def check_deployed_release(origin: str, expected_instance: str) -> list[str]:
    """Check one already validated origin without sending credentials or writes."""

    timeout = aiohttp.ClientTimeout(total=10, connect=5)
    async with aiohttp.ClientSession(
        timeout=timeout, headers={"User-Agent": "vmshpwa-production-smoke/1"}
    ) as session:
        passed: list[str] = []
        for audience in AUDIENCES:
            passed.extend(
                await _check_api(session, origin, audience, expected_instance)
            )
            passed.extend(await _check_static(session, origin, audience))
        return passed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin", default=os.environ.get("VMSH_PWA_PUBLIC_ORIGIN", "")
    )
    parser.add_argument(
        "--expected-instance", default=os.environ.get("VMSH_PWA_EXPECTED_INSTANCE", "")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        origin = validate_public_origin(arguments.origin)
        if not arguments.expected_instance:
            raise ValueError("expected runtime instance is required")
        passed = asyncio.run(
            check_deployed_release(origin, arguments.expected_instance)
        )
    except (
        ValueError,
        ProductionSmokeFailure,
        aiohttp.ClientError,
        TimeoutError,
    ) as error:
        print(f"FAILED: {error}")
        return 1
    print(
        f"PASS: {len(passed)} read-only checks accepted {origin} as {arguments.expected_instance}."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through tests
    raise SystemExit(main())
