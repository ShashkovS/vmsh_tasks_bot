# Статус плана разработки

Последнее обновление: 2026-07-26.

## Состояние документов

| Документ/этап       | Статус                                | Решение/блокер                                                                                     |
| ------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Инженерный контракт | draft for approval                    | Формат proof описан; фактически заполняется при реализации                                         |
| Решения и границы   | reviewed input                        | Исходный опросник закрыт; 4 новые развилки ревью зафиксированы в `17-open-questions.md`            |
| Модель данных       | revised planning input                | Cutoff, season backfill, analytics snapshots и reaction migration уточнены                         |
| API/events/files    | accepted planning input               | Batch move, cross-group confirm и classroom history зафиксированы                                  |
| Этап 0              | ready                                 | Вопросы ревью не блокируют baseline/preflight; добавлены DB/auth/load/external gates               |
| Этапы 1–11          | planned with gates                    | `SCHEDULE-01`, `AUTH-01`, `CLASSROOM-01`, `RETENTION-01` блокируют только названные cutover        |
| Design system       | phases 5–7 ready for review           | [Этапы связаны](18-design-implementation-map.md) с components/story IDs; остался ручной owner gate |
| Multi-course model  | verified prototype; owner visual gate | Phase 1–11, UI, stories и tests обновлены; backend/migrations не реализованы                       |

## Журнал решений

| Дата       | ID       | Решение                                                                                                  | Последствие                                                                                                                                        |
| ---------- | -------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-23 | PLAN-001 | Этапы строятся как вертикальные работающие срезы                                                         | Backend/UI/contracts/tests/docs закрываются вместе                                                                                                 |
| 2026-07-23 | PLAN-002 | E2E и visual regression выполняются на production Vite build/preview                                     | Dev server остаётся для локальной разработки, но не proof релизного поведения                                                                      |
| 2026-07-23 | PLAN-003 | A11y gate остаётся для Staff                                                                             | Не создаётся отдельный исключённый контур                                                                                                          |
| 2026-07-23 | PLAN-004 | Reconnect всегда вызывает authoritative refetch                                                          | WS cursor не используется как доказательство отсутствия пропусков между workers                                                                    |
| 2026-07-23 | PLAN-005 | `_vmsh_examples` — golden corpus, `_external_pipelines` — characterization references                    | Их не редактируют и не импортируют в новый production runtime                                                                                      |
| 2026-07-24 | PLAN-006 | Первый выпуск: сезон 2025–2026, занятия 39–41, все три уровня                                            | Вертикальные этапы должны привести к полному онлайн-занятию, а не к pilot одной группы                                                             |
| 2026-07-24 | PLAN-007 | Telegram остаётся двусторонним рабочим каналом на переходе                                               | Треды и provenance объединяют PWA и Telegram; все external pipelines сохраняются до cutover                                                        |
| 2026-07-24 | PLAN-008 | Печатный/очный раздел, Staff→Telegram и AI перенесены во вторую версию                                   | Эти функции не блокируют первый рабочий выпуск                                                                                                     |
| 2026-07-24 | PLAN-009 | Исходный продуктовый опросник закрыт                                                                     | Новые вопросы добавляются только при реальной развилке реализации                                                                                  |
| 2026-07-24 | PLAN-010 | Ответы разнесены по модели, API, этапам и эксплуатационным документам                                    | Этап 0 можно начинать без повторного сбора продуктовых требований                                                                                  |
| 2026-07-24 | PLAN-011 | Аудитории разделены на глобальный каталог, наследуемую схему по группам и версионируемый план школьников | Этап 7 получает admin-only catalog/layout/preview/confirm, без capacity и drag-and-drop; initial Excel используется один раз через dry-run/import  |
| 2026-07-25 | PLAN-012 | Classroom planner использует compact single/bulk select и локально накопленный draft                     | Каждая смена select не пишет на server; reload восстанавливает draft, batch-save атомарен, cross-group move требует confirmation                   |
| 2026-07-25 | PLAN-013 | Classroom read model показывает age/class/auto-strength, aggregates, fuzzy search и history              | `users`/`student_strength` остаются источниками; nullable values не входят в averages; confirmed plans образуют историю                            |
| 2026-07-25 | PLAN-014 | Незавершённую значимую работу Student/Staff нельзя терять                                                | `localStorage` хранит serializable drafts, Dexie — blobs/outbox; очистка только после receipt/confirm/discard                                      |
| 2026-07-25 | PLAN-015 | Ребёнок никогда не отмечается на групповой статистике                                                    | Self marker, percentile и словесное сравнение с группой запрещены в Student/Family charts                                                          |
| 2026-07-25 | PLAN-016 | Test input повторяет 23 legacy-типа и `strip()+fullmatch`                                                | Видимая format error; tuple без «Отправится»; list preview после parsing; select передаёт видимый label                                            |
| 2026-07-25 | PLAN-017 | Review — хронологическая основная колонка, teacher controls компактны, но подписаны                      | Evidence, существующий thread и новый ответ не разделяются на три независимые панели                                                               |
| 2026-07-25 | PLAN-018 | Condition, hint и solution публикуются независимо; metadata имеет task/answer dropdown                   | У каждого artifact своё «сейчас»/расписание/rollback; TSV paste сохраняется                                                                        |
| 2026-07-25 | PLAN-019 | Условия идут полноценным Telegram Rich Message, а broadcast editor переносится во вторую фазу            | Stories используют text/math/lists и export corpus; v1 не имитирует рассылку, отдельная submission-квитанция отсутствует                           |
| 2026-07-25 | PLAN-020 | Client format validation не мешает незавершённому вводу                                                  | `TestAnswer` раскрывает ошибку после blur/submit; fixed tuple остаётся спокойным между слотами; weekday использует кнопки `пн–вс`                  |
| 2026-07-25 | PLAN-021 | Authoritative schema — применённые migrations + проверенный inventory, не старый snapshot в одиночку     | Этап 0 проверяет/перегенерирует `docs/db_structure.sql`; runtime schema drift обнаруживается до business migration                                 |
| 2026-07-25 | PLAN-022 | SQLite concurrency и migration lifecycle становятся обязательным ADR до первой бизнес-миграции           | Нет общего concurrent connection/`await` в transaction; yoyo запускается отдельным deploy command, startup только проверяет version                |
| 2026-07-25 | PLAN-023 | Submission cutoff и solution publication моделируются раздельно                                          | `lesson_windows.submission_closes_at` существует заранее; policy переноса расписания вынесена в `SCHEDULE-01`                                      |
| 2026-07-25 | PLAN-024 | Legacy analytics переносится versioned full-run snapshots, история текущего сезона backfill-ится         | `a53`/`a54` получают numerical parity; занятия 1–38 не исчезают из history/progress из-за отсутствия новых publication rows                        |
| 2026-07-25 | PLAN-025 | Каждый внешний процесс имеет legacy bridge и конечного внутреннего владельца                             | `a00_dates`, `a03`, print/analytics/old-site chains добавлены в register; «не v1» больше не означает бессрочно внешний процесс                     |
| 2026-07-25 | PLAN-026 | Внешнее ревью открыло четыре новые продуктовые развилки без блокировки этапа 0                           | Production cutover соответствующих фаз ждёт ответов `SCHEDULE-01`, `AUTH-01`, `CLASSROOM-01`, `RETENTION-01`                                       |
| 2026-07-25 | PLAN-027 | У каждого этапа есть явный design implementation map                                                     | Phase-файл ведёт к компонентам, story source и URL; изменение accepted UI обновляет код, story, карту и status вместе                              |
| 2026-07-26 | PLAN-028 | Internal teacher reactions получают компактный Mod+Alt shortcut                                          | `⌘/Ctrl + Alt + 1…4` работает при фокусе в комментарии; простой Mod+digit оставлен браузеру, `AltGraph` игнорируется                               |
| 2026-07-26 | PLAN-029 | Внешние converter binaries задаются общим backend config и разрешаются через service `PATH`              | Defaults: `pdf2svg`, `cwebp`, `pdflatex`, `magick`; absolute override/`None` явны, readiness/deploy проверяют capabilities до первого задания      |
| 2026-07-26 | PLAN-030 | S3 adapter использует общий profile-aware backend config для Beget                                       | Local/manual integration читает allowlisted `s3_*` из test config, production — из prod; agent/E2E остаются filesystem, secrets всегда redacted    |
| 2026-07-26 | PLAN-031 | Telegram channel destination хранится отдельно для каждой группы в SQLite                                | `@vmsh179devbot` + private test channel используются opt-in; Bot API canonical ID/rights проверяются, token остаётся config-only, unit/E2E offline |
| 2026-07-26 | PLAN-032 | Принята иерархия season→course→group→lesson, логические синонимы и multi-course in-person events         | Фазы 1–11 дополнены; Storybook prototype реализован; production backend/migrations остаются невыполненными                                         |

