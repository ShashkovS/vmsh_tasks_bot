# Phase 8: явная сверка удаления Telegram-поста

Дата: 3 августа 2026 года.

## Решение

Обычный Bot API update не сообщает боту об удалении уже опубликованного
`channel_post`. Поэтому Staff не изображает автоматическую гарантию, которой
нет: global admin явно отмечает зеркальный пост удалённым либо исправляет
ошибочную отметку. User-account MTProto client, новый сервис и новая таблица не
добавлялись.

## Реализовано

- admin-only `PATCH /staff/api/v1/news/{post_id}/source-state`;
- строгий JSON v1 с `deleted|present` и обязательной причиной;
- optimistic `If-Match`, `409` для stale/повторного перехода;
- одна транзакция для `news_posts`, `news_visibility` и `audit_events`;
- немедленное исключение `source_deleted` из Student/Family feed;
- безопасные audit actions `news_source.marked_deleted|marked_present` без
  Telegram ID, текста поста и credentials;
- Staff confirmation dialog и отображение событий в общем audit;
- Zod contract, typed client и interaction story
  `product-news-moderation--lifecycle`.

## Автоматические проверки

- Focused Python moderation/audit: **6 PASS**.
- Полный PWA Python gate: **1564 PASS / 6 intentional skips / 9 warnings**,
  восемь worker-процессов, **70.97s**.
- Frontend unit: **111 files / 588 PASS**, **9.13s**.
- ESLint + Stylelint: **PASS**.
- Strict TypeScript: **PASS**.
- Production build Student/Family/Staff: **PASS**; оба PWA service worker
  собраны через `injectManifest`.
- `git diff --check`: выполняется перед коммитом.

Интеграционный API-тест отдельно доказывает teacher `403`, Student feed,
stale-version conflict, correction, audit filter и rollback обеих таблиц при
искусственной ошибке audit insert.

## Незакрытый browser gate

`make pwa-storybook-test` 3 августа 2026 года завершился до импорта stories и
до выполнения тестов: Playwright Chromium аварийно остановился в macOS
`MachPortRendezvous` (`bootstrap_check_in`, error 141). Результат не считается
PASS или свидетельством поведения компонента. Production build и jsdom unit
gates зелёные; browser interaction/a11y нужно повторить после исправления
локального launcher. Visual snapshots не обновлялись.

## Связанные файлы

- Runbook:
  `vmshpwa/docs/telegram-news-deletion-reconciliation.md`.
- API/domain/storage:
  `apps/pwa_api/news_moderation_routes.py`,
  `models/pwa/news_moderation.py`,
  `db_methods/pwa/news_moderation.py`.
- API integration:
  `pwa_tests/integration/test_phase8_news_moderation.py`.
- Contracts/client/UI:
  `vmshpwa/packages/contracts/src/news.ts`,
  `vmshpwa/packages/app-shell/src/news-moderation-client.ts`,
  `vmshpwa/packages/product/src/news-moderation.tsx`,
  `vmshpwa/apps/staff/src/staff-news-page.tsx`.
