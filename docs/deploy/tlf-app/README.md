# TLF Prep Clubs deployment

Owner-approved 2026-09-30: current vmshpwa code plus TLF identity, empty database
and first admin, two PWA workers, one separate Zoom archive worker, no automatic
deployment. All signed Zoom events from every meeting must be durably archived
before acknowledgement, including unknown event types and duplicate deliveries.
Queue/lesson interpretation is deferred. Lessons start 2026-10-02.

Implementation: [adapter](../../../apps/zoom_archive.py),
[archive writes](../../../db_methods/pwa/zoom_archive.py),
[migration 0102](../../../migrations/0102.zoom_webhook_archive.sql) and
[tests](../../../pwa_tests/test_zoom_archive.py). The archive uses the clone's main DB,
keeps exact request bodies, requires FULL synchronous writes, retains duplicates,
and has no automatic retention. CRC follows Zoom's webhook protocol; ordinary
requests require a valid signature. No participant payloads enter operational logs.

## Deployed and verified — 2026-09-30

Site: https://prep.leaders.tech/. Staff: https://prep.leaders.tech/staff/.
Initial login `admin`, password from the host's `first_admin_password`.
Identity selection is `/staff/branding` after login; see
[branding implementation](../../../vmshpwa/docs/branding.md).

Fresh `db/production_prep.db`, no database/accounts copied from vmshbeget.
TLF identity and English selected before the initial administrator was created.
`vmshpwa.service` runs two Gunicorn/uvloop workers on a Unix socket and loopback
8000; `vmshzoom.service` runs one independent archive worker on a Unix socket.
Both force `pwa-production`, disable prototype auth and start no Telegram/Google
adapter. The legacy JSON `apps` value does not start the old Zoom parser.

Webhook URL: https://prep.leaders.tech/zoomevents. Ordinary receipts go to
`zoom_webhook_receipts`; CRC is handled separately. The owner's Zoom app still
needs subscriptions pointed at this URL. Only synthetic deliveries are proven;
queue/lesson interpretation is deferred.

Shared NATS stays on `127.0.0.1:4222`, unchanged PID. The clone uses subject
prefix `production_prep_hetzner`. NATS HTTP monitoring remains disabled because
enabling it requires restarting the shared service. Prometheus discovers PWA
metrics on loopback 8000; aiohttp, nginx, node and prometheus targets are `up`.
Public `/metrics` returns 404. [Monitoring runbook](../tlf-monitoring/README.md).

`vmsh-backup.timer` runs at 00:15/08:15/16:15 Europe/Moscow, retains 14 days.
Online SQLite backups include the main DB/Zoom archive and independent analytics
store. Each snapshot is copied to a temporary directory and verified using
`PRAGMA integrity_check`; the rehearsal passed with all three synthetic receipts.
Backups are local to this server. `vmsh-analytics.timer` runs every two hours;
its first run completed with no active courses. No automatic deployment.

Source is the local `vmshpwa` snapshot, base `b9ca44aa`, plus the uncommitted
implementation recorded in `deployment-snapshot.json`. The base commit alone
does not contain the deployed identity/archive code. Frontend provenance is
`production`, release `tlfprep-20260930`, MSW/prototype disabled, with host Sentry
and S3 origins. Node 26.9.0, pnpm 11.15.1, uv 0.12.18 are pinned under toolchains.
The OS Python 3.14.4 segfaulted on a bare asyncio subprocess test; this clone
uses isolated upstream CPython 3.14.4. OS Python and existing services unchanged.

Verified: admin login/session/logout and secure cookies; TLF manifests/icons;
English landing/Student/Staff browser pages; 25 public HTTP checks, nginx/systemd checks;
real TikZ→PDF→SVG and raster→PNG→WebP; S3 put/private GET/public GET/delete of one
temporary object; signed Zoom/CRC, invalid signature rejection, exact bodies,
duplicates/unknown meeting; receipt IDs/body digest unchanged after restarting
Zoom; restore integrity; two PWA workers/one Zoom worker; four healthy targets.
Local focused suites passed, including 23 HTTP-smoke/archive tests and the
schema/first-admin regression checks.

## Host layout and operation

All paths below are relative to `/web/vmsh_tasks_bot`. Use SSH alias
`tlfprepagent` and `sudo`; the service account has no interactive login.

