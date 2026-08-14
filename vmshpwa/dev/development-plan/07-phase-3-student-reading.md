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
- Переключатель показывает только действительно доступные группы: пояснение «доступна» возле каждой из них не выводится, а недоступных групп в Student UI нет.
- Режим листка рендерит тот же semantic math document, что и отдельная задача, и после каждой задачи (либо после каждого её пункта) вставляет полноценные controls сдачи, подсказки, решения и вопрос преподавателю. Opaque `problem_id` используется только в URL/API и никогда не становится пользовательским заголовком.
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
Следующий после него gate Phase 3F закрыт ниже.

Промежуточный gate **Phase 3F — осознанное раскрытие подсказок и решений**
реализован 28 июля 2026, revision `fabdf93`:

- [x] canonical task projection сообщает отдельно `unavailable`, `available`
      и `revealed` для подсказки и решения конкретной задачи;
- [x] старый прямой Student GET закрыт `409`, а strict POST повторно проверяет
      session, course/group access, текущие condition/material publications и
      точный opaque problem ID;
- [x] immutable reveal event создаётся атомарно и идемпотентно; повтор сохраняет
      первоначальный timestamp, а новая publication образует новую audit
      boundary;
- [x] API возвращает только выбранную задачу, без introduction, соседних задач
      и материала другого вида;
- [x] shared disclosure не показывает содержимое до успешного audit-запроса,
      восстанавливается после сетевой ошибки и не просит повторное подтверждение
      после reload;
- [x] полный regression **265 TS + 1100 Python PASS**, Storybook **181 PASS**,
      strict checks PASS, production browser checkpoint **3/3 PASS**.

Proof:
[`phase3-student-material-reveal.md`](../../../pwa_tests/reports/phase3-student-material-reveal.md).
Следующий после него gate Phase 3G закрыт ниже.

Промежуточный gate **Phase 3G — authenticated Dexie и cold-offline reading**
реализован 28 июля 2026, revisions `50cd541`, `d4b0b9b`, `89cefb7`,
`bb6c6ef`, `d822e2e`:

- [x] secret-free auth snapshot открывает только ещё действующий namespace
      прежнего аккаунта; expiry, authoritative rejection, logout и account
      switch очищают его атомарно вместе с documents/outbox;
- [x] все Student read models и condition сохраняются отдельными
      owner/resource-scoped Zod-validated envelopes с version/fetched/expiry;
- [x] expired copy явно помечается stale, повреждённая удаляется, а fallback
      разрешён только для настоящей сетевой ошибки;
- [x] audited hint повторно открывается offline, но unaudited или заменённая
      publication не может использовать старый cached reveal;
- [x] document budget — 10 MiB/500 записей на owner; oldest-first eviction,
      owner separation и corrupt-record recovery покрыты unit-тестами;
- [x] production browser flow после холодной перезагрузки с недоступным API
      читает condition/hint, а после login второго Student доказывает отсутствие
      утечки первого owner во всех трёх браузерах;
- [x] полный regression **283 TS + 1101 Python PASS**, Storybook **182 PASS**,
      strict checks и production build PASS, browser checkpoint **3/3 PASS**.

Proof:
[`phase3-student-offline-reading.md`](../../../pwa_tests/reports/phase3-student-offline-reading.md).

Промежуточный gate **Phase 3H — длинный реальный листок и KaTeX performance**
реализован 28 июля 2026, revision `f787a64`:

- [x] stress-fixture состоит из четырёх независимых копий настоящих условий
      занятий 39–41: 132 задачи и 56 клиентских формул;
- [x] browser harness измеряет переход от React action до завершения всех
      `MathExpression`, а не загрузку Storybook;
- [x] мягкий catastrophic-regression budget 2500 мс прошёл; полный interaction
      test занял 672 мс на текущем локальном Chromium run;
- [x] точные counts, отсутствие invalid/pending KaTeX и fallback недоступного
      SVG с сохранённой подписью проверяются независимо от wall-clock;
- [x] focused unit **7 PASS**, полный regression **285 TS + 1101 Python PASS**,
      Storybook browser **183 PASS**, strict checks и production build PASS;
      snapshots не обновлялись.

