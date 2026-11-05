# Optional legacy Telegram and Google Sheets integrations

Owner requirement (2026-09-30): an empty `telegram_bot_token` must disable the
legacy bot without preventing the remaining backend from starting.
An empty `google_sheets_key` independently disables all Google Sheets imports.

Implemented:

- [apps/__init__.py](../apps/__init__.py) skips `tg_bot` before its imports,
  handler registration and webhook lifecycle wiring.
- [helpers/bot.py](../helpers/bot.py) exposes `bot = None` without constructing
  an aiogram client when the token is empty. Other legacy web adapters may
  still import the shared module; game notifications are skipped in
  [apps/game_web_app.py](../apps/game_web_app.py).
- [helpers/config.py](../helpers/config.py) reads the runtime configuration
  before deciding whether Google credentials are required, based only on
  `google_sheets_key`.
- [main.py](../main.py) starts polling only for a selected Telegram adapter
  with a configured token. Webhook wiring follows the selected adapter list.

A configured nonempty token retains the existing client validation and bot
startup. Invalid nonempty tokens remain configuration errors.

The `apps` list is still authoritative: omitting `tg_bot` (for example,
`"apps": "zoom_events_parser"`) skips Telegram entirely regardless of token.

Google Sheets boundaries:

- [apps/tg_bot.py:on_startup](../apps/tg_bot.py) skips loader setup when the key
  is empty; the rest of Telegram startup continues normally.
- [handlers/admin_handlers.py](../handlers/admin_handlers.py) filters out
  all seven import commands and their aliases when the key is empty.
- [models/spreadsheets.py](../models/spreadsheets.py) blocks explicit import
  calls with `GoogleSheetsDisabled` before reads/writes, even if the loader was
  previously configured. The empty-database bootstrap becomes a no-op.
- [helpers/loader_from_google_spreadsheets.py](../helpers/loader_from_google_spreadsheets.py)
  blocks an unconfigured standalone loader before Google imports or access.
- Existing `allow_google_update_all` cutover protection remains effective;
  individual imports are available only with a nonempty sheet key.

Validation:
[pwa_tests/test_optional_legacy_integrations.py](../pwa_tests/test_optional_legacy_integrations.py)
covers configuration loading for both production/test modes and all four
token/key combinations, Google import guards, real legacy aiohttp lifecycle
without a token, and Telegram startup/command filters without Google Sheets.
All fixtures, tokens and databases are synthetic; no external API is contacted.

Passed on 2026-09-30:

- `.venv/bin/python -m pytest -n0 -q pwa_tests/test_optional_legacy_integrations.py pwa_tests/test_app_factory.py pwa_tests/test_config_safety.py pwa_tests/test_google_loader_inventory.py`
  — 33 passed, including configured-token startup without Google and the
  `apps="zoom_events_parser"` case with a configured token.
- `VMSH_RUNTIME_PROFILE=telegram-history-test .venv/bin/python -m pytest -n0 -q tests/test_spreadsheets_loader.py tests/test_admin_weekly_ops.py`
  — 18 passed; Google bulk-cutover protection and explicit recovery retained.
- Ruff for the new regression file and `git diff --check` for the changed files
  passed. Both suites reported the existing SymPy deprecation warning.

No schema/config-file changes or production deployment required for this code
change. The configured JSON remains the integration-switch source of truth.
