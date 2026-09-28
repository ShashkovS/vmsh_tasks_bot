# Готовность к понедельничной нагрузке, 28 сентября

## Проверено до нагрузки

Read-only проверка 08:40–08:45 UTC (11:40–11:45 МСК/Кипр).
Production HEAD 627aa0c, текущие workers с 27.09 12:52:52 UTC, NRestarts=0.
[Baseline Prometheus](2026-09-28-baseline.json): последние 18 часов до
08:41:27 UTC, целиком после hotfix фото. Counts приблизительные (increase),
p95 интерполирован по buckets, включает все HTTP statuses. Это baseline,
не A/B-доказательство ускорения и не гарантия устойчивости вечернего пика.

- 172 372 HTTP requests, 186 >1 с (0,108%). Peak 5m rate 25,46 req/s.
- CPU mean 7,28%, peak 5m 31,79%; available RAM минимум 1,08 GiB,
  disk vda busy peak 5m 1,09%. Утром available RAM 2366 MiB.
- p95: review/items 175 мс, auth/me 88 мс, список задач 165 мс,
  материал занятия 158 мс, review/series 341 мс.
- Read admission p95 42,9 мс, peak queue 23 у каждого worker;
  максимумы не обязательно одновременны.
- Staff photo GET: 2305 requests, mean 281 мс, p95 603 мс;
  upload: 139, mean 2,23 с, p95 5,04 с.
- Statistics: 855 requests, mean 615 мс, p95 1,57 с.
- Reveal: 59 HTTP 500, 183 HTTP 200, 7 HTTP 401: 23,7% ошибок этого
  маршрута. Это функциональная проблема, не доказанная нехватка мощности.
- Push subscriptions: 16 HTTP 500. В доступном свежем stacktrace есть
  ConnectionResetError во время request.read: не все такие 500 обязательно
  означают серверную бизнес-ошибку; нельзя обобщать один stacktrace на все 16.
- Prometheus /api/v1/rules вернул groups:[] — recording/alert rules на этом
  сервере отсутствуют. Grafana-managed/external alerts этим не проверены.

## До пика

Не менять workers, reader concurrency, SQL/schema или снова способ получения
фото без измерений/браузерного smoke. Сначала проверить reveal stacktrace и
сделать узкий исправляющий выпуск, если воспроизведение подтвердит причину.
Не считать авторизованным здесь запуск большого performance refactor.

Приоритет диагностики:
1. Полный временной интервал journald vmshpwa, а не последние 100 строк.
   Имеющийся SSH sudo allowlist не даёт исторический экспорт. Администратору
   нужен ограниченный read-only exporter по unit и времени или подготовленный
   архив. Не менять доступ обходными способами.
2. Существующие pwa_slow_request (>=200 мс), pwa_db_operation и
   pwa_event_loop_lag (>=100 мс) уже дают DB queue/owner/SQL stages. Их сохранять
   вместе с timestamps, PID и request_id, включая stacktraces ошибок.
3. Добавить узкие stage timings upload.read / image.normalize / image.webp /
   storage.put / storage.get / media.sign. Использовать существующий trace_stage
   из helpers/pwa/request_trace.py, не логировать payload или signed URLs.
   Это предложение; код ещё не изменён.
4. Loop lag сейчас только в журнале: histogram по worker/процессу позволит
   сопоставить лаг, DB очередь и CPU в Prometheus без полного журнала.
5. Раздельные counts по media delivery (proxy/direct) и frontend media-load
   failures: HTTP 302 не подтверждает успешную загрузку картинки. Не плодить
   Sentry event на каждый retry; дедупликация/лимит на эпизод.
6. Уточнить восстановление Sentry error quota; вечерний сбор не должен зависеть
   от него. Настроить/проверить отдельный канал алертов Prometheus/Grafana.

Предлагаемые стартовые пороги (требуют настройки, сейчас не включены):
interactive p95 >500 мс 5 минут при >=100 requests за 5 минут; read queue >20
30 секунд; loop lag >200 мс повторно; 5xx>=5 за 5 минут на одном маршруте.
Uploads/statistics отделять от interactive. Для малопосещаемых критичных
действий показывать абсолютное число 5xx рядом с долей.

## Вечерний разбор

Сравнивать 5-минутные окна RPS/count, p95/p99, долю >0,5/1/5 с, errors по
маршрутам; DB wait/hold и waiting/active по PID; CPU/iowait/memory pressure;
loop lag и deployment timestamps. Сначала найти интервал деградации, затем
по журналу владельца слота/стадию, и только после этого выбирать оптимизацию.
Стадии auth и db.admission_queue вложены: не суммировать их как независимые.
Отдельно фиксировать frontend failures: вчерашний инцидент давал 302 вместо 5xx.

Установочный скрипт предусматривает journald persistent/512M/14day, но фактический
conf недоступен пользователю SSH. Вывод journalctl --disk-usage показывает 8M в
доступной области и не доказывает сохранность системных журналов. Retention
следует проверить администратору до нагрузки. Prometheus baseline сохранён;
полный journald, новые stage metrics и alerts в этом аудите не включались.
