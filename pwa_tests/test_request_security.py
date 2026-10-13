import ipaddress
from dataclasses import dataclass

import pytest

from helpers.pwa.request_security import (
    RequestSecurityFailureKind,
    evaluate_request_security,
)
from models.pwa.auth import AuthAudience


@dataclass(frozen=True)
class _Config:
    origins_by_audience: dict[AuthAudience, frozenset[str]]
    trusted_proxy_networks: tuple[object, ...] = ()
    trusted_proxy_hops: int = 0
    trusted_proxy_unix_socket_paths: tuple[str, ...] = ()


def _config(
    *,
    origins=("https://student.vmsh.example",),
    networks=(),
    hops=0,
    unix_sockets=(),
):
    return _Config(
        origins_by_audience={
            AuthAudience.STUDENT: frozenset(origins),
            AuthAudience.FAMILY: frozenset({"https://family.vmsh.example"}),
            AuthAudience.STAFF: frozenset({"https://staff.vmsh.example"}),
        },
        trusted_proxy_networks=tuple(
            ipaddress.ip_network(network) for network in networks
        ),
        trusted_proxy_hops=hops,
        trusted_proxy_unix_socket_paths=tuple(unix_sockets),
    )


def _evaluate(
    *,
    method="GET",
    headers=None,
    peer="198.51.100.7",
    unix_socket=None,
    scheme="https",
    host="student.vmsh.example",
    config=None,
    json=False,
    require_source=False,
):
    return evaluate_request_security(
        audience=AuthAudience.STUDENT,
        method=method,
        headers={} if headers is None else headers,
        peer_address=peer,
        peer_unix_socket_path=unix_socket,
        transport_scheme=scheme,
        request_host=host,
        config=_config() if config is None else config,
        expects_json=json,
        require_browser_source=require_source,
    )


def _assert_failure(decision, *, kind, code, status):
    assert not decision.allowed
    assert decision.boundary is None
    assert decision.failure is not None
    assert decision.failure.kind is kind
    assert decision.failure.code == code
    assert decision.failure.http_status == status


@pytest.mark.parametrize("method", ["GET", "head", "OPTIONS"])
def test_safe_direct_methods_do_not_require_browser_source_headers(method):
    decision = _evaluate(
        method=method,
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
    )

    assert decision.allowed
    assert decision.boundary is not None
    assert decision.boundary.external_origin == "https://student.vmsh.example"
    assert decision.boundary.client_address == "198.51.100.7"
    assert not decision.boundary.via_trusted_proxy


def test_trace_is_not_treated_as_a_browser_safe_method():
    _assert_failure(
        _evaluate(method="TRACE"),
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_source_missing",
        status=403,
    )


def test_websocket_get_requires_exact_browser_origin():
    missing = _evaluate(require_source=True)
    cross_origin = _evaluate(
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
        require_source=True,
    )
    allowed = _evaluate(
        headers={
            "Origin": "https://student.vmsh.example",
            "Sec-Fetch-Site": "same-origin",
        },
        require_source=True,
    )

    _assert_failure(
        missing,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_source_missing",
        status=403,
    )
    _assert_failure(
        cross_origin,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_source_not_allowed",
        status=403,
    )
    assert allowed.allowed


def test_direct_ipv6_target_and_client_are_preserved_canonically():
    decision = _evaluate(
        peer="2001:db8::17",
        host="[2001:db8::179]:8443",
        config=_config(origins=("https://[2001:db8::179]:8443",)),
    )

    assert decision.allowed
    assert decision.boundary is not None
    assert decision.boundary.external_origin == "https://[2001:db8::179]:8443"
    assert decision.boundary.client_address == "2001:db8::17"


@pytest.mark.parametrize(
    "peer, code",
    [
        (None, "peer_address_missing"),
        ("not-an-address", "invalid_peer_address"),
        ("fe80::1%en0", "invalid_peer_address"),
    ],
)
def test_missing_or_ambiguous_direct_peer_is_malformed(peer, code):
    _assert_failure(
        _evaluate(peer=peer),
        kind=RequestSecurityFailureKind.MALFORMED,
        code=code,
        status=400,
    )


