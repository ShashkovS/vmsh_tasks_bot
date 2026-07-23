# Фаза 5. Страницы и потоки

## Общие требования

Каждая страница имеет canonical route, page title, loading/empty/error/offline варианты, keyboard-first порядок и реалистичные русские данные. Search/filter/sort/tab, которые пользователь ожидает переслать ссылкой или восстановить после reload, живут в TanStack Router search params с Zod validation.

Login — отдельный shell без раскрытия защищённого контента. Prototype screens не становятся production auth bypass.

## Student PWA

Нижняя навигация телефона строго: «Сейчас», «Задачи», «Новости», «Прогресс», «Профиль».

### Login

Логин, текущий Telegram-токен как пароль, password reveal, rate-limit/invalid/blocked/deactivated states, восстановление с понятным переходом в поддерживаемый Telegram-процесс. Не обещать Telegram OAuth. После входа — возврат к безопасному intended route.

### Сейчас / текущая неделя

Урок, уровень, online/очный режим, текущая фаза недели, ближайшее событие, компактный progress и продолжение последней задачи. Attention order может поднимать новый feedback и незавершённое действие выше натурального порядка задач. Отдельно: pending submission, новый feedback, group problem-review call с конференцией, hints available, solutions published, no current lesson, offline cached.

### Задачи

Листок целиком с anchors и фильтром, строго в порядке номеров; архив уроков; focused task. Условие не дробится на cards без необходимости. Task detail содержит version/status/deadline, test или written/oral action, hidden-until-available hint/solution и историю. `WRITTEN_BEFORE_ORALLY` выглядит устной задачей и одновременно даёт письменную отправку и данные подключения в разрешённое окно.

Submission flows: test answer с format/error/rate limit; written text/photos/delete-and-reupload ordering/compress/review/offline queue/receipt; oral instructions/current availability. Result/thread показывает зафиксированные после verdict pages, annotations, comments, последний градуированный verdict + раскрываемую историю, разрешённую AI provenance, реакцию ученика, пересдачу и changed-condition notice. Новый feedback остаётся отмеченным до просмотра.

### Новости, прогресс, профиль

News list/detail с Telegram-rich content и albums. Progress: собственная динамика, достижения, streak, accessible statistics. Profile: identity/group/mode/devices/sessions; notification categories и push permission; outbox storage details.

## Family PWA

### Login и child switcher

Отдельный family account, recovery и session devices. Child switcher всегда показывает активного ребёнка и не смешивает cached data. Empty link state ведёт к безопасной процедуре привязки.

### Сейчас и ребёнок

Online/очный режим ребёнка виден постоянно. Главная показывает текущий урок, phase/deadline, значимые изменения и активность без сравнений с другими. Detail ребёнка: текущие задачи/attempts/feedback и прошлая статистика с ясным источником.

### Самостоятельное решение

После publication решения родитель может открыть условие/решение в reading mode, попробовать самостоятельно и отметить private self-check. Это не меняет школьный результат и явно отделено от него.

### Новости и профиль

Те же canonical публикации с family-relevant фильтрами; настройки push/email если появится, device sessions, privacy explanation.

## Staff SPA

Teacher и admin работают в одном приложении. Navigation и backend permissions адаптируются по capabilities; запрещённые admin routes не просто скрываются, а возвращают корректный forbidden state.

### Weekly dashboard

Текущая фаза, публикации по уровням, submission/review/question/oral counts, delivery/incidents, быстрые безопасные действия. Teacher видит свои группы, admin — полный scope.

### Written review

Queue page с основным grouping по задаче/`synonyms`, list/fast modes, сортировками по задаче, ожиданию, группе и ученику, фильтрами и deep link. Detail — три зоны: очередь, evidence/опциональная annotation, student context+thread+registry-driven verdict. Состояния claim, 30-minute lease, lock lost, another reviewer with name, long session, abandon with draft deletion, recheck, plus-without-comment, non-plus confirmation, next item и return-to-problem-picker. Keyboard shortcuts отображаются, `1` означает `+` и не перехватывает ввод текста. На телефоне зоны превращаются в последовательный flow без потери функций; offline verdict запрещён.

### Questions и oral

Questions отделяют общий SOS от вопроса к задаче и позволяют ответить без искусственного письменного verdict; migration state объясняет legacy Telegram source без смешения с verdict queue. Oral admin показывает Zoom/школьный режим, очередь/поиск, один разговор, несколько отметок и атомарное завершение.

### AI review surfaces — future states

Staff показывает готовый advisory сразу, но никогда не ждёт AI и не блокирует human review. Stories/pages покрывают AI off, pending, advisory only, full AI reviewer, failed/not-ready и сравнение AI/human verdict для admin analytics. Human teacher остаётся автором собственного результата. Student/Family получают только policy-разрешённую часть и всегда различают AI и человека.

### Content administration

Lesson list/detail, upload по уровням, source diagnostics, missing-assets matching, web/Telegram/PDF previews, publication/rollback. Metadata grid с TSV. Problem settings включая answer type, synonym candidate и trusted `cor_ans_checker` diff/tests/audit.

### Operations

News moderation; users/groups/roles; classroom auto-assignment и ручной план; broadcast composer/delivery; statistics with accessible tables; searchable audit with request ID and before/after.

## Responsive acceptance viewports

- Student/Family: 320×568 minimum audit, 390×844 primary mobile, 768×1024 tablet, 1280×800 desktop;
- Staff: 1024×768 minimum supported workspace, 1440×900 primary, 1920×1080 wide. На меньшем экране Staff остаётся работоспособным через последовательный layout/Drawer, но не имитирует mobile Student app.

## Gate

Принимаются flow coherence, URL/history, responsive layouts, reading comfort, density, states и role permissions. Не принимать красивые happy-path pages без error/offline/empty/locked variants.
