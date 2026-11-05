"""Pure HTTP request-boundary and browser-CSRF decisions for the PWA API.

The aiohttp middleware is deliberately kept out of this module: callers pass
the transport facts and raw headers, then map the returned stable failure to an
HTTP response.  In particular, no request origin is inferred from an arbitrary
``Host`` or forwarding header.  A candidate becomes authoritative only after
it exactly matches an origin from :class:`~helpers.pwa.auth_config.AuthRuntimeConfig`.

Governing decisions: ADR 0003 and Phase 1 in
``vmshpwa/dev/development-plan/05-phase-1-auth.md``.  The conservative proxy
chain order follows RFC 7239/aiohttp's documented ``Request.forwarded`` order:
the client-facing proxy contributes the first element and the application-
facing proxy contributes the last one.
"""

from __future__ import annotations

import ipaddress
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Protocol, TypeAlias
from urllib.parse import urlsplit

from models.pwa.auth import AuthAudience


IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork: TypeAlias = ipaddress.IPv4Network | ipaddress.IPv6Network
HeaderInput: TypeAlias = Mapping[str, str] | Iterable[tuple[str, str]]

# OWASP's browser-CSRF safe-method set intentionally excludes TRACE. The PWA
# adapter does not expose TRACE routes, and treating an unexpected TRACE as an
# unsafe request keeps future routing changes fail-closed.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_MEDIA_TYPE = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_FETCH_SITES = frozenset({"cross-site", "same-origin", "same-site", "none"})
_FORWARDED_NAMES = frozenset(
    {"forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto"}
)


class RequestSecurityConfig(Protocol):
    """Structural subset of ``AuthRuntimeConfig`` required by this policy."""

    origins_by_audience: Mapping[AuthAudience, frozenset[str]]
    trusted_proxy_networks: Sequence[IPNetwork]
    trusted_proxy_hops: int
    trusted_proxy_unix_socket_paths: Sequence[str]


class RequestSecurityFailureKind(StrEnum):
    """Stable middleware-level classification, independent from aiohttp."""

    MALFORMED = "malformed"
    FORBIDDEN = "forbidden"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"


@dataclass(frozen=True, slots=True)
class RequestBoundary:
    """Validated external request facts safe for downstream decisions."""

    external_origin: str
    client_address: str
    proxy_hops: int

    @property
    def via_trusted_proxy(self) -> bool:
        return self.proxy_hops > 0


@dataclass(frozen=True, slots=True)
class RequestSecurityFailure:
    """A secret-free rejection that middleware can map without string parsing."""

    kind: RequestSecurityFailureKind
    code: str
    http_status: int


@dataclass(frozen=True, slots=True)
class RequestSecurityDecision:
    """Result of the complete target, CSRF, Fetch Metadata and JSON policy."""

    boundary: RequestBoundary | None = None
    failure: RequestSecurityFailure | None = None

    def __post_init__(self) -> None:
        if (self.boundary is None) == (self.failure is None):
            raise ValueError("A security decision must allow or reject, never both")

    @property
    def allowed(self) -> bool:
        return self.boundary is not None


class _RejectedRequest(Exception):
    def __init__(
        self,
        kind: RequestSecurityFailureKind,
        code: str,
        http_status: HTTPStatus,
    ) -> None:
        super().__init__(code)
        self.failure = RequestSecurityFailure(kind, code, int(http_status))


def _malformed(code: str) -> _RejectedRequest:
    return _RejectedRequest(
        RequestSecurityFailureKind.MALFORMED,
        code,
        HTTPStatus.BAD_REQUEST,
    )


def _forbidden(code: str) -> _RejectedRequest:
    return _RejectedRequest(
        RequestSecurityFailureKind.FORBIDDEN,
        code,
        HTTPStatus.FORBIDDEN,
    )


def _unsupported_media_type(code: str) -> _RejectedRequest:
    return _RejectedRequest(
        RequestSecurityFailureKind.UNSUPPORTED_MEDIA_TYPE,
        code,
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    )


