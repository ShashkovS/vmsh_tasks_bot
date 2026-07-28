# Этап 3. Student «Сейчас», уроки и офлайн-чтение

## Результат

Авторизованный школьник открывает «Сейчас», видит фазу недели, свой текущий урок, требующие внимания задачи, новости/баннеры и корректные unread states. Он читает длинный лист, работает с любой задачей из `allowed_groups`, видит обновлённое условие и повторно открывает кеш без сети.

Дизайн-контракт этапа: [Student «Сейчас», список и чтение задач, disclosure/offline states и Storybook stories](18-design-implementation-map.md#phase-3-design).

## Backend/read models

- `GET home`, lesson list/detail, problem detail, available groups, active banners.
- Read model учитывает active group, полный action access по `allowed_groups`, online mode, publication revisions, latest results и week phase.
- Natural task order сохраняет порядок листка; attention order отделён от canonical list.
- Hint/solution endpoint проверяет publication, просит confirmation в UI и пишет reveal event.
- Group/mode changes доступны Student и Family, немедленно меняют текущие задачи, пишут `user_changes_log` и invalidation; история старых групп остаётся.
- Ответ содержит `contentRevision`, `entityVersion`, `cachePolicy`, server time, отдельный `submissionClosesAt` и nullable schedule/fact публикации solution. UI показывает абсолютный cutoff как самостоятельное значение и не выводит его из `publishedAt`.

## Frontend

Существующие routes:

- `student/src/routes/index.tsx` — «Сейчас»;
- `tasks.index.tsx`, `tasks.$taskId.tsx`;
- `profile.*` для group/mode;
- bottom nav: «Сейчас», «Задачи», «Новости», «Прогресс», «Профиль».

Features: `student/src/features/home`, `tasks`; shared `packages/content` renderer.

Состояния:

- no lesson, not published, long list, partial content, solution not yet available;
- accepted/needs work/unreviewed/new comment badges;
- separate configurable group banner and oral-window card placeholder;
- level chip + confirmation; prominent online/in-person control без deadline на смену;
- индикатор изменившегося условия для пользователя, который открывал прежнюю revision; скрытое занятие исчезает целиком;
- hint and solution deliberate reveal; latest verdict summary without fake production actions;
- loading/error/offline/stale/update available.

## Offline

- Dexie documents store только authenticated audience/user namespace, document revision, fetched/expiry metadata и sanitized payload.
- Cache lesson text and KaTeX fonts; figures with rolling ~2-week policy and total budget monitor.
- Offline route reads last successful revision, marks staleness and never invents publication/hint availability.
- Logout warning and namespace cleanup policy follow phase-1 decision.

## Tests

- Home priority/domain tests across week phases, group/mode and result states, включая раздельные cutoff/solution times и перенос одного без неявного изменения другого.
- Contract fixtures for empty/full/long/forbidden/stale home and task.
- Dexie upgrade/cache eviction/user separation/offline fallback tests.
- Renderer stress: long list, many formulas main thread performance budget, missing SVG.
- Storybook first-priority mobile-light pages plus desktop/dark follow-up matrix according to accepted design gate.
- Playwright: history/deep links, group permission, confirm reveal, reload offline, cache isolation after logout/login different user, unread routing.

## Критерии приёмки

- Home не требует N+1 API calls и показывает данные одного consistent version.
- Другой `allowed_group` доступен для чтения и сдачи; группа вне `allowed_groups` возвращает `403`.
- Hint/solution до publication невозможно получить подбором URL.
- Offline показывает явно подписанную последнюю копию и переживает browser restart в поддерживаемом режиме.
- Switch in-person объясняет последствия до сохранения и оставляет history.
- Ученический mobile-light layout принят в Storybook до подключения последующих submission actions.

## Пруфы завершения этапа

Промежуточный gate **Phase 3A — Student course/access boundary** реализован
28 июля 2026, revision `d70b0d9`:

- [x] `GET /student/api/v1/courses` и course-scoped enrollment detail проецируют
      revalidated session authority без второго repository/N+1 слоя;
- [x] response использует общий Zod CourseEnrollment contract, один active и
      несколько allowed groups, per-course attendance и optimistic versions;
- [x] чужой/неизвестный course context не раскрывается (`403`), произвольный
      `studentId` и неожиданные query-параметры не принимаются;
- [x] same-origin browser client фиксирует Student runtime, валидирует ответ,
      использует principal-scoped query keys и повторяет GET после auth refresh;
- [x] real aiohttp/SQLite regression **45 PASS**, app-shell/contracts **90 PASS**,
      strict checks и Student production build PASS.

Proof: [`phase3-course-access-api.md`](../../../pwa_tests/reports/phase3-course-access-api.md).
Экран «Сейчас» намеренно ещё не подключён: до этого нужен настоящий lesson/home
read model, чтобы не выдавать фиктивные даты и progress за server state.

Промежуточный gate **Phase 3B — Student lesson read model** реализован
28 июля 2026, revision `66f30c0`:

- [x] course/group-scoped list и detail используют конкретный `group_lesson`;
- [x] список ограничен 50 строками, имеет cursor и строится одним SQLite query;
- [x] active group выбирается по умолчанию, другой `allowed_group` разрешён,
      группа вне revalidated enrollment получает `403`;
- [x] scheduled/draft/hidden condition не раскрывает занятие, а hide удаляет
      его и из list, и из detail;
- [x] condition/hint/solution содержат только фактическую published projection;
- [x] `submissionClosesAt` и `solutionScheduledAt` передаются независимо;
- [x] общий Zod fixture, browser client и principal/course/group query keys
      проверены TypeScript unit suite;
- [x] полный content HTTP regression: **32 PASS**; focused TS: **16 PASS**.

Proof: [`phase3-student-lessons-api.md`](../../../pwa_tests/reports/phase3-student-lessons-api.md).
Production «Сейчас» ещё не входил в этот gate: его server-owned projection и
реальный transport закрыты следующим инкрементом.

Промежуточный gate **Phase 3C — production Student «Сейчас»** реализован
28 июля 2026, revision `77927e0`:

- [x] `GET /student/api/v1/home` возвращает один consistent snapshot всех
      course enrollments и выбирает последнее опубликованное занятие active
      group одним bounded SQLite statement;
- [x] фаза занятия вычисляется на сервере с независимыми cutoff и публикацией
      решения; скрытое condition удаляет урок из home projection;
- [x] Zod contract/fixture запрещает duplicate courses и current lesson другой
      группы, browser client использует один same-origin запрос;
- [x] production `/student/` заменил prototype данные на настоящий transport и
      показывает loading/error/offline/empty/published states без фиктивных
      чисел;
- [x] переход из карточки курса открывает конкретный опубликованный
      `group_lesson` с provenance группы;
- [x] полный content HTTP regression **32 PASS**, focused TS **22 PASS**,
      production build PASS, browser checkpoint **3/3 PASS**.

Proof: [`phase3-student-home.md`](../../../pwa_tests/reports/phase3-student-home.md).
Следующий gate — production «Задачи» с course/group context, после него —
problem/reveal и offline Dexie.

Промежуточный gate **Phase 3D — production Student «Задачи» и архив листков**
реализован 28 июля 2026, revision `42ea05c`:

- [x] production `/student/tasks` использует course/group/lesson API вместо
      prototype задач и фиктивных verdict/status;
- [x] validated URL state выбирает только revalidated course и allowed group;
      недоступный context отображается как forbidden;
- [x] архив страниц подгружается по server cursor через infinite query и
      сохраняет canonical reverse lesson order;
- [x] выбор другого allowed group меняет только контекст чтения, а не active
      enrollment; отдельный текст этого режима проверен Storybook interaction;
- [x] карточка показывает только server-owned публикации и открывает точный
      `group_lesson` в long-sheet renderer;
- [x] полный unit/integration regression **259 TS + 1098 Python PASS**,
      Storybook **180 PASS**, production browser checkpoint **3/3 PASS**.

Proof: [`phase3-student-task-archive.md`](../../../pwa_tests/reports/phase3-student-task-archive.md).
Следующий gate — публичная identity и canonical problem list/status projection;
после него deliberate reveal и offline Dexie.

Промежуточный gate **Phase 3E — canonical список задач и реальные статусы**
реализован 28 июля 2026, revisions `1aeb78d`, `8448a8b`:

- [x] legacy `problems` получили отдельный immutable public ID с точным
      migration up/down/up и deterministic fixture identities;
- [x] новый course/group-scoped endpoint отдаёт задачи только текущей
      опубликованной condition revision и запрещает недоступную группу;
- [x] статусы строятся из настоящих queue/discussion/result/verdict rows;
      pending queue перекрывает старую оценку;
- [x] подтверждённые synonym groups объединяют work state логически, сохраняя
      исходные задачи и результаты раздельно;
- [x] strict Zod fixture, same-origin client и principal-scoped query key не
      пропускают произвольные IDs или malformed payload;
- [x] production task rows используют принятый `TaskListItem`, реальные
      status/verdict и route с непрозрачным `problem-*` ID;
- [x] полный regression **263 TS + 1100 Python PASS**, strict checks PASS,
      production browser checkpoint **3/3 PASS**.

Proof:
[`phase3-student-problem-list.md`](../../../pwa_tests/reports/phase3-student-problem-list.md).
Следующий gate — deliberate reveal подсказок/решений и offline Dexie.

- [x] Revision/migrations: `1aeb78d`, `8448a8b`;
      `migrations/0044.pwa_problem_identity*`, API/read model и frontend paths
      перечислены в Phase 3E proof.
- [ ] Demo Student Now/list/long/focused/offline: Now + lesson archive +
      canonical problem status + focused condition **3/3 PASS**; offline и
      deliberate reveal открыты.
- [x] Lesson list query/read contract: один bounded SQLite statement; proof выше.
- [x] Home query count/plan and response contract: bounded single statement,
      Zod fixture и browser proof в `phase3-student-home.md`.
- [ ] Hint/solution authorization + reveal events: `<tests/result>`.
- [ ] Dexie cache/quota/isolation tests: `<result>`.
- [ ] Storybook priority stories, interactions, a11y, visuals:
      `product-courses--allowed-group-reading-context`, suite **180 PASS**;
      problem/offline stories и visual owner gate открыты.
- [ ] Playwright online/offline/deep-link 3 browsers: online
      home→course/group archive→URL-selected lesson→opaque problem URL→focused
      condition **3/3 PASS**; cold-offline/deep-link isolation ещё открыты.
- [ ] Performance evidence long math document/KaTeX: `<path/result>`.
- [ ] Docs/cache policy/known limitations/acceptance: `<paths/issues/name/date>`.

## Многокурсовый инкремент Phase 3

«Сейчас» показывает карточку каждого course enrollment. Tasks и focused task используют validated `course/group/lesson`; query/cache/draft keys не смешивают курсы. Отозванный group access скрывает новые материалы, но сохраняет собственную старую историю.

Дополнительный proof: `Pages/Student--today-multiple-courses`, `--tasks-course-and-group`, offline cache isolation и deep links двух курсов; `Pages/Family--activity-by-course` read-only parity.
