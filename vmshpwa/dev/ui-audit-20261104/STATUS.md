# UI-аудит 4 ноября 2026 — статус

- 2026-11-04: два независимых аудита (Claude, Codex) сведены в [BACKLOG.md](BACKLOG.md). Около 130 уникальных проблем; дубли объединены, ID обоих отчётов сохранены. Недоступные старые изображения исключены (S3 на beget).
- 2026-11-04, решения владельца по фазе 1: 1A.7 (9п.4) — не баг; 1A.10 (Zod JSON) — отложено; 1B.14 — переносы в условиях оставить, убрать только из UI; 1B.15 — эмодзи оставить, вердикт сделать заметнее; 1B.16 — Enter остаётся переводом строки; 1B.24 (`#` в новости) — проблема контента. Модель часовых поясов (курс + пользователь) — отложена, см. конец BACKLOG.md.

## Фаза 1 — сделано (не закоммичено)

| Пункт                               | Реализация                                                                                                                                                              |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1A.1 меню Staff                     | `packages/app-shell/src/app-shell.tsx` — у aside собственная прокрутка                                                                                                  |
| 1A.2 журнал изменений               | `packages/contracts/src/audit.ts` (`offset: true`), тест `audit.test.ts`                                                                                                |
| 1A.3 текст ошибки чтения            | `packages/app-shell/src/page-layout.tsx`                                                                                                                                |
| 1A.4 московское время               | `classroom-assignment-page.tsx`, `classroom-layout-page.tsx` (МСК), `oral-weekly-draft.tsx`, `staff-oral-windows-page.tsx` (ввод и показ в Москве вместо зоны браузера) |
| 1A.5 выбор события                  | `live-marking-page.tsx`, `classroom-event-page.tsx` — дата и время                                                                                                      |
| 1A.6 «Группа пуста»                 | `packages/product/src/classroom-planning.tsx` — «Нет очных школьников» / «Ещё не распределены», склонение аудиторий                                                     |
| 1A.8 сезон                          | `packages/product/src/course-admin.tsx`                                                                                                                                 |
| 1A.9 «синхронизировано»             | убрано из `app-shell.tsx`                                                                                                                                               |
| 1A.11 закреплённая колонка          | `packages/product/src/metadata-grid-table.tsx`                                                                                                                          |
| 1A.12 тестовые аккаунты             | `db_methods/pwa/student_results.py`, `db_methods/pwa/family_digest.py`; тест в `pwa_tests/integration/test_staff_testing_http.py`                                       |
| 1B.13 офлайн-строка и push          | `ShellNoticeArea` в `page-layout.tsx`, корни student/family, `student-offline-preparation.tsx`                                                                          |
| 1B.14 переносы в UI                 | `packages/content/src/content.css` — `hyphens: manual` для `.font-sans`/полей внутри листка                                                                             |
| 1B.15 вердикт                       | `ProblemStatusBadge` в `student-task-detail-page.tsx`                                                                                                                   |
| 1B.16 нижняя навигация, тост        | `scroll-padding-bottom` в `app-shell.tsx`; компактный `pwa-update.tsx`                                                                                                  |
| 1B.17 шапка урока                   | `content-page.tsx` («Курс · Группа / Занятие N»), перенос действий в `PageLayout`                                                                                       |
| 1B.18 технические строки            | `time-zone-label.ts`, «Admin»/«Admin only»/«all»/«metadata»/ISO-время в учёте работы                                                                                    |
| 1B.19 склонения                     | дашборд, рабочее место проверки, аудитории                                                                                                                              |
| 1B.20 достижения                    | `packages/product/src/student-progress.tsx`                                                                                                                             |
| 1B.21 «Задать вопрос организаторам» | `student-home-page.tsx` — в действия шапки                                                                                                                              |
| 1B.22 опасные действия              | «Закрыть приём сейчас» — destructive + подтверждение; «Удалить школьника» — маленькая, справа внизу                                                                     |
| 1B.23 «План не рассчитан»           | info-тон вместо ошибки                                                                                                                                                  |

## Проверки

