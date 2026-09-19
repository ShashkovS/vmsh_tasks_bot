# Phase 6G proof: non-destructive review photo annotations

Date: 2026-07-28

Revision: `16d5e7b` — live Staff photo-annotation editor, persisted review draft,
real-media E2E seed and three-browser acceptance scenario.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Exact evidence photos in the Staff review workspace have a non-destructive
  SVG annotation layer. The original submitted WebP is never rewritten.
- The editor supports pencil, eraser, text, arrow, rectangle and highlight;
  semantic red, blue, graphite and amber colors; zoom, 90-degree rotation,
  undo, redo and clear-all.
- Image and annotation canvas use one transform, so marks remain aligned while
  zooming or rotating. Coordinates are normalized and independent of the
  displayed image size.
- The canonical, Zod-validated manifest records schema version, source
  attachment ID, source dimensions, rotation and ordered marks. Completion
  sends the manifest together with the immutable evidence snapshot.
- Annotation work is part of the account/case/evidence-scoped local review
  draft. Reload restores it; successful completion clears it; failed or stale
  completion preserves it.
- Images found elsewhere in the merged conversation remain read-only. Only the
  exact evidence snapshot being reviewed can receive a verdict annotation.

Implementation:

- `vmshpwa/packages/product/src/review-annotation-editor.tsx`
- `vmshpwa/packages/product/src/review-annotation.stories.tsx`
- `vmshpwa/packages/contracts/src/review-queue.ts`
- `vmshpwa/apps/staff/src/review-workspace-page.tsx`
- `vmshpwa/scripts/seed_e2e_review.py`
- `vmshpwa/e2e/review-workspace.spec.ts`

## Design and interaction evidence

- Storybook story:
  `Product/Review annotation--Editor`
  (`product-review-annotation--editor`).
- The interaction story exercises rotation, undo/redo, zoom and pointer-drawn
  geometry, then restores a stable reviewable visual baseline.
- The story was manually inspected in agent Storybook on desktop at port 6106.
  The transformed image and SVG overlay shared the same geometry; toolbar,
  focus states and scroll boundary remained usable at 150% zoom and after a
  90-degree rotation.
- Storybook browser/a11y gate: **40 files / 192 passed**.

## Executable evidence

- ESLint, Stylelint and workspace TypeScript: **PASS**.
- Frontend unit suite: **51 files / 384 passed**.
- Python PWA suite: **1256 passed / 3 intentional skips / 1 existing SymPy
  deprecation warning**.
- Student, Family and Staff production builds: **PASS**; Student and Family
  `injectManifest` service workers were generated.
- Focused production-build command `make pwa-e2e-review`: **3 passed**, one
  independent real-aiohttp case in Chromium, WebKit and Firefox.
- `git diff --check`: **PASS** for the accepted implementation increment.

The E2E scenario uses a real WebP stored by the guarded E2E media adapter. It
draws a rectangle on the evidence photo, rotates the canvas, reloads the Staff
page, proves that the local draft survived, completes the review through the
real API and verifies the returned attachment ID, schema version, rotation and
mark count.

## Still open in Phase 6

- canonical read-only annotation rendering in Student and Family;
- Student reactions and the admin complaint/appeal view;
- historical Telegram review/reaction backfill and duplicate-resolution report;
- durable outbox dispatch for review notifications;
- correction/recheck policy and Telegram composite-PNG derivative;
- repair of unrelated full Playwright failures recorded in the Phase 6F proof.

This proof accepts Staff annotation creation and no-data-loss persistence, not
Phase 6 as a whole.