Proof:
[`phase3-long-math-rendering.md`](../../../pwa_tests/reports/phase3-long-math-rendering.md).

- [x] Revision/migrations: `1aeb78d`, `8448a8b`, `fabdf93`, `50cd541`,
      `d4b0b9b`, `89cefb7`, `bb6c6ef`, `d822e2e`; public identity — `0044`,
      exact material-match reveal trigger — `0045`; paths перечислены в proof.
- [x] Demo Student Now/list/long/focused/offline: Now + lesson archive +
      canonical problem status + focused condition + audited hint reveal +
      cold API failure + account switch **3/3 PASS**.
- [x] Lesson list query/read contract: один bounded SQLite statement; proof выше.
- [x] Home query count/plan and response contract: bounded single statement,
      Zod fixture и browser proof в `phase3-student-home.md`.
- [x] Hint/solution authorization + reveal events: exact current-publication
      projection, immutable/idempotent audit, **34 HTTP PASS**, production
      browser **3/3 PASS**; proof выше.
- [x] Dexie cache/quota/isolation tests: strict envelope, stale/corrupt records,
      10 MiB/500-entry eviction, auth expiry/logout/account switch и owner
      separation входят в общий **283 TS PASS**.
- [ ] Storybook priority stories, interactions, a11y, visuals:
      `product-courses--allowed-group-reading-context` и
      `product-reading--audited-reveal-recovery`,
      `product-reading--offline-last-copy`, suite **182 PASS**; visual owner
      gate открыт, snapshots не обновлялись.
- [x] Playwright online/offline/deep-link 3 browsers: online
      home→course/group archive→URL-selected lesson→opaque problem URL→focused
      condition→audited hint→cold reload/API failure→online rollback→login
      второго Student→offline cache-isolation **3/3 PASS**.
- [x] Performance evidence long math document/KaTeX: 132 реальных corpus-задачи,
      56 формул, browser budget ≤2500 мс и SVG load-error PASS; proof
      `phase3-long-math-rendering.md`.
- [x] Docs/cache policy/known limitations/acceptance:
      `phase3-student-offline-reading.md`, 28 июля 2026.

## Многокурсовый инкремент Phase 3

«Сейчас» показывает карточку каждого course enrollment. Tasks и focused task используют validated `course/group/lesson`; query/cache/draft keys не смешивают курсы. Отозванный group access скрывает новые материалы, но сохраняет собственную старую историю.

Дополнительный proof: `Pages/Student--today-multiple-courses`, `--tasks-course-and-group`, offline cache isolation и deep links двух курсов; `Pages/Family--activity-by-course` read-only parity.

## Pilot correction: читаемый листок — 14 августа 2026

- Читаемый URL показывает номер и название занятия; статус каждой задачи
  остаётся виден, а формы ответа свёрнуты. Подсказка, решение и компактная
  кнопка переписки находятся вне формы сдачи.
- После дедлайна редакторы тестового и письменного ответа не создаются;
  ранее отправленные ответы и проверки остаются доступны.
- Рисунок масштабируется реальным размером canvas внутри прокручиваемой области,
  поэтому увеличение не создаёт пустой отступ и не обрезает края.
- Открытие вопроса по задаче сначала находит существующий thread; composer
  открывается только по кнопке. Сообщение и письменное решение отправляются по
  `Cmd+Enter`/`Ctrl+Enter`.
- Архив выбранной доступной группы перепроверяется при открытии страницы и
  возвращении в окно; offline-копия используется только при сетевой ошибке.

Реализация: [`student-readable-task-page.tsx`](../../apps/student/src/student-readable-task-page.tsx),
[`student-task-detail-page.tsx`](../../apps/student/src/student-task-detail-page.tsx),
[`student-support-pages.tsx`](../../apps/student/src/student-support-pages.tsx),
[`zoomable-asset-figure.tsx`](../../packages/content/src/zoomable-asset-figure.tsx),
[`course-client.ts`](../../packages/app-shell/src/course-client.ts).
