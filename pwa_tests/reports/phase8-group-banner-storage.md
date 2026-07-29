# Phase 8: group banner storage and rules

## Result

- Migration `0068.pwa_group_banners` stores one group-owned display window,
  audience (`student|family|both`), priority, dismissibility and optimistic
  version. Cancellation keeps the audit row; there is no hard delete.
- Current reads use the server timestamp and an exclusive `endsAt` boundary.
- The v1 sanitizer allows only `a`, `b`, `code`, `i`; links allow only HTTPS or
  mailto and receive `noopener noreferrer`. Script content and unsafe URL
  schemes cannot reach the browser.
- Editing and cancellation require the current version. Window and audience
  rules live above the direct SQL operations.

## Proof

- `uv run pytest -q -n0 pwa_tests/integration/test_phase8_group_banners.py pwa_tests/integration/test_phase8_news_mirror.py`
  — 7 passed.
- `uv run ruff check db_methods/pwa/group_banners.py models/pwa/group_banners.py pwa_tests/integration/test_phase8_group_banners.py`
  — passed.
- Migration up → down → up and `PRAGMA integrity_check` — covered by
  `test_group_banner_migration_is_reversible`.
- `uv run pytest -q -n0 pwa_tests/test_schema_inventory.py pwa_tests/integration/test_migration_lifecycle.py`
  — 26 passed.
- Canonical inventory generated at 399 product schema objects.
- `git diff --check` — passed.

No browser or external service is involved in this storage slice.

## Authenticated HTTP increment

- Student and Family read `GET /{audience}/api/v1/banners/active`; scope comes
  only from authenticated active course enrollments and their allowed groups.
- Admin lists, creates, edits and cancels scheduled banners under
  `/staff/api/v1/group-banners`. Teacher access is rejected with `403`.
- Mutations require optimistic `If-Match` after creation and publish a
  best-effort `banners` refetch hint after the SQLite commit.
- `uv run pytest -q -n0 pwa_tests/integration/test_phase8_group_banner_http_api.py pwa_tests/integration/test_phase8_group_banners.py`
  — 4 passed.
