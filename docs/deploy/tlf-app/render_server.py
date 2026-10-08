"""Render this server's units/static release. Run as root after a frozen build.

See README.md. Credentials stay on the host; this reads only the Sentry origin.
It does not restart services or install nginx links.
"""

import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path("/web/vmsh_tasks_bot")
CODE = BASE / "vmsh_tasks_bot"
RUNTIME = BASE / "vmshpwa/runtime"
RELEASE_ID = os.environ.get("TLF_RELEASE_ID", "tlfprep-20260930")
if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", RELEASE_ID) is None:
    raise ValueError("Invalid release name")
RELEASE = BASE / "vmshpwa/releases" / RELEASE_ID


def write(path, text, mode=0o640):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.chmod(path, mode)
    shutil.chown(path, user="root", group="nginx")


def main():
    for audience in ("landing", "student", "family", "staff"):
        shutil.copytree(
            CODE / f"vmshpwa/apps/{audience}/dist",
            RELEASE / audience,
            dirs_exist_ok=True,
        )
        # Recover clients which cached an asset miss during initial cutover.
        # Fingerprinted bodies stay append-only; release entrypoints revalidate.
        entrypoint = RELEASE / audience / "index.html"
        entrypoint.write_text(
            re.sub(
                r'((?:src|href)="/[^"?]+/assets/[^"?]+\.(?:js|css))"',
                rf'\1?release={RELEASE_ID}"',
                entrypoint.read_text(),
            )
        )
        shutil.copytree(
            RELEASE / audience / "assets",
            BASE / f"vmshpwa/immutable-assets/{audience}/assets",
            dirs_exist_ok=True,
        )
    for directory in (RELEASE, BASE / "vmshpwa/immutable-assets"):
        shutil.chown(directory, user="root", group="nginx")
        for path in directory.rglob("*"):
            shutil.chown(path, user="root", group="nginx")
            os.chmod(path, 0o750 if path.is_dir() else 0o640)
    current = BASE / "vmshpwa/current"
    # production-rollout-checklist.md: keep the previous release reachable
    # until the complete new static tree is published with one atomic rename.
    temporary = current.with_name(f".current.{RELEASE_ID}")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(RELEASE)
    temporary.replace(current)
    unit = (CODE / "vmshpwa/deploy/systemd/vmshpwa.service.template").read_text()
    unit = unit.replace(
        "VMSH 179 Student, Family and Staff PWA API",
        "TLF Prep Clubs PWA API (two workers)",
    )
    unit = unit.replace("nats-server.service", "nats.service")
    unit = unit.replace(
        "Group=nginx\n", "Group=nginx\nSupplementaryGroups=vmsh_tasks_bot web\n"
    )
    write(RUNTIME / "vmshpwa.service", unit)
    # Preserve the installed host environment during subsequent manual releases.
    if not (RUNTIME / "vmshpwa.env").exists():
        write(
            RUNTIME / "vmshpwa.env",
            (CODE / "vmshpwa/deploy/systemd/vmshpwa.env.example").read_text(),
            0o600,
        )
    zoom = unit.replace(
        "TLF Prep Clubs PWA API (two workers)", "TLF signed Zoom archive (one worker)"
    )
    zoom = zoom.replace("--workers 2", "--workers 1")
    zoom = zoom.replace("vmshpwa.sock", "zoom.sock")
    zoom = zoom.replace("--bind 127.0.0.1:8000 ", "")
    zoom = zoom.replace("main:app", "apps.zoom_archive:create_app()")
    zoom = zoom.replace("vmsh-prometheus", "vmshzoom-prometheus")
    write(RUNTIME / "vmshzoom.service", zoom)
    for name in ("vmsh-analytics.service", "vmsh-analytics.timer"):
        write(RUNTIME / name, (CODE / f"vmshpwa/deploy/systemd/{name}").read_text())
    config = json.loads((CODE / "creds_prod/vmsh_bot_config_prod.json").read_text())
    sentry = urlsplit(config["sentry_dsn"])
    replacements = {
        "PUBLIC_HOST": "prep.leaders.tech",
        "BACKEND_UNIX_SOCKET": str(RUNTIME / "vmshpwa.sock"),
        "STATIC_ROOT": str(current),
        "TLS_CONFIG_FILE": str(RUNTIME / "nginx/tls.conf"),
        "CSP_MEDIA_ORIGIN": "https://tlfprepimages.nbg1.your-objectstorage.com",
        "CSP_SENTRY_ORIGIN": f"{sentry.scheme}://{sentry.hostname}",
    }
    nginx = (CODE / "vmshpwa/deploy/nginx/vmshpwa.conf.template").read_text()
    # Resolve independently: current is a symlink, so current/.. traverses
    # the release parent instead of the stable immutable-assets directory.
    nginx = nginx.replace(
        "@@STATIC_ROOT@@/../immutable-assets", str(BASE / "vmshpwa/immutable-assets")
    )
    for key, value in replacements.items():
        nginx = nginx.replace(f"@@{key}@@", value)
    nginx = nginx.replace(
        "server {\n    listen 80;",
        "upstream vmshzoom_backend {\n"
        f"    server unix:{RUNTIME}/zoom.sock fail_timeout=0;\n"
        "}\n\nserver {\n    listen 80;",
        1,
    )
    nginx = nginx.replace(
        "    location = /service-status {",
        "    # Dedicated signed ingress; all meetings archived.\n"
        "    location = /zoomevents {\n"
        "        limit_except POST { deny all; }\n"
        "        client_max_body_size 8m;\n"
        "        include /etc/nginx/snippets/vmshpwa-proxy-headers.conf;\n"
        "        proxy_read_timeout 5s;\n"
        "        proxy_pass http://vmshzoom_backend;\n"
        "    }\n\n    location = /service-status {",
        1,
    )
    # Failed asset lookups must not leave a year-long negative browser cache.
    nginx = nginx.replace(
        "limit_req_zone $vmshpwa_login_limit_key",
        'map "$status:$vmshpwa_release_cache_control" $tlf_response_cache_control {\n'
        "    default $vmshpwa_release_cache_control;\n"
        "    ~^[45] no-store;\n}\n\nlimit_req_zone $vmshpwa_login_limit_key",
        1,
    )
    nginx = nginx.replace(
        "add_header Cache-Control $vmshpwa_release_cache_control always;",
        "add_header Cache-Control $tlf_response_cache_control always;",
    )
    write(RUNTIME / "nginx/vmshpwa.conf", nginx)
    write(
        RUNTIME / "nginx/vmshpwa-proxy-headers.conf",
        (CODE / "vmshpwa/deploy/nginx/vmshpwa-proxy-headers.conf").read_text(),
    )
    write(
        RUNTIME / "nginx/tls.conf",
        "ssl_certificate /etc/letsencrypt/live/prep.leaders.tech/fullchain.pem;\n"
        "ssl_certificate_key /etc/letsencrypt/live/prep.leaders.tech/privkey.pem;\n"
        "include /etc/letsencrypt/options-ssl-nginx.conf;\n"
        "ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;\n",
    )
    write(
        RUNTIME / "vmsh-backup.service",
        """[Unit]
Description=TLF SQLite online backups and restore verification
After=vmshpwa.service
[Service]
Type=oneshot
User=vmsh_tasks_bot
Group=nginx
SupplementaryGroups=vmsh_tasks_bot web
WorkingDirectory=/web/vmsh_tasks_bot/vmsh_tasks_bot
ExecStart=/web/vmsh_tasks_bot/vmsh_tasks_bot/.venv/bin/python /web/vmsh_tasks_bot/deploy/bin/backup.py
UMask=0077
TimeoutStartSec=30min
Nice=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/web/vmsh_tasks_bot/backups /web/vmsh_tasks_bot/vmsh_tasks_bot/db
""",
    )
    write(
        RUNTIME / "vmsh-backup.timer",
        """[Unit]
Description=TLF backup every eight hours
[Timer]
OnCalendar=*-*-* 00/8:15:00 Europe/Moscow
Persistent=true
Unit=vmsh-backup.service
[Install]
WantedBy=timers.target
""",
    )
    print("Static release and host artifacts rendered")


if __name__ == "__main__":
    main()
