# Phase 6T proof: reload-safe support text drafts

Date: 2026-07-29

Revision: `3a3735d` — versioned, account-scoped browser drafts for new Student
questions and Student/Staff replies.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted boundary

- Unsent text is stored in the canonical runtime namespace and isolated by
  audience, human/agent instance, authenticated account and exact compose
  target.
- Targets distinguish a new problem question, a new general question and a
  reply in an existing thread. No draft can silently appear in another
  dialogue.
- A draft owns one stable idempotency key and client creation timestamp across
  edits and reloads. Editing only advances `updatedAt`.
- Corrupt or structurally key-mismatched data is removed one key at a time;
  another account's valid draft is retained.
- A denied/quota-exhausted `localStorage` write raises a typed error. The
  application must expose that durability is unavailable rather than showing a
  false “saved” state.
- Clear removes either the confirmed sent target or all drafts for one account.
  It never clears the whole runtime namespace.
- This increment deliberately stores text metadata only. Question attachments
  and offline queued delivery are separate later decisions; Staff remains a
  normal SPA and does not acquire Dexie merely for text drafts.

Implementation and executable specification:

- `vmshpwa/packages/offline/src/support-draft.ts`
- `vmshpwa/packages/offline/src/support-draft.test.ts`
- public export: `vmshpwa/packages/offline/src/index.ts`

## Executable evidence

- Focused draft-store specification: **6 passed**.
- Complete frontend unit gate: **58 files / 418 tests passed**.
- `make pwa-lint`: **PASS** for ESLint and Stylelint.
- `make pwa-typecheck`: **PASS** for route generation, all applications,
  packages and tool configuration.
- `make pwa-build`: **PASS** for Student, Family and Staff production builds;
  Student and Family each produced an `injectManifest` service worker.
- Prettier and `git diff --check`: **PASS**.
- The preceding backend/realtime gate at `cf8ed5b` remains **1297 Python tests
  passed / 3 intentional skips**; this increment changes no Python or schema.

## Still open in this slice

- wire the store into the real Student and Staff question composers, clear it
  only after the server acknowledges the mutation and show save failures;
- add application interaction stories and production-build E2E for reload and
  account isolation;
- add support attachments through the existing media proxy.

This proof accepts the browser persistence primitive, not yet its page-level
composition.
