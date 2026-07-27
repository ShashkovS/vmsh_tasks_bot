# Фаза 4. Product components и layout patterns

Product components живут вне нейтральных primitives — преимущественно в `packages/app-shell`, `packages/content` или новом явно названном shared product package после согласования. Каждый компонент принимает data/view-model и callbacks, не делает скрытый fetch.

## Математический документ

`MathDocument` покрывает заголовок, вводный текст, условие, подпункты, theorem-like callouts, numbered/unnumbered display math, inline math, широкую таблицу, code-like answer format, TikZ/SVG и подпись. Требования:

- reading serif только в документе, UI controls остаются sans;
- формула не обрезается: wrap where valid, otherwise локальный horizontal scroll с affordance;
- номера формул и anchor/deep link;
- обычный текст документа читается и копируется без потери смысла; для формул не добавляются отдельные copy menu, selection helper или другие необязательные интерактивные функции;
- zoomable figure с keyboard zoom/reset, caption и alt;
- print preview не подменяет web renderer.

## Task experience

- ProblemHeader/ProblemStatus: номер, уровень, вид сдачи, deadline, текущий результат и history link.
- TaskTypeIndicator: registry-driven `TEST`, `WRITTEN`, `ORALLY`; технический `WRITTEN_BEFORE_ORALLY` школьнику всегда представлен как oral. **Любую устную задачу можно сдать письменно** (интерфейс письменной сдачи), а данные подключения к Zoom доступны по tap; во время oral window доступны оба пути. Иконка имеет accessible name и объяснение способа сдачи по tap/focus.
- TaskListItem и long worksheet navigation: номер+иконка, status, title, anchor, фильтр статусов, отличие `not-started` от `opened-not-submitted`, progress summary без рейтинга. Полный листок сортируется по номеру; attention order используется только на «Сейчас».
- HintDisclosure/SolutionDisclosure: недоступное скрыто; одна подсказка; и подсказка, и решение требуют подтверждения осознанного раскрытия; already-viewed state и методическое событие просмотра, корректный deep link.
- DeadlineNotice: абсолютное время + понятная относительная фраза; closed/queued-before-deadline/conflict cases.
- VerdictMark/VerdictRegistry: course-configurable binary/ternary/full scale; symbol, owner-approved decoder, numeric weight и отдельный semantic color. Частичный результат называется «Частично»; `REJECTED_ANSWER` имеет admin-detail «Отклонено после перепроверки».
- AttemptTimeline: последний verdict сразу, раскрываемая история test attempts, submissions, verdict corrections, edits и пересдач без обязательного искусственного номера попытки и обвинительного языка.
- FeedbackAttention/ReactionPicker: unread feedback заметен без push; Student reactions скрыты от teacher, teacher internal reactions скрыты от Student/Family, admin видит обе стороны согласно permission contract. На один verdict доступна одна реакция каждого разрешённого actor type; её можно заменить или удалить в течение часа. В быстром teacher-flow emoji не заменяет формулировку: точный текст реакции остаётся видимым в маленьком компактном chip; `⌘/Ctrl + Alt + 1…4` выбирает или снимает internal reaction, не покидая поле комментария.
- GroupReviewCallout: спокойная плашка группового разбора с временем, conference ID/code и устойчивым join action.

## Test answer inputs

Компонент выбирается по contract, а не эвристике JSX. Покрыть все 23 значения текущего `helpers.consts.ANS_TYPE` и их format fixtures, без generic fallback для известного типа. Клиент зеркалит только форматную часть `helpers/checkers.py`: `student_answer.strip()` и `fullmatch` по явному `ans_validation` либо текущему `ANS_REGEX`; server остаётся авторитетом. Expected format виден сразу, но ошибка появляется только после выхода из целого control или явной попытки отправки: первый заполненный слот fixed tuple, незаконченная смешанная дробь, дата или время не должны краснеть во время набора. День недели выбирается семью короткими кнопками `пн–вс` в одну строку и отправляет видимую подпись. Для fixed tuple не показывать лишнее «Отправится»; для sequence/set допустим только блок «Распознано» после успешного реального parsing. `SELECT_ONE` отправляет ровно показанный русский текст option, без скрытого `odd`/внутреннего значения. Invalid-format ответ сохраняется, но не расходует попытку. Состояния: untouched, partial/focused, invalid-after-blur, invalid-after-submit, checking, pending checker configuration, correct, incorrect, rate-limited, closed, corrected checker/re-evaluated.

