# Фаза 5. Страницы и потоки

Связь принятых page compositions с вертикальными backend/frontend-этапами, конкретными компонентами и открываемыми story IDs ведётся в [`development-plan/18-design-implementation-map.md`](../development-plan/18-design-implementation-map.md).

## Общие требования

Каждая страница имеет canonical route, page title, loading/empty/error/offline варианты, keyboard-first порядок и реалистичные русские данные. Search/filter/sort/tab, которые пользователь ожидает переслать ссылкой или восстановить после reload, живут в TanStack Router search params с Zod validation.

Порядок реализации страниц: Student «Сейчас» → список задач → карточки test/written/oral → результат и тред → Staff queue/quick review. Первый проход выполняется в `mobile-light`; dark и desktop добавляются после принятия этого потока. Family и остальные Staff pages идут следующим проходом, не блокируя проверку первого Student slice.

Login — отдельный shell без раскрытия защищённого контента. Prototype screens не становятся production auth bypass.

## Student PWA

Нижняя навигация телефона строго: «Сейчас», «Задачи», «Новости», «Прогресс», «Профиль».

### Login

Логин вида `transliterated-surname-birth-day`, текущий Telegram-токен как пароль, password reveal, rate-limit/invalid/blocked/deactivated states. Восстановление доступа — обращение на почту `vmsh@179.ru` (логин выдаётся на почту после регистрации на кружок); Telegram-токен остаётся паролем, но Telegram OAuth не обещаем. Онбординга в первой фазе нет. После входа — возврат к безопасному intended route.

Owner-confirmed core разрешает после прежнего online-входа cold start без сети с cached content/drafts без повторного пароля и logout с outbox после предупреждения. Implementation default делает cache account-scoped, явно подписывает непроверенную сессию и после подтверждённого logout очищает данные общего устройства. Уже реализован срок жизни shell: prior-verified вкладка остаётся явно `offline-unverified` только до server `sessionExpiresAt` и закрывается на expiry/browser resume. Durable cold start, cached content/drafts и Family-эквивалент этой персистентной части ещё не реализованы.

### Сейчас / текущая неделя

Каждый курс имеет отдельную карточку: group lesson, online/очный режим этого enrollment, текущая фаза, ближайшее событие, компактный progress и продолжение последней задачи. Для очного режима здесь же видна подтверждённая аудитория, состояние «Аудитория переназначается» или отсутствие применимости. Активная группа одна внутри курса, но allowed groups этого enrollment дают полный доступ к чтению, сдаче и проверке. Attention order может поднимать новый feedback и незавершённое действие выше натурального порядка задач. Отдельно: pending submission, новый feedback, group problem-review call с конференцией, hints available, solutions published, no current lesson, offline cached.

### Задачи

Листок целиком с anchors и фильтром, строго в порядке номеров; архив уроков; focused task. Условие не дробится на cards без необходимости. Task detail содержит version/status/deadline, test или written/oral action, hidden-until-available hint/solution и историю. `WRITTEN_BEFORE_ORALLY` выглядит устной задачей и одновременно даёт письменную отправку и данные подключения в разрешённое окно.

Submission flows: все исторические test answer types с format/error/rate limit/pending-checker; written text/photos/up-down reordering/compress/review/offline queue/receipt; oral instructions/current availability и письменная сдача любой устной задачи. До первого review lock исходную written entry можно изменить/удалить; после lock новый материал добавляется в общий тред. Result/thread показывает зафиксированные после verdict pages, annotations, comments, последний градуированный verdict + раскрываемую историю, разрешённую AI provenance, реакцию ученика, пересдачу и changed-condition notice. Owner-confirmed teacher flow показывает перенесённые сообщения/фотографии в target timeline; scoped admin, preview и post-review correction — implementation default. Records не сливаются физически. Новый feedback остаётся отмеченным до трёх секунд видимости.

### Новости, прогресс, профиль

News list/detail с Telegram-rich content и albums. Progress: собственная динамика, достижения, streak, accessible statistics. Profile: identity/group/mode/devices/sessions; notification categories и push permission; outbox storage details. Student profile использует реальный `AccountSessionManager`: current device, revoke другого устройства, current logout и logout-all, с fail-closed состояниями и подтверждением.

## Family PWA

### Login и child switcher

Отдельный family account, recovery и те же реальные session devices через
`AccountSessionManager`. Child switcher всегда показывает активного ребёнка и
не смешивает cached data. Empty link state ведёт к безопасной процедуре
привязки. Отдельный Staff profile route только ради session UI не создаётся.

### Сейчас и ребёнок

