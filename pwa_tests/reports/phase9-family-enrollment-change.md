# Phase 9: Family course group and attendance change

## Result

- Family can change one linked child's active allowed group and attendance mode
  for one course.
- The HTTP boundary validates the child link, course, allowed group, exact body,
  same-origin request and optimistic version before the write.
- `models/pwa/family_enrollment.py` contains the short transaction rule;
  `db_methods/pwa/family_enrollment.py` contains only direct SQLite statements.
- A real change creates separate group and attendance history events. A stale
  browser receives `409` instead of overwriting newer data.
- Draft or already-stale classroom plans for scheduled events are marked stale.
  Confirmed plans and past attendance history are not rewritten.
- The legacy single-course `users.group_id`, `users.online` and
  `user_changes_log` remain synchronized. This compatibility write is skipped
  once a student has more than one active course.
- Family UI uses a two-step confirmation and explains that an in-person choice
  reserves real resources. The compact form has no long-lived draft: its two
  selections are not meaningful work until confirmation.

Immediate room reassignment remains an administrator action through the
existing classroom-plan preview and confirmation flow.

## Verification

- Family course HTTP integration suite: `6 passed`, including unlinked child,
  unavailable group, missing origin, extra query and version conflict.
- Contract, client and isolated two-step form tests: `3 files, 30 tests passed`.
- Python lint and Contracts, App Shell and Family TypeScript checks: passed.
- Family production build and `injectManifest` service worker: passed; 95 files
  were precached.
- `git diff --check`: passed.

No visual baseline was updated.
