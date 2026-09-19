# Phase 8: authenticated news feed proof

Дата: 2026-07-29.

## Граница среза

- `db_methods/pwa/news.py` выполняет только прямые SQLite-чтения ленты, одной публикации и её медиа.
- `apps/pwa_api/news_routes.py` определяет доступ Student/Family по подтверждённой сессии и активным курсам/группам, формирует HTTP-ответы и пользовательские ошибки.
- `packages/contracts/src/news.ts` строго проверяет wire-формат, включая rich-text entities, медиа, cursor и request ID.
- `packages/app-shell/src/news-client.ts` читает список и detail endpoint с audience-specific API base и штатным refresh сессии.
- Реальные маршруты Student и Family используют backend; прототипы в `pages.tsx` сохранены только для Storybook.

## Проверяемое поведение

- новости курса и доступной группы складываются, а общий пост не дублируется в Family;
- список имеет стабильную cursor-пагинацию, detail URL проверяет ту же область доступа;
- публикация не появляется до сохранения всех её медиа;
- форматирование после emoji сохраняет Telegram UTF-16 offsets;
- неизвестные поля и небезопасные media URL отклоняются TypeScript-контрактом;
- loading, empty, error/forbidden и «показать более ранние» подключены к реальному query state;
- source title, revision state, изображения и документы доходят до принятого `TelegramRichPost`.

## Результаты

- Ruff format/check: passed.
- Backend news/app-factory regression: 48 passed.
- TypeScript: contracts, app-shell, product, Student и Family passed.
- Frontend unit: 72 files, 478 passed.
- Student production PWA build: passed, `injectManifest`, 107 precache entries.
- Family production PWA build: passed, `injectManifest`, 92 precache entries.
- Visual snapshots: не изменялись; компонент использует уже принятую Storybook-композицию `Product/News`.

## Следующий срез

Сохранение опубликованной ленты в audience/owner-scoped IndexedDB для чтения без сети, затем realtime invalidation и Staff moderation/local publications.
