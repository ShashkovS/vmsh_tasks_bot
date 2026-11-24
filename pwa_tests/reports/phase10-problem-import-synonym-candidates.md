# Phase 10 problem-import synonym candidates

Date: 2026-07-30

## Result

The Staff XLSX preview now reports equal normalized problem titles found in
different groups of the same lesson. The preview is advisory: it does not
create `problem_synonym_groups`, add members, or rewrite submissions/results.

Normalization uses Unicode NFKC, case folding and collapsed whitespace. A
duplicate title that occurs more than once inside one group is marked as
ambiguous, so the administrator must choose one problem before a later merge.
Problem and answer types are shown but do not prevent a candidate, matching the
accepted product rule.

## Implementation

- `models/pwa/problem_import.py` — pure candidate grouping over the already
  compared workbook rows;
- `apps/pwa_api/problem_import_routes.py` — camel-case HTTP projection;
- `vmshpwa/packages/contracts/src/problem-import.ts` — strict Zod contract;
- `vmshpwa/apps/staff/src/problem-import-page.tsx` — compact review block in
  the existing preview screen;
- `vmshpwa/apps/staff/src/pages.stories.tsx` — interactive Staff story with two
  unlike task types sharing one title.

## Proof

- Python domain and real aiohttp/SQLite integration: `15 passed`;
- TypeScript contracts and HTTP client: `10 passed`;
- focused Storybook browser run for `Pages/Staff`: `18 passed`;
- `make pwa-lint`: passed;
- `make pwa-typecheck`: passed;
- `make pwa-build`: passed for Student, Family and Staff; both PWA service
  workers were generated in `injectManifest` mode;
- `git diff --check`: passed.

The integration test checks that `problem_synonym_groups` still contains zero
rows after preview. Applying or splitting a logical synonym remains a separate
Phase 10 increment.
