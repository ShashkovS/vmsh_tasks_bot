"""Fail-closed runtime configuration for PWA authentication.

This module reads only explicitly supplied environment values and a PWA
``Config`` object. It never falls back to Telegram or Google credential files.
See ADR 0003 and ``vmshpwa/docs/runtime-isolation.md``.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias
from urllib.parse import urlsplit

from helpers.config import Config
from models.pwa.auth import (
    DEFAULT_ACCESS_MAX_AGE_SECONDS,
    AccessTokenCodec,
    AuthAudience,
)


Network: TypeAlias = ipaddress.IPv4Network | ipaddress.IPv6Network


class AuthConfigurationError(RuntimeError):
    """Authentication cannot start without an unambiguous safe configuration."""


def _validate_proxy_unix_socket_paths(values: tuple[str, ...]) -> tuple[str, ...]:
    for value in values:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or "\x00" in value
            or not os.path.isabs(value)
            or os.path.normpath(value) != value
        ):
            raise AuthConfigurationError(
                "Trusted proxy Unix socket paths must be exact canonical absolute paths"
            )
    if len(set(values)) != len(values):
        raise AuthConfigurationError("Trusted proxy Unix socket paths must be unique")
    return values


@dataclass(frozen=True, slots=True)
class AudienceCookiePolicy:
    access_name: str
    refresh_name: str
    path: str
    http_only: bool = True
    same_site: str = "Lax"


COOKIE_POLICY = MappingProxyType(
    {
        AuthAudience.STUDENT: AudienceCookiePolicy(
            "vmsh_student_access", "vmsh_student_refresh", "/student"
        ),
        AuthAudience.FAMILY: AudienceCookiePolicy(
            "vmsh_family_access", "vmsh_family_refresh", "/family"
        ),
        AuthAudience.STAFF: AudienceCookiePolicy(
            "vmsh_staff_access", "vmsh_staff_refresh", "/staff"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class AuthRuntimeConfig:
    """Validated secrets and browser boundaries injected into auth services."""

    origins_by_audience: Mapping[AuthAudience, frozenset[str]]
    trusted_proxy_networks: tuple[Network, ...]
    trusted_proxy_hops: int
    access_ttl_seconds: int
    secure_cookies: bool
    signing_keys: tuple[str, ...] = field(repr=False)
    refresh_pepper: bytes = field(repr=False)
    throttle_pepper: bytes = field(repr=False)
    trusted_proxy_unix_socket_paths: tuple[str, ...] = ()
    test_only_defaults: bool = False

    def __post_init__(self) -> None:
        _validate_proxy_unix_socket_paths(self.trusted_proxy_unix_socket_paths)
        if set(self.origins_by_audience) != set(AuthAudience):
            raise AuthConfigurationError("Every PWA audience needs allowed origins")
        if any(not origins for origins in self.origins_by_audience.values()):
            raise AuthConfigurationError("Every PWA audience needs an allowed origin")
        if self.trusted_proxy_hops < 0:
            raise AuthConfigurationError("Trusted proxy hop count must be non-negative")
        if self.trusted_proxy_hops and not (
            self.trusted_proxy_networks or self.trusted_proxy_unix_socket_paths
        ):
            raise AuthConfigurationError(
                "Trusted proxy hops require at least one explicit TCP network "
                "or Unix socket"
            )
        if self.trusted_proxy_hops > 1 and not self.trusted_proxy_networks:
            raise AuthConfigurationError(
                "Multiple trusted proxy hops require explicit proxy networks"
            )
        if self.trusted_proxy_unix_socket_paths and not self.trusted_proxy_hops:
            raise AuthConfigurationError(
                "Trusted Unix proxy sockets require a positive proxy hop count"
            )
        if len(self.refresh_pepper) < 32 or len(self.throttle_pepper) < 32:
            raise AuthConfigurationError(
                "Authentication peppers must be at least 32 bytes"
            )
        # Construction also validates signing-key length and access TTL.
        self.access_codec()

    def access_codec(self) -> AccessTokenCodec:
        return AccessTokenCodec(
            self.signing_keys,
            max_age_seconds=self.access_ttl_seconds,
        )


def _validated_origin(raw_value: str, *, production: bool) -> str:
    value = raw_value.strip()
    parsed = urlsplit(value)
    if (
        not value
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not parsed.hostname
    ):
        raise AuthConfigurationError(
            "PWA public origins must be bare origins without credentials, path or query"
        )
    if production:
        if parsed.scheme != "https":
            raise AuthConfigurationError("Production PWA origins must use HTTPS")
    elif parsed.scheme == "http":
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise AuthConfigurationError("Plain HTTP is allowed only on loopback")
    elif parsed.scheme != "https":
        raise AuthConfigurationError("PWA origins must use HTTP loopback or HTTPS")
    # A trailing slash is not part of an origin and would complicate exact
    # Origin-header comparison. IPv6 brackets/ports are preserved by netloc.
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_origins(
    raw_value: str,
    *,
    production: bool,
) -> Mapping[AuthAudience, frozenset[str]]:
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as error:
        raise AuthConfigurationError(
            "VMSH_PWA_PUBLIC_ORIGINS_JSON must be a JSON object"
        ) from error
    if not isinstance(payload, dict) or set(payload) != {
        audience.value for audience in AuthAudience
    }:
        raise AuthConfigurationError(
            "PWA public-origin JSON must contain student, family and staff"
        )
    parsed: dict[AuthAudience, frozenset[str]] = {}
    for audience in AuthAudience:
        values = payload[audience.value]
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(value, str) for value in values)
        ):
            raise AuthConfigurationError(
                f"PWA {audience.value} origins must be a non-empty string array"
            )
        parsed[audience] = frozenset(
            _validated_origin(value, production=production) for value in values
        )
    return MappingProxyType(parsed)


def _parse_signing_keys(raw_value: str) -> tuple[str, ...]:
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as error:
        raise AuthConfigurationError(
            "VMSH_PWA_AUTH_SIGNING_KEYS_JSON must be a JSON array"
        ) from error
    if (
        not isinstance(payload, list)
        or not payload
        or not all(isinstance(value, str) and value for value in payload)
    ):
        raise AuthConfigurationError(
            "Access signing keys must be a non-empty string array"
        )
    return tuple(payload)


def _decode_pepper(raw_value: str, variable_name: str) -> bytes:
    try:
        decoded = base64.b64decode(raw_value, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as error:
        raise AuthConfigurationError(
            f"{variable_name} must be URL-safe base64"
        ) from error
    if len(decoded) < 32:
        raise AuthConfigurationError(
            f"{variable_name} must decode to at least 32 bytes"
        )
    return decoded


def _parse_proxy_networks(raw_value: str) -> tuple[Network, ...]:
    if not raw_value.strip():
        return ()
    values = [value.strip() for value in raw_value.split(",") if value.strip()]
    try:
        return tuple(ipaddress.ip_network(value, strict=True) for value in values)
    except ValueError as error:
        raise AuthConfigurationError(
            "VMSH_PWA_TRUSTED_PROXY_CIDRS contains an invalid canonical CIDR"
        ) from error


def _parse_proxy_unix_socket_paths(raw_value: str) -> tuple[str, ...]:
    if not raw_value.strip():
        return ()
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as error:
        raise AuthConfigurationError(
            "VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON must be a JSON array"
        ) from error
    if (
        not isinstance(payload, list)
        or not payload
        or not all(isinstance(value, str) and value for value in payload)
    ):
        raise AuthConfigurationError(
            "Trusted proxy Unix sockets must be a non-empty string array"
        )

    return _validate_proxy_unix_socket_paths(tuple(payload))


def _prototype_origins(runtime_config: Config) -> Mapping[AuthAudience, frozenset[str]]:
    ports = {
        "pwa-human": (5173, 5174, 5175),
        "pwa-agent": (5273, 5274, 5275),
        # Production-like browser tests use one gateway origin for all apps.
        "pwa-e2e": (5380, 5380, 5380),
    }
    try:
        student, family, staff = ports[runtime_config.runtime_profile]
    except KeyError as error:
        raise AuthConfigurationError(
            "Test-only auth defaults are limited to known PWA profiles"
        ) from error
    return MappingProxyType(
        {
            AuthAudience.STUDENT: frozenset({f"http://127.0.0.1:{student}"}),
            AuthAudience.FAMILY: frozenset({f"http://127.0.0.1:{family}"}),
            AuthAudience.STAFF: frozenset({f"http://127.0.0.1:{staff}"}),
        }
    )


def _prototype_secret(runtime_config: Config, purpose: str) -> bytes:
    # These values isolate repeatable local profiles; they are not random and
    # therefore must never cross the explicit prototype boundary below.
    material = (
        f"vmsh-pwa-test-only-v1:{purpose}:{runtime_config.runtime_profile}:"
        f"{runtime_config.pwa_instance}"
    ).encode("utf-8")
    return hashlib.sha256(material).digest()


def load_auth_runtime_config(
    runtime_config: Config,
    environment: Mapping[str, str] | None = None,
) -> AuthRuntimeConfig:
    """Build auth configuration without consulting legacy credential loaders."""

    env = os.environ if environment is None else environment
    prototype = runtime_config.pwa_prototype
    if runtime_config.production_mode and prototype:
        raise AuthConfigurationError("Production cannot enable test-only auth defaults")

    raw_origins = env.get("VMSH_PWA_PUBLIC_ORIGINS_JSON", "")
    raw_keys = env.get("VMSH_PWA_AUTH_SIGNING_KEYS_JSON", "")
    raw_refresh_pepper = env.get("VMSH_PWA_REFRESH_PEPPER_B64", "")
    raw_throttle_pepper = env.get("VMSH_PWA_THROTTLE_PEPPER_B64", "")
    security_values = (
        raw_origins,
        raw_keys,
        raw_refresh_pepper,
        raw_throttle_pepper,
    )
    supplied_security_values = all(security_values)
    if any(security_values) and not supplied_security_values:
        # Mixing one real-looking value with deterministic prototype defaults
        # would produce a configuration that appears secure but is not.
        raise AuthConfigurationError(
            "Non-prototype PWA auth requires origins, signing keys and both peppers"
        )

    if prototype and not supplied_security_values:
        origins = _prototype_origins(runtime_config)
        signing_keys = (_prototype_secret(runtime_config, "access").hex(),)
        refresh_pepper = _prototype_secret(runtime_config, "refresh")
        throttle_pepper = _prototype_secret(runtime_config, "throttle")
        test_only_defaults = True
    else:
        if not supplied_security_values:
            raise AuthConfigurationError(
                "Non-prototype PWA auth requires origins, signing keys and both peppers"
            )
        origins = _parse_origins(raw_origins, production=runtime_config.production_mode)
        signing_keys = _parse_signing_keys(raw_keys)
        refresh_pepper = _decode_pepper(
            raw_refresh_pepper, "VMSH_PWA_REFRESH_PEPPER_B64"
        )
        throttle_pepper = _decode_pepper(
            raw_throttle_pepper, "VMSH_PWA_THROTTLE_PEPPER_B64"
        )
        test_only_defaults = False

    raw_ttl = env.get(
        "VMSH_PWA_ACCESS_TTL_SECONDS", str(DEFAULT_ACCESS_MAX_AGE_SECONDS)
    )
    try:
        access_ttl_seconds = int(raw_ttl)
    except ValueError as error:
        raise AuthConfigurationError("PWA access TTL must be an integer") from error
    try:
        trusted_proxy_hops = int(env.get("VMSH_PWA_TRUSTED_PROXY_HOPS", "0"))
    except ValueError as error:
        raise AuthConfigurationError(
            "Trusted proxy hop count must be an integer"
        ) from error

    return AuthRuntimeConfig(
        origins_by_audience=origins,
        trusted_proxy_networks=_parse_proxy_networks(
            env.get("VMSH_PWA_TRUSTED_PROXY_CIDRS", "")
        ),
        trusted_proxy_hops=trusted_proxy_hops,
        access_ttl_seconds=access_ttl_seconds,
        secure_cookies=runtime_config.production_mode,
        signing_keys=signing_keys,
        refresh_pepper=refresh_pepper,
        throttle_pepper=throttle_pepper,
        trusted_proxy_unix_socket_paths=_parse_proxy_unix_socket_paths(
            env.get("VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON", "")
        ),
        test_only_defaults=test_only_defaults,
    )


__all__ = [
    "COOKIE_POLICY",
    "AudienceCookiePolicy",
    "AuthConfigurationError",
    "AuthRuntimeConfig",
    "load_auth_runtime_config",
]
