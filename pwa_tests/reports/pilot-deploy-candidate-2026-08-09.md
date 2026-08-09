# Pilot deploy candidate — 2026-08-09

## Scope

Проверяется переход от фазового плана к закрытому пилоту по
[`23-pilot-deployment.md`](../../vmshpwa/dev/development-plan/23-pilot-deployment.md).
Отчёт не утверждает, что приложение уже развёрнуто на production host.

Проверяемая базовая ревизия: `cebebf2581dad3a9fb23bcedb0d421dd411e014d`.
Стабилизация browser gates зафиксирована в `962947b`; сам отчёт добавляется
следующим документационным коммитом.

## Локальные проверки

- `make pwa-lint pwa-typecheck pwa-build` — `PASS`; Student и Family собрали
  `injectManifest` Service Worker, Staff собрал обычный SPA.
- `make pwa-test` — `PASS`: frontend Vitest 606/606; PWA Python 1646 passed,
  6 skipped, 9 warnings за 96,90 секунды с `pytest-xdist -n8`. Интеграционные
  фикстуры используют отдельную временную SQLite для каждого worker.
- `make pwa-storybook-test` — `PASS`: 54 файлов, 262 tests.
- `make python-test-legacy telegram-history-test` — `PASS`: 124 legacy tests,
  1 skip; 45 исторических Telegram tests.
- `make pwa-e2e-auth` — `PASS`: 90 passed и 12 ожидаемых single-writer skips в
  Chromium, WebKit и Firefox.
- `make pwa-e2e-news` — `PASS`: 18/18 в трёх браузерах.
- `make pwa-e2e-realtime` — `PASS`: 12/12 в трёх браузерах.
- финальный `make pwa-e2e-runtime` — `PASS`: 69/69 в трёх браузерах после
  объединения Student/Family scope-проверок в один последовательный browser
  context; assertions на manifest, scope, control, update, Cache Storage,
  IndexedDB, WebSocket и audience isolation сохранены.
- полные production-build прогоны подтвердили 227 product scenarios и 12
  ожидаемых single-writer skips. До последней правки они завершались с одним
  WebKit flaky при создании второго холодного Service Worker context. После
  правки повтор полного набора был остановлен: весь host замедлился в 5–10 раз
  после серии браузерных прогонов и обычные auth tests стали упираться в timeout.
  Это не записано как `PASS`; требуется один чистый контрольный запуск после
  освобождения ресурсов.

E2E-исправления затрагивают только тестовый setup и ожидания. Они перестали
предполагать пустую новостную ленту, отсутствие чужих валидных invalidation,
мгновенное удаление истёкшей cookie из Firefox cookie jar и отдельный холодный
WebKit context для каждого PWA. Production API и данные не менялись.

## Rehearsal и release

- `make pwa-phase11-course-rehearsal` на новой копии `db/vmsh.db` — `PASS`:
  `integrityCheck=ok`, исходная БД не изменена, 4 legacy-группы привязаны к
  курсу, получены 1617 course enrollments и 110 group lessons.
- Исторический discussion backfill честно имеет
  `discussionMigrationReady=false`: 40 531 legacy Telegram-only media reference
  нельзя восстановить из имеющихся message logs, а problem revisions требуют
  проверки владельцем. Для пилота нового учебного года это принятое ограничение:
  новые ветки и фотографии работают, старые Telegram-only фотографии в PWA не
  обещаются и физически не переносятся.
- `make pwa-phase11-restore-rehearsal` — `PASS`: 72 migrations,
  `integrityCheck=ok`, `schemaCurrent=true`, legacy row parity сохранён,
  исходная БД не изменена, общее время 0,633 секунды.
- static release `pilot-20260809-candidate` упакован и проверен — `PASS`:
  Student 156 файлов, Family 145, Staff 169; manifest/checksums совпали.
  Privacy-safe отчёты лежат в `.runtime/phase11-rehearsal/` и не предназначены
  для Git.

## Внешние проверки

- production FQDN и установленный nginx/systemd profile — `NOT RUN`;
- production S3 capability probe — `NOT RUN`;
- Sentry synthetic frontend/backend error — `NOT RUN`;
- public HTTPS smoke — `NOT RUN`;
- ручной smoke четырёх test accounts — `NOT RUN`;
- production backup ID и фактический rollback target — `NOT RUN`;
- доступ пилотных пользователей — `NOT STARTED`.

## Решение

Статус: `LOCAL CANDIDATE — CONTROL RUN PENDING`.

Сборка, unit/interaction/Python/legacy gates, migration/restore rehearsal,
release packaging и все отдельные browser suites зелёные. Перед установкой на
сервер остаётся один контрольный полный non-visual run на освободившемся host.
До server smoke нельзя использовать статус `DEPLOYED`.
