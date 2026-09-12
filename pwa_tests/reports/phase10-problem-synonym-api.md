# Phase 10 logical problem-synonym API

Date: 2026-07-30

## Result

The Staff API now supports the complete reviewed mutation boundary for logical
problem synonyms:

- list equal-title candidates inside one course lesson;
- preview the exact effect of a merge or split;
- merge two or more problems, including unlike task/answer types;
- split selected members while preserving a useful group of two or more;
- automatically remove the last orphan member when a two-problem group is
  split;
- reject a stale preview with `409`.

Only membership rows and the synonym-group version/status change. Problems,
test/written submissions, messages, results and verdicts keep their original
`problem_id`.

## Layer boundary

- `db_methods/pwa/problem_synonyms.py` contains only short SQLite reads and
  writes;
- `models/pwa/problem_synonyms.py` owns the course-lesson, one-problem-per-group
  and merge/split rules;
- `apps/pwa_api/problem_synonym_routes.py` owns authentication, wire validation
  and Russian user-facing messages;
- the existing runtime database factory is only consumed at the HTTP boundary;
  this increment adds no factory, repository, service container or retry layer.

## Proof

- focused real aiohttp/SQLite flow: `2 passed`;
- full Python PWA regression: `1446 passed, 3 skipped`;
- Ruff format/check: passed;
- `git diff --check`: passed.

The integration flow proves admin-only access, different task types, read-only
preview, merge, stale-preview conflict, split, immutable original problem rows
and an unchanged legacy result row.

## Audit follow-up — 2 August 2026

Merge and split now append compact `problem_synonym` Staff-audit events inside
the existing mutation transaction. The audit is a navigation summary rather than
a replacement for versioned membership history. A forced audit-insert failure
rolls back the synonym group and every member row. The current full PWA gate is
**1524 passed, 5 skipped**; frontend unit is **578 passed**; lint, strict
TypeScript and production builds pass.
