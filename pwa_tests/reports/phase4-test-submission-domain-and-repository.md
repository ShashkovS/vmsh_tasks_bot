# Phase 4A–4G — правила, хранение, Student/Staff UI, E2E и Telegram policy

Дата: 2026-07-28

Revisions: `6409191`, `bd0487f`, `1d5df54`, `7793d0f`, `0475cd0`,
`6d1909c`, `bab5947`, `5b682d1`, `3d22373`, `a779493`, `6268092`,
`9358e76`, `2b00b06`, `e5b83a4`, `0fde237`

## Проверяемый результат

Каркас Phase 4 теперь содержит доменные правила всех исторических типов
тестового ответа, атомарный SQLite repository, authenticated Student HTTP
вертикаль, браузерный transport, local draft, Dexie outbox и Staff-поток
повторной проверки отложенных попыток после исправления конфигурации. Production
Student и Staff pages и сквозной Playwright path готовы, а Telegram и PWA
используют одну domain normalization/verdict policy. Инкремент ещё не считается
завершением всего этапа из-за ручного visual gate и отдельной будущей миграции
исторического Telegram persistence в structured attempt ledger. Последнее не
является gate Phase 4: legacy Telegram намеренно остаётся совместимым adapter.

Реализовано:

- additive migration `0046.pwa_test_attempts_idempotency.sql` с immutable попытками,
  idempotency ledger и snapshot версии checker/config;
- поддержка всех 23 значений legacy `ANS_TYPE`, включая точные правила
  `strip()` + `fullmatch`, несколько `cor_ans` через `;` и visible-label
  семантику `SELECT_ONE`;
- совместимый trusted-admin executor `cor_ans_checker` с тем же ограниченным
  окружением, которое использует legacy bot;
- безопасный `pending_configuration`, если checker отсутствует или не может
  быть выполнен: школьнику не возвращаются source code и traceback;
- отдельный format outcome, который сохраняется, но не расходует лимит попыток;
- server-authoritative cutoff и сохранение client/server timestamps. Ответ,
  созданный на клиенте до cutoff и доставленный позже, принимается, а
  расхождение часов больше часа получает audit-флаг;
- календарные hour/day limits в business timezone группового занятия:
  по умолчанию 3/6, с поддержкой явного unlimited или отключения отдельного
  измерения;
- idempotency key на операцию `test-attempt:create`: одинаковый canonical
  payload возвращает сохранённый response, другой payload получает `409`;
- атомарная запись новой попытки и ровно одной legacy-compatible строки
  `results`. Ошибка между вставками откатывает обе записи;
- повторная тестовая сдача после правильного ответа разрешена, а попытки и
  rate limits остаются привязанными к исходному `problem_id`.

## Wire и HTTP

Strict Zod contract и versioned fixtures находятся в
`vmshpwa/packages/contracts/src/submissions.ts` и
`vmshpwa/packages/contracts/fixtures/submissions/`. Они фиксируют:

- request `schemaVersion`, canonical UUID, expected `problemRevision`, исходный
  `displayAnswer` и UTC `clientCreatedAt`;
- согласованные `outcome`, `checkStatus`, nullable verdict/result version,
  user-facing feedback и лимиты;
- owner/problem-scoped query keys и безопасную reverse-chronological history;
- отсутствие client-controlled `studentId`, правильного ответа, checker source
  и внутренних SQLite ID.

`apps/pwa_api/submission_routes.py` реализует:

- `POST /student/api/v1/problems/{problemPublicId}/test-attempts`;
- `GET /student/api/v1/problems/{problemPublicId}/test-attempts?cursor=`;
- strict JSON/body/time/UUID validation и общий correlated error envelope;
- revalidated cookie identity вместо identity из payload;
- owner-scoped `problems/{problemId}/test-attempts` invalidation только после
  нового commit. Exact replay не создаёт вторую invalidation;
- историю до 50 строк на страницу. Пустая история требует текущего доступа,
  но собственная старая работа остаётся видимой после отзыва group access.

После admin recheck история предпочитает authoritative attempt state
и не соединяет его со stale feedback старого idempotency receipt.

## Staff recheck после исправления конфигурации

Revisions `e5b83a4`, `0fde237` закрывают Staff recheck/configuration-repair
вертикаль для нового attempt ledger:

- `GET` и `POST`
  `/staff/api/v1/problems/{problemPublicId}/recheck-test-attempts` дают preview
  и применяют повторную проверку только пользователю с `checker.manage`;
- repository выбирает только `pending_configuration`, заново загружает текущую
  опубликованную конфигурацию и перед записью повторно проверяет её revision;
