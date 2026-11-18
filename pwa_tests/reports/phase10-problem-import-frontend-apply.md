# Phase 10: Staff confirmation for problem workbook imports

Date: 2026-07-30

## Working result

- Staff keeps the XLSX preview read-only until an admin explicitly confirms the write.
- The confirmation shows how many problem rows will be created and updated; invalid rows are called out before the write and are skipped by the backend.
- A successful apply shows the stored import identifier and exact create/update/skip counts.
- Rollback requires a second explicit confirmation and reports completion without re-uploading the workbook.
- Changing the selected file or course invalidates the reviewed selection and requires a fresh preview.

## Contract and interaction evidence

- `packages/contracts/src/problem-import.ts` validates apply/rollback receipts and rejects inconsistent summary counts.
- `packages/app-shell/src/admin-course-client.ts` sends the exact reviewed file plus its source and preview hashes, and sends the optimistic receipt version for rollback.
- `apps/staff/src/problem-import-page.tsx` contains the two short confirmation flows and no import business rules.
- Story `Pages/Staff--ProblemWorkbookPreview` exercises preview, apply confirmation, receipt, rollback confirmation and rolled-back state.

## Verification evidence

- Frontend unit suite: 99 files / 551 tests passed.
- Storybook browser suite: 46 files / 220 tests passed with accessibility violations configured as errors.
- Production builds for Student, Family and Staff passed; both PWA service workers were generated through `injectManifest`.
- Authentication E2E: 78 passed and 6 intentionally skipped across Chromium, Firefox and WebKit.
- The real 1,813-row reference XLSX preview passed in all three browser engines.
- The reversible SQLite write ran once in Chromium because all Playwright projects intentionally share one seeded database. Running that mutation concurrently in all three engines was proven to race on the same receipt; backend atomic/idempotent/rollback behavior is covered separately in `phase10-problem-import-apply.md`.
- `make pwa-lint`, `make pwa-typecheck`, `make pwa-test`, `make pwa-storybook-test`, `make pwa-build` and `git diff --check` passed before commit.

No visual snapshots were updated.
