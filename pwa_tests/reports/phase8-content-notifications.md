# Phase 8: lesson-material publication notifications

Дата проверки: 2026-07-29.

## Реализованная граница

- Фактическая публикация `condition`, `hint` или `solution` создаёт соответственно `lesson_published`, `hint_published` или `solution_published`.
- Постановка материала в расписание событие не создаёт; тот же post-commit путь вызывается при реальном срабатывании расписания.
- Получатели определяются по active enrollment и active group. Доступ к дополнительной группе сам по себе не создаёт уведомление о её материалах.
- Student и связанный активный Family account получают разные account-scoped события с одним publication dedupe key.
- Payload хранит только public course/group/group-lesson/publication/student IDs, вид материала и номер занятия.
- Student route открывает соответствующий course/group/lesson в задачах; Family route открывает страницу нужного ребёнка.
- Событие создаётся до realtime invalidation, поэтому последующий refetch видит уже committed notification row.

## Автоматические проверки

- Реальный Staff upload → compile → metadata → lesson window → publish через aiohttp/SQLite создаёт ровно Student и Family events.
- Проверены категория, общий dedupe key, routes, payload и отсутствие получателей у неактивной группы.
- Scheduler unit-набор подтверждает единый `content-schedule-activated` post-commit путь.
- Полный связанный content HTTP/scheduler-набор: 51 passed; Ruff passed; `git diff --check` passed.

## Открыто отдельно

- Course-scoped overrides notification preferences.
- Явный подтверждённый триггер Family weekly review digest.
- Уведомления `deadline`, `oral_window` и `thread_updated` из соответствующих доменных переходов.
