# Peak read admission — 19 October 2026

Owner approved fixing the measured multi-second interactive read queue. Work is
based on deployed source e4b3953d; unrelated earlier work remains in its checkout.

## Scope and invariants

1. Restrict personal progress and lesson work to requested student/course/lesson
   before effective-result aggregation, preserving logical aliases and precedence.
2. Reuse bounded WorkerReadCache for personal progress/work with single-flight,
   copies, event fencing, owner/resource invalidation and bypass on lost NATS.
   Keep access checks outside every cache; legacy mutations get a short TTL bound.
3. Collapse auth miss grant reads into one admitted snapshot; preserve cookie,
   expiry, revocation and principal-integrity checks. Fast auth must not queue
   repeatedly behind the same heavy readers. Do not remove concurrency bounds.
4. Diagnose analytics startup using approved read-only access; fix the actual
   failure, expose readiness/failure/drop counters, cover recovery and shutdown.

Only measured indexes: 0123 adds a partial live_mark_cells(result_id) lookup. No changes to grading formulas,
photo processing or LLM latency. Metadata correctness and broader statistics
profiling remain separate from the read queue fix unless evidence links them.

## Verification

Parity tests for results/aliases/manual/written/test/clear/undo and scope isolation;
cache/invalidation/single-flight/failure tests; auth snapshot parity and admission
counts; realistic mixed read queue regression; source-copy SQL plans and alternating
old/new benchmarks. Run the combined release gate including authentication,
content, realtime, live-marking, statistics, review and submissions once complete.
Record measurements and release state here and in STATUS; never call deployment
smoke a peak-load performance comparison.

Status: released on VMSH and TLF from 3ddb0a8e; post-release checks passed.


## Implemented components

- `db_methods/pwa/progress.py`: course/student scope before result precedence.
- `db_methods/pwa/effective_results.py`: logical-key membership uses indexed
  IN-set lookup, avoiding repeated scans of the key set; personal candidates are
  limited to this student's result/cell sources plus requested targets.
- `db_methods/pwa/content.py`: personal work maps generated public IDs to primary
  keys with an equality recheck, and restricts alias membership to relevant
  personal ledgers. Migration 0123 avoids rebuilding a temporary result_id index on every read.
- `apps/pwa_api/personal_reads.py`: 5 s / 4096 / 32 MiB, single-flight/copies,
  owner/course/lesson fencing, disconnected bypass. Student/Family share progress.
- `db_methods/pwa/auth.py`, `apps/pwa_api/auth_service.py`: one admitted grant
  snapshot, a bounded read-only auth lane and addressed auth cache invalidation.
- `main.py`, `helpers/pwa/product_analytics.py`: retry failed optional telemetry
  startup every 30 seconds; readiness/startup failure/unavailable-event metrics.
  No automatic migration or permission changes during recovery.

Owner-run diagnostics confirm the configured analytics file currently opens as
the app identity in WAL, with correct ownership/access. The historical startup
CANTOPEN is not reproduced; retry fixes the permanent disabled state after a
transient failure. Deployment must verify `vmsh_product_analytics_ready` for all
workers and written events rather than counting successful HTTP204 as persistence.

Release gate passed on the implementation in local commit 6e952f6f: 3114 Python
(6 skipped), 1142 frontend, 384 Storybook, 159 E2E (18 skipped), Chromium, Firefox
and WebKit; format/types/lint/i18n/build all passed, source_changed=false.
Gate source digest: adef9731bf5eb883b80d859f668facb9998d5a9a8e4c97f017158b46b7382cda.
Implementation tree: 672b0f62e061c1ea4af52cc4326fb4dd00eacd7b (later evidence-only
documentation does not change tested code). Migration 0123 focused checks: 32 passed.
The tested implementation is deployed on both production hosts from 3ddb0a8e.


## Measured index decision

A private host-copy probe isolated the remaining automatic index build for the
manual result_id join: identical output hash, median 55.50 ms without the index
versus 1.05 ms with `live_mark_cells_result_idx`. This justifies migration 0123,
a partial non-unique index on non-null result_id. It changes neither records nor
precedence and is reversible. The application schema guard remains strict.

## Server-copy proof

On each host, a private SQLite backup stayed on that host and was removed after
the run. Migration 0123 up/down/up preserved all business-table fingerprints.
Eight student/course cases matched old/new response hashes (including work);
queries alternated on the same data, with the index toggled outside timing.
Six samples per variant mean the reported local p95 is effectively the maximum,
not a production tail estimate.

- VMSH progress median: 182–225 ms → 2.9–5.9 ms; personal work: 18.5–53 ms →
  2.7–4.9 ms. Scoped statistics result read: 514 → 493 ms.
- TLF progress median: 2.1–2.9 ms → 0.8–1.1 ms; work: 1.6–3.9 ms → 1.1–2.8 ms.
  Statistics result read: 5.5 → 4.6 ms.

Private receipts remain in the local report folder, outside source publication.
No authenticated production mutations or test accounts were used. These query
measurements do not establish production p95/p99 or a five-second queue bound.

## Release and recovery

Release only the tested backend tree plus index 0123; preserve current static,
NATS and settings. TLF keeps its main Telegram process stopped. Before switching,
verify backups; stop writers for migration. TLF additionally compares all business
table hashes while writers are stopped. Use the installed fixed VMSH deploy
helper and the guarded TLF backend procedure.

Rollback to e4b3953d requires reversing only migration 0123 under maintenance,
then restoring the previous code and service state; never restore an old data
snapshot over new user work. Keep maintenance on if rollback cannot be verified.
Confirm HTTP/assets, 0123, services, NATS and analytics readiness for every worker
after restart. Inspect accepted/written/error counters on natural traffic.

## Production receipt

19 October UTC: TLF finished at 18:21:36 and VMSH at 18:24:13. Both run
`3ddb0a8e8d54184c1cacd032cfa77f3a7e2bbdd0` including implementation `6e952f6f`.
Source was published using ordinary `git push`. No frontend or dependency build
was needed. Migration 0123 and quick_check passed on both production databases.

- Verified backups before/after each release. TLF's stopped-writer comparison
  preserved all business tables and configuration, with NATS PID unchanged.
- 25 read-only HTTP checks per origin; all four HTML files and 216 JS/CSS asset
  hashes per host match the preserved production static releases. No public maps.
- PWA and required companion services active, analytics timers active, maintenance
  off. TLF's main Telegram process remains inactive. No NATS restart was needed.
- `vmsh_product_analytics_ready=1` for both workers on each host; startup failures
  zero. VMSH's first six natural telemetry events were accepted and written (6/6).
  TLF had no new telemetry batch at the first readiness check; no test events were
  injected. The original historical CANTOPEN cause remains unconfirmed.
- The first VMSH metrics snapshot includes personal-cache fills/hits and zero
  waiting main/auth/write operations at that instant. This is an availability and
  instrumentation check, not a comparable-load p95/p99 or peak queue measurement.

The bounded last-100 PWA journal check found no startup/SQLite-open/NATS errors
on either host; the single traceback in TLF's sparse tail was an older
ConnectionResetError at 01:00 UTC, before this release. This is not a complete
post-release error census.

Private release logs, SQL plans, alternating timing receipts, gate summary and
source/schema/assets/metrics proofs are retained locally under
`pwa_tests/reports/peak-read-fix-20261019/`; private diagnostics were excluded from
the pushed commits. Follow up production tails under comparable natural peak
load; do not compare a quiet post-deploy period with Monday's earlier peak.
