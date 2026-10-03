# Phase 6E proof: internal Teacher review reactions

Date: 2026-07-28

Revisions:

- `1db6f0b` — current state, immutable event history and atomic completion;
- `978d0e9` — strict aiohttp endpoints, Zod contracts and Staff client.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Implemented boundary

- `submission_review_internal_reactions` stores at most one current hidden
  Teacher reaction per completed review. The actor is the original reviewer;
  reaction IDs must belong to legacy-compatible written-Teacher registry type
  `100` (`100..103`).
- The optional initial reaction is part of `CompleteReviewCommand`, its
  idempotency digest and the same SQLite transaction as the result, comment,
  evidence snapshot, annotations and queue removal.
- `submission_review_internal_reaction_events` records every select, change and
  delete with a monotonically increasing state version. Events and the state
  row cannot be physically changed or deleted.
- The original reviewer may select, replace, remove and reselect the reaction
  for one hour after review completion. Writes use `expectedVersion`; stale
  clients fail with `409` rather than overwriting newer state. Repeating the
  already-current selection is an idempotent no-op.
- `PUT /staff/api/v1/reviews/{reviewPublicId}/internal-reaction` and matching
  `DELETE` accept strict versioned JSON bodies. The completion receipt exposes
  the current state only to Staff. Student/Family payloads and owner
  invalidations do not include this hidden reaction.
- The accepted-verdict policy now consistently treats both `+` and `+.` as
  solved: neither needs a redundant no-comment confirmation. Lower verdicts
  still require a comment or explicit confirmation.
- TypeScript contracts restrict the registry to IDs `100..103`, validate the
  active/tombstone invariant and reject timestamps outside the edit window.
  The Staff client sends exact PUT/DELETE bodies and exposes TanStack mutation
  helpers keyed by the public review ID.

Implementation:

- `migrations/0054.pwa_submission_review_internal_reactions.sql`
- `db_methods/pwa/reviews.py`
- `apps/pwa_api/review_routes.py`
- `vmshpwa/packages/contracts/src/review-queue.ts`
- `vmshpwa/packages/app-shell/src/review-queue-client.ts`

## Executable evidence

- Focused migration/repository/schema suite: **39 passed**.
- Real aiohttp authorization and transport suite: **6 passed**.
- Focused TypeScript contract/client suite: **2 files / 14 passed**.
- Complete frontend unit checkpoint: **50 files / 381 passed**.
- Complete Python checkpoint: **1254 passed / 3 intentional skips / 1 existing
  SymPy deprecation warning**.
- Storybook browser regression: **39 files / 190 passed**.
- ESLint, Stylelint, TypeScript and all three production builds: **PASS**.
- Student and Family `injectManifest` service workers: **PASS**.
- Deterministic schema: **312 objects**, SHA-256
  `22d818de32641ee4c5b724067b71a1d54b3af55ca6d2447e8c881e2e6a29ad74`.
- `git diff --check`: **PASS**.

Tests prove atomic initial persistence and replay, all four registry choices,
optimistic replacement/deletion/reselection, idempotent same-value selection,
original-reviewer ownership, Staff scope checks, the one-hour cutoff, rejection
of Student reaction IDs, immutable events and exact migration up/down/up. The
HTTP proof covers strict bodies, hidden server-side actor identity, stale
version `409`, foreign reviewer `403`, invalid type `422` and a tombstone
receipt.

## Intentionally still open

- Student reactions and the admin complaint/appeal view;
- historical legacy reaction backfill and duplicate/manual-resolution report;
- live wiring of `ReviewFeedbackForm` to the real queue lease/completion API;
- durable local draft recovery for comment, verdict, reaction and annotation;
- full Student/Family thread serialization and Playwright review workspace;
- annotation editor/renderer and Telegram composite derivative.

This proof accepts internal Teacher-reaction persistence and transport, not the
complete Phase 6 workspace.
