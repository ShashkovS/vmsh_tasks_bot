# Phase 9: production-build E2E семейного контекста

Дата проверки: 2026-07-29.

## Проверяемый маршрут

Один сценарий выполняется независимо в Chromium, WebKit и Firefox:

1. Family входит через настоящий экран аутентификации.
2. Родитель видит двух связанных детей и открывает первого.
3. Для ребёнка с опубликованным занятием показывается актуальный курс и работает
   переход к browser-ready листку.
4. Для второго ребёнка без опубликованного занятия показывается честное пустое
   состояние без неработающей кнопки.
5. Прямой переход к несвязанному student ID заканчивается `403`-состоянием и не
   раскрывает учебные данные.

## Изоляция и данные

- тест работает с production-сборками трёх Vite-приложений;
- backend — настоящий aiohttp, база — отдельная seeded
  `db/vmshpwa_e2e.sqlite3`, MSW не используется;
- используются уже существующие изолированные Family, Student и course fixtures;
- тест не обращается к Telegram, Google, S3 или production-БД.

## Автоматические доказательства

```text
make pwa-e2e-family
  Chromium: pass
  WebKit:   pass
  Firefox:  pass
  total:    3 passed

pwa_tests/test_e2e_runner.py
  8 passed

Ruff / ESLint / strict TypeScript / git diff --check
  pass
```

Во время завершения одного browser project aiohttp gateway записал известную
гонку закрытия WebSocket (`transport is None`); пользовательский сценарий и все
три browser project завершились успешно. Visual snapshots не создавались и не
обновлялись.

## Файлы

- `vmshpwa/e2e/family-context.spec.ts` — сквозной семейный сценарий;
- `vmshpwa/scripts/e2e_runner.py` — отдельный режим `family`;
- `vmshpwa/package.json` — команда `e2e:family`;
- `Makefile` — команда `pwa-e2e-family`.
