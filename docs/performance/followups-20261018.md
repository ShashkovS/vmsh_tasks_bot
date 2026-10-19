# Performance/correctness follow-ups — 18 October 2026

Owner approved implementing and releasing the performance/correctness follow-ups.

## Contract and implementation

- Student selected photos must all finish preparation and durable save before
  enqueue, including keyboard Send and multiple sequential photos. Preserve
  owner/revision guards, snapshots, offline/outbox and existing image processing.
- Review sheet: migration 0121 adds only the two measured indexes; pending
  candidates follow logical aliases before expensive context. Preserve scopes,
  all mode, full counts, case CAS and evidence validation. Avoid unused per-case
  snapshots and repeat AST/overlay work within one collection request.
- Product analytics: enable existing persistent thread-owned connections with
  cancellation-safe startup/drain/close. Bounded best-effort batch ingestion must
  not queue telemetry indefinitely or hold teaching DB slots. Frontend batches
  short bursts and flushes on pagehide. Business audit writes are unchanged.
- Admission diagnostics distinguish fixed stores main/product_analytics as well
  as roles. Never use paths or identities as metric labels.
- Push timeout/connection exceptions normalize to existing transport errors;
  one provider failure must finish/retry its item and not strand the batch.
- GlitchTip Telegram digest explicitly closes SQLite connections. Keep durable
  retry/dedupe and verify bounded resources; a source-level leak fix is not proof
  that every observed OOM has been explained. Main TLF bot remains stopped.

## Implementation references

- [Composer](../../vmshpwa/apps/student/src/student-written-submission.tsx) and
  [interaction regressions](../../vmshpwa/apps/student/src/student-written-submission.test.tsx).
- [Sheet projection](../../models/pwa/review_sheet.py),
  [scoped SQL](../../db_methods/pwa/review_sheet.py),
  [request-local AST reuse](../../db_methods/pwa/review_series.py),
  [0121](../../migrations/0121.review_sheet_indexes.py),
  [parity tests](../../pwa_tests/integration/test_review_sheet.py) and
  [index lifecycle](../../pwa_tests/integration/test_review_sheet_indexes.py).
- [Bounded ingestion](../../helpers/pwa/product_analytics.py),
  [persistent lifecycle](../../main.py),
  [store](../../db_methods/pwa/product_analytics.py),
  [HTTP](../../apps/pwa_api/product_analytics_routes.py),
  [browser batching](../../vmshpwa/packages/app-shell/src/product-analytics.tsx),
  [lifecycle/batch tests](../../pwa_tests/integration/test_product_analytics_store.py).
- [Admission metrics](../../helpers/pwa/db_observability.py),
  [factory store label](../../db_methods/pwa/connection.py),
  [dashboard](../deploy/tlf-monitoring/overview.json).
- [Push adapter](../../helpers/pwa/web_push.py),
  [batch continuation test](../../pwa_tests/integration/test_phase8_push_delivery.py).
- [Digest transport](../deploy/glitchtip/telegram-webhook.py),
  [resource regression](../../tests/test_glitchtip_telegram.py).

The telemetry queue accepts at most 5120 events per worker, batches at most
200 with a 50 ms collection window, and drops on overflow/failure. Browser
batching waits 100 ms; no new event fields, retry persistence or business-audit
best-effort path was introduced. Shutdown drains before legacy task cancellation;
its five-second budget still waits for a dispatched SQLite callback to end.

## Additional gate finding: offline preparation during refresh

Firefox exposed an existing race during real cookie rotation: background
`StudentOfflinePreparation` built course/content clients without the common
refresh callback. One old-cookie content read returned 401 and ended the local
session while a successful refresh was already completing. The next test fetch
was aborted by navigation to Login. This is an application race, not a waived test.

[Preparation](../../vmshpwa/apps/student/src/prepare-offline-lessons.ts) now passes
its optional shared refresh to both default clients;
[the caller](../../vmshpwa/apps/student/src/student-offline-preparation.tsx) supplies
`authentication.refresh`. Existing clients recheck coordinated authority and retry
once, with no access/refresh-cookie lifetime or authorization changes.
[Regressions](../../vmshpwa/apps/student/src/prepare-offline-lessons.test.ts) cover
both clients' 401/recovery and permanent denial preserving the previous bundle.


## Validation and release

Six implementation commits passed the full release gate at source `806c0449`:
Python 3056 PASS / 12 SKIP, frontend 1136 PASS, Storybook 380 PASS,
E2E 156 PASS / 18 SKIP in Chromium/WebKit/Firefox; format/types/lint/i18n/build
PASS, source unchanged. Tested modes: authentication/content/realtime/live-marking/
statistics/review/submissions. Automatic retries were disabled.

Fresh server-side copies on both hosts passed 0121 up/down/up, business-table
parity, full pending/all response parity and scoped index SEARCH plans. Temporary
copies were removed. These benchmarks do not establish production tail latency.
Owner authorized one release on VMSH and TLF; deployment receipts remain local.
