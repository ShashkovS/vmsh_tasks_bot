# Phase 7: production-build E2E устного приёма

Дата проверки: 2026-07-29.

## Проверяемый маршрут

Один браузер последовательно проходит настоящий пользовательский путь:

1. Student входит в кабинет и открывает опубликованную устную задачу.
2. Student видит письменную альтернативу, раскрывает URL и код открытого окна.
3. Teacher входит в свой кабинет с отдельной cookie, выбирает того же школьника,
   ставит результат и внутреннюю реакцию.
4. aiohttp записывает результат в существующий `results` и реакцию в
   `reactions`, не создавая второго журнала результатов.
5. Student возвращается в свой кабинет и видит статус «Зачтено».

## Изоляция и данные

- сценарий работает с production-сборками Vite через E2E gateway;
- backend — настоящий aiohttp, база — заново созданная
  `db/vmshpwa_e2e.sqlite3`, MSW не используется;
- `vmshpwa/scripts/seed_e2e_oral.py` создаёт по одному независимому занятию для
  Chromium, WebKit и Firefox прямыми SQLite-запросами;
- seed содержит готовую `web_ast`-производную, поэтому занятие проходит те же
  правила видимости, что и обычная публикация;
- тест не обращается к Zoom, Telegram, Google, S3 или production-БД.

## Автоматические доказательства

```text
make pwa-e2e-oral
  Chromium: pass
  WebKit:   pass
  Firefox:  pass
  total:    3 passed

pwa_tests/test_e2e_runner.py
  8 passed

Ruff / ESLint / Prettier затронутых файлов
  pass
```

Snapshots не создавались и не обновлялись.

## Файлы

- `vmshpwa/e2e/oral-admission.spec.ts` — сквозной браузерный сценарий;
- `vmshpwa/scripts/seed_e2e_oral.py` — изолированные данные трёх browser
  projects;
- `vmshpwa/playwright.config.ts` — seed перед запуском aiohttp;
- `vmshpwa/scripts/e2e_runner.py` — отдельный режим `oral`;
- `Makefile` — команда `pwa-e2e-oral`.
