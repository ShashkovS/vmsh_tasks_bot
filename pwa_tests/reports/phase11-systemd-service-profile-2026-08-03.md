# Phase 11: отдельный production systemd profile — 3 августа 2026

## Результат

Добавлены простые deploy-артефакты отдельного PWA API service:

- [`vmshpwa.service.template`](../../vmshpwa/deploy/systemd/vmshpwa.service.template);
- [`vmshpwa.env.example`](../../vmshpwa/deploy/systemd/vmshpwa.env.example);
- [`systemd_config_check.py`](../../vmshpwa/scripts/systemd_config_check.py);
- команда `make pwa-systemd-check`.

Unit запускает только `main:app` с `pwa-production`, prototype=false, двумя
Gunicorn workers и Unix socket. Telegram polling/webhook и Google loader не
подключаются этим service; существующий Telegram service остаётся отдельным.
Rolling reload отсутствует, поскольку migrations выполняются в maintenance
window после остановки всех SQLite writers.

Environment file обязан иметь exact mode `0600`. Checker не печатает значения
auth peppers, VAPID keys, Sentry DSN или operator email. Он блокирует
пропущенные поля, profile/adapter overrides, не-HTTPS origins, неверную proxy
границу, unresolved markers, один worker, preload и ослабленный unit.

## Проверки

- Ruff format/check: **PASS**;
- focused structural suite: **10 PASS**;
- совместный focused smoke/nginx/systemd suite: **47 PASS** до финального
  exact-mode test; после него systemd-only suite повторён: **10 PASS**.
- полный PWA Python gate на восьми изолированных workers после финального
  изменения: **1616 PASS / 6 intentional skips**, 71,70 с. Первый sandboxed
  запуск не мог bind local aiohttp sockets; тот же gate с разрешёнными только
  local test sockets прошёл полностью.

Тесты не стартуют service, Telegram, Google, NATS или production S3. На Linux
production host команда дополнительно требует `systemd-analyze verify`.

## Открытые production gates

- заменить все markers реальными owner-approved paths/host/secrets;
- выполнить `systemd-analyze verify`, `daemon-reload` и настоящий restart;
- подтвердить ownership/mode socket directory и доступ nginx;
- выполнить public HTTP smoke и rollback уже после переключения release.

Primary source для environment precedence:
[systemd.exec `EnvironmentFile=`](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#EnvironmentFile=).
