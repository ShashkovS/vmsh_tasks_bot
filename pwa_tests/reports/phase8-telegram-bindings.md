# Phase 8F: Telegram bindings backend proof

Дата: 2026-07-29.

## Граница среза

- Одна таблица `telegram_bindings` хранит destination курса или группы. Bot token в SQLite не попадает.
- `db_methods/pwa/telegram_bindings.py` содержит только короткие SQL-операции.
- Проверка owner/purpose/destination и правило inheritance находятся в `models/pwa/telegram_bindings.py`.
- Русские сообщения и HTTP status находятся только в `apps/pwa_api/telegram_binding_routes.py`.
- Срез даёт admin-only list/create/edit/disable/restore-draft. Bot API verification и Staff UI не подменяются mock-backdoor и остаются следующими срезами.

## Проверяемое поведение

- migration проходит up/down/up и `PRAGMA integrity_check`;
- teacher получает `403`, admin может создать и изменить draft;
- повтор того же owner/purpose/chat/topic отклоняется `409`;
- stale `If-Match` отклоняется `409`;
- edit сбрасывает привязку в `draft`, так как изменённый destination нужно проверить заново;
- `news_source` курса и группы складываются;
- групповой `materials_target` заменяет course default; без него будет использован target курса.

## Результаты

- Focused migration/domain/HTTP: 3 passed.
- Telegram bindings + classroom/auth/PWA app regression: 50 passed.
- Ruff: passed.
- Schema inventory: 385 objects, SHA-256 `4c977a5d76db476101a4d8fe5f9416188efb9940adfb13b3e787c12f9b473714`.
- Visual snapshots: не изменялись.

## Следующий срез

Server-side `getMe`/`getChat`/`getChatMember` verification с явным переходом draft → verified, затем strict frontend contract/client и подключение принятого `TelegramBindingsEditor` к этому API.
