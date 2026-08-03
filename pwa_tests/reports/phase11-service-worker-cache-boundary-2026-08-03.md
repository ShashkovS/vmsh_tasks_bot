# Phase 11: production service-worker cache boundary

Дата проверки: 3 августа 2026 года.

## Проблема

Production nginx обслуживает `student/sw.js` и `family/sw.js` по стабильным URL.
До этого инкремента test one-origin gateway задавал worker response
`Cache-Control: no-store`, а production template не имел отдельной политики.
Это оставляло обновление PWA зависимым от обычной HTTP cache policy сервера и
браузера.

## Решение

В `http` scope добавлены две точные URI map:

- cache value `no-store` только для двух service-worker URL;
- `Service-Worker-Allowed` только с соответствующим `/student/` или `/family/`
  scope.

Оба `add_header ... always` находятся на том же TLS-server level, что CSP,
HSTS и остальные security headers. Они не перенесены в дочерние static
locations: стандартная nginx-модель наследует родительские `add_header` только
если child level не объявляет собственных. Пустое map value для остальных URI
не добавляет второй Cache-Control к API response.

Новая cache library, revision endpoint и runtime state не добавлялись. Workbox
update flow и stable worker URLs остаются прежними.

## Доказательства

- structural test требует обе точные URI, `no-store`, audience scope и
  server-level placement;
- тот же тест запрещает `add_header` внутри Student/Family static locations;
- существующие template tests продолжают проверять exact host, API/WS/history
  boundaries, CSP, HSTS, login rate limit и proxy-header replacement;
- настоящий `nginx -t` остаётся отдельным production-host gate и не заменяется
  structural parser.

Результаты:

```text
pwa_tests/test_nginx_proxy_config.py: 23 passed
Ruff changed Python: PASS
git diff --check: PASS
current full PWA Python worktree: 1590 passed / 6 intentional skips
```

Последний широкий запуск видел параллельный незакоммиченный `oral_window`
notification slice и поэтому не выдаётся за clean-revision count. Он всё же
подтверждает отсутствие общей регрессии. Точный cache-boundary diff доказан 23
focused тестами; до инкремента в этом файле было 21 тест.

На текущем Mac отсутствует установленный `nginx`, поэтому `nginx -t` не
объявляется пройденным. Обновлённый helper теперь также откажется принимать
установленный site config, если тот синтаксически валиден, но не содержит обе
URI map и server-level headers.

## Источники

- [официальный nginx headers module](https://nginx.org/en/docs/http/ngx_http_headers_module.html):
  стандартное наследование `add_header` и формирование Cache-Control;
- [актуальная спецификация Service Workers](https://www.w3.org/TR/service-workers/):
  update job и `updateViaCache` остаются частью браузерной модели обновления.
