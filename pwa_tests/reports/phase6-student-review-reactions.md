# Phase 6M proof: Student reactions to completed reviews

Date: 2026-07-29

Revision: `d73447a` — persisted Student reaction state, immutable history,
Student/Family projection, owner-scoped realtime delivery and the interactive
Student control.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Each completed `submission_review` has at most one current Student reaction.
  The allowed written-reaction IDs are `0` (understood), `1` (unclear) and `2`
  (disagreement). Different reviews of the same problem retain independent
  reactions.
- The reviewed Student is the only actor allowed to create, change or clear
  the reaction. A one-hour edit window is anchored to review completion and an
  optimistic `expectedVersion` rejects stale tabs.
- Clearing is a tombstone update, not a row deletion. Every selected, changed
  and deleted state has an immutable append-only event with the matching state
  version. Database triggers protect ownership, reaction type, monotonic
  versions, edit-window timestamps and event immutability.
- Existing legacy `reactions` rows are deliberately untouched. Their ambiguous
  relationship to historical checks requires a separate rehearsal before any
  backfill or dual write.
- Student and linked Family thread projections expose the current Student
  reaction. Family sees it read-only. Internal Teacher reactions remain absent
  from both projections.
- Realtime invalidation is account-scoped: the owner Student and linked Family
  accounts refetch affected threads. The future reaction-inbox resource is sent
  only to active global-admin Staff accounts, never as a Staff-wide event to
  ordinary teachers.
- The Student control sits under its concrete verdict. It supports selection,
  replacement and clearing; mutation errors trigger an authoritative thread
  refetch instead of preserving a possibly stale optimistic state.

Implementation:

- `migrations/0055.pwa_submission_review_student_reactions.sql`
- `db_methods/pwa/reviews.py`
- `db_methods/pwa/written_submissions.py`
- `apps/pwa_api/review_routes.py`
- `apps/pwa_app.py`
- `vmshpwa/packages/contracts/src/written-submissions.ts`
- `vmshpwa/packages/app-shell/src/written-submission-client.ts`
- `vmshpwa/packages/product/src/written-review-history.tsx`
- `vmshpwa/apps/student/src/student-written-submission.tsx`
- `vmshpwa/e2e/review-workspace.spec.ts`

## Storybook evidence

- `product-feedback--reviewed-student-reaction`: editable reaction attached to
  one concrete review, including select and clear interaction coverage.
- `product-feedback--family-student-reaction`: the linked Family read-only
  projection.
- Storybook browser tests: **40 files / 196 tests passed**; accessibility
  violations remain errors.
- Visual snapshots were not updated and still require owner review before an
  accepted baseline changes.

## Executable evidence

- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for route generation, all applications,
  shared packages and tool configuration.
- `make pwa-test`: **400 frontend tests passed** and **1267 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- Repository and migration tests cover ownership, the exact reaction type,
  optimistic conflicts, the one-hour window, no-op replay, tombstones,
  append-only events and forbidden physical mutation.
- HTTP tests cover strict request bodies, hidden foreign reviews, set/change/
  delete, stale versions, Student and Family projections and account-scoped
  cursor advances.
- Realtime unit coverage proves exact Student, Family and global-admin account
  targets and proves that no Staff-wide reaction event is published.
- `make pwa-schema-check`: **PASS**, 321 product objects, SHA-256
  `fda50039d639acec06428b17685b63196322a85e5c0504682ef4aa4cb10e787b`.
- `make pwa-build`: **PASS** for Student, Family and Staff. Student and Family
  generated their `injectManifest` service workers.
- `make pwa-e2e-review`: **3 passed** in Chromium, WebKit and Firefox against a
  real seeded aiohttp/SQLite runtime without MSW. The flow completes a Staff
  review, sets Student reaction `2`, verifies its Student projection, receives
  the linked Family WebSocket invalidation and verifies the Family projection.
- `git diff --check`: **PASS**.

Known non-blocking build output remains unchanged: the Student chunk-size
warning and the Workbox/Rolldown `inlineDynamicImports` deprecation.

## Still open in Phase 6

- admin reaction/appeal inbox API and Staff interface;
- historical legacy-reaction duplicate report, migration rehearsal and any
  explicitly approved backfill or compatibility dual write;
- oral-review reactions;
- merged synonymous timelines and combined review presentation with complete
  provenance;
- durable batched result notifications and correction/recheck policy;
- visual acceptance by the product owner.

This proof accepts persisted written-review Student reactions and their
Student/Family delivery boundary, not Phase 6 as a whole.
