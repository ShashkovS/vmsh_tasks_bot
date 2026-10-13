# Позадачная публикация

Реализация проверена в отдельном worktree, ветка
`codex/problem-release` от `vmshpwa` (`6a3891f0`).

## Решение

Открытие задач принадлежит занятию группы, независимо от публикации неизменяемого
листка. Все задачи исходно открыты. Один переключатель управляет всем условием
с подпунктами. Off скрывает задачу у всех Student/Family, сохраняя работу и
статистику. Занятие с нулём открытых задач остаётся видимым и сообщает
«Задачи скоро откроются».

Сопоставленные стабильные problem IDs сохраняют состояния между версиями.
Новая задача закрыта, если в текущем занятии есть закрытые задачи; иначе открыта.
Новые подпункты наследуют состояние общего условия. Объединение задач с
разными состояниями закрывает объединённое условие.

Переключения сохраняются сразу, групповые операции атомарны. Конкуренция
проверяется общей версией доступности и ID проверяемого листка. Перед первой
публикацией готовый сопоставленный листок допускает подготовку переключателей.
После публикации редактируется только её текущая версия; другие превью
показывают прогноз состояний.

## Реализация и границы

- [Миграция](../../migrations/0108.pwa_problem_release.sql), механическое
  [хранилище](../../db_methods/pwa/problem_release.py) и
  [доменный сервис](../../models/pwa/problem_release.py).
- [Staff API](../../apps/pwa_api/problem_release_routes.py):
  GET/PUT `/staff/api/v1/group-lessons/{id}/problem-release`.
- [Zod-контракт](../packages/contracts/src/problem-release.ts),
  [StaffProblemReleasePreview](../apps/staff/src/staff-problem-release-preview.tsx)
  и [transport](../apps/staff/src/problem-release-client.ts). Контролы находятся
  в PWA-превью условий; одна строка управляет всем условием с подпунктами.
- [Student offline transport](../apps/student/src/offline-student-data.ts)
  сравнивает `problemReleaseVersion` раньше времени загрузки, чтобы stale
  bundle не вернул известные закрытые задачи.
- Student/Family получают фильтрованные условия, hint/solution, списки и
  счётчики. Telegram, готовый PDF и полная Staff-статистика не фильтруются.
- WebSocket инвалидирует данные после commit, без push/Telegram-рассылки.
  Reconnect восстанавливает состояние из SQLite. Offline показывает последнюю
  полученную версию; известная более новая версия доступности имеет приоритет над старым bundle.
- Off не удаляет черновики или очередь отправки. Новые операции по закрытой
  задаче отвергаются; ранее принятые идемпотентные операции сохраняют receipt.

## Проверка

Пройдены 91 тест SQLite/HTTP (`test_content_repository.py`,
`test_content_http_api.py`, [test_problem_release.py](../../pwa_tests/integration/test_problem_release.py)).
Включены подготовка Off до первой публикации, ноль задач у обеих аудиторий,
запрет нового ответа и reveal, replay принятого ответа, конфликт версий,
новые задачи при закрытом листке и сохранение Off после исправления условий.

Пройдены 975 общих frontend unit-проверок и 46 сфокусированных unit-проверок контентных контрактов/клиента, Staff и offline,
включая [регрессию старого bundle](../apps/student/src/prepare-offline-lessons.test.ts).
[Storybook](../apps/staff/src/staff-problem-release-preview.stories.tsx):
AllOpen (interaction), AllClosed и RevisionPreview — 3/3.
Полный `make pwa-test`: 975 frontend прошли; backend исходно дал 2444 passed
и 17 failures (отсутствующие ignored corpus/config files в новом worktree и
устаревший schema object count). После подготовки отдельной копии ровно
54 утверждённых corpus-файлов, reference pipeline-файлов и пустого локального
config, обновления ожидаемого count 497 → 501 все 17 прошли в повторных запусках
`pytest --lf`. Итого проверены 2461 backend сценарий, 6 skipped. Секреты не
копировались, Telegram polling/Google не запускались; локальные inputs не
входят в commit.

`make pwa-typecheck pwa-i18n-check`, schema inventory, scoped ESLint/Ruff и
четыре production-сборки проходят. E2E запуск: lock-aware
`python -m vmshpwa.scripts.e2e_runner --mode problem-release`, retries 0.
Финальный прогон — 3/3 в 22.9 секундах после сборки/seed. Начало preview
ждёт доступную кнопку; reconnect проверяется после подтверждённого Staff
состояния и допускает штатные таймауты транспорта, без перезагрузки.

