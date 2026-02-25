# handlers Agent Guide

## Scope
This folder contains Telegram interaction flows: commands, callbacks, message processing, and user/teacher state transitions.

## Core Flow Invariants
- Use aiogram 3 router decorators from `helpers.bot.router`.
- Keep custom state machine architecture:
  - register state handlers via `@reg_state(STATE.*)`
  - register callback handlers via `@reg_callback(CALLBACK.*)`
  - state is persisted in DB through `models.state.State`.
- Do not replace with aiogram FSM unless explicitly planned as a separate migration track.
- Preserve `process_regular_message()` behavior in `handlers/main_handlers.py` as the fallback entrypoint for ordinary messages.

## Callback and Message Protocols
- Callback payload design is compact: first character identifies callback processor (`query.data[0]`).
- Keep callback payload backward-compatible; old inline keyboards may still be clicked later.
- Respect existing media restrictions:
  - photos/documents are processed only in specific states;
  - media group handling relies on `media_group_id` deduplication.
- Preserve keyboard lifecycle updates via `db.last_keyboard` to avoid stale interactive UI.

## Domain-Specific Behavior to Preserve
- Student flow:
  - selecting tasks
  - sending test answers / written solutions
  - SOS / waitlist interactions.
- Teacher flow:
  - taking items from written queue
  - checking and verdicting
  - oral/zoom-related actions.
- Registration flow depends on `REG_MODE` feature flags and token-based identity mapping.

## Observability Guidance (for web migration prep)
- Instrument events at business boundaries, not every line.
- Prefer consistent event names such as:
  - `auth.start`, `auth.success`, `state.changed`
  - `solution.submitted`, `solution.queued`, `solution.checked`
  - `zoom.queue_enter`, `zoom.queue_exit`, `verdict.saved`.
- Include minimal but sufficient context:
  - `user_id`, `chat_id`, `role`, `state`
  - `problem_id`, `lesson`, `res_type`
  - message ids / callback code for replay.
- Log exceptions with traceback and enough request context to reproduce incidents.

## Implementation Discipline
- Keep handler functions small and explicit; extract reusable logic into helper/model calls.
- Before changing a state transition, map previous and new state graph to avoid dead-end states.
- Preserve behavior under missing user records (`REG_ANYBODY` vs `REG_NEEDED` paths).
- Avoid long blocking operations in handlers; use async tasks where existing pattern already does.

## Validation Checklist
- Smoke-test key commands (`/start`, level/mode switches, teacher queue flows).
- Validate at least one full student cycle:
  - choose problem
  - submit answer/solution
  - see queue/verdict effects.
- Validate at least one teacher cycle:
  - take from queue
  - send feedback/verdict
  - return to action menu.
