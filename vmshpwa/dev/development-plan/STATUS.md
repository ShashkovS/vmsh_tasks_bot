# Статус плана разработки

Последнее обновление: 2026-07-25.

## Состояние документов

| Документ/этап       | Статус                    | Решение/блокер                                                     |
| ------------------- | ------------------------- | ------------------------------------------------------------------ |
| Инженерный контракт | draft for approval        | Формат proof описан; фактически заполняется при реализации         |
| Решения и границы   | accepted input            | Полный опросник и classroom-уточнения закрыты 25 июля              |
| Модель данных       | accepted planning input   | Classroom profile/rating/history/draft projection синхронизирована |
| API/events/files    | accepted planning input   | Batch move, cross-group confirm и classroom history зафиксированы  |
| Этап 0              | ready                     | Блокирующих продуктовых вопросов нет                               |
| Этапы 1–11          | planned                   | Scope и переносы между первой/второй версией уточнены              |
| Design system       | external work in progress | Фактический статус ведётся в соседнем `../design-system/STATUS.md` |

## Журнал решений

| Дата       | ID       | Решение                                                                                                  | Последствие                                                                                                                                       |
| ---------- | -------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-23 | PLAN-001 | Этапы строятся как вертикальные работающие срезы                                                         | Backend/UI/contracts/tests/docs закрываются вместе                                                                                                |
| 2026-07-23 | PLAN-002 | E2E и visual regression выполняются на production Vite build/preview                                     | Dev server остаётся для локальной разработки, но не proof релизного поведения                                                                     |
| 2026-07-23 | PLAN-003 | A11y gate остаётся для Staff                                                                             | Не создаётся отдельный исключённый контур                                                                                                         |
| 2026-07-23 | PLAN-004 | Reconnect всегда вызывает authoritative refetch                                                          | WS cursor не используется как доказательство отсутствия пропусков между workers                                                                   |
| 2026-07-23 | PLAN-005 | `_vmsh_examples` — golden corpus, `_external_pipelines` — characterization references                    | Их не редактируют и не импортируют в новый production runtime                                                                                     |
| 2026-07-24 | PLAN-006 | Первый выпуск: сезон 2025–2026, занятия 39–41, все три уровня                                            | Вертикальные этапы должны привести к полному онлайн-занятию, а не к pilot одной группы                                                            |
| 2026-07-24 | PLAN-007 | Telegram остаётся двусторонним рабочим каналом на переходе                                               | Треды и provenance объединяют PWA и Telegram; все external pipelines сохраняются до cutover                                                       |
| 2026-07-24 | PLAN-008 | Печатный/очный раздел, Staff→Telegram и AI перенесены во вторую версию                                   | Эти функции не блокируют первый рабочий выпуск                                                                                                    |
| 2026-07-24 | PLAN-009 | Исходный продуктовый опросник закрыт                                                                     | Новые вопросы добавляются только при реальной развилке реализации                                                                                 |
| 2026-07-24 | PLAN-010 | Ответы разнесены по модели, API, этапам и эксплуатационным документам                                    | Этап 0 можно начинать без повторного сбора продуктовых требований                                                                                 |
| 2026-07-24 | PLAN-011 | Аудитории разделены на глобальный каталог, наследуемую схему по группам и версионируемый план школьников | Этап 7 получает admin-only catalog/layout/preview/confirm, без capacity и drag-and-drop; initial Excel используется один раз через dry-run/import |
| 2026-07-25 | PLAN-012 | Classroom planner использует compact single/bulk select и локально накопленный draft                     | Каждая смена select не пишет на server; reload восстанавливает draft, batch-save атомарен, cross-group move требует confirmation                  |
| 2026-07-25 | PLAN-013 | Classroom read model показывает age/class/auto-strength, aggregates, fuzzy search и history              | `users`/`student_strength` остаются источниками; nullable values не входят в averages; confirmed plans образуют историю                           |
| 2026-07-25 | PLAN-014 | Незавершённую значимую работу Student/Staff нельзя терять                                                | `localStorage` хранит serializable drafts, Dexie — blobs/outbox; очистка только после receipt/confirm/discard                                     |
| 2026-07-25 | PLAN-015 | Ребёнок никогда не отмечается на групповой статистике                                                    | Self marker, percentile и словесное сравнение с группой запрещены в Student/Family charts                                                         |
| 2026-07-25 | PLAN-016 | Test input повторяет 23 legacy-типа и `strip()+fullmatch`                                                | Видимая format error; tuple без «Отправится»; list preview после parsing; select передаёт видимый label                                           |
| 2026-07-25 | PLAN-017 | Review — хронологическая основная колонка, teacher controls компактны, но подписаны                      | Evidence, существующий thread и новый ответ не разделяются на три независимые панели                                                              |
| 2026-07-25 | PLAN-018 | Condition, hint и solution публикуются независимо; metadata имеет task/answer dropdown                   | У каждого artifact своё «сейчас»/расписание/rollback; TSV paste сохраняется                                                                       |
| 2026-07-25 | PLAN-019 | Условия идут полноценным Telegram Rich Message, а broadcast editor переносится во вторую фазу            | Stories используют text/math/lists и export corpus; v1 не имитирует рассылку, отдельная submission-квитанция отсутствует                          |
| 2026-07-25 | PLAN-020 | Client format validation не мешает незавершённому вводу                                                  | `TestAnswer` раскрывает ошибку после blur/submit; fixed tuple остаётся спокойным между слотами; weekday использует кнопки `пн–вс`                 |

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