| Path                                                  | Purpose                                                                                                                                                         |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vmsh_tasks_bot/`                                     | Backend repository with nested frontend source                                                                                                                  |
| `vmsh_tasks_bot/creds_prod/vmsh_bot_config_prod.json` | Canonical secrets, owner `vmsh_tasks_bot`, 0600; moved from temporary `/web` file                                                                               |
| `vmsh_tasks_bot/db/`                                  | Independent product/analytics databases, WAL/locks                                                                                                              |
| `vmshpwa/current`                                     | Symlink to the current release, four applications                                                                                                               |
| `vmshpwa/immutable-assets/`                           | Append-only hashed assets for open tabs                                                                                                                         |
| `vmshpwa/runtime/`                                    | Units, transport environment, nginx/TLS, sockets, media/write                                                                                                   |
| `deploy/bin/`                                         | [build](build_source.sh), [renderer](render_server.py), [initializer](initialize.py), [backup](backup.py), [live probe](live_probe.py), [S3 probe](s3_probe.py) |
| `deploy/reports/`                                     | Build, migration, converters, nginx/systemd, HTTP/S3, live and restart proofs, no credentials                                                                   |
| `deploy/systemd/`, `deploy/config/`                   | Convenience pointers to installed runtime files                                                                                                                 |
| `backups/<UTC timestamp>/`                            | Main/analytics snapshots and integrity report                                                                                                                   |
| `toolchains/`                                         | Pinned Python/Node/pnpm/uv                                                                                                                                      |
| `tls/`, `monitoring/`                                 | Root-only pointers to certs, config, monitoring source/Grafana credentials                                                                                      |

`/etc/systemd/system` and `/etc/nginx` link inside this tree. The immutable asset
root is absolute: `current/..` would follow the symlink into the wrong release
parent. Failed asset responses use `no-store`, preventing prolonged negative
browser caching.
Release entrypoint JS/CSS URLs carry a release query, recovering clients that
cached a miss during the initial cutover while preserving fingerprinted bodies.
Certbot's existing renewal timer now has an nginx reload deploy hook linked
from `tls/reload-nginx.sh`; no certificate/private key was copied into the repo.

As root on the server:

```sh
systemctl status vmshpwa vmshzoom
journalctl -u vmshpwa -u vmshzoom
systemctl list-timers vmsh-backup.timer vmsh-analytics.timer
systemctl start vmsh-backup.service
curl --unix-socket /web/vmsh_tasks_bot/vmshpwa/runtime/zoom.sock http://localhost/health
cd /web/vmsh_tasks_bot/vmsh_tasks_bot
.venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production
```

Manual update: take a verified backup, build reviewed code with frozen locks and
production frontend provenance, stop **both** workers before the maintenance
migration, run `VMSH_RUNTIME_PROFILE=pwa-production .venv/bin/python -m vmshpwa.scripts.migrate_runtime`,
publish a new release retaining old assets, check units/nginx, start both and
rerun public HTTP checks. Preserve the host JSON and independent databases.
Use the managed Python when recreating the venv, not `/usr/bin/python3.14`.
`live_probe.py` is not a routine readiness check: it logs in and appends three
synthetic receipts. HTTP smoke is read-only.

Restore: stop both workers, take a safety snapshot, select a verified backup,
restore both SQLite files while stopped, remove only their stale WAL/SHM files,
check schema/integrity and ownership, restart and run HTTP smoke. Restoring an
older backup rolls back newer receipts; never replace DB files under live writers.

## Course attendance release (2026-10-01)

Course metadata `hasInPersonClasses` is enabled by default (migration
`0103.course_in_person_classes`). Staff course catalog → Configure →
“This course has in-person classes” applies immediately; no restart is needed
for later toggles. Enrollment preferences and all historical rows are preserved.
Disabled scopes cannot change attendance or receive new classroom operations;
ordinary material PDFs remain available. See
[acceptance and implementation](../../../vmshpwa/docs/course-attendance-settings.md).

For each manual release set `TLF_RELEASE_ID=tlfprep-YYYYMMDD-description`
when running both `build_source.sh` and `render_server.py`. This selects
a separate static release and matching Sentry/entrypoint cache version.
Take a verified main+analytics backup and retain a source rollback archive,
stop `vmshpwa` and `vmshzoom` before migration, then build from frozen locks,
run the existing guarded production migration, publish the new static release,
and start both services. Verify two PWA workers, one Zoom worker, public
HTTP/asset smoke, SQLite integrity and unchanged counts/preferences.
Do not automatically toggle any production course. Leave vmshbeget and
autodeploy untouched.

Roll back code/static to the retained source/current symlink while both services
are stopped. The runtime schema guard rejects an unknown migration head: roll back only
`0103` through yoyo while its migration source is still present, then restore
the retained source and static symlink. Retain all other migrations/history.
Avoid restoring a DB snapshot after new Zoom receipts have arrived.

Attendance release deployed: `tlfprep-20261001-attendance`, 2026-10-01.
Pre-release verified backup: `backups/20261001T091337.198003Z`.
Proofs, source rollback archive and previous static target are retained in
`deploy/releases/tlfprep-20261001-attendance/`. Migration preserved two courses,
16 enrollments/preferences and three Zoom receipts; all existing courses were
enabled at release time. Main DB integrity, two PWA workers, one Zoom worker, unchanged shared
NATS PID and public HTTP smoke passed. Public landing and Staff sign-in render
TLF identity in English. The maintenance build leaves the secret JSON untouched.
Authenticated catalog verification passed for both courses; the live Staff
course-settings dialog displayed the new checked checkbox. The browser admin
session was supplied by the owner. After verification the owner explicitly
requested all prep courses to have no in-person classes: TLF Math Club and
TLF Physics Club were both disabled through the audited Staff UI. New course
defaults stay enabled. Existing enrollment preferences/history remain intact.

## Current PWA consolidation — 2026-10-01

Both production portals now use the current PWA code at `0926b9ea`, including
English/mixed LaTeX, localized problem headings, branding, course attendance
settings and the cold-start maintenance recovery fix. Current branches were
already ancestors of `vmshpwa`; historical experimental branches were excluded
at the owner's request. Documentation-only follow-ups do not require a TLF
runtime restart or rebuilding this retained production artifact.

TLF release: `tlfprep-20261001-consolidated-0926b9ea`. The guarded manual cutover
retains the source/runtime snapshot under
`deploy/releases/tlfprep-20261001-consolidated-a7bccbc1` (the directory records
initial preparation; the activated artifact is from `0926b9ea`). Fresh backups
`20261001T110948.589235Z` and `20261001T110957.296089Z` passed integrity. All
course flags, enrollment rows and three raw Zoom receipts were compared while
writers were stopped and remained identical. Both courses stay online-only.
Existing secret configuration is preserved. Shared NATS was not restarted.

An initial internal health probe lacked the required trusted proxy chain and
triggered the prepared source/runtime/static rollback. Health checks through
nginx passed; the corrected direct socket probe uses the same forwarding
headers as nginx and does not weaken backend security:

```sh
curl --fail --unix-socket /web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.sock \
  -H 'X-Forwarded-For: 127.0.0.1' \
  -H 'X-Forwarded-Host: prep.leaders.tech' \
  -H 'X-Forwarded-Proto: https' \
  http://localhost/student/api/v1/health
