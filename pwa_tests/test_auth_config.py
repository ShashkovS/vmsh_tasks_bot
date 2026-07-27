import base64
import json

import pytest

from helpers.config import Config, _setup
from helpers.pwa.auth_config import (
    COOKIE_POLICY,
    AuthConfigurationError,
    AuthRuntimeConfig,
    load_auth_runtime_config,
)
from models.pwa.auth import AuthAudience


def _runtime(**overrides):
    values = {
        "runtime_profile": "pwa-agent",
        "pwa_instance": "agent",
        "pwa_prototype": True,
        "production_mode": False,
    }
    values.update(overrides)
    return Config(**values)


def _encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _explicit_environment(*, secure_origins: bool = True):
    scheme = "https" if secure_origins else "http"
    return {
        "VMSH_PWA_PUBLIC_ORIGINS_JSON": json.dumps(
            {audience.value: [f"{scheme}://vmsh.example"] for audience in AuthAudience}
        ),
        "VMSH_PWA_AUTH_SIGNING_KEYS_JSON": json.dumps(["a" * 32, "b" * 32]),
        "VMSH_PWA_REFRESH_PEPPER_B64": _encoded(b"r" * 32),
        "VMSH_PWA_THROTTLE_PEPPER_B64": _encoded(b"t" * 32),
    }


def test_known_prototype_profiles_get_isolated_test_only_defaults():
    agent = load_auth_runtime_config(_runtime(), {})
    human = load_auth_runtime_config(
        _runtime(runtime_profile="pwa-human", pwa_instance="human"), {}
    )

    assert agent.test_only_defaults
    assert agent.origins_by_audience[AuthAudience.STUDENT] == frozenset(
        {"http://127.0.0.1:5273"}
    )
    assert agent.signing_keys != human.signing_keys
    assert agent.refresh_pepper != human.refresh_pepper
    assert "refresh_pepper" not in repr(agent)
    assert "throttle_pepper" not in repr(agent)
    assert "signing_keys" not in repr(agent)


def test_e2e_uses_one_origin_for_all_audiences():
    config = load_auth_runtime_config(
        _runtime(runtime_profile="pwa-e2e", pwa_instance="e2e"), {}
    )

    assert set(config.origins_by_audience.values()) == {
        frozenset({"http://127.0.0.1:5380"})
    }


def test_production_refuses_prototype_defaults_and_missing_secrets():
    with pytest.raises(AuthConfigurationError, match="Production cannot"):
        load_auth_runtime_config(_runtime(production_mode=True), {})

    with pytest.raises(AuthConfigurationError, match="requires origins"):
        load_auth_runtime_config(_runtime(pwa_prototype=False), {})


@pytest.mark.parametrize(
    ("runtime_profile", "prod_marker"),
    (("pwa-production", None), ("pwa-agent", "true")),
)
def test_pwa_startup_production_markers_enable_secure_auth_policy(
    monkeypatch,
    runtime_profile,
    prod_marker,
):
    monkeypatch.setenv("VMSH_RUNTIME_PROFILE", runtime_profile)
    monkeypatch.setenv("VMSH_PWA_PROTOTYPE", "false")
    if prod_marker is None:
        monkeypatch.delenv("PROD", raising=False)
    else:
        monkeypatch.setenv("PROD", prod_marker)

    runtime = _setup()
    auth = load_auth_runtime_config(runtime, _explicit_environment())

    assert runtime.production_mode is True
    assert runtime.telegram_bot_token == ""
    assert runtime.google_cred_json == ""
    assert auth.secure_cookies is True
    with pytest.raises(AuthConfigurationError, match="HTTPS"):
        load_auth_runtime_config(
            runtime,
            _explicit_environment(secure_origins=False),
        )


@pytest.mark.parametrize("runtime_profile", ("pwa-production", "pwa-agent"))
def test_pwa_production_startup_rejects_prototype(
    monkeypatch,
    runtime_profile,
):
    monkeypatch.setenv("VMSH_RUNTIME_PROFILE", runtime_profile)
    monkeypatch.setenv("VMSH_PWA_PROTOTYPE", "true")
    if runtime_profile == "pwa-production":
        monkeypatch.delenv("PROD", raising=False)
    else:
        monkeypatch.setenv("PROD", "true")

    with pytest.raises(RuntimeError, match="cannot enable VMSH_PWA_PROTOTYPE"):
        _setup()


def test_explicit_production_config_is_validated_and_builds_codec():
    config = load_auth_runtime_config(
        _runtime(pwa_prototype=False, production_mode=True),
        {
            **_explicit_environment(),
            "VMSH_PWA_TRUSTED_PROXY_CIDRS": "127.0.0.1/32,::1/128",
            "VMSH_PWA_TRUSTED_PROXY_HOPS": "1",
            "VMSH_PWA_ACCESS_TTL_SECONDS": "600",
        },
    )

    assert config.secure_cookies
    assert config.access_ttl_seconds == 600
    assert len(config.trusted_proxy_networks) == 2
    assert config.trusted_proxy_hops == 1
    assert config.access_codec().max_age_seconds == 600
    assert not config.test_only_defaults


