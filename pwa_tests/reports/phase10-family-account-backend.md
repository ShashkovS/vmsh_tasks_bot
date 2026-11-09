# Phase 10 proof: Family account and child-link backend

Date: 2026-08-02

Authoritative plan:
[`14-phase-10-admin-and-google-exit.md`](../../vmshpwa/dev/development-plan/14-phase-10-admin-and-google-exit.md).

## Result

The existing Staff account boundary now supports three admin-only operations:

- create an active Family account and link it to one Student atomically;
- link an existing Family login to another Student;
- revoke one Family-to-Student link without deleting the account or its other
  child links.

This fills the backend half of the previously recorded Family-account gap. It
does not decide how an initial password is communicated outside Staff; that
product question remains explicit and does not weaken password storage.

## Implementation boundary

- Pure normalization and length rules live in
  `models/pwa/admin_accounts.py`.
- `db_methods/pwa/admin_accounts.py` contains only direct reads/inserts/link
  updates and audit inserts.
- `apps/pwa_api/admin_account_routes.py` owns authorization, localized errors,
  password hashing and response serialization.
- Existing `auth_accounts` and `family_student_links` are sufficient; no schema
  change or generic import framework was added.
- The Student directory now includes the Family username for admin-visible
  account management. Teacher serialization still returns no private account
  or link data.

The password is hashed before the transaction, is never returned, and is never
written to audit metadata. Link events record only actor, Student public ID,
relationship label and primary flag. Revoking a link closes the Family account's
live sockets so another tab cannot keep stale child access; it does not revoke
the account's login sessions or unrelated child links.

## Executable evidence

Focused domain and real aiohttp/SQLite tests: **23 passed**.

They prove:

- NFKC/whitespace/case normalization and blank-field rejection;
- Teacher `403` and admin creation;
- unique normalized Family login conflict;
- successful Family login with the newly stored password;
- no raw password in the response, SQLite credential field or audit metadata;
- one Family account linked to a second child;
- revoked child access returns `403` while the account itself is preserved;
- append-only create/link/unlink audit event types;
- existing account lifecycle and Student directory behavior remain green.

Targeted Ruff formatting/check and `git diff --check` passed before commit.
Strict TypeScript contracts, Staff UI, Storybook and production-browser proof
belong to the next increment.
