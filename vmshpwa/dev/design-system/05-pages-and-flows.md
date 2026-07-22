# Фаза 5. Страницы и потоки

## Общие требования

Каждая страница имеет canonical route, page title, loading/empty/error/offline варианты, keyboard-first порядок и реалистичные русские данные. Search/filter/sort/tab, которые пользователь ожидает переслать ссылкой или восстановить после reload, живут в TanStack Router search params с Zod validation.

Login — отдельный shell без раскрытия защищённого контента. Prototype screens не становятся production auth bypass.

## Student PWA

Нижняя навигация телефона строго: «Сейчас», «Задачи», «Новости», «Прогресс», «Профиль».

### Login

Логин, текущий Telegram-токен как пароль, password reveal, rate-limit/invalid/blocked/deactivated states, восстановление с понятным переходом в поддерживаемый Telegram-процесс. Не обещать Telegram OAuth. После входа — возврат к безопасному intended route.

### Сейчас / текущая неделя

Урок, уровень, online/очный режим, текущая фаза недели, ближайшее событие, компактный progress и продолжение последней задачи. Отдельно: pending submission, новый feedback, hints available, solutions published, no current lesson, offline cached.

### Задачи

Листок целиком с anchors и фильтром; архив уроков; focused task. Условие не дробится на cards без необходимости. Task detail содержит version/status/deadline, test или written/oral action, hints/solution и историю.

Submission flows: test answer с format/error/rate limit; written text/photos/reorder/compress/review/offline queue/receipt; oral instructions/current availability. Result/thread показывает immutable sent pages, annotations, comments, verdict, пересдачу и changed-condition notice.

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

Queue page с grouping/filter/deep link. Detail — три зоны: очередь, evidence/annotation, student context+thread+verdict. Состояния claim, lock lost, another reviewer, long session, cancel without verdict, recheck, next item. Keyboard shortcuts отображаются и не перехватывают ввод текста.

### Questions и oral

Questions отделяют общий SOS от вопроса к задаче и позволяют ответить без искусственного письменного verdict. Oral admin показывает Zoom/школьный режим, очередь/поиск, один разговор, несколько отметок и атомарное завершение.

### Content administration

Lesson list/detail, upload по уровням, source diagnostics, missing-assets matching, web/Telegram/PDF previews, publication/rollback. Metadata grid с TSV. Problem settings включая answer type, synonym candidate и trusted `cor_ans_checker` diff/tests/audit.

### Operations

News moderation; users/groups/roles; classroom auto-assignment и ручной план; broadcast composer/delivery; statistics with accessible tables; searchable audit with request ID and before/after.

## Responsive acceptance viewports

- Student/Family: 320×568 minimum audit, 390×844 primary mobile, 768×1024 tablet, 1280×800 desktop;
- Staff: 1024×768 minimum supported workspace, 1440×900 primary, 1920×1080 wide. На меньшем экране Staff остаётся работоспособным через последовательный layout/Sheet, но не имитирует mobile Student app.

## Gate

Принимаются flow coherence, URL/history, responsive layouts, reading comfort, density, states и role permissions. Не принимать красивые happy-path pages без error/offline/empty/locked variants.
