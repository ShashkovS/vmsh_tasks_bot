# Pilot deploy candidate — 2026-08-09

## Scope

Проверяется переход от фазового плана к закрытому пилоту по
[`23-pilot-deployment.md`](../../vmshpwa/dev/development-plan/23-pilot-deployment.md).
Отчёт не утверждает, что приложение уже развёрнуто на production host.

Проверяемая ревизия: `17a95bec356bfd607a1eb91838184f206675f8a2`.
Production provenance зафиксирован в `8bd236a`, последний test-only refresh
setup — в `17a95be`.

## Локальные проверки

- `make pwa-lint pwa-typecheck pwa-build` — `PASS`; Student и Family собрали
  `injectManifest` Service Worker, Staff собрал обычный SPA.
- `make pwa-test` — `PASS`: frontend Vitest 611/611; PWA Python 1651 passed,
  6 skipped, 9 warnings за 189,57 секунды с `pytest-xdist -n8`. Интеграционные
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
- финальный `make pwa-e2e-functional` — `PASS`: 225 passed, 12 ожидаемых
  single-writer skips, 0 flaky в Chromium, WebKit и Firefox за 6,7 минуты.

Последние E2E-исправления затрагивают только тестовый setup и ожидания. После
reload тест дожидается законченного router redirect, а фильтрованная очистка
Playwright cookie явно возвращает намеренно сохранённую HttpOnly refresh cookie
до навигации. Production API и данные не менялись.

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
- synthetic production build `pilot-provenance-smoke` с безопасными example
  origins собран, упакован и повторно проверен — `PASS`: все три приложения
  содержат один release ID, `prototype=false`, `msw=false`, Sentry/media origins
  и совпадающие manifest/checksums. Обычный credential-free `make pwa-build`
  создаёт `profile=verification` и проверенно отклоняется packager до создания
  release. Example build не активирован и не является production bundle.
  Privacy-safe отчёты лежат в `.runtime/phase11-rehearsal/` и не предназначены
  для Git.

## Разрешённые live integration smoke

- test S3 lifecycle — `PASS`: synthetic put, private read, public GET и delete
  под отдельным `integration/<run-id>/`.
- TikZ→SVG и raster→WebP через реальные локальные инструменты и test S3 —
  `PASS`; оба объекта прочитаны и удалены.
- письменное вложение через реальный `WrittenAttachmentService`, WebP и путь
  `sol_imgs/user_{id}/{year}/lesson_{n}/...` — `PASS`; объект удалён. Для
  non-interactive запуска нужен явный
  `VMSH_PDFLATEX_PATH=/Users/sergeyshashkov/bin/pdflatex`, поскольку общий
  tool resolver проверяет весь набор converter tools.
- обычная и rich Telegram-публикации тестовым ботом — `PASS`; synthetic
  сообщения отправлены, изменены и удалены из приватного test-канала. Safe
  reports сохранены только в `.runtime/vmshpwa/telegram-smoke/`.
- локальный NATS prefix fan-out/isolation — `PASS`: 1 test.
- два aiohttp workers с NATS — `PASS`: основной smoke 1 test, bounded load
  smoke 2 tests. Временный локальный `nats-server` после проверки остановлен.

## Внешние проверки

- production FQDN и установленный nginx/systemd profile — `NOT RUN`;
- production S3 capability probe — `NOT RUN`;
- Sentry synthetic frontend/backend error — `NOT RUN`;
- public HTTPS smoke — `NOT RUN`;
- ручной smoke четырёх test accounts — `NOT RUN`;
- production backup ID и фактический rollback target — `NOT RUN`;
- доступ пилотных пользователей — `NOT STARTED`.

## Решение

Статус: `LOCAL DEPLOY CANDIDATE — SERVER INPUTS PENDING`.

Сборка, unit/interaction/Python/legacy gates, migration/restore rehearsal,
production provenance/release packaging и полный browser matrix зелёные.
Следующая работа начинается с утверждённых FQDN, public media origin, frontend
Sentry DSN и production service paths, затем выполняет server install и smoke.
До этого нельзя использовать статус `DEPLOYED`.
