# Phase 9: production-build E2E семейного контекста

Дата проверки: 30 июля 2026 года.

## Проверяемый маршрут

Два сценария выполняются независимо в Chromium, WebKit и Firefox:

1. Family входит через настоящий экран аутентификации.
2. Родитель видит двух связанных детей и открывает первого.
3. Для ребёнка с опубликованным занятием показывается актуальный курс и работает
   переход к browser-ready листку.
4. Для второго ребёнка без опубликованного занятия показывается честное пустое
   состояние без неработающей кнопки.
5. Прямой переход к несвязанному student ID заканчивается `403`-состоянием и не
   раскрывает учебные данные.
6. У отдельной тестовой семьи два ребёнка с разными классами и независимыми
   course enrollment.
7. Ответ `home` второго ребёнка намеренно задерживается. После перехода экран
   сразу показывает его заголовок/loading state и не подставляет имя, класс или
   учебное состояние первого ребёнка из TanStack Query cache.
8. Родитель меняет первому ребёнку группу и формат, читает объяснение, отдельно
   подтверждает действие и получает успешный ответ настоящего aiohttp.
9. После reload select-ы и прямой API read показывают сохранённые значения и
   следующую optimistic version.

## Изоляция и данные

- тест работает с production-сборками трёх Vite-приложений;
- backend — настоящий aiohttp, база — отдельная seeded
  `db/vmshpwa_e2e.sqlite3`, MSW не используется;
- для изменяемого сценария каждый browser project получает отдельный Family
  account и двух отдельных Student, поэтому параллельные браузеры не делят
  enrollment/version;
- маленький `seed_e2e_family_progress.py` добавляет fixture прямыми SQLite
  insert-ами до старта aiohttp и не подменяет production API;
- тест не обращается к Telegram, Google, S3 или production-БД.

## Автоматические доказательства

```text
make pwa-e2e-family
  Chromium: 2 passed
  WebKit:   2 passed
  Firefox:  2 passed
  total:     6 passed

pwa_tests/test_e2e_runner.py
  8 passed

Ruff / ESLint / strict TypeScript / git diff --check
  pass
```

Visual snapshots не создавались и не обновлялись.

## Файлы

- `vmshpwa/e2e/family-context.spec.ts` — сквозной семейный сценарий;
- `vmshpwa/scripts/seed_e2e_family_progress.py` — отдельные изменяемые Family
  personas для трёх браузеров;
- `vmshpwa/playwright.config.ts` — запуск нового seed до aiohttp;
- `vmshpwa/scripts/e2e_runner.py` — отдельный режим `family`;
- `vmshpwa/package.json` — команда `e2e:family`;
- `Makefile` — команда `pwa-e2e-family`.
