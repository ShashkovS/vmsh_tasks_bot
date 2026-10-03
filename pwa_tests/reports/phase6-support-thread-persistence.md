# Phase 6P proof: private support-thread persistence

Date: 2026-07-29

Revision: `4309efd` — additive support-thread migration, transactional repository,
current Student/Staff scope checks, idempotent chronological replies and
deterministic schema artifacts.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- New PWA questions use `support_threads` and `support_entries`; they do not
  invent negative `problem_id` values. The existing Telegram `questions` table
  and bot behavior are unchanged in this increment.
- A new PWA thread is either a question about one exact problem in one group
  lesson or a general question about that group lesson. Database triggers prove
  that a problem belongs to the selected content source/group lesson.
- A thread is one private chronological dialogue owned by one Student. It has no
  assignee and no artificial open/closed ticket status; authorized Teachers may
  answer without claiming it.
- Creation requires the Student's current active-course access to the selected
  group. Exact historical threads remain readable by their owner after group
  access is revoked.
- Student reads/appends are owner-checked. Staff reads/appends are checked
  against current course/group scope. Replaying an old idempotency key does not
  bypass a later Staff scope revocation.
- The first creation, later Student replies and Staff replies are idempotent per
  actor. Exact concurrent retries create one entry; a changed payload with the
  same key fails closed.
- Entries are append-only. Thread identity is immutable, versions/timestamps are
  monotonic and hard deletion is forbidden. The schema reserves one optional
  submission-namespace asset and legacy provenance fields for later increments.
- Browser/API contracts, local draft UI, realtime invalidation, attachments and
  Telegram dual-write are intentionally outside this persistence-only gate.

Implementation and executable specification:

- `migrations/0056.pwa_support_threads.sql`
- `migrations/0056.pwa_support_threads.rollback.sql`
- `db_methods/pwa/support.py`
- `pwa_tests/integration/test_phase6_support_thread_migration.py`
- `pwa_tests/integration/test_support_thread_repository.py`

## Executable evidence

- Support migration/repository tests: **6 passed**.
- Complete migration-focused selection: **38 passed**.
- Schema inventory/support selection: **27 passed** after the Staff replay
  privacy regression was added.
- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for route generation, all applications,
  packages and tool configuration.
- `make pwa-test`: **404 frontend tests passed** and **1286 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- Targeted Ruff format/check and `git diff --check`: **PASS**.
- `make pwa-schema-check`: **PASS**, 338 product objects, SHA-256
  `d968c6a5ec83bbebc695619bc010cba850af335ea50c0698f8198fad9a7baaba`.
- The migration's exact up/down/up lifecycle passes and generated
  `schema_inventory.v1.json`, `schema_snapshot.sql` and `docs/db_structure.sql`
  were refreshed from a clean migration-head database.

## Still open in the support flow

- strict TypeScript/Zod contracts and authenticated Student/Staff HTTP routes;
- list pagination, unanswered derivation and owner-scoped realtime events;
- Student and Staff pages, reload-safe local drafts, Storybook interactions and
  three-browser production-build E2E;
- attachment upload through the existing media proxy;
- characterized Telegram dual-write/mapping to legacy `questions` and
  historical negative-problem/SOS paths;
- notification delivery after a new Student or Staff entry.

This proof accepts the durable privacy/idempotency boundary for support
conversations, not the complete Phase 6 questions experience.
