# Phase 9: работы, ожидающие проверки, в личном прогрессе

Дата проверки: 2026-07-29.

## Проверяемый результат

- Существующая `written_tasks_queue` добавляется к персональной сводке курса
  без новой таблицы и без копирования состояния очереди.
- Одна ожидающая письменная работа считается в `attempted` даже до первого
  verdict и отдельно попадает в `awaitingReview`.
- Если после прошлого verdict отправлена пересдача, задача может одновременно
  учитываться в достигнутом результате и в `awaitingReview`; это не два разных
  задания.
- Активные синонимы в очереди схлопываются тем же логическим ключом, что и
  проверенные результаты.

## Реализация и доказательства

`db_methods/pwa/progress.py` содержит отдельный короткий прямой SQL к
`written_tasks_queue`, `problems` и `groups`. Объединение фактов выполняет
`models/pwa/progress.py`.

```text
Python domain + aiohttp/SQLite integration
  6 passed

Zod contract + Student client
  12 passed

Ruff / ESLint / strict TypeScript
  pass
```

Production и human SQLite не открывались. Новая миграция не потребовалась.
