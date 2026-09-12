# Phase 7: устные результаты

Дата проверки: 2026-07-29.

## Что работает

- Staff получает список online-школьников и опубликованных устных задач выбранного
  `group_lesson`.
- Преподаватель отправляет один устный раунд с плюсами/минусами и необязательной
  внутренней реакцией.
- Результат записывается в существующие `zoom_conversation`, `results` и
  `reactions`; отдельный журнал устных вердиктов не создан.
- Повтор запроса с тем же ключом возвращает прежний результат, а другой payload с
  тем же ключом отклоняется.
- Плюс удаляет ожидающую письменную сдачу этой задачи, минус переводит прежний
  положительный устный/очный результат в отклонённый — как в legacy-потоке бота.
- Очный школьник не попадает в roster и не может получить online-результат.

## Изменение схемы

Миграция `0071.pwa_oral_results_idempotency` добавляет nullable
`zoom_conversation.pwa_idempotency_key` и частичный unique index. Проверен цикл
up → down → up и `PRAGMA integrity_check`.

Canonical schema artifacts обновлены. В migration-head 403 объекта.

## Автоматические проверки

```text
uv run pytest -q pwa_tests/integration/test_phase7_oral_results.py
3 passed

uv run pytest -q -n0 \
  pwa_tests/test_schema_inventory.py \
  pwa_tests/integration/test_migration_lifecycle.py \
  pwa_tests/integration/test_phase7_oral_results.py
29 passed

uv run ruff check \
  apps/pwa_api/oral_result_routes.py \
  db_methods/pwa/oral_results.py \
  models/pwa/oral_results.py \
  pwa_tests/integration/test_phase7_oral_results.py
All checks passed
```

## Реализация и доказательства

- HTTP: `apps/pwa_api/oral_result_routes.py`;
- правила: `models/pwa/oral_results.py`;
- прямые SQL-операции: `db_methods/pwa/oral_results.py`;
- миграция: `migrations/0071.pwa_oral_results_idempotency.sql`;
- интеграционный тест: `pwa_tests/integration/test_phase7_oral_results.py`.

Следующий проверяемый срез — компактный Staff-интерфейс выставления устных
результатов и его Storybook interaction-сценарий.
