# Этап 12. Кандидат на пилотный деплой

## Цель

Довести текущую реализацию до закрытого пилота на настоящем сервере и начать
собирать обратную связь от владельца, нескольких школьников, семей и
преподавателей. Этот этап не требует закрыть все оставшиеся пункты фаз 0–11.
Telegram-бот остаётся рабочим параллельным каналом и способом отката учебного
процесса.

Полный публичный rollout по-прежнему выполняется по
[`production-rollout-checklist.md`](../../docs/production-rollout-checklist.md).
Здесь перечислен более узкий набор условий для первого закрытого запуска.

## Что входит в пилот

### Student PWA

- вход существующим логином и Telegram-токеном;
- выбор курса и доступной группы;
- чтение опубликованных условий, подсказок и решений;
- тестовые ответы с серверной проверкой;
- письменная сдача с фотографиями, сохранением черновика и повторной
  отправкой;
- просмотр статуса, проверки и переписки;
- новости, баннеры и in-app уведомления;
- профиль, смена режима и базовое offline/PWA-поведение.

### Family PWA

- отдельный вход;
- переключение связанных детей;
- просмотр текущего курса, активности, новостей и аудитории;
- настройка доступных категорий уведомлений;
- получение одного явного итога занятия после действия администратора.

### Staff SPA

- вход и разделение прав teacher/admin;
- рабочая сводка, чтение и публикация материалов;
- проверка письменных работ, вопросы и устный приём;
- новости и локальные публикации;
- управление курсами, группами, пользователями и web-аккаунтами;
- каталог аудиторий, план очного события и отдельная рассылка подтверждённого
  плана;
- просмотр статистики без сравнения конкретного школьника с группой.

## Что не блокирует первый закрытый запуск

- завершение всех визуальных вариантов и обновление всех screenshot-baseline;
- физическая проверка Web Push на каждом поддерживаемом устройстве;
- достижения и streak школьника;
- напоминания о дедлайне;
- полная автоматизация печати и отказ от всех Dropbox/Excel-процедур;
- расширенный markdown-редактор рассылок;
- перенос каждого исторического административного сценария из Google;
- оптимизация размера KaTeX precache и крупных frontend chunks;
- удобства, не влияющие на сохранность данных и основной учебный цикл.

Отложенная функция не должна показываться как работающая, если её endpoint или
сохранение ещё прототипные. Production build обязан оставаться без MSW и
prototype adapters.

## Обязательные локальные ворота кандидата

- production build Student, Family и Staff успешно собирается;
- lint, strict typecheck, frontend unit и обязательные interaction tests зелёные;
- PWA Python tests и затронутые legacy/Telegram-history tests зелёные;
- production-build Playwright проходит основной non-visual набор в Chromium,
  WebKit и Firefox без flaky-result;
- отдельные сценарии доказывают вход/выход, audience isolation, content,
  тестовую и письменную сдачу, review, новости, Family, аудитории, realtime,
  Service Worker и offline queue;
- rehearsal создаёт и мигрирует только копию `db/vmsh.db`, исходная БД не
  изменяется;
- backup/restore rehearsal проходит SQLite integrity и согласованные read-model
  проверки;
- статический release упаковывается и проверяется по manifest/checksums только
  из `pwa-production-build`: все три `build-provenance.json` подтверждают один
  release ID, Sentry/media origins и выключенные prototype/MSW;
- в отчёте нет credentials, персональных данных и публичных URL ученических
  фотографий.

Визуальный прогон и Storybook остаются обязательными инструментами ревью
дизайна, но незавершённая косметическая правка сама по себе не блокирует
закрытый пилот. Блокируют потеря данных, недоступный основной сценарий,
смешение аудиторий, сломанная навигация или невозможность отката.

## Обязательные серверные ворота

До первого входа пилотных пользователей должны быть фактически выполнены:

