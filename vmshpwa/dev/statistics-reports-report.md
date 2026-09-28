# Staff statistics reports — verification, 2026-09-28

Implemented [the reporting contract](../docs/lesson-statistics.md#staff-reporting-course-summary-and-plus-matrix-2026-09-28).
The route defaults to course summary; the live matrix and existing analytics are
separate URL-addressable tabs. Review workload counts each completed verdict
event, plus one pending unit per student/problem pair. Current credit retains
corrections, partial marks and exactly one attribution channel.

## Verification

Environment: Node 26, pnpm 11.15.1, existing frozen lockfile; Python project venv.
All HTTP/E2E checks use isolated test databases and loopback servers.

- Frontend: `pnpm test` — **187 files, 950 tests passed**.
- `make pwa-typecheck` and full `make pwa-lint` passed; final changed-file
  ESLint, Stylelint and Prettier checks also passed. Formatting was scoped to
  changed files to preserve unrelated work.
- `make pwa-i18n-extract pwa-i18n-check` — complete Russian/English catalogs,
  including backend catalog validation.
- `make pwa-e2e-statistics` — **9 passed**, Chromium, WebKit and Firefox.
  The runner builds production bundles first. Tests cover tab-specific fetching,
  URL reload, switching levels without changing the lesson, 700 rendered rows,
  20 problem columns, no nested vertical scroll, no desktop horizontal overflow,
  narrow layouts, both themes, 200% zoom and keyboard navigation. Existing
  recalculation and teacher-access scenarios remain green.
- Targeted Storybook command with `vitest.storybook.config.ts` over
  `staff-statistics-page`, `staff-statistics-reports`, `staff-statistics-summary`
  — **5 passed**, including full axe checks. Representative cells include full,
  partial, rejected, empty and pending states. Large row count is exercised by E2E.
- Final backend command: pytest over `test_statistics_reports_http.py`,
  `test_lesson_statistics_http.py`, `test_phase10_staff_statistics.py`, domain
  `test_statistics_reports.py`, `test_staff_statistics.py`,
  `test_lesson_statistics.py`, and `test_e2e_runner.py` — **42 passed**.
  Covers repeated same-verdict reviews, idempotency, reviewed evidence vs pending,
  partial credit, rechecks, source attribution by verdict-event timestamp/ID,
  deleted users, scoped authorization, lesson zero and distinct student counts.
- Broad `make pwa-python-test`: 2106 passed, 6 skipped; two assertions describing
  the old E2E runner command changed with the new statistics profile. Both were
  updated and passed in the final targeted regression above. No known failures
  remain from that run.
- `git diff --check` passed.

## Performance and visual review

Read-only `EXPLAIN QUERY PLAN` inspection on the guarded E2E database confirmed
existing indexes for effective test-result lookup, live-mark cells, queued work
and review evidence. A local read of 42,008 current result facts took about
163 ms; this is a fixture measurement, not a production SLA. Each report uses a
fixed set of bulk reads, not one query per matrix cell. No index migration was
needed.

Visual inspection caught and fixed the narrow-screen sticky-header offset.
Source colors blend the existing chart tokens with foreground for accessible
contrast; letters and accessible cell descriptions also identify the source.
The following final artifacts were inspected:

| Browser | Desktop, light | Narrow, dark |
| --- | --- | --- |
| Chromium | [1440px](assets/statistics-reports/chromium-plus-light-1440.png) | [390px](assets/statistics-reports/chromium-plus-dark-390.png) |
| WebKit | [1440px](assets/statistics-reports/webkit-plus-light-1440.png) | [390px](assets/statistics-reports/webkit-plus-dark-390.png) |
| Firefox | [1440px](assets/statistics-reports/firefox-plus-light-1440.png) | [390px](assets/statistics-reports/firefox-plus-dark-390.png) |

## Delivery

No schema or configuration migration is required. Deploy the backend and Staff
bundle together through the normal process. The existing analytics response
retains its metrics for compatibility; the combined view hides pooled means,
share and distribution and counts students uniquely across levels. Telegram,
Student and Family scoring rules are unchanged. No deployment was performed.
