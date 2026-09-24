# Phase 10: Staff student enrollment frontend

## Delivered

- `/staff/users` now uses the authenticated Staff API instead of prototype
  data. An admin can search students, inspect their linked accounts and edit
  the active group, allowed groups, attendance mode and enrollment status.
- Search tolerates case, `ё/е`, whitespace, word order and small spelling
  mistakes across the bounded student directory.
- Every unsaved enrollment edit is stored under a versioned `localStorage`
  key. Reloading the page restores the exact edit; a successful server write
  clears it.
- Empty search values are omitted from the URL. Non-empty `q`, `student` and
  `course` state remains shareable through validated TanStack Router search
  parameters.
- The E2E classroom seed now creates the required active group-access row for
  every synthetic enrollment. Runtime code does not compensate for invalid
  fixture data.

## Boundaries

- The frontend adds two concrete methods to the existing Staff client. It does
  not add a repository, service locator or generic request abstraction.
- Search and local-draft handling are small pure helpers with direct unit
  tests.
- The real SQLite write uses a dedicated synthetic classroom student so that
  parallel browser projects never mutate the baseline Student persona.

## Proof

- Contract and client tests:
  `packages/contracts/src/admin-student-enrollments.test.ts` and
  `packages/app-shell/src/admin-course-client.test.ts`.
- Search and draft tests:
  `apps/staff/src/student-directory-search.test.ts` and
  `apps/staff/src/student-enrollment-draft.test.ts`.
- Storybook: `pages-staff--student-course-access`, including interaction
  coverage for fuzzy search, group selection, local draft and save callback.
- Manual visual inspection on the agent Storybook (`6106`): desktop and
  mobile-light; no browser console errors.
- `make pwa-lint`: passed.
- `make pwa-typecheck`: passed.
- `make pwa-storybook-test`: `217 passed`.
- `make pwa-test`: `540` frontend tests passed; `1420` PWA Python tests passed
  and `3` skipped.
- `make pwa-e2e-auth`: `70 passed`, `2 skipped` across Chromium, WebKit and
  Firefox. The skips are the intentionally Chromium-only shared-SQLite write.
- Production builds for Student, Family and Staff passed inside the E2E gate;
  both PWA service workers were generated through `injectManifest`.