Online/очный режим ребёнка и назначенная аудитория видны отдельно для каждого курса. Главная показывает course lessons, phase/deadline, значимые изменения, активность и спокойные личные достижения курса без сравнений с другими. Подписи достижений совпадают со Student UI; неизвестный server rule не показывается техническим кодом. Detail ребёнка включает фотографии, полный student-visible synonym thread с provenance, comments, annotations, verdict history, текущие задачи и прошлую course-scoped статистику. Родитель может менять active group/mode конкретного курса и независимо раскрывать опубликованные hint/solution.

### Опубликованные решения

Родитель может независимо открыть опубликованные условие, подсказку и решение. Отдельной Family self-check операции, результата или влияния на прогресс нет.

### Новости и профиль

Общие публикации для нескольких детей дедуплицируются; адресные элементы
подписываются ребёнком/группой. Family получает один итог конкретного занятия
только после явного admin-действия, а не отдельные review pushes и не по
автоматическому признаку пустой очереди. Поздно связанный Family account можно
уведомить без дубля прежним получателям. В первой версии есть push preferences,
device sessions и privacy explanation; email UI отложен. Реализация:
[`family-notifications-page.tsx`](../../apps/family/src/family-notifications-page.tsx).

## Staff SPA

Уточнение 9 сентября 2026: обычный teacher получает на «Уроки» и «Курсы»
список доступных назначений и вход в собственную тестовую Student-личность;
«Новости» открывает ту же ленту, что школьнику. Admin сохраняет редакторы и
получает отдельное «Тестирование». Полный цикл отправки и проверки не входит
в учебную статистику. Заглушка oral скрыта из навигации.
Реализация: [`StaffTestingPage`](../../apps/staff/src/staff-testing-page.tsx),
[контракт и проверки](../../docs/staff-testing.md).

Teacher и admin работают в одном приложении. Navigation и backend permissions адаптируются по capabilities; запрещённые admin routes не просто скрываются, а возвращают корректный forbidden state.

### Weekly dashboard

Текущая фаза по курсам и группам, независимые публикации group lessons, submission/review/question/oral counts, delivery/incidents, быстрые безопасные действия. Teacher видит только course/group scopes; admin получает полный административный scope. Aggregate Staff statistics допустимы по capability, но Student/Family comparisons запрещены.

### Written review

Queue page с основным grouping по задаче/`synonyms`, list/fast modes, сортировками по задаче, ожиданию, группе и ученику, фильтрами и deep link. Detail имеет компактную очередь и одну основную хронологическую колонку: immutable evidence/annotation, затем весь student/teacher thread, затем composer нового teacher reply и registry-driven verdict. Типично до ответа уже есть 1–2 student messages, но длинная переписка не ломает layout. Owner-confirmed teacher flow переносит одно или несколько выбранных сообщений/фотографий и показывает target timeline; implementation default добавляет scoped admin, source/target preview и post-review correction поверх append-only projection. В combined synonym case concrete target для verdict выбирается по задаче последней посылки по server receive time, не client time. Состояния claim, 30-minute lease, lock lost, another reviewer with name, long session, abandon с сохранением local unsent draft, recheck, accepted-without-comment, non-accepted confirmation, next item и return-to-problem-picker. Keyboard shortcuts отображаются, `1` означает `+` и не перехватывает ввод текста. На телефоне основная зона сохраняет тот же порядок, очередь открывается отдельно; offline verdict запрещён. Перенос материала и его Staff UI пока не реализованы.

### Questions и oral

Questions отделяют общий SOS от вопроса к задаче и позволяют ответить без искусственного письменного verdict. Это приватная диалоговая лента без назначения одному teacher и без close/reopen статуса; migration state объясняет legacy Telegram source без смешения с verdict queue. Oral admin показывает Zoom/школьный режим, поиск школьника, уже зачтённые задачи, быстрое добавление/исправление отметок и атомарное завершение.

### AI review surfaces — future states

Staff показывает готовый advisory сразу, но никогда не ждёт AI и не блокирует human review. Stories/pages покрывают AI off, pending, advisory only, full AI reviewer, failed/not-ready и сравнение AI/human verdict для admin analytics. Human teacher остаётся автором собственного результата. Student/Family получают только policy-разрешённую часть и всегда различают AI и человека.

### Content administration

Course/group catalog, lesson list/detail, upload по group lesson, positional problem reconciliation, source diagnostics, missing-assets matching, web/Telegram/PDF derivative previews и отдельная scheduled publication/hide для условия, подсказки и решения каждой группы. LaTeX в браузере не редактируется. Metadata grid с TSV и dropdown-ячейками task type/answer type. Problem settings включают answer type, synonym candidate/merge/split impact и trusted `cor_ans_checker` diff/optional examples/audit; неготовый checker оставляет ответы pending до recheck.

