# Локальные публикации PWA по расписанию

Staff может создать новость, которая относится ко всему курсу или к одной
группе и появляется в Student/Family PWA в заданное время. Эта операция не
публикует и не редактирует сообщения в Telegram.

## Граница первой версии

- Публикация содержит обычный текст длиной до 32 768 символов. Markdown-редактор
  и произвольные рассылки относятся ко второй версии.
- Время вводится как московское и перед отправкой преобразуется в UTC. Backend
  принимает только timezone-aware timestamp и хранит нормализованное UTC-время.
- Для публикации используются существующие `news_posts`, `news_revisions` и
  `news_visibility`; отдельная таблица scheduler не нужна.
- До `published_at` публикация видна в Staff как «По расписанию», но отсутствует
  в Student/Family feed, detail API и списке in-app событий.
- Notification events создаются в одной транзакции с публикацией и получают
  `deliver_after = published_at`. В payload хранится `courseId`, поэтому
  course-specific notification preference применяется корректно.
- Черновик формы хранится в `localStorage` с ключом runtime + Staff account и
  удаляется только после подтверждённого ответа backend. Перезагрузка и ошибка
  запроса не теряют текст, адресата и время.
- Отменить публикацию можно существующим действием «Скрыть в PWA». Изменение
  текста и перенос времени будут отдельным инкрементом, чтобы сохранить историю
  revisions и не подменять уже созданную запись.

## Интерфейсы

- `POST /staff/api/v1/news/local` — только global admin; строгий JSON-контракт
  `{schemaVersion, ownerType, ownerId, text, publishedAt}`.
- Student/Family `GET /{audience}/api/v1/news` и detail endpoint фильтруют
  будущие публикации по серверному времени.
- `GET /{audience}/api/v1/notification-events` не возвращает событие раньше
  `deliver_after`.
- Изменение, initial visibility, notifications и privacy-safe audit
  `news_local.created` фиксируются одной SQLite-транзакцией.

## Realtime-граница

Создание сразу инвалидирует Staff moderation list. Будущая публикация остаётся
скрытой на клиентских чтениях до срока, поэтому ранняя инвалидация не раскрывает
её. Существующий content scheduler раз в пять секунд проверяет, появилась ли
хотя бы одна due local publication после предыдущего успешного прохода, и
посылает `local-news-published` для `news` и `notification-events`. Поэтому уже
открытая вкладка обновляется независимо от Web Push; обычная погрешность — до
пяти секунд.

Отдельный durable scheduler/lease не используется. NATS остаётся
неавторитетным refetch hint, и два production-worker могут одновременно послать
одинаковую инвалидацию. Два безопасных refetch несколько раз в неделю дешевле,
чем новый distributed state. После рестарта websocket reconnect всё равно
требует полный authoritative refetch, поэтому старые окна не воспроизводятся.

## Проверка

- Python integration: права admin/teacher, строгая валидация, course/group
  visibility, атомарные notifications/audit и отсутствие ранней выдачи.
- TypeScript unit: Zod-контракт, HTTP client, reload-safe draft и Moscow→UTC.
- Storybook:
  `pages-staff-local-news-composer--scheduled` и
  `product-news-moderation--scheduled-local`.
- Сводный результат записан в
  [`pwa_tests/reports/phase8-local-scheduled-news.md`](../../pwa_tests/reports/phase8-local-scheduled-news.md).
- Due-time realtime proof:
  [`pwa_tests/reports/phase8-local-news-due-invalidation.md`](../../pwa_tests/reports/phase8-local-news-due-invalidation.md).
