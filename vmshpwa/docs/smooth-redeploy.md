# Спокойный редеплой — 15 сентября 2026

Принят пользователем: текущая страница и черновики сохраняются, отправка
приостанавливается. Через 60 секунд спокойное пояснение, восстановление
продолжается. Плановое обновление не называется проблемой интернета.

## Реализация

- [`service-availability.ts`](../packages/contracts/src/service-availability.ts):
  только same-origin audience API; один цикл на вкладку, 1/2/5 секунд + jitter.
  Сначала HTTP status, затем JSON; HTML 502/503/504 не считается неверным runtime.
  Старый сервер без `/service-status` поддерживается проверкой runtime.
- [`runtime-bootstrap.tsx`](../packages/app-shell/src/runtime-bootstrap.tsx),
  auth и общие API-клиенты используют транспорт. Подтверждённая сессия и экран
  остаются смонтированы. Настоящие 401/403, срок сессии и audience validation
  сохраняются; настоящий offline использует прежний account-scoped cache.
- [`service-availability.tsx`](../packages/app-shell/src/service-availability.tsx)
  показывает компактный status без alert и обновляет активные queries после
  восстановления. [`realtime.tsx`](../packages/app-shell/src/realtime.tsx)
  возобновляет соединение, не снимая auth-policy block. Перезагрузки/SW activation нет.
- Новые API-отправки ждут известную паузу. Уже отправленный запрос без ответа
  автоматически повторяется только для receipt-backed test-attempts/live-marking.
  Другие неоднозначные записи получают `request_not_confirmed`: проверить результат
  перед повтором. Существующий письменный outbox повторяет собственную операцию
  с прежними ключами. Явный nginx `service_updating` гарантирует, что запрос
  не передавался backend, поэтому повтор безопасен и для обычной записи.
- S3/внешние URL и Sentry transport не перехватываются. Ожидаемые request errors
  не создают по событию; затяжной эпизод регистрируется один раз на 60-й секунде,
  краткий неожиданный — при восстановлении. В событии только тип и длительность.

## Серверный контракт

[`nginx/vmshpwa.conf.template`](../deploy/nginx/vmshpwa.conf.template) проверяет
`/web/vmsh_tasks_bot/vmshpwa/runtime/service-updating`. Содержимое файла не важно.
`GET /service-status` отвечает `{"state":"ready"}` или `{"state":"updating"}`
независимо от Python. Новые API/WS при флаге получают 503 JSON
`error.code=service_updating`, `X-VMSH-Service-State: updating`, `Retry-After: 2`,
`Cache-Control: no-store`. Статика доступна. Уже принятые запросы обслуживает
существующий graceful shutdown; unsafe proxy retries не добавлены.

[`deploy-vmsh-tasks-bot.sh`](../../docs/deploy/deploy-vmsh-tasks-bot.sh)
собирает и упаковывает frontend до паузы. Перед остановкой включает флаг;
при миграции останавливает analytics timer/service, PWA и Telegram writers.
До включения флага миграции автоматически репетируются на согласованной копии
production SQLite и проходят query-plan/latency guard. Guard повторяется на
production-БД после migration и до запуска сервисов.
Прежнее active/inactive состояние таймера сохраняется отдельно и переживает
сбой deploy. Снятие флага — только после миграций, запуска, runtime checks всех audiences через доверенный Unix-сокет и активации frontend. ERR trap оставляет флаг,
состояние таймера и прежнее уведомление администратору.

[`static_release.py`](../scripts/static_release.py) сохраняет public `assets/`
текущего и нового релизов в append-only `immutable-assets/{audience}/assets`.
Nginx берёт их из `@@STATIC_ROOT@@/../immutable-assets`; STATIC_ROOT обязательно
`/web/vmsh_tasks_bot/vmshpwa/current`. Старые lazy chunks остаются доступны
открытым вкладкам. Коллизия имени с другими bytes блокирует упаковку, HTML/SW
не архивируются в этом каталоге. Автоматического GC пока нет: следить за диском,
не чистить каталог вместе со старыми release directories.

## Порядок установки (отдельное root-действие)

1. Сначала выпустить совместимый клиент обычным механизмом. Убедиться, что
   новая упаковка уже создала и наполнила `immutable-assets`, включая текущий
   релиз. До этого не переключать nginx asset locations.
