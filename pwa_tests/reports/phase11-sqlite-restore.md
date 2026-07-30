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
- API/WS/static bundles ещё не запускались именно на этой restore-копии;
- согласованность SQLite с S3 media и pending notification outbox ещё не
  проверена;
- production service user, systemd/nginx и atomic release rollback этой
  локальной репетицией не покрыты.

Поэтому это первый database-restore proof Phase 11, а не закрытие полного
backup/restore gate.
