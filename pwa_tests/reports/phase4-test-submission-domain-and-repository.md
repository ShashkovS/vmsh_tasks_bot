# Phase 4A–4D — правила, хранение, Student API и offline foundation тестовых сдач

Дата: 2026-07-28

Revisions: `6409191`, `bd0487f`, `1d5df54`, `7793d0f`, `0475cd0`,
`6d1909c`, `bab5947`, `5b682d1`, `3d22373`

## Проверяемый результат

Каркас Phase 4 теперь содержит доменные правила всех исторических типов
тестового ответа, атомарный SQLite repository, authenticated Student HTTP
вертикаль, браузерный transport, local draft и Dexie outbox. Инкремент ещё не
подключён к production Student page и не считается завершением всего этапа.

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

После будущего admin recheck история предпочитает authoritative attempt state
и не соединяет его со stale feedback старого idempotency receipt.

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
6 files / 92 PASS; typecheck and ESLint PASS

full pwa_tests (JUnit authority)
1172 PASS / 3 intentional skips / 5 existing SymPy warnings

full frontend unit
39 files / 311 PASS

offline package focused
7 files / 34 PASS

submission contract + browser transport focused
2 files / 14 PASS

Ruff format-check + Ruff check
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

Real aiohttp test дополнительно проходит настоящий Staff upload → compile →
matching → metadata → lesson window → publication, после чего Student делает
submit/replay/mismatch/invalid-format/history. Проверены same-origin gate,
отсутствие client identity, отсутствие checker secrets, точные row counts и
Student-only realtime cursor.

## Изоляция

Тесты этого инкремента не обращались к Telegram, Google, S3 или внешней сети,
не использовали настоящие credentials и не записывали в `db/vmsh.db`.
Пропущены только уже существующие явно opt-in live/local-toolchain smokes.

## Открытые границы Phase 4

- local draft/outbox и transport ещё не скомпонованы с production Student
  route; нет optimistic/pending UI и полного reload orchestration;
- нет production page wiring и Storybook interaction с настоящим transport;
- нет production-build Playwright сценария с настоящим aiohttp/SQLite;
- legacy Telegram adapter ещё не переведён на общий submission service;
- нет Staff recheck/configuration-repair flow.

Phase 4 остаётся открытым до закрытия этих границ и ручного visual gate.