[E2E](../e2e/problem-release.spec.ts) с реальным aiohttp: исходная выдача
15 → 0 → 2 → 5 → 15 и обратное скрытие без reload прошли в Chromium,
WebKit и Firefox. Reconnect без reload также прошёл во всех трёх браузерах.
Для WebKit/Firefox с реальным `context.setOffline` дополнительно посылаются
стандартные browser offline/online events: их эмуляция Playwright неполна.
Использована свободная пара loopback-портов 5381/8381: стандартные 5380/8380
заняты параллельной задачей. Временные подстановки только origin/портов и
одноразовые тестовые ключи восстановлены после запуска; стандартная
конфигурация не изменяется. MSW и внешние сервисы в E2E не используются.
Светлые, тёмные и мобильные снимки сохраняются в `vmshpwa/test-results`;
visual baselines не обновлялись. Развёртывание не выполнялось.

## Интеграция с актуальной vmshpwa

1 октября начато вливание `vmshpwa` (`3bb20281`, затем `73d6730e`) в `codex/problem-release`.
Сохраняются новые настройки metadata, индекс receipt и редактор рисунков.
[Content workspace](../apps/staff/src/content-page.tsx) объединяет редактор рисунков
и переключатели в одном PWA-превью; фильтрация доступности применяется после
замороженного оформления публикации. Миграция доступности перенумерована в 0107
после 0106 рисунков; schema artifacts генерируются из общей цепочки миграций.
Merge кода сохранён в `188d97eb`; второй merge включает только новые
production-отчёты `73d6730e` и протокол этих проверок. Оба merge завершены
локально; текущая `vmshpwa` полностью входит в историю feature-ветки.

Проверки общей ветки:

- `.venv/bin/python -m pytest pwa_tests -q`: **2501 passed, 5 skipped**,
  полный прогон; 20 предупреждений зависимостей.
- `pnpm exec vitest run --project unit --maxWorkers=2`: **978 passed**,
  2 failures в неизменённом `media-diagnostics.test.ts` после timeout
  холодного импорта 5 s; продолжение первого теста затронуло следующий.
  Отдельно с `--maxWorkers=1 --testTimeout=15000`: **2 passed**.
  Итого проверены все **980** unit cases. Неограниченный первый прогон
  также прервался с timeout; ограничение workers применяется только в команде.
- `make pwa-typecheck pwa-i18n-check pwa-schema-check`: проходят,
  **502** schema objects. Каталоги пересобраны `make pwa-i18n-extract`.
- ESLint для разрешённых TS-конфликтов и регрессии, Ruff для Python-тестов:
  проходят. Исправлен только лишний non-null assertion в JSX merge.
- Четыре production-сборки и **3/3** release E2E в Chromium/WebKit/Firefox:
  проходят; 15 → 0 → 2 → 5 → 15, обратное скрытие и reconnect без reload.
- Изолированный gate figure-layout/whiteboard-export/worksheet-print:
  **12/12** в Chromium/WebKit/Firefox, с той же сборкой и отдельной свежей
  E2E-базой. Итого **15 E2E**, без retries и обновления visual baselines.

Повторно использованы независимые порты 5381/8381 и lock-aware
`commands_for_mode` / `run_commands` из E2E runner. Добавлено только временное
исправление test Origin в figure-layout fixture; все подстановки восстановлены
после запуска. Desktop light и mobile dark показывают переключатели и
редактор рисунков вместе без обрезания интерфейса. Runtime основной рабочей
копии не затрагивался; production rollout рисунков сохранён как upstream proof,
развёртывание позадачной публикации не выполнялось.

## Выпуск — 2 октября 2026

Владелец разрешил commit/push, VMSh autodeploy и ручной выпуск TLF.
Перед выпуском подлит `e20bbed9`: новые типы metadata и внимание к ответам
сохраняются. Миграция доступности перенумерована в 0108 после уже выпущенной 0107.
Глобальная навигация по непрочитанным ответам исключает Off; переключения
инвалидируют также Student questions. Локальные gates, TLF cutover,
migration rehearsal и проверка сохранности данных завершены.

Ручной выпуск: [deploy_problem_release.sh](../../docs/deploy/tlf-app/deploy_problem_release.sh)
с точным SHA, frozen deps и изолированной сборкой;
[checker](../../docs/deploy/tlf-app/problem_release_data_check.py) сравнивает все
прежние product columns, проверяет default-On и append-only guards.
Up/down/up репетируется на копии до остановки writers. До их повторного запуска
можно откатить только 0108/source/static; после — source/schema остаются новыми,
откатывается совместимый старый static, сохраняя новые flags/audit/Zoom.

