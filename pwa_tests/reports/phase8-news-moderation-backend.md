# Phase 8: news moderation backend proof

Дата: 2026-07-29.

## Граница среза

- Существующая `news_visibility` используется без новой миграции.
- `db_methods/pwa/news_moderation.py` содержит один прямой list query и один optimistic update.
- `models/pwa/news_moderation.py` содержит только допустимые переходы `visible ↔ manual_hidden`.
- Русские сообщения, HTTP statuses и JSON находятся в `apps/pwa_api/news_moderation_routes.py`.
- Срез не создаёт local posts, scheduler, banner или broadcast editor.

## Проверяемое поведение

- только global admin читает и меняет moderation state; teacher получает `403`;
- список показывает источник, course/group owner, excerpt, media count и visibility version;
- hide немедленно убирает Telegram-пост из Student/Family feed, не меняя источник Telegram;
- restore возвращает вручную скрытый пост;
- stale `If-Match` получает `409`;
- `source_deleted` нельзя вручную вернуть в PWA;
- причина скрытия нормализуется и хранится вместе с actor/timestamp audit-полями.

## Результаты

- Ruff format/check: passed.
- Focused moderation/news/app-factory regression: 49 passed.
- Schema: без изменений.
- Visual snapshots: не изменялись; frontend подключается следующим отдельным срезом.
