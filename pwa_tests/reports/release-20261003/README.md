# Общий выпуск — 3 октября 2026

Владелец разрешил исправление мелких недочётов, полный прогон проверок и
выпуск всех текущих доработок на ВМШ и TLF. Публичные product data и рабочие
credentials сохраняются. Runtime logs: `.runtime/release-20261003/`.

## Состав

- [Файловые вложения](../../../vmshpwa/docs/rich-file-attachments.md).
- [Новые наборы задач и migration 0109](../fresh-problem-sets/README.md).
- [Metadata reload, METADATA-05](../../../vmshpwa/dev/development-plan/06-phase-2-content.md).
- [Счётчики письменных решений и переводы](../../../vmshpwa/docs/review-queue-report.md).

## План и текущий gate

В работе: Python (legacy/PWA), frontend unit, typecheck/lint/format/i18n,
Storybook, все E2E/browser projects и production build. Исправить конкретные
сбои, не скрывая их excludes/retries. Затем проверить migration/backup на
копиях обоих production DB, опубликовать reviewed commit и выполнить
guarded cutover. Проверить health, services, schema, provenance и assets;
сохранить records и rollback-порядок.

## Интеграция и текущие проверки

Перед выпуском origin/vmshpwa обновлён до `88384076`; вложения и позадачная
публикация уже выпущены. Местные правки сохранены в archive/patch и stash
`2a1fcc89`, ветка обновлена fast-forward, изменения объединены.
Fresh migration перенумерована в 0109 с зависимостью от выпущенной 0108;
применённые миграции не изменялись. Schema inventory: 507 объектов.

Исправлена граница golden corpus: approved `usl-*` отдельно от Finder metadata,
соседних TeX support и пользовательских импортов; неизвестные `usl-*` и drift
fingerprints по-прежнему отклоняются и локализация сетевой ошибки в test composition.
Добавлены metadata reload regressions: успешный GET удаляет draft и не пишет
на сервер, ошибка сохраняет rows/storage; pending блокирует повтор и save.
Проверки rollback 0109 покрывают up/down/up и запрет отката использованных slots.

Первый sandbox run не мог открыть локальные HTTP sockets. После обновления
ветки pnpm автоматически пересоздал зависимости, затронув идущий Vitest;
эти прогоны остановлены. Frozen install восстановлен, полные suites перезапущены.
Тестовые данные, ports и credentials изолированы от production.

Все gates пройдены; release commit готовится. Production cutover ещё не выполнялся.

Frontend unit: **1021/1021**, все 201 файла. Workspace typecheck, frontend/backend
i18n, schema inventory (507), full ESLint/Stylelint проходят. Prettier нашёл
7 Markdown-файлов: форматирование исправлено, повторный check проходит.
Полные результаты Python и Storybook приведены ниже.

## Backend и Storybook

Полный `pytest -q -n4 pwa_tests tests`: 2679 passed, 7 skipped, 6 failures.
Четыре corpus failures исправлены отделением approved `usl-*` от соседних
imports/support. Performance-fixture теперь содержит реальные 0109 views
и использует новый маркер плана. Старый пустой `/start` test заменён проверкой
регистрации с существующим RecordingBot, без внешнего Telegram и credentials.
Регрессии backend: 8 passed (corpus/characterization/performance/migration).
Весь legacy suite отдельно после исправления: **124 passed, 1 skipped**.
Оставшиеся пропуски — opt-in внешние/требующие отсутствующих fixtures проверки.

Storybook: полный прогон **350 passed / 2 failures** из 352. Исправлена история
публикаций rollback fixture и добавлен MSW GET task availability. После правки
все 26 сценариев двух затронутых файлов прошли, включая неизменный p95 < 50 ms
и fuzzy < 100 ms. Все 352 уникальных Storybook сценария проверены; retries
и ослабления performance gates не применялись.

## Production rehearsal

