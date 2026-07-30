# Phase 11: репетиция переноса учеников в курс

Дата: 30 июля 2026 года.

## Результат

На отдельной копии `db/vmsh.db` выполнены обезличивание, все актуальные
миграции и первый многокурсовый backfill:

- создан сезон `2025-26` и курс `course-math-5-7` «Математика 5–7»;
- четыре существующих `group_id` сохранены и привязаны к курсу;
- для 1 617 школьников созданы course enrollment;
- текущая группа совпала у всех 1 617 школьников;
- режим `online|in_person` совпал у всех 1 617 школьников;
- созданы 4 851 активных интервала доступа к группам;
- `PRAGMA integrity_check`: `ok`.

Агрегированный результат сохранён в
[`phase11-course-enrollment-rehearsal.json`](phase11-course-enrollment-rehearsal.json).
В нём нет имён, дат рождения, Telegram ID или токенов.

## Граница безопасности

[`legacy_course_rehearsal.py`](../../vmshpwa/scripts/legacy_course_rehearsal.py)
открывает исходную SQLite только для чтения через backup API. Новая база может
находиться только внутри `.runtime/phase11-rehearsal` и не должна существовать
до запуска. До применения миграций в копии заменяются имена, фамилии, даты
рождения и токены, а Telegram chat ID очищаются. Исходные строки, legacy ID,
задачи и результаты не изменяются.

Команда для новой одноразовой копии:

```shell
PWA_REHEARSAL_TARGET=.runtime/phase11-rehearsal/<run-id>.sqlite3 \
PWA_REHEARSAL_REPORT=.runtime/phase11-rehearsal/<run-id>.json \
make pwa-phase11-course-rehearsal
```

## Проверки

- unit/integration: исходная БД остаётся неизменной, копия обезличивается,
  legacy group IDs сохраняются, group/mode/access parity совпадает;
- повторный backfill не создаёт дубли;
- неизвестная группа блокирует всю транзакцию;
- существующий или находящийся вне `.runtime/phase11-rehearsal` target
  отклоняется;
- focused suite: `5 passed`;
- полный Python regression PWA: `1 451 passed, 3 skipped`.

Этот инкремент не переносит занятия, историю `G/O`, письменные обсуждения или
синонимы. Они остаются следующими независимыми срезами Phase 11.