На странице конкретного группового занятия global admin видит отдельный блок
«Итоги для семей» после content/review context. Он проверяет получателей,
подтверждает рассылку вручную и после receipt видит идемпотентное состояние;
teacher блока не получает. Реализация: [`StaffContentWorkspace`](../../apps/staff/src/content-page.tsx)
и [`FamilyDigestPanel`](../../apps/staff/src/family-digest-panel.tsx).

### Operations

News moderation; users/groups/roles; statistics with accessible tables; searchable audit with request ID и before/after. Полный broadcast composer с Markdown editor, print, быстрый очный ввод результатов и Staff→Telegram channel publication относятся ко второй фазе. Узкая персональная classroom delivery Student входит в v1 как отдельный confirm→preview→send flow.

`/staff/classrooms` называется «Аудитории», доступен только admin и сохраняет URL-state `event`, optional `course/group`, `tab`, `roomStatus`:

1. «Каталог»: add/rename/search, active/hidden filter, archive и quick restore; duplicate conflict не очищает ввод и показывает существующую аудиторию.
2. «По группам»: effective inherited layout, явное materialize-on-edit, строки комнат с group select/unassigned, level-color marker + мягкая border tint, фактические counts комнат и `очно/распределено` по каждой группе, confirm с optimistic conflict.
3. «Школьники»: compact flex-wrap room cards, отдельная reassigning/unassigned-секция, строки имя/возраст/класс/сила + compact room select, room count/average age/average grade/average strength, fuzzy search с подсветкой/jump, single и checkbox bulk move, classroom history, recalculate, stale state, blocking no-room/mismatch incident и confirm.

После confirm появляется отдельный блок «Рассылка аудиторий». Он не отправляет ничего автоматически: admin открывает preview, проверяет owner-confirmed per-channel counts, выбирает PWA и/или Telegram и нажимает «Разослать аудитории». Partial delivery явно отделена от полного успеха, списки раскрываются по запросу. Implementation-default «Повторить ошибки» повторяет только failed channel–recipient pairs без дублей success. Изменение плана после batch возвращает `есть неразосланные изменения`; Family получает только authoritative room state. Расширенный report/retry flow ещё не реализован.

Школьники внутри каждой комнаты всегда отсортированы по фамилии и имени. Выбор комнаты другой группы того же курса требует confirmation одновременной смены active group; комнаты другого курса не предлагаются для этой строки. Изменения не пишутся на сервер по одному: local draft переживает reload и очищается после explicit batch-save/confirm либо явного discard. Типичный fixture показывает 6/5/2 фактически используемых комнат, но не изображает эти значения как вместимость или целевое ограничение. Неиспользованные active rooms допустимы. Archive используемой комнаты немедленно переводит затронутых текущих школьников в reassigning; restore не возвращает назначения. Mobile Staff использует последовательный layout без потери трёх шагов.

## Responsive acceptance viewports

- Student/Family: 320×568 minimum audit, 390×844 primary mobile, 768×1024 tablet, 1280×800 desktop;
- Staff: 1024×768 minimum supported workspace, 1440×900 primary, 1920×1080 wide. На меньшем экране Staff остаётся работоспособным через последовательный layout/Drawer, но не имитирует mobile Student app.

## Реализация и проверяемые точки

- Общий адаптивный shell и page-state contract: [`AppShell`](../../packages/app-shell/src/app-shell.tsx) и [`PageLayout`/`PageStatePanel`](../../packages/app-shell/src/page-layout.tsx). Login исключается из защищённого shell в [`student routes`](../../apps/student/src/routes/__root.tsx), [`family routes`](../../apps/family/src/routes/__root.tsx) и [`staff routes`](../../apps/staff/src/routes/__root.tsx).
- Student compositions: [`apps/student/src/pages.tsx`](../../apps/student/src/pages.tsx); детерминированные page stories и interaction checks: [`Pages/Student`](../../apps/student/src/pages.stories.tsx). Реальный detail route выводит test/written/oral fixture по `taskId`; production-данные позже заменят это правило без изменения page contract.
- Family compositions: [`apps/family/src/pages.tsx`](../../apps/family/src/pages.tsx) и [`family-children-page.tsx`](../../apps/family/src/family-children-page.tsx); proof: [`Pages/Family`](../../apps/family/src/pages.stories.tsx). Stories `Course achievements` и `Read only task` отдельно доказывают course-scoped личные факты без ranking и отсутствие textbox/self-check.
- Staff dashboard, review, publication/import, classrooms и permission state: [`apps/staff/src/pages.tsx`](../../apps/staff/src/pages.tsx); proof: [`Pages/Staff`](../../apps/staff/src/pages.stories.tsx).
- Shareable classroom URL contract `event/course/group/tab/roomStatus` с Zod runtime validation и синхронизацией вкладки: [`routes/classrooms.tsx`](../../apps/staff/src/routes/classrooms.tsx). Task-list search contract `course/group/lesson/view/topic`: [`routes/tasks.index.tsx`](../../apps/student/src/routes/tasks.index.tsx).
- `/staff/classrooms` использует принятый product component без DnD: [`ClassroomStudentPlanner`](../../packages/product/src/classroom-planning.tsx); плотная и local-draft фикстуры находятся в [`Product/Classrooms`](../../packages/product/src/classroom-planning.stories.tsx).

