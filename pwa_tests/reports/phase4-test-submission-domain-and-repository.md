# Phase 4A–4B — правила и атомарное хранение тестовых сдач

Дата: 2026-07-28

Revisions: `6409191`, `bd0487f`, `1d5df54`

## Проверяемый результат

Каркас Phase 4 теперь содержит доменные правила всех исторических типов
тестового ответа и атомарный SQLite repository. Этот инкремент не открывает
HTTP endpoint и не считается завершением всего этапа.

Реализовано:

- additive migration `0046.pwa_test_attempt_ledger.sql` с immutable попытками,
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
62 PASS

wide answer/content/schema/SQLite regression
142 PASS

full pwa_tests (JUnit authority)
1169 tests / 0 failures / 0 errors / 3 intentional skips

make pwa-test frontend unit
35 files / 285 PASS

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

## Изоляция

Тесты этого инкремента не обращались к Telegram, Google, S3 или внешней сети,
не использовали настоящие credentials и не записывали в `db/vmsh.db`.
Пропущены только уже существующие явно opt-in live/local-toolchain smokes.

## Открытые границы Phase 4

- нет Student HTTP contract, route и истории попыток;
- нет frontend draft/outbox, optimistic/pending UI и восстановления после
  reload;
- нет production page wiring и Storybook interaction для настоящего клиента;
- нет production-build Playwright сценария с настоящим aiohttp/SQLite;
- legacy Telegram adapter ещё не переведён на общий submission service;
- нет Staff recheck/configuration-repair flow.

Phase 4 остаётся открытым до закрытия этих границ и ручного visual gate.
