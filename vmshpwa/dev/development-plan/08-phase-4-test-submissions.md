# Этап 4. Тестовые задачи и все исторические типы ответа

Дополнение 2026-09-09: [диагностика ошибок отправки](../../docs/submission-error-diagnostics.md)
в Student и общем app-shell; повторяемые HTTP-ошибки больше не называются потерей сети.

## Результат

Школьник вводит ответ любого исторического `ANS_TYPE`, заранее видит подсказку формата, но не получает преждевременную ошибку во время набора составного ответа. Ошибка формата появляется после выхода из control или попытки отправки. День недели выбирается кнопками `пн–вс`. Ответ отправляется online или через offline outbox и получает inline verdict либо ясный статус «принято, ожидает настройки проверки». Все введённые ответы сохраняются; повтор запроса не создаёт дубль.

Дизайн-контракт этапа: [`TestAnswer`, полная матрица исторических форматов и page-level Storybook stories](18-design-implementation-map.md#phase-4-design).

## Поддерживаемая матрица

В первом релизе реализуются все значения из `helpers/consts.py`, а не только простые:

- `DIGIT`, `NATURAL`, `INTEGER`, `RATIO`, `FLOAT`, `FLOAT_EPS`, `FRACTION`, `MIXED_FRACTION`;
- `INT_SEQ`, `INT_SET`, `INT_2`, `INT_3`, `INT_4`;
- `POLYNOMIAL`, `TIME`, `DATE`, `WEEKDAY`;
- `FRAC_SEQ`, `MULTISET`;
- `SYMB_EXPRESSION`, `SYMB_EQUIV`, `SELECT_ONE`, `STRING`.

Названия enum и numeric compatibility сохраняются. Для каждого типа нужны input representation, help text, normalization, valid/invalid boundary fixtures, accessibility label и rendering принятого ответа.

## Модель данных и backend

Migration: `pwa_test_attempts_idempotency`; таблицы `test_attempts`, `idempotency_records`; dual-write в `results`.

- Server authoritative проверяет `lesson_windows.submission_closes_at`, attempts policy, active student/problem revision и answer schema. Фактическая публикация solution не подменяет cutoff. Invalid-format сохраняется, но попытку не расходует; отправка после правильного ответа разрешена.
- Default attempt policy: не более трёх **неверных** валидных ответов в одном календарном часу business timezone и не более пяти любых расходующих попытку ответов в календарный день. Верные ответы не уменьшают часовой остаток; invalid-format не уменьшает ни один остаток. Policy хранится в revision и допускает будущую настройку/отключение на уровне курса.
- Metadata semantics повторяют legacy без неявных преобразований: custom `ans_validation` делает `fullmatch` на `student_answer.strip()`, пустое поле берёт default из `ANS_TYPE`, `SELECT_ONE` использует видимые `;`-separated labels, а не hidden values. `cor_ans` поддерживает несколько вариантов через `;`.
- `validation_error` отвечает за понятный формат и контекст задачи; `wrong_ans` — за валидный, но неверный ответ; `congrat` — за верный. Первый текст по возможности называет искомую величину/порядок и даёт пример, чтобы отличить ошибку формата от промаха по задаче.
- Offline `clientCreatedAt` до `submission_closes_at` считается своевременным даже при поздней доставке. Clock skew больше часа маркируется для диагностики.
- Same idempotency key + same payload возвращает записанный response. Same key + different payload → `409 IDEMPOTENCY_PAYLOAD_MISMATCH`.
- Checker version/hash сохраняется с attempt. Если checker ещё не настроен, attempt получает `pending_configuration`; admin запускает совместимую `problem_recheck` после настройки.
- Trusted `cor_ans_checker` исполняется только в выбранном контролируемом path; UI не создаёт новый arbitrary execution surface для teacher. Observable legacy contract закреплён в [`handlers/student_handlers.py`](../../../handlers/student_handlers.py): `is_py_func`, `GLOBALS_FOR_TEST_FUNCTION_CREATION` и `run_py_func_checker`. Это compatibility boundary доверенного admin-кода, не security sandbox.
- Ответ содержит attempts used/remaining/unlimited, verdict и canonical display answer.

Пути: `models/pwa/submissions.py`, `db_methods/pwa/submissions.py`, `helpers/pwa/idempotency.py`, `contracts/src/tasks.ts`, `student/features/submissions/test-answer-*`.

## Frontend/offline

- Type-specific input выбирается по contract, но использует общий Field/Form минимум.
- Format help сохраняет все исторические форматы и всегда виден до ошибки. Клиентская подсветка зеркалит только `student_answer.strip()` + `fullmatch` по problem `ans_validation` либо текущему `helpers/checkers.py:ANS_REGEX`; server остаётся авторитетом. Совместимые улучшения можно добавлять, не ломая старый ввод.
- Fixed `INT_2/3/4` использует отдельные компактные поля без блока «Отправится». `INT_SEQ/INT_SET/FRAC_SEQ/MULTISET` показывает «Распознано» только после успешного parsing теми же token rules. `SELECT_ONE` передаёт ровно видимый label, например `Нечётное`, без скрытого `odd`.
- Submit state: ready → queued offline/uploading → checking → accepted/wrong/domain error/rate limited.
- Fast result меняет inline status, не только toast. Повторная попытка сохраняет историю.
- Outbox хранит normalized versioned payload + original display value, problem revision, client time и idempotency key.
- Введённый, но ещё не отправленный ответ записывается в account/problem/revision-scoped `localStorage` после каждого осмысленного изменения и восстанавливается после reload/update. Server receipt очищает draft; conflict или failed submit не очищают.
- Если deadline наступил offline, item остаётся виден; server решает timely/late, UI объясняет результат и не удаляет доказательство.

## Tests

- Table-driven Python + TS fixtures для всех типов, invalid-does-not-count, answer-after-success, pending checker, Unicode/minus/decimal/date/time/duplicate/order edge cases.
- Differential characterization нынешнего validation/checker поведения; любые исправления явно перечислены.
- Attempt policy: first/wrong/correct/limit/unlimited/deadline/race two devices.
- Idempotency crash windows: before transaction, after result before response, replay different payload.
- Dexie queue ordering/retry/logout warning/schema upgrade.
- Local answer draft reload/account isolation/revision conflict/receipt cleanup.
- Storybook states каждого answer family, help/errors/attempt counter/offline/late.
- E2E: минимум один сценарий каждой input family, full matrix остаётся unit/contract; online + offline replay + duplicate retry.
- Compatibility tests `cor_ans_checker` сначала характеризуют текущие `is_py_func`/`run_py_func_checker` на синтетическом positive/negative corpus: начальный `def`, exact restricted globals/builtins, trim входа, выбор созданного callable, cache по точной строке, ожидаемую пару `(bool, optional message)`, а также compile/call/result-shape failures. Реальные production checker strings не копируются в fixtures. Затем новый path доказывает согласованную нормализацию ошибок и safe failure to `pending_configuration`; создание новой sandbox не является prerequisite v1.

## Критерии приёмки

- Ни один legacy `ANS_TYPE` не падает в generic text без согласованного решения.
- [`TestAnswer`](../../packages/product/src/test-answer.tsx) сохраняет спокойное partial-состояние tuple/fraction/date/time, а [`Product/Test answer`](../../packages/product/src/test-answer.stories.tsx) доказывает blur/submit validation и weekday buttons.
- Test attempt и `results` появляются ровно один раз при сетевом retry.
- UI и Telegram используют одну domain normalization/verdict policy.
- Client не может увеличить attempts; offline-created-before-deadline receipt сохраняется и при поздней доставке, а clock anomaly попадает в диагностику.
- История ответов читабельна и не раскрывает `cor_ans`/checker.
- Reload до отправки не теряет введённый ответ; другой аккаунт его не видит.

## Пруфы завершения этапа

- [ ] Revision/migration/dual-write integrity: `<sha/paths/results>`.
- [ ] ANS_TYPE support matrix and shared fixtures: `<path>`; all cases `<result>`.
- [ ] Legacy differential report: `<path>`.
- [ ] Metadata differential matrix: blank/custom validation, `SELECT_ONE` labels, multi-answer `cor_ans`, contextual validation/wrong/congrat messages and no secret answer/checker in Student/Family payload `<path/result>`.
- [ ] Idempotency/crash/race tests: `<result>`.
- [ ] Local draft reload/isolation/conflict/cleanup tests: `<result>`.
- [ ] `cor_ans_checker` trust/compatibility decision, ссылка на legacy symbols и synthetic allow/deny/error/cache corpus: `<path/result>`.
- [ ] Storybook stories/interactions/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright online/offline/retry 3 browsers: `<result>`.
- [ ] Telegram historical test submissions: `<result>`.
- [ ] Docs/known limitations/acceptance: `<paths/issues/name/date>`.

## Многокурсовый инкремент Phase 4

Тестовые попытки/checker/rate limit остаются per concrete problem. Confirmed synonym-group одного course lesson вычисляет общий status и засчитывает результат в каждый доступный group sheet; merge/split не меняет attempt/result IDs.

Дополнительный proof: candidate/merge/split impact fixtures для разных task/answer types, identity assertions до/после, split recomputation и `Product/Staff-data--synonym-merge-and-split`.
