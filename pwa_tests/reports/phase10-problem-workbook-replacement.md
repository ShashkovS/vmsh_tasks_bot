# Phase 10: replacement of the legacy problem workbook workflow

Date: 2026-08-02

## Result

The Staff workflow for the legacy sheets `Задачи` and `Старые` is implemented
end to end. It does not call Google and does not require Telegram credentials:

1. An admin selects a course and uploads the current XLSX workbook.
2. Staff shows a read-only row-by-row preview with create/update/unchanged/invalid
   counts, diagnostics and advisory synonym candidates.
3. Apply reparses the reviewed bytes and rechecks the SQLite state inside one
   transaction. Invalid rows are skipped without partial writes.
4. The stored receipt is idempotent. A guarded rollback restores updated rows
   and removes unreferenced rows created by the import.
5. The existing metadata grid remains the native small-edit path after import.

This closes the software replacement for these two sheets. It does **not**
declare the operational cutover complete: the owner must still use the Staff
path for a real weekly cycle, name the cutover date, and retain the legacy
loader as a documented read-only fallback until that acceptance.

## Authoritative implementation

- HTTP: `apps/pwa_api/problem_import_routes.py`.
- SQLite operations: `db_methods/pwa/problem_imports.py`.
- Parsing/comparison: `models/pwa/problem_import.py`.
- Apply/rollback rules: `models/pwa/problem_import_apply.py`.
- Staff page: `vmshpwa/apps/staff/src/problem-import-page.tsx` and route
  `vmshpwa/apps/staff/src/routes/problems.index.tsx`.
- Strict browser contract/client:
  `vmshpwa/packages/contracts/src/problem-import.ts` and
  `vmshpwa/packages/app-shell/src/admin-course-client.ts`.
- Native follow-up editing: `GET/PUT
  /staff/api/v1/group-lessons/{group_lesson_id}/metadata-grid` and
  `vmshpwa/packages/product/src/metadata-grid.tsx`.

## Evidence chain

- [Preview and workbook characterization](phase10-problem-import-preview.md).
- [Transactional apply, idempotency and rollback](phase10-problem-import-apply.md).
- [Staff confirmation and receipt UI](phase10-problem-import-frontend-apply.md).
- [Real workbook/SQLite parity](phase10-problem-import-parity.md) and its
  [machine-readable aggregate](phase10-problem-import-parity.json).
- [Synonym candidates without physical merge](phase10-problem-import-synonym-candidates.md).

The protected-copy rehearsal read all 1,813 rows from the real workbook and
reported 1,813 unchanged rows, zero creates, zero updates and zero diagnostics.
The source `db/vmsh.db` was not modified.

## Browser and interaction proof

- Storybook `Pages/Staff--ProblemWorkbookPreview` covers file selection,
  diagnostics, synonym candidates, explicit apply, receipt and rollback.
- Production-build Playwright runs the real 1,813-row preview in Chromium,
  Firefox and WebKit against aiohttp and seeded SQLite.
- The reversible apply/rollback mutation runs once in Chromium because the
  browser projects intentionally share one seeded database; backend tests cover
  concurrent/idempotent/atomic behavior independently.
- Google and Telegram network access are absent from the workflow.

## Remaining operational gate

- Run one current weekly problem-configuration cycle through Staff.
- Record the owner, date, workbook fingerprint, receipt and rollback command.
- Switch the old problem loader to manual read-only fallback for the agreed
  observation period.
- Remove its Google credential dependency only after owner acceptance. Other
  Google-backed processes are separate entries in the external-process register
  and are not implicitly cut over by this result.
