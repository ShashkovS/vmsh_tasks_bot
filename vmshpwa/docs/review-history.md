# История письменных проверок — 9 сентября 2026

Принятый план: история по курсу/занятию, своим проверкам для Teacher и всем
для Admin, fuzzy student search, задача и комментарий. Карточка исправляет
вердикт, комментарий и аннотации append-only. Поздний чужой вердикт можно
заменить только с подтверждением и optimistic latest-review/thread-version.
Активная чужая аренда запрещает запись; новая посылка остаётся в очереди.
Быстрый возврат сохраняет последний review ID по аккаунту и не теряет черновик.

## Реализация

- `apps/pwa_api/review_routes.py`: `GET /staff/api/v1/review/history`
  возвращает варианты фильтров и страницу из 50 кратких записей; параметр
  `review` загружает отдельную карточку с evidence, аннотациями и историей.
  `course`, `lesson`, `teacher`, `student`, `problem`, `comment`, `cursor` —
  фильтры. `db_methods/pwa/review_history.py` ограничивает все выборки текущим
  Staff scope (включая все группы объединённого evidence) и автором для Teacher,
  выполняет буквальный Unicode-casefold поиск.
- `models/pwa/review_corrections.py` и `db_methods/pwa/review_corrections.py`:
  расширенная команда принимает `annotations`, `expectedLatestReviewId`,
  `expectedThreadVersion`, `confirmReplaceNewer`. Проверка прав выполняется
  до idempotent replay; CAS и аренда проверяются внутри write-транзакции.
  Новые аннотации ограничены выбранным immutable evidence. Для старого клиента
  сохраняются исходные аннотации и запрет замены более нового вердикта.
  Аудит содержит `correctsReviewPublicId` и `supersedesReviewPublicId`.
  Наличие новой очереди сохраняет статус ожидания и саму очередь.
- `migrations/0086.pwa_review_history.sql`: индексы автора/времени и группы/занятия.
  Новых сервисов, БД или фоновых процессов нет.
- `vmshpwa/packages/contracts/src/review-history.ts`, `review-reactions.ts` и
  `packages/app-shell/src/review-queue-client.ts`: runtime-проверяемые контракты.
- `vmshpwa/apps/staff/src/review-history-page.tsx`, `review-history-search.ts`,
  `routes/review.history.tsx`: список, URL-фильтры, существующий fuzzy-поиск,
  редактор фото и оценки по шкале курса, подтверждение замены, сохранение
  черновика. Условие берётся из Web AST версии исходного материала; если
  производная отсутствует, используется сохранённый текст с явным пустым состоянием.
- `last-completed-review.ts`, `review-workspace-page.tsx`, `review-series-page.tsx`
  и `routes/review.tsx`: account/runtime-scoped ID последней проверки и общий
  редактор исправления. Текущая работа серии остаётся смонтированной.

## Проверки

- `pwa_tests/integration/test_review_queue_http_api.py`: история, собственные
  проверки, русский literal search, 53 записи без дублей на двух страницах,
  подтверждённая замена нового чужого вердикта, optimistic conflict, replay,
  аннотации и их удаление только в новой версии, чужая аренда, новая посылка.
- Регрессия: `test_review_queue_repository.py`, `test_schema_inventory.py`,
  `test_staff_testing_http.py`. Совместный прогон: **73 passed**.
- `review-series-page.test.tsx`: сохранность следующей смонтированной работы,
  восстановление черновика исправления и обязательное подтверждение замены,
  изоляция ID последней проверки по аккаунту и runtime.
  Вместе с review-draft, fuzzy search, контрактами и клиентом: **23 passed**.
- `vmshpwa/e2e/review-workspace.spec.ts`: реальный HTTP + браузер + SQLite,
  исправление из истории с удалением пометок, reload и Student/Family-проекции.
  **Chromium, WebKit, Firefox: 3 passed** (`make pwa-e2e-review`).
  В тесте явно прокручивается SVG-область в viewport перед рисованием.
  Аналитика тестового запуска изолирована через
  `VMSH_ANALYTICS_DB_FILENAME=$PWD/.runtime/pwa-e2e/analytics.sqlite3`.

Выпуск: миграция 0086 вместе с backend/frontend; никаких новых настроек сервера.
Ruff, ESLint, Staff TypeScript и `make pwa-build` прошли.
Полный исторический набор вне затронутых компонентов не переоценивался:
ранее зафиксированные baseline-сбои этого репозитория не относятся к выпуску.
