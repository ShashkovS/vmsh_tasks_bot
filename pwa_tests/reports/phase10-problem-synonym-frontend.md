# Phase 10: Staff interface for problem synonyms

Date: 2026-07-30

## Working result

- Admins can open `/staff/problems/synonyms?lesson=<course-lesson-public-id>` and
  see both unconfirmed equal-title candidates and existing synonym groups for
  the selected course lesson.
- A merge or split always opens the existing impact preview before the write.
- Splitting requires a short reason. The action remains disabled until the
  reason is present.
- The screen makes the storage rule explicit: problems, submissions, messages
  and reviews remain attached to their original problem.
- Teachers receive the standard forbidden state; the backend remains the
  authority and returns `403` for the same operation.
- A successful merge or split invalidates the Staff review projection and the
  affected Student and Family lesson/progress projections. Clients refetch the
  authoritative SQLite state.

## Implementation boundary

- `db_methods/pwa/problem_synonyms.py` only returns the additional columns
  needed by the screen.
- `models/pwa/problem_synonyms.py` groups active rows without user-facing text
  or HTTP concerns.
- `apps/pwa_api/problem_synonym_routes.py` owns wire payloads and localized
  errors.
- `packages/contracts/src/problem-synonyms.ts` validates the exact wire format.
- `packages/app-shell/src/problem-synonym-client.ts` is a direct HTTP adapter;
  no repository, factory or service layer was added.
- `apps/staff/src/problem-synonym-page.tsx` owns the page interaction.

## Proof

- focused real aiohttp/SQLite flow: `2 passed`;
- frontend unit suite: `101 files / 559 tests passed`;
- Storybook browser suite: `47 files / 223 tests passed`;
- full Python PWA regression: `1446 passed, 3 skipped`;
- ESLint and Stylelint: passed;
- strict TypeScript: passed;
- production builds: Student, Family and Staff passed; Student and Family
  generated `injectManifest` service workers;
- manual Storybook review: desktop and 390 px mobile layout, merge flow and
  required split reason checked without updating visual snapshots;
- `git diff --check`: passed.

Stories:

- `pages-staff-problem-synonyms--candidate-and-active-group`;
- `pages-staff-problem-synonyms--split-requires-reason`;
- `product-staff-data--split-confirmation-disabled`.

No visual snapshots were updated.
