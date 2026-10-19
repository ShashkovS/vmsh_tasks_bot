# Phase 2 — явные цели массовой загрузки

Дата: 28 июля 2026 года.

## Результат

Создана проверенная граница discovery для массовой загрузки LaTeX: по одному
текущему `group_lesson` Staff получает все конкретные групповые занятия того же
`course_lesson`. Ответ содержит course/lesson context и явные group lesson,
group name/short code/color/status.

Файл сам по себе никогда не определяет курс, номер занятия или группу. Это
важно после перехода к независимым группам: одинаковые названия файлов не дают
права загрузить материал в соседний курс или занятие. Будущий UI сопоставляет
каждый файл одной выбранной цели и виду `condition|hint|solution`, после чего
переиспользует существующие single-upload/compile операции.

## Реализация

- `PwaContentRepository.list_content_upload_targets()` выбирает siblings только
  через общий внутренний `course_lesson_id` и стабильно сортирует их по
  `groups.sort_order`, имени и ID.
- `GET /staff/api/v1/content/group-lessons/{id}/upload-targets` требует
  `CONTENT_MANAGE`; Teacher получает `403`, неизвестный anchor — `404`.
- Строгий Zod contract ограничивает batch 100 целями и запрещает повторные
  `groupLessonId`/`groupId`.
- Same-origin Staff client и TanStack query key используют только public IDs.

## Проверки

```text
ruff check
PASS

pytest pwa_tests/integration/test_content_http_api.py
27 passed

strict TypeScript: contracts + content
PASS

ESLint + Prettier affected files
PASS

vitest unit: content-api.test.ts + content-client.test.ts
28 passed
```

## Что ещё не закрыто

Это backend/contract precondition, а не готовый bulk workflow. Остаются:

- явное file → group lesson → material kind сопоставление в Staff;
- последовательная загрузка/компиляция с per-file progress и partial failure;
- сохранение результатов в history без автоматической публикации;
- Storybook interaction и production-build Playwright в трёх браузерах.
