# Aiogram 2 -> 3 Migration Plan (VMSh Tasks Bot)

## Scope and constraints
- Keep current state machine and callback processing (`helpers/bot.py` `reg_state`, `reg_callback`, `state_processors`, `callbacks_processors`) unchanged.
- Minimize behavioral changes; only adapt aiogram API and wiring.
- Preserve dual runtime modes: webhook in prod (gunicorn) and long polling in dev.

## Inventory: aiogram 2 touchpoints (from ripgrep)
- `requirements.txt` (aiogram==2.25.2)
- `main.py` (aiogram webhook `web` import)
- `apps/tg_bot.py` (configure_app/start_polling/LoggingMiddleware/webhook wiring)
- `helpers/bot.py` (Bot subclass, Dispatcher, aiogram exceptions/types)
- `handlers/__init__.py` (register_message_handler)
- `handlers/group_and_channel_handlers.py` (channel_post_handler, filters, exceptions)
- `handlers/main_handlers.py` (message/callback handlers)
- `handlers/student_handlers.py` (message/callback handlers, exceptions)
- `handlers/teacher_handlers.py` (filters, InputFile, exceptions)
- `handlers/common_handlers.py` (message handler, exceptions)
- `handlers/admin_handlers.py` (BotCommand, BotCommandScope, exceptions)
- `handlers/*_keyboards.py` (types for markup)
- `tests/dataset.py` (Bot.set_current, aiogram.utils.payload._normalize)
- `tests/test_user_start.py` (aiogram logger config)
- Docs mentioning aiogram 2: `README.md`, `ARCHITECTURE.md`, `adr/0001-record-architecture-decisions.md`

## Step-by-step migration

1) [x] **Upgrade dependencies**
   - Update `requirements.txt` to aiogram 3.x (pin a specific version, e.g. `aiogram==3.7.0` or `>=3,<4`).
   - Verify `aiohttp` version remains compatible with aiogram 3.
   - If `requirements-test.txt` pins aiogram indirectly, adjust as needed.

2) [x] **Refactor bot bootstrap in `helpers/bot.py` (core wiring)**
   - Replace `from aiogram.dispatcher import Dispatcher` with `from aiogram import Bot, Dispatcher, Router`.
   - Instantiate `bot = BotIg(...)` using `DefaultBotProperties(parse_mode=ParseMode.HTML)` and an optional `AiohttpSession(timeout=...)` to keep the old `timeout=5` behavior.
   - Create a `router = Router()` and include it in the dispatcher (`dispatcher.include_router(router)`), or use the `Dispatcher` itself for handler registration if you want one object.
   - Update imports:
     - `aiogram.types` and `aiogram.enums` for `ParseMode`, `ChatType`, `ContentType`.
     - `aiogram.exceptions` for `BadRequest`, `TelegramAPIError`, `MessageNotModified`, `RetryAfter`, etc.
   - Keep the existing `BotIg` logic and state processors intact; only adjust method signatures/types if aiogram 3 renamed return types (e.g., `MessageId`).

3) [x] **Switch handlers to aiogram 3 router API**
   - Replace decorator usage:
     - `@dispatcher.message_handler(...)` -> `@router.message(...)`
     - `@dispatcher.callback_query_handler(...)` -> `@router.callback_query(...)`
     - `@dispatcher.channel_post_handler(...)` -> `@router.channel_post(...)`
   - Migrate filters and arguments:
     - `commands=['start']` -> `Command('start')`
     - `ChatTypeFilter(ChatType.PRIVATE)` stays but import from `aiogram.filters`
     - `RegexpCommandsFilter(...)` -> `F.text.regexp(r"...")` or a custom filter class
     - `content_types=ContentType.ANY` can be removed (default matches all), or use `F.content_type` if needed
   - Files to touch: every file under `handlers/` (see inventory).
   - Preserve existing handler bodies and state processing logic.

4) [ ] **Update imports in handlers**
   - Replace `from aiogram.dispatcher.webhook import types` with `from aiogram import types` (or `from aiogram.types import Message, CallbackQuery, ...`).
   - Replace `aiogram.dispatcher.filters` with `aiogram.filters`.
   - Replace `aiogram.utils.exceptions` with `aiogram.exceptions`.
   - Replace `types.ParseMode` with `ParseMode` from `aiogram.enums`.
   - Replace `types.input_file.InputFile` with `FSInputFile`/`BufferedInputFile` (`handlers/teacher_handlers.py`).

5) [ ] **Rewire webhook + polling integration in `apps/tg_bot.py`**
   - Use `from aiohttp import web` (remove aiogram webhook import).
   - Add aiogram 3 webhook helpers:
     - `from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application`
   - Implement:
     - `setup_tgbot_webhook(app)`:
       - Build webhook path using `config.webhook_path` (and/or token if you want the old path style).
       - Register `dp.startup`/`dp.shutdown` callbacks.
       - Create `SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=...)`.
       - `handler.register(app, path=path)` and `setup_application(app, dp, bot=bot, path=path)`.
       - Set webhook URL in `on_startup` and delete in `on_shutdown`.
     - `run_tg_bot_in_polling_mode()`:
       - `await bot.delete_webhook(drop_pending_updates=False)` then `await dp.start_polling(bot)`.
   - Keep DB/spreadsheet init and shutdown logic as-is inside the startup/shutdown hooks.

6) [ ] **Update `main.py` to select webhook vs polling**
   - Import `web` from `aiohttp`.
   - In dev (`__main__`), run aiohttp app with `AppRunner/TCPSite` and start `run_tg_bot_in_polling_mode()` as a task (match your aiogram 3 example).
   - In prod (gunicorn import), call `setup_tgbot_webhook(app)` before returning the app.
   - Keep the existing `apps.all_apps` wiring and shutdown ordering unchanged.

7) [ ] **Adjust tests for aiogram 3**
   - `tests/dataset.py`:
     - Replace `Bot.set_current` usage (removed in aiogram 3). Prefer passing the bot explicitly to functions or use context utilities if needed.
     - Replace `aiogram.utils.payload._normalize` (internal in aiogram 2) with a safe serializer; if you only need JSON, use `json.dumps(message_data)`.
   - Keep test fixtures/messages unchanged to avoid behavior drift.

8) [ ] **Update docs to reflect aiogram 3**
   - Update `README.md`, `ARCHITECTURE.md`, `adr/0001-record-architecture-decisions.md` to mention aiogram 3 and the new webhook/polling wiring.

9) [ ] **Validation checklist**
   - Run `pytest -vvs tests/` (or `./run_tests.sh`).
   - Run `python main.py` in dev and confirm:
     - aiohttp app starts
     - polling bot responds
   - In prod-like mode (gunicorn), confirm webhook is set and updates are processed.

## Notes on minimal change strategy
- Keep all handler bodies intact; only update imports, decorators, and filters.
- Keep state machine (`models/state.py` + `helpers/bot.py` registries) unchanged.
- Avoid refactoring into scenes/FSM; use aiogram 3 routing only as a transport layer.
