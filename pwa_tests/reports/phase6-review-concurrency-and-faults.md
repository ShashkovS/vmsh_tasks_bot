# Phase 6O proof: review concurrency and atomic failure recovery

Date: 2026-07-29

Revision: `ee9e4f0` — process-level SQLite claim race, expired-lease recovery,
completion race and deterministic rollback checks for every authoritative
completion boundary.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Two independent Python interpreters opening the same SQLite WAL database
  cannot claim the same logical review case: exactly one claim succeeds and
  both queue rows retain one shared Teacher/token pair.
- An expired lease cannot create a result, review or partial queue mutation.
  Another Teacher can reclaim the still-pending case with a new token.
- Two concurrent completion requests with different idempotency keys produce
  one authoritative review, result, evidence snapshot and audit event. The
  losing request fails closed after observing that the queue case no longer
  exists; it does not create a second result.
- Completion has one transaction boundary around the result, optional comment,
  review, optional internal reaction, evidence lock, annotations, thread state,
  queue removal and review event.
- A synthetic failure immediately after any of those nine write boundaries
  rolls back all completion effects. The original claim remains recoverable,
  thread versions/statuses remain unchanged and media does not accidentally
  inherit the reviewed-evidence immutability trigger.
- The completion checkpoint is a no-op observer in production. Tests inject a
  raising callback solely to make every rollback position deterministic; it is
  not reachable from HTTP or configuration and does not weaken the transaction.

Implementation and executable specification:

- `db_methods/pwa/reviews.py`
- `pwa_tests/integration/test_review_queue_repository.py`
  - `test_separate_processes_have_exactly_one_claim_winner`
  - `test_expired_lease_cannot_complete_and_another_teacher_recovers`
  - `test_concurrent_completion_has_one_commit_and_no_duplicate_result`
  - `test_completion_fault_at_every_write_boundary_rolls_back_atomically`

## Executable evidence

- Focused concurrency/fault selection: **12 passed**. This includes nine
  independently parametrized transaction failure boundaries.
- Complete review-queue repository file: **32 passed**.
- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for generated routes, all applications,
  packages and tool configuration.
- `make pwa-test`: **404 frontend tests passed** and **1280 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- Targeted Ruff format/check and `git diff --check`: **PASS**.
- `make pwa-schema-check`: **PASS**, 321 product objects, SHA-256
  `fda50039d639acec06428b17685b63196322a85e5c0504682ef4aa4cb10e787b`.
  This increment has no migration or schema change.

The independent-interpreter test uses the platform `spawn` context rather than
forking an already-open event loop or SQLite connection. It therefore exercises
fresh repository/connection objects against the same database file, matching
the relevant two-worker production boundary.

## Scope and remaining work

This proof accepts the SQLite review claim/completion concurrency boundary and
transaction rollback behavior. It introduces no UI, Storybook story, visual
snapshot, HTTP route or realtime contract change.

Still open in Phase 6:

- legacy reaction duplicate report, migration rehearsal and any explicitly
  approved backfill or compatibility dual write;
- correction/recheck and support-question workflows;
- proactive client handling when a lease expires while the workspace is open;
- Telegram annotation composite derivative;
- the remaining end-to-end visibility, draft-recovery and visual-acceptance
  gates listed by the authoritative phase plan.
