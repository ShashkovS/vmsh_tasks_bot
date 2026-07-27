# Phase 0 runtime and browser isolation evidence

Дата проверки: 27 июля 2026 года.

Статус: runtime/browser-isolation инкремент реализован, а его текущий
non-visual functional gate зелёный в трёх браузерах. Targeted Python, frontend
unit, Storybook, lint/typecheck/build и итоговые browser результаты перечислены
ниже. Visual snapshots не обновлялись и owner approval отсутствует; этот отчёт
не является proof завершения всего этапа 0.

## Boundary under test

E2E больше не моделирует три приложения тремя независимыми Vite origins. После
production build один loopback gateway отдаёт все bundles и проксирует
настоящий aiohttp:

| Boundary                 | Value                                                   |
| ------------------------ | ------------------------------------------------------- |
| Browser origin           | `http://127.0.0.1:5380`                                 |
| Student                  | `/student/*`, `/student/api/v1/*`, `/student/ws`        |
| Family                   | `/family/*`, `/family/api/v1/*`, `/family/ws`           |
| Staff                    | `/staff/*`, `/staff/api/v1/*`, `/staff/ws`              |
| Upstream API             | `http://127.0.0.1:8380`, только loopback                |
| Runtime profile/instance | `pwa-e2e` / `e2e`                                       |
| SQLite                   | `db/vmshpwa_e2e.sqlite3`                                |
| Media                    | `.runtime/vmshpwa/e2e`                                  |
| NATS                     | отключён; reserved prefix `vmshpwa_e2e` не используется |
| Suite lock               | `.runtime/vmshpwa/e2e-suite.lock`                       |

Server runtime payload имеет обязательный `contractVersion: 1` и проходит
audience-specific validation обязательных полей до монтирования router.
Additive v1 fields допускаются для rolling deployment, а неизвестная версия
отклоняется. Browser namespace выводится только из валидированных server-owned
`audience` и `instance`:

| State                | Student E2E               | Family E2E               | Staff E2E               |
| -------------------- | ------------------------- | ------------------------ | ----------------------- |
| Namespace            | `vmsh-179:v1:student:e2e` | `vmsh-179:v1:family:e2e` | `vmsh-179:v1:staff:e2e` |
| Theme key            | `<namespace>:theme`       | `<namespace>:theme`      | `<namespace>:theme`     |
| Dexie database       | namespace verbatim        | namespace verbatim       | отсутствует             |
| Service-worker scope | `/student/`               | `/family/`               | отсутствует             |
| Workbox prefix       | `vmsh-179-student`        | `vmsh-179-family`        | отсутствует             |
| Workbox suffix       | `<full scope>v1`          | `<full scope>v1`         | отсутствует             |

Эта таблица фиксирует ownership/collision convention корректных приложений, но
не security isolation: same-origin JavaScript может перечислять соседние
browser stores. Server authorization/session/CSP proof относится к этапу 1.

