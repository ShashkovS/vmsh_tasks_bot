# Этап 4. Тестовые задачи и все исторические типы ответа

## Результат

Школьник вводит ответ любого исторического `ANS_TYPE`, заранее видит подсказку формата, но не получает преждевременную ошибку во время набора составного ответа. Ошибка формата появляется после выхода из control или попытки отправки. День недели выбирается кнопками `пн–вс`. Ответ отправляется online или через offline outbox и получает inline verdict либо ясный статус «принято, ожидает настройки проверки». Все введённые ответы сохраняются; повтор запроса не создаёт дубль.

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

- Server authoritative проверяет publication deadline, attempts policy, active student/problem revision и answer schema. Invalid-format сохраняется, но попытку не расходует; отправка после правильного ответа разрешена.
- Offline `clientCreatedAt` до публикации решений считается своевременным даже при поздней доставке. Clock skew больше часа маркируется для диагностики.
- Same idempotency key + same payload возвращает записанный response. Same key + different payload → `409 IDEMPOTENCY_PAYLOAD_MISMATCH`.
- Checker version/hash сохраняется с attempt. Если checker ещё не настроен, attempt получает `pending_configuration`; admin запускает совместимую `problem_recheck` после настройки.
- Trusted `cor_ans_checker` исполняется только в выбранном контролируемом path; UI не создаёт новый arbitrary execution surface для teacher.
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
- Compatibility tests `cor_ans_checker`: current trusted-admin `exec` behavior, exception/output normalization and safe failure to `pending_configuration`; a new sandbox is not a v1 prerequisite.

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
- [ ] Idempotency/crash/race tests: `<result>`.
- [ ] Local draft reload/isolation/conflict/cleanup tests: `<result>`.
- [ ] `cor_ans_checker` trust/compatibility decision and tests: `<path/result>`.
- [ ] Storybook stories/interactions/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright online/offline/retry 3 browsers: `<result>`.
- [ ] Telegram historical test submissions: `<result>`.
- [ ] Docs/known limitations/acceptance: `<paths/issues/name/date>`.
