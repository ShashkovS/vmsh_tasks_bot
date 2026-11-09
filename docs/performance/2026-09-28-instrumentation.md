# Диагностика перед нагрузкой 28 сентября

Основание: [baseline и проблемы](2026-09-28-readiness.md).
Поведение загрузки фото, авторизация и redirect policy не меняются.

## Измерения и стоимость

- `vmsh_media_stage_duration_seconds{stage,outcome}`: upload.read,
  image.convert, image.normalize, image.webp, storage.put, storage.get, media.sign.
  [Контекст измерений](../../helpers/pwa/media_observability.py),
  [HTTP routes](../../apps/pwa_api/written_submission_routes.py),
  [attachment service](../../helpers/pwa/written_attachments.py),
  [converter](../../helpers/pwa/content/assets.py).
  image.convert включает normalize/webp: времена нельзя складывать.
  outcome означает завершение контекста; ненулевой код команды проверяется
  после внутреннего контекста и учитывается внешним image.convert как error.
- `vmsh_event_loop_lag_seconds` и `vmsh_event_loop_lag_current_seconds`:
  histogram и gauge по live worker PID в существующем секундном мониторе
  [request_trace.py](../../helpers/pwa/request_trace.py). Новых таймеров нет.
- `media.load.failed`: ошибки Blob fetch/validation двух attachment clients
  и img со stable mediaPath. AbortError исключён. Не более одного события
  в минуту и десяти за жизнь страницы. Успехи событий не создают.
  [Frontend](../../vmshpwa/packages/app-shell/src/product-analytics.tsx),
  [приём событий](../../apps/pwa_api/product_analytics_routes.py).
  Используется текущий пользовательский контекст analytics, без новых URL,
  текста ошибки или ID фото. Ошибки декодирования blob URL не покрыты.
  `vmsh_client_media_load_failures_total{audience}` считает принятые сообщения,
  а не все ошибки фото: процент ошибок по нему вычислять нельзя.

Labels фиксированы; метрики используют существующее хранилище Prometheus.
Новых Sentry events, SQL или сетевых запросов на успешную загрузку нет.
При ошибках добавляется ограниченное событие и его запись в существующую
аналитику. Stages попадают также в существующий slow-request log от 200 мс.
Локальный synthetic benchmark: около 2–4 мкс на observation, включая trace
и multiprocess вариант. Это не production load test и не гарантия нулевой цены.

## Вечерний анализ

```promql
histogram_quantile(0.95, sum by (le, stage) (rate(vmsh_media_stage_duration_seconds_bucket[5m])))
sum by (stage, outcome) (increase(vmsh_media_stage_duration_seconds_count[1h]))
max(vmsh_event_loop_lag_current_seconds)
increase(vmsh_event_loop_lag_seconds_count[5m]) - increase(vmsh_event_loop_lag_seconds_bucket{le="0.2"}[5m])
sum by (audience) (increase(vmsh_client_media_load_failures_total[1h]))
```

Сопоставлять с HTTP latency/errors, DB admission queue и CPU.
Причина reveal 500 пока не установлена; эта диагностика не является её исправлением.

## Для администратора: подготовлено, не включено

[Четыре alert rules](monday-alerts.yml) проверены production promtool.
Нужно подключить файл в rule_files Prometheus и настроить доставку через
Alertmanager либо эквивалентные Grafana alerts. Пустой rules API Prometheus
не исключает существующих Grafana managed alerts.

[Экспорт журнала](export-journal.sh) проверен bash -n. После вечерней нагрузки
из корня checkout:

```sh
sudo bash docs/performance/export-journal.sh '2026-09-28 09:00:00 UTC' '2026-09-28 21:00:00 UTC' /tmp/vmsh-20260928.jsonl.gz
```

Файл имеет закрытые права и содержит production logs: не добавлять в git.
SSH allowlist разрешает только последние 100 строк journal; полный экспорт
и проверка retention требуют администратора.

## Проверки

114 focused Python tests, затем 33 analytics/metrics tests; 23 frontend tests,
ESLint и app-shell typecheck PASS. Проверены сохранение исключений,
отсутствие событий на success/cancel и ограничение частоты browser events.
