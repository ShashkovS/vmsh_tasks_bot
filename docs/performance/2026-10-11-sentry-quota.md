# Frontend Sentry при квоте 5 000 — 11 октября 2026

Владелец подтвердил месячный лимит ВМШ 5 000 ошибок и уточнил, что у двух
production порталов отдельные Sentry аккаунты. Бюджеты считаются независимо;
квота второго аккаунта здесь не проверялась. Политика
[10 октября](2026-10-10-sentry-noise.md) ограничивала отдельную вкладку,
но новые вкладки/пользователи могли по-прежнему расходовать всю квоту.
В настройках `vmshpwa` проверено: custom DSN rate limits и error-message
filters требуют Business; поля бесплатного плана disabled. Настройки не менялись.
Свежая проверка MCP: последний release даёт 2 895 handled query TypeError
за 24 часа, synthetic capture stack исторических событий не содержит причины.

## Уточнённая политика, реализация проверена

- Typed read network/deadline failures и recovery episodes — только breadcrumbs.
- Handled query TypeError без безопасной исходной app location — breadcrumbs,
  без отдельного события. Тип ошибки не объявляется сетевым.
- Остальные diagnostics и важные ошибки проходят общий admission в существующем
  aiohttp backend перед отправкой в Sentry. Нет разрешения — нет отправки.
- На одну SQLite/портал: diagnostics до 3 за скользящие 24 часа и 100 за
  скользящие 32 дня; ошибки отправки/хранения/автоматические crashes до 30
  и 900 соответственно. Повтор одной сигнатуры допускается раз за 24 часа.
  Верхняя граница нового фронтенда ВМШ — 1 000 событий в любом периоде
  до 32 дней. Остальные 4 000 предназначены другим источникам его аккаунта;
  их собственный объём этим изменением не ограничивается. Второй портал
  имеет собственный ledger и не расходует бюджет ВМШ.

Admission хранит только время, lane и bounded hash безопасной сигнатуры,
без account/session IDs, сообщений, URL, ответов и event payload. SQLite
`BEGIN IMMEDIATE` делает проверку и reservation атомарными между workers;
reload, release и process restart не обнуляют бюджет. Взятая reservation
не возвращается при недоставке/timeout — предел остаётся консервативным.
Это ограничение штатных SDK новых выпусков, не защита от прямой отправки
в публичный DSN вне приложения. Старые вкладки прежних выпусков ещё обходят
admission до обновления. Восстановление старой DB backup может откатить ledger.

## Implementation и проверка

- [SDK policy](../../vmshpwa/packages/app-shell/src/sentry-noise.ts),
  [safe diagnostics и init](../../vmshpwa/packages/app-shell/src/observability.ts),
  [client admission](../../vmshpwa/packages/app-shell/src/sentry-admission.ts).
- [Zod protocol](../../vmshpwa/packages/contracts/src/sentry-admission.ts)
  проверяет boolean admission и исключает дополнительные поля request.
- [Публичный telemetry endpoint](../../apps/pwa_api/sentry_admission_routes.py)
  принимает только lane/hash, проверяет существующую same-origin boundary;
  доступ к бизнес-данным/сессиям не выдаёт. Он нужен и для pre-login crashes.
- [Budget service](../../helpers/pwa/sentry_budget.py),
  [SQLite ledger](../../db_methods/pwa/sentry_budget.py),
  [migration 0117](../../migrations/0117.frontend_sentry_budget.py),
  [bounded Prometheus counter](../../helpers/prometheus_metrics.py).

Проверены quotas/repeats/rolling window/concurrency/reopen,
HTTP origin/public boundary/fail-closed, SDK failures и meaningful TypeError.
Единый fast gate: format/types/lint/i18n PASS; 1 088 frontend,
364 Storybook, четыре app builds и 12 Chromium submissions/redeploy/offline-current
PASS. Полный Python: 2 877 PASS / 8 SKIP / 19 FAIL в первом запуске;
13 связанных failures устранены (dict row factory и migration head assertions),
все 43 targeted quota/HTTP/runtime-schema/inventory PASS. Остались 6 прежних
failures отсутствующих private `_external_pipelines` inputs; общий gate не зелёный.
[Квитанция](../../pwa_tests/reports/sentry-quota-20261011/validation.json)
сохраняет исходные FAIL и focused repairs; полные suites повторно не запускались.
Releases действующих порталов пока не менялись. Backend с 0117/endpoint выпускается до нового
frontend: старый backend отклонит admission, новый SDK не отправит событие.

## Альтернатива размещению

Владелец выбрал размещение на своём сервере. Выбран
[GlitchTip](https://glitchtip.com/documentation/install/), бесплатный self-hosting,
Sentry SDK compatibility и [MCP](https://glitchtip.com/documentation/mcp/).
Второй вариант — [Bugsink](https://www.bugsink.com/docs/), ориентированный на
ошибки и совместимый с Sentry SDK; [self-hosting бесплатен для non-competing
uses](https://www.bugsink.com/blog/new-license-new-pricing/).
GlitchTip 6.2.6 развёрнут на prep.leaders.tech, https://glitch.leaders.tech;
отдельный [deployment runbook](../deploy/glitchtip/README.md) и safe proof
подтверждают HTTPS/IPv4/IPv6, real login, event ingestion/stacks, restart и restore.
VMSH/TLF имеют отдельные организации и проекты. DSN порталов пока не переключены.
Переход приложений потребует
нового DSN, source-map upload и CSP origin; masking/breadcrumbs/diagnostic
location остаются полезными. Quota-specific budget 1 000 потребуется отдельно
пересмотреть под retention/ресурсы собственного сервера.


## Выпуск и перенос приёма ошибок

11 октября correction выпущен (`e0324272`), затем оба портала переключены на
[GlitchTip](../deploy/glitchtip/migration-20261011.md) (`99552697`): отдельные
frontend/backend проекты, private maps с original TS locations, native Python
SDK, 25 HTTP checks на каждом и Telegram delivery PASS. Исторический hosted
Sentry сохраняется; старым вкладкам нужно обновиться. Frontend budgets и
фильтрация сохраняются для ограничения шума и собственного хранения.
