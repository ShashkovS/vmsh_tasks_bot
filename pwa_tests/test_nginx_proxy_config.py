"""Structural proof for the production nginx template and syntax helper."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vmshpwa.scripts import nginx_config_check


ROOT = Path(__file__).resolve().parents[1]
NGINX_DIR = ROOT / "vmshpwa" / "deploy" / "nginx"
TEMPLATE = NGINX_DIR / "vmshpwa.conf.template"
PROXY_HEADERS = NGINX_DIR / "vmshpwa-proxy-headers.conf"
MAKEFILE = ROOT / "Makefile"


def _location(source: str, selector: str) -> str:
    marker = f"location {selector} {{"
    start = source.index(marker)
    cursor = start + len(marker)
    depth = 1
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    assert depth == 0, f"unterminated nginx location: {selector}"
    return source[start:cursor]


def _rendered_site(public_host: str = "pwa.example.org") -> str:
    return f"""
map $uri $vmshpwa_service_worker_cache_control {{
    default "";
    /student/sw.js "no-store";
    /family/sw.js "no-store";
}}
map $uri $vmshpwa_service_worker_scope {{
    default "";
    /student/sw.js "/student/";
    /family/sw.js "/family/";
}}
server {{ server_name {public_host}; return 308 https://{public_host}$request_uri; }}
server {{
    server_name {public_host};
    add_header Content-Security-Policy "default-src 'none'; connect-src 'self' wss://{public_host}";
    add_header Cache-Control $vmshpwa_service_worker_cache_control always;
    add_header Service-Worker-Allowed $vmshpwa_service_worker_scope always;
}}
"""


def test_template_has_one_host_and_separate_static_api_websocket_boundaries():
    source = TEMPLATE.read_text(encoding="utf-8")

    assert source.count("server_name @@PUBLIC_HOST@@;") == 2
    assert "return 308 https://@@PUBLIC_HOST@@$request_uri;" in source
    assert "root @@STATIC_ROOT@@;" in source
    assert source.count("include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;") == 7

    content_assets = _location(source, "^~ /pwa-content-assets/")
    assert "limit_except GET { deny all; }" in content_assets
    assert "client_max_body_size 1k;" in content_assets
    assert "proxy_pass http://vmshpwa_backend;" in content_assets

    for audience in ("student", "family", "staff"):
        api = _location(source, f"^~ /{audience}/api/")
        assert "client_max_body_size 64m;" in api
        assert 'proxy_set_header Connection "";' in api
        assert "proxy_pass http://vmshpwa_backend;" in api

        websocket = _location(source, f"= /{audience}/ws")
        assert "client_max_body_size 64k;" in websocket
        assert "proxy_set_header Upgrade $http_upgrade;" in websocket
        assert 'proxy_set_header Connection "upgrade";' in websocket
        assert "proxy_read_timeout 75s;" in websocket
        assert "proxy_buffering off;" in websocket

        static = _location(source, f"^~ /{audience}/")
        assert f"try_files $uri $uri/ /{audience}/index.html;" in static
        assert f"location = /{audience}/api {{ return 404; }}" in source
        assert f"location = /{audience}/ws/ {{ return 404; }}" in source


def test_proxy_header_snippet_replaces_client_forwarding_evidence():
    source = PROXY_HEADERS.read_text(encoding="utf-8")
    directives = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )

    assert (
        'proxy_set_header Forwarded "for=\\"$remote_addr\\";'
        'proto=https;host=\\"$host\\"";'
    ) in source
    for header in (
        "X-Forwarded-For",
        "X-Forwarded-Host",
        "X-Forwarded-Proto",
        "X-Forwarded-Port",
        "X-Forwarded-Prefix",
        "X-Forwarded-Server",
        "X-Forwarded-Ssl",
    ):
        assert f'proxy_set_header {header} "";' in source
    for forbidden in (
        "$proxy_add_x_forwarded_for",
        "$http_forwarded",
        "$http_x_forwarded",
    ):
        assert forbidden not in directives
    assert "proxy_connect_timeout 5s;" in source
    assert "proxy_send_timeout 120s;" in source
    assert "proxy_read_timeout 120s;" in source


def test_login_limit_is_exact_per_ip_and_returns_retry_semantics():
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "~^/(student|family|staff)/api/v1/auth/login$ $binary_remote_addr;" in source
    assert "limit_req_zone $vmshpwa_login_limit_key" in source
    assert "rate=6r/m;" in source
    assert "limit_req zone=vmshpwa_login_per_ip burst=4 nodelay;" in source
    assert "limit_req_status 429;" in source
    assert "REJECTED 60;" in source
    assert "add_header Retry-After $vmshpwa_retry_after always;" in source


def test_csp_and_security_headers_are_strict_with_explicit_render_markers():
    source = TEMPLATE.read_text(encoding="utf-8")

    for marker in (
        "@@BACKEND_UNIX_SOCKET@@",
        "@@PUBLIC_HOST@@",
        "@@TLS_CONFIG_FILE@@",
        "@@STATIC_ROOT@@",
        "@@CSP_MEDIA_ORIGIN@@",
        "@@CSP_SENTRY_ORIGIN@@",
    ):
        assert marker in source
    for directive in (
        "default-src 'none'",
        "base-uri 'none'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "script-src 'self'",
        "connect-src 'self' wss://@@PUBLIC_HOST@@",
    ):
        assert directive in source
    assert "unsafe-eval" not in source
    assert 'add_header X-Content-Type-Options "nosniff" always;' in source
    assert 'add_header X-Frame-Options "DENY" always;' in source
    assert "Strict-Transport-Security" in source


def test_service_workers_are_never_cached_without_losing_server_headers():
    source = TEMPLATE.read_text(encoding="utf-8")

    assert source.count("map $uri $vmshpwa_service_worker_cache_control {") == 1
    assert source.count("map $uri $vmshpwa_service_worker_scope {") == 1
    for audience in ("student", "family"):
        assert f'/{audience}/sw.js "no-store";' in source
        assert f'/{audience}/sw.js "/{audience}/";' in source
        # Keep add_header at server level. Defining it in the static child
        # location would suppress the inherited CSP/HSTS set on common nginx.
        static = _location(source, f"^~ /{audience}/")
        assert "add_header" not in static
    assert (
        "add_header Cache-Control $vmshpwa_service_worker_cache_control always;"
        in source
    )
    assert (
        "add_header Service-Worker-Allowed $vmshpwa_service_worker_scope always;"
        in source
    )


def test_make_target_invokes_only_the_fail_closed_syntax_helper():
    source = MAKEFILE.read_text(encoding="utf-8")

    assert ".PHONY: pwa-nginx-check" in source
    assert "python -m vmshpwa.scripts.nginx_config_check" in source
    assert "VMSH_PWA_NGINX_CONFIG:-/etc/nginx/nginx.conf" in source
    assert "VMSH_PWA_NGINX_SITE_CONFIG:-/etc/nginx/conf.d/vmshpwa.conf" in source
    assert 'VMSH_PWA_PUBLIC_HOST:-}"' in source


def test_syntax_check_reports_missing_nginx_as_unavailable(
    monkeypatch, tmp_path, capsys
):
    config = tmp_path / "nginx.conf"
    config.write_text("events {}\n", encoding="utf-8")
    monkeypatch.setattr(nginx_config_check.shutil, "which", lambda _binary: None)

    result = nginx_config_check.check_nginx_config(config)

    assert result == 2
    output = capsys.readouterr().out
    assert "UNAVAILABLE" in output
    assert "still open" in output


def test_syntax_check_refuses_unrendered_config_before_invocation(
    monkeypatch, tmp_path, capsys
):
    config = tmp_path / "nginx.conf"
    config.write_text("events {}\n# @@STATIC_ROOT@@\n", encoding="utf-8")
    monkeypatch.setattr(
        nginx_config_check.shutil,
        "which",
        lambda _binary: "/usr/sbin/nginx",
    )

    result = nginx_config_check.check_nginx_config(
        config,
        site_config_path=config,
        public_host="pwa.example.org",
    )

    assert result == 2
    assert "unresolved markers" in capsys.readouterr().out


def test_syntax_check_refuses_installed_site_without_worker_cache_boundary(
    monkeypatch, tmp_path, capsys
):
    config = tmp_path / "nginx.conf"
    config.write_text("events {}\n", encoding="utf-8")
    site_config = tmp_path / "vmshpwa.conf"
    site_config.write_text(
        """
server { server_name pwa.example.org; return 308 https://pwa.example.org$request_uri; }
server {
    server_name pwa.example.org;
    add_header Content-Security-Policy "default-src 'none'; connect-src 'self' wss://pwa.example.org";
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        nginx_config_check.shutil,
        "which",
        lambda _binary: "/usr/sbin/nginx",
    )

    result = nginx_config_check.check_nginx_config(
        config,
        site_config_path=site_config,
        public_host="pwa.example.org",
    )

    assert result == 2
    assert "service-worker cache boundary" in capsys.readouterr().out


def test_syntax_check_runs_exact_nginx_test_command(monkeypatch, tmp_path, capsys):
    config = tmp_path / "nginx.conf"
    config.write_text("events {}\n", encoding="utf-8")
    site_config = tmp_path / "vmshpwa.conf"
    site_config.write_text(_rendered_site(), encoding="utf-8")
    observed: list[str] = []
    monkeypatch.setattr(
        nginx_config_check.shutil,
        "which",
        lambda _binary: "/usr/sbin/nginx",
    )

    def fake_run(command, **kwargs):
        observed.extend(command)
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 30,
        }
        return subprocess.CompletedProcess(command, 0, "", "syntax is ok\n")

    monkeypatch.setattr(nginx_config_check.subprocess, "run", fake_run)

    result = nginx_config_check.check_nginx_config(
        config,
        site_config_path=site_config,
        public_host="pwa.example.org",
    )

    assert result == 0
    assert observed == ["/usr/sbin/nginx", "-t", "-c", str(config.resolve())]
    output = capsys.readouterr().out
    assert "syntax is ok" in output
    assert "PASS" in output


@pytest.mark.parametrize("returncode", (1, 2))
def test_syntax_check_never_turns_nginx_failure_into_success(
    monkeypatch, tmp_path, returncode
):
    config = tmp_path / "nginx.conf"
    config.write_text("events {}\n", encoding="utf-8")
    site_config = tmp_path / "vmshpwa.conf"
    site_config.write_text(_rendered_site(), encoding="utf-8")
    monkeypatch.setattr(
        nginx_config_check.shutil,
        "which",
        lambda _binary: "/usr/sbin/nginx",
    )
    monkeypatch.setattr(
        nginx_config_check.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, returncode, "", "bad config"
        ),
    )

    assert (
        nginx_config_check.check_nginx_config(
            config,
            site_config_path=site_config,
            public_host="pwa.example.org",
        )
        == 1
    )


@pytest.mark.parametrize(
    "public_host",
    (
        "",
        "localhost",
        "PWA.example.org",
        "*.example.org",
        "https://pwa.example.org",
        "pwa.example.org:443",
        "pwa.example.org/path",
        "pwa.example.org.",
    ),
)
def test_syntax_check_rejects_unsafe_or_ambiguous_public_host(
    monkeypatch, tmp_path, public_host, capsys
):
    config = tmp_path / "nginx.conf"
    config.write_text("events {}\n", encoding="utf-8")
    site_config = tmp_path / "vmshpwa.conf"
    site_config.write_text(_rendered_site(), encoding="utf-8")
    monkeypatch.setattr(
        nginx_config_check.shutil,
        "which",
        lambda _binary: "/usr/sbin/nginx",
    )

    result = nginx_config_check.check_nginx_config(
        config,
        site_config_path=site_config,
        public_host=public_host,
    )

    assert result == 2
    assert "public host must be" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("site_source", "expected"),
    (
        (_rendered_site("other.example.org"), "server_name"),
        (
            _rendered_site().replace(
                "https://pwa.example.org$request_uri",
                "https://other.example.org$request_uri",
            ),
            "HTTPS redirect",
        ),
        (
            _rendered_site().replace(
                "wss://pwa.example.org", "wss://other.example.org"
            ),
            "CSP WebSocket origin",
        ),
    ),
)
def test_syntax_check_rejects_public_host_mismatch(
    monkeypatch, tmp_path, site_source, expected, capsys
):
    config = tmp_path / "nginx.conf"
    config.write_text("events {}\n", encoding="utf-8")
    site_config = tmp_path / "vmshpwa.conf"
    site_config.write_text(site_source, encoding="utf-8")
    monkeypatch.setattr(
        nginx_config_check.shutil,
        "which",
        lambda _binary: "/usr/sbin/nginx",
    )

    result = nginx_config_check.check_nginx_config(
        config,
        site_config_path=site_config,
        public_host="pwa.example.org",
    )

    assert result == 2
    assert expected in capsys.readouterr().out