```

VMSh was updated by the main-branch webhook after TLF verification. Initial
static release: `0926b9ea9c41-20261001111130`. Before/after backups
`vmsh-before-deploy-20261001111229.sqlite3` and
`vmsh-after-deploy-20261001111306.sqlite3` have identical enrollment digests,
1519 enrollments and 34498 result rows; schema contains 75 migrations and the
existing VMSh course remains enabled for in-person classes. Student/Family
manifest proxy locations were added to the live nginx configuration with a
retained copy and successful `nginx -t` before reload. Telegram remains active.

Validation on both live portals: 25 read-only public HTTP checks each,
authenticated Staff overview/catalog/settings, correct VMSh/TLF identities and
English navigation. VMSh published PWA preview shows 11 English `Problem`
headings and all six figures load; authored Russian content stays intact.
All 182 JS/CSS URLs captured before cutover still return
HTTP 200 with the correct MIME types. Five VMSh/four TLF Prometheus targets are
up with empty scrape errors; post-cutover backend 5xx increase is zero over one
minute. NATS PIDs are unchanged. No synthetic Zoom receipts or submissions were
written into production by these checks. All 15 maintenance recovery scenarios
and 6 Family context scenarios passed in three browsers without retries before
cutover; see [integration evidence](../../../vmshpwa/dev/development-plan/23-pilot-deployment.md#2026-10-01--consolidation-and-two-portal-rollout-complete).


## Receipt lookup index — 2026-10-01

Migration `0105.pwa_recheck_receipt_lookup` is deployed from `0a05b685` on
both portals; independent figure migration 0104 is excluded. VMSh used its
main-branch webhook. TLF used a reviewed manual script with a fresh verified
backup, stopped PWA/Zoom/analytics writers, explicit production migration and
performance guard, exact all-product-table digest comparison, unchanged
credentials/static/NATS, health checks and 25 public read-only HTTP checks.

TLF deployment record and executable rollback script:
`/web/vmsh_tasks_bot/deploy/releases/recheck-index-0a05b685c044-20261001T120604Z/`.
The script drops only 0105 through yoyo before restoring the previous source;
it never replaces a production DB. Backups before/after:
`20261001T120604.531651Z` / `20261001T120612.278270Z` (integrity ok, three raw
Zoom receipts preserved). Both hosts have 76 migrations; the VMSh historical
lookup selects 714 answers in 15 ms using the new index. Shared NATS and the
existing frontend releases are unchanged. Documentation-only source updates
need no worker restart or frontend build. [Migration, regression and verification](../../../vmshpwa/docs/sqlite-admission-performance.md#receipt-lookup-index--1-october-2026).


## Course metadata language/model — 2026-10-01

Both portals run metadata release `a13c01ba`; VMSH deployed through the existing
webhook, TLF through the reviewed SSH script retained at
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261001-metadata-a13c01ba3f7f/deploy.sh`.
The TLF script builds in a separate source directory, rehearses migration 0104
on a copy, retains verified backups and compares all pre-existing product rows
while PWA/Zoom/analytics writers are stopped. Runtime configuration and
credentials remain unchanged. Current TLF static release:
`tlfprep-20261001-metadata-a13c01ba3f7f`; both databases have 77 migrations.