@pytest.mark.parametrize(
    "mutator, expected",
    [
        (
            lambda env: env.update(
                {
                    "VMSH_PWA_PUBLIC_ORIGINS_JSON": json.dumps(
                        {
                            audience.value: ["http://vmsh.example"]
                            for audience in AuthAudience
                        }
                    )
                }
            ),
            "HTTPS",
        ),
        (
            lambda env: env.update(
                {"VMSH_PWA_AUTH_SIGNING_KEYS_JSON": json.dumps(["short"])}
            ),
            "32 bytes",
        ),
        (
            lambda env: env.update({"VMSH_PWA_REFRESH_PEPPER_B64": _encoded(b"short")}),
            "at least 32 bytes",
        ),
        (
            lambda env: env.update({"VMSH_PWA_TRUSTED_PROXY_CIDRS": "127.0.0.1/8"}),
            "canonical CIDR",
        ),
        (
            lambda env: env.update({"VMSH_PWA_TRUSTED_PROXY_HOPS": "1"}),
            "require at least one",
        ),
    ],
)
def test_invalid_security_configuration_fails_closed(mutator, expected):
    environment = _explicit_environment()
    mutator(environment)
    with pytest.raises((AuthConfigurationError, ValueError), match=expected):
        load_auth_runtime_config(
            _runtime(pwa_prototype=False, production_mode=True), environment
        )


def test_plain_http_is_limited_to_loopback_even_outside_production():
    with pytest.raises(AuthConfigurationError, match="loopback"):
        load_auth_runtime_config(
            _runtime(pwa_prototype=False), _explicit_environment(secure_origins=False)
        )


def test_partial_explicit_secret_set_does_not_mix_with_test_defaults():
    with pytest.raises(AuthConfigurationError, match="requires origins"):
        load_auth_runtime_config(
            _runtime(), {"VMSH_PWA_AUTH_SIGNING_KEYS_JSON": json.dumps(["a" * 32])}
        )


def test_cookie_names_and_paths_are_pairwise_isolated():
    assert {policy.path for policy in COOKIE_POLICY.values()} == {
        "/student",
        "/family",
        "/staff",
    }
    names = {
        name
        for policy in COOKIE_POLICY.values()
        for name in (policy.access_name, policy.refresh_name)
    }
    assert len(names) == 6
    assert all(
        policy.http_only and policy.same_site == "Lax"
        for policy in COOKIE_POLICY.values()
    )


def test_exact_unix_proxy_socket_configuration_is_canonical_and_explicit():
    environment = _explicit_environment()
    environment.update(
        {
            "VMSH_PWA_TRUSTED_PROXY_HOPS": "1",
            "VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON": json.dumps(
                ["/run/vmshpwa/vmshpwa.sock"]
            ),
        }
    )

    config = load_auth_runtime_config(
        _runtime(pwa_prototype=False),
        environment,
    )

    assert config.trusted_proxy_hops == 1
    assert config.trusted_proxy_networks == ()
    assert config.trusted_proxy_unix_socket_paths == ("/run/vmshpwa/vmshpwa.sock",)


@pytest.mark.parametrize(
    "paths",
    [
        ["relative/backend.sock"],
        ["/run/vmshpwa/../backend.sock"],
        [" /run/vmshpwa/backend.sock"],
        ["/run/vmshpwa/backend.sock", "/run/vmshpwa/backend.sock"],
        ["\x00abstract"],
    ],
)
def test_unix_proxy_socket_allowlist_rejects_non_exact_paths(paths):
    environment = _explicit_environment()
    environment.update(
        {
            "VMSH_PWA_TRUSTED_PROXY_HOPS": "1",
            "VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON": json.dumps(paths),
        }
    )

    with pytest.raises(AuthConfigurationError, match="canonical|unique"):
        load_auth_runtime_config(
            _runtime(pwa_prototype=False),
            environment,
        )


def test_unix_proxy_socket_never_enables_implicit_or_multi_hop_trust():
    base = _explicit_environment()
    base["VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON"] = json.dumps(
        ["/run/vmshpwa/vmshpwa.sock"]
    )

    with pytest.raises(AuthConfigurationError, match="positive proxy hop"):
        load_auth_runtime_config(_runtime(pwa_prototype=False), base)

    base["VMSH_PWA_TRUSTED_PROXY_HOPS"] = "2"
    with pytest.raises(AuthConfigurationError, match="Multiple trusted proxy"):
        load_auth_runtime_config(_runtime(pwa_prototype=False), base)


def test_direct_auth_config_construction_cannot_bypass_unix_path_validation():
    valid = load_auth_runtime_config(
        _runtime(pwa_prototype=False),
        _explicit_environment(),
    )

    with pytest.raises(AuthConfigurationError, match="canonical absolute"):
        AuthRuntimeConfig(
            origins_by_audience=valid.origins_by_audience,
            trusted_proxy_networks=(),
            trusted_proxy_hops=1,
            access_ttl_seconds=valid.access_ttl_seconds,
            secure_cookies=valid.secure_cookies,
            signing_keys=valid.signing_keys,
            refresh_pepper=valid.refresh_pepper,
            throttle_pepper=valid.throttle_pepper,
            trusted_proxy_unix_socket_paths=("relative.sock",),
        )
