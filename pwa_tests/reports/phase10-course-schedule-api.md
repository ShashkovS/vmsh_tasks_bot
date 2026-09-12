# Phase 10: independent course and group schedule API

## Result

- Admin can read course defaults and group overrides without a global level
  context.
- A changed field is first stored as an immutable draft. The response includes
  its exact ETag and, for a course rule, the number of existing group lessons
  and already materialized windows affected by the proposed change.
- Confirmation is a separate version-checked action. Existing lesson windows
  remain unchanged; their saved timestamps and provenance are not recomputed.
- A group override is based on the currently active course rule for the same
  field. `inherit`, `override` and `disabled` are explicit; the submission
  cutoff cannot be disabled.
- Teachers receive `403`. SQLite statements added by this increment are plain
  read functions in `db_methods/pwa/course_schedules.py`; existing schedule
  domain operations remain the only write path.

## Verification

- Focused schedule HTTP suite: `3 passed`.
- App-factory, course-catalog and schedule regression: `43 passed`.
- Ruff on the new route, direct SQL reads and tests: passed.
- No migration or schema snapshot changed.

The connected Staff editor and production E2E evidence are recorded in
`phase10-course-schedule-frontend.md`. Lesson-window materialization remains a
separate Phase-10 increment. No visual baseline was updated.