class _Headers:
    """Small case-insensitive multi-value view over aiohttp-compatible headers."""

    def __init__(self, source: HeaderInput) -> None:
        items = source.items() if hasattr(source, "items") else source
        values: defaultdict[str, list[str]] = defaultdict(list)
        for name, value in items:
            if not isinstance(name, str) or not isinstance(value, str):
                raise _malformed("invalid_header_value")
            values[name.casefold()].append(value)
        self._values = dict(values)

    def values(self, name: str) -> tuple[str, ...]:
        return tuple(self._values.get(name.casefold(), ()))

    def single(self, name: str) -> str | None:
        values = self.values(name)
        if len(values) > 1:
            raise _malformed(f"duplicate_{name.casefold().replace('-', '_')}")
        return values[0] if values else None

    @property
    def forwarding_names(self) -> frozenset[str]:
        return frozenset(
            name
            for name in self._values
            if name == "forwarded" or name.startswith("x-forwarded-")
        )


def _split_quoted(value: str, separator: str) -> list[str]:
    """Split a structured header without treating quoted separators as syntax."""

    parts: list[str] = []
    start = 0
    quoted = False
    escaped = False
    for index, character in enumerate(value):
        if ord(character) < 0x20 and character != "\t":
            raise _malformed("invalid_forwarded_syntax")
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif character == separator and not quoted:
            parts.append(value[start:index].strip())
            start = index + 1
    if quoted or escaped:
        raise _malformed("invalid_forwarded_syntax")
    parts.append(value[start:].strip())
    if any(not part for part in parts):
        raise _malformed("invalid_forwarded_syntax")
    return parts


def _decode_forwarded_value(value: str) -> str:
    if value.startswith('"'):
        if len(value) < 2 or not value.endswith('"'):
            raise _malformed("invalid_forwarded_syntax")
        decoded: list[str] = []
        escaped = False
        for character in value[1:-1]:
            if escaped:
                decoded.append(character)
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"' or ord(character) < 0x20:
                raise _malformed("invalid_forwarded_syntax")
            else:
                decoded.append(character)
        if escaped:
            raise _malformed("invalid_forwarded_syntax")
        return "".join(decoded)
    if _TOKEN.fullmatch(value) is None:
        raise _malformed("invalid_forwarded_syntax")
    return value


def _parse_forwarded(values: Sequence[str]) -> list[dict[str, str]]:
    if not values:
        return []
    elements: list[dict[str, str]] = []
    for raw_header in values:
        for raw_element in _split_quoted(raw_header, ","):
            element: dict[str, str] = {}
            for raw_pair in _split_quoted(raw_element, ";"):
                if "=" not in raw_pair:
                    raise _malformed("invalid_forwarded_syntax")
                raw_name, raw_value = raw_pair.split("=", 1)
                name = raw_name.strip().casefold()
                value = raw_value.strip()
                if _TOKEN.fullmatch(name) is None or not value or name in element:
                    raise _malformed("invalid_forwarded_syntax")
                element[name] = _decode_forwarded_value(value)
            elements.append(element)
    return elements


def _parse_csv(values: Sequence[str], *, code: str) -> list[str]:
    parsed: list[str] = []
    for raw_header in values:
        if any(ord(character) < 0x20 for character in raw_header):
            raise _malformed(code)
        parsed.extend(part.strip() for part in raw_header.split(","))
    if not parsed or any(not part for part in parsed):
        raise _malformed(code)
    return parsed


def _parse_address(value: str, *, code: str) -> IPAddress:
    candidate = value.strip()
    if not candidate or candidate.casefold() == "unknown" or candidate.startswith("_"):
        raise _malformed(code)
    if "%" in candidate:
        # Zone identifiers are link-local transport details, not stable proxy
        # identities and cannot be compared safely with configured CIDRs.
        raise _malformed(code)
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        pass

    if candidate.startswith("["):
        closing = candidate.find("]")
        if closing < 0:
            raise _malformed(code)
        address = candidate[1:closing]
        suffix = candidate[closing + 1 :]
        if suffix and (not suffix.startswith(":") or not suffix[1:].isdigit()):
            raise _malformed(code)
        try:
            return ipaddress.ip_address(address)
        except ValueError as error:
            raise _malformed(code) from error

    address, separator, port = candidate.rpartition(":")
    if separator and port.isdigit():
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            pass
        else:
            if isinstance(parsed, ipaddress.IPv4Address):
                return parsed
    raise _malformed(code)


