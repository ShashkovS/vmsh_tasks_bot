# Фаза 5. Страницы и потоки

## Общие требования

Каждая страница имеет canonical route, page title, loading/empty/error/offline варианты, keyboard-first порядок и реалистичные русские данные. Search/filter/sort/tab, которые пользователь ожидает переслать ссылкой или восстановить после reload, живут в TanStack Router search params с Zod validation.

Порядок реализации страниц: Student «Сейчас» → список задач → карточки test/written/oral → результат и тред → Staff queue/quick review. Первый проход выполняется в `mobile-light`; dark и desktop добавляются после принятия этого потока. Family и остальные Staff pages идут следующим проходом, не блокируя проверку первого Student slice.

Login — отдельный shell без раскрытия защищённого контента. Prototype screens не становятся production auth bypass.

## Student PWA

Нижняя навигация телефона строго: «Сейчас», «Задачи», «Новости», «Прогресс», «Профиль».

### Login

Логин вида `transliterated-surname-birth-day`, текущий Telegram-токен как пароль, password reveal, rate-limit/invalid/blocked/deactivated states. Восстановление доступа — обращение на почту `vmsh@179.ru` (логин выдаётся на почту после регистрации на кружок); Telegram-токен остаётся паролем, но Telegram OAuth не обещаем. Онбординга в первой фазе нет. После входа — возврат к безопасному intended route.

### Сейчас / текущая неделя

Урок, уровень, online/очный режим, текущая фаза недели, ближайшее событие, компактный progress и продолжение последней задачи. Для очного режима здесь же видна подтверждённая аудитория, состояние «Аудитория переназначается» или отсутствие применимости. Активная группа одна, но группы из `allowed_groups` дают полный доступ к чтению, сдаче и проверке. Attention order может поднимать новый feedback и незавершённое действие выше натурального порядка задач. Отдельно: pending submission, новый feedback, group problem-review call с конференцией, hints available, solutions published, no current lesson, offline cached.

### Задачи

Листок целиком с anchors и фильтром, строго в порядке номеров; архив уроков; focused task. Условие не дробится на cards без необходимости. Task detail содержит version/status/deadline, test или written/oral action, hidden-until-available hint/solution и историю. `WRITTEN_BEFORE_ORALLY` выглядит устной задачей и одновременно даёт письменную отправку и данные подключения в разрешённое окно.

Submission flows: все исторические test answer types с format/error/rate limit/pending-checker; written text/photos/up-down reordering/compress/review/offline queue/receipt; oral instructions/current availability и письменная сдача любой устной задачи. До первого review lock исходную written entry можно изменить/удалить; после lock новый материал добавляется в общий тред. Result/thread показывает зафиксированные после verdict pages, annotations, comments, последний градуированный verdict + раскрываемую историю, разрешённую AI provenance, реакцию ученика, пересдачу и changed-condition notice. Новый feedback остаётся отмеченным до трёх секунд видимости.

### Новости, прогресс, профиль

News list/detail с Telegram-rich content и albums. Progress: собственная динамика, достижения, streak, accessible statistics. Profile: identity/group/mode/devices/sessions; notification categories и push permission; outbox storage details.

## Family PWA

### Login и child switcher

Отдельный family account, recovery и session devices. Child switcher всегда показывает активного ребёнка и не смешивает cached data. Empty link state ведёт к безопасной процедуре привязки.

### Сейчас и ребёнок

Online/очный режим ребёнка и назначенная аудитория видны постоянно. Главная показывает текущий урок, phase/deadline, значимые изменения и активность без сравнений с другими. Detail ребёнка включает фотографии, полный student-visible thread, comments, annotations, verdict history, текущие задачи и прошлую статистику с ясным источником. Родитель может менять уровень/режим и независимо раскрывать опубликованные hint/solution.

### Опубликованные решения

Родитель может независимо открыть опубликованные условие, подсказку и решение. Отдельной Family self-check операции, результата или влияния на прогресс нет.

### Новости и профиль

Общие публикации для нескольких детей дедуплицируются; адресные элементы подписываются ребёнком/группой. По умолчанию Family получает один недельный итог после окончания всех проверок, а не отдельные review pushes. В первой версии есть push preferences, device sessions и privacy explanation; email UI отложен.

## Staff SPA

Teacher и admin работают в одном приложении. Navigation и backend permissions адаптируются по capabilities; запрещённые admin routes не просто скрываются, а возвращают корректный forbidden state.

### Weekly dashboard

Текущая фаза, публикации по уровням, submission/review/question/oral counts, delivery/incidents, быстрые безопасные действия. Teacher видит операционные очереди разрешённых групп, но отдельный statistics route может показывать данные всего кружка; admin получает полный административный scope.

### Written review

Queue page с основным grouping по задаче/`synonyms`, list/fast modes, сортировками по задаче, ожиданию, группе и ученику, фильтрами и deep link. Detail имеет компактную очередь и одну основную хронологическую колонку: immutable evidence/annotation, затем весь student/teacher thread, затем composer нового teacher reply и registry-driven verdict. Типично до ответа уже есть 1–2 student messages, но длинная переписка не ломает layout. Состояния claim, 30-minute lease, lock lost, another reviewer with name, long session, abandon с сохранением local unsent draft, recheck, accepted-without-comment, non-accepted confirmation, next item и return-to-problem-picker. Keyboard shortcuts отображаются, `1` означает `+` и не перехватывает ввод текста. На телефоне основная зона сохраняет тот же порядок, очередь открывается отдельно; offline verdict запрещён.

### Questions и oral

