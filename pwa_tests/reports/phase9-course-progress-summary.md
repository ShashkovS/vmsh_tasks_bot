# Phase 9: персональная сводка результатов курса

Дата проверки: 2026-07-29.

## Проверяемый результат

- Student получает собственную сводку по явно доступному курсу через
  `/student/api/v1/courses/{courseId}/progress`.
- Повторные попытки одной задачи и активные синонимы считаются одной логической
  задачей; статус определяется лучшим сохранённым verdict так же, как в списке
  задач.
- Ответ содержит личные totals, раскладку по занятиям и число затронутых задач
  по дням. Сравнение с группой, percentile и позиция школьника отсутствуют.
- Недоступный курс не раскрывается (`403`), произвольные query-параметры
  отклоняются (`422`).

## Граница этого инкремента

Это первая read-only часть Phase 9 поверх уже сохранённых `results`. Она ещё не
смешивает текущие факты с будущим versioned analytics run: strength curves,
best-group calculation, pending written submissions, streak и achievements
остаются отдельными следующими инкрементами.

Доступ к данным — один прямой SQL в `db_methods/pwa/progress.py`. Склейка
повторных попыток и синонимов находится в короткой функции
`models/pwa/progress.py`; HTTP-текст остаётся в route.

## Автоматические доказательства

```text
pwa_tests/domain/test_pwa_progress.py
pwa_tests/integration/test_phase9_family_courses.py
  6 passed

Ruff / git diff --check
  pass
```

Использовалась временная SQLite теста; production и human-база не открывались.
