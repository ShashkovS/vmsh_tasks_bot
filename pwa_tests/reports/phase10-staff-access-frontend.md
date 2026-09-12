# Phase 10: Staff teacher-scope editor

Date: 2026-07-30

## Working result

- `/staff/users?tab=teachers` loads the real Staff access directory and course catalogue.
- An admin can grant a teacher either a complete course or selected groups and save the complete desired scope set through `PUT /staff/api/v1/staff-members/{staffUserId}/scopes`.
- An unsaved edit is kept in audience/account/member/version-scoped browser storage and survives reload.
- A teacher does not see the teacher-access tab. A direct request to that tab remains forbidden.
- Staff capabilities remain fixed by role; this screen changes only course/group data scope.

## Implementation evidence

- Contracts and validation: `vmshpwa/packages/contracts/src/staff-access.ts`.
- HTTP client and query: `vmshpwa/packages/app-shell/src/admin-course-client.ts`.
- Local draft helpers: `vmshpwa/apps/staff/src/staff-access-draft.ts`.
- Page and real route: `vmshpwa/apps/staff/src/staff-access-page.tsx`, `vmshpwa/apps/staff/src/routes/users.tsx`.
- Storybook interaction: `Pages/Staff--teacher-course-scopes` in `vmshpwa/apps/staff/src/pages.stories.tsx`.
- Real API/browser round trip and baseline restoration: `vmshpwa/e2e/authentication.spec.ts`.

## Verification evidence

- `make pwa-lint`: passed.
- `make pwa-typecheck`: passed.
- `make pwa-test`: 98 frontend files / 546 tests and 1428 Python tests passed; 3 Python tests skipped.
- `make pwa-storybook-test`: 46 files / 219 tests passed.
- `make pwa-e2e-auth`: 78 browser cases executed across Chromium, WebKit and Firefox; the shared SQLite write runs in Chromium and restores the fixture baseline, while the two duplicate write cases are skipped in the other browsers as intended.
- Production builds of Student, Family and Staff completed as part of the authentication E2E runner; both PWA service workers were generated.
- Targeted Prettier check and `git diff --check`: passed.

No backend schema or migration was added by this frontend increment.
