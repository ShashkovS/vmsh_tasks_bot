# TLF Prep Clubs monitoring

Prepared 2026-09-30 for `ssh -F ssh/config tlfprepagent` (`vmsh-nbg`).
This directory adapts the reviewed [vmshbeget installer](../install_vmsh_monitoring_beget.sh)
without its global APT, journald, logrotate or NATS changes. The reference host's
live targets/versions were checked read-only; its configuration files require
privileges unavailable to vmshbegetagent.

## Scope

[install.sh](install.sh) replaces the owner-approved legacy monitoring state,
keeping backups under `/root/tlf-monitoring-backups/<UTC timestamp>/`.
It installs checksum-pinned Prometheus 3.13.2, Node Exporter 1.12.1, nginx Exporter
1.5.1 and NATS Exporter 0.20.1. Existing Grafana OSS 13.2.3 is retained.
[Service units](prometheus.service) and all metric listeners bind loopback.
[Prometheus configuration](prometheus.yml) limits retention to 60 days/2500MB,
uses instance `prep.leaders.tech`, and retains query limits from vmshbeget.

[Grafana configuration](grafana.ini) binds `127.0.0.1:3001`, disables anonymous
access/signup, uses secure cookies and provisions one local [datasource](datasource.yaml).
The [dashboard](overview.json), adapted from the vmshbeget installer, contains
host, nginx, NATS, backend and SQLite graphs. The
[nginx virtual host](grafprep.nginx.conf) serves `grafprep.leaders.tech` over the
previously issued certificate, with HTTP redirect and WebSocket support.
The legacy Grafana virtual host is disabled; other sites remain untouched.

First invocation requires `bash install.sh --reset-legacy-monitoring` as root.
It moves old Prometheus data, Grafana database and provisioning into the backup,
then initializes a fresh Grafana administrator. Passwords are generated on the
server and stored in `/root/grafprep-admin-credentials.txt` (0600); retrieve via
SSH using `sudo cat` locally. Never copy that file into the repository.
Subsequent invocations preserve database state and credentials.

## Deployed and verified — 2026-09-30

Installed at `/root/tlf-monitoring-release-20260930/tlf-monitoring/`.
Backup: `/root/tlf-monitoring-backups/20260930T185824Z/`.
Public HTTP returns 301 to HTTPS; HTTPS login returns 200 with verified TLS.
Grafana 13.2.3 reports database `ok`; authenticated administrator access loads
the provisioned 18-panel `TLF Prep Clubs server overview` and the datasource
health is `OK`. All three enabled Prometheus targets (`node`, `nginx`,
`prometheus`) are `up`, with instance `prep.leaders.tech`; `nginx_up = 1` and
host memory metrics are present. All monitoring listeners are on `127.0.0.1`.
Promtool/nginx checks pass. Unrelated running services and the shared NATS process
are preserved. Initial provisioning directory permissions were corrected before
verification; the installer includes that fix.

## Connect the clone after deployment

2026-09-30: [application rollout](../tlf-app/README.md) activated `aiohttp.json`
with loopback 8000. Four targets (aiohttp/nginx/node/prometheus) verified `up`.
NATS and Telegram discovery stay empty; the shared NATS process is unchanged.

The file-discovery targets `aiohttp.json`, `telegram-bot.json` and `nats.json`
initially contain `[]`. The installer does not touch/restart the shared NATS
service. [NATS monitoring listeners are not reloadable](https://docs.nats.io/reference/config/),
so enable the clone's monitoring endpoint as part of its own deployment.
After checking the endpoint is local and healthy, write a target such as:

```json
[{"targets":["127.0.0.1:8000"],"labels":{"instance":"prep.leaders.tech"}}]
```

Use port 8000 for aiohttp only after confirming the clone's actual listener;
use the clone's NATS exporter port in `nats.json` after enabling its service.
Prometheus rereads discovery files automatically. Do not point these files to
vmshbeget or an unrelated backend on this shared server.

## Verification and rollback

Deployment status is recorded in
[development STATUS](../../../vmshpwa/dev/development-plan/STATUS.md).
Check `nginx -t`, Prometheus `/-/ready` and `/api/v1/targets`, Grafana `/api/health`,
authenticated dashboard/datasource access, TLS and listener addresses.
App panels now have the clone's metrics. NATS panels remain empty until its
monitoring endpoint and discovery target are enabled.

For rollback stop the monitoring services, restore the configuration/binaries
archive and the moved Prometheus/Grafana state from the same backup, remove only
new TLF nginx/provisioning files, then run `nginx -t`, `systemctl daemon-reload`,
reload nginx and start the previously recorded monitoring units. Backups include
nginx sites/symlinks and the before/after running-service inventory.