На E2E origin итоговые precache names равны
`vmsh-179-student-precache-http://127.0.0.1:5380/student/v1` и
`vmsh-179-family-precache-http://127.0.0.1:5380/family/v1`. Разные prefix — не
косметика: официальный contract генерирует cache name как
`<prefix>-<cache-id>-<suffix>` и прямо называет предотвращение конфликтов
нескольких приложений одним из применений
[`setCacheNameDetails`](https://developer.chrome.com/docs/workbox/modules/workbox-core/#setcachenamedetails).
Сохранённый scope позволяет
[`cleanupOutdatedCaches()`](https://developer.chrome.com/docs/workbox/modules/workbox-precaching/#cleanupoutdatedcaches)
распознать собственный старый precache; executable E2E создаёт `v0` и проверяет
его удаление после активации нового worker.

Финальный production build для runtime gate создал Student precache из 91
entry / 2238.52 KiB и Family precache из 90 entry / 2149.05 KiB. Это укладывается
в принятый общий offline budget 10–15 MiB. Build продолжает показывать upstream
deprecation warning vite-plugin-pwa/Rollup
`inlineDynamicImports -> codeSplitting: false`; это не скрыто как PASS и требует
проверки при следующем обновлении toolchain.

## Implementation evidence

Backend и wire contract:

- [`helpers/pwa/api_contracts.py`](../../helpers/pwa/api_contracts.py) — runtime
  `contractVersion`, instance grammar, audience paths и единый error envelope;
- [`helpers/pwa/app_keys.py`](../../helpers/pwa/app_keys.py) — canonical aiohttp
  `AppKey`, одинаковый при `import main` и `python main.py` (`__main__`);
- [`apps/pwa_app.py`](../../apps/pwa_app.py) — runtime endpoint использует
  builders, отклоняет unsafe instance при composition и применяет stable
  `PwaApiError`, request/security/no-store headers ко всем PWA API responses,
  включая exact `/{audience}/api` и пересобранные aiohttp exceptions;
  per-audience locks сериализуют cursor allocation, а invalid WebSocket JSON
  получает versioned recoverable error event;
- [`packages/contracts/src/index.ts`](../../vmshpwa/packages/contracts/src/index.ts)
  и [`packages/contracts/fixtures`](../../vmshpwa/packages/contracts/fixtures) —
  audience-specific Zod boundary, explicit wire version, additive-field rolling
  compatibility, versioned runtime/HTTP/realtime-error fixtures и namespace
  builder;
- [`test_api_contracts.py`](../test_api_contracts.py) — Python builders против
  тех же JSON fixtures, exact API/no-store/header preservation, unsafe instance
  и direct-script AppKey regression;
- [`test_pwa_app.py`](../test_pwa_app.py) и
  [`test_nats_broker.py`](../test_nats_broker.py) — concurrent cursor ordering,
  audience fan-out, invalid JSON и startup/shutdown transport boundaries.

Frontend startup и storage:

- [`runtime-bootstrap.tsx`](../../vmshpwa/packages/app-shell/src/runtime-bootstrap.tsx)
  и [`runtime-bootstrap.test.tsx`](../../vmshpwa/packages/app-shell/src/runtime-bootstrap.test.tsx) —
  loading/error/retry/correlation-ID boundary и десятисекундный request timeout
  до protected shell;
- [`providers.tsx`](../../vmshpwa/packages/app-shell/src/providers.tsx) — theme
  key под полным namespace и in-memory fallback при отказе `localStorage`;
- [`database.ts`](../../vmshpwa/packages/offline/src/database.ts),
  [`provider.tsx`](../../vmshpwa/packages/offline/src/provider.tsx) и
  [`database.test.tsx`](../../vmshpwa/packages/offline/src/database.test.tsx) —
  реальные Dexie databases, record isolation, open-before-consumers,
  blocked/timeout/rejected-open/unexpected-close recovery и teardown;
- [`student/src/main.tsx`](../../vmshpwa/apps/student/src/main.tsx),
  [`family/src/main.tsx`](../../vmshpwa/apps/family/src/main.tsx) и
  [`staff/src/main.tsx`](../../vmshpwa/apps/staff/src/main.tsx) — audience
  composition; PWA update controller вне runtime/Dexie gates; Staff без Dexie;
- [`student/src/sw.ts`](../../vmshpwa/apps/student/src/sw.ts) и
  [`family/src/sw.ts`](../../vmshpwa/apps/family/src/sw.ts) — disjoint Workbox
  prefixes, scope-preserving cache versions, reserved-navigation denylist и
  recent-media caches.

Startup state stories находятся в
[`runtime-bootstrap.stories.tsx`](../../vmshpwa/packages/app-shell/src/runtime-bootstrap.stories.tsx):

- `product-app-startup--runtime-loading`;
- `product-app-startup--runtime-rejected`;
- `product-app-startup--offline-storage-unavailable`.

Production-like E2E:

- [`scripts/e2e_runner.py`](../../vmshpwa/scripts/e2e_runner.py) — один
  fail-fast cross-process lock на build + Playwright и явные
  all/nonvisual/runtime-isolation/visual modes; runner удаляет все inherited
  `VITE_*` и подставляет только reviewed безопасные browser-build значения,
  включая пустые Sentry/media и выключенные MSW/prototype;
- [`scripts/e2e_gateway.py`](../../vmshpwa/scripts/e2e_gateway.py) — один
  loopback origin, exact API/WS routing, safe history fallback, authoritative
  no-store proxy, cookie-less upstream client, dist-root/path/symlink protection
  и local-only worker-generation/runtime-mode probes; отменённый downstream
  WebSocket upgrade закрывает уже открытый upstream;
- [`playwright.config.ts`](../../vmshpwa/playwright.config.ts) — production
  bundles + real aiohttp + gateway;
- [`fixtures.ts`](../../vmshpwa/e2e/fixtures.ts) — auto-fixture, который
  пропускает browser HTTP/WebSocket только к literal
  `http://127.0.0.1:5380` / `ws://127.0.0.1:5380`, блокирует и делает
  test-failure любой иной origin;
- [`runtime-isolation.spec.ts`](../../vmshpwa/e2e/runtime-isolation.spec.ts) —
  runtime/health, history and assets, active-worker API/WS/static/PDF page
  navigations, request-based manifests/icons, SW
  scopes/caches/update/cleanup/recovery, WebSocket heartbeat/reconnect,
  literal-loopback network guard, localStorage и IndexedDB;
- [`shells.spec.ts`](../../vmshpwa/e2e/shells.spec.ts) — same-origin shell/deep
  links/theme и visual pages с `document.fonts.ready`;
- [`test_e2e_gateway.py`](../test_e2e_gateway.py) — gateway unit/integration
  boundary;
- [`test_e2e_runner.py`](../test_e2e_runner.py) — lock ownership, command modes,
  fail-fast command sequence и exact sanitized subprocess environment;
- [`test_production_build_guard.py`](../test_production_build_guard.py) — все
  три apps × process-environment `VITE_ENABLE_MSW`/`VITE_PROTOTYPE`, отказ до
  изменения output;
- [`vite-production-guard.ts`](../../vmshpwa/vite-production-guard.ts) и
  [`vite-production-guard.test.ts`](../../vmshpwa/packages/test-utils/src/vite-production-guard.test.ts) —
  Vite `loadEnv` и controlled `.env.production` boundary.

Gateway capabilities делают реальный built Workbox worker byte-different и
runtime несовместимым, затем проверяют startup error → доступный update prompt →
waiting worker → `SKIP_WAITING` → новый controller → cleanup `v0`. Они не
являются production routes и не заменяют product authentication. Control token
эфемерен, loopback-only и может попасть в retained Playwright trace; он не даёт
product/API authority.

Playwright документирует свои service-worker events/network interception как
Chromium-only и рекомендует ждать activation/controller state. Наш proof
использует browser-native `navigator.serviceWorker`/Cache Storage API и на этом
tree проходит во всех трёх engines. Capability-based skip разрешён только при
реальном отсутствии API и должен оставаться видимым
([Playwright Service Workers](https://playwright.dev/docs/service-workers)).

## Verified results on this worktree

Focused Python boundary command из корня репозитория:

```text
UV_CACHE_DIR=.runtime/uv-cache \
VMSH_RUNTIME_PROFILE=pwa-e2e \
VMSH_INSTANCE=e2e \
VMSH_DB_FILENAME=db/vmshpwa_e2e.sqlite3 \
VMSH_MEDIA_ROOT=.runtime/vmshpwa/e2e \
VMSH_NATS_SERVER= \
VMSH_NATS_TOPIC_PREFIX=vmshpwa_e2e \
VMSH_PWA_PROTOTYPE=true \
uv run pytest -q -n0 \
  pwa_tests/test_api_contracts.py \
  pwa_tests/test_pwa_app.py \
  pwa_tests/test_nats_broker.py \
  pwa_tests/test_e2e_gateway.py \
  pwa_tests/test_e2e_runner.py \
  pwa_tests/test_production_build_guard.py

97 passed (после добавления structural Vite-input gate)
```

Финальные workspace gates:

- `make pwa-test` — Vitest 7 files / 68 tests PASS; Python `pwa_tests` 461
  PASS, 1 intentional skip, 1 pre-existing SymPy deprecation warning;
- `make pwa-lint` — ESLint + Stylelint PASS;
- `make pwa-typecheck` — все packages/apps/tools PASS;
- `make pwa-storybook-test` — Chromium browser mode 32 files / 140 tests PASS;
  non-blocking Node `module.register` deprecation и существующее предупреждение
  о пустом `dev/design-system/**/*.stories` glob сохранены в выводе;
- `make pwa-build` — Student/Family injectManifest и Staff SPA PASS; тот же
  build является обязательным первым шагом E2E runner, precache counts/sizes
  приведены выше.
- targeted Prettier check всех изменённых и новых frontend/docs файлов,
  targeted Ruff и `git diff --check` — PASS. Общий repository-wide Prettier
  check отдельно показывает три ранее существовавших несвязанных файла и не
  переписывался этим инкрементом.

Production-like browser результаты:

- follow-up 27 июля 2026: после обнаруженного regression test mismatch кнопка
  обновления напрямую отправляет `SKIP_WAITING` browser-owned waiting worker,
  а navigation assertion сохраняет фактический текущий audience-local URL
  вместо предположения, что auth boundary оставил корень. Focused production
  bundle proof — Student + Family, Chromium/WebKit/Firefox, **6/6 PASS**;
  полный runtime suite на итоговом tree остаётся отдельным повторным gate;

- `make pwa-e2e-functional` — сначала production build, затем 72/72 PASS
  суммарно в Chromium, WebKit и Firefox;
- после расширения static-suffix denylist, очистки browser-build environment и
  установки external-network guard финальный `make pwa-e2e-runtime` — 60/60
  PASS в Chromium, WebKit и Firefox; изменения после полного functional run
  затрагивали только этот повторно проверенный runtime spec и общий fixture;
- в этот current-tree run входят все runtime-isolation cases: active-controller
  navigation denylist, incompatible-runtime update recovery, exact scope/script,
  response от текущего byte-generation controller, cleanup obsolete cache и
  реальный заблокированный `.invalid` HTTP/WebSocket probe;
- focused `pwa_tests/test_e2e_runner.py` — 8 PASS, включая hostile inherited
  `VITE_*`, exact environment каждого build/Playwright subprocess и
  обязательное использование auto-fixture всеми specs;
- `make pwa-visual` без обновления snapshots — 3 PASS для Staff dashboard и 3
  ожидаемых stale Student current-week failures в Chromium/WebKit/Firefox:
  baseline 390×1188 против текущего 390×1615. Артефакты сохранены в
  `vmshpwa/test-results/...`; это открытый owner-review gate, а не product
  failure. `pwa-visual-update` не запускался.

Итоговый независимый read-only review текущего dirty increment не обнаружил
P0/P1/P2-дефектов. В review отдельно проверялись browser-build environment,
external-network guard, отсутствие credential artifacts, gateway/header
streaming, HTTP/WebSocket error boundary и audience-specific SW cleanup.

## Commands required before acceptance

Следующие команды должны быть выполнены на итоговом tree; результат добавляется
сюда, а не подразумевается:

```text
make pwa-format
make pwa-lint
make pwa-typecheck
make pwa-test
make pwa-storybook-test
make pwa-build
make pwa-e2e
make pwa-visual
```

`make pwa-visual-update` до просмотра владельцем не запускается. Снимки этого
инкремента не обновлялись. Текущий `make pwa-e2e-functional` зелёный; общий
`make pwa-e2e` останется красным на тех же трёх visual diffs до принятия и
отдельного обновления baselines.

## Remaining gates and limitations

- Browser namespaces/cache prefixes предотвращают случайные коллизии, но не
  изолируют hostile/compromised same-origin JavaScript. Это не должно
  описываться как security boundary; этап 1 доказывает server authorization,
  session cookies и CSP.
- E2E gateway этапа 0 не моделирует trusted reverse proxy: upstream `Host`
  указывает на API 8380, browser `Origin` — на gateway 5380. До auth/CSRF E2E
  этапа 1 нужны явные public-origin/trusted-proxy semantics и negative tests для
  spoofed `Forwarded`/`X-Forwarded-*`.
- При будущих изменениях capability skips допустимы только для реально
  отсутствующего Service Worker API и должны остаться видимыми в результате.
- Runtime bootstrap требует network response на cold start. Cached,
  versioned runtime bootstrap с expiry/revocation semantics относится к этапу
  3; текущий precache/Dexie proof не объявляет cold offline reading готовым.
- Ошибка открытия IndexedDB в Student/Family сейчас блокирует protected shell,
  имеет bounded/retryable lifecycle и не блокирует регистрацию PWA update, но
  не включает online-only shell. Degraded online-only policy, если понадобится,
  требует отдельного продуктового решения и тестов перед изменением.
- Phase 0 проверяет audience/runtime browser boundary, но не доказывает
  account-level session isolation: реальные login/session endpoints относятся
  к этапу 1.
- Visual snapshots не обновлялись. Три Student current-week snapshots
  расходятся по ожидаемой высоте многокурсовой страницы и требуют ручного
  owner review; новые startup states, Family/dark visual baseline и точный
  environment manifest ещё не приняты.
- Test-only gateway доказывает ожидаемую one-host маршрутизацию, но не заменяет
  deploy smoke реальной nginx/systemd конфигурации этапа 11.
