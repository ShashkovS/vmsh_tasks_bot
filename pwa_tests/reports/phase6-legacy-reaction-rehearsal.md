# Phase 6 proof: legacy written-reaction rehearsal

Date: 2026-08-02

Authoritative decisions:

- [`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md);
- [implementation question 13](../../vmshpwa/dev/development-plan/20-implementation-questions.md#перенос-истории-письменной-проверки).

## Result

The read-only rehearsal proves that historical Telegram-era reactions cannot be
honestly backfilled into `submission_review_*_reactions`: a legacy reaction is
linked to a `results` row, while the legacy schema has no concrete review round.
The accepted product decision explicitly forbids inventing that relationship.

Therefore this gate finishes with a reproducible inventory and an owner-only
duplicate report, not with a speculative migration. Existing legacy rows remain
available to the Telegram adapter; every new PWA review uses the exact new
reaction state and event tables.

## Real database aggregate

`vmshpwa/scripts/review_reaction_rehearsal.py` opened `db/vmsh.db` in SQLite
read-only/query-only mode and reported:

- written Student reactions (`type 0`): **9212**;
- written Teacher reactions (`type 100`): **712**;
- oral Student reactions (`type 200`): **3005**;
- oral Teacher reactions (`type 300`): **561**;
- total written rows: **9924** over **9738** distinct non-null result IDs;
- duplicate written targets: **41**, containing **108** rows;
- rows without a valid result target: **5**, including **3** null result IDs;
- invalid written reaction-enum pairs: **0**;
- inferable written actors missing from `users`: **0**;
- `submission_reviews` available in this legacy snapshot: **false**;
- safely mappable historical review rows: **0**.

The aggregate contains no names, contacts, tokens or legacy row IDs. The
separate ID-only owner report was written to
`/private/tmp/vmsh-phase6-legacy-reaction-owner-details.json` with mode `0600`;
it contains **41** duplicate targets and **5** malformed row IDs and is not
committed.

## Implementation and tests

- `vmshpwa/scripts/review_reaction_rehearsal.py` performs only aggregate reads
  and optional report writes; there is no apply command.
- `pwa_tests/test_review_reaction_rehearsal.py` covers a legacy-only schema,
  exact review targets, occupied targets, actor mismatch, duplicates, malformed
  rows, aggregate privacy, owner-report permissions and unchanged source bytes.
- Targeted suite: **4 passed**.
- Rehearsal plus legacy-reaction characterization and both new reaction-schema
  migration suites: **9 passed**.
- Targeted Ruff formatting/check: **PASS**.
- External-process register/link suite: **7 passed** in the same Phase-6
  documentation increment.
- The real database SHA-256 was identical before and after a second rehearsal:
  `a9cf42cb67e9d2d614b93a43e2f413be3c93fbaacec88f1988a9a03af6bb7dc3`.
- `git diff --check`: **PASS** before commit.

## Cutover consequence

No automatic historical reaction backfill or dual write is introduced. If a
future requirement needs legacy reactions inside a new PWA review, it must
provide an explicit owner-reviewed mapping from the legacy result to the exact
review round. The current accepted history model instead keeps old verdicts and
reactions as independent legacy history and gives exact linkage only to records
created after the PWA cutover.

This proof closes the migration-rehearsal/manual-duplicate-report gate without
claiming false historical precision.
