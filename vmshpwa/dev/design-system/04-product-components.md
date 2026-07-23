# Фаза 4. Product components и layout patterns

Product components живут вне нейтральных primitives — преимущественно в `packages/app-shell`, `packages/content` или новом явно названном shared product package после согласования. Каждый компонент принимает data/view-model и callbacks, не делает скрытый fetch.

## Математический документ

`MathDocument` покрывает заголовок, вводный текст, условие, подпункты, theorem-like callouts, numbered/unnumbered display math, inline math, широкую таблицу, code-like answer format, TikZ/SVG и подпись. Требования:

- reading serif только в документе, UI controls остаются sans;
- формула не обрезается: wrap where valid, otherwise локальный horizontal scroll с affordance;
- номера формул и anchor/deep link;
- copy текста без потери смысла;
- zoomable figure с keyboard zoom/reset, caption и alt;
- print preview не подменяет web renderer.

## Task experience

- ProblemHeader/ProblemStatus: номер, уровень, вид сдачи, deadline, текущий результат и history link.
- TaskListItem и long worksheet navigation: anchor, фильтр статусов, progress summary без рейтинга.
- HintDisclosure/SolutionDisclosure: время доступности, подтверждение осознанного раскрытия, already-viewed state, корректный deep link.
- DeadlineNotice: абсолютное время + понятная относительная фраза; closed/queued-before-deadline/conflict cases.
- AttemptTimeline: test attempts, submissions, verdicts, edits и пересдачи без обвинительного языка.

## Test answer inputs

Компонент выбирается по contract, а не эвристике JSX. Покрыть исторические типы: свободная строка, число/выражение, один выбор, несколько выборов и другие типы, подтверждённые fixtures. Показать expected format до ошибки. Состояния: untouched, invalid format, checking, correct, incorrect, rate-limited, closed, corrected checker/re-evaluated.

## Письменная сдача

Composer поддерживает текст и до 10 фотографий:

- выбрать camera/files, доступное объяснение типов и лимита;
- per-file preprocessing progress worker-а;
- thumbnail, full preview и удаление; ошибочный порядок исправляется удалением и повторной загрузкой страницы;
- rotate/remove/retry, upload progress, общий payload size;
- draft autosave, offline queue, duplicate retry/idempotency receipt;
- final review порядка страниц до отправки;
- server receipt с временем клиента и сервера.

Оригинальная полученная фотография после submit неизменяема. Teacher annotation — отдельный overlay с pen/highlight/comment, undo/redo, масштабом и page navigation. FeedbackThread связывает точечные annotations и текстовые сообщения, показывает автора/время/канал и позволяет пересдачу без потери истории.

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
- ReviewQueue: grouping problem family, SLA/time, filters, live invalidation без прыжка текущей строки;
- ReviewLock: owner/lease, lost lock, safe reacquire;
- ThreePaneReview: queue / immutable evidence / feedback+verdict, resizable with accessible alternatives;
- LaTeXUpload: file/batch progress, diagnostics, source preview, derived previews;
- MissingAssetsFlow: exact missing refs, match candidates, upload/reuse, blocking resolution;
- PublicationControl: per-level task/hint/solution state, scheduled time, diff, publish/rollback confirmation;
- BroadcastComposer: audience query, count/preview, PWA/Telegram delivery options, quiet/category, dry run;
- ClassroomPlanner: capacity, auto-assignment explanation, conflict list и лёгкий app-local pointer/native drag-and-drop без новой dependency. Достаточен простой select/move fallback; сложная keyboard DnD-модель не требуется.

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
