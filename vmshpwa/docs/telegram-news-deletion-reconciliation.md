# Сверка удалённых Telegram-публикаций

## Зачем нужен отдельный процесс

Bot API доставляет новые и изменённые `channel_post`, но не предоставляет
обычному боту событие удаления уже опубликованного поста. Поэтому PWA не может
надёжно угадать удаление по отсутствию события или периодически перечислить всю
историю канала.

В первой версии используется простой явный процесс:

1. администратор замечает, что зеркальный пост отсутствует в Telegram;
2. в Staff `/staff/news` нажимает «Нет в Telegram»;
3. указывает краткую причину и подтверждает действие;
4. пост сразу исчезает из Student/Family news feed;
5. изменение, причина, actor и request ID сохраняются в audit;
6. если отметка была ошибочной, администратор нажимает «Пост доступен» и снова
   указывает причину.

Действие не удаляет и не редактирует Telegram-сообщение. Оно меняет только
состояние локального зеркала.

## Границы и инварианты

- Действие доступно только global admin. Teacher получает `403`.
- Сверка разрешена только для `source_type = telegram`.
- Клиент обязан передать текущую версию в `If-Match`; устаревшая вкладка
  получает `409` и должна обновить список.
- Пустая причина запрещена; максимальная длина — 500 символов.
- Изменение `news_posts`, `news_visibility` и append-only `audit_events`
  выполняется в одной SQLite-транзакции. Ошибка audit откатывает весь переход.
- В audit не попадают исходный текст поста, `chat_id`, `message_id`, bot token
  или иной Telegram credential.
- Повторное подтверждение уже установленного состояния возвращает конфликт, а
  не создаёт лишнюю audit-запись.
- Ручная отметка не является durable tombstone для источника. Если Telegram
  adapter позднее получает новую ревизию того же поста, существующий ingest
  снова делает публикацию видимой.

Состояние `source_deleted` использует существующую модель зеркала. Как и
автоматический `mark_source_deleted`, оно временно замещает ручное
`manual_hidden`; подтверждённое появление новой source revision возвращает
`visible`. Это не отдельная система модерации и не требует новой таблицы.

## Реализация

- HTTP: `PATCH /staff/api/v1/news/{post_id}/source-state` в
  `apps/pwa_api/news_moderation_routes.py`.
- Доменный переход: `models/pwa/news_moderation.py`.
- Короткие SQLite-записи: `db_methods/pwa/news_moderation.py`.
- Zod-контракт: `vmshpwa/packages/contracts/src/news.ts`.
- Browser client: `vmshpwa/packages/app-shell/src/news-moderation-client.ts`.
- Staff UI: `vmshpwa/apps/staff/src/staff-news-page.tsx`.
- Audit UI: `vmshpwa/apps/staff/src/staff-audit-page.tsx`.
- Storybook: `product-news-moderation--lifecycle`.

## Проверка

Интеграционный тест `pwa_tests/integration/test_phase8_news_moderation.py`
проверяет запрет для teacher, скрытие Student feed, optimistic conflict,
исправление ошибочной отметки, audit-содержимое и транзакционный rollback при
ошибке audit insert. Контракты и transport проверяются соответствующими
Vitest-тестами. Сводный результат находится в
`pwa_tests/reports/phase8-news-source-deletion-reconciliation.md`.

## Эксплуатационное ограничение

Процесс требует человеческого наблюдения и не обещает мгновенную синхронизацию
после удаления в Telegram. Если это станет заметной операционной нагрузкой,
следующий шаг — отдельный подтверждённый импорт журнала/экспорта владельца
канала. Добавлять user-account MTProto session только ради поиска удалений в v1
не следует: это новая credential- и operational-модель без текущей необходимости.
