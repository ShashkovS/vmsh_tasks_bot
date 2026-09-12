# Phase 9: проверка аналитики на 1500 школьниках

Дата проверки: 30 июля 2026 года.

## Проверяемый объём

Тест создаёт временную SQLite с той частью текущей схемы и теми же индексами,
которые использует расчёт прогресса курса:

- 1500 школьников;
- 38 занятий;
- 3 доступные группы на школьника;
- 6 задач на группу и занятие;
- 57 000 результатов;
- 57 000 рассчитанных и атомарно сохранённых точек `student_lesson_metrics`.

Проверяется полный путь `SQLite reads → calculate_course_lesson_metrics →
save_completed_course_metrics → personal read`. Это фоновый расчёт, который
планируется запускать раз в несколько часов, а не синхронный запрос страницы.

## Результат

```text
phase9 analytics elapsed=0.769s
1 passed in 1.22s
```

Порог теста — 15 секунд. Это широкий regression tripwire для developer Mac, а
не обещание production latency. Фактическое измерение имеет более чем
десятикратный запас.

`EXPLAIN QUERY PLAN` подтвердил:

- выборка доступов начинает с
  `course_enrollments_course_status_idx`, затем использует
  `course_group_access_enrollment_history_idx`;
- synonym lookup использует
  `problem_synonym_members_problem_active_uq`;
- связи с задачами, verdict и synonym-group читаются по primary key;
- SQLite не создаёт automatic indexes;
- course-wide выборка результатов закономерно читает все результаты курса и
  строит временный B-tree для требуемой сортировки. При измеренном объёме это
  не является проблемой.

Новый индекс, кэш, connection factory или отдельный read model для этой задачи
не добавлялись: измерение не показывает такой необходимости.

## Воспроизведение

```text
UV_CACHE_DIR=.runtime/uv-cache uv run pytest -q -n0 \
  pwa_tests/integration/test_phase9_course_performance.py -s
```

Тест: `pwa_tests/integration/test_phase9_course_performance.py`.
Production, human/agent runtime, Telegram, Google и S3 не используются.
