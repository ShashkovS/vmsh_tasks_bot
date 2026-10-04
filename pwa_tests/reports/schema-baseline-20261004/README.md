# Схлопывание схемы SQLite — 4 октября 2026

Вместо 82 последовательных миграций используется
[`0111.current_schema.sql`](../../../migrations/0111.current_schema.sql).
Все 155 старых forward/rollback SQL файлов удалены; они остаются в Git до
`dc808173`. Новые миграции начинаются с 0112. Схема сохранила 510 product objects
и тот же DDL/PRAGMA fingerprint. Новые БД получают справочники/defaults,
но не 627 исторических строк `kv_logins`.

Удалены 66 исторических test функций цепочки, up/down/up и backfill;
[список](removed-historical-tests.json). Оставшиеся auth/content/submission/
classroom constraints и бизнес-сценарии проверяются на полной текущей схеме.
Названия бывших смешанных `*_migration.py` приведены к их нынешнему назначению.

| Измерение                           |                 До |              После |
| ----------------------------------- | -----------------: | -----------------: |
| Миграции / файлы SQL                |           82 / 155 |              1 / 1 |
| Пустая БД + WAL, медиана 5 запусков |            0,609 с |            0,306 с |
| Полный Python, 4 workers, wall time |           79,489 с |           49,294 с |
| Полный Python, результат            | 2846 pass / 7 skip | 2782 pass / 7 skip |

Относительно уже ускоренного Python gate — ещё **38%** сокращения времени.
Пустой bootstrap ускорился примерно вдвое; большую часть экономии этого
шага даёт удаление исторических chain checks. Это сравнение меньшего набора
после согласованного удаления тестов. Исходные замеры предыдущей оптимизации:
[check-optimization-20261003](../check-optimization-20261003/README.md).

Chromium: 8 content/review/submissions сценариев на настоящем backend и новой
БД — PASS, 0 retries, 44,508 с wall time. Верифицированная frontend сборка
переиспользована (0,186 с), новый чистый seed занял 0,509 с. Frontend source
не менялся; unit/Storybook/вся browser matrix повторно не запускались.

## Совместимость существующих БД

[`migrations.py`](../../../db_methods/pwa/migrations.py) распознаёт прежний
head по hash 0110 и точному product DDL fingerprint. Runtime проверяет его
read-only. Явная команда под yoyo lock делает `mark` новой baseline, сохраняя
исторические bookkeeping rows; baseline SQL над текущими product rows не
исполняется. Telegram и PWA используют один путь. Устаревшая или изменённая
схема не принимается автоматически.

На изолированной копии рабочей ВМШ БД регистрация заняла **0,024 с**:
все 158 product tables и их строки, DDL и прежние 82 записи миграций сохранены;
добавлена только новая запись baseline и yoyo log. Прежние 627 FK violations
не изменились. Исходная БД не менялась. Это однократная репетиция, а не
сохранённый тест старой цепочки.

Live DDL обоих production прочитан read-only: 0110, 510 объектов, точное
совпадение DDL и hash прежнего head с новой исходной точкой. Product rows
не выбирались. [Обезличенное доказательство](production-schema-check.json).
Production в этом шаге **не менялся**, изменения пока не закоммичены.

## Проверки и исходные данные

- `pytest tests pwa_tests -n4 -q --tb=short`: 2782 passed, 7 skipped,
  46,59 с pytest / 49,294 с wall time.
- `python -m vmshpwa.scripts.e2e_runner --mode content --mode review
--mode submissions --browser chromium`: 8 PASS.
- Schema inventory и read-only historical live report, scoped Ruff,
  `git diff --check`: PASS.
- Первый full Python запуск без разрешения bind localhost не пригоден для
  замера; завершённый успешный повтор использовал разрешённые local servers.
- После полного Python были только format/import-order правки в оставшихся
  тестах и комментариях; поведение не менялось.

Сводные [measurements.json](measurements.json) не содержат product rows,
credentials, user names или bodies. Полные логи, копии БД и временная архивная
цепочка сохранены только в игнорируемом `.runtime/schema-squash-20261004/`.
[Решение и компоненты](../../../vmshpwa/docs/schema-baseline-20261004.md).
