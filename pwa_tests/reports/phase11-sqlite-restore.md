# Phase 11: SQLite restore rehearsal

Дата: 30 июля 2026 года.

## Результат

`db/vmsh.db` открыта только для чтения и скопирована через SQLite backup API в
новый owner-local файл внутри `.runtime/phase11-rehearsal/restores`. К копии
применены все миграции текущего checkout, после чего выполнены проверки:

- все 69 миграций находятся в актуальном состоянии;
- `PRAGMA integrity_check` вернул `ok`;
- восстановленная база работает в WAL-режиме;
- до и после миграций сохранились точные legacy row counts: 2 279 users,
  113 lessons, 1 813 problems, 223 370 results и 84 805 строк письменных
  обсуждений;
- исходная база не изменялась.

Локальное измерение на текущем Mac: backup 0,141 с, миграции 0,302 с,
проверка 0,187 с, суммарно 0,631 с для восстановленного файла 76 075 008 байт.
Это измерение локальной технической операции, а не обещание production RTO.

Машиночитаемый агрегированный отчёт:
[`phase11-sqlite-restore.json`](phase11-sqlite-restore.json). Он не содержит
имён, токенов, сообщений или Telegram ID. Сама ignored restore-копия содержит
реальные данные, имеет режим `0600`, не коммитится и предназначена только для
локальной репетиции владельца.

## Команда

```shell
PWA_RESTORE_TARGET=.runtime/phase11-rehearsal/restores/<run-id>.sqlite3 \
PWA_RESTORE_REPORT=.runtime/phase11-rehearsal/restores/<run-id>.json \
make pwa-phase11-restore-rehearsal
```

Target обязан быть новым файлом внутри фиксированного каталога. Команда не
удаляет и не заменяет существующие базы.

## Запуск PWA API на восстановленной копии

После restore проверки настоящий `main.py` был запущен поверх этой копии на
отдельном loopback-порту `8381` с профилем `pwa-agent`, instance
`phase11-restore` и синтетическими локальными auth-ключами. Prototype mode был
выключен. Telegram, Google и NATS не подключались.

Student, Family и Staff health endpoints вернули `200` и сохранили заданные
request IDs. Runtime contract подтвердил:

```json
{
  "instance": "phase11-restore",
  "features": {
    "telegram": false,
    "google": false,
    "nats": false,
    "prototype": false
  }
}
```

Процесс завершён штатным shutdown; lifecycle lock и SQLite connections были
освобождены.

## Проверки

- focused suite: `2 passed`;
- full regression: `559` frontend unit tests and `1 463` Python PWA tests
  passed; `3` Python tests were intentionally skipped;
- nonexistent source, существующий target и target вне разрешённого каталога
  отклоняются до копирования;
- row-count parity проверяется до и после миграций;
- исходная строка с именем и токеном остаётся неизменной в тесте;
- Ruff и `git diff --check`: PASS.

## Что ещё не доказано

- RPO текущего внешнего cron-backup не измерен: для этого нужны расписание и
  timestamp реального backup artifact;
- authenticated historical reads, WebSocket и static bundles ещё не проверены
  именно на этой restore-копии; health/runtime и полный app startup проверены;
- согласованность SQLite с S3 media и pending notification outbox ещё не
  проверена;
- production service user, systemd/nginx и atomic release rollback этой
  локальной репетицией не покрыты.

Поэтому это первый database-restore proof Phase 11, а не закрытие полного
backup/restore gate.
