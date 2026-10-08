# Phase 10: Staff course/group catalog backend

## Result

- Admin can list the real active season with its courses, groups and current
  active-student counts.
- Admin can create and versioned-edit courses and groups. Archiving a group
  also updates the legacy `is_active` compatibility field.
- Course codes are normalized to lowercase and remain unique within a season;
  group short codes are normalized to lowercase and remain unique within a
  course. Existing Cyrillic group codes remain valid.
- Teacher access is rejected with `403`; duplicate identities and stale
  optimistic versions return `409`.
- The increment reuses the existing Phase-1 tables. It adds no migration,
  repository, factory or connection abstraction.
- `db_methods/pwa/course_catalog.py` contains only direct SQLite reads and
  writes. Validation and Russian error text stay at the aiohttp boundary in
  `apps/pwa_api/admin_course_routes.py`.

## Verification

- Focused aiohttp integration suite: `3 passed`, including real counts,
  teacher denial, strict input, duplicate code, stale version and legacy
  `is_active` synchronization.
- App-factory, Family-course and Telegram-binding regression: `17 passed`.
- Ruff on the route, SQL module, app wiring and tests: passed.
- `git diff --check`: passed.

The Staff page is still a prototype in this backend-only increment. Its real
contract/client/page wiring is the next Phase-10 slice. No visual baseline was
updated.
