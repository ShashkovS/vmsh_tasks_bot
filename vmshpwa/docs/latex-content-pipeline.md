# LaTeX и content pipeline

## Единственный источник

Условие, подсказка и решение хранятся как версионируемый LaTeX source. Безопасный HTML для web, Telegram Rich Message HTML, SVG/WebP для рисунков и PDF для печати — воспроизводимые производные конкретной версии source и toolchain. Ручное редактирование производного HTML/PDF запрещено.

Новый parser/converter использует опыт `_external_pipelines/a16_html_from_tex.py` и `edt_tasks_parser.py`, но не копирует их как непрозрачный скрипт. LaTeX сначала превращается в нормализованное document representation с явными math/asset/list/table nodes, а затем — в channel-specific output.

## Web и Telegram renderers

Web HTML сохраняет исходные LaTeX expressions в безопасных math nodes. KaTeX работает на клиенте с HTML+MathML output; его CSS и fonts собираются Vite и входят в precache Student/Family. Текущий полный набор увеличивает precache примерно до 1.4 MiB; после стабилизации корпуса нужно оставить необходимые web-форматы/subsets с regression-набором реальных формул. Выделение/copy helper и интерактивное меню формул отключены, но assistive semantics не удаляются.

Production browser boundary — Zod-first [`WebContentDocument v1`](../packages/contracts/src/content.ts), а не внутренний Python AST и не строка `web_html`. Deterministic adapter выбирает ровно один `materialKind` (`condition|hint|solution`), поэтому condition payload структурно не содержит соседние hint/solution/answer branches. Pre-persistence compiler preview имеет отдельную схему со строго `revisionId: null`; persisted/read payload требует непустой opaque `revisionId`. До recursive parsing контракт ограничивает JSON depth, block depth, число nodes и общий объём текста. Python↔TypeScript parity закреплена общей fixture [`python-compiler-preview.v1.json`](../packages/contracts/fixtures/content/python-compiler-preview.v1.json).

Основной browser renderer — [`SemanticMathDocument`](../packages/content/src/math-document.tsx). Compatibility [`MathHtml`](../packages/content/src/index.tsx) принимает только явный semantic HTML allowlist: неподдерживаемый tag/attribute, event handler, inline style/SVG/form или запрещённый URL отклоняет всю производную, а не показывает безопасно выглядящий остаток. Sanitizer возвращает `DocumentFragment`, поэтому приложение не создаёт raw-string `innerHTML` sink и совместимо с Trusted Types policy DOMPurify. KaTeX запускается на main thread с `trust: false`, bounded `maxSize`/`maxExpand`; ошибка одной формулы оставляет детерминированный текстовый fallback и не скрывает документ.

