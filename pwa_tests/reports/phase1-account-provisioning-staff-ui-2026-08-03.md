# Phase 1: Staff account provisioning UI

Date: 2026-08-03.

## Delivered

- Admin-only `/staff/users?tab=imports` has two explicit steps: Student accounts
  first, Family accounts second.
- Each step accepts a fixed TSV shape, validates it before HTTP, calls the real
  preview/apply API and renders reviewed login adjustments and row diagnostics.
- Raw drafts are scoped by runtime namespace and Staff account in
  `localStorage`. Editing invalidates the previous preview; a draft is removed
  only after every row receives a successful creation receipt.
- Preview and receipt contracts never contain passwords, Telegram tokens or
  Family email addresses. Course enrollment remains a separate operation.

## Implementation

- Wire contracts: `packages/contracts/src/account-provisioning.ts`.
- HTTP client: `packages/app-shell/src/admin-course-client.ts`.
- TSV parser and durable draft key: `apps/staff/src/account-provisioning-tsv.ts`.
- Staff page and route: `apps/staff/src/account-provisioning-page.tsx` and
  `apps/staff/src/routes/users.tsx`.
- Storybook: `Pages/Staff/Account provisioning--Empty` and
  `Pages/Staff/Account provisioning--StudentPreviewAndApply`.

## Automated evidence

- Frontend unit: **116 files, 603 tests passed**.
- Storybook browser interaction/a11y: **54 files, 259 tests passed**.
- ESLint, Stylelint and strict TypeScript: pass.
- Production Vite build: Student, Family and Staff pass; Student and Family
  `injectManifest` service workers generated.
- `git diff --check`: pass.

Focused coverage includes TSV column counts, optional Student fields, Russian
date conversion, grade bounds, Family child/email splitting, storage-key
isolation, exact audience API paths and secret-free response parsing.

## Visual evidence

The interaction story was inspected manually on the agent Storybook at desktop
width and at 390×844. The two-step layout remained readable, had no horizontal
overlap and produced no browser warnings or errors. Visual snapshots were not
updated.

## Boundary

No real account, credential, email, Telegram call, course enrollment or
production database was used. Plaintext credential persistence is the explicit
owner-approved v1 provisioning policy; external email delivery remains outside
this increment.