Questions отделяют общий SOS от вопроса к задаче и позволяют ответить без искусственного письменного verdict. Это приватная диалоговая лента без назначения одному teacher и без close/reopen статуса; migration state объясняет legacy Telegram source без смешения с verdict queue. Oral admin показывает Zoom/школьный режим, поиск школьника, уже зачтённые задачи, быстрое добавление/исправление отметок и атомарное завершение.

### AI review surfaces — future states

Staff показывает готовый advisory сразу, но никогда не ждёт AI и не блокирует human review. Stories/pages покрывают AI off, pending, advisory only, full AI reviewer, failed/not-ready и сравнение AI/human verdict для admin analytics. Human teacher остаётся автором собственного результата. Student/Family получают только policy-разрешённую часть и всегда различают AI и человека.

### Content administration

Lesson list/detail, upload по уровням, positional problem reconciliation, source diagnostics, missing-assets matching, web/Telegram/PDF derivative previews и отдельная scheduled publication/hide для условия, подсказки и решения каждого уровня. LaTeX в браузере не редактируется. Metadata grid с TSV и dropdown-ячейками task type/answer type. Problem settings включая answer type, synonym candidate и trusted `cor_ans_checker` diff/optional examples/audit; неготовый checker оставляет ответы pending до recheck.

### Operations

News moderation; users/groups/roles; statistics with accessible tables; searchable audit with request ID и before/after. Полный broadcast composer с Markdown editor, print, быстрый очный ввод результатов и Staff→Telegram publication относятся ко второй фазе.

`/staff/classrooms` называется «Аудитории», доступен только admin и сохраняет URL-state `lesson`, `tab`, `roomStatus`:

1. «Каталог»: add/rename/search, active/hidden filter, archive и quick restore; duplicate conflict не очищает ввод и показывает существующую аудиторию.
2. «По группам»: effective inherited layout, явное materialize-on-edit, строки комнат с group select/unassigned, level-color marker + мягкая border tint, фактические counts комнат и `очно/распределено` по каждой группе, confirm с optimistic conflict.
3. «Школьники»: compact flex-wrap room cards, отдельная reassigning/unassigned-секция, строки имя/возраст/класс/сила + compact room select, room count/average age/average grade/average strength, fuzzy search с подсветкой/jump, single и checkbox bulk move, classroom history, recalculate, stale state, blocking no-room/mismatch incident и confirm.

Школьники внутри каждой комнаты всегда отсортированы по фамилии и имени. Выбор комнаты другой группы требует confirmation одновременной смены группы. Изменения не пишутся на сервер по одному: local draft переживает reload и очищается после explicit batch-save/confirm либо явного discard. Типичный fixture показывает 6/5/2 фактически используемых комнат, но не изображает эти значения как вместимость или целевое ограничение. Неиспользованные active rooms допустимы. Archive используемой комнаты немедленно переводит затронутых текущих школьников в reassigning; restore не возвращает назначения. Mobile Staff использует последовательный layout без потери трёх шагов.

## Responsive acceptance viewports

- Student/Family: 320×568 minimum audit, 390×844 primary mobile, 768×1024 tablet, 1280×800 desktop;
- Staff: 1024×768 minimum supported workspace, 1440×900 primary, 1920×1080 wide. На меньшем экране Staff остаётся работоспособным через последовательный layout/Drawer, но не имитирует mobile Student app.

## Реализация и проверяемые точки

- Общий адаптивный shell и page-state contract: [`AppShell`](../../packages/app-shell/src/app-shell.tsx) и [`PageLayout`/`PageStatePanel`](../../packages/app-shell/src/page-layout.tsx). Login исключается из защищённого shell в [`student routes`](../../apps/student/src/routes/__root.tsx), [`family routes`](../../apps/family/src/routes/__root.tsx) и [`staff routes`](../../apps/staff/src/routes/__root.tsx).
- Student compositions: [`apps/student/src/pages.tsx`](../../apps/student/src/pages.tsx); детерминированные page stories и interaction checks: [`Pages/Student`](../../apps/student/src/pages.stories.tsx). Реальный detail route выводит test/written/oral fixture по `taskId`; production-данные позже заменят это правило без изменения page contract.
- Family compositions: [`apps/family/src/pages.tsx`](../../apps/family/src/pages.tsx); proof: [`Pages/Family`](../../apps/family/src/pages.stories.tsx). Story `Read only task` отдельно доказывает отсутствие textbox/self-check.
- Staff dashboard, review, publication/import, classrooms и permission state: [`apps/staff/src/pages.tsx`](../../apps/staff/src/pages.tsx); proof: [`Pages/Staff`](../../apps/staff/src/pages.stories.tsx).
- Shareable classroom URL contract `lesson/tab/roomStatus` с Zod runtime validation и синхронизацией вкладки: [`routes/classrooms.tsx`](../../apps/staff/src/routes/classrooms.tsx). Task-list search contract: [`routes/tasks.index.tsx`](../../apps/student/src/routes/tasks.index.tsx).
- `/staff/classrooms` использует принятый product component без DnD: [`ClassroomStudentPlanner`](../../packages/product/src/classroom-planning.tsx); плотная и local-draft фикстуры находятся в [`Product/Classrooms`](../../packages/product/src/classroom-planning.stories.tsx).

Текущий page corpus использует фиксированные prototype data и callbacks: он проверяет IA, состояния и взаимодействия, но не является production auth/API implementation и не добавляет mock backdoor.

## Gate

Принимаются flow coherence, URL/history, responsive layouts, reading comfort, density, states и role permissions. Не принимать красивые happy-path pages без error/offline/empty/locked variants.
