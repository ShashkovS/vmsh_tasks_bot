# Phase 10: apply and rollback of the problem workbook

Date: 2026-07-30

## Working result

- Preview now returns a deterministic hash of the selected course, exact XLSX bytes, current SQLite comparison and row diagnostics.
- Admin-only `POST /staff/api/v1/problem-imports/apply` reparses the same XLSX and recomputes the comparison inside one SQLite write transaction.
- Only `create` and `update` rows are written. Invalid rows are skipped and counted; unchanged rows remain untouched.
- A successful response is an idempotent receipt. Repeating the exact request after a lost response returns the same receipt without a second write.
- Admin-only `POST /staff/api/v1/problem-imports/{importId}/rollback` restores updated rows and removes newly created rows in one transaction.
- Rollback stops without partial changes if any imported row was edited later or a created problem is already referenced.

## Small-layer evidence

- `db_methods/pwa/problem_imports.py` contains only short fixed SQLite reads and writes; it has no messages, HTTP status mapping or import decisions.
- `models/pwa/problem_import.py` parses and compares the workbook. `models/pwa/problem_import_apply.py` contains the apply/rollback rules.
- Russian messages and request validation stay in `apps/pwa_api/problem_import_routes.py`.
- One receipt table stores the summary and the exact before/after rows needed for rollback. No repository class, service factory, retry wrapper, queue or per-row audit table was added.

## Verification evidence

- Migration `0074.pwa_problem_import_receipts` passed up/down/up and SQLite integrity checks.
- Focused parser, hash, migration, HTTP, repeat and atomic rollback suite: 32 passed.
- `make pwa-schema-check`: passed; generated inventory contains 412 product objects.
- `make pwa-test`: 99 frontend files / 549 tests and 1439 Python tests passed; 3 Python tests skipped.
- `make pwa-storybook-test`: 46 files / 220 browser tests passed with addon-a11y in error mode.
- `make pwa-lint` and `make pwa-typecheck`: passed.
- The two warnings are pre-existing SymPy deprecation and openpyxl's notice about unsupported data-validation extensions; workbook rows are still parsed without diagnostics.
- Ruff formatting/lint and `git diff --check`: passed before commit.

The Staff confirmation/receipt UI and production-copy parity report remain separate Phase-10 increments.