Implementation anchors: [`TestAnswer`](../../packages/product/src/test-answer.tsx), [`AnswerSpec`](../../packages/product/src/answer-spec.ts), [`answer-validation.ts`](../../packages/product/src/answer-validation.ts) и stories [`Product/Test answer`](../../packages/product/src/test-answer.stories.tsx).

## Письменная сдача

Composer поддерживает текст и до 10 фотографий:

- выбрать camera/files, доступное объяснение типов и лимита;
- per-file preprocessing progress worker-а;
- thumbnail, full preview, удаление и **изменение порядка кнопками вверх/вниз** (без DnD-зависимости, доступно с клавиатуры); удаление и повторная загрузка — запасной путь для типового 1–2 фото;
- rotate/remove/retry, upload progress, общий payload size;
- draft autosave, offline queue и duplicate/idempotency handling;
- final review порядка страниц до отправки;
- после успешной отправки — короткий обычный status в треде; отдельной «квитанции», reference number и доказательного экрана нет.

До первого review lock ученик может изменить или удалить исходную отправку с подтверждением. После начала проверки он добавляет новый материал отдельной записью; reviewer обязан увидеть его до завершения verdict. В момент завершения проверки evidence фиксируется навсегда. Teacher annotation — отдельный неизменяемый после отправки overlay: карандаш, ластик, поворот, масштабирование, 4–5 основных цветов и page navigation. FeedbackThread показывает автора/время/канал и позволяет дослать ответ или пересдать без потери истории.

Human feedback и AI feedback имеют разные author/provenance components, accessible labels и tokens. Даже в режиме AI-verdict школьник не должен принять AI за живого преподавателя; complaint/escalation ведёт к human review.

## Новости

TelegramRichPost отображает полный allowlisted Telegram Rich Message: headings, paragraphs, emphasis/mark/sub/sup/spoiler, links, lists, quotes, code, details, tables, divider, albums, media placeholders, source attribution и math extension. Новые условия задач публикуются в Telegram полноценным текстом, а не скриншотом; рисунки остаются отдельными media/SVG. Нужны card/list, detail и два editor preview: PWA и Telegram. Различать source revision, local editorial override, hidden/source-deleted и delivery error. Исторический corpus для stories — `_external_pipelines/ChatExport_2026-07-25`.

## Connectivity

ConnectionBanner/SyncIndicator/UpdatePrompt/PushPermissionCard:

- online не занимает постоянное заметное место;
- reconnecting/offline сообщают влияние на конкретное действие;
- queued count ведёт в outbox details;
- conflict/failed требует решения, не исчезает toast-ом;
- update prompt не уничтожает draft;
- push permission объясняет категории до browser prompt и уважает отказ.

DraftPersistence — не отдельная декоративная карточка, а общий поведенческий контракт Student/Staff composers и editors. Компонент показывает `сохранено локально`, восстановление после reload, конфликт base version, успешную серверную фиксацию и явный discard. Текст/UI-state сохраняются в `localStorage`, blobs/outbox — в Dexie; update prompt, route change и accidental reload не очищают draft.

## Staff data work

