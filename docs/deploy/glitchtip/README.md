# GlitchTip on prep.leaders.tech

Deployed at **https://glitch.leaders.tech** on 2026-10-11 at the owner's request,
using `ssh -F ssh/config tlfprepagent` and sudo. DNS A `188.245.158.162` and AAAA
`2a01:4f8:1c1b:c08f::1` verified. HTTPS works through both addresses.

## Installed state

[compose.yml](compose.yml) pins GlitchTip **6.2.6** and PostgreSQL **18** by digest.
Project `glitchtip` has independent PostgreSQL/uploads volumes. Application binds
`127.0.0.1:8011`; PostgreSQL has no published port. The host's existing PostgreSQL,
Docker `matrix_db`, PWA/Zoom, NATS and monitoring are separate from these containers.
Memory limits: application 1 GiB, PostgreSQL 768 MiB; observed after the probe:
about 198/63 MiB. Docker logs rotate at 3 × 10 MiB per container.

[nginx virtual host](glitch.leaders.tech.conf) serves IPv4/IPv6 and redirects HTTP
to HTTPS. Certificate expires 2027-01-09. Existing Certbot timer and nginx reload
hook handle renewal; `certbot renew --cert-name glitch.leaders.tech --dry-run`
passed. [systemd unit](glitchtip.service) and Docker restart policies enable boot
startup. The embedded worker uses PostgreSQL for its queue/cache, without Valkey.

Error/file retention is 30 days, release retention 90 days. Logs, uptime and cold
storage are disabled. Hosted billing is disabled. MCP is available at
**https://glitch.leaders.tech/mcp** and rejects unauthenticated requests.
Email transport is disabled at the owner's request. Error notifications use
Telegram; password-reset email is unavailable. Public/social registration are disabled.

The administrator is **sergey.shashkov@leaders.tech**. Retrieve the generated
initial password over the existing SSH connection:

```sh
ssh -F ssh/config tlfprepagent 'sudo cat /opt/glitchtip/admin-credentials.json'
```

The root-only file is 0600 and was never copied into the repository or deployment
proof. [Bootstrap helper](bootstrap-admin.py) creates the first superuser and can
rename that same account through `--email`, preserving organization memberships.
It preserves an existing password on rerun. The stored initial password becomes
stale after a user changes their password.

[Provisioning helper](provision-projects.py) created separate namespaces:

| Organization | Frontend project | ID | Backend project | ID |
| --- | --- | --- | --- | --- |
| VMSH (`vmsh`) | `vmshpwa` | 1 | `backend` | 2 |
| TLF (`tlf`) | `tlfpwa` | 3 | `backend` | 4 |

The administrator owns both organizations. Each has its own team and project keys.
DSNs are available in project Settings and `/opt/glitchtip/projects.json` (0600).
Both portals now use GlitchTip frontend/backend DSNs, with private release maps,
persistent build configuration, CSP and bounded source-side reporting.
[Rollout, checks and activated versions](migration-20261011.md).

[Telegram transport](telegram-webhook.py) uses the existing `@vmsh179bot` and its
VMSH operator group for both portals, with separate labels. Four native new-issue
rules feed authenticated webhooks; only counts and issue links are sent. Durable
digests deduplicate and limit delivery to once per 15 minutes/project. The
[systemd unit](glitchtip-telegram.service) runs as DynamicUser with LoadCredential,
loopback port 8012 and its own state directory. `/opt/glitchtip/telegram.json` is
0600 root-only; registration and email transport stay disabled.

## Verification

[Safe deployment proof](deployment-proof.json) records:

- Real SPA login through the HTTPS allauth endpoint, secure session cookie,
  access to both organizations and no public registration.
- Main frontend JS files load. Two JavaScript envelope events with browser Origin
  and one real Sentry Python SDK event were persisted in their correct projects
  with original stacks. Public ingest CORS is supported.
- After restarting only GlitchTip's PostgreSQL/application containers, the same
  tracked event IDs, organization/project assignments and stacks were present.
- Every Django migration applied, nginx validation passed, MCP requires auth,
  certificate renewal rehearsal passed.
- Existing prep portal: 25 read-only HTTP smoke checks PASS; existing PWA, Zoom,
  NATS and nginx main PIDs unchanged, Grafana database health `ok`.

[verify-live.py](verify-live.py) exercises this flow on the host. Credentials and
session cookies stay inside its process. On subsequent runs it rechecks stored
synthetic IDs instead of creating new errors. The database contains four synthetic
events: an initial CORS check also submitted one before the final three tracked
checks. These belong to `deployment-check`, with no real user data.

## Backups and operation

[backup.sh](backup.sh), [unit](glitchtip-backup.service) and
[timer](glitchtip-backup.timer) run daily at 02:35 UTC plus 0–10 minutes, retain
seven days, and store snapshots under `/var/backups/glitchtip/<UTC timestamp>/`.
Each contains a PostgreSQL custom dump, uploads archive, pinned Compose file,
private environment and SHA256 manifest. New snapshots also include Telegram
configuration/source/unit and a consistent digest-state copy. Files/directories are root-only.
These backups are on the same host; no off-host copy was configured.

The fresh snapshot `20261011T082010Z` restored successfully into a separate
temporary database: 1 user, 2 organizations, 4 projects, 4 synthetic events.
[verify-restore.sh](verify-restore.sh) checks hashes/archive and actually restores
the dump, then removes only its temporary database. The live database stays intact.

As root on the server:

```sh
systemctl status glitchtip glitchtip-telegram glitchtip-backup.timer
docker compose --project-directory /opt/glitchtip ps
docker compose --project-directory /opt/glitchtip logs --tail=100
systemctl start glitchtip-backup.service
/opt/glitchtip/verify-restore.sh /var/backups/glitchtip/20261011T082010Z
python3 /opt/glitchtip/verify-live.py
```

Before a manual upgrade, take and verify a new snapshot, review upstream release
notes, then change the pinned tag/digest in `/opt/glitchtip/compose.yml`. Run
`docker compose --project-directory /opt/glitchtip up -d --wait` and recheck login,
ingestion and migrations. Django migrations run automatically at startup. There
is no automatic image update.

For disaster recovery, retain the current state first, stop only GlitchTip,
and restore the snapshot's Compose/environment into fresh GlitchTip volumes.
Start PostgreSQL alone, restore `database.dump` with `pg_restore --exit-on-error`,
restore `uploads.tar.gz` into the uploads volume, then start the application.
Verify ownership, login and the stored event IDs before routing traffic to it.
Do not replace database files underneath a running PostgreSQL process or delete
other Compose projects/volumes.

References: [official installation guide](https://glitchtip.com/documentation/install/),
[release tags](https://gitlab.com/glitchtip/glitchtip-backend/-/tags),
[6.2 release notes](https://glitchtip.com/blog/2026-06-22-glitchtip-6-2-released/)
and [MCP guide](https://glitchtip.com/documentation/mcp/).
