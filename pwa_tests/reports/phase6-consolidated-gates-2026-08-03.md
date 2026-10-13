# Phase 6 consolidated acceptance gates

Date: 2026-08-03

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

This report reconciles the Phase-6 checklist with the implementation already
accepted in smaller increments. It does not replace their detailed evidence and
does not claim owner visual acceptance.

## Functional matrix

| Requirement                                                                  | Authoritative evidence                                                                                                                                                                                                               |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| One logical queue case, conditional claim, renewable lease and Staff scope   | [`phase6-review-queue-leases.md`](phase6-review-queue-leases.md), [`phase6-review-queue-http.md`](phase6-review-queue-http.md)                                                                                                       |
| One atomic/idempotent completion and exact immutable evidence                | [`phase6-review-completion.md`](phase6-review-completion.md)                                                                                                                                                                         |
| Process-level claim/completion races and rollback after every write boundary | [`phase6-review-concurrency-and-faults.md`](phase6-review-concurrency-and-faults.md)                                                                                                                                                 |
| Reload-safe Staff workspace and chronological conversation                   | [`phase6-review-workspace.md`](phase6-review-workspace.md)                                                                                                                                                                           |
| Normalized non-destructive annotation editor and Student/Family viewer       | [`phase6-review-annotation-editor.md`](phase6-review-annotation-editor.md), [`phase6-student-review-projection.md`](phase6-student-review-projection.md), [`phase6-family-review-projection.md`](phase6-family-review-projection.md) |
| Hidden Teacher reaction, Student disagreement and admin-only current inbox   | [`phase6-review-internal-reactions.md`](phase6-review-internal-reactions.md), [`phase6-student-review-reactions.md`](phase6-student-review-reactions.md), [`phase6-review-reaction-inbox.md`](phase6-review-reaction-inbox.md)       |
| Append-only Teacher correction/Admin recheck                                 | [`phase6-review-corrections.md`](phase6-review-corrections.md)                                                                                                                                                                       |
| Owner-scoped Student/Family refresh and Staff queue/admin fan-out            | [`phase6-review-audience-fanout.md`](phase6-review-audience-fanout.md)                                                                                                                                                               |
| Student submission and review-queue handoff in one transaction               | [`phase6-submission-queue-handoff.md`](phase6-submission-queue-handoff.md)                                                                                                                                                           |
| Text-only private Student/Staff questions and durable drafts                 | [`phase6-support-pages.md`](phase6-support-pages.md), [`phase6-support-draft-storage.md`](phase6-support-draft-storage.md)                                                                                                           |
| Telegram PNG derivative over immutable WebP                                  | [`phase6-review-telegram-composite.md`](phase6-review-telegram-composite.md)                                                                                                                                                         |
| External prototype used only as an idea inventory                            | [`phase6-external-review-reference.md`](phase6-external-review-reference.md)                                                                                                                                                         |
| Historical reactions handled without fabricated review linkage               | [`phase6-legacy-reaction-rehearsal.md`](phase6-legacy-reaction-rehearsal.md)                                                                                                                                                         |

## Current executable gates

- `make python-test`: **121 passed / 1 skipped** in the legacy suite and
  **1552 passed / 6 skipped** in `pwa_tests`; both suites used eight xdist
  workers. Total wall time: **91.85 s**.
- `make pwa-storybook-test`: **50 files / 239 passed** in browser mode;
  `addon-a11y` violations remain errors.
- `make pwa-e2e-review`: **3 passed**, one complete production-build flow in
  each of Chromium, WebKit and Firefox against real aiohttp and an isolated
  seeded SQLite database, without MSW.
- `make telegram-history-test`: **44 passed**. The command uses the dedicated
  history-test profile and does not start polling or contact Telegram.

The production browser flow exercises two concurrent Staff sessions, claim
visibility, annotation, reload-safe draft, atomic completion, Student and
Family projections, hidden Teacher reaction, Student disagreement, admin-only
reaction inbox, append-only correction and realtime refetch.

## Storybook evidence

The current automated matrix includes:

- `product-review--queue`, `--workspace`, `--feedback-plus`,
  `--feedback-guard`, `--feedback-restored-draft` and
  `--feedback-reaction-shortcuts`;
- `product-review-annotation--editor` and `--read-only-student-view`;
- `product-feedback--result`, `--teacher-reaction`,
  `--reviewed-written-photo`, `--reviewed-student-reaction` and
  `--private-support-dialogue`;
- `product-review-reaction-inbox--current-written-reactions`,
  `--already-rechecked` and `--empty`;
- `product-review--synonym-combined-case` and
  `product-feedback--synonym-merged-timeline`.

These stories prove interaction and accessibility behavior. They are not a
substitute for the owner's visual review, and no snapshot was updated during
this reconciliation.

## Legacy reaction decision

The read-only rehearsal found **9924** historical written reaction rows, but
the legacy schema links them only to a `results` row and has no concrete review
round. Safely mappable historical review rows: **0**. Therefore a backfill or
dual write would invent data and is deliberately absent. The owner-only ID
report remains outside the repository; the committed aggregate contains no
names, contacts, credentials or row IDs.

## Open gates

- Owner visual acceptance of the review, correction and support surfaces;
  visual snapshots remain unchanged.
- Support image attachments and continuation of one logical support thread
  through Telegram.
- Delivery wiring for the already tested Telegram annotation PNG derivative;
  recipient selection and sending belong to the Telegram adapter, not the
  renderer.
- Oral review reactions belong to Phase 7 and are not implied by the written
  Phase-6 reaction tables.

Operational behavior and recovery are documented in
[`vmshpwa/docs/review-workflow.md`](../../vmshpwa/docs/review-workflow.md).
