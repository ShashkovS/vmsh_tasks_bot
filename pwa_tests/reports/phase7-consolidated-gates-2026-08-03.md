# Phase 7 consolidated acceptance gates

Date: 2026-08-03

Authoritative plan:
[`vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md`](../../vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md).

This report reconciles the Phase-7 checklist with the implemented classroom
and online-oral vertical slices. It accepts the software boundary; it does not
claim the owner's visual approval or production cutover from the legacy print
workbook.

## Functional matrix

| Requirement | Authoritative evidence |
| --- | --- |
| Unicode-normalized catalog, archive/restore and optimistic writes | [`phase7-classroom-catalog.md`](phase7-classroom-catalog.md) |
| Multi-course event composition and inherited room-to-group layout | [`phase7-classroom-layout.md`](phase7-classroom-layout.md) |
| Deterministic assignment, history, nullable demographics, fuzzy lookup and reload-safe batch draft | [`phase7-classroom-assignments.md`](phase7-classroom-assignments.md) |
| One-time `IDd`/level/room workbook preview, atomic apply and receipt | [`phase7-classroom-import.md`](phase7-classroom-import.md) |
| Explicit immutable PWA/personal-Telegram announcement snapshot | [`phase7-classroom-delivery.md`](phase7-classroom-delivery.md), [`phase7-classroom-delivery-ui.md`](phase7-classroom-delivery-ui.md) |
| Telegram claim/send/fail/retry without Telegram in PWA-only startup | [`phase8-classroom-telegram-transport.md`](phase8-classroom-telegram-transport.md) |
| Delivery counts and partial-recipient report derived from recipient evidence | [`phase8-classroom-delivery-observability.md`](phase8-classroom-delivery-observability.md) |
| Student/Family assignment state and no Family notification | [`phase7-classroom-delivery-e2e.md`](phase7-classroom-delivery-e2e.md) |
| Production-size planner behavior and explicit v1 print boundary | [`phase7-classroom-scale-and-print-boundary.md`](phase7-classroom-scale-and-print-boundary.md) |
| Multiple oral windows and tap-only no-store join secret | [`phase7-oral-windows.md`](phase7-oral-windows.md) |
| Existing-ledger oral result, idempotency and internal reaction | [`phase7-oral-results.md`](phase7-oral-results.md) |
| Compact Staff oral workflow and reload-safe draft | [`phase7-oral-staff-ui.md`](phase7-oral-staff-ui.md) |
| Student written fallback, Staff result and final Student state | [`phase7-oral-e2e.md`](phase7-oral-e2e.md) |

## Current executable evidence

- Focused catalog/layout/assignment/import/delivery/oral Python selection:
  **40 passed** in eight xdist workers on 2026-08-03.
- Focused Zod/client Vitest selection: **8 files / 37 passed**.
- Complete PWA Python gate after the latest shared change:
  **1552 passed / 6 intentional skips in 112.81s**, eight workers. This is a
  current wall-clock observation rather than a performance SLO; an earlier run
  of the same suite took 72.83s on a less busy machine.
- Last successful production-build classroom matrix, recorded on 2026-08-02:
  **9 passed** — three flows in each of Chromium, WebKit and Firefox.
- Last successful production-build oral matrix: **3 passed**, one complete flow
  per browser engine.
- Synthetic scale rehearsal: **1500 in-person Students / 15 rooms**, balanced
  to 100 per room; recalculation plus confirmation took 0.55s under a generous
  5s regression guard.

The 2026-08-03 browser rerun did not execute a product assertion. All browser
projects failed at launch (`MachPortRendezvous`/`SIGABRT`); a separately
installed full headed Chromium also aborted in macOS crashpad before a page was
created. These 0ms launcher failures neither replace the last successful matrix
nor count as a current PASS. The API, build and test servers were shut down.

## Storybook evidence

The executable component/page matrix includes:

- `product-classrooms--catalog-active`, `--catalog-hidden-and-restore` and
  `--catalog-duplicate`;
- `--layout-inherited-typical-counts`, `--layout-materialized-and-confirm` and
  `--layout-optimistic-conflict`;
- `--plan-preview-and-confirm`, `--plan-stale`,
  `--plan-reassigning-and-no-room`, `--plan-local-draft-restored`,
  `--plan-dense-two-hundred-students`, `--public-assignment-states` and
  `--mobile-staff-layout`;
- `--delivery-preview`, `--delivery-changed-after-send`,
  `--delivery-partial-report` and `--delivery-retry-failed`;
- `product-classrooms--multi-course-inherited-event`;
- `product-oral-admission--schedule`, `--reveal-join-details`, `--no-windows`;
- `product-oral-administration--compact-round` and `--empty-roster`;
- `pages-staff--classrooms`, `--multi-course-classroom-event` and
  `--classroom-delivery`; `pages-student--oral-task`.

Interaction/a11y results are recorded in the linked slice reports. No visual
snapshot is updated by this reconciliation; final visual acceptance remains an
owner gate.

## Accepted boundary and open production gates

The Phase-7 software path is functionally ready. The following gates remain
explicit instead of being hidden behind a compatibility abstraction:

- the owner must review a real current classroom workbook preview before the
  one-time production import;
- v1 deliberately has no classroom print/export endpoint. The external
  `a11`–`a14` workbook flow remains the print source of truth until the planned
  second-version Staff print section can consume an explicitly selected
  confirmed-plan snapshot;
- the real operational sequence “early announcement → later mode changes → new
  confirmed version → final paper print” still needs an owner-run rehearsal;
- the complete classroom/oral visual matrix still needs owner acceptance;
- live-device Web Push remains a Phase-8 provider gate and is not inferred from
  the hermetic delivery tests;
- the macOS browser-launch problem must be cleared before claiming a fresh
  three-engine rerun.

Operational use and recovery are documented in
[`vmshpwa/docs/classroom-and-oral-workflow.md`](../../vmshpwa/docs/classroom-and-oral-workflow.md).
