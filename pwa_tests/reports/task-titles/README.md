# Названия задач — проверка 11 сентября 2026

[Требования и реализация](../../../vmshpwa/docs/task-titles.md).

Названия отображаются в общих листках Student/Family и Staff preview,
у самостоятельных пунктов, в таблицах очного приёма, Zoom и результатах школьника.
Условие использует метаданные своей версии; подсказка и решение сопоставляются
с опубликованным условием по ID задачи. Старые документы не переписываются.

## Проверки

- Backend: **5 passed** — `test_task_titles.py`, сценарии `flattens_subparts`,
  `resolved_material_match_without_duplicate_metadata`, `exact_revision_rollback`.
  Проверены авторизованные Student/Family/Staff, отсутствие названия в исходнике,
  переименование, неопубликованный черновик, fallback, самостоятельные пункты,
  reveal и откат. Команда: `.venv/bin/python -m pytest
  pwa_tests/integration/test_task_titles.py
  pwa_tests/integration/test_content_repository.py
  pwa_tests/integration/test_content_http_api.py -q -n 2
  -k 'task_titles or flattens_subparts or resolved_material_match_without_duplicate_metadata or exact_revision_rollback'`.
- Unit: **34 passed** — `math-document.test.tsx` и `content.test.ts`,
  `pnpm exec vitest run --project unit` с этими файлами.
- Storybook: **5 passed** — `math-document.stories.tsx`,
  `live-marking-grid.stories.tsx`, фильтр `Task Titles|Classroom|^Zoom$`.
  Включены длинные названия, независимые пункты, интеракции и таблица 200×50
  с прежним пределом p95 клика менее 50 мс.
- E2E: **18 passed**, без повторов — `content-publication.spec.ts`,
  `live-marking.spec.ts`, `student-results.spec.ts`, Chromium/WebKit/Firefox.
  Прогон использует production build и реальный изолированный aiohttp через
  `e2e_runner.exclusive_e2e_run` / `run_commands`.
  После окончательной правки плотности Zoom — **6 passed** в `live-marking.spec.ts`
  во всех движках, также без повторов. Сохранена проверка, что последняя из 24
  кнопок находится выше 740 px на экране 390×844.
- Проверены mobile 320/390, desktop, светлая/тёмная тема, 200% в результатах,
  клавиатура, публикация/rollback, offline/reload, undo и синхронизация оценок.
- TypeScript приложений/пакетов, ESLint, Ruff, Prettier, `git diff --check`,
  production build прошли. Миграции не нужны.

Дополнительный полный прогон двух Storybook-файлов выявил старый сценарий
`Zoom canvas: scroll-backed keyboard zoom`: он ищет отсутствующую роль
`region` «Просмотр рисунка» в прежнем интерфейсе просмотрщика. Этот сценарий
не относится к названиям задач и не включён в указанные 5 успешных сценариев;
сам просмотр условий/рисунков проверяется существующими E2E.

## Просмотренные снимки

| Экран | Снимок |
| --- | --- |
| Student, desktop | [Листок](student-desktop.png) |
| Family, 320 px | [Светлая тема](family-mobile.png), [тёмная тема WebKit](family-dark.png) |
| Zoom, 390 px | [Все 24 задачи](zoom-mobile.png) |
| Zoom, desktop | [Сетка](zoom-desktop.png) |
| Очное занятие | [Мобильная таблица](classroom-mobile.png) |
| Результаты школьника | [Desktop](results-desktop.png), [320 px, Firefox](results-mobile.png) |

Владелец разрешил commit и push 11 сентября 2026; серверное развёртывание не выполнялось. Внешние сервисы и пользовательская
база для тестов не использовались.