def _is_trusted(address: IPAddress, networks: Sequence[IPNetwork]) -> bool:
    return any(
        address.version == network.version and address in network
        for network in networks
    )


def _candidate_origin(scheme: str, host: str, *, code: str) -> str:
    normalized_scheme = scheme.strip().casefold()
    normalized_host = host.strip()
    if normalized_scheme not in {"http", "https"} or not normalized_host:
        raise _malformed(code)
    parsed = urlsplit(f"{normalized_scheme}://{normalized_host}")
    try:
        parsed_port = parsed.port
    except ValueError as error:
        raise _malformed(code) from error
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in normalized_host)
    ):
        raise _malformed(code)
    # Accessing ``port`` above validates it even though the exact textual
    # origin (including an explicit port) remains significant to the policy.
    del parsed_port
    return f"{normalized_scheme}://{parsed.netloc}"


def _configured_origin(candidate: str, allowed_origins: frozenset[str]) -> str:
    try:
        # Returning the configured value, rather than the header-derived
        # candidate, makes the provenance of RequestBoundary explicit.
        return next(origin for origin in allowed_origins if origin == candidate)
    except StopIteration as error:
        raise _forbidden("request_origin_not_allowed") from error


def _select_proxy_value(values: list[str], proxy_hops: int, *, code: str) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == proxy_hops:
        return values[0]
    raise _malformed(code)


def _validate_trusted_chain(
    *,
    peer_address: str | None,
    peer_unix_socket_path: str | None,
    forwarded_for: Sequence[str],
    trusted_networks: Sequence[IPNetwork],
    trusted_unix_socket_paths: Sequence[str],
    proxy_hops: int,
) -> IPAddress:
    if peer_address is not None and peer_unix_socket_path is not None:
        raise _malformed("ambiguous_transport_peer")
    if peer_unix_socket_path is not None:
        # AF_UNIX is not trusted merely for being local. The aiohttp adapter
        # supplies the server-side ``sockname`` and the exact canonical path
        # must be allowlisted. Filesystem ownership/mode remains part of the
        # deployment boundary documented in deployment.md.
        if peer_unix_socket_path not in trusted_unix_socket_paths:
            raise _forbidden("untrusted_forwarding_peer")
    else:
        if peer_address is None:
            raise _malformed("peer_address_missing")
        parsed_peer = _parse_address(peer_address, code="invalid_peer_address")
        if not _is_trusted(parsed_peer, trusted_networks):
            raise _forbidden("untrusted_forwarding_peer")
    if len(forwarded_for) != proxy_hops:
        raise _forbidden("unexpected_proxy_chain_length")
    addresses = [
        _parse_address(value, code="invalid_forwarded_address")
        for value in forwarded_for
    ]
    # The immediate peer is the final trusted hop.  Every ``for`` value after
    # the first is another proxy closer to the client; the first is the client.
    if any(not _is_trusted(address, trusted_networks) for address in addresses[1:]):
        raise _forbidden("untrusted_forwarding_chain")
    return addresses[0]


