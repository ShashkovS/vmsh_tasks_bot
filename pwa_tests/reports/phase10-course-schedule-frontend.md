# Phase 10: real Staff schedule editor

## Result

- `/staff/courses?tab=schedule` reads the authenticated course catalog, course
  defaults and the selected group's overrides from the real aiohttp API.
- Admin can create and separately confirm drafts for opening, hint,
  submission-cutoff and solution times. Group fields support `inherit`,
  `override` and `disabled`; the submission cutoff cannot be disabled.
- The course draft remains visible after reload together with its impact on
  existing group lessons and materialized windows. Existing lesson timestamps
  are not changed by confirming a new default.
- Editors save every input change in account-, runtime-, owner-, field- and
  version-scoped `localStorage`; only a successful server write clears that
  local draft.
- The page fetches only the selected group's schedule. It does not preload all
  group schedules.
- Contracts are strict Zod schemas. All writes carry the current ETag and keep
  the editor open when the server rejects a stale version.

## Verification

- Complete frontend unit suite: `93 files, 527 passed`.
- Complete PWA Python/integration suite: `1411 passed, 3 skipped`.
- ESLint, Stylelint and the complete workspace TypeScript check: passed.
- Production builds for Student, Family and Staff: passed; Student and Family
  `injectManifest` service workers were generated.
- Authentication Playwright suite: `66 passed` in Chromium, WebKit and Firefox
  against the real aiohttp API and seeded SQLite. The schedule scenario creates
  a course, saves a condition-publication draft and confirms it through Staff.
- No visual baseline was updated.

The browser run still prints the pre-existing transient aiohttp gateway
WebSocket assertion when a page closes during connection setup; it did not
fail or retry any test in this run.
