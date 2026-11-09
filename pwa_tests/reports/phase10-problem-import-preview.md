# Phase 10: preview of the legacy problem workbook

Date: 2026-07-30

## Working result

- Admin-only `POST /staff/api/v1/problem-imports/preview` accepts one XLSX file and an explicit course.
- The parser reads only the legacy sheets `Задачи` and `Старые`; formulas are treated as cell data and are never executed.
- All 14 legacy problem fields are normalized with the current `PROB_TYPE` and `ANS_TYPE` values.
- The response reports every row as `create`, `update`, `unchanged`, or `invalid` without changing SQLite.
- Group codes are resolved only inside the selected course. Duplicate natural keys, unknown groups, malformed numbers/types and invalid custom regexes are explicit row diagnostics.

## Layer boundary

- `db_methods/pwa/problem_imports.py` contains three short read-only SQL functions.
- Workbook parsing and dry-run comparison live in `models/pwa/problem_import.py` and do not know about connections or HTTP copy.
- Russian diagnostic text and HTTP status mapping live only in `apps/pwa_api/problem_import_routes.py`.
- This increment adds no factory, repository class, migration, retry loop, write path, or background task.

## Characterization evidence

The checked-in reference workbook `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx` is parsed successfully:

- `Задачи`: 816 data rows;
- `Старые`: 997 data rows;
- parser diagnostics: 0.

The workbook remains read-only. Its rows are not copied into fixtures or reports.

## Verification evidence

- Focused parser and real aiohttp/SQLite tests: 7 passed.
- `make pwa-test`: 98 frontend files / 546 tests and 1435 Python tests passed; 3 Python tests skipped.
- Ruff lint and format checks: passed.
- `git diff --check`: passed before commit.

The apply/receipt/rollback path and Staff upload UI remain the next Phase-10 increments.
