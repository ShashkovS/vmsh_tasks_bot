# Phase 11: read-only production HTTP smoke — 3 августа 2026

## Что закрывает этот инкремент

Добавлена одна операторская команда для проверки уже переключённого публичного
релиза:

```text
make pwa-production-http-smoke \
  PWA_PRODUCTION_ORIGIN=https://<approved-fqdn> \
  PWA_PRODUCTION_INSTANCE=<expected-runtime-instance>
```

Реализация: [`production_http_smoke.py`](../../vmshpwa/scripts/production_http_smoke.py).
Команда выполняет только GET, не принимает cookies/логины и не читает
credential files. Public target обязан быть точным HTTPS origin с lowercase
ASCII FQDN без credentials, port, path, query или fragment; redirect не
следуется.

Проверяются:

- health/runtime каждого audience, request/correlation ID и `no-store`;
- один ожидаемый instance, contract/base paths, `prototype=false`,
  `google=false`, `nats=true`;
- production CSP, HSTS, nosniff, frame, referrer и permissions headers;
- JSON 404 для отсутствующего API отдельно от HTML history fallback;
- `no-cache` для стабильного HTML shell после atomic release switch;
- Student/Family manifest, audience-owned icons, stable `sw.js`, exact
  `Service-Worker-Allowed` и `Cache-Control: no-store`;
- отсутствие PWA manifest у Staff;
- timeout 10 секунд и предел ответа 4 MiB.

Предел тела проверяется потоково: один короткий `read(n)` не обязан вернуть все
доступные байты и потому не является корректным ограничителем. Никаких retry в
smoke нет — post-deploy сигнал должен показывать первый реальный сбой, а не
маскировать нестабильный релиз.

## Проверки

- focused aiohttp/unit contract: **16 PASS**;
- focused smoke + nginx structural contract: **39 PASS**;
- Ruff format/check: **PASS**;
- clean-scope PWA regression в 8 workers: **1606 PASS / 6 intentional skips**,
  финальный прогон после упрощения команды — 74,05 с; legacy: **124 PASS / 1
  intentional skip**;
- полный dirty-worktree `make python-test`, включавший ещё 8 соседних untracked
  systemd tests: **124 + 1614 PASS / 7 skips**, 79,48 с wall time.

Тесты поднимают только локальный aiohttp и не обращаются к production,
Telegram, Google или S3. Они доказывают happy path, строгий target parsing,
отказ при prototype runtime, отсутствие redirect-follow и bounded body read.

## Открытые внешние gates

- владелец ещё не выбрал production FQDN и runtime instance;
- команда ещё не запускалась после реального release switch;
- установленный `nginx -t`, настоящий login `429`, authenticated WebSocket и
  physical-device PWA install остаются отдельными Phase 11 доказательствами.

Primary sources, сверенные для решения 3 августа 2026:

- [aiohttp client session, redirects and timeouts](https://docs.aiohttp.org/en/stable/client_reference.html);
- [W3C Service Worker update and scope model](https://www.w3.org/TR/service-workers/);
- [RFC 9111 `no-store`](https://www.rfc-editor.org/rfc/rfc9111.html#name-no-store).