Telegram renderer создаёт HTML для проверенного 27 июля 2026 dialect [Bot API 10.2](https://core.telegram.org/bots/api) `sendRichMessage`: inline math становится `<tg-math>`, display math — `<tg-math-block>`, а headings, lists, tables, details, quotations и media проходят строгий Telegram allowlist. Это отдельный dialect и не передаётся в legacy `sendMessage(parse_mode=HTML)`. Named/numeric entities, children структурных tags, nesting, URL/attribute ranges и custom-emoji `<img>` проверяются до send; обычные media остаются отдельными blocks. Pipeline проверяет актуальные limits до публикации: не более 32 768 UTF-8 characters, 500 blocks, 16 уровней вложенности, 50 media и 20 table columns. Bot API 10.2 отдельно поддерживает `InputRichMessage.media`; media blocks принимают только HTTP(S), а formula source передаётся как raw LaTeX. Версия dialect и применённые limits входят в provenance и regression corpus, чтобы следующее изменение Bot API не стало молчаливым изменением renderer.

Основной browser wire — versioned typed `WebContentDocument`, а не внутренний compiler AST и не сгенерированный HTML. Compiler выбирает ровно один `materialKind`, поэтому condition payload физически не содержит hint/answer/solution siblings. Pre-persistence preview допускает `revisionId: null`; public read contract требует канонический revision ID. HTML renderer остаётся диагностической производной, а Student/Family рендерят Zod-проверенный документ через client KaTeX. Реализованная матрица и оставшиеся integration gates перечислены в [матрице поддержки compiler](content-compiler-support-matrix.md).

## Загрузка урока

Материалы разделены по уровню. Условия и решения загружаются отдельными файлами, по одному или массовым набором; решения могут появиться позже. Импорт проходит стадии:

1. upload и content hash;
2. parse/normalize без публикации;
3. поиск команд, задач, подпунктов, ссылок и assets;
4. diagnostics с точной позицией и severity;
5. сопоставление недостающих изображений;
6. generation preview: web и Telegram; PDF derivative проверяется regression-тестом, а print UI относится ко второй версии;
7. редактирование метаданных;
8. approval и атомарная публикация выбранного уровня;
9. immutable version/audit и возможность rollback.

Два preview обязательны до публикации: Student web с настоящим client KaTeX и Telegram Rich Message/media. Print/admin pipeline сознательно перенесён во вторую версию; до него три листка одного уровня из `_vmsh_examples` всё равно сравниваются в PWA, Telegram и PDF.

## Задачи и метаданные

Обязательного ID в LaTeX нет. Parser получает задачи и решения по порядку и сопоставляет их с legacy `problems`; изменение числа/структуры требует отдельного Staff reconciliation до publication. Внутренний problem record содержит lesson, level, ordinal/item, title, kind, answer input type и checker configuration. Одинаковое название создаёт кандидата synonym-group, который подтверждает admin.

LaTeX в Staff не редактируется. Metadata grid содержит название, task type, answer type, validation/wrong/congratulation messages и optional topic tags; поддерживает keyboard navigation и batch table upload. Ошибочные строки импорта пропускаются и попадают в явный report.

Все исторические форматы ответов сохраняются. Invalid-format не расходует attempt, после правильного ответа можно отправлять снова, а все ответы остаются в истории. `cor_ans_checker` редактируется trusted admin; тестовые examples желательны, но не блокируют publication. Пока checker не настроен, ответ получает pending status и позже проходит admin `problem_recheck`.

### Семантика legacy-метаданных, которую нельзя потерять

`_external_pipelines/a03_tempate_for_bot.py` извлекает из TeX только структурный каркас с заглушками. После него оператор осознанно заполняет следующие поля; новый compiler/grid не должен выдавать заглушку за проверенную metadata:

- `title` — короткий, но достаточно узнаваемый идентификатор задачи в кнопках/списках. Исторически разные задачи одного занятия получали разные названия, а совпадающие задачи разных уровней — одинаковое, что запускало title-based synonym projection.
- В целевой многокурсовой модели равный `title` лишь создаёт кандидата внутри одного `course_lesson`; admin подтверждает merge. Другой курс/номер занятия не склеивается. Данные submission/result/thread всегда остаются у concrete `problem_id`, поэтому ошибочный merge обратим.
- `prob_type` определяет тестовую, письменную или устную задачу. Исторический `Письменно<-Устно` мигрирует в canonical oral с доступной письменной сдачей.
- `ans_type` выбирает normalization/checker ответа. Пустой `ans_validation` использует regex исторического типа; непустой переопределяет его и применяется к `student_answer.strip()` через `fullmatch`. Для `SELECT_ONE` это не regex, а разделённый `;` список видимых вариантов; бот/PWA хранит и передаёт сам label, без скрытого value.
- `validation_error` объясняет не верность, а ожидаемый формат. Он по возможности называет искомую величину/порядок чисел и даёт пример, чтобы школьник сразу заметил и неверный формат, и промах по номеру задачи.
- `cor_ans` хранит один или несколько правильных ответов, разделённых `;`; перечисление даже десятков допустимых ответов является поддерживаемым legacy-сценарием. Поле никогда не попадает в Student/Family payload.
- `cor_ans_checker` — optional trusted-admin Python checker для нестандартной проверки. Фактическая legacy-граница находится в [`handlers/student_handlers.py`](../../handlers/student_handlers.py): `is_py_func` выбирает строки с начальным `def`, `run_py_func_checker` исполняет весь текст с `GLOBALS_FOR_TEST_FUNCTION_CREATION`, кеширует callable по точной строке кода и ожидает пару `(bool, optional message)`. Ограниченный набор globals/builtins является лишь наблюдаемым compatibility contract, а не надёжной sandbox-границей. До замены обязателен синтетический positive/negative characterization corpus для выбора checker, доступных имён, compile/call/result-shape ошибок и кеширования; реальные production checker strings в committed fixtures не копируются. Каждая новая ревизия, diff, ошибка выполнения и recheck аудируются. Это не teacher-интерфейс и не production sandbox для произвольного кода.
- `wrong_ans` показывается, когда формат верен, но ответ неверен; `congrat` — когда ответ правилен. Оба текста могут быть спокойными default-фразами либо уточнять контекст конкретной задачи.

Все эти поля версионируются вместе с concrete problem revision. Смена названия, checker или synonym membership не переписывает исторические attempts/results.

## Assets

Библиотека content-addressed: binary hash определяет object key, одинаковые assets переиспользуются. Source хранит логическое имя и связь с hash. Pipeline предлагает match по имени/hash/preview; недостающие assets показывает отдельным blocking списком и никогда не заменяет пустой картинкой.

Pure compiler принимает known asset не как раздельные `hash + URL`, а как
единый строгий `WebAssetDescriptor`: canonical public ID, SHA-256,
root-relative либо credential-free HTTPS `src`, поддерживаемый media type и
целочисленные dimensions `1..20000`. Descriptor сначала проходит Python
validation, затем тот же shape проверяет Zod. Конфликт отдельно переданного URL
с descriptor даёт diagnostic; сгенерированный TikZ без опубликованного SVG
descriptor остаётся `asset.missing` и блокирует публикацию.

TikZ компилируется контролируемым toolchain в отдельный SVG object в S3 и подходящие print/Telegram производные. SVG не инлайнится в HTML. Для каждого рисунка сохраняются alt/описание, dimensions и provenance. Zoomable figure открывает изображение без потери доступной подписи. Реализация наследует проверенные операции `mathimg_service.py`: content hash, `pdflatex`, PDF→SVG и S3 upload.

Browser [`ZoomableAssetFigure`](../packages/content/src/zoomable-asset-figure.tsx) загружает только root-relative либо credential-free HTTPS SVG/raster URL. Рамка-холст и изображение имеют единый transform; `+`, `−`, `0`, кнопки, pinch и pan меняют только локальный viewer state. Missing/error asset сохраняет alt и caption в явном fallback; исходный SVG никогда не инлайнится в DOM.

## Конфигурация внешнего toolchain

Converter binaries являются зависимостями существующего backend, а не отдельным сервисом. Канонические поля общего Python config:

```python
pdf2svg_path: Optional[str] = "pdf2svg"
cwebp_path: Optional[str] = "cwebp"
pdflatex_path: Optional[str] = "pdflatex"
magick_path: Optional[str] = "magick"
```

Значение по умолчанию ищется в `PATH` того профиля, под которым запущены gunicorn/worker/локальный процесс. Поэтому Homebrew paths и пользовательский wrapper `pdflatex` могут использоваться локально без появления абсолютных путей в репозитории; на сервере те же имена разрешаются его service profile. При необходимости deployment может задать абсолютный executable path. `None` означает сознательно отключённую capability, а не автоматический fallback на shell.

Каждое поле содержит только имя/путь executable. Вызов выполняется без shell, с фиксированными argv flags, isolated temporary directory, timeout/resource bounds и ограниченным stderr. Startup/readiness probe проверяет наличие, executable bit и capability/version; включённый pipeline с отсутствующей обязательной утилитой fail-fast до пользовательского compile/upload. В provenance derivative сохраняются compiler version и нормализованные версии использованных tools, но публичный diagnostic не раскрывает абсолютный server path.

Реализация этого контракта находится в `helpers/pwa/toolchain.py`, а redacted preflight и реальный synthetic smoke — в `vmshpwa/scripts/toolchain_{preflight,smoke}.py`. Выбор executable следует актуальному поведению [`shutil.which`](https://docs.python.org/3.14/library/shutil.html#shutil.which). Процессы запускаются через [`asyncio.create_subprocess_exec`](https://docs.python.org/3.14/library/asyncio-subprocess.html#asyncio.create_subprocess_exec), читаются через `communicate()` и ограничиваются внешним timeout, как требует Python 3.14 API; при timeout завершается отдельная process group. Smoke всегда передаёт LaTeX `-no-shell-escape` и проверяет сигнатуры полученных PDF, SVG, PNG и WebP, а не только exit code.

## Версии и откат

Публикация может быть scheduled и выполняется независимо по уровню/типу. Student, который открывал прежнее условие, видит заметный update marker; teacher review показывает последнюю опубликованную версию. Скрытие занятия убирает его из Student UI как неопубликованное. Старый публичный сайт пока обновляется внешними скриптами и не входит в этот pipeline.

`datetime-local` не содержит timezone, поэтому browser не преобразует его через
свою локальную зону. Staff отправляет `scheduledLocalTime` (`YYYY-MM-DDTHH:mm`)
и authoritative IANA `businessTimezone` группового занятия. Сервер сверяет зону,
разрешает wall time через Python `zoneinfo`, отклоняет DST gap/fold и хранит UTC.
Read/history возвращают абсолютный `scheduledAt` и `businessTimezone`.

Успешная компиляция (`ready`) сама по себе недостаточна для публикации.
Publish/schedule/rollback требуют полного resolved positional matching и
reviewed problem metadata; solution дополнительно требует существующий
`submission_closes_at`. Изменение cutoff — отдельная optimistic operation с
явным подтверждением и append-only `lesson_window_changes`; schedule решения
не меняет deadline.

## Владение материалами групп

LaTeX source revision и все производные принадлежат конкретному `group_lesson`. Одинаковый номер занятия внутри курса создаёт общий `course_lesson`, но не переиспользует source/publish state другой группы. Course schedule даёт только шаблон дат; публикация condition, hint и solution выполняется независимо по группе. Совпадение названий задач создаёт лишь кандидата synonym-group, который подтверждает admin. См. [многокурсовую модель](courses-groups-and-lessons.md).

## Состояние реализации на 28 июля 2026

Revisions `1aad776` и `866e3fe` фиксируют authenticated aiohttp + frontend
vertical: upload/compile retry, diagnostics, typed PWA/Telegram preview,
independent publication/schedule/cancel/hide/rollback, bounded history,
Student/Family published reads и update marker. Полный checkpoint:
lint/typecheck/build/schema PASS, 218 TypeScript и 1028 Python tests PASS (3
skip, 1 warning), 167 Storybook browser tests PASS, 192 schema objects.

Этап 2 ещё не завершён. Не реализованы HTTP asset upload/resolution и
missing-assets recovery, problem matching/metadata mutation UI/API,
stored/openable generated PDF, bulk upload, production-build content E2E и
owner visual approval. Актуальные proofs:
[`phase2-content-api.md`](../../pwa_tests/reports/phase2-content-api.md) и
[`phase2-content-frontend.md`](../../pwa_tests/reports/phase2-content-frontend.md).