Both portals pass 25 public read-only HTTP checks and live authenticated course
settings show the OpenRouter model field. TLF branding is English; VMSH is
Russian. Existing course models stay `openai/gpt-5.6-luna`, TLF courses stay
online-only, and the three Zoom receipts are preserved. TLF retains two PWA
workers and one Zoom worker; shared NATS was not restarted. Detailed backups,
rollback and verification: [metadata production record](../../../vmshpwa/docs/metadata-generation.md#production--1-октября-2026).

## Inline figure editor — 2026-10-01

Both portals run figure release `3bb202815078d89c55c9a819ee3584f66fc6d8a1`.
VMSh deployed through its existing `vmshpwa` webhook; TLF through the reviewed
[SSH cutover](deploy_figure_layout.sh). Active static releases:
VMSh `3bb202815078-20261001131914`,
TLF `tlfprep-20261001-figures-3bb202815078`.
Both databases now contain 78 migrations, including
[0106](../../../migrations/0106.pwa_figure_presentation.sql).

TLF retained record and executed script:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261001-figures-3bb202815078/`.
Migration rehearsal passed on a copy before cutover. All 154 pre-existing
product table digests matched while writers were stopped; frozen legacy scales
are checked separately by [data guard](figure_layout_data_check.py).
Backups `20261001T132032.802773Z` / `20261001T132100.591519Z` passed integrity,
preserving all three raw Zoom receipts. Credentials, runtime configuration and
shared NATS remain unchanged. PWA and Zoom are active, analytics timer restored.

The script's failure handler rolls back only 0106/source/static, never replaces
the DB, and rejects that rollback if late figure edits would be lost. After a
successful rollout, any further operational rollback must inspect current drafts
and publications before applying the guarded migration down; do not restore an
old backup over current production data. Retained backups are recovery evidence.

Each portal passed 25 public read-only HTTP checks. All four public production
provenance records match the active release; Staff bundles contain the new
editor. All 182 old JS/CSS URLs retain SHA256/MIME. Authenticated editing and
publication were verified in isolated three-browser E2E before cutover; the live
smoke did not write synthetic content/events. Detailed VMSh data comparison,
backups and test results: [figure production record](../../../vmshpwa/dev/figure-layout-report.md#production--2026-10-01).
Documentation-only follow-ups do not require a TLF runtime rebuild/restart.

## Question attention — 2026-10-02

Source release `5bb8d38227df59503cfcf45ec1c489726d9bb55d` is live on both
portals. VMSh used the existing webhook; TLF used
[reviewed cutover](deploy_support_attention.sh) with
[read-only data checker](support_attention_data_check.py). Active TLF static:
`tlfprep-20261002-questions-5bb8d38227df`. Record:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261002-questions-5bb8d38227df/`.

All 154 old product tables and credentials are identical across the stopped-writer
cutover. Migration 0107 was rehearsed up/down/up on a copy; both databases have
79 migrations, current schema and quick_check ok. Backup IDs
`20261002T055732.874226Z` / `20261002T055913.981909Z` have integrity ok and preserve
three raw Zoom receipts. NATS PID 1936264 is unchanged; PWA, Zoom and analytics
are active. Backend health passed before frontend activation. Each portal passed
25 public read-only HTTP checks; all four production artifacts and public Student
attention code were verified. No synthetic production replies/submissions/Zoom
events were created.

Before reopening writers the script can roll back only 0107 and prior source/static.
After reopening writers it retains the new source/schema and restores compatible
old static, preserving all accepted receipts and Zoom events; it never restores
a backup over live production data.
[Requirement, exact releases and operational proof](../../../vmshpwa/docs/question-attention.md#production--2-октября-2026).

## Progressive task release — 2026-10-02

The owner authorized the VMSh webhook push and the manual TLF release.
[Reviewed cutover](deploy_problem_release.sh) takes the exact full commit SHA;
[read-only data checker](problem_release_data_check.py) compares all old product
columns and checks default-On release state. It rehearses migration 0108
up/down/up on a database copy, stops PWA/Zoom/analytics writers for the actual
migration, verifies backend health before static activation, preserves old
hashed assets and records backups. NATS and credentials stay in place.

Before restarting writers rollback removes only migration 0108 and restores
prior source/static. After restarting writers it retains the new source/schema
and restores compatible old static, preserving flags, audit, receipts and Zoom
events. [Requirement, tests and release record](../../../vmshpwa/docs/problem-release.md#выпуск--2-октября-2026).

Source `0b2964a80b6db6e94fa04f478848092a0f3dfdb6` is deployed on both
portals. Active TLF static: `tlfprep-20261002-problem-release-0b2964a80b6d`;
record: `/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261002-problem-release-0b2964a80b6d/`.
All 155 prior product tables/columns and credentials are identical across the
stopped-writer cutover. Migration 0108 up/down/up passed on a copy; runtime
has 80 migrations, current schema, quick_check ok and default-On baseline.
Backups `20261002T112938.930161Z` / `20261002T113019.363874Z` have integrity
ok and preserve three raw Zoom receipts. A fourth receipt arrived after writers
reopened. NATS PID 1936264 is unchanged; PWA, Zoom and analytics are active.
All four production artifacts, 25 HTTP checks and 205 old hashed asset URLs
passed; no synthetic production tasks/replies/Zoom events were created.

## File attachments — 2026-10-02

Feature source `9584efb7fd53da1eff41a1e60564d02fa7497fdc` is live on both
portals. VMSH used the existing webhook; TLF used [deploy_rich_files.sh](deploy_rich_files.sh)
and [rich_files_data_check.py](rich_files_data_check.py), without migrations.
Active TLF static: `tlfprep-20261002-rich-files-9584efb7fd53`; record:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261002-rich-files-9584efb7fd53/`.

All 157 product tables and credentials are identical across the stopped-writer
cutover; schema remains current with 80 migrations. Before/after backups
`20261002T153530.870193Z` / `20261002T153708.227404Z` have integrity ok and
851 raw Zoom receipts each. NATS PID 1936264 is unchanged; PWA, Zoom and
analytics are active, maintenance cleared. Only the public filesystem location
was added to the existing nginx configuration; nginx -t and reload passed.
Backend health preceded frontend activation; rollback retains every DB row and S3
object. Both portals passed 25 read-only HTTP checks, four-app production
provenance, new Staff client bundle checks and anonymous upload rejection.

A disposable TLF S3 attachment with a Unicode filename was fetched publicly
with the original bytes/MIME, then deleted. No production posts/submissions/Zoom
events were created. VMSH S3 probe was not run because the agent SSH user cannot
read production configuration. [Requirements and release details](../../../vmshpwa/docs/rich-file-attachments.md#production--выпуск-2-октября-2026),
[safe machine-readable proof](../../../pwa_tests/reports/rich-file-attachments/production-proof.json).

## Content publication and diagnostics — 2026-10-04

Owner explicitly authorized manual TLF deployment alongside VMSh autodeploy.
Source `9a14443fbc231617929536af3d5f17c3124eb7b9` and static
`tlfprep-20261004-content-recovery-9a14443fbc23` are active. Migration 0112
allows superseded/hidden publications to retain their schedule provenance.
[Requirements and implementation](../../../vmshpwa/docs/content-recovery-20261004.md),
[guarded manual deploy](../../../pwa_tests/reports/content-recovery-20261004/deploy-tlf.sh).

Rehearsal and stopped-writer comparison preserved all 158 product tables /
18,786 rows, including 1,421 raw Zoom receipts; only `lesson_publications` DDL
changed. Backups `20261004T093736.871407Z` / `20261004T093804.117638Z` have
integrity ok. Schema current, 25 public HTTP checks and authenticated Staff
overview passed; four production artifacts and 588 prior assets verified.
Credentials/NATS PID unchanged, PWA/Zoom/analytics active, maintenance cleared.
Compatible code rollback `43b7d2f` retains 0112; never restore an older DB after
writers reopen or remove migration history. Record and safe proof:
[production-proof.json](../../../pwa_tests/reports/content-recovery-20261004/production-proof.json).
