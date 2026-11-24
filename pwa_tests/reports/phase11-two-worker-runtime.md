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
Проверка не измеряет production network, systemd и nginx; эти границы
остаются deployment gate.

## Небольшой численный прогон

Отдельная команда:

```shell
make pwa-two-worker-load-local-smoke
```

Те же два процесса получили одновременно 40 успешных Student login.
Каждый запрос выполняет реальную транзакцию: создаёт session, пишет
auth event и обновляет account timestamp. Это больше наблюдаемых за
минуту 38 ingress, 13 submission и 11 review-completion events.

Измерение на текущем Mac:

- 40/40 HTTP responses — `200`;
- вся вспышка — `1.490s`, 26.8 request/s;
- p50 `1.355s`, p95 `1.484s`, max `1.487s`;
- в SQLite появилось ровно 40 новых session и 40 `session.created`
  events; journal остался WAL;
- в логах обоих worker нет `database is locked` и exhausted busy.

Тест ставит только широкие smoke-пороги (30s на burst, 20s p95), а не
выдуманный production SLA. Дополнительно прошли `6` узких проверок:
откат целой транзакции при ошибке, явный busy outcome без half-write,
один победитель при двух одновременных teacher claims в coroutine и в
отдельных процессах.

## Письменные сдачи и фотографии

3 августа тем же target добавлен второй небольшой burst, приближенный к
серверной части flush локальных outbox. Два отдельных Python-процесса
одновременно записывают в одну WAL-базу независимые ветки двух школьников:

- 16 письменных сдач — немного больше наблюдаемого пика в 13 submission
  events за минуту;
- 32 фотографии по 512 KiB, всего 16 777 152 bytes;
- отдельный временный media root для каждого процесса;
- полный серверный путь `draft → attachment metadata → submitted`, включая
  idempotency records и очередь проверки;
- ровно 2 новых thread, 16 entry, 32 attachment/media asset, 64 idempotency
  record и 2 queue item;
- ни одного исчерпанного `SQLITE_BUSY`; journal после burst остаётся WAL.

Измерение на текущем Mac: вся запись заняла **0.692s**, p95 одной сдачи с
двумя фотографиями — **0.033s**. Smoke-пороги намеренно широкие: 30s на burst
и 10s p95. Это защита от зависшего writer, а не production SLA. Допустимый
user-visible budget для исчерпанного `SQLITE_BUSY` при таком объёме — ноль;
ограниченный внутренний retry допустим.

Файлы в этом тесте содержат репрезентативное количество opaque bytes, а не
повторяют декодирование изображений. Реальные HEIC/JPEG/WebP conversion,
размеры и metadata отдельно доказаны
[`phase5-written-media-corpus.md`](phase5-written-media-corpus.md). Клиентский
Dexie/localStorage recovery отдельно покрыт Phase 5 browser/unit-набором.
Таким образом, один простой opt-in smoke измеряет только недостающую здесь
границу SQLite/file IO и не превращает проект в отдельный load-test framework.

Итоговый повторный прогон `make pwa-two-worker-load-local-smoke`:
**2 passed in 5.53s**. Первый диагностический прогон не достиг readiness,
поскольку пользовательский `127.0.0.1:4222` не был запущен; после временного
локального NATS тот же код прошёл, а созданный тестом сервер был штатно
остановлен. После изменения общий PWA Python gate в восьми workers:
**1552 passed / 6 intentional skips in 72.83s**.
