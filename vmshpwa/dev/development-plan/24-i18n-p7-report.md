# P7 — Staff users, access, audit, Telegram bindings, analytics and support

Requirements: [P7 of the execution plan](24-i18n-execution-plan.md#p7--staff-users-access-audit-telegram-bindings-analytics-and-support).
Source language is Russian; English translations live in
[`apps/staff/src/locales/en.po`](../../apps/staff/src/locales/en.po) and
[`helpers/pwa/locales/en.po`](../../../helpers/pwa/locales/en.po). The complete
Staff source scope is enforced by [`i18n-scopes.json`](../../i18n-scopes.json),
which makes a new raw user-facing Staff string fail the catalog gate.

| Batch | Implementation                                                                                                                                                                                                               | English UI coverage                                                                                                                    | Data that remains unchanged                                                                                            |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| P7.1  | `account-provisioning-*`, `student-account-*`, `family-account-manager`, `staff-student-directory-page`, `teacher-batch-*`, `users-section-tabs`; backend account, batch and enrolment routes                                | Account creation, batch previews/results, TSV validation, directory search, family links and course enrolment controls                 | Imported rows, usernames, passwords, names, TSV column protocol and copied credentials                                 |
| P7.2  | `staff-access-page`, `staff-audit-page`, `telegram-bindings-page`; backend access, audit and Telegram routes                                                                                                                 | Staff roles/scopes, known audit action and field labels, filters, binding errors and controls                                          | Action IDs, object IDs, request IDs, actor names, audit before/after payload values, chat values and historical titles |
| P7.3  | `staff-dashboard-page`, `product-analytics-page`, `staff-support-pages`, `staff-support-utils`, `family-digest-panel`, route shells and remaining `pages.tsx` sections; dashboard/analytics/support/organizer backend routes | Dashboard cards, filters, empty/error states, support actions and accessibility labels; numbers and dates use cached locale formatters | Course/group/room names, authored support messages, uploaded files, saved support captions and fixture/domain values   |

`student-directory-search.ts` continues to normalize Russian names using the
Russian locale and treats `ё`/`е` as equivalent. Its narrow lint comments mark
that behavior as data normalization. `staff-support-pages.tsx` similarly keeps
the required default `Фотография` in a saved support entry: it is persistent
message content, rather than a localized interface label.

The English regression tests cover the boundary deliberately:

- `account-provisioning-page.test.tsx` checks English validation/UI with an
  untouched imported Russian row.
- `teacher-batch-tsv.test.ts` checks localized parser errors while retaining the
  TSV credentials as entered.
- `staff-audit-page.test.tsx` checks a known action and field label in English
  while preserving the actor and serialized audit value.
- `family-digest-panel.test.tsx` checks English digest chrome while preserving
  group and student names.
- `e2e/i18n.spec.ts` visits the built Staff user import, access, audit,
  analytics, Telegram-binding and support routes after the real account locale
  switch, and restores Russian in `finally`.

## Verification results

- `make pwa-i18n-extract` generated 1,626 Staff catalog entries with no missing
  translations. The backend catalog has 753 entries; its six unfilled entries
  belong only to the P8 legacy print routes outside this phase's backend scope.
  `make pwa-i18n-check` passed the frontend and backend scope/completeness gates.
- The focused Staff regressions passed: 7 tests in `account-provisioning-page`,
  `teacher-batch-tsv`, `staff-audit-page` and `family-digest-panel`.
- The complete frontend unit suite passed: **916 tests in 180 files**. `make
pwa-lint`, `make pwa-typecheck` and `make pwa-build` passed.
- `make pwa-python-test` passed: **2,095 passed, 6 skipped**. The command runs
  aiohttp integration tests on isolated loopback ports.
- `make pwa-e2e-i18n` passed: **30 tests** across Chromium, WebKit and Firefox.
  It includes the P7 English account, access, audit, analytics, Telegram-binding
  and support navigation after a persisted account locale switch.
- `git diff --check` passed. Formatting is checked for the changed TypeScript
  and TSX files before commit; repository-wide formatting retains unrelated
  existing failures outside P7.

The P6 catalog-loading optimization remains deferred. The cumulative P0
performance gate is still open and is not rebased by P7. P8 remains queued.
