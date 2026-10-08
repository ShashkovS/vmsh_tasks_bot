# Phase 8 proof: исправление опубликованной локальной новости

Дата проверки: 3 августа 2026 года.

## Проверяемый результат

- Global admin исправляет plain text уже опубликованной local PWA news через
  `PATCH /staff/api/v1/news/{postId}/local` с optimistic `If-Match`.
- Исправление создаёт новую immutable `news_revisions`, повышает revision и
  visibility version, сохраняет privacy-safe audit и обновляет `editedAt`.
- Исходные owner и `published_at` неизменны. Переданный для опубликованной
  записи `publishedAt` отклоняется кодом
  `local_news_publication_time_locked` без частичного изменения.
- Сохранённые `notification_events` и `notification_deliveries` до и после
  исправления совпадают. Повторной in-app/Web Push рассылки нет.
- Student и Family получают исправленный текст, новую revision и `editedAt`.
- Staff показывает действие «Исправить опубликованную», заблокированное
  исходное время и отметку «обновлено». Черновик текста остаётся
  runtime/account/post/version-scoped в `localStorage`.

## Реализация и трассировка

- Domain rule: `models/pwa/local_news.py::edit_local_news`.
- Mechanical SQLite writes: `db_methods/pwa/local_news.py` и существующий
  immutable revision insert в `db_methods/pwa/news.py`.
- HTTP, optimistic version и audit:
  `apps/pwa_api/news_moderation_routes.py::edit_local_publication`.
- Zod и HTTP client: `vmshpwa/packages/contracts/src/news.ts` и
  `vmshpwa/packages/app-shell/src/news-moderation-client.ts`.
- Staff UI: `vmshpwa/apps/staff/src/staff-news-page.tsx`,
  `staff-local-news-composer.tsx` и
  `vmshpwa/packages/product/src/news-moderation.tsx`.
- Story IDs: `pages-staff-local-news-composer--editing-published` и
  `product-news-moderation--published-local-correction`.
- Production E2E scenario:
  `vmshpwa/e2e/news-notifications.spec.ts` — disabled publication time, PATCH
  без `publishedAt`, revision 2 и visible update marker.
- Commits: `f24ba50` (domain/API/integration) и `fc43f4f`
  (contracts/Staff/Storybook/E2E).

## Автоматические проверки

- Полный `test_phase8_news_moderation.py`: **12 PASS** в 8 workers.
- Focused frontend unit: **3 файла / 6 PASS**.
- Полный frontend unit: **114 файлов / 594 PASS**.
- ESLint, Stylelint, strict TypeScript и production build Student, Family,
  Staff: **PASS**.
- Focused Storybook browser-mode запуск дважды не дошёл до stories: системный
  Chromium завершился на macOS `MachPortRendezvous` code 141. Этот запуск не
  записан как зелёный interaction/a11y gate.
- Свежий production E2E news не дошёл до браузера: параллельно незавершённая
  migration 0076 изменила seed schema digest до обновления canonical digest.
  Это не считается пройденным E2E; сценарий и предыдущий news corpus не
  используются как замена свежему результату.

Visual snapshots не обновлялись. Ручное visual acceptance и свежие
Storybook/E2E browser gates остаются открытыми до устранения двух внешних
условий выше.
