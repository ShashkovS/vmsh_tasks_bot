# Phase 11: production-build browser checkpoint

Дата: 2 августа 2026 года.

## Проверяемая граница

`make pwa-e2e-functional` сначала собрал production bundles Student, Family и
Staff, включая `injectManifest` workers Student/Family, затем запустил:

- один настоящий aiohttp на `127.0.0.1:8380`;
- один test-only one-origin gateway на `127.0.0.1:5380`;
- заново seeded изолированную `db/vmshpwa_e2e.sqlite3`;
- Chromium, WebKit и Firefox одновременно.

MSW, prototype mode, Sentry, внешний media origin, Telegram и Google были
отключены. Browser network fixture разрешал только единый gateway origin.
Visual stories и snapshots этим checkpoint не изменялись: команда исключает
`@visual`, пока владелец не примет новые изображения.

## Исправленная изоляция

Функциональные ошибки предыдущего checkpoint оказались зависимостями тестов от
общих изменяемых fixtures, а не product failures:

- Family enrollment mutation перенесена на отдельного Family-only ребёнка;
- auth и classroom mutations стали повторяемыми относительно реально
  прочитанного начального состояния;
- news Student/Family получили отдельных synthetic principals для каждого
  browser project;
- news read подтверждается authoritative API polling после foreground и
  трёхсекундного visibility window, а не гонкой с `waitForResponse`;
- runtime socket assertion требует `connected`, но не объявляет корректный
  параллельный owner-scoped `invalidate` ошибкой.

Playwright запускает разные spec-файлы параллельно даже при
`fullyParallel: false` ([официальная модель](https://playwright.dev/docs/test-parallel)).
Поэтому конфигурация использует три общих workers и ровно один worker на каждый
browser project. Project-level `workers` и `failOnFlakyTests` поддерживаются с
Playwright 1.52
([release notes](https://playwright.dev/docs/release-notes#version-152)). Retry
сохраняет диагностику, но любой flaky делает gate красным.

## Фактический результат

Playwright HTML report и `.last-run.json` зафиксировали:

- **228 total**;
- **216 expected / passed**;
- **12 intentional browser-matrix skips**;
- **0 unexpected**;
- **0 flaky**;
- **3 actual workers**;
- browser duration **208.01 s**.

Production build завершился до browser run. Student precache содержит 107
entries, Family — 95; оба service worker собраны в `injectManifest` mode.
После suite aiohttp и gateway завершились, порты 8380/5380 освободились.

Дополнительные гейты того же worktree:

- ESLint + Stylelint: **PASS**;
- strict TypeScript: **PASS**;
- Vitest unit: **110 files / 586 PASS**;
- PWA Python: **1547 PASS / 5 intentional skips** в восьми workers;
- legacy Python: **120 PASS / 2 intentional skips** в восьми workers;
- review ImageMagick integration: **3/3 PASS**.

Storybook browser gate трижды не дошёл до collection: macOS отказал Chromium в
Mach rendezvous до создания browser context. Это внешний launch failure с
нулём выполненных stories, не PASS и не product regression; последний
подтверждённый Storybook checkpoint до E2E-only изменений — **236 PASS**.

## Оставшиеся границы

- Visual snapshots по-прежнему требуют ручного просмотра владельцем и не
  обновлялись автоматически.
- Этот checkpoint не заменяет deploy smoke, nginx check, physical-device smoke,
  live S3/Telegram probes, backup/restore rehearsal и production rollback.
- Transient HTML report, traces и browser profiles не коммитятся; этот документ
  хранит воспроизводимую сводку, а assertions остаются в `vmshpwa/e2e`.
