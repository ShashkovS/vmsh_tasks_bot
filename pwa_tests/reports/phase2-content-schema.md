# Phase 2A: versioned content schema and repository proof

Date: 2026-07-27. Scope: the first persistence/domain increment of Phase 2.
The compiler, HTTP API, frontend renderer, Telegram adapter, legacy backfill and
production migration activation are deliberately outside this proof.

## Implemented boundary

- Additive yoyo migration
  [`0041.pwa_content_lessons.sql`](../../migrations/0041.pwa_content_lessons.sql)
  and exact rollback
  [`0041.pwa_content_lessons.rollback.sql`](../../migrations/0041.pwa_content_lessons.rollback.sql).
- Concurrency/audit hardening migration
  [`0042.pwa_content_concurrency.sql`](../../migrations/0042.pwa_content_concurrency.sql)
  and exact rollback
  [`0042.pwa_content_concurrency.rollback.sql`](../../migrations/0042.pwa_content_concurrency.rollback.sql):
  one active source slot, recoverable compiler lease, terminal publication
  audit and SQL-bypass guards.
- Pure domain rules in
  [`models/pwa/content.py`](../../models/pwa/content.py): exact-byte source
  hashing, canonical UTF-8/CP1251 labels, BOM removal after hashing,
  timezone-aware windows, DST-safe schedule resolution, revision/publication
  lifecycles and deterministic synonym candidates.
- Connection-per-operation repository in
  [`db_methods/pwa/content.py`](../../db_methods/pwa/content.py): course/group
  lessons, append-only source revisions, optimistic compiler state, versioned
  schedule rules/overrides, immutable window provenance, assets/derivatives,
  problem matching, synonym membership and atomic publication activation,
  replacement and rollback.
- Canonical generated inventory/snapshots now contain 188 product schema
  objects and are regenerated only from migration head.

## Proven invariants

- `(course_id, lesson_number)` identifies a course lesson; a group from another
  course cannot be attached to it. `cycle_anchor_date` is canonical ISO date,
  not a datetime or an assumed lesson/Monday date.
- A schedule is four separately versioned fields relative to the neutral cycle
  anchor. Every group override retains an active course base rule;
  `submission_closes_at` cannot be disabled. Local times reject `24:00`, unknown
  zones, DST gaps and ambiguous folds. Materialization stores exact UTC values
  plus immutable per-field rule/override provenance. Later rule confirmation
  does not move an existing window. Confirmed/superseded rule audit metadata is
  terminal, and a group override draft conflicts if its base rule is no longer
  active when confirmation begins.
- Source hashes cover exact uploaded bytes, including a BOM. Decoded LaTeX
  strips the BOM and stores only canonical `utf-8` or `cp1251` encoding labels.
  A new revision points to its immediate predecessor but does not silently
  change an older `ready` row; explicit superseding is a separate transition,
  preserving rollback material.
- First upload uses one atomic resolve/create/append operation; concurrent
  requests with different filenames cannot split one material into parallel
  active source histories. Source identity cannot be changed or deleted after
  creation; archive is the sole one-way transition.
- Compiler transitions persist canonical JSON and diagnostics under optimistic
  version checks. Claim token, fixed lease cutoff, attempt counter and terminal
  time make worker cancellation and crash recovery explicit without exposing
  claim tokens on the wire. Revisions cannot be deleted.
- Content/generated assets deduplicate only when hash, conversion version,
  media type, byte size and dimensions agree. Object keys and public URLs pass
  canonical input validation, and stored dimensions are bounded to 1..20000.
  Derivative asset hashes must equal the referenced
  media hash; derivative payload is immutable and invalidation is one-way.
- Resolved problem matches, problem revisions and revision asset associations
  cannot be silently reassociated or deleted. Equal normalized titles only
  return cross-group candidates within one course lesson; merge/split remains
  explicit and membership history is append-only.
- Only a `ready` revision of the same group lesson and kind can be published.
  Immediate replacement, scheduled activation and rollback are atomic. The
  newly active row records the actual previously published row in
  `supersedes_publication_id` and the consumed scheduled row in
  `activated_from_schedule_id`; a failed replacement rolls the previous state
  back with the transaction.
- Publication terminal transitions retain actor and timestamp. A second DB
  trigger rejects direct version bumps, payload edits, terminal-row creation
  and terminal transitions without their audit pair.
- Hint/solution reveal rows require a published matching kind and a concrete
  problem belonging to the publication's group lesson. Reveal identity and
  time are immutable and rows cannot be deleted.

## Commands and results

- Focused migration/repository/HTTP/scheduler suite from
  [`phase2-content-api.md`](phase2-content-api.md): **41 passed**; both 0041 and
  0042 up/down/up, SQLite `integrity_check`, source/claim/publication races and
  two-worker activation pass.
- `uv run python -m vmshpwa.scripts.schema_inventory check` and
  `pwa_tests/test_schema_inventory.py`: **pass**; canonical migration-head
  inventory contains **188** product objects.
- `ruff check`, `ruff format --check` and `git diff --check` for the affected
  Phase-2 Python/migration/test/report files: **pass**.

No command in this increment opened or migrated `db/vmsh.db`. All migration and
repository checks used disposable synthetic SQLite databases.

## Remaining Phase 2 gates

- Safe LaTeX compiler, golden corpus, TikZ/SVG and raster/WebP derivatives.
- Filesystem/S3 adapter contract and opt-in live S3 proof.
- HTTP contracts, Staff upload/diagnostics/problem matching/publication UI,
  Student/Family reads and realtime invalidations.
- Telegram-rich rendering and opt-in test-channel proof.
- Historical lessons 1–38 dry-run/backfill and compatibility projection.
- Storybook, Playwright and owner visual approval.
