# Инженерный контракт и Definition of Done

## Цель

Каждый этап должен оставлять репозиторий в состоянии, которое можно запустить, продемонстрировать, проверить автоматически и безопасно продолжить другой моделью или человеком. «Backend готов, UI потом» и «макет есть, данных нет» не являются завершёнными этапами.

## Неподвижные границы

- Используется существующий Python/aiohttp backend. Второй backend и отдельная доменная БД не создаются.
- Telegram-бот остаётся параллельным adapter к общей доменной логике и общей SQLite.
- Новые dev/test-пути не загружают Telegram- или Google-конфигурацию и не обращаются к их API.
- Staff, Student и Family имеют разные base path, cookie, PWA scope, IndexedDB namespace и права.
- Agent-процессы запускаются только через `make pwa-agent-*`; human-порты, human-БД и polling Telegram не используются агентами.
- Новые таблицы и миграции добавочны. Legacy-путь не ломается до отдельного подтверждённого cutover.
- Производные HTML, Telegram-rich HTML, SVG/WebP и PDF не становятся ручным источником истины: источником остаётся LaTeX.
- `_vmsh_examples` и `_external_pipelines` не редактируются в рамках PWA-фичи.

## Definition of Ready этапа

До реализации этапа должны быть выполнены все пункты:

1. Решения из `01-decisions-and-boundaries.md` и статуса закрытого опросника `17-open-questions.md` учтены в scope этапа; новая реальная развилка явно зафиксирована до реализации.
2. API-схемы, error codes, query keys и WS invalidation keys добавлены в план или зафиксированы ADR.
3. Названы миграции, таблицы, индексы, backfill и rollback-путь.
4. Для UI есть принятые Storybook-компоненты либо явно согласованная временная заглушка.
5. Определены fixtures: happy path, empty, loading, error, forbidden, offline, reconnect и конфликт.
6. Назван минимальный вертикальный сценарий, который будет продемонстрирован владельцу продукта.

## Definition of Done этапа

### Работающий срез

- Пользовательский сценарий проходит от настоящего aiohttp endpoint до интерфейса.
- Production-код не использует MSW, prototype flag или mock auth.
- Telegram-совместимость либо подтверждена, либо сознательно не затрагивается и это записано.
- Ошибки не маскируются успешными заглушками; повтор операции безопасен там, где возможен offline/retry.

### Контракты и данные

- SQLite migration проходит на пустой seeded-БД и на копии схемы предыдущего этапа.
- Backfill идемпотентен и имеет dry-run/отчёт, если затрагивает legacy-данные.
- Zod-схемы проверяют все ответы API; Python fixtures и TypeScript contract fixtures совпадают.
- Даты хранятся в UTC; московское время используется как явно указанная бизнес-зона дедлайнов и расписания.
- Есть индексы под фактические list/detail/queue-запросы; `EXPLAIN QUERY PLAN` приложен для новых горячих запросов.

### Тестовая пирамида

- Python unit/domain tests проверяют правила и переходы состояний.
- Python API tests проверяют авторизацию, валидацию, error envelope, request ID и транзакции.
- TypeScript unit tests покрывают contracts, query keys, offline/outbox и чистые преобразования.
- Любой экран с значимой незавершённой работой имеет тест восстановления после reload/remount, изоляции аккаунтов, server-version conflict и очистки только после receipt/confirm/explicit discard. Serializable state проверяется в `localStorage`, blobs/outbox — в Dexie.
- Storybook содержит все значимые состояния изменённых общих и продуктовых компонентов; interactions проходят в browser mode.
- A11y addon остаётся `error` для Student, Family и Staff. Для Staff обязательны label/alt/ARIA/contrast; отдельный полноценный keyboard-аналог специализированного DnD не является общим gate. Исключения axe возможны только локально, с причиной и issue.
- Playwright использует production build/preview, настоящий aiohttp и отдельную seeded SQLite; MSW запрещён.
- E2E проходит в Chromium, WebKit и Firefox; PWA/SW-специфичное проверяется там, где браузер поддерживает механизм.
- Исторические Telegram tests запускаются отдельно, если менялась общая доменная логика.
- Нет формального процента coverage: в proof перечисляются непокрытые ветви и почему их риск приемлем.

### Качество и эксплуатация

- `pwa-format`, `pwa-lint`, `pwa-typecheck`, `pwa-test`, `pwa-storybook-test`, `pwa-build`, `pwa-e2e` зелёные в нужном профиле.
- В логи не попадают токены, cookie, тексты приватных работ и полные S3 URL, если они не нужны для диагностики.
- Sentry events имеют release, audience, route и correlation ID, но не содержат PII по умолчанию.
- Для фоновых задач описаны повтор, дедупликация, lease и поведение после падения процесса.
- Документация обновлена вместе с кодом; `routeTree.gen.ts` и другие generated-файлы не редактировались вручную.

## Обязательный набор доказательств

В конце каждого phase-файла уже есть шаблон. При закрытии этапа его placeholders заменяются ссылками/хешами:

1. Git revision и перечень миграций.
2. Команда seed и идентификатор fixture-набора.
3. URL/маршрут демонстрации и ожидаемый результат.
4. Результаты каждого test gate с датой и окружением.
5. Storybook story IDs и принятые screenshots/visual diffs.
6. Contract fixture и пример запроса/ответа без секретов.
7. Migration/backfill report и проверка rollback.
8. Sentry/лог/метрика или объяснение, почему на этапе не применимо.
9. Обновлённые документы и принявший решение человек.
10. Известные ограничения, каждое со следующим этапом или issue.

## Формат proof

Запрещено писать только «готово» или вставлять необработанный многостраничный лог. Хороший proof воспроизводим:

```text
- Revision: <git sha>
- Demo: make pwa-agent-seed && make pwa-agent-dev; /student/...; fixture <name>
- Tests: <command> — PASS, YYYY-MM-DD, macOS <version>
- Migration: <file>; empty/upgraded DB PASS; rollback <result>
- Stories: <story ids>; visual approval <link/path>
- Contracts: <fixture paths>
- Docs: <paths>
- Known limitations: <issue or “none”>
- Accepted by/date: <name>, <date>
```
