# Phase 6C proof: atomic written review completion

Date: 2026-07-28

Revisions:

- `7c52472` — immutable review/evidence schema and the shared-SQLite completion
  transaction;
- `30c9f11` — authenticated Staff HTTP endpoint, owner-scoped invalidation,
  strict TypeScript contracts and Staff client;
- `7df0d81` — bounded historical migration slices and the updated deterministic
  schema inventory.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Implemented boundary

- Migration `0052.pwa_submission_reviews_evidence` adds append-only
  `submission_reviews`, exact evidence-entry/attachment rows and review events.
- Evidence triggers freeze every reviewed Student entry, attachment and media
  asset. The original `problem_id`, thread, entry, revision and attachment
  provenance remain unchanged; synonymous branches are united only by the
  immutable review snapshot.
- `PwaWrittenReviewQueueRepository.complete()` runs in one `BEGIN IMMEDIATE`
  transaction. It validates the authenticated lease owner, every queue and
  thread version and the exact evidence boundary before writing anything.
- If a Student submits or changes evidence after claim, completion fails with
  `review_thread_changed`/`review_evidence_unavailable`; verdict, result,
  comment, queue deletion and evidence locks are all rolled back.
- A combined synonym case produces one logical review. Its target is the
  problem of the latest included Student entry by server timestamp, with the
  internal ID only as a deterministic tie-break. The legacy `results` row and
  optional Teacher reply belong only to that target problem.
- Peer branches are closed but retain their own data and status history. No
  submission, attachment, discussion or result is copied between problems.
- Successful completion atomically removes every queue branch. Replaying the
  same idempotency key and canonical payload returns the same receipt even
  after queue removal; reusing the key with another payload is rejected.
- `POST /staff/api/v1/review/items/{queuePublicId}/complete` accepts a strict
  versioned manifest containing every claimed branch and its evidence. Actor
  identity and Student ownership are derived from the Staff session and DB,
  never from the request body.
- Claim and heartbeat receipts now expose public-ID-only `evidenceBranches`,
  so the browser can submit the exact manifest it reviewed.
- A committed review emits best-effort owner-scoped invalidations for all
  affected Student problem threads. Durable outbox dispatch remains a later
  Phase 6 increment.

Implementation:

- `migrations/0052.pwa_submission_reviews_evidence.sql`
- `db_methods/pwa/reviews.py`
- `apps/pwa_api/review_routes.py`
- `apps/pwa_app.py`
- `vmshpwa/packages/contracts/src/review-queue.ts`
- `vmshpwa/packages/app-shell/src/review-queue-client.ts`

## Executable evidence

- Focused repository and real-aiohttp completion suite: **12 passed**.
- Focused TypeScript contracts and Staff-client suite: **12 passed**.
- Complete frontend checkpoint: ESLint, Stylelint and TypeScript **PASS**;
  Vitest **50 files / 379 passed**.
- Complete Python checkpoint: **1241 passed / 3 intentional skips / 1 existing
  SymPy deprecation warning**.
- Deterministic schema check: **298 objects**, SHA-256
  `d9247cd66b5b23b329936aa7fc144e751193302f31f6f16c4b4d72e50ce6635d`.
- Student, Family and Staff production builds: **PASS**. Student and Family
  `injectManifest` service workers were generated successfully.
- `git diff --check`: **PASS** for the accepted code/report increment.

The repository suite covers a multi-branch synonym case, latest-target choice,
immutable evidence, idempotent replay, payload mismatch, a new Student entry
during review and full rollback on stale evidence. The HTTP suite uses real
Staff login cookies and migrated SQLite, and covers strict manifests,
confirmation without a comment, malformed bodies and owner-scoped completion.
The TypeScript suite proves cross-branch manifest validation, malformed receipt
rejection, session refresh retry and account-scoped cache invalidation.

## Intentionally still open

- persisted normalized photo annotations and their immutable renderer contract;
- internal Teacher and Student review reactions, including legacy backfill;
- correction/recheck semantics and admin complaint views;
- durable outbox delivery and full Student merged-timeline serialization;
- Staff review-workspace wiring, local draft recovery and Storybook interaction;
- multi-browser Playwright race and historical Telegram review tests.

This proof accepts the review-completion transaction and its typed transport,
not Phase 6 as a whole.
