# db_methods Agent Guide

## Scope
This folder is the data-access layer for SQLite.  
Each module exposes focused read/write APIs for one domain area (`users`, `results`, `written queue`, `logs`, etc.).

## Architecture Rules
- Keep DB access in `db_methods/*`; do not move SQL to handlers.
- This layer is deliberately mechanical: execute focused SQL, map rows, and
  report storage outcomes. Business decisions belong in `models/*` (or a thin
  application service), and localized/user-facing text belongs at the HTTP,
  Telegram, or UI boundary.
- Do not add connection factories, repository classes, retry wrappers, command
  objects, or abstraction layers merely for possible future load or a possible
  database-engine migration. Reuse the project's existing SQLite lifecycle and
  add an abstraction only for a demonstrated current need.
- Prefer short named queries and small functions. A large projection may use a
  documented analytical query, but ordinary state transitions must not become
  multi-page SQL or mix querying, policy, and response construction.
- Follow the existing pattern:
  - class inherits from `DB_ABC`
  - methods use `self.db.conn`
  - module exports a singleton at the bottom (for example `result = DB_RESULT(sql)`).
- Use `db_methods.db_abc.sql` connection lifecycle (`setup()` / `disconnect()`) as the source of truth.
- Keep return types stable (`dict`, `list[dict]`, ids, simple tuples), because models and handlers depend on them.

## Query and Transaction Conventions
- For writes, prefer `with self.db.conn as conn:` and one explicit SQL statement per state transition.
- Keep timestamps in ISO format (`datetime.now().isoformat()`), matching existing tables and reports.
- Preserve existing semantics:
  - negative `problem_id` means SOS/question flow;
  - queue status and teacher lock logic rely on current SQL conditions.
- Avoid embedding business branching in this layer; keep logic close to storage semantics.
- Never raise errors containing localized product copy or HTTP status codes
  from this layer. Return a small storage result or raise a storage-specific
  exception; the caller chooses product behavior and wording.

## Migrations and Schema
- Schema changes must be done via yoyo migrations in `migrations/`, not ad-hoc SQL edits.
- If a query depends on a new column/index, include migration and backward-compatible read behavior.
- Do not silently rename or repurpose columns used by old analytics and incident investigation.

## Observability Guidance (for migration prep)
- Prefer append-only event capture over mutating old records when adding traceability.
- When adding new logging tables/fields, include:
  - `ts` (ISO timestamp)
  - actor ids (`student_id`, `teacher_id`, `chat_id` where applicable)
  - action/event type
  - primary entity ids (`problem_id`, `lesson`, `state` when relevant).
- Keep log-writing methods idempotent where possible, or document duplicate behavior explicitly.

## Safety Checklist Before Merge
- Reads: verify expected row shape and empty-result behavior.
- Writes: verify rowcount/returned id behavior for conflict paths.
- Concurrency-sensitive updates (queue/status locks): validate optimistic conditions still hold.
- Run affected tests (`pytest -vvs`) and add coverage for new DB branches.

## Traceability And Progress

- Storage changes cite the authoritative data-model/migration decision and related model/API/test; documentation links to exact query modules and migrations.
- Update affected phase plans, proof sections, and status files with schema progress, rehearsal evidence, and known compatibility gaps.