- DenseDataTable: sticky headers, resize/visibility, sort/filter, row selection, keyboard traversal;
- MetadataGrid: cell edit, TSV copy/paste, dry-run errors, bulk actions, undo boundary; отдельные колонки task type (`test|written|oral`) и answer type, обе с dropdown editor, который принимает табличную вставку как обычная spreadsheet-ячейка;
- ReviewQueue: основной вход по `synonyms`, счётчик и возраст очереди; list mode и fast one-at-a-time mode; sort по задаче, ожиданию, группе и ученику; полное название и recheck already-reviewed action;
- ReviewLock: текущая атомарная 30-минутная lease; занятая работа остаётся видна с именем проверяющего и disabled action; lost lock блокирует устаревший verdict и требует refetch;
- ReviewWorkspace: компактная queue и единая хронологическая основная колонка `immutable evidence → существующее обсуждение → новый teacher reply + verdict`. Это не три независимые панели: комментарий преподавателя добавляется в конец реальной переписки. Verdict actions строятся из course registry, идут от лучшего к худшему, доступны маленькими подписанными кнопками и digits (`1` всегда `+`); shortcuts не работают в editable fields и имеют видимую legend;
- ReviewCommentGuard: для любого verdict кроме «Зачтено» без комментария спрашивает подтверждение, но не запрещает отправку; «Зачтено» без комментария сохраняет и листает дальше; abandon освобождает lock и переходит дальше без обязательной причины, а локальный unsent draft не теряется;
- ReviewReaction: одна staff-only internal reaction на verdict, недоступная Student/Family API/view-model, с заменой/удалением в течение часа; compact controls имеют видимую Mod+Alt shortcut legend;
- LaTeXUpload: file/batch progress, diagnostics, source preview, derived previews;
- MissingAssetsFlow: exact missing refs, match candidates, upload/reuse, blocking resolution;
- PublicationControl: три независимые per-group-lesson операции — условие, подсказка и решение. Для каждой явно видны state, «сейчас», собственное расписание и rollback/cancel confirmation; общий неоднозначный action на всю группу запрещён. Артефактная колонка имеет стабильную компактную ширину `12rem`: native `datetime-local` ограничен шириной колонки, рендерится отдельным block, а `Запланировать / Отмена` идут следующей строкой. На узком Staff viewport горизонтально прокручивается таблица целиком — поле даты не растягивает колонку, не перекрывает соседние действия и не обрезается собственной ячейкой;
- Полный BroadcastComposer не входит в эту фазу. Во второй фазе он получает нормальный Markdown editor, audience/count, PWA/Telegram previews, расписание, dry run и агрегированную delivery statistics. Story первой фазы показывает границу scope и не имитирует реальную отправку;
- ClassroomCatalog: add/rename/search, active/hidden filter, archive/quick restore, optimistic conflict и duplicate state после trim + Unicode NFKC + casefold. Display-name сохраняет внутренние пробелы; hard delete отсутствует.
- ClassroomGroupLayout: effective/inherited source, materialize-on-first-edit, room rows с group select/unassigned и фактический count комнат по группе. Group summary использует semantic level marker + мягкую border tint и показывает `очно N · распределено M`. Одна комната относится максимум к одной группе, одна группа получает любое число комнат; capacity/weights отсутствуют.
- ClassroomStudentPlanner: compact flex-wrap room cards для 6–15 комнат и примерно 200 строк, отдельная заметная секция `reassigning|unassigned`, always-on фамильно-именная сортировка, stale warning, blocking incidents, recalculate и confirm. Room header показывает assigned count, средний возраст, средний класс и среднюю силу с одним десятичным знаком.
- ClassroomStudentRow: имя, nullable возраст на сегодня (`13.3`), nullable класс, nullable auto-strength 0–10, компактный room select и history affordance. Missing value — `—`; дата рождения не показывается. Комната другой группы того же курса открывает confirmation смены группы; комнаты другого курса не входят в варианты строки.
- ClassroomStudentSearch: нормализует case/`ё–е`/пробелы/порядок имени и допускает небольшое edit distance; совпадение подсвечивается на месте, результат содержит jump action.
- ClassroomBulkMove: режим checkbox-selection, sticky bar с count и одним room select; применяет несколько локальных правок разом. DnD не используется. До explicit batch-save/confirm все изменения восстанавливаются из local draft; print/export и Staff→Telegram action в v1 отсутствуют.
- ClassroomAssignmentStatus: Student/Family варианты `not_applicable|reassigning|assigned`, имя комнаты и время публикации. Только Student-вариант содержит notification affordance; Family не обещает classroom push.