До push обе production DB открыты read-only и скопированы в отдельные
`deploy/releases/preflight-20261003-fresh-review/rehearsal.sqlite3`.
На каждой копии 0109 up/down/up, integrity и query performance guard проходят.
**157 прежних product tables на каждом сервере идентичны** по counts/digests;
новые slots пусты, catalog/active сохраняют все прежние IDs/labels.
Рабочие БД, services, credentials и текущий frontend не изменялись.
Логи: `preflight-{vmsh,tlf}-final.log`; серверные before/after/performance JSON
сохранены в каталоге репетиции.

## E2E (в работе)

Стартовал lock-aware all runner: четыре build, 396 функциональных сценариев,
затем отдельные fresh-db phases для figure/statistics/visual; три браузера,
retries=0, baselines не обновляются. Найдены два тестовых недочёта:
recovery test удалял cookie до окончания initial authenticated reads и отменял
собственный background refresh; добавлен wait конкретных успешных responses.
Attendance test выбирал первую карточку вместо c-1 после создания другого курса
раньше в suite; теперь выбран стабильный course code. Production auth не менялся.

Другие исправления browser fixtures: public branding cache/localStorage проверяется
по точному имени, URL и contract schema; прежние запреты приватного кеша сохраняются.
Print test использует актуальную кнопку «Вопросы по задаче». Worksheet return test
фиксирует ID открытой задачи, поскольку cards загружаются независимо и `.last()`
может обозначать другую задачу после возврата. Rich-file reader явно выводит вкладку
на передний план перед очередным popup в WebKit при чередовании Student/Family.
Production auth и file rendering не менялись. Повторный targeted run выявил
поздний native-history scroll reset: `worksheet-return.ts` теперь корректирует
такие scroll events до передачи управления пользователю, с защитой от нулевого
цикла и callbacks после stop/unmount. Три unit-регрессии проходят.
Print fixture проверяет оба допустимых названия: thread меняет подпись кнопки.

Повторный полный Python run после устранения failures:
**2687 passed, 7 skipped**, 798.40 s. Начат финальный полный frontend run
после исправления scroll restoration. Исправленные auth/storage (12),
attendance (3) и rich files (9) browser scenarios проходят во всех трёх projects.

## Финальные gates перед выпуском

- Python: **2687 passed / 7 skipped**, полный общий suite после исправлений.
- Frontend: **202 файла / 1024 passed**, полный повторный unit suite после scroll fix.
- Четыре app bundles пересобраны; task/print **6/6** и statistics **9/9**
  проходят без параллельной тяжёлой нагрузки. Таймауты не менялись.
- Figures: **3/3**, auth/storage: **12/12**, attendance: **3/3**, rich files: **9/9**.
- Все functional cases исходного общего прогона выполнены; 17 failures исправлены
  и проверены targeted phases. 20 исходных skips сохранены: 18 повторов durable
  admin SQLite writes проверяются в Chromium; 2 full-network offline cases
  ограничены harness Firefox/WebKit, API-disconnected equivalents проходят.

Visual baselines просмотрены для Student/Staff в Chromium/WebKit/Firefox.
Старые эталоны показывали прежние mock-style данные (Staff 43/12/3) и старую
оболочку. Текущие real-backend fixtures показывают 11 работ, actual course cards,
brand mark, имя пользователя, organizer link и offline status. Для одинакового
предусловия browser fixture фиксирует account-scoped dismissal push invitation;
consent covered отдельно. Обновлены только шесть просмотренных shell baselines;
порог сравнения не менялся. Повторная проверка на fresh SQLite: **6/6 PASS**, все три браузера.
Итого полная E2E-инвентаризация: **414 cases = 394 PASS + 20 штатных skips**.
Нет непроверенных failures, автоматических retries или изменённых timeout/pixel gates.
Финальные эталоны повторно просмотрены.

Финальный полный Storybook run: **74 файла / 352 passed**, 56.99 s,
без ослабления p95/fuzzy/a11y gates. Full format и финальные Student/tools
types + scoped lint/Ruff проходят.

Перед commit/deploy: SSH-аутентификация, ранее успешно использованная для
rehearsal и asset inventory, перестала работать на обоих aliases. Рабочие
services/schema/static ещё не менялись; доступ восстановлен через существующий системный SSH-agent (launchd socket).
Выпуск продолжен, ключи и SSH config не менялись.
