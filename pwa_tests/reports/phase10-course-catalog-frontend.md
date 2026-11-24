# Phase 10: real Staff course/group catalog

## Result

- `/staff/courses?tab=catalog` now renders the authenticated API catalog rather
  than the static multi-course prototype.
- Admin can create and edit courses and groups, archive/restore a course and
  see real active-student counts. Loading, forbidden, error and mutation-error
  states are explicit.
- Every mutation uses the server version in an exact ETag. A conflict keeps the
  editor and its draft open instead of replacing newer server state.
- Course/group editor drafts are scoped by runtime, Staff account, entity and
  base version in `localStorage`. Reload/remount restores fields; a successful
  receipt clears only that draft. A denied storage write is visible.
- The production page reuses `CourseGroupCatalog`; the product component now
  exposes compact group edit actions and draft/active/archived states.
- Contracts are strict Zod schemas and the Staff client uses same-origin
  credentialed requests with one normal session refresh.

## Verification

- Contract, client and editor unit suite: `3 files, 6 passed`; complete frontend
  unit suite: `91 files, 521 passed`.
- Complete Storybook browser interaction/a11y suite: `46 files, 216 passed`,
  including `Product/Staff admin--Course and group catalog`.
- ESLint, Stylelint and the complete workspace TypeScript check: passed.
- Production builds for Student, Family and Staff passed; both PWA service
  workers were generated through `injectManifest`.
- Complete PWA Python/integration suite: `1408 passed, 3 skipped`; canonical
  schema inventory: `410` product objects.
- Authentication Playwright suite: `66 passed` in Chromium, WebKit and Firefox
  against the real aiohttp API and seeded SQLite. This includes creating a
  course through the real Staff catalog.
- `git diff --check`: passed.

No visual baseline was updated. Independent schedule editing and the complete
users/import workflows remain separate Phase-10 slices.
