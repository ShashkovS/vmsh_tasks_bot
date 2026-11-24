# Phase 9: personal activity and Family course history

## Result

- Student progress renders the existing per-course activity rows as a compact
  calendar instead of a technical list of dates.
- Calendar intensity represents only the number of problem items worked on that
  day. It contains no cohort, rank, percentile or group comparison.
- The visual grid has a readable date-by-date equivalent and remains locally
  scrollable when a season contains many weeks.
- Family course cards expose the same child's per-course lesson history and
  activity behind one collapsed disclosure. Different children and courses keep
  their existing query scopes.
- No schema, SQL or API change was needed for this increment.

## Verification

- Full frontend unit suite: `87 files, 513 tests passed`.
- Activity calendar and Family form isolated checks: `2 passed`.
- Storybook browser interaction for `Product/Progress--activity`: `5 passed`
  in the progress story file.
- Product, Student and Family TypeScript checks and scoped ESLint: passed.
- Student and Family production builds passed; both `injectManifest` service
  workers were generated.
- Manual browser inspection covered the expanded date list and the compact
  visual grid. No visual baseline was updated.
- `git diff --check`: passed.