- `pnpm format:check`, `typecheck`, `eslint`, `lint:css`, `i18n:check` — PASS.
- Vitest unit: 1123/1123 PASS.
- pytest `tests` + `pwa_tests`: 3007 PASS, 1 FAIL — `test_database_performance_guard.py::test_guard_rejects_a_correlated_full_scan_and_accepts_indexed_lookup`: синтетическая схема, не связана с изменениями, падает и отдельно.
- `make pwa-check-fast` останавливается на `python-dependencies`: в `.venv` 15 пакетов вне lock (mcp, uvicorn…); `uv sync` их удалил бы — не запускался.
- E2E (Chromium/WebKit/Firefox, по режимам): content 6, classrooms+review+submissions 33, organizers 9, student-results 9, oral 15, oral-windows 3, live-marking 15, news 18, rich-files 9 — PASS после обновления подписей в спеках (`fef930ac`). rich-files один раз упал в Chromium на шаге входа (нет редиректа на /staff/login), повтор зелёный — нестабильность, не связанная с изменениями.
- Визуально на agent runtime: меню Staff (1280×720), шапка урока, «Аудитории» (время, состояния групп), Zoom-окна, «Сейчас» и задачи школьника (375 px), переносы.

## Часовые пояса (2026-11-04, не закоммичено)

Ввод и показ разовых времён — в поясе браузера, время курса (МСК) рядом; подробности и файлы — в разделе «Часовые пояса» BACKLOG.md. Проверки: format/types/eslint/i18n PASS, Vitest 1128/1128. Вживую в поясе Asia/Nicosia: дедлайн «18:30» в Staff сохранился как 16:30Z (19:30 МСК), школьник видит «до 15 ноября в 18:30 (19:30 МСК)».

## Известные хвосты

- Страницы Zoom-приёма всё ещё показывают «Групповое занятие gl-N» в надзаголовке.

## Фаза 2 (2026-11-05, одним релизом, не закоммичено)

Решение владельца: фаза 2 выкатывается одним релизом, полный E2E — один раз перед выкаткой. Ответы Q1–Q12 и разбор Q12 — в BACKLOG.md. Правило: только перекомпоновка, ни одна функция не убрана.

| Тема | Реализация |
| --- | --- |
| O1–O4 каркас школьника | `app-shell.tsx` (имя на одной линии с брендом, ширина меню), `student-home-page.tsx`/`pages.tsx` (без надзаголовка «Ваши курсы», один курс — во всю ширину), `group-banner.tsx` (карточка, заголовки не крупнее страницы), `level-chip.tsx`, `course-context.tsx` (переключатель групп без рамки в рамке) |
| Q1 статус офлайна | `student-offline-preparation.tsx` — молчит при успехе, показывает только ошибку с «Повторить» и истёкший вход; `data-state` для E2E (`offline-current-lessons.spec.ts`, `shells.spec.ts`) |
| Q2 материалы листка | `student-tasks-view.ts` (`publishedMaterialLabel` → null без подсказки/решения), `student-tasks-page.tsx` (бейдж с лампочкой; надзаголовок «Занятие N» только над своим названием, дата — в подписи) |
| Q3 повторная отправка | `chat-composer.tsx` (`sendVariant`), `student-test-answer.tsx` — «Отправить ещё раз» вторичной кнопкой после «Зачтено»; `test-submission.spec.ts` |
| A1 образец ответа | `test-answer.tsx` — пример только в подсказке под полем, не плейсхолдером |
| Q5 аудитории | `classroom-event-page.tsx` — те же галочки в `<details>`, сводка выбранного, порядок по группам |
| Q6 формы ниже данных | `CollapsibleCreateSection` в `page-layout.tsx`; `staff-news-page.tsx`, `staff-group-banners-page.tsx`; пустой пакет web-входов — одна строка (`student-account-batch-panel.tsx`); E2E `news-notifications`, `rich-file-attachments` |
| Q9 уведомления | `student-notifications-page.tsx` — лента сверху, «Настройки уведомлений» ниже |
| Q10 навигация Staff | `routes/__root.tsx` (группы Работа/Материалы/Люди/Связь/Администрирование, разные иконки), `app-shell.tsx` (заголовки групп, active ≠ hover) |
| Q11 лендинг | `apps/landing/src/landing-page.tsx` — главная кнопка у кабинета школьника |
| 2.2 вкладки | `sectionTabClassName`/`sectionTabsClassName` в `page-layout.tsx`; `routes/review.tsx`, `routes/questions.tsx`, `routes/statistics.tsx`; `TabsList variant="line"` в аудиториях |
| Вход | `apps/{staff,student,family}/src/login-page.tsx` — шапка и форма на одной оси; без «admin — административные разделы» |
| Проверка | `review-workspace-page.tsx` (в серии заголовок — школьник, без третьего повтора задачи; «Отказаться» — кнопка), `review-sheet-card.tsx` |
| Урок | `content-page.tsx` — своя кнопка выбора LaTeX-файла вместо «Choose File / No file chosen» |
| Рисунки на телефоне | `packages/content/src/content.css` — минимум 11rem до 40rem ширины |
| Zoom-окна | `oral-weekly-draft.tsx` — даты не обрезаются, легенда, «Добавить ещё окно» кнопкой |
| Сводка | `staff-dashboard-page.tsx` — «Уведомления об аудиториях», понятная строка устных окон |
| Реакции, тестирование, курсы, MCP, результаты | `review-reaction-inbox.tsx`, `staff-testing-page.tsx`, `course-admin.tsx`, `mcp-access-page.tsx` (копирование), `student-results-page.tsx` (отчество в имени) |
| Профиль, новости, вопросы | `student-profile-page.tsx` (карточки не растягиваются), `student-news-page.tsx` (карточка с датой и источником), `student-support-pages.tsx` («К задаче») |
| Аварийный экран | `packages/i18n/src/catalog-failure.ts` — два языка отдельными блоками |
| Старые сторис | `content-page.stories.tsx`, `staff-local-news-composer.stories.tsx` — подписи после перехода на пояс браузера |

