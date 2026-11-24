# Phase 10: Staff student scopes

## Delivered

- `GET /staff/api/v1/student-enrollments` now returns only enrollment rows whose
  active course/group is covered by the authenticated teacher's current
  `staff_scopes`. A global admin still receives the complete directory.
- Teacher responses omit web-account and family-account details. The Staff page
  keeps those fields admin-only.
- A teacher may change only `activeGroupId`, and only when both the current and
  target groups are in the teacher scope and the target is already allowed for
  the student. Attendance mode, enrollment status and allowed-group membership
  remain admin-only. Unauthorized mutations return `403`.
- The teacher view does not request the admin-only course catalog. Its group
  selector uses the allowed groups already present in the scoped enrollment.

## Implementation boundary

- Storage code gained one parameterized SQL scope clause and exposes the
  already-selected internal group ID. It contains no permission decisions,
  user-facing copy or new repository/factory layer.
- Authorization stays in the existing HTTP route and existing immutable
  principal. UI restrictions mirror the server checks but are not trusted for
  authorization.

## Proof

- HTTP integration:
  `pwa_tests/integration/test_phase10_admin_enrollments.py` covers scoped reads,
  hidden account links, forbidden admin-field changes, a forbidden target group
  and a permitted active-group change with the teacher recorded as actor.
- Storybook: `pages-staff--teacher-scoped-student-access`, with interaction
  checks for hidden private fields, disabled admin controls and active-group
  editing.
- E2E: the real `/staff/users` teacher flow passes in Chromium, WebKit and
  Firefox.
- `make pwa-lint`: passed.
- `make pwa-typecheck`: passed.
- `make pwa-storybook-test`: `218 passed`.
- `make pwa-test`: `540` frontend tests passed; `1421` PWA Python tests passed
  and `3` skipped.
- `make pwa-build`: passed for Student, Family and Staff; both PWA service
  workers were generated through `injectManifest`.
- `make pwa-e2e-auth`: `73 passed`, `2 skipped` across Chromium, WebKit and
  Firefox. The existing gateway shutdown race may still log
  `AssertionError: transport is not None`; it does not fail a scenario and is
  outside this increment.