Questions/SOS получают отдельный от verdict queue product surface. Это приватный диалог по задаче или общий диалог занятия: teacher/admin видят входящие, student — только свои; закрепления за одним teacher и отдельного close/reopen статуса нет. Adapter сохраняет совместимость с legacy negative `problem_id` и Telegram handlers до отдельной backend-миграции.

## AI review states — future-ready, не первая версия

Компоненты проектируются на policy registry с режимами `off`, `student-visible negative check`, `teacher-only advisory`, `full AI reviewer`. Обязательные состояния: pending после submission, result absent/late, advisory text, student-visible AI comment, AI verdict, failure и escalation to human.

Teacher advisory — отдельная сворачиваемая панель, видимая сразу, если результат уже готов. Она не применяет verdict и не блокирует проверку; доступны «полезно/туфта» и явное действие скопировать текст в teacher comment. Full AI reviewer визуально остаётся особым AI author. Student/Family видят только разрешённый policy output; human final verdict не маркируется как «с участием AI», поскольку за него отвечает teacher.

AI comment допускает будущий безопасный math/SVG fragment, но story использует только санитизированный fixture. Дизайн не определяет prompts, leak prevention или LLM integration.

## Progress

StudentProgress показывает личную динамику, спокойные первые достижения и streak только относительно собственной истории. Не показывать leaderboard, percentile или красные «провалы». Empty/early state объясняет, что данные появятся естественно. Charts имеют table/text equivalent, не зависят от цвета и используют semantic chart tokens.

## Layout patterns

- Student/Family mobile: sticky top context, reading column, bottom navigation и safe-area;
- Student desktop: больше воздуха, но тот же информационный порядок;
- Staff: fixed application header/side navigation, wide workspace, compact toolbars;
- Split/master-detail сохраняет выбранную строку в URL;
- loading skeleton повторяет стабильную геометрию, empty state сообщает причину и действие, error сохраняет контекст.

## Multi-course extension

- `CourseCard` — крупный структурный блок курса на «Сейчас»: subject, собственные lesson/phase/progress, attendance и active group. Course accent остаётся спокойной рамкой, а не цветной pill.
- `CourseContext` и `CourseGroupSwitcher` разделяют выбор курса и active/allowed groups. Смена group/mode относится только к enrollment выбранного курса.
- `CourseNotificationSettings` показывает optional course override отдельно от global default.
- `CourseGroupCatalog`, `IndependentScheduleMatrix`, `TelegramBindingsEditor` покрывают Staff CRUD/archive, course defaults, group overrides/materialized snapshot и inheritance course/group Telegram targets.
- `SynonymMergeSplitPreview` показывает impact без физического переноса IDs. `SynonymMergedTimeline` даёт одну chronology без branch filter, но с provenance course/group/task. `SynonymReviewCase` объединяет все evidence и явно показывает concrete target verdict.
- `InPersonEventComposer` выбирает group lessons разных курсов/номеров и показывает полностью наследуемые rooms/assignments до перехода к planner.
- Product prototypes используют `CourseView`/`GroupView`; `LevelView` допустим только как legacy adapter на data boundary.

Authoritative behavior: [`docs/courses-groups-and-lessons.md`](../../docs/courses-groups-and-lessons.md). Source/story mapping: [`development-plan/18-design-implementation-map.md`](../development-plan/18-design-implementation-map.md).

## Gate

Storybook покрывает все перечисленные normal/loading/empty/error/offline/permission/long-content states, mobile и desktop. Владелец отдельно принимает математическое чтение, submission, review workspace, news и dense grid до сборки страниц.