1. Выбран HTTPS FQDN и подготовлен отдельный production service profile.
2. Сделана согласованная резервная копия SQLite; все writers остановлены перед
   migration.
3. Yoyo migrations применены отдельной командой под lifecycle lock.
4. Проверенный static release активирован атомарным symlink switch. Каталог
   задаётся явным `PWA_RELEASE_ROOT` вне deployment checkout, а nginx
   обслуживает `<PWA_RELEASE_ROOT>/current`.
5. Отдельный PWA systemd unit запускает два worker без Telegram polling и
   Google loader; legacy Telegram service продолжает работать отдельно.
6. Nginx обслуживает три base path, API, WebSocket и Service Worker; login rate
   limit и security headers проверены установленным конфигом.
7. Production S3 credentials и media origin проходят redacted capability
   probe. Запись, чтение и удаление probe-object не затрагивают реальные
   работы.
8. Sentry получает synthetic frontend/backend error без cookie, токена, ответа,
   комментария или media URL.
9. Публичный HTTPS smoke проверяет health/runtime, history fallback, auth,
   WebSocket и manifests на уже разложенной сборке.
10. Выполнен ручной smoke отдельными тестовыми Student, Family, teacher и admin
    аккаунтами; реальные учебные данные не изменены.

Hostname, systemd/nginx paths и production secret source являются внешними
параметрами деплоя. Пока они не указаны и не проверены на сервере, локальная
сборка называется «кандидат на деплой», а не «задеплоено».

## Пилот и обратная связь

Ручной проход владельца по пустой базе описан отдельно в
[`manual-pilot-cycle.md`](../../docs/manual-pilot-cycle.md). Он является
операционным сценарием приёмки, а не вторым планом реализации.

- Сначала выдаётся доступ малой явно перечисленной группе тестировщиков.
- Telegram остаётся доступен всем участникам пилота; при инциденте учебный цикл
  возвращается в Telegram без ожидания исправления PWA.
- Для каждого сообщения об ошибке фиксируются audience, route, время, краткое
  действие и request ID. Нельзя просить присылать cookie, токен или исходную
  фотографию работы в общий чат.
- Потеря черновика, двойная отправка, чужие данные, невозможность войти или
  проверить работу имеют высший приоритет.
- Косметические замечания собираются отдельно и не смешиваются с инцидентами.

## Условия немедленного отката

- миграция или schema preflight не завершились;
- пользователь видит данные другого account/audience;
- подтверждённая работа, комментарий или classroom-plan теряются либо
  перезаписываются;
- основные Student/Staff сценарии недоступны;
- PWA deployment нарушил работу legacy Telegram adapter;
- public smoke, Sentry или backup после запуска показывают критическую ошибку.

Rollback выполняется по
[`deployment.md`](../../docs/deployment.md) и заранее проверенному release/DB
пути. Исправление «на живой базе» без backup и rehearsal не является планом
отката.

## Порядок текущей работы

Локальные пункты 1–4 завершены; доказательства сведены в
[`pilot-deploy-candidate-2026-08-09.md`](../../../pwa_tests/reports/pilot-deploy-candidate-2026-08-09.md).
Текущий порядок дальнейшей работы:

1. Утвердить FQDN, public media origin, frontend Sentry DSN, production service
   user и пути установки.
2. Подготовить server environment, nginx/systemd и production secret sources.
3. Собрать настоящий production release с утверждёнными публичными параметрами,
   упаковать и проверить его до активации.
4. Выполнить maintenance-window deploy и публичный smoke.
5. Выдать доступ пилотной группе и начать журнал обратной связи.

До начала пилота не возвращаться к полному закрытию фаз 0–11, если найденный
пункт не блокирует deploy, сохранность данных, основной учебный сценарий или
откат.

## Пруфы завершения этапа

В `pwa_tests/reports/` должен лежать privacy-safe отчёт со следующими
артефактами:

- Git revision и release ID;
- результаты обязательных локальных команд и browser matrix;
- migration/restore reports с временем и версиями схемы;
- static release manifest/checksum report;
- redacted nginx/systemd/toolchain/S3/Sentry reports;
- public smoke и список проверенных test accounts без credentials;
- backup ID и проверенный rollback target;
- время начала пилота, ответственный и ссылка на журнал обратной связи;
- каждый внешний пункт, который ещё не запускался, явно помечен `NOT RUN`, а не
  `PASS`.

### 2026-10-01 — Consolidation and two-portal rollout (in progress)

Owner requests consolidation into vmshpwa and sequential rollout to
vmsh.shashkovs.ru and prep.leaders.tech. Current PWA branches (including
codex/rich-markdown) are already ancestors. Owner explicitly excludes historical
experimental branches; consolidation includes the current PWA source work only. Preserve and review all
current source work; exclude local TeX build output and credentials. Run
integration gates, retain verified host-specific DB/source/static rollback
artifacts, rehearse migrations, then deploy and verify each independent portal.
Implementation/runbooks: [deployment.md](../../docs/deployment.md),
[production checklist](../../docs/production-rollout-checklist.md),
[VMSh deploy](../../../docs/deploy/deploy-vmsh-tasks-bot.sh),
[TLF operations](../../../docs/deploy/tlf-app/README.md).

Consolidation gate update: owner excludes legacy experimental branches. VMSh
SQLite online backup and migration 0101–0103 rehearsal passed, including rollback
to 0100 and reapply. Integrity and counts preserved (1 course, 1451 enrollments,
4021 accounts, 34402 results); existing courses stay enabled and account locales
stay explicit. Query performance guard passed (~47 ms). Host evidence remains
in /tmp/vmsh-consolidation-vaq_iyb3; no data rows or credentials copied into Git.
All changed Python files pass Ruff; complete frontend type checks and RU/EN
catalog checks pass. Full backend/frontend suites and rollout gates continue.

Integration gate update: bounded frontend suite ran 967 cases; four stale
expectations/config-import failures were repaired and the affected 10 cases
passed. All changed Storybook scenarios passed (49 Chromium cases). Full PWA
backend ran 2458 cases (2441 passed, 6 skipped, 11 failures); all failed cases
were resolved by focused reruns, including the unchanged performance tripwire.
Golden corpus verification used only the 54 hash-pinned fixtures in an isolated
copy; additional author examples remain untouched. Legacy Telegram suite passed
124 cases, one skipped. TypeScript, ESLint/CSS, formatting and both catalog gates
passed. The browser matrix continues with fresh database phases; navigation-safe
locale cleanup and explicit analytics/group selection repair outdated test
assumptions rather than weakening product checks.

TLF candidate frozen backend and all four production frontend builds passed.
Online backup 20261001T101510.578028Z and source/runtime rollback artifacts are
retained under deploy/releases/tlfprep-20261001-consolidated-a7bccbc1. Isolated
TLF migration/performance rehearsal passed: 75 migrations, integrity ok, both
courses remain disabled for in-person attendance and all three Zoom receipts
preserved. No portal has been switched to the candidate yet.

Pre-cutover integration found a real branding regression: cold starts during
nginx 502/maintenance 503 bypassed the existing recovery boundary and displayed
the catalog failure screen. Rollout remains held while branding GETs join the
shared service transport, with a translated pre-brand waiting screen and
prolonged recovery. No fallback/default identity mounts before validation.
Implementation: packages/branding/src/index.ts and startup.ts; regression:
e2e/smooth-redeploy.spec.ts. Rebuild both host candidates after this fix.

Branding recovery fix passes focused transport/bootstrap/locale tests (20 cases),
three startup Storybook scenarios, complete TypeScript checks and catalog checks.
Chromium/WebKit real maintenance, form, mark and photo-outbox scenarios pass;
the final Firefox gate remains in progress before cutover.
