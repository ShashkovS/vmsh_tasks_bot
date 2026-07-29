# Phase 9: course analytics snapshot

Implemented in commits `5b584cd`, `5879bb5` and `c2223b5`, plus the API/UI
increment that includes this report.

## Result

- `migrations/0072.pwa_course_analytics.sql` stores one immutable set of lesson
  points per completed course run.
- `models/pwa/course_analytics.py` applies the current `a53` test-attempt penalty,
  simple/complex formulas, synonym projection and stable best-group choice.
- `db_methods/pwa/course_analytics.py` contains only direct SQLite reads and the
  atomic snapshot write.
- Student and Family progress responses expose only the latest completed run.
  A running or failed run is invisible.
- Student renders the existing personal `StrengthTrend`; the response and chart
  contain no cohort, rank, percentile or individual marker inside a distribution.

The calculation reads the current `problem_complexity` values maintained by the
legacy `a53` process. Re-estimating those values, the historical backfill, the
rolling window and achievements remain separate Phase-9 increments.

## Verification

- Migration up/down/up and integrity check: `1 passed`.
- Pure formula, synonym, attempt-penalty and stable-tie tests: `3 passed`.
- Analytics plus Student/Family progress integration selection: `10 passed`.
- Contract/client tests: `16 passed`.
- Contracts and Student TypeScript checks: passed.
- Student and Family production builds: passed; both `injectManifest` service
  workers were generated.

No visual baseline was updated.
