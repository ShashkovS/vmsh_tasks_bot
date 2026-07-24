# Этап 3. Student «Сейчас», уроки и офлайн-чтение

## Результат

Авторизованный школьник открывает «Сейчас», видит фазу недели, свой текущий урок, требующие внимания задачи, новости/баннеры и корректные unread states. Он читает длинный лист, работает с любой задачей из `allowed_groups`, видит обновлённое условие и повторно открывает кеш без сети.

## Backend/read models

- `GET home`, lesson list/detail, problem detail, available groups, active banners.
- Read model учитывает active group, полный action access по `allowed_groups`, online mode, publication revisions, latest results и week phase.
- Natural task order сохраняет порядок листка; attention order отделён от canonical list.
- Hint/solution endpoint проверяет publication, просит confirmation в UI и пишет reveal event.
- Group/mode changes доступны Student и Family, немедленно меняют текущие задачи, пишут `user_changes_log` и invalidation; история старых групп остаётся.
- Ответ содержит `contentRevision`, `entityVersion`, `cachePolicy`, server time и solution deadline.

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

- Home priority/domain tests across week phases, group/mode and result states.
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

- [ ] Revision/migrations: `<sha/paths>`; integrity/index plans `<path>`.
- [ ] Demo Student Now/list/long/focused/offline: `<seed/routes/evidence>`.
- [ ] Home query count/plan and response contract: `<path/result>`.
- [ ] Hint/solution authorization + reveal events: `<tests/result>`.
- [ ] Dexie cache/quota/isolation tests: `<result>`.
- [ ] Storybook priority stories, interactions, a11y, visuals: `<ids/paths>`.
- [ ] Playwright online/offline/deep-link 3 browsers: `<result>`.
- [ ] Performance evidence long math document/KaTeX: `<path/result>`.
- [ ] Docs/cache policy/known limitations/acceptance: `<paths/issues/name/date>`.
