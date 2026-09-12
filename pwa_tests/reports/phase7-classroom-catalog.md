# Phase 7A proof: classroom catalog

Date: 2026-07-29

Revisions:

- `70df3da` — additive SQLite catalog and append-only audit events;
- `b67f553` — admin-only aiohttp API;
- `324cc36` — strict frontend contract and browser client;
- `c8c9f8d` — live Staff page and production-build browser scenario.

Authoritative plan:
[`vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md`](../../vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md).

## Accepted vertical slice

- Admin can list, create, rename, hide and restore rooms on the real
  `/staff/classrooms?tab=catalog` route. Teacher access is rejected with `403`.
- Display names are trimmed and compared by Unicode NFKC plus casefold. A
  duplicate such as `АКТОВЫЙ ЗАЛ` returns `409`, keeps the entered value and
  can reveal the existing room.
- Rename, archive and restore require the current `If-Match` version. A stale
  write returns `409`; hard delete is forbidden by the schema.
- The catalog uses one additive migration, small connection-taking database
  functions and direct SQL. HTTP text and status mapping stay at the aiohttp
  boundary; this slice does not introduce a repository, service or connection
  factory.
- Existing prototype tabs for the room-to-group layout and Student assignment
  plan are unchanged. They are not claimed as implemented by this proof.

Implementation:

- `migrations/0057.pwa_classroom_catalog.sql` and rollback;
- `models/pwa/classrooms.py`;
- `db_methods/pwa/classrooms.py`;
- `apps/pwa_api/classroom_routes.py`;
- `vmshpwa/packages/contracts/src/classrooms.ts`;
- `vmshpwa/packages/app-shell/src/classroom-client.ts`;
- `vmshpwa/apps/staff/src/classroom-catalog-page.tsx`;
- `vmshpwa/e2e/classroom-catalog.spec.ts`.

Design and interaction references:

- `Product/Classrooms--catalog-active`;
- `Product/Classrooms--catalog-hidden-and-restore`;
- `Product/Classrooms--catalog-duplicate`;
- source: `vmshpwa/packages/product/src/classroom-planning.stories.tsx`.

## Executable evidence

- `make pwa-lint`: **PASS**.
- `make pwa-typecheck`: **PASS** for all applications, packages and tools.
- `make pwa-test`: **427 frontend tests passed** and **1306 Python tests
  passed / 3 intentional skips**.
- `make pwa-storybook-test`: **41 files / 199 tests passed**, including the
  existing catalog interaction stories and a11y gate.
- Production build: **PASS** for Student, Family and Staff; Student and Family
  generated `injectManifest` service workers.
- `make pwa-e2e-classrooms`: **3/3 PASS** in Chromium, WebKit and Firefox
  against production bundles, real aiohttp and an isolated seeded SQLite.
  The flow proves trim, create, Unicode/case duplicate, reveal, rename, archive
  and restore. MSW and external services are not used.
- Focused E2E-runner specification: **8 tests passed**.
- `git diff --check`: **PASS**. Visual snapshots were not updated.

## Still open in Phase 7

- versioned inherited room-to-group layouts for an in-person event;
- Student assignment preview, local reload-safe draft, fuzzy search, history,
  atomic confirm and invariants;
- explicit PWA/Telegram classroom-delivery preview and retry report;
- Student/Family classroom projection and owner-scoped updates;
- oral-administration workflow and the complete Phase 7 visual owner gate.

This proof accepts only the durable catalog vertical slice. It does not close
Phase 7.
