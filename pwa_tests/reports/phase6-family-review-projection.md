# Phase 6I proof: Family read-only submitted work and review projection

Date: 2026-07-28

Revision: `bc88e73` — child-scoped Family thread/media API, strict frontend
contract and client, shared review renderer and real-aiohttp browser coverage.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Family can read the submitted or locked written material of an explicitly
  linked child. Drafts, uploading entries and failed/pending attachments are
  not projected, even when the Family account is valid.
- Child ownership is resolved from the revalidated server-side Family session.
  A child public ID from the URL is never trusted as authority; another child
  returns `403`.
- Family media uses a dedicated `/family/api/v1/children/{studentId}/...` path
  and the Family session cookie. It does not reuse the Student route or depend
  on a Student cookie with another `Path`.
- The read-only view contains the exact submitted text and immutable WebP
  pages, public verdict/comment/reviewer metadata and non-destructive
  annotation manifests.
- Staff-only internal reactions are neither serialized by Python nor accepted
  by the strict Family Zod contract.
- Student and Family render review results and annotations through the same
  `WrittenReviewHistory` and `ReviewAnnotationViewer` implementation. The
  audience-specific media path remains outside the shared visual component.
- This increment does not add Family submission, reaction or notification
  mutations.

Implementation:

- `apps/pwa_api/written_submission_routes.py`
- `db_methods/pwa/written_submissions.py`
- `vmshpwa/packages/contracts/src/written-submissions.ts`
- `vmshpwa/packages/app-shell/src/family-written-thread-client.ts`
- `vmshpwa/packages/product/src/written-review-history.tsx`
- `vmshpwa/apps/family/src/content-page.tsx`
- `vmshpwa/apps/student/src/student-written-submission.tsx`
- `pwa_tests/integration/test_content_http_api.py`
- `vmshpwa/e2e/review-workspace.spec.ts`

## Design and interaction evidence

- Storybook story:
  `Product/Feedback--Проверенная письменная работа`
  (`product-feedback--reviewed-written-photo`).
- Its interaction proves the prominent result, actual annotated page and
  absence of Staff-only copy.
- Storybook browser/a11y gate: **40 files / 194 passed**.
- Product-owner visual snapshot acceptance remains open; no snapshots were
  updated by this increment.

## Executable evidence

- ESLint, Stylelint and workspace TypeScript: **PASS**.
- Frontend unit suite: **53 files / 396 passed**.
- Python PWA suite: **1258 passed / 3 intentional skips / 1 existing SymPy
  deprecation warning**.
- Student, Family and Staff production builds: **PASS**; Student and Family
  `injectManifest` service workers were generated.
- Focused production-build command `make pwa-e2e-review`: **3 passed**, one
  independent real-aiohttp case in Chromium, WebKit and Firefox.
- `git diff --check`: **PASS** for the accepted implementation increment.

The HTTP integration test proves that a Family draft read returns no thread,
then submits a real image, reads it through the dedicated Family media route,
rejects an unlinked child, completes an annotated Staff review and verifies
that the public projection contains no internal reaction. The browser scenario
performs the full Staff review, validates the Student projection, signs in as
the linked Family account, validates the strict Family contract and downloads
the exact WebP through the Family session.

## Still open in Phase 6

- one merged Student/Family chronology with course, group and problem
  provenance for synonymous branches;
- automatic creation of a review-queue case when a new PWA written submission
  becomes reviewable (the current Phase 6 fixture inserts the legacy queue row
  explicitly);
- Student reactions and the admin complaint/appeal view;
- historical Telegram review/reaction backfill and duplicate-resolution report;
- durable outbox dispatch for review notifications;
- correction/recheck policy and Telegram composite-PNG derivative;
- visual snapshot acceptance by the product owner.

This proof accepts the Family read-only written-review projection and its
audience boundary, not Phase 6 as a whole.
