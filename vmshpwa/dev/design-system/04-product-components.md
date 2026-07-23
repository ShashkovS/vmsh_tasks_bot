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
- FeedbackAttention/ReactionPicker: unread feedback заметен без push; Student reactions скрыты от teacher, teacher internal reactions скрыты от Student/Family, admin видит обе стороны согласно permission contract.
- GroupReviewCallout: спокойная плашка группового разбора с временем, conference ID/code и устойчивым join action.

## Test answer inputs

Компонент выбирается по contract, а не эвристике JSX. Покрыть исторические типы: свободная строка, число/выражение, один выбор, несколько выборов и другие типы, подтверждённые fixtures. Показать expected format до ошибки. Состояния: untouched, invalid format, checking, correct, incorrect, rate-limited, closed, corrected checker/re-evaluated.

## Письменная сдача

Composer поддерживает текст и до 10 фотографий:

- выбрать camera/files, доступное объяснение типов и лимита;
- per-file preprocessing progress worker-а;
- thumbnail, full preview, удаление и **изменение порядка кнопками вверх/вниз** (без DnD-зависимости, доступно с клавиатуры); удаление и повторная загрузка — запасной путь для типового 1–2 фото;
- rotate/remove/retry, upload progress, общий payload size;
- draft autosave, offline queue, duplicate retry/idempotency receipt;
- final review порядка страниц до отправки;
- server receipt с временем клиента и сервера.

Оригинальная полученная фотография после submit неизменяема. Teacher annotation — отдельный overlay с pen/highlight/comment, undo/redo, масштабом и page navigation. FeedbackThread связывает точечные annotations и текстовые сообщения, показывает автора/время/канал и позволяет пересдачу без потери истории.

Human feedback и AI feedback имеют разные author/provenance components, accessible labels и tokens. Даже в режиме AI-verdict школьник не должен принять AI за живого преподавателя; complaint/escalation ведёт к human review.

## Новости

TelegramRichPost отображает entities, links, quotes, albums, video/document placeholders, forwarded/source attribution и math extension. Нужны card/list, detail и два editor preview: PWA и Telegram. Различать source revision, local editorial override, hidden/source-deleted и delivery error.

## Connectivity

ConnectionBanner/SyncIndicator/UpdatePrompt/PushPermissionCard:

- online не занимает постоянное заметное место;
- reconnecting/offline сообщают влияние на конкретное действие;
- queued count ведёт в outbox details;
- conflict/failed требует решения, не исчезает toast-ом;
- update prompt не уничтожает draft;
- push permission объясняет категории до browser prompt и уважает отказ.

## Staff data work

- DenseDataTable: sticky headers, resize/visibility, sort/filter, row selection, keyboard traversal;
- MetadataGrid: cell edit, TSV copy/paste, dry-run errors, bulk actions, undo boundary;
- ReviewQueue: основной вход по `synonyms`, счётчик и возраст очереди; list mode и fast one-at-a-time mode; sort по задаче, ожиданию, группе и ученику; полное название и recheck already-reviewed action;
- ReviewLock: текущая атомарная 30-минутная lease; занятая работа остаётся видна с именем проверяющего и disabled action; lost lock блокирует устаревший verdict и требует refetch;
- ThreePaneReview: queue / immutable evidence / feedback+verdict, resizable with accessible alternatives. Verdict actions строятся из course registry, идут от лучшего к худшему, доступны кнопками и digits (`1` всегда `+`); shortcuts не работают в editable fields и имеют видимую legend;
- ReviewCommentGuard: для verdict ниже `+` без комментария спрашивает подтверждение, но не запрещает отправку; `+` без комментария сохраняет и листает дальше; abandon удаляет unsaved comment/annotation, освобождает lock и переходит дальше;
- ReviewReaction: staff-only internal reaction, недоступная Student/Family API/view-model;
- LaTeXUpload: file/batch progress, diagnostics, source preview, derived previews;
- MissingAssetsFlow: exact missing refs, match candidates, upload/reuse, blocking resolution;
- PublicationControl: per-level task/hint/solution state, scheduled time, diff, publish/rollback confirmation;
- BroadcastComposer: audience query, count/preview, PWA/Telegram delivery options, quiet/category, dry run;
- ClassroomPlanner: capacity, auto-assignment explanation, conflict list и лёгкий app-local pointer/native drag-and-drop без новой dependency. Достаточен простой select/move fallback; сложная keyboard DnD-модель не требуется.

Questions/SOS получают отдельный от verdict queue product surface. Его adapter сохраняет совместимость с legacy negative `problem_id` и Telegram handlers до отдельной backend-миграции.

## AI review states — future-ready, не первая версия

Компоненты проектируются на policy registry с режимами `off`, `student-visible negative check`, `teacher-only advisory`, `full AI reviewer`. Обязательные состояния: pending после submission, result absent/late, advisory text, student-visible AI comment, AI verdict, failure и escalation to human.

Teacher advisory — отдельная сворачиваемая панель, видимая сразу, если результат уже готов. Она не предлагает и не применяет verdict, не заполняет human comment и не блокирует проверку. Full AI reviewer визуально остаётся особым AI author. Student/Family видят только разрешённый policy output; human final verdict не маркируется как «с участием AI», поскольку за него отвечает teacher.

AI comment допускает будущий безопасный math/SVG fragment, но story использует только санитизированный fixture. Дизайн не определяет prompts, leak prevention или LLM integration.

## Progress

StudentProgress показывает личную динамику, спокойные первые достижения и streak только относительно собственной истории. Не показывать leaderboard, percentile или красные «провалы». Empty/early state объясняет, что данные появятся естественно. Charts имеют table/text equivalent, не зависят от цвета и используют semantic chart tokens.

## Layout patterns

- Student/Family mobile: sticky top context, reading column, bottom navigation и safe-area;
- Student desktop: больше воздуха, но тот же информационный порядок;
- Staff: fixed application header/side navigation, wide workspace, compact toolbars;
- Split/master-detail сохраняет выбранную строку в URL;
- loading skeleton повторяет стабильную геометрию, empty state сообщает причину и действие, error сохраняет контекст.

## Gate

Storybook покрывает все перечисленные normal/loading/empty/error/offline/permission/long-content states, mobile и desktop. Владелец отдельно принимает математическое чтение, submission, review workspace, news и dense grid до сборки страниц.