Локальные gates перед выпуском: 165 backend / 72 frontend, TypeScript,
i18n, schema 504 objects, Ruff и cutover up/down/up проходят.
Browser gate выявил старый GET после успешного toggle (Firefox: 4 вместо 5,
409 на следующем If-Match). Staff теперь отменяет предыдущий refetch перед
записью и читает ETag из подтверждённого Query cache.
[Регрессия delayed GET](../apps/staff/src/staff-problem-release-preview.test.tsx)
проходит. Ещё 40 auth/realtime/Staff unit-проверок проходят, включая отмену
старого HTTP-запроса при восстановлении сети. [RealtimeProvider](../packages/app-shell/src/realtime.tsx)
принудительно сверяет активные HTTP-модели по `online` для ранее подтверждённой
в этой вкладке сессии: кешированный offline GET может считаться свежим в Query,
а ошибка проверки сессии останавливает WS. Сервер повторно проверяет права;
старая ошибка не перекрывает новую подтверждённую авторизацию.
[Регрессия](../packages/app-shell/src/realtime-provider.test.tsx) сохраняет
проверку отсутствия socket до авторизации. E2E после доказанного возврата
вкладки в foreground дополнительно доставляет `visibilitychange`, как уже
принято в `news-notifications.spec.ts`: Playwright может пропустить это событие.
Финальная трёхбраузерная проверка: **3/3 за 52.6 s**, retries 0,
15 → 0 → 2 → 5 → 15, reconnect и обратное скрытие без reload.
Предыдущий запуск завершился ENOSPC при записи WebKit-артефакта; освобождён
только собственный Python bytecode cache worktree, успешный запуск повторён
на свежей базе без записи `.pyc`. Support с этой же сборкой и новой E2E-базой
дал **5 passed, 1 failed** (Firefox: viewport ratio 0 после 5 s при переходе
к старому ответу). Изолированный `support --project firefox` со свежей базой:
**2/2 за 1.0 min**, без изменения source и retries. Проверены все **6**
support cases; вместе с позадачной публикацией — **9** уникальных сценариев.
До выпуска проверены 410 прежних публичных JS/CSS URL (205 на портал),
их SHA256 и MIME сохранены для проверки после cutover.

### Production подтверждён

Merge-коммит `0b2964a80b6db6e94fa04f478848092a0f3dfdb6` отправлен в
`origin/vmshpwa`. VMSh выпущен существующим webhook, TLF —
закоммиченным `deploy_problem_release.sh` с этим точным SHA.

| Портал                            | Активный frontend                               | Schema                                 | HTTP    |
| --------------------------------- | ----------------------------------------------- | -------------------------------------- | ------- |
| [VMSh](https://vmsh.shashkovs.ru) | `0b2964a80b6d-20261002112802`                   | 80 migrations, current, quick_check ok | 25 PASS |
| [TLF](https://prep.leaders.tech)  | `tlfprep-20261002-problem-release-0b2964a80b6d` | 80 migrations, current, quick_check ok | 25 PASS |

Все четыре production artifacts каждого портала проверены: Sentry включён,
MSW/prototype выключены, release/media origin корректны. Во всех 15 VMSh и
3 TLF занятиях release version = 1; flags/events = 0: все существующие задачи
открыты по умолчанию. Immutable audit guards присутствуют.
Все **410** прежних публичных JS/CSS URL после cutover имеют прежние SHA256,
MIME и HTTP 200; уже открытые вкладки сохраняют доступ к своим bundles.

VMSh backups: `vmsh-before-deploy-20261002112858.sqlite3` /
`vmsh-after-deploy-20261002112948.sqlite3`, integrity ok, default-On проверен
в post-deploy snapshot. Из 155 прежних product tables 152 имеют одинаковые
hash. Добавлена одна auth event и одна consumed-refresh запись; все прежние
строки этих таблиц сохранены, сессии не удалены. В одной сессии изменены только
`last_seen_at`, `refresh_secret_hash`, `updated_at`, `version`.
Это совместимо с обычным refresh между двумя backup, первый из которых
создан до остановки writers. Закрытые backups сравнивались на временных
серверных копиях, чтобы SQLite мог создать WAL sidecars; оригиналы не менялись.

TLF record:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261002-problem-release-0b2964a80b6d/`.
Up/down/up на копии — PASS, все **155** старых product tables/columns
и credentials идентичны при остановленных writers. Backups
`20261002T112938.930161Z` / `20261002T113019.363874Z` имеют integrity ok и
по 3 raw Zoom receipts. После открытия writers получен ещё один receipt
(live count 4); тестовых production-событий не создавалось.

PWA/Telegram VMSh, PWA/Zoom TLF, analytics timers и NATS активны; maintenance
снят. NATS PID VMSh **1409**, TLF **1936264** прежние. Backend health прошёл
до frontend activation. Предупреждение VMSh webhook о `docs/deploy` относится
к новому TLF runbook/cutover: установленные VMSh webhook/nginx/systemd файлы
не менялись, переустановка не требуется.
[Машиночитаемый пруф](../../pwa_tests/reports/problem-release/production-proof.json).
