# Phase 9: Student course settings in the real profile

## Result

- The production Student profile now uses the authenticated principal and the
  real course-enrollment API instead of prototype profile data.
- A student can change only their own active group, only to a group already
  present in `allowedGroups`, and can choose online or in-person attendance.
- The HTTP boundary validates the exact request body and optimistic version.
  The existing short enrollment transaction records the change and keeps the
  current single-course legacy fields synchronized; no schema or repository
  abstraction was added.
- The UI uses a two-step confirmation and explains the real cost of reserving
  an in-person place. Course queries are refreshed after a successful change.
- The offline decorator never queues this account-setting mutation: it is sent
  only while online, while ordinary Student drafts remain governed by their
  existing local persistence.

## Verification

- Student/Family course HTTP integration suite: `7 passed`, including Student
  ownership, allowed-group and attendance-mode persistence.
- Focused client, offline decorator and profile component suite: `3 files,
  15 tests passed`.
- App Shell and Student TypeScript checks and scoped ESLint: passed.
- Student production build and `injectManifest` service worker: passed; 107
  files were precached.
- Complete Playwright authentication/profile gate: `63 passed` in Chromium,
  WebKit and Firefox.
- `git diff --check`: passed.

No visual baseline was updated.
