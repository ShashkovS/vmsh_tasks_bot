# Этап 2. LaTeX-контент, diagnostics, preview и публикация

## Результат

Admin загружает условие/подсказку/решение одного уровня или пакет урока, разрешает позиционные расхождения задач, получает diagnostics и missing-assets flow, проверяет PWA/Telegram preview и публикует либо планирует конкретную revision по уровню. Print-раздел откладывается во вторую версию.

## Модель данных

Логическая migration: `pwa_content_revisions_assets_publications`.

Таблицы: `content_sources`, `content_revisions`, `media_assets`, `content_revision_assets`, `content_derivatives`, `content_problem_matches`, `problem_revisions`, `problem_synonym_groups`, `problem_synonym_members`, `lesson_publications`, `hint_reveals`, `solution_reveals`.

Legacy `lessons/problems` сохраняются. Compiler создаёт versioned representation и только после явной публикации обновляет совместимую projection/adapter, если это требуется Telegram.

## Compiler pipeline

1. Detect encoding (`CP1251`/UTF-8) и нормализовать в Unicode без изменения source hash record.
2. Parse LaTeX в canonical typed document AST; unknown macro даёт diagnostic с file/line/column.
3. Сопоставить задачи по порядку. Если число/структура пунктов изменились, остановить публикацию и показать ручное сопоставление с legacy `problems`; обязательного ID в LaTeX нет.
4. Content-address assets; TikZ → отдельный sanitized SVG; raster → WebP.
5. Сгенерировать web AST/HTML для client KaTeX, Telegram-rich dialect и PDF.
6. Проверить link/media/Telegram limits и sanitizer/CSP. Поддерживаемый корпус — KaTeX + конструкции исторического `a16_html_from_tex.py`.
7. Сохранить compiler version/hash. Recompile не меняет publication до явного действия.

Reference: `_external_pipelines/a16_html_from_tex.py`, `edt_tasks_parser.py`, `mathimg_*`, `a12`, `a14`, `a20`; production не импортирует их напрямую.

## Staff UI

- Routes: `staff/src/routes/lessons.*`, `problems.*`.
- Upload single/bulk; conditions and solutions separate; per-level selection.
- Diagnostics grouped by errors/warnings with source location and recovery action.
- Missing asset: search content-addressed library, upload replacement, reuse exact hash, rerun compile.
- LaTeX в браузере не редактируется. Metadata grid содержит название, task/answer type, validation/wrong/congratulation messages и optional topic tags; поддерживает keyboard edits, TSV paste preview, cell errors и optimistic version conflict.
- Synonym suggestion from equal titles with explicit accept/reject.
- Side-by-side PWA and Telegram preview. Уже сгенерированный PDF derivative можно открыть для regression/контроля, но команд печати и отдельного print workflow в v1 нет.
- Publish/schedule/hide confirmation per level/kind. Hidden lesson исчезает из Student как неопубликованный; просмотревший старую revision получает индикатор обновления после новой публикации.

## Client renderer

- `packages/content`: semantic math document, client KaTeX on main thread, KaTeX font precache, tables/lists/subparts.
- Figure viewer: SVG as external asset, pinch zoom mobile, keyboard +/-/reset desktop, accessible alt/caption.
- Sanitized content policy shared between preview and real Student renderer.
- Long lesson stress story; invalid formula/asset fallback never blanks whole document.

## Tests

- Golden corpus references every `_vmsh_examples` file; отдельный visual gate берёт три листка одного уровня и сравнивает PWA/Telegram/PDF derivatives, даже если print UI пока отложен.
- Parser unit tests per construct and diagnostic location.
- Characterization against selected `_external_pipelines` outputs with intentional diff report.
- Storage adapter contract: filesystem and mocked S3 implement same methods; retries/dedup/hash/collision.
- Telegram-rich sanitizer/limit fixtures; Bot API sending is not used in unit/E2E.
- PDF smoke plus visual pages for representative geometry/table examples.
- API publish/rollback concurrency, unauthorized Teacher, partial level failure and immutable revision.
- Storybook document/figure/upload/grid/problem-matching/diagnostic/preview/update-marker states and a11y.
- Playwright: upload example → fix missing asset → preview → publish n level → Student API sees it → rollback.

## Критерии приёмки

- Один сложный CP1251 example публикуется без ручного редактирования source/generated HTML; структурно изменённый example требует явного problem matching.
- Unknown/unsupported input останавливает publication с диагностикой, а не теряется.
- Повторный asset переиспользуется; отсутствующий явно запрашивается.
- Telegram preview и real renderer исходят из одной revision.
- Уровни публикуются и откатываются независимо; solution может отсутствовать.
- Source, compiler version и все derivatives воспроизводимы по revision ID.

## Пруфы завершения этапа

- [ ] Revision/migration/upgrade/rollback: `<sha/paths/results>`.
- [ ] Golden corpus report: `<path>`; CP1251/TikZ/table/assets cases `<result>`.
- [ ] External pipeline parity + intentional diffs: `<path>`.
- [ ] Demo upload/diagnostics/preview/publish/rollback: `<fixture/routes/video or screenshots>`.
- [ ] Storage filesystem/S3 contract tests: `<result>`.
- [ ] Contract fixtures and API tests: `<paths/result>`.
- [ ] Storybook stories, a11y and approved visuals: `<ids/paths>`.
- [ ] PDF and Telegram preview evidence: `<paths>`.
- [ ] Playwright 3 browsers: `<result>`.
- [ ] Docs/compiler support matrix/known limitations/acceptance: `<paths/issues/name/date>`.
