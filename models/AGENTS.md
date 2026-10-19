# models Agent Guide

## Scope
This folder is the domain layer between handlers and `db_methods`.  
Models encapsulate entity behavior and convert DB rows into application objects.

New PWA behavior follows the same boundary: domain invariants and decisions
live here (or in an equally small domain service), while `db_methods/*` remains
focused on SQLite reads/writes and HTTP/Telegram/UI owns localized copy.

## Design Conventions
- Keep models thin and explicit: domain operations plus small invariants.
- Most constructors are write-through:
  - when `id is None`, `__post_init__` inserts into DB.
  - when row exists, constructors normalize types (enums, optional fields).
- Use `@classmethod` getters (`get_by_id`, `get_by_chat_id`, etc.) as the canonical read API.

## Critical Behavior to Preserve
- `User`:
  - token normalization is part of identity lookup;
  - group/online updates also write to change log.
- `State`:
  - state payload `info` is JSON-serialized with `orjson`;
  - this is the persistent state machine storage for handlers.
- `Result`:
  - DB write is coupled with NATS publish on positive verdict.
- `WrittenQueue`:
  - queue/discussion operations reflect teacher-student review workflow.

## Dependency Rules
- Models may call `db_methods` and light helpers/constants.
- Avoid importing handlers into models to prevent circular flow coupling.
- Keep domain side effects obvious and documented in method names.

## Observability Guidance (for migration prep)
- Emit/record events after successful state-changing operations (not before).
- For each domain event, include identifiers required for cross-channel replay:
  - `user_id`, `problem_id`, `result_id`, `teacher_id`, `state`, `res_type`.
- Keep event naming stable and business-oriented, so Telegram and future web channels can share analytics.

## Data Compatibility
- Preserve enum/value compatibility with existing DB rows.
- Avoid changing method signatures broadly; handlers rely on current call shapes.
- If adding fields, keep defaults safe for old rows and old fixtures.

## Validation Checklist
- Verify object creation from DB rows still works for nullable/legacy values.
- Verify side effects (logs, queue updates, NATS publish) fire exactly once per action.
- Add tests around new model behavior and serialization boundaries.

## Traceability And Progress

- Domain changes cite the governing decision/data-model section and related migration/API/test; documentation links to exact model methods or files.
- Keep phase plans, proof sections, and status files current as implementation or compatibility boundaries change.
