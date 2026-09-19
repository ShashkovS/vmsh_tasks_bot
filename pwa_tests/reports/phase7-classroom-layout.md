# Phase 7B proof: inherited classroom layout

Date: 2026-07-29

Revisions:

- `2d84add` — in-person events, versioned layouts and inheritance rules;
- `532f9bf` — admin-only aiohttp layout API;
- `6acffa1` — strict contracts, browser client and live Staff editor;
- `c625d7b` — production-build browser proof with reload-safe local draft.

Authoritative plan:
[`vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md`](../../vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md).

## Accepted vertical slice

- An in-person event selects concrete group lessons. Its effective layout is
  resolved from the latest confirmed layout of every participating group;
  non-participating groups are not copied.
- The first edit creates an event-specific draft. Room mappings use optimistic
  versions, and confirmation makes the resulting layout historical evidence.
- One room can belong to only one group in a layout. Active rooms may remain
  unused. An archived mapped room blocks confirmation.
- The Staff `По группам` tab uses the real API and shows course/group context,
  group color, `очно/распределено`, inherited/draft/confirmed state and the
  catalog's active and archived rooms.
- Select changes stay in an account/event/version-scoped `localStorage` draft.
  Reload restores them. The browser sends one batch immediately before the
  explicit confirmation action and clears the local draft only after success.
- A changed server version does not silently overwrite the local draft. The UI
  preserves it and reports that the administrator must compare the versions.

This slice does not implement student assignment plans, classroom delivery or
oral administration.

## Implementation

- `migrations/0058.pwa_classroom_layouts.sql` and rollback;
- `db_methods/pwa/classroom_layouts.py`;
- `models/pwa/classroom_layouts.py`;
- `apps/pwa_api/classroom_layout_routes.py`;
- `vmshpwa/packages/contracts/src/classrooms.ts`;
- `vmshpwa/packages/app-shell/src/classroom-client.ts`;
- `vmshpwa/apps/staff/src/classroom-layout-page.tsx`;
- `vmshpwa/e2e/classroom-catalog.spec.ts`.

## Executable evidence

- Layout migration/domain integration covers separate previous Math and
  Physics events, a combined later event, omission of non-participating groups,
  materialization, confirmation, archived-room rejection and optimistic
  conflicts.
- `make pwa-lint`: **PASS**.
- `make pwa-typecheck`: **PASS** for all applications, packages and tools.
- `make pwa-test`: **432 frontend tests passed** and **1309 Python tests
  passed / 3 intentional skips**.
- `make pwa-storybook-test`: **41 files / 199 tests passed**, including layout
  interaction stories and the a11y error gate.
- `make pwa-build`: **PASS** for Student, Family and Staff. Student and Family
  generated their `injectManifest` service workers.
- `make pwa-e2e-classrooms`: **6/6 PASS** in Chromium, WebKit and Firefox
  against production bundles, real aiohttp and isolated seeded SQLite. Three
  scenarios cover the catalog; three cover materialize, local change, reload,
  batch save and explicit confirmation.
- `git diff --check`: **PASS**. Visual snapshots were not changed.

## Still open in Phase 7

- versioned student assignment preview/confirm, nullable age/grade/strength,
  aggregates, fuzzy search, room history and bulk move;
- Student/Family room projection and owner-scoped invalidation;
- explicit PWA/personal-Telegram delivery preview, batch and retry report;
- oral windows and result administration;
- one-time classroom import, production-size rehearsal and visual owner gate.

This proof accepts only the inherited layout vertical slice. It does not close
Phase 7.
