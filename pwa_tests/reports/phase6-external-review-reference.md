# Phase 6 proof: decision record for the external written-review prototype

Date: 2026-08-02

Reviewed idea-only artifacts:

- [`_external_pipelines/viewwrittensols.html`](../../_external_pipelines/viewwrittensols.html);
- [`_external_pipelines/viewwrittensols.js`](../../_external_pipelines/viewwrittensols.js);
- [`_external_pipelines/_viewmailings_helpers.js`](../../_external_pipelines/_viewmailings_helpers.js).

Authoritative product plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

These files belong to another project and remain references only. No DOM,
state shape, endpoint, dependency or score semantics from them is imported into
the PWA runtime.

## Ideas already reimplemented for ВМШ

- A dense review workspace with queue context, immutable work, chronological
  discussion, reply and verdict was rebuilt in React/Base UI as
  `vmshpwa/apps/staff/src/review-workspace-page.tsx` and the shared
  `vmshpwa/packages/product/src/review-workspace.tsx` components.
- Student/problem search, problem grouping, checked/unchecked meaning and
  deterministic queue order were redefined through the Phase-6 queue API and
  strict contracts rather than client-side filtering of a large raw response.
- Previous/next navigation and adjacent-image preparation informed the compact
  evidence viewer. The PWA keeps the logical review case and immutable evidence
  snapshot as the navigation boundary rather than a mutable image record.
- Pen, rectangle, arrow, text, colors, zoom, pan, rotation, delete and undo/redo
  informed `vmshpwa/packages/product/src/review-annotation-editor.tsx`. The PWA
  stores versioned normalized geometry; it never rewrites the Student image.
- Background-save intent was retained as account/review/evidence-scoped local
  draft recovery. Server state changes only on explicit atomic completion, so a
  half-written comment or annotation cannot become a partial review.
- A compact image comment plus quick verdict control became one chronological
  Teacher reply and the accepted 11–17 verdict scale. Internal suspicions became
  the separate hidden Teacher reactions with exact text labels.
- Deep-link intent was retained through stable Staff routes and validated URL
  state. Internal numeric IDs and arbitrary query parameters are not exposed.
- Realtime intent was retained as queue invalidation, lease ownership and
  conflict recovery through WebSocket/NATS. The external prototype's mutable
  per-image presence state is not treated as an authorization or locking source.
- Correcting a mistaken result was reimplemented as an append-only correction
  in `models/pwa/review_corrections.py`; old review evidence and verdict history
  stay immutable.
- PNG export of the annotated image was reimplemented server-side in
  `helpers/pwa/review_composite.py` for the Telegram adapter. Clipboard support
  is not required for that delivery path.

## Ideas deliberately deferred

- Selecting several exam sets at once may inform future cross-course Staff
  filters, but Phase 6 reviews one leased logical case at a time.
- Fuzzy Student search and broader batch operations are useful for Staff
  directories and classrooms, not a prerequisite for the correctness of one
  review transaction.
- Copying an image or deep link to the clipboard is convenient but does not
  replace the existing review history, notification or Telegram delivery.
- Explicit live presence highlights may be added if simultaneous Staff work
  proves confusing. The current lease and invalidation behavior already
  prevents two completed reviews of the same case.
- Correcting an image attached to the wrong task needs its own audited product
  action. It must not silently mutate evidence after a review has frozen it.
- Mailing history filters and delivery preview ideas belong to Phase 8. If
  adopted, they use strict contracts and sanitized product rendering rather
  than the external helper's raw HTML insertion.

## Ideas consciously rejected

- The external 0–10 score, per-image checked flag and replace-in-place verdict
  do not match ВМШ. ВМШ uses one verdict per logical review case, immutable
  history and the established 11–17 written-verdict semantics.
- Saving comments, annotations and suspicion flags independently to the server
  is rejected. A review is one atomic action; unfinished work stays local.
- Direct mutation or deletion of a reviewed photograph is rejected. The
  original WebP and evidence snapshot are immutable after review.
- Browser-generated review PDFs are rejected. All printing remains in the
  authoritative LaTeX/PDF pipeline.
- The external raw HTML/shadow-root mailing preview is not a sanitizer and is
  not reused for Student, Family, Staff or Telegram content.
- Its raw colors, DaisyUI markup, global mutable DOM state, endpoint names,
  numeric identifiers and access-token handling are not copied.
- Anonymous/exam-specific reviewer behavior does not replace ВМШ Staff scopes,
  claims, leases or server-side authorization.

## Verification

- All three reviewed files remain under `_external_pipelines`; production
  Python and TypeScript contain no imports from them.
- The accepted ideas point to concrete PWA implementations and their Phase-6
  proof reports: `phase6-review-workspace.md`,
  `phase6-review-annotation-editor.md`, `phase6-review-corrections.md` and
  `phase6-review-telegram-composite.md`.
- Repository-local links and `git diff --check` were verified before commit.

This record closes the idea-inventory gate only. It does not declare all of
Phase 6 accepted or turn the external prototype into a compatibility target.
