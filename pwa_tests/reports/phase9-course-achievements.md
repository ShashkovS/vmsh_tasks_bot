# Phase 9: initial course achievements

## Result

- Migration `0073.pwa_course_achievements` adds the small course-scoped earned
  ledger and three versioned definition codes.
- The initial rules are deliberately fixed and readable: first submission,
  first accepted task and first written submission.
- `db_methods/pwa/course_achievements.py` only reads facts and stores earned
  rows. `models/pwa/course_achievements.py` contains the three business rules.
- Russian labels live in the Student UI, not in SQL or the data-access module.
- Re-running the maintenance command is idempotent. A historical earlier fact
  moves `earned_at` backwards; it never duplicates an achievement.
- Every achievement is scoped to one course and exposes no ranking or group
  comparison.

Streak and completed-lesson milestones remain follow-up Phase-9 rules; they do
not require a schema change.

## Verification

- Migration up/down/up and seeded definition codes: `1 passed`.
- Pure earliest-fact rules: `2 passed`.
- Analytics/achievement command, HTTP and Family boundary selection: `9 passed`.
- Frontend unit suite: `85 files, 510 tests passed`.
- Contracts and Student TypeScript checks: passed.
- Student production build and `injectManifest` service worker: passed.
- Agent-profile smoke migrated 44 revisions and recalculated 2 lesson points.

No visual baseline was updated.
