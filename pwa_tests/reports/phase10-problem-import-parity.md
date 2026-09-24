# Phase 10: parity of the real problem workbook and SQLite

Date: 2026-07-30

## Result

The exact workbook `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx` was compared with an isolated copy of `db/vmsh.db` after all 69 repository migrations and a rehearsal-only mapping of the four legacy groups to `course-math-5-7`.

- SQLite integrity check: `ok`.
- Workbook rows: 1,813.
- Stored problems: 1,813.
- Create: 0.
- Update: 0.
- Unchanged: 1,813.
- Invalid rows or diagnostics: 0.

The aggregate machine-readable report is [`phase10-problem-import-parity.json`](phase10-problem-import-parity.json). It contains no names, tokens, messages or row-level problem content.

## Defect found by the rehearsal

Before the fix, the preview falsely reported 1,054 updates:

- 1,017 non-test rows differed only because legacy SQLite stores an empty answer type as `''`, while the new importer uses `NULL`;
- 23 answers entered as fractions, dates or times were converted by openpyxl to Python date/time values instead of the displayed spreadsheet text;
- two comma-separated integer sets were read as decimal numbers;
- 11 multiline fields differed only by CRLF versus LF.

`models/pwa/problem_import.py` now interprets the finite set of date/time display formats actually present in the workbook, uses the answer type to restore comma-separated numeric collections, normalizes line endings for comparison, and treats legacy blank answer type as equivalent to `NULL`. An unknown temporal format produces an invalid-row diagnostic instead of a silent conversion.

## Safety and verification

- The source database was opened only for read operations and copied before migrations; all writes were confined to `/private/tmp/vmsh-phase10-rehearsal.74IGMV/copy.sqlite3`.
- Source database fingerprint: `a9cf42cb67e9d2d614b93a43e2f413be3c93fbaacec88f1988a9a03af6bb7dc3`.
- Workbook fingerprint: `6c79d4c0f4fd6090e58be67f961f5edc352d21ff8eb584f3e56dc5297dc00df5`.
- Focused parser and real aiohttp apply/rollback suite: 12 passed.
- Full gate: 99 frontend files / 551 tests and 1,441 Python tests passed; 3 Python tests skipped.
- The reference workbook itself is a committed characterization fixture; date, time, numeric collection and legacy line-ending behavior also have synthetic regression tests.

The rehearsal did not modify `db/vmsh.db`, send Telegram messages, access Google, or use S3. It does not authorize production apply; the real Staff action still requires a fresh preview and explicit confirmation.
