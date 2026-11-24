# Phase 8A: notification core proof

Дата: 2026-07-29.

## Граница среза

- Migration `0063.pwa_notification_core` добавляет только account-scoped in-app events и глобальные настройки категорий.
- `db_methods/pwa/notifications.py` содержит только прямые SQLite read/write операции.
- Дефолты девяти категорий, проверка timezone/quiet-hours и идемпотентное чтение находятся в `models/pwa/notifications.py`.
- Русские сообщения ошибок находятся только в `apps/pwa_api/notification_routes.py`.
- Явная PWA-рассылка аудиторий создаёт событие только Student account; Family не получает его.
- Web Push, course overrides, news ingest и delivery outbox не входят в этот срез.

## Проверяемое поведение

- migration проходит up/down/up и `PRAGMA integrity_check`;
- defaults включены для всех категорий кроме `oral_window`;
- одна категория сохраняется независимо от остальных;
- список событий применяет `in_app_enabled`; без сохранённой настройки все категории видимы, кроме выключенного по умолчанию `oral_window`;
- неизвестные категории, timezone и quiet-hours отклоняются;
- dedupe не создаёт второе событие;
- read acknowledgement сохраняет server timestamp, повтор безопасен;
- другое account не может прочитать чужое событие;
- authenticated Student API читает событие, настройки и подтверждает прочтение;
- Family API возвращает пустой список для classroom announcement;
- classroom delivery создаёт структурированный payload без Telegram destination.

## Результаты

- Ruff: passed.
- Notification/classroom model and migration tests: 9 passed.
- Preference visibility regression: passed вместе с notification/push/review-набором (15 passed).
- Authenticated classroom/notification HTTP tests: 4 passed.
- PWA app, schema inventory and notification/classroom tests: 66 passed.
- Schema inventory: 377 objects, SHA-256 `5d0aeabf96f0616645717dd174c08ea7ebfa4bf3eaa326f69a8ea3777dd4bcbb`.
- `make pwa-schema-check`: passed.
- `git diff --check`: passed.

## Следующий срез

Shared Zod contracts, Student query/client and the real notification settings/event UI. Web Push remains a later independent commit.