def _resolve_boundary(
    *,
    audience: AuthAudience,
    headers: _Headers,
    peer_address: str | None,
    peer_unix_socket_path: str | None,
    transport_scheme: str,
    request_host: str,
    config: RequestSecurityConfig,
) -> RequestBoundary:
    allowed_origins = config.origins_by_audience[audience]
    forwarding_names = headers.forwarding_names
    unknown_forwarding_names = forwarding_names - _FORWARDED_NAMES
    if unknown_forwarding_names:
        raise _malformed("unsupported_forwarding_header")

    if not forwarding_names:
        if config.trusted_proxy_hops:
            raise _forbidden("trusted_proxy_chain_required")
        if peer_unix_socket_path is not None:
            raise _forbidden("direct_unix_transport_not_allowed")
        if peer_address is None:
            raise _malformed("peer_address_missing")
        peer = _parse_address(peer_address, code="invalid_peer_address")
        candidate = _candidate_origin(
            transport_scheme,
            request_host,
            code="invalid_request_target_origin",
        )
        return RequestBoundary(
            external_origin=_configured_origin(candidate, allowed_origins),
            client_address=str(peer),
            proxy_hops=0,
        )

    if not config.trusted_proxy_hops:
        raise _forbidden("forwarding_headers_not_allowed")

    has_forwarded = bool(headers.values("forwarded"))
    has_x_forwarded = any(
        headers.values(name)
        for name in ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto")
    )
    if has_forwarded and has_x_forwarded:
        raise _malformed("ambiguous_forwarding_headers")

    if has_forwarded:
        elements = _parse_forwarded(headers.values("forwarded"))
        if len(elements) != config.trusted_proxy_hops:
            raise _forbidden("unexpected_proxy_chain_length")
        first = elements[0]
        # This is an explicit reverse-proxy sanitization contract, not a generic
        # RFC 7239 inference: the client-facing trusted hop must record the
        # original external host/proto in the first element. Later elements may
        # describe internal hops and are therefore never used as target origin.
        if "for" not in first or "host" not in first or "proto" not in first:
            raise _malformed("incomplete_forwarded_header")
        if any("for" not in element for element in elements):
            raise _malformed("incomplete_forwarded_header")
        client = _validate_trusted_chain(
            peer_address=peer_address,
            peer_unix_socket_path=peer_unix_socket_path,
            forwarded_for=[element["for"] for element in elements],
            trusted_networks=config.trusted_proxy_networks,
            trusted_unix_socket_paths=config.trusted_proxy_unix_socket_paths,
            proxy_hops=config.trusted_proxy_hops,
        )
        candidate = _candidate_origin(
            first["proto"],
            first["host"],
            code="invalid_forwarded_origin",
        )
    else:
        required = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto")
        if any(not headers.values(name) for name in required):
            raise _malformed("incomplete_x_forwarded_headers")
        forwarded_for = _parse_csv(
            headers.values("x-forwarded-for"),
            code="invalid_x_forwarded_for",
        )
        client = _validate_trusted_chain(
            peer_address=peer_address,
            peer_unix_socket_path=peer_unix_socket_path,
            forwarded_for=forwarded_for,
            trusted_networks=config.trusted_proxy_networks,
            trusted_unix_socket_paths=config.trusted_proxy_unix_socket_paths,
            proxy_hops=config.trusted_proxy_hops,
        )
        host = _select_proxy_value(
            _parse_csv(
                headers.values("x-forwarded-host"),
                code="invalid_x_forwarded_host",
            ),
            config.trusted_proxy_hops,
            code="invalid_x_forwarded_host",
        )
        proto = _select_proxy_value(
            _parse_csv(
                headers.values("x-forwarded-proto"),
                code="invalid_x_forwarded_proto",
            ),
            config.trusted_proxy_hops,
            code="invalid_x_forwarded_proto",
        )
        candidate = _candidate_origin(
            proto,
            host,
            code="invalid_forwarded_origin",
        )

    return RequestBoundary(
        external_origin=_configured_origin(candidate, allowed_origins),
        client_address=str(client),
        proxy_hops=config.trusted_proxy_hops,
    )


def _origin_from_header(raw_origin: str) -> str:
    value = raw_origin.strip()
    if value == "null":
        raise _forbidden("origin_not_allowed")
    parsed = urlsplit(value)
    try:
        parsed_port = parsed.port
    except ValueError as error:
        raise _malformed("invalid_origin_header") from error
    candidate = f"{parsed.scheme}://{parsed.netloc}"
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or candidate != value
    ):
        raise _malformed("invalid_origin_header")
    del parsed_port
    return candidate


def _origin_from_referer(raw_referer: str) -> str:
    value = raw_referer.strip()
    parsed = urlsplit(value)
    try:
        parsed_port = parsed.port
    except ValueError as error:
        raise _malformed("invalid_referer_header") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise _malformed("invalid_referer_header")
    del parsed_port
    return f"{parsed.scheme}://{parsed.netloc}"


