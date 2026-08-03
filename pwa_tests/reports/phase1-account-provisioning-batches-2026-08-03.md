# Phase 1: Student and Family account batches

Date: 2026-08-03.

## Delivered

- Migration `0076.pwa_account_provisioning_batches` adds the v1 owner-only
  plaintext provisioning value and ordered Family email addresses. The normal
  login path still verifies Argon2 hashes.
- Four admin-only endpoints implement independent Student and Family
  preview/apply flows.
- Student rows create the legacy `users` record and its linked Student account.
  Family rows create one Family account, ordered emails and links to all named
  Student logins.
- Login collisions are resolved in preview with a reviewed random `-NN`
  suffix. Apply accepts only that exact input/hash pair and never returns a
  password, token or email.
- Course enrollment is intentionally separate because the active-group rule is
  still an explicit product question.

## Architecture check

- `models/pwa/account_batches.py`: pure row validation and login selection.
- `db_methods/pwa/account_batches.py`: short direct SQLite statements only;
  no localized strings, HTTP errors, command objects, repositories or retry
  policy.
- `apps/pwa_api/account_batch_routes.py`: admin authorization, preview/apply
  orchestration, Argon2 work outside the SQLite write transaction and localized
  HTTP responses.

## Automated evidence

- Domain + migration + HTTP focused suite: `11 passed`.
- Schema inventory, migration lifecycle, migration up/down/up, domain and HTTP
  suite: `37 passed`.
- Ruff format/check and `git diff --check`: pass.
- Full Python PWA suite with eight workers: `1627 passed, 6 skipped` in
  `125.76s`. The first sandboxed attempt could not bind loopback sockets; the
  unchanged approved local-socket rerun is the recorded gate.

The HTTP tests prove Teacher `403`, reviewed collision suffix, Student and
Family login after apply, Family email/link persistence, legacy Student fields,
plaintext exclusion from responses, and mismatch rejection after a previewed
table changes. The migration test proves `up → down → up` plus SQLite
`integrity_check`.

## Manual/live boundary

No real student data, email delivery, Telegram call, Google loader, production
database or production credential was used. External credential mailing remains
an owner-run v1 script and is not part of this HTTP increment.