2. По [webhook setup](../../docs/deploy/vmsh-webhook-setup.md#2-установить-неизменяемые-исполняемые-файлы-и-конфигурацию)
   вручную установить root-owned deploy script и `vmsh-webhook-sudoers`.
   Выполнить `sudo visudo -cf /etc/sudoers.d/vmsh-webhook` и `bash -n` скрипта.
   Один push эти установленные файлы не обновляет.
3. Перенести изменения template в реально установленный rendered nginx site,
   сохранив production hostname, certificates, socket, security headers и media
   origin. Не заменять весь конфиг неотрендеренным шаблоном. Проверить доступ
   nginx к родительскому каталогу maintenance marker (нужен traverse/stat) и к
   retained assets. Выполнить `sudo nginx -t`, затем reload nginx.
   Полный [nginx gate](deployment.md) остаётся обязательным.
4. Проверить `/service-status` и старый asset URL. Провести согласованный
   контрольный backend redeploy с открытыми Student/Family/Staff: текст/фото/
   оценка, отсутствие logout, сохранение черновика, ровно одна серверная запись.
   Проверить логи, состояние analytics timer и новые Sentry episodes.

## Ручное восстановление после неудачи

Не удалять флаг просто по таймеру. Сначала посмотреть
`/web/vmsh_tasks_bot/deploy/logs/runs/vmsh-tasks-bot.log` и systemd journal,
устранить причину миграции/старта. При ошибке миграции writers остаются остановлены:
восстановление БД выполняется по существующему backup/rollback runbook, не запускать
старый код на неподтверждённой схеме. Затем завершить deploy исправленной revision.
Повтор той же уже записанной revision может завершиться как no-op; это не recovery proof.

Перед ручным снятием проверить оба сервиса, все три runtime напрямую на
Unix-сокет `/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.sock` с
`Forwarded: for="127.0.0.1";proto=https;host="vmsh.shashkovs.ru"`,
выбранный frontend release и его assets. TCP runtime-check на `127.0.0.1:8000`
не проходит production trust policy; `/metrics` остаётся обычным TCP-запросом.
Если файл `/web/vmsh_tasks_bot/deploy/runtime/deploy/analytics-timer-before-maintenance`
содержит `active`, запустить `vmsh-analytics.timer`; если `inactive`, не включать.
Только после подтверждения удалить этот файл и точный maintenance marker,
проверить публичные API и `/service-status`. Эти действия требуют оператора;
автоматический fail-open не предусмотрен.

## Проверки и ограничения выпуска

- Unit: `service-availability.test.ts` — совместный polling, HTML/JSON, 20/60+
  секунд, offline, cancellation, отсутствие повторов unsafe write, сохранение
  idempotency payload, бизнес/auth/runtime ошибки и внешние origins.
- `make pwa-e2e-redeploy` — настоящий isolated HTTP gateway, Chromium/Firefox/WebKit;
  cold start, ожидание Family дольше минуты, 20-секундная пауза формы,
  письменная отправка с фото и потерянный после записи ответ на оценку учителя. Управление
  fault mode существует только в E2E gateway с local/token guard.
- `pwa_tests/test_smooth_redeploy.py`, nginx/static-release/runner tests:
  порядок deploy, pre-maintenance migration rehearsal, двукратный DB performance
  guard, сохранение флага на ERR, narrow sudoers, сохранение assets.
  Это структурная проверка shell, не реальная неудачная production-миграция.
- Production root-конфиги в этой работе не устанавливались. Реальный `nginx -t`,
  fault rehearsal миграции и контрольный production redeploy остаются release
  gates; локально nginx не установлен. Отдельный сквозной fault-тест тестового
  ответа после записи/потери ответа ещё не выполнен; транспорт и существующие
  receipt/outbox регрессии проверяются unit/HTTP-тестами.

Локальные результаты: 844 frontend unit;
57 deploy/nginx/static-release/runner, 21 gateway HTTP и 71 lifecycle/
submission/live-marking regression passed. Три Storybook/axe состояния прошли
после восстановления отсутствовавшей локальной ссылки на уже установленный
Tailwind (не изменение исходных зависимостей). TypeScript приложений/shared/tools,
целевые ESLint/Ruff и production builds прошли. Browser gate: **15 passed** в
Chromium/WebKit/Firefox, включая реальные 20 и 60+ секунд ожидания.

## Исправление deploy health-check — 16 сентября 2026

Проверка runtime в установленном скрипте использовала TCP без доверенной цепочки,
получала 403 и оставляла maintenance включённым. `check_http_200` теперь только
для трёх точных локальных runtime URL выбирает доверенный Unix-сокет и Forwarded.
Для metrics и публичного HTTPS заголовки не меняются. Проверены 8 тестов
`pwa_tests/test_smooth_redeploy.py`, включая фактическую сборку argv curl
для всех пяти вариантов. Скрипт требует установки от root по разделу выше;
push исходника не заменяет установленную копию.