## Проверка многокурсового прототипа

Проверено 26 июля 2026 года:

- `make pwa-lint`, `make pwa-typecheck`, `make pwa-test`, `make pwa-storybook-test`, `make pwa-build` — успешно;
- unit: 4 файла / 29 тестов; Python PWA: 11 тестов; Storybook browser mode: 31 файл / 137 тестов с `addon-a11y` в режиме error;
- production build всех трёх приложений и отдельный Storybook build — успешно; Student/Family собрали `injectManifest` service workers с 103/102 precache entries;
- локальные ссылки проверены в 48 Markdown-файлах; `git diff --check` — успешно;
- вручную в agent Storybook просмотрены mobile-light Student/Family и desktop Staff/course/synonym/progress/classroom stories из [карты design→implementation](18-design-implementation-map.md);
- production visual без обновления snapshots: Staff baseline совпал в Chromium/WebKit/Firefox; Student current week ожидаемо отличается во всех трёх браузерах (1188→1615 px, около 4% пикселей) из-за новой многокурсовой композиции;
- visual snapshots намеренно не обновлены до решения владельца;
- backend endpoints, migrations и production wiring не реализованы и не считаются proof завершения фаз 1–11.

## Фактические proof этапов

Пока отсутствуют: это план, а не отчёт о реализации. При завершении этапа сюда добавляется одна строка со ссылкой на заполненный proof-раздел соответствующего phase-файла.

| Этап | Revision | Proof | Принято |
| ---: | -------- | ----- | ------- |
|    0 | —        | —     | —       |
|    1 | —        | —     | —       |
|    2 | —        | —     | —       |
|    3 | —        | —     | —       |
|    4 | —        | —     | —       |
|    5 | —        | —     | —       |
|    6 | —        | —     | —       |
|    7 | —        | —     | —       |
|    8 | —        | —     | —       |
|    9 | —        | —     | —       |
|   10 | —        | —     | —       |
|   11 | —        | —     | —       |
