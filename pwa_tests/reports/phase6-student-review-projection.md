# Phase 6H proof: Student review result and immutable annotation viewer

Date: 2026-07-28

Revision: `d9905db` — Student-visible review projection, shared read-only
annotation surface and real-aiohttp acceptance coverage.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- A completed written review is projected into every concrete Student thread
  whose submitted entry formed part of the immutable evidence snapshot.
- Synonymous submissions remain stored separately. The projection preserves the
  review ID, target problem ID and the exact evidence entry IDs visible in each
  concrete branch; it does not copy or merge submissions, results or verdicts.
- The Student contract includes the verdict, public comment, reviewer, source,
  completion time and complete annotation manifests. Staff-only internal
  reactions are not queried, serialized or accepted by the strict Zod schema.
- Annotation manifests are accepted only when their evidence entry and source
  attachment belong to the visible concrete thread. A combined review may
  therefore expose the same review in two branches while showing each branch
  only its own evidence and annotations.
- Student renders the latest result prominently and earlier results in reverse
  chronology. Each manifest is drawn over the original submitted media path;
  the immutable WebP is never rewritten.
- Staff editing and Student/Family read-only rendering use one image/SVG
  geometry implementation, including rotation, normalized coordinates, zoom
  and semantic annotation colors.
- The viewer supports 100–300% zoom, resets both scale and scroll origin, and
  repeats text annotations as accessible text outside the decorative SVG.

Implementation:

- `db_methods/pwa/written_submissions.py`
- `vmshpwa/packages/contracts/src/written-submissions.ts`
- `vmshpwa/packages/product/src/review-annotation-surface.tsx`
- `vmshpwa/packages/product/src/review-annotation-editor.tsx`
- `vmshpwa/packages/product/src/verdict-registry.ts`
- `vmshpwa/apps/student/src/student-written-submission.tsx`
- `pwa_tests/integration/test_review_queue_repository.py`
- `vmshpwa/e2e/review-workspace.spec.ts`

## Design and interaction evidence

- Storybook story:
  `Product/Review annotation--Read Only Student View`
  (`product-review-annotation--read-only-student-view`).
- The interaction proves rotation, zoom, reset and accessible text content.
- The story was manually inspected in agent Storybook on desktop at port 6106.
  That inspection found that reset restored the scale but retained the old
  scroll offset; the shared surface now resets both axes when zoom returns to
  100%, and the corrected baseline was inspected again.
- Storybook browser/a11y gate: **40 files / 193 passed**.

## Executable evidence

- ESLint, Stylelint and workspace TypeScript: **PASS**.
- Frontend unit suite: **52 files / 393 passed**.
- Python PWA suite: **1257 passed / 3 intentional skips / 1 existing SymPy
  deprecation warning**.
- Student, Family and Staff production builds: **PASS**; Student and Family
  `injectManifest` service workers were generated.
- Focused production-build command `make pwa-e2e-review`: **3 passed**, one
  independent real-aiohttp case in Chromium, WebKit and Firefox.
- `git diff --check`: **PASS** for the accepted implementation increment.

The repository integration test completes one logical review over two
synonymous branches and proves that both Student threads receive the same
review identity while retaining their own evidence. The real HTTP/browser test
then completes an annotated Staff review, signs in as the Student, validates
the strict thread contract, checks the full rectangle manifest and proves that
the hidden internal reaction did not cross the audience boundary.

## Still open in Phase 6

- live Family result/thread integration using the same read-only viewer;
- the single merged Student chronology with course/group/problem provenance;
- Student reactions and the admin complaint/appeal view;
- historical Telegram review/reaction backfill and duplicate-resolution report;
- durable outbox dispatch for review notifications;
- correction/recheck policy and Telegram composite-PNG derivative;
- visual snapshot acceptance by the product owner.

This proof accepts the Student review projection and canonical read-only
annotation rendering, not Phase 6 as a whole.
