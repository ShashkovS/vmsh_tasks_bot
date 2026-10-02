# Файловые вложения: проверка 2 октября 2026

Реализован локально [принятый план](../../../vmshpwa/docs/rich-file-attachments.md):
«Прикрепить файл» в news, broadcasts/banners и блоках до/после задач;
постоянная публичная ссылка, максимум 50 МиБ, все 15 разрешённых расширений.
Файл сохраняется без преобразования в существующий ObjectStorage. SQLite
миграция не нужна. Production-выпуск и live S3 не выполнялись.

## Выполненные проверки

- Backend upload/storage, существующие rich-media/lesson-block API, nginx и
  E2E runner — **74 PASS** в финальном целевом прогоне. Команда:
  `uv run pytest -q -n4 pwa_tests/integration/test_rich_files.py pwa_tests/integration/test_rich_markdown_media.py pwa_tests/integration/test_lesson_blocks_api.py pwa_tests/test_nginx_proxy_config.py pwa_tests/test_e2e_runner.py`.
  Проверены все форматы, server MIME вместо присланного MIME, исходные байты,
  публичный S3-shaped URL, кириллица/спецсимволы, пустой файл, запрещённое
  расширение, предел имени, ровно 50 МиБ через HTTP, превышение на байт,
  лишняя/nested multipart-часть, S3/filesystem errors, 401/403 до записи,
  анонимный GET, SHA-256 и защита от traversal/symlinks.
- Frontend unit:
  `pnpm exec vitest run --project unit --exclude apps/staff/src/staff-testing-page.test.tsx`
  — **1002 PASS**, 196 файлов. Новый Zod-контракт, multipart/401 refresh обоих
  клиентов, canonical local URL только для ссылок, экранирование имени,
  повторный выбор файла, ошибка, актуальный текст/выделение CodeMirror и обоих
  textarea после ожидания. Upload сам не сохраняет и не публикует текст.
- Storybook:
  `pnpm exec vitest run --config vitest.storybook.config.ts apps/staff/src/staff-file-upload.stories.tsx apps/staff/src/staff-lesson-block-editor.stories.tsx`
  — **6 PASS**. Готовность, ожидание, ошибка, disabled, EN/dark/reduced motion
  в узкой композиции, существующий lesson editor; keyboard focus и addon-a11y
  в режиме `error`.
- `make pwa-e2e-rich-files` — **9/9 PASS без retries**, два успешных прогона:
  Chromium, WebKit и Firefox. Настоящий aiohttp, filesystem ObjectStorage,
  изолированные SQLite/media/NATS prefix, единый E2E gateway и production
  bundles всех четырёх приложений. Нет S3/Telegram/Google credentials или
  запросов к внешним сервисам.
- `make pwa-lint pwa-typecheck` — PASS. `make pwa-i18n-extract` выполнен;
  новые Staff/backend строки переведены. Финальный `make pwa-i18n-check` —
  PASS для frontend и backend. Production Vite build всех четырёх приложений
  — PASS в runner.
- Scoped Prettier, Ruff и `git diff --check` — PASS.

Сценарии в
[`rich-file-attachments.spec.ts`](../../../vmshpwa/e2e/rich-file-attachments.spec.ts):

1. `news attachment survives publication and caption editing for Student and Family`:
   upload, новая публикация, редактирование подписи обычной Markdown-ссылки,
   открытие из Student и Family, анонимное получение исходных байтов.
2. `broadcast banner attachment is published to Student and Family`:
   настоящий banner upload/save/publication, ссылка на обоих домашних экранах.
3. `both lesson blocks retain file links through draft and publication`:
   before и after, draft/save/publication/reload, ссылки в обеих аудиториях,
   получение исходных байтов.

## Ограничения общей тестовой базы

`make pwa-test` остановился на существующем
`StaffTestingPage > shows failed entry without navigating and allows retry`:
ожидается русская fallback-строка, а ошибка сервиса содержит английский текст.
Прогон: 1000 PASS, 1 FAIL; тест/компонент этой задачи не менялись. Остальные
unit-файлы повторно прошли командой выше. Это исключение явно сохранено,
полностью зелёный общий unit gate не заявляется.

Полный `make pwa-python-test`: 2536 PASS, 6 SKIP, 5 FAIL. Четыре ошибки в
`test_content_characterization`/`test_legacy_golden_corpus` связаны с прежним
игнорируемым `_vmsh_examples/.DS_Store`. Файл и старый corpus сохранены.
Пятая была проверкой числа nginx locations: ожидание 9 обновлено до 10 после
добавления публичного namespace, целевой nginx прогон повторно прошёл.

Во время финальных проверок в общем рабочем дереве появились изменения
другой задачи — новый набор задач и миграция `0108.pwa_fresh_problem_sets`.
Гонка с созданием migration-файла остановила инициализацию тестовых fixtures;
повторный backend-прогон после появления файла прошёл. Промежуточный общий
`make pwa-i18n-check` остановился на двух новых строках этой параллельной
задачи. После появления переводов финальный общий i18n gate прошёл.
Чужие изменения сохранены; этот инкремент не добавляет миграций.

## Снимки

Просмотрены кнопка, подсказка, Markdown и preview в трёх браузерах. Снимки
получены в финальном успешном E2E с fixture-данными. Фиксированная общая шапка
попадает в снимки форм при прокрутке; это не новый overlay в редакторе.

| Движок   | Staff news editor                               | Staff before/after                             | Student news                                   |
| -------- | ----------------------------------------------- | ---------------------------------------------- | ---------------------------------------------- |
| Chromium | [редактор](chromium/news-file-editor-staff.png) | [блоки](chromium/lesson-attachments-staff.png) | [ссылка](chromium/news-attachment-student.png) |
| WebKit   | [редактор](webkit/news-file-editor-staff.png)   | [блоки](webkit/lesson-attachments-staff.png)   | [ссылка](webkit/news-attachment-student.png)   |
| Firefox  | [редактор](firefox/news-file-editor-staff.png)  | [блоки](firefox/lesson-attachments-staff.png)  | [ссылка](firefox/news-attachment-student.png)  |

## Выпуск

Выпустить backend с upload/GET API и frontend с кнопкой/контрактами; применить
обновлённый nginx, если используется filesystem. S3 использует существующий
публичный bucket/prefix без новых настроек. Удаление/скрытие ссылок не удаляет
объекты. Inventory не сканирует эти ссылки в AST и не разрешает очистку
`rich-files` по `unreferencedKeys`; см.
[retention](../../../vmshpwa/docs/media-inventory-and-retention.md).

## Release integration — 2 октября 2026

Фича перенесена отдельным patch поверх `b6d32e2a` (после production release
progressive tasks `0b2964a8`). Сохранены problem-release API и все его контракты;
единственный import conflict разрешён с сохранением обоих route registries.
Незавершённый fresh-problem-set инкремент и его migration исключены.

Повторно на этой source-версии: 83 backend (включая problem-release), 17
attachment unit, 9 E2E без retries в трёх браузерах, production builds, lint,
TypeScript и оба i18n gate — PASS. Тестовый профиль — пустой ignored JSON,
без Telegram/Google/S3 credentials. Ручной data checker проверен на стабильных
хешах и обнаружении изменения raw Zoom receipt; shell syntax и Ruff — PASS.
