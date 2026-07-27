# Этап 2. LaTeX-контент, diagnostics, preview и публикация

## Результат

Admin загружает условие/подсказку/решение одного уровня или пакет урока, разрешает позиционные расхождения задач, получает diagnostics и missing-assets flow, проверяет PWA/Telegram preview и публикует либо планирует конкретную revision по уровню. Print-раздел откладывается во вторую версию.

Дизайн-контракт этапа: [математический документ, publication controls, diagnostics, metadata grid и Storybook stories](18-design-implementation-map.md#phase-2-design).

## Модель данных

Первая additive migration этого этапа:
[`0041.pwa_content_lessons.sql`](../../../migrations/0041.pwa_content_lessons.sql)
с точным rollback. Она не выполняет production backfill и не меняет legacy IDs.

Два следующих additive шага уже реализуют runtime-инварианты, не меняя эту
границу backfill: [`0042.pwa_content_concurrency.sql`](../../../migrations/0042.pwa_content_concurrency.sql)
фиксирует конкурентные source/publication transitions, а
[`0043.pwa_lesson_window_audit.sql`](../../../migrations/0043.pwa_lesson_window_audit.sql)
добавляет неизменяемый `lesson_window_changes` с actor, request ID и точными
before/after для обычного изменения расписания и отдельно подтверждаемого
изменения cutoff.

Таблицы: `course_lessons`, `group_lessons`, `course_schedule_rules`,
`group_schedule_overrides`, `content_sources`, `content_revisions`,
`media_assets`, `content_revision_assets`, `content_derivatives`,
`content_problem_matches`, `problem_revisions`, `problem_synonym_groups`,
`problem_synonym_members`, `lesson_windows`,
`lesson_window_schedule_sources`, `lesson_publications`, `hint_reveals`,
`solution_reveals`.

Legacy `lessons/problems` сохраняются. Compiler создаёт versioned representation и только после явной публикации обновляет совместимую projection/adapter, если это требуется Telegram. Source/publication принадлежат concrete `group_lesson`; Telegram destination разрешается через effective `telegram_bindings` (`group materials_target` заменяет course default, иначе наследует его), а token по-прежнему принадлежит runtime config.

Production migration не начинает историю с занятия 39. Для существующих занятий 1–38 текущего сезона отдельный dry-run/backfill создаёт минимальные source/revision/problem-match/publication/window records из legacy `lessons`/`problems`, файлового корпуса и утверждённого schedule mapping. Report показывает занятия/уровни без source, несовпадающее число задач и неизвестные фактические timestamps. Неизвестное время сохраняется как nullable/provenance, а не подменяется точным вымышленным значением.

## Compiler pipeline

1. Detect encoding (`CP1251`/UTF-8) и нормализовать в Unicode без изменения source hash record.
2. Parse LaTeX в canonical typed document AST; unknown macro даёт diagnostic с file/line/column.
3. Сопоставить задачи по порядку. Если число/структура пунктов изменились, остановить публикацию и показать ручное сопоставление с legacy `problems`; обязательного ID в LaTeX нет.
4. Content-address assets; TikZ → отдельный sanitized SVG; raster → WebP.
5. Сгенерировать web AST/HTML для client KaTeX, Telegram-rich dialect и PDF.
6. Проверить link/media/Telegram limits и sanitizer/CSP. Поддерживаемый корпус — KaTeX + конструкции исторического `a16_html_from_tex.py`.
7. Сохранить compiler version/hash. Recompile не меняет publication до явного действия.

Внешний toolchain берётся из общего backend config: `pdflatex_path='pdflatex'`, `pdf2svg_path='pdf2svg'`, `cwebp_path='cwebp'`, `magick_path='magick'`. Default names разрешаются через `PATH` service profile; absolute override допустим, но machine-specific path не является частью content revision. Перед compile worker проверяет требуемые capabilities и использует только безопасный argv-вызов без shell. Provenance сохраняет нормализованные tool versions вместе с compiler version.

Reference: `_external_pipelines/a16_html_from_tex.py`, `edt_tasks_parser.py`, `mathimg_*`, `a12`, `a14`, `a20`; production не импортирует их напрямую.

## Сопоставление задач и metadata review

- **MATCH-01.** Canonical identity строки — `(source_ordinal, source_item)` из
  exact compiler AST; если `source_item` в LaTeX отсутствует, используется
  строковое значение ordinal. Один полный batch обязан покрывать каждую
  canonical задачу ровно один раз. Частичные batch, повтор одного legacy
  `problem_id` и match за пределами concrete group lesson отклоняются до
  публикации.
- **MATCH-02.** `auto_position` разрешён только при совпадении ordinal;
  `manual_match` выбирает существующую задачу того же group lesson;
  `insert_new` создаёт минимальную legacy projection со статусом письменной
  задачи, которую всё равно нельзя опубликовать до review metadata; `omit`
  оставляет явную immutable запись без `problem_id`. Исправление уже
  подтверждённого batch выполняется новой source revision.
- **MATCH-03.** Готовая `content_revision` и строки review immutable. Поэтому
  optimistic review version равна `1 + count(content_problem_matches) +
  count(problem_revisions)` для exact revision. API выдаёт отдельный
  hash-derived review ETag, который нельзя перепутать с compile ETag. Полные
  batch вставляются одной `BEGIN IMMEDIATE` транзакцией; точный повтор уже
  сохранённого batch идемпотентен.
- **METADATA-01.** Metadata-grid относится к revision **условия** и подтверждает
  все её non-omitted match одной транзакцией. Каждая строка создаёт immutable
  `problem_revisions`, а legacy
  `problems` обновляется только как текущая Telegram-compatible projection.
  Все 23 исторических `ANS_TYPE` поддерживаются; test требует answer type,
  non-test не сохраняет скрытую test-конфигурацию. Пустой checker допустим и
  означает будущий `pending_configuration`, а не ложную успешную проверку.
- **METADATA-02.** Каждая revision условия, подсказки или решения проходит
  собственное structural matching: файлы и публикации независимы и parser не
  вправе молча считать их задачи совпавшими. При этом task/answer metadata
  принадлежит задаче занятия и не дублируется для подсказки или решения.
  Поэтому condition publication требует matching + metadata review, а
  hint/solution publication — matching соответствующей revision.
- До появления `problems.public_id` в Phase 3 Staff-only reconciliation wire
  использует legacy integer `problemId` только как candidate/mutation token.
  Он не попадает в Student/Family URL или payload; Phase 3 заменяет эту
  переходную Staff-границу opaque problem identity вместе с task-list API.

## Staff UI

- Routes: `staff/src/routes/lessons.*`, `problems.*`.
- Upload single/bulk; conditions and solutions separate; per-level selection.
- Diagnostics grouped by errors/warnings with source location and recovery action.
- Missing asset: search content-addressed library, upload replacement, reuse exact hash, rerun compile.
- LaTeX в браузере не редактируется. Metadata grid содержит название, task/answer type, validation/wrong/congratulation messages и optional topic tags; поддерживает keyboard edits, TSV paste preview, cell errors и optimistic version conflict.
- Structural output `a03_tempate_for_bot.py` не считается готовой metadata: до публикации **условия** admin явно просматривает `title`, `prob_type`, `ans_type`, `ans_validation`, `validation_error`, `cor_ans`, `cor_ans_checker`, `wrong_ans` и `congrat`. Заглушка или непроверенное parser default блокирует publish с полевым diagnostic. Подсказка и решение проходят собственное structural matching, но переиспользуют уже подтверждённую task metadata занятия.
- Title остаётся коротким UI-именем, но должен узнаваемо отличать задачу. Равное название разных групп одного `course_lesson` только предлагает synonym candidate; автоматический merge не выполняется, а другой course/lesson не рассматривается.
- Synonym suggestion from equal titles with explicit accept/reject.
- Side-by-side PWA and Telegram preview. Уже сгенерированный PDF derivative можно открыть для regression/контроля, но команд печати и отдельного print workflow в v1 нет.
- Publish/schedule/hide confirmation per level/kind. Отдельная версионируемая lesson-window form задаёт `opensAt`, `submissionClosesAt` и hint/solution schedule; изменение cutoff требует отдельного confirmation/audit по `SCHEDULE-01`, а schedule решения и фактический publish не переопределяют его молча. Hidden lesson исчезает из Student как неопубликованный; просмотревший старую revision получает индикатор обновления после новой публикации.
- Поле `datetime-local` передаёт серверу только локальное время минуты
  `scheduledLocalTime` и IANA `businessTimezone`, полученный из authoritative
  `group_lesson`. Browser timezone и `Date.parse()` не участвуют в расчёте:
  Python `zoneinfo` проверяет timezone, переводит wall time в UTC и отклоняет
  несуществующий либо неоднозначный DST-момент. В history/read response
  возвращаются абсолютный `scheduledAt` и тот же `businessTimezone`.
- После reload Staff может продолжить `uploaded` revision или повторить
  истёкший compile claim, выбирает для rollback только предыдущую `ready`
  revision и подтверждает publish/schedule/rollback/hide. На desktop PWA и
  Telegram previews стоят рядом, на узком экране складываются вертикально.

## Client renderer

- `packages/contracts/src/content.ts`: bounded Zod `WebContentDocument v1`; persisted/read revision ID обязателен, pre-persistence preview с `null` отделён собственной схемой. Python compiler projection и TypeScript parser используют общую fixture.
- Web figure создаётся только из полного типизированного asset descriptor:
  canonical public asset ID, SHA-256, root-relative либо credential-free HTTPS
  URL, поддерживаемый media type и целочисленные dimensions `1..20000`.
  Отдельные hash и URL не являются двумя источниками истины; конфликт descriptor
  с URL даёт diagnostic, а отсутствующий TikZ SVG остаётся blocking missing
  asset.
- `packages/content`: `SemanticMathDocument` — основной typed renderer; client KaTeX на main thread с `trust=false`, explicit `maxSize`/`maxExpand`, KaTeX font precache, tables/lists/subparts/callouts и локальным formula fallback.
- Legacy `MathHtml` использует fail-closed semantic allowlist и DOMPurify `DocumentFragment`: no raw `innerHTML`, inline SVG/style/forms/events/data URLs запрещены; любой удалённый/неподдерживаемый material блокирует всю производную.
- `ZoomableAssetFigure`: внешний SVG/raster asset, общий transform холста и изображения, pinch/pan mobile, keyboard `+/-/0` и buttons desktop, accessible alt/caption, missing/load-error state и reduced-motion.
- Одинаковые contracts/components используются Staff preview и будущим Student renderer; page/API wiring выполняется следующим вертикальным инкрементом.
- Long lesson stress story; invalid formula/asset fallback never blanks whole document.

## Tests

- Golden corpus references every `_vmsh_examples` file; отдельный visual gate берёт три листка одного уровня и сравнивает PWA/Telegram/PDF derivatives, даже если print UI пока отложен.
- Parser unit tests per construct and diagnostic location.
- Characterization against selected `_external_pipelines` outputs with intentional diff report.
- Storage adapter contract: filesystem and mocked S3 implement same methods; retries/dedup/hash/collision.
- Telegram-rich sanitizer/limit fixtures; Bot API sending is not used in unit/E2E.
- Opt-in live integration с `@vmsh179devbot`: verified test binding → private test channel, synthetic Rich Message boundary cases в пределах Telegram limits, сохранение returned binding/chat/message IDs. Это proof adapter/renderer, не общий Staff→Telegram channel publisher; classroom personal delivery тестируется своим contract в этапах 7/8.
- PDF smoke plus visual pages for representative geometry/table examples.
- Toolchain contract: default-name/absolute-path lookup, disabled/missing binary, version probe, timeout/non-zero exit/stderr truncation и отсутствие shell interpolation; local smoke для `pdflatex → pdf2svg` и raster → `cwebp`/`magick`, повторяемый на staging в этапе 11.
- API publish/rollback concurrency, unauthorized Teacher, partial level failure and immutable revision.
- Lesson-window API: stale `If-Match`, independent solution-schedule/cutoff edits, confirmation/audit и DST/UTC fixtures.
- Staff history bounded сервером до 250 revisions и 250 publications на вид
  материала; response всегда содержит authoritative `businessTimezone`.
- Historical season backfill: занятия 1–38 доступны в Student/Family history, повторный run идемпотентен, неизвестное время имеет provenance и не применяется как retroactive deadline.
- Storybook document/figure/upload/grid/problem-matching/diagnostic/preview/update-marker states and a11y.
- Playwright: upload example → fix missing asset → preview → publish n level → Student API sees it → rollback.

## Критерии приёмки

- Один сложный CP1251 example публикуется без ручного редактирования source/generated HTML; структурно изменённый example требует явного problem matching.
- Unknown/unsupported input останавливает publication с диагностикой, а не теряется.
- Повторный asset переиспользуется; отсутствующий явно запрашивается.
- Telegram preview и real renderer исходят из одной revision.
- Отсутствующий/unverified channel блокирует live send конкретной группы с diagnostic, но не compile/PWA publication; никакой fallback в чужой или глобальный канал не допускается.
- Уровни публикуются и откатываются независимо; solution может отсутствовать.
- Submission cutoff существует до фактической публикации solution, выводится абсолютным временем и меняется только отдельной версионируемой операцией по правилу `SCHEDULE-01`.
- Source, compiler version и все derivatives воспроизводимы по revision ID.
- Отсутствующая обязательная утилита обнаруживается readiness/preflight до compile; diagnostic называет capability и config field, но публичный response не раскрывает полный server path.

## Пруфы завершения этапа

Browser renderer increment реализован, но сам этап 2 не закрыт: [`phase2-web-renderer.md`](../../../pwa_tests/reports/phase2-web-renderer.md).

Промежуточный gate **Phase 2A — schema/domain/repository** закрыт 27 июля 2026:

- [x] Additive migration и точный up/down/up без legacy backfill;
- [x] connection-per-operation repository и pure domain invariants;
- [x] versioned schedule rules/overrides и immutable per-field materialization snapshot;
- [x] append-only source/problem/synonym/publication/reveal lineage;
- [x] focused tests, schema inventory и подробный
      [proof report](../../../pwa_tests/reports/phase2-content-schema.md).

Сам Phase 2A не завершал весь этап 2: compiler/renderers/converters, HTTP/UI и
безопасный backfill tool закрыты следующими gate, а production backfill apply и
полная product acceptance остаются ниже незакрытыми.

Промежуточный gate **Phase 2B — pure compiler/renderers/converters** закрыт
27 июля 2026 без подключения DB, S3, Telegram или HTTP side effects:

- [x] bounded UTF-8/CP1251 scanner, typed AST, role isolation и positional diagnostics;
- [x] строгий [`WebContentDocument v1`](../../packages/contracts/src/content.ts)
      с общей Python/Zod
      [fixture](../../packages/contracts/fixtures/content/python-compiler-preview.v1.json);
- [x] client-KaTeX web projection и Bot API 10.2 Rich HTML renderer/validator;
- [x] TikZ→sanitized SVG и raster/HEIC→1920 px WebP converter boundary с
      fixed argv, isolated temp files, timeout и redacted failures;
- [x] unit-tested
      [`ContentAssetService`](../../../helpers/pwa/content/asset_service.py):
      converter → shared ObjectStorage → repository attachment, 5/5 PASS;
- [x] 30/30 TeX sources и 334 problem nodes без compiler errors в
      [golden report](../../../pwa_tests/reports/phase2-content-compiler.md);
- [x] [support matrix и известные ограничения](../../docs/content-compiler-support-matrix.md).

Этот gate сам по себе не означает публикацию контента. Позднейшие изолированные
proof закрыли live S3 content-asset roundtrip, live Telegram Rich lifecycle,
safe historical backfill tooling и authenticated HTTP/frontend orchestration.
Production owner-reviewed backfill apply, problem-matching/metadata flow,
открытие сохранённого PDF через Staff и browser E2E пока остаются открыты.

Промежуточный gate **Phase 2C — authenticated HTTP и audience frontend**
зафиксирован 28 июля 2026 в revisions [`1aad776`](../../../pwa_tests/reports/phase2-content-api.md)
и [`866e3fe`](../../../pwa_tests/reports/phase2-content-frontend.md):

- [x] настоящие aiohttp Staff/Student/Family endpoints поверх общей SQLite,
      session/capability/scope checks и owner-scoped invalidation;
- [x] compile lease/retry, atomic derivatives, independent publication slots,
      scheduler, cancel/hide и rollback только на выбранную `ready` revision;
- [x] publish/schedule/rollback fail-closed до resolved problem matches;
      condition дополнительно требует reviewed problem metadata, а solution —
      отдельного `submission_closes_at`;
- [x] server-authoritative IANA wall-time conversion, immutable audit migration
      `0043` и bounded history;
- [x] Staff resume/preview/confirmation flow, side-by-side desktop preview,
      Student/Family published reads и update marker;
- [x] полный checkpoint: `make pwa-lint`, `make pwa-typecheck`,
      `make pwa-storybook-test`, `make pwa-build` и `make pwa-schema-check` PASS;
      `make pwa-test` — 218 TypeScript и 1028 Python PASS, 3 skip, 1 warning;
      Storybook browser mode — 167 PASS; schema inventory — 192 product objects;
      production-build auth regression — 60/60 PASS в трёх браузерах (это не
      content E2E).

Следующий промежуточный gate **Phase 2D — asset recovery и durable media**
зафиксирован 28 июля 2026 в revisions `43b0323`, `08a8d0b` и `d39141d`:

- [x] versioned/idempotent Staff asset inventory/upload, строгий `If-Match`,
      raster→WebP, sanitized SVG, server-side TikZ→SVG и typed descriptors;
- [x] immutable filesystem media route, прямые public S3 URL, nginx/E2E/Vite
      proxy и двухнедельная Student/Family Workbox policy;
- [x] Staff missing-assets recovery с сохранением выбранного файла при сбое,
      `409` refresh, recompile и interaction stories;
- [x] provider-first PDF persistence с hash/provenance, exact retry и
      concurrent conflict checks; Staff preview/download ещё не подключён;
- [x] 302 Python asset regression, 10 PDF persistence, 21 frontend unit и 17
      Storybook browser tests, Ruff/ESLint/strict TypeScript и production build
      трёх apps — PASS.

Полный [proof Phase 2D](../../../pwa_tests/reports/phase2-content-assets-http.md)
не закрывает Phase 2 целиком. Открыты problem matching/metadata UI+API,
Staff-openable generated PDF, bulk upload, production-build content E2E и
ручное visual approval владельца. Snapshots не обновлялись.

Промежуточный backend gate **Phase 2E — problem matching и metadata review**
реализован 28 июля 2026:

- [x] полный positional/manual/insert/omit batch с group-lesson scope и
      атомарным rollback;
- [x] отдельный review ETag, stale conflict и идемпотентный exact retry;
- [x] полная metadata-grid mutation, immutable problem revision и обновление
      legacy projection;
- [x] admin-only aiohttp endpoints, Teacher `403`; condition publication
      fail-closed до обоих review шагов, hint/solution — до matching;
- [x] 111 domain/repository/real-aiohttp tests и Ruff PASS.

Frontend contracts, Staff workflow, Storybook interaction/visual gate и
production-build content E2E остаются продолжением Phase 2E; backend proof:
[`phase2-problem-review-api.md`](../../../pwa_tests/reports/phase2-problem-review-api.md).

Contract/client increment Phase 2E также реализован 28 июля 2026:

- [x] bounded strict Zod schemas, все 23 historical answer types и cross-field
      task/answer validation;
- [x] full-batch match/metadata request validation, unique identities и
      Staff-only transitional legacy problem ID;
- [x] authenticated GET/PUT client, exact `If-Match`, body/header ETag check и
      стабильные TanStack Query keys/hooks;
- [x] два strict TypeScript package check, ESLint и 24 unit tests PASS.

На contract/client checkpoint production Staff UI, Storybook interaction/
visual gate и production-build content E2E ещё оставались открыты. Contract proof:
[`phase2-problem-review-frontend.md`](../../../pwa_tests/reports/phase2-problem-review-frontend.md).

Production Staff UI increment Phase 2E реализован 28 июля 2026:

- [x] controlled `ProblemMatching` и real-client adapter с full-batch
      positional/manual/new/omit flow;
- [x] condition-only metadata grid со всеми task/answer/config fields;
- [x] publication gate следует фактически подтверждённому matching/metadata;
- [x] matching и metadata drafts переживают remount/reload в Staff-namespaced
      `localStorage`, а `409` не уничтожает локальную работу;
- [x] strict TypeScript/ESLint, 24 contract/client unit tests, 14 targeted
      Storybook browser tests и Staff production build PASS.

Production-build content E2E и owner visual approval остаются открыты. UI
proof и точные story IDs:
[`phase2-problem-review-ui.md`](../../../pwa_tests/reports/phase2-problem-review-ui.md).

- [x] Revision/migration/upgrade/rollback для Phase 2A:
      [`0041`](../../../migrations/0041.pwa_content_lessons.sql), 48 focused PASS,
      69 PASS вместе со schema inventory; full Phase-2 migration/backfill proof ещё
      не закрыт.
- [x] Golden corpus/compiler report:
      [`phase2-content-compiler.md`](../../../pwa_tests/reports/phase2-content-compiler.md);
      CP1251/TikZ/table/assets и 30/30 TeX sources покрыты pure tests.
- [ ] External pipeline parity + intentional diffs: `<path>`.
- [ ] TeX → structural task skeleton → reviewed metadata report: placeholders rejected, every field has provenance/revision, compact titles reviewed and equal-title candidates require explicit admin decision `<path/result>`.
- [x] Safe lessons 1–38 backfill CLI, deterministic preview, synthetic
      apply/repeat и provenance:
      [`phase2-content-history-backfill.md`](../../../pwa_tests/reports/phase2-content-history-backfill.md).
- [ ] Production owner-reviewed mapping/rehearsal/apply на отдельной
      анонимизированной migrated copy: `<private result>`.
- [ ] Demo upload/diagnostics/preview/publish/rollback: `<fixture/routes/video or screenshots>`.
- [x] Storage filesystem/S3 contract и разрешённый synthetic TikZ/SVG +
      raster/WebP live roundtrip с private read, public GET и cleanup:
      [`phase2-content-assets-live.md`](../../../pwa_tests/reports/phase2-content-assets-live.md),
      13 hermetic PASS + 1 real converter PASS + 2/2 live objects PASS/deleted.
- [x] Authenticated revision asset API, Staff recovery UI, immutable local
      route, PWA cache/proxy и durable PDF storage boundary:
      [`phase2-content-assets-http.md`](../../../pwa_tests/reports/phase2-content-assets-http.md),
      revisions `43b0323`, `08a8d0b`, `d39141d`.
- [x] Contract fixtures and authenticated API tests:
      [`phase2-content-api.md`](../../../pwa_tests/reports/phase2-content-api.md) и
      [`phase2-content-frontend.md`](../../../pwa_tests/reports/phase2-content-frontend.md).
- [ ] Storybook stories и a11y automated (**167 PASS**); owner-approved visuals
      ещё не получены, snapshots не обновлялись:
      [`phase2-content-frontend.md`](../../../pwa_tests/reports/phase2-content-frontend.md).
- [x] Real-corpus Storybook increment: условия начинающих 39–41 связаны с
      exact source/PDF hashes, typed PWA и Telegram derivatives; 1/1 browser story,
      mobile 390 px reflow и ручной desktop/mobile light осмотр прошли. Owner visual
      approval и snapshots остаются в предыдущем незакрытом пункте:
      [`phase2-real-content-corpus.md`](../../../pwa_tests/reports/phase2-real-content-corpus.md).
- [ ] Staff-openable persisted PDF and combined PDF/Telegram preview evidence:
      `<paths>` (storage boundary реализован в `d39141d`).
- [x] RecordingBot fixtures и разрешённый live test-channel Rich Message на
      границе 32 768 symbols: send/edit/delete PASS,
      [`phase2-derivative-adapters.md`](../../../pwa_tests/reports/phase2-derivative-adapters.md).
- [ ] Toolchain config/probe и версии `pdflatex`/`pdf2svg`/`cwebp`/`magick` в local target runtime; staging gate относится к этапу 11: `<path/result>`.
- [ ] Production-build content Playwright в трёх браузерах: `<result>`.
- [x] Pure compiler support matrix/known limitations:
      [`content-compiler-support-matrix.md`](../../docs/content-compiler-support-matrix.md),
      принято как Phase 2B engineering gate 27 июля 2026; product acceptance всего
      этапа остаётся открытым.

## Многокурсовый инкремент Phase 2

Ввести `course_lesson` по `(course_id, lesson_number)` и независимые `group_lesson`. Course schedule rules и group overrides материализуют concrete windows; позднее изменение шаблона требует impact preview/confirm. Condition, hint и solution имеют отдельные group-scoped publish/rollback state и LaTeX revisions.

Дополнительный proof: две группы одного номера с разными source/schedule; отсутствующий номер у третьей группы; snapshot stability; независимые publication actions; stories `Product/Staff-admin--independent-schedules` и `Pages/Staff--course-and-group-administration`.