def test_direct_target_must_exactly_match_one_configured_origin():
    _assert_failure(
        _evaluate(host="student.vmsh.example:443"),
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_origin_not_allowed",
        status=403,
    )


def test_direct_target_with_malformed_host_is_not_used_as_an_origin():
    _assert_failure(
        _evaluate(host="student.vmsh.example/path"),
        kind=RequestSecurityFailureKind.MALFORMED,
        code="invalid_request_target_origin",
        status=400,
    )


def test_allowed_origin_selects_the_matching_configured_value():
    decision = _evaluate(
        host="student-alt.vmsh.example",
        config=_config(
            origins=(
                "https://student.vmsh.example",
                "https://student-alt.vmsh.example",
            )
        ),
    )

    assert decision.allowed
    assert decision.boundary.external_origin == "https://student-alt.vmsh.example"


def test_cookie_source_must_match_this_target_not_another_configured_origin():
    decision = _evaluate(
        method="POST",
        host="student-alt.vmsh.example",
        headers={"Origin": "https://student.vmsh.example"},
        config=_config(
            origins=(
                "https://student.vmsh.example",
                "https://student-alt.vmsh.example",
            )
        ),
    )

    _assert_failure(
        decision,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_source_not_allowed",
        status=403,
    )


def test_unsafe_cookie_request_accepts_exact_origin_and_json_with_parameters():
    decision = _evaluate(
        method="POST",
        headers={
            "Origin": "https://student.vmsh.example",
            "Sec-Fetch-Site": "same-origin",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json=True,
    )

    assert decision.allowed


def test_exact_referer_origin_is_fallback_only_when_origin_is_absent():
    accepted = _evaluate(
        method="PATCH",
        headers={
            "Referer": "https://student.vmsh.example/tasks/42?tab=answer",
            "Content-Type": "application/json",
        },
        json=True,
    )
    rejected = _evaluate(
        method="PATCH",
        headers={
            "Origin": "https://attacker.example",
            "Referer": "https://student.vmsh.example/tasks/42",
            "Content-Type": "application/json",
        },
        json=True,
    )

    assert accepted.allowed
    _assert_failure(
        rejected,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_source_not_allowed",
        status=403,
    )


@pytest.mark.parametrize(
    "headers, kind, code",
    [
        (
            {"Content-Type": "application/json"},
            RequestSecurityFailureKind.FORBIDDEN,
            "request_source_missing",
        ),
        (
            {
                "Origin": "null",
                "Content-Type": "application/json",
            },
            RequestSecurityFailureKind.FORBIDDEN,
            "origin_not_allowed",
        ),
        (
            {
                "Origin": "https://student.vmsh.example/",
                "Content-Type": "application/json",
            },
            RequestSecurityFailureKind.MALFORMED,
            "invalid_origin_header",
        ),
        (
            {
                "Referer": "https://student.vmsh.example.evil/tasks/42",
                "Content-Type": "application/json",
            },
            RequestSecurityFailureKind.FORBIDDEN,
            "request_source_not_allowed",
        ),
        (
            {
                "Referer": "not a URL",
                "Content-Type": "application/json",
            },
            RequestSecurityFailureKind.MALFORMED,
            "invalid_referer_header",
        ),
        (
            [
                ("Origin", "https://student.vmsh.example"),
                ("origin", "https://student.vmsh.example"),
                ("Content-Type", "application/json"),
            ],
            RequestSecurityFailureKind.MALFORMED,
            "duplicate_origin",
        ),
    ],
)
def test_cookie_source_failures_have_stable_malformed_or_forbidden_kind(
    headers, kind, code
):
    _assert_failure(
        _evaluate(method="POST", headers=headers, json=True),
        kind=kind,
        code=code,
        status=400 if kind is RequestSecurityFailureKind.MALFORMED else 403,
    )


@pytest.mark.parametrize("site", ["cross-site", "same-site", "none"])
def test_fetch_metadata_rejects_non_same_origin_cookie_mutations(site):
    _assert_failure(
        _evaluate(
            method="DELETE",
            headers={
                "Origin": "https://student.vmsh.example",
                "Sec-Fetch-Site": site,
            },
        ),
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="cross_origin_fetch_metadata",
        status=403,
    )


def test_invalid_fetch_metadata_is_malformed_but_missing_header_is_allowed():
    malformed = _evaluate(
        method="POST",
        headers={
            "Origin": "https://student.vmsh.example",
            "Sec-Fetch-Site": "somewhere-else",
        },
    )
    absent = _evaluate(
        method="POST",
        headers={"Origin": "https://student.vmsh.example"},
    )

    _assert_failure(
        malformed,
        kind=RequestSecurityFailureKind.MALFORMED,
        code="invalid_fetch_metadata",
        status=400,
    )
    assert absent.allowed


def test_login_mutation_requires_same_origin_before_a_session_exists():
    missing_source = _evaluate(
        method="POST",
        headers={"Content-Type": "application/json"},
        json=True,
    )
    cross_origin = _evaluate(
        method="POST",
        headers={
            "Origin": "https://attacker.example",
            "Content-Type": "application/json",
        },
        json=True,
    )
    allowed = _evaluate(
        method="POST",
        headers={
            "Origin": "https://student.vmsh.example",
            "Content-Type": "application/json",
        },
        json=True,
    )

    _assert_failure(
        missing_source,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_source_missing",
        status=403,
    )
    _assert_failure(
        cross_origin,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_source_not_allowed",
        status=403,
    )
    assert allowed.allowed


@pytest.mark.parametrize(
    "headers, kind, code, status",
    [
        (
            {"Origin": "https://student.vmsh.example"},
            RequestSecurityFailureKind.UNSUPPORTED_MEDIA_TYPE,
            "json_content_type_required",
            415,
        ),
        (
            {
                "Origin": "https://student.vmsh.example",
                "Content-Type": "text/plain",
            },
            RequestSecurityFailureKind.UNSUPPORTED_MEDIA_TYPE,
            "json_content_type_required",
            415,
        ),
        (
            {
                "Origin": "https://student.vmsh.example",
                "Content-Type": "application/json; charset",
            },
            RequestSecurityFailureKind.MALFORMED,
            "invalid_content_type",
            400,
        ),
        (
            [
                ("Origin", "https://student.vmsh.example"),
                ("Content-Type", "application/json"),
                ("content-type", "application/json"),
            ],
            RequestSecurityFailureKind.MALFORMED,
            "duplicate_content_type",
            400,
        ),
    ],
)
def test_json_media_type_failures_are_distinguished(headers, kind, code, status):
    _assert_failure(
        _evaluate(method="POST", headers=headers, json=True),
        kind=kind,
        code=code,
        status=status,
    )


def test_json_content_type_is_not_required_for_safe_method():
    assert _evaluate(method="GET", json=True).allowed


def test_untrusted_direct_peer_cannot_supply_standard_forwarding_headers():
    decision = _evaluate(
        headers={"Forwarded": "for=203.0.113.9;proto=https;host=student.vmsh.example"}
    )

    _assert_failure(
        decision,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="forwarding_headers_not_allowed",
        status=403,
    )


@pytest.mark.parametrize(
    "header_name",
    [
        "X-Forwarded-For",
        "X-Forwarded-Host",
        "X-Forwarded-Proto",
        "X-Forwarded-Port",
    ],
)
def test_any_unconfigured_forwarding_header_is_rejected(header_name):
    decision = _evaluate(headers={header_name: "spoofed"})

    expected_kind = (
        RequestSecurityFailureKind.MALFORMED
        if header_name == "X-Forwarded-Port"
        else RequestSecurityFailureKind.FORBIDDEN
    )
    expected_code = (
        "unsupported_forwarding_header"
        if header_name == "X-Forwarded-Port"
        else "forwarding_headers_not_allowed"
    )
    _assert_failure(
        decision,
        kind=expected_kind,
        code=expected_code,
        status=400 if expected_kind is RequestSecurityFailureKind.MALFORMED else 403,
    )


def test_configured_proxy_hops_require_forwarding_evidence():
    _assert_failure(
        _evaluate(
            config=_config(networks=("10.0.0.0/8",), hops=1),
            peer="10.0.0.5",
        ),
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="trusted_proxy_chain_required",
        status=403,
    )


def test_one_trusted_standard_proxy_resolves_origin_and_ipv4_client():
    decision = _evaluate(
        headers={"Forwarded": "for=203.0.113.42;proto=https;host=student.vmsh.example"},
        peer="10.0.0.5",
        scheme="http",
        host="127.0.0.1:8280",
        config=_config(networks=("10.0.0.0/8",), hops=1),
    )

    assert decision.allowed
    assert decision.boundary is not None
    assert decision.boundary.external_origin == "https://student.vmsh.example"
    assert decision.boundary.client_address == "203.0.113.42"
    assert decision.boundary.proxy_hops == 1
    assert decision.boundary.via_trusted_proxy


def test_one_trusted_x_forwarded_proxy_resolves_origin_and_ipv6_client():
    decision = _evaluate(
        headers={
            "X-Forwarded-For": "2001:db8::42",
            "X-Forwarded-Host": "student.vmsh.example",
            "X-Forwarded-Proto": "https",
        },
        peer="2001:db8:ffff::5",
        scheme="http",
        host="[::1]:8280",
        config=_config(networks=("2001:db8:ffff::/48",), hops=1),
    )

    assert decision.allowed
    assert decision.boundary is not None
    assert decision.boundary.client_address == "2001:db8::42"


def test_exact_allowlisted_unix_socket_resolves_forwarded_client():
    socket_path = "/run/vmshpwa/vmshpwa.sock"
    decision = _evaluate(
        headers={
            "Forwarded": ('for="2001:db8::42";proto=https;host=student.vmsh.example')
        },
        peer=None,
        unix_socket=socket_path,
        scheme="http",
        host="localhost",
        config=_config(hops=1, unix_sockets=(socket_path,)),
    )

    assert decision.allowed
    assert decision.boundary is not None
    assert decision.boundary.client_address == "2001:db8::42"
    assert decision.boundary.external_origin == "https://student.vmsh.example"


@pytest.mark.parametrize(
    ("peer", "unix_socket", "code", "kind"),
    [
        (
            None,
            "/run/vmshpwa/other.sock",
            "untrusted_forwarding_peer",
            RequestSecurityFailureKind.FORBIDDEN,
        ),
        (
            "127.0.0.1",
            "/run/vmshpwa/vmshpwa.sock",
            "ambiguous_transport_peer",
            RequestSecurityFailureKind.MALFORMED,
        ),
    ],
)
def test_unix_proxy_requires_one_exact_unambiguous_allowlisted_path(
    peer, unix_socket, code, kind
):
    decision = _evaluate(
        headers={
            "Forwarded": ("for=203.0.113.42;proto=https;host=student.vmsh.example")
        },
        peer=peer,
        unix_socket=unix_socket,
        config=_config(
            networks=("127.0.0.1/32",),
            hops=1,
            unix_sockets=("/run/vmshpwa/vmshpwa.sock",),
        ),
    )

    _assert_failure(
        decision,
        kind=kind,
        code=code,
        status=400 if kind is RequestSecurityFailureKind.MALFORMED else 403,
    )


def test_unix_transport_is_not_implicitly_trusted_for_direct_requests():
    decision = _evaluate(peer=None, unix_socket="/run/vmshpwa/vmshpwa.sock")

    _assert_failure(
        decision,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="direct_unix_transport_not_allowed",
        status=403,
    )


def test_standard_forwarded_accepts_quoted_ipv6_with_port():
    decision = _evaluate(
        headers={
            "Forwarded": (
                'for="[2001:db8::42]:4711";proto=https;host=student.vmsh.example'
            )
        },
        peer="2001:db8:ffff::5",
        config=_config(networks=("2001:db8:ffff::/48",), hops=1),
    )

    assert decision.allowed
    assert decision.boundary.client_address == "2001:db8::42"


def test_two_trusted_proxy_hops_validate_right_side_of_standard_chain():
    decision = _evaluate(
        headers={
            "Forwarded": (
                "for=203.0.113.42;proto=https;host=student.vmsh.example, "
                "for=10.0.0.4;proto=http;host=internal-proxy"
            )
        },
        peer="10.0.0.5",
        scheme="http",
        host="127.0.0.1:8280",
        config=_config(networks=("10.0.0.0/8",), hops=2),
    )

    assert decision.allowed
    assert decision.boundary.client_address == "203.0.113.42"
    assert decision.boundary.proxy_hops == 2


def test_two_trusted_proxy_hops_accept_exact_x_forwarded_chains():
    decision = _evaluate(
        headers={
            "X-Forwarded-For": "203.0.113.42, 10.0.0.4",
            "X-Forwarded-Host": "student.vmsh.example, internal-proxy",
            "X-Forwarded-Proto": "https, http",
        },
        peer="10.0.0.5",
        scheme="http",
        host="127.0.0.1:8280",
        config=_config(networks=("10.0.0.0/8",), hops=2),
    )

    assert decision.allowed
    assert decision.boundary.client_address == "203.0.113.42"


@pytest.mark.parametrize(
    "headers, peer, hops, kind, code",
    [
        (
            {"Forwarded": "for=203.0.113.42;proto=https;host=student.vmsh.example"},
            "192.0.2.4",
            1,
            RequestSecurityFailureKind.FORBIDDEN,
            "untrusted_forwarding_peer",
        ),
        (
            {
                "Forwarded": (
                    "for=203.0.113.42;proto=https;host=student.vmsh.example, "
                    "for=192.0.2.4"
                )
            },
            "10.0.0.5",
            2,
            RequestSecurityFailureKind.FORBIDDEN,
            "untrusted_forwarding_chain",
        ),
        (
            {
                "Forwarded": (
                    "for=198.51.100.8;proto=https;host=student.vmsh.example, "
                    "for=203.0.113.42, for=10.0.0.4"
                )
            },
            "10.0.0.5",
            2,
            RequestSecurityFailureKind.FORBIDDEN,
            "unexpected_proxy_chain_length",
        ),
        (
            {
                "Forwarded": "for=203.0.113.42;proto=https;host=student.vmsh.example",
                "X-Forwarded-For": "203.0.113.42",
                "X-Forwarded-Host": "student.vmsh.example",
                "X-Forwarded-Proto": "https",
            },
            "10.0.0.5",
            1,
            RequestSecurityFailureKind.MALFORMED,
            "ambiguous_forwarding_headers",
        ),
        (
            {"X-Forwarded-For": "203.0.113.42"},
            "10.0.0.5",
            1,
            RequestSecurityFailureKind.MALFORMED,
            "incomplete_x_forwarded_headers",
        ),
        (
            {"Forwarded": "for=unknown;proto=https;host=student.vmsh.example"},
            "10.0.0.5",
            1,
            RequestSecurityFailureKind.MALFORMED,
            "invalid_forwarded_address",
        ),
    ],
)
def test_proxy_spoof_mixed_and_malformed_chains_fail_closed(
    headers, peer, hops, kind, code
):
    decision = _evaluate(
        headers=headers,
        peer=peer,
        scheme="http",
        host="127.0.0.1:8280",
        config=_config(networks=("10.0.0.0/8",), hops=hops),
    )

    _assert_failure(
        decision,
        kind=kind,
        code=code,
        status=400 if kind is RequestSecurityFailureKind.MALFORMED else 403,
    )


def test_trusted_proxy_cannot_select_an_unconfigured_public_origin():
    decision = _evaluate(
        headers={"Forwarded": "for=203.0.113.42;proto=https;host=attacker.example"},
        peer="10.0.0.5",
        scheme="http",
        host="127.0.0.1:8280",
        config=_config(networks=("10.0.0.0/8",), hops=1),
    )

    _assert_failure(
        decision,
        kind=RequestSecurityFailureKind.FORBIDDEN,
        code="request_origin_not_allowed",
        status=403,
    )
