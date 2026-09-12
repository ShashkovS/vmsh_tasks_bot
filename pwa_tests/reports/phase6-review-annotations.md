# Phase 6D proof: immutable normalized review annotations

Date: 2026-07-28

Revisions:

- `9fdfe98` — migration, normalized domain manifest, atomic repository
  persistence and evidence immutability;
- `b93defa` — strict aiohttp transport, Zod contracts and Staff-client
  compatibility.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Implemented boundary

- `submission_review_annotations` stores one immutable, versioned manifest per
  reviewed evidence attachment. A composite foreign key prevents annotation of
  a photo outside the exact review snapshot.
- Coordinates, sizes and stroke widths are normalized to the evidence canvas.
  The manifest records the evidence rotation (`0|90|180|270`); zoom and pan are
  intentionally absent because they are local viewer state.
- Supported persisted marks are `pencil`, `eraser`, `text`, `arrow`,
  `rectangle` and the already exposed optional `highlight`. Mark IDs and target
  attachments are unique within their scopes.
- Geometry is strict and bounded: finite 0..1 coordinates, rectangles contained
  by the canvas, non-zero arrows, 2..4096 points per stroke, at most 20,000
  stroke points and 250 marks per photo. Text is non-blank and at most 500
  characters; only semantic annotation colors are accepted.
- Canonical JSON plus SHA-256 preserves an exact renderable payload. Update and
  deletion triggers make a completed manifest append-only; the original WebP
  remains unchanged and is already frozen by the Phase 6C evidence guards.
- Annotations are part of `CompleteReviewCommand`, its idempotency digest and
  the same SQLite transaction as result, comment, evidence and queue removal.
  No separate post-verdict write window exists.
- `POST /staff/api/v1/review/items/{queuePublicId}/complete` accepts up to ten
  strict manifests and returns public annotation/attachment IDs, schema,
  rotation and mark count. Unknown fields, invalid geometry and an attachment
  outside current evidence fail before commit.
- TypeScript uses the same discriminated mark union and bounds. The existing
  review client validates the manifest before sending and rejects a malformed
  receipt at runtime.

Implementation:

- `migrations/0053.pwa_submission_review_annotations.sql`
- `db_methods/pwa/reviews.py`
- `apps/pwa_api/review_routes.py`
- `vmshpwa/packages/contracts/src/review-queue.ts`

## Executable evidence

- Focused migration/repository/real-aiohttp suite: **19 passed**.
- Focused TypeScript contract/client suite: **2 files / 12 passed**.
- Complete frontend unit checkpoint: **50 files / 379 passed**.
- Complete Python checkpoint: **1248 passed / 3 intentional skips / 1 existing
  SymPy deprecation warning**.
- Storybook browser regression: **39 files / 190 passed**.
- ESLint, Stylelint, TypeScript and production builds: **PASS**.
- Student and Family `injectManifest` service workers: **PASS**.
- Deterministic schema: **303 objects**, SHA-256
  `e8473a302eb8875406ffdd1a52251515f41862a0b589f68b9a96665e026bd99b`.
- `git diff --check`: **PASS**.

The repository test persists all six supported mark kinds, verifies exact
receipt/replay, blocks update and deletion, and proves that a foreign attachment
causes no review/result writes. Domain cases reject out-of-bounds strokes,
zero-length arrows, overflowing rectangles and blank text. The real HTTP test
claims a two-branch synonym case, completes it with an annotation and validates
the public receipt; a malformed rectangle returns
`422 review_annotation_invalid` without consuming the lease.

## Intentionally still open

- interactive Staff editor state, undo/redo and local draft recovery;
- rendering the canonical manifest in Staff/Student/Family instead of the
  earlier read-only prototype shape;
- deterministic Telegram composite-PNG derivative;
- correction/recheck policy for an already completed immutable annotation;
- reactions, complaint views, full thread serialization and Playwright review
  workspace flow.

This proof accepts annotation persistence and transport, not the visual editor
or Phase 6 as a whole.