def _validate_cookie_request_source(
    headers: _Headers,
    allowed_origins: frozenset[str],
) -> None:
    # Per OWASP's Origin/Referer verification guidance, Referer is a fallback,
    # never an alternative that can override a present but forbidden Origin.
    raw_origin = headers.single("origin")
    if raw_origin is not None:
        source_origin = _origin_from_header(raw_origin)
    else:
        raw_referer = headers.single("referer")
        if raw_referer is None:
            raise _forbidden("request_source_missing")
        source_origin = _origin_from_referer(raw_referer)
    if source_origin not in allowed_origins:
        raise _forbidden("request_source_not_allowed")

    # Fetch Metadata is additional evidence, not a replacement for the source
    # check because older browsers and non-browser clients may omit it.
    fetch_site = headers.single("sec-fetch-site")
    if fetch_site is None:
        return
    normalized_site = fetch_site.strip().casefold()
    if normalized_site not in _FETCH_SITES:
        raise _malformed("invalid_fetch_metadata")
    if normalized_site != "same-origin":
        raise _forbidden("cross_origin_fetch_metadata")


def _validate_json_content_type(headers: _Headers) -> None:
    raw_content_type = headers.single("content-type")
    if raw_content_type is None:
        raise _unsupported_media_type("json_content_type_required")
    parts = [part.strip() for part in raw_content_type.split(";")]
    media_type = parts[0].casefold()
    if not media_type or _MEDIA_TYPE.fullmatch(media_type) is None:
        raise _malformed("invalid_content_type")
    for parameter in parts[1:]:
        if not parameter or "=" not in parameter:
            raise _malformed("invalid_content_type")
        name, value = (item.strip() for item in parameter.split("=", 1))
        if _TOKEN.fullmatch(name) is None or not value:
            raise _malformed("invalid_content_type")
    if media_type != "application/json":
        raise _unsupported_media_type("json_content_type_required")


def evaluate_request_security(
    *,
    audience: AuthAudience,
    method: str,
    headers: HeaderInput,
    peer_address: str | None,
    peer_unix_socket_path: str | None = None,
    transport_scheme: str,
    request_host: str,
    config: RequestSecurityConfig,
    expects_json: bool,
    require_browser_source: bool = False,
) -> RequestSecurityDecision:
    """Evaluate one request without I/O, globals or aiohttp exceptions.

    Every unsafe endpoint under a browser audience—including login before a
    cookie exists—requires same-origin source evidence. Non-browser webhooks
    live outside this middleware and use their own signed request boundary.
    Safe methods still validate the request target/proxy boundary, but normally
    do not require Origin, Referer, Fetch Metadata or a JSON request body.
    WebSocket handshakes are the explicit exception: their HTTP method is GET,
    yet browsers attach cookies and a hostile page can initiate a connection.
    The aiohttp adapter therefore passes ``require_browser_source=True`` for
    every audience WebSocket handshake. See ADR 0003.
    """

    try:
        normalized_headers = _Headers(headers)
        boundary = _resolve_boundary(
            audience=audience,
            headers=normalized_headers,
            peer_address=peer_address,
            peer_unix_socket_path=peer_unix_socket_path,
            transport_scheme=transport_scheme,
            request_host=request_host,
            config=config,
        )
        unsafe = method.strip().upper() not in SAFE_METHODS
        if unsafe or require_browser_source:
            _validate_cookie_request_source(
                normalized_headers,
                frozenset({boundary.external_origin}),
            )
        if unsafe and expects_json:
            _validate_json_content_type(normalized_headers)
    except _RejectedRequest as rejected:
        return RequestSecurityDecision(failure=rejected.failure)
    return RequestSecurityDecision(boundary=boundary)


__all__ = [
    "SAFE_METHODS",
    "HeaderInput",
    "RequestBoundary",
    "RequestSecurityConfig",
    "RequestSecurityDecision",
    "RequestSecurityFailure",
    "RequestSecurityFailureKind",
    "evaluate_request_security",
]
