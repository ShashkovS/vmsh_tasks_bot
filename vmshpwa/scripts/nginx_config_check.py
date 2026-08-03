"""Run the real nginx syntax check without treating absence as success."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Sequence


UNRESOLVED_MARKER = re.compile(r"@@[A-Z0-9_]+@@")
PUBLIC_HOST = re.compile(
    r"(?=.{4,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
)


def _validate_public_host(public_host: str) -> str | None:
    if PUBLIC_HOST.fullmatch(public_host) is None:
        return (
            "public host must be a lowercase ASCII FQDN without wildcard, "
            "scheme, port, path or trailing dot"
        )
    return None


def _validate_rendered_site(source: str, public_host: str) -> str | None:
    markers = sorted(set(UNRESOLVED_MARKER.findall(source)))
    if markers:
        return "site config still contains unresolved markers: " + ", ".join(markers)
    uncommented = "\n".join(line.split("#", 1)[0] for line in source.splitlines())
    server_names = re.findall(r"\bserver_name\s+([^;]+);", uncommented)
    if len(server_names) != 2 or any(
        name.strip() != public_host for name in server_names
    ):
        return "site config must use the exact public host in both server_name blocks"
    if f"return 308 https://{public_host}$request_uri;" not in uncommented:
        return "site config HTTPS redirect does not match the exact public host"
    if f"connect-src 'self' wss://{public_host}" not in uncommented:
        return "site config CSP WebSocket origin does not match the exact public host"
    worker_boundary = (
        "map $uri $vmshpwa_service_worker_cache_control",
        '/student/sw.js "no-store";',
        '/family/sw.js "no-store";',
        "map $uri $vmshpwa_service_worker_scope",
        '/student/sw.js "/student/";',
        '/family/sw.js "/family/";',
        "add_header Cache-Control $vmshpwa_service_worker_cache_control always;",
        "add_header Service-Worker-Allowed $vmshpwa_service_worker_scope always;",
    )
    if any(required not in uncommented for required in worker_boundary):
        return "site config is missing the production service-worker cache boundary"
    return None


def check_nginx_config(
    config_path: Path,
    *,
    site_config_path: Path | None = None,
    public_host: str = "",
    nginx_binary: str = "nginx",
    prefix: Path | None = None,
) -> int:
    """Return 0 only for an actual successful ``nginx -t`` invocation."""

    executable = shutil.which(nginx_binary)
    if executable is None:
        print(
            "UNAVAILABLE: nginx executable was not found; "
            "the production syntax proof is still open."
        )
        return 2

    public_host_failure = _validate_public_host(public_host)
    if public_host_failure is not None:
        print(f"UNAVAILABLE: {public_host_failure}.")
        return 2

    resolved_config = config_path.expanduser().resolve()
    if not resolved_config.is_file():
        print(
            f"UNAVAILABLE: nginx config does not exist: {resolved_config}; "
            "the production syntax proof is still open."
        )
        return 2
    root_source = resolved_config.read_text(encoding="utf-8")
    markers = sorted(set(UNRESOLVED_MARKER.findall(root_source)))
    if markers:
        print(
            "UNAVAILABLE: nginx config still contains unresolved markers: "
            + ", ".join(markers)
        )
        return 2

    if site_config_path is None:
        print(
            "UNAVAILABLE: rendered PWA site config was not supplied; "
            "the public-host proof is still open."
        )
        return 2
    resolved_site_config = site_config_path.expanduser().resolve()
    if not resolved_site_config.is_file():
        print(
            f"UNAVAILABLE: rendered PWA site config does not exist: "
            f"{resolved_site_config}."
        )
        return 2
    site_failure = _validate_rendered_site(
        resolved_site_config.read_text(encoding="utf-8"), public_host
    )
    if site_failure is not None:
        print(f"UNAVAILABLE: {site_failure}.")
        return 2

    command = [executable, "-t", "-c", str(resolved_config)]
    if prefix is not None:
        command.extend(["-p", str(prefix.expanduser().resolve())])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print("FAILED: nginx -t exceeded the 30-second safety timeout.")
        return 1

    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip())
    if completed.returncode != 0:
        print(f"FAILED: nginx -t exited with status {completed.returncode}.")
        return 1
    print("PASS: nginx -t accepted the installed production configuration.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("VMSH_PWA_NGINX_CONFIG", "/etc/nginx/nginx.conf")),
        help="Top-level installed nginx config (default: env or /etc/nginx/nginx.conf)",
    )
    parser.add_argument("--nginx", default="nginx", help="nginx executable name/path")
    parser.add_argument("--prefix", type=Path, help="optional nginx -p prefix")
    parser.add_argument(
        "--site-config",
        type=Path,
        default=Path(
            os.environ.get(
                "VMSH_PWA_NGINX_SITE_CONFIG",
                "/etc/nginx/conf.d/vmshpwa.conf",
            )
        ),
        help="installed rendered PWA site config",
    )
    parser.add_argument(
        "--public-host",
        default=os.environ.get("VMSH_PWA_PUBLIC_HOST", ""),
        help="owner-approved exact lowercase public FQDN",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    return check_nginx_config(
        arguments.config,
        site_config_path=arguments.site_config,
        public_host=arguments.public_host,
        nginx_binary=arguments.nginx,
        prefix=arguments.prefix,
    )


if __name__ == "__main__":  # pragma: no cover - exercised through main tests
    raise SystemExit(main())
