# Phase 11: two-worker SQLite/NATS/WebSocket smoke

Дата: 30 июля 2026 года.

## Результат

Два независимых процесса `main.py` одновременно работали с одной временной
SQLite WAL database и одним одноразовым NATS prefix. Telegram, Google, S3 и
production credentials не подключались.

Проверен один полный межпроцессный путь:

1. Worker A принял настоящий Student login и записал сессию в SQLite.
2. Worker B с тем же cookie сразу вернул `200` на `auth/me`, прочитав сессию из
   общей базы.
3. К каждому worker открылся отдельный authenticated WebSocket.
4. Одно owner-neutral invalidation было опубликовано в локальный Core NATS.
5. Оба WebSocket получили `invalidate` с ресурсом `phase11/two-worker`.
6. После reconnect к worker B клиент получил `resync-required`, а не ложное
   подтверждение непрерывности cursor между процессами.

Команда:

```shell
make pwa-two-worker-local-smoke
```

Результат: **1 passed in 2.13s**. Тест использует временные DB/media/ports и
случайный agent-only NATS prefix. Оба worker и все NATS clients закрываются в
`finally`; сам `nats-server` тест не запускает и не останавливает.

## Диагностический первый прогон

Первый запуск корректно не достиг readiness, потому что пользовательский
`127.0.0.1:4222` в тот момент не слушал. Оба дочерних worker были остановлены,
данные не сохранились. После временного запуска локального `nats-server 2.14.3`
тот же неизменённый тест прошёл; сервер затем штатно остановлен.

## Граница доказательства

Проверены реальная межпроцессная видимость SQLite session и fan-out через NATS.
Это не численный load/failure gate: не измерялись write latency,
`SQLITE_BUSY`, 200 одновременных browser sessions, photo bytes и outbox depth.
Наблюдаемый production baseline из event logs значительно меньше — максимум
13 submission и 11 review-completion events в минуту — но отдельный небольшой
нагрузочный прогон всё равно остаётся Phase 11 gate.
