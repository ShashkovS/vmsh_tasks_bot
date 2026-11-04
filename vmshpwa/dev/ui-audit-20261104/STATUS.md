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