- исходные answer, timestamps, payload и attempt ID остаются неизменными;
  меняются только authoritative check outcome, verdict, feedback, actor и
  result projection;
- broken checker оставляет попытку в повторяемом pending-состоянии без ложного
  результата; stale revision получает `409`, а ошибка записи откатывает весь
  batch;
- конкурентные recheck не создают дубликаты результатов, успешный commit
  публикует только owner-scoped Student invalidations;
- teacher получает `403`; Origin, cookie authority и strict request/response
  schemas проверяются на настоящем aiohttp.

[`test-recheck-client.ts`](../../vmshpwa/packages/app-shell/src/test-recheck-client.ts)
предоставляет strict Staff transport и TanStack Query hooks.
[`test-attempt-recheck.tsx`](../../vmshpwa/packages/product/src/test-attempt-recheck.tsx)
фиксирует product states preview/apply/still-pending/conflict/loading в stories
`product-test-answer--recheck-pending`,
`product-test-answer--recheck-still-pending`,
`product-test-answer--recheck-conflict` и
`product-test-answer--recheck-loading`.

Production route
[`/staff/problems/$problemId`](../../vmshpwa/apps/staff/src/routes/problems.$problemId.tsx)
использует server-backed page
[`test-attempt-recheck-page.tsx`](../../vmshpwa/apps/staff/src/test-attempt-recheck-page.tsx).
Parent route теперь корректно рендерит вложенный `Outlet`, а индексный экран
вынесен в отдельный route.

## Browser transport, draft и outbox

[`submission-client.ts`](../../vmshpwa/packages/app-shell/src/submission-client.ts)
даёт same-origin Student transport и TanStack Query hooks. При единственном
retry после `401` он повторяет тот же сериализованный body и idempotency UUID,
отделяет network/cancel/protocol/API errors и принимает только точные `201`/`200`
contract responses.

[`test-answer-draft.ts`](../../vmshpwa/packages/offline/src/test-answer-draft.ts)
хранит малый текстовый draft в `localStorage` под ключом runtime + audience +
account + problem + condition revision + config version. Несовместимая старая
revision возвращается отдельно и не перезаписывается; corrupt value удаляется,
а quota/write error обязательно доходит до UI.

[`test-answer-outbox.ts`](../../vmshpwa/packages/offline/src/test-answer-outbox.ts)
создаёт один immutable versioned wire request в Dexie. Expected
`problemRevision` является обязательной частью POST-контракта, поэтому сервер
отклоняет доставленный после редактирования условия ответ как
`409 test_problem_revision_changed`. Очередь:

- повторяет исходные UUID, timestamp, display value, revision и payload hash;
- сериализует конкурентный claim и восстанавливает просроченный sending lease;
- оставляет network failure в `retrying`, revision/idempotency mismatch — в
  `conflict`, terminal отказ — в `failed`;
- сохраняет валидный server receipt в состоянии `synced` до того, как UI
  очистит точный draft и явно вызовет acknowledge.

## Production Student UI и browser proof

[`student-test-answer.tsx`](../../vmshpwa/apps/student/src/student-test-answer.tsx)
компонует настоящий same-origin transport, offline input cache, account/problem/
revision-scoped draft и Dexie outbox на production focused-task route. UI:

- выполняет локальную format validation до POST и показывает server verdict
  inline;
- сохраняет набранный ответ при reload и очищает только после валидного
  server receipt;
- различает активную отправку и уже сохранённый retryable item: статус очереди
  не показывается, пока `deliverNext` не зафиксировал retryable failure;
- после reload восстанавливает pending value и позволяет явно повторить
  отправку тем же immutable UUID/payload;
- показывает reverse-chronological историю без правильного ответа и checker
  source.

Production-build сценарий
[`test-submission.spec.ts`](../../vmshpwa/e2e/test-submission.spec.ts) для каждого
из Chromium, WebKit и Firefox использует отдельное seeded занятие. Настоящий
Admin UI загружает LaTeX, создаёт задачу, задаёт metadata и публикует условие;
затем Student UI доказывает invalid-without-POST, draft reload, online verdict,
реальный browser-offline outbox, reload и retry. Финальная история в настоящей
SQLite содержит ровно две попытки в ожидаемом порядке; MSW не используется.

## Telegram compatibility adapter

Revision `2b00b06` переводит исторический Telegram test-answer path на
[`evaluate_test_answer`](../../models/pwa/submissions.py). Handler больше не
копирует regex/checker/verdict rules и сохраняет прежние публичные compatibility
symbols как aliases общей policy.

