# helpers Agent Guide

## Scope
This folder contains shared infrastructure: bot wiring, config loading, feature flags, checkers, messaging utilities, and shutdown/runtime helpers.

## High-Impact Modules
- `helpers/config.py`:
  - loads runtime config and credentials at import time;
  - sets `APP_PATH` and changes process working directory;
  - initializes logging and optional Sentry.
- `helpers/bot.py`:
  - defines custom `BotIg` with retry/ignore wrappers;
  - owns global `bot`, `router`, `dispatcher`;
  - stores callback/state registries used by handlers.
- `helpers/features.py`:
  - maps config values into active feature switches used across flows.

## Non-Negotiable Invariants
- Keep bot API calls keyword-based and compatible with aiogram 3.
- Prefer `*_ig` helper methods when existing code intentionally ignores Telegram API edge-case errors.
- Keep rate limiting behavior in `helpers/bot.py` unless a migration task explicitly changes it.
- Do not bypass centralized error capture (`post_logging_message`, Sentry integration).

## Configuration and Secrets
- Never hardcode secrets or commit credential files.
- Preserve production/test split based on `PROD=true`.
- When adding config fields, provide safe defaults and backward compatibility.

## Observability Guidance (for migration prep)
- Keep logging and tracing primitives centralized here, so handlers/models stay focused on business logic.
- If adding structured logging helpers, ensure consistent keys across the app:
  - `event`, `ts`, `user_id`, `chat_id`, `role`, `state`, `problem_id`, `lesson`.
- Do not log full sensitive payloads (tokens, credentials, personal data) unless explicitly required for incident forensics.
- Keep exception reporting deterministic: one captured exception should carry enough context to replay the scenario.

## Reliability Guidelines
- Retry logic should be explicit and bounded (current timeout ladder style).
- Preserve async safety: background tasks must not crash silently.
- Keep helper APIs stable; many modules import these globals directly.

## Validation Checklist
- Confirm app starts in both test and production config modes.
- Confirm bot wrappers still handle common Telegram errors gracefully.
- Confirm Sentry integration still initializes without breaking local development when DSN is absent.
