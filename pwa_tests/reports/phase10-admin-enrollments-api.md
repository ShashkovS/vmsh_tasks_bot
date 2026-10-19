# Phase 10: Staff student enrollment API

## Delivered

- `GET /staff/api/v1/student-enrollments` returns every Student together with
  the web account, linked Family accounts, course enrollments and allowed
  groups. The intended population is about 1500 students, so the first version
  deliberately returns one sortable snapshot instead of adding pagination.
- `PUT /staff/api/v1/course-enrollments/{enrollment_public_id}` lets an admin
  change the active group, allowed groups, attendance mode and enrollment
  status as one optimistic update.
- Teacher access is rejected with `403`; stale versions return `409`; invalid
  course/group combinations return `422`.
- Group, mode and status changes are recorded separately in
  `course_enrollment_events`. Group-access history remains append/close only.
- A successful change invalidates the affected Student and Family accounts and
  the open Staff directory. SQLite remains authoritative if fan-out fails.

## Boundaries

- Database functions in `db_methods/pwa/admin_enrollments.py` contain direct,
  short SQL operations only.
- Desired-state validation and diff calculation live in the pure
  `models/pwa/admin_enrollment.py` rule.
- Russian response text stays at the aiohttp boundary in
  `apps/pwa_api/admin_enrollment_routes.py`.
- This increment reuses the existing PWA database runtime. It adds no factory,
  repository, retry layer, schema migration or general-purpose abstraction.

## Proof

- Pure rules: `pwa_tests/test_admin_enrollment.py`.
- Audience-scoped realtime fan-out:
  `pwa_tests/test_admin_enrollment_invalidation.py`.
- Authenticated HTTP, database history, optimistic conflicts and legacy
  single-course compatibility:
  `pwa_tests/integration/test_phase10_admin_enrollments.py`.
- Focused result: `9 passed` on 2026-07-30.
- Canonical `make pwa-test`: `527` frontend tests passed; `1420` PWA Python
  tests passed and `3` skipped.

The Staff page and browser E2E are a separate vertical slice and are not
claimed by this proof.
