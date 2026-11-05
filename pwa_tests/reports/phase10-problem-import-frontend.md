# Phase 10: Staff problem workbook preview

Date: 2026-07-30

## Working result

- `/staff/problems` is an admin-only screen backed by the real preview endpoint.
- An admin selects a course, uploads one XLSX file and sees the dry-run summary and row diagnostics.
- The screen states explicitly that preview does not write to SQLite.
- Results can be filtered by action. The table renders at most the first 300 matching rows and reports the complete count.
- The browser client sends multipart data without setting its boundary manually and validates the complete response contract.
- Teachers receive the existing forbidden state; no mock-auth or Google network path was added.

## Implementation evidence

- Contract: `vmshpwa/packages/contracts/src/problem-import.ts`.
- Browser client: `vmshpwa/packages/app-shell/src/admin-course-client.ts`.
- Staff page and route: `vmshpwa/apps/staff/src/problem-import-page.tsx`, `vmshpwa/apps/staff/src/routes/problems.index.tsx`.
- Storybook interaction: `Pages/Staff--problem-workbook-preview` in `vmshpwa/apps/staff/src/pages.stories.tsx`.
- Real reference-workbook browser test: `vmshpwa/e2e/authentication.spec.ts`.

## Verification evidence

- Contract and browser-client unit tests: included in the frontend suite; 99 files / 549 tests passed.
- Storybook browser tests: 46 files / 220 tests passed.
- Production Student, Family and Staff builds passed; both PWA service workers were generated.
- Authentication E2E: 76 passed and 4 intentionally skipped across Chromium, WebKit and Firefox. The XLSX preview passed in all three browsers against the real aiohttp API and seeded SQLite.
- One unrelated Chromium cookie-refresh test needed its configured retry and then passed; this remains visible as one flaky result in the run.
- Targeted formatting, lint, typecheck and `git diff --check`: passed before commit.

Apply, receipt and rollback remain separate Phase-10 increments. This screen exposes no write action yet.
