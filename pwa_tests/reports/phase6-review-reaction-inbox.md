# Phase 6N proof: admin review-reaction inbox

Date: 2026-07-29

Revision: `53f513e` — strict current-reaction projection, admin-only HTTP and
Staff UI, exact filters, cursor pagination and account-scoped realtime refresh.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- `/staff/api/v1/review/reactions` is available only to a global Staff admin
  with `audit.read`. An ordinary Teacher receives `403`; hiding the navigation
  item is not treated as authorization.
- The inbox combines only current, non-deleted written-review reactions:
  Student reactions `0–2` and hidden Teacher reactions `100–103`. It does not
  reinterpret legacy `reactions` rows and does not expose deleted history.
- Every row keeps its concrete review, Student, reviewer, problem, course/group,
  verdict, compact comment and exact reaction wording. Reactions are oversight
  metadata and never mutate a verdict automatically.
- Source and exact-reaction filters are strict in TypeScript and Python. A
  reaction outside the selected actor kind is rejected with `422`; an unknown
  cursor is also rejected rather than silently restarting the list.
- The list is ordered by the current reaction update time, uses opaque cursor
  pagination and exposes no SQLite or legacy numeric IDs.
- Student and Teacher changes publish the shared `review-reactions` resource
  only to active global-admin account IDs. Student/Family thread invalidations
  remain owner-scoped, and no admin inbox event is broadcast to all Staff.
- Completing a review with an internal reaction, later changing that reaction
  and deleting it all refresh an already open admin inbox. Student reactions
  also appear live without a page reload.

Implementation:

- `db_methods/pwa/reviews.py`
- `apps/pwa_api/review_routes.py`
- `apps/pwa_app.py`
- `vmshpwa/packages/contracts/src/review-reactions.ts`
- `vmshpwa/packages/app-shell/src/review-queue-client.ts`
- `vmshpwa/packages/product/src/review-reaction-inbox.tsx`
- `vmshpwa/apps/staff/src/review-reaction-inbox-page.tsx`
- `vmshpwa/apps/staff/src/routes/reactions.tsx`
- `vmshpwa/e2e/review-workspace.spec.ts`

## Storybook evidence

- `product-review-reaction-inbox--current-written-reactions`: Student and
  Teacher records, source filter and exact disagreement filter interaction.
- `product-review-reaction-inbox--empty`: no-current-reaction state.
- Storybook browser tests: **41 files / 198 tests passed**; accessibility
  violations remain errors.
- Visual snapshots were not updated and still require owner review before an
  accepted baseline changes.

## Executable evidence

- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for route generation, all applications,
  shared packages and tool configuration.
- `make pwa-test`: **404 frontend tests passed** and **1268 PWA Python tests
  passed / 3 intentional skips / 1 existing SymPy deprecation warning**.
- Contract and client tests cover strict schemas, actor/reaction consistency,
  filter serialization and malformed envelopes.
- Repository and real aiohttp tests cover admin/Teacher authorization, exact
  Student and Teacher records, current-only visibility, cross-kind rejection,
  opaque two-page traversal and absence of internal reactions from Student and
  Family projections.
- Realtime unit coverage proves that `review-reactions` invalidations contain
  an explicit admin `accountId`; completion-with-reaction advances the Staff
  cursor separately from the Staff-wide queue update.
- `make pwa-schema-check`: **PASS**, 321 product objects, SHA-256
  `fda50039d639acec06428b17685b63196322a85e5c0504682ef4aa4cb10e787b`.
- `make pwa-build`: **PASS** for Student, Family and Staff. Student and Family
  generated their `injectManifest` service workers.
- `make pwa-e2e-review`: **3 passed** in Chromium, WebKit and Firefox against a
  real seeded aiohttp/SQLite runtime without MSW. The flow proves Teacher
  `403`, initial visibility of the hidden Teacher reaction for admin and live
  arrival of the Student disagreement in an already open admin inbox.
- `git diff --check` and targeted Prettier/Ruff checks: **PASS**.

Known non-blocking build output remains unchanged: the Student chunk-size
warning and the Workbox/Rolldown `inlineDynamicImports` deprecation.

## Still open in Phase 6

- an explicit admin recheck/correction action from an inbox item;
- historical legacy-reaction duplicate report, migration rehearsal and any
  explicitly approved backfill or compatibility dual write;
- oral-review reactions;
- merged synonymous timelines and combined review presentation with complete
  provenance;
- durable batched result notifications and correction/recheck policy;
- visual acceptance by the product owner.

This proof accepts the current written-review oversight inbox and its privacy/
realtime boundary, not Phase 6 as a whole.