Не сделано в фазе 2 (остаётся в BACKLOG): Q7 учёт работы и Q8 сеансы — по решению владельца; подписи Q12 ждут решения; поиск/фильтры списка уроков (UI-12); плотность очереди проверки (F6); панель пометок и размер фото в проверке (X15–X17); таблица метаданных (X6–X9); график прогресса (P2); родные file-input в импорте задач, пакетной загрузке и публикации; ленивый рендер (T2), гонка `useAuthenticatedPrincipal` (N3), `pwa-agent-dev` на свежем checkout, несколько `--mode` в `e2e_runner`.

Проверки: typecheck, eslint, i18n:check — PASS; Vitest 1152/1152; Storybook 384/384.

E2E фазы 2, Chromium (одним прогоном `e2e_runner --mode all --browser chromium`, затем добивка этапов после первой остановки):
- основной набор: 141 PASS, 2 FAIL в `e2e/i18n.spec.ts` — ожидания старых текстов («New PWA publication» теперь за кнопкой «New post»; заголовок урока «LaTeX and publications» заменён фазой 1 на «Class N»). Спека исправлена, режим i18n — 12/12 PASS;
- `figure-layout` 1/1, статистика (`playwright.statistics.config.ts`) 3/3 PASS — запущены напрямую `playwright test` после того, как раннер остановился на первом этапе;
- `@visual`: «student current week» и «staff weekly dashboard» разошлись ожидаемо (шапка школьника, карточка объявления, группы меню, строка устных окон). Диффы просмотрены, эталоны обновлены для Chromium, WebKit и Firefox (просмотрен WebKit), 6/6 PASS.

Выкатка фазы 2 (2026-11-05): `3a633879` → выпуск `ui-audit-20261104-3a633879503d` на vmsh.shashkovs.ru и prep.leaders.tech — оба PASS (25 read-only HTTP-проверок, онлайн-бэкапы, конфигурация и NATS сохранены; на VMSh сохранены три посторонние правки). Записи — `/web/vmsh_tasks_bot/deploy/releases/ui-audit-20261104-3a633879503d/result.json` на каждом сервере.

## Q12 (2026-11-05)

Оба лимита попыток считают только неверные ответы (`db_methods/pwa/submissions.py`); подпись лимита скрыта до первой ошибки, затем «Осталось ошибок: N за час · M за день»; прогресс «N задач зачтено · начато M». Проверки: pytest по отправкам 207 PASS, Vitest 1152, Storybook 384, i18n/types/lint PASS, E2E submissions (Chromium) 3/3.