Telegram adapter при этом намеренно остаётся отдельным каналом доставки и
пишет проверенные ответы в legacy `results`: migration 0046 не требует у
исторических bot-задач web account, publication revision и PWA idempotency
context. Это не вторая реализация правил проверки; это сохранённая граница
persistence до отдельного cutover.

Проверено:

- все 23 исторических `ANS_TYPE`, включая visible-label `SELECT_ONE`;
- invalid-format не расходует legacy rate limit;
- malformed trusted checker даёт безопасный `pending_configuration`, не пишет
  ложный минус и не раскрывает source/answer/traceback;
- legacy admin recheck не меняет существующий verdict, пока checker сломан;
- исторический handler-flow сбрасывает state и возвращает ученика к задачам.

`make telegram-history-test`: **44 PASS**. Тест использует fake Bot и
изолированную SQLite, без Telegram network/credentials.

## Границы authority и транзакции

Repository разрешает сдачу только через активный Student account, активный
course enrollment, действующий `course_group_access`, опубликованную и ready
condition revision с `web_ast` derivative и открытое `lesson_window`.
Идентификатор школьника не принимается из клиентского payload.

Выполнение доверенного checker вынесено за пределы writer transaction. Перед
записью repository заново проверяет revision, publication, cutoff и access,
поэтому длительный checker не удерживает SQLite writer lock и одновременно не
может сохранить результат в устаревший контекст.

Отказы по deadline/rate limit сохраняются в idempotency ledger, чтобы retry
получал тот же ответ, но не создают server attempt. Исходный payload до
успешной фиксации обязан оставаться в будущем клиентском draft/outbox.

## Автоматические проверки

Проверено на Python 3.14.3:

```text
domain + repository focused suite
66 PASS

wide answer/content/schema/SQLite regression
142 PASS

repository + real aiohttp + app-factory regression
91 PASS

contracts package
6 files / 94 PASS; typecheck and ESLint PASS

full pwa_tests
1180 PASS / 3 intentional skips / 1 existing SymPy warning

full frontend unit
42 files / 323 PASS

offline package focused
7 files / 34 PASS

submission contract + browser transport focused
2 files / 14 PASS

full Storybook browser mode
38 files / 187 PASS

production-build Playwright test submissions
6 PASS: two workflows in Chromium / WebKit / Firefox

ESLint + Stylelint + strict TypeScript + production Vite build
PASS
```

Repository integration tests используют отдельную мигрированную synthetic
SQLite и доказывают:

- правильный ответ и legacy projection;
- неправильный ответ после уже успешного;
- format error без расхода лимита;
- exact replay и payload mismatch;
- missing/broken checker;
- offline-at-cutoff и late rejection replay;
- hour/day limits и explicit unlimited;
- конкурентную гонку одного idempotency key;
- полный rollback через synthetic SQLite trigger failure;
- owner isolation: чужая задача не раскрывается и отвечает `404`.

Recheck integration дополнительно доказывает preview/apply, current-publication
binding, teacher `403`, broken-checker retry, stale revision `409`, конкурентный
batch и полный rollback без частично обновлённых attempts/results.

Real aiohttp test дополнительно проходит настоящий Staff upload → compile →
matching → metadata → lesson window → publication, после чего Student делает
submit/replay/mismatch/invalid-format/history. Второй production browser workflow
сначала публикует неполную checker-конфигурацию и получает immutable pending
attempt, затем Staff загружает новую revision с тем же logical filename,
публикует исправление, выполняет recheck и проверяет обновлённую Student history.
Проверены same-origin gate, отсутствие client identity, отсутствие checker
secrets, точные row counts и Student-only realtime cursor.

## Изоляция

Тесты этого инкремента не обращались к Telegram API, Google, S3 или внешней
сети, не использовали настоящие credentials и не записывали в `db/vmsh.db`.
Пропущены только уже существующие явно opt-in live/local-toolchain smokes.

## Открытые границы Phase 4

- Telegram `results` persistence ещё не перенесён в structured attempt/
  idempotency ledger; это отдельная cutover-задача, а не дублирование domain
  normalization/verdict policy;
- Storybook проверяет изолированную матрицу Staff recheck states, а настоящий
  transport и production routes проверяет Playwright. Ручной visual gate
  focused Student page и нового Staff recheck panel остаётся открытым.

Функциональные критерии Phase 4 закрыты. Этап остаётся открыт только для ручного
visual owner gate; Telegram ledger cutover относится к будущей миграции adapter,
а не к приёмке тестовых ответов. Snapshots намеренно не обновлялись.