## Multi-course page flows

- Student «Сейчас» показывает отдельную `CourseCard` на каждый enrollment; Tasks хранит course/group/lesson; Progress и course notification overrides никогда не смешивают курсы.
- Family current activity разделяется по курсам ребёнка и остаётся read-only. Ни один курс не показывает position/percentile/group comparison.
- Staff получает `/courses` с каталогом курсов/групп, независимыми schedule snapshots и Telegram bindings. Lesson/content views всегда имеют явный course/group context.
- Synonym detail показывает одну chronology без tabs/filter; provenance встроен в каждый message/evidence. Combined review остаётся одним кейсом.
- Classroom flow начинается с `in_person_event`: admin выбирает group lessons разных курсов и номеров, видит inherited plan, затем использует существующие catalog/layout/students steps.
- URL params course/group/lesson/event/tab runtime-validated. Они восстанавливают контекст, но не заменяют backend permission checks.

Proof pages: `Pages/Student--today-multiple-courses`, `--tasks-course-and-group`, `--progress-by-course`; `Pages/Family--activity-by-course`; `Pages/Staff--course-and-group-administration`, `--multi-course-classroom-event`.

Текущий page corpus использует фиксированные prototype data и callbacks: он проверяет IA, состояния и взаимодействия, но не является production auth/API implementation и не добавляет mock backdoor.

## Gate

Принимаются flow coherence, URL/history, responsive layouts, reading comfort, density, states и role permissions. Не принимать красивые happy-path pages без error/offline/empty/locked variants.


### Компактный live-приём — 10 сентября 2026

Замечания владельца и контракт: [live-marking.md](../../docs/live-marking.md).
[LiveZoomGrid](../../apps/staff/src/live-marking-grid.tsx) размещает задачи
адаптивной сеткой с независимыми кнопками оценки и условия;
[LiveConditionDialog](../../apps/staff/src/live-marking-condition.tsx) открывает
опубликованный математический документ и возвращает фокус к той же задаче.
[LiveMarkingPage](../../apps/staff/src/live-marking-page.tsx) сворачивает мобильные
селекторы очного занятия в настройки, а таблица ограничивает ФИО шириной 112 px
даже при малом числе задач. Проверки и снимки:
[отчёт](../../../pwa_tests/reports/live-marking-compact.md).
Визуальное принятие владельцем остаётся открытым.


## Результаты школьника (admin-only)

[StudentResultsPage](../../apps/staff/src/student-results-page.tsx) и
[ResultHistory](../../apps/staff/src/student-results-history.tsx) реализуют
[принятые требования](../../docs/student-results.md): fuzzy-поиск, компактные
таблицы по занятиям/уровням, read-only PWA/Telegram история выбранного занятия,
защищённые фотографии/аннотации, версии условий и переходы в существующую
проверку. URL сохраняет школьника, курс и номер занятия. Мобильная адаптация,
клавиатура и обе темы проверены в трёх браузерах;
[отчёт](../../../pwa_tests/reports/student-results/README.md).


## Вопросы организаторам (Student/Family/Staff)

[Решение и API](../../docs/organizer-questions.md): вход на «Сейчас» и в профиле,
личные обращения без привязки к занятию, текст + фотографии, необязательный ребёнок
родителя. Счётчик ответов в профиле. Административная очередь с фильтрами
«Нужен ответ», «Ответили», «Все», без назначения/закрытия. Нижняя навигация не меняется.
Композиция — `packages/app-shell/src/organizer-pages.tsx`; общий `FeedbackThread`
различает родителя, школьника и администратора. [Отчёт](../../../pwa_tests/reports/organizer-questions/README.md).

## Названия задач — 11 сентября 2026

В листках, таблицах плюсов и истории результатов видны номер и название,
включая названия самостоятельных пунктов. Источник — метаданные соответствующей
версии условия; fallback — исходник. [Детали и файлы реализации](../../docs/task-titles.md).

### Печать ученических листков

`/student/tasks` и ссылки на отдельный листок/задачу поддерживают обычную печать
браузера: [требования и компоненты](../../docs/worksheet-print.md). Печатаются
уже показанные занятия и только раскрытые учебные материалы. Ответы ученика,
фотографии работ, проверки и переписка исключены; экранное состояние сохраняется.
