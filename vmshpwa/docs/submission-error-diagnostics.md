# Ошибки отправки и Sentry — 9 сентября 2026

`student-test-answer.tsx` и `student-written-submission.tsx` больше не трактуют
любую повторяемую ошибку outbox как отсутствие интернета. HTTP 5xx, 429,
401/403, отклонение сервером, транспорт и ошибки приложения имеют разные
сообщения через `app-shell/src/observability.ts::submissionFailureMessage`.
Транспортная ошибка не доказывает отсутствие интернета. Отправка без известной
ошибки показывается как неподтверждённая. Существующие retry/idempotency и
сохранение ответа не меняются. Outbox lastError дополнен requestId; старые
записи читаются без миграции. Код сохраняется и отображается после перезагрузки.

`reportHandledError` передаёт только operation, ID аккаунта/задачи/очереди,
число попыток, HTTP status/code/requestId и navigator.onLine (не доказательство
доступности сервера). Исходные message/cause/details/variables не передаются.
Original stack с 10 октября сохраняет только same-origin public app `.js`
locations без сообщений/имён функций/URL parameters; остальные URL исключены.
Это даёт место исходного сбоя без передачи приватного cause.
Один объект ошибки отправляется один раз. С 10 октября повторные объекты
одинаковой сигнатуры дополнительно ограничиваются общим SDK `beforeSend`;
ошибки отправки/хранения имеют отдельный от query/recovery бюджет.
Подтверждённые отказы по сроку/лимиту попыток остаются в UI/outbox без Sentry.
[Численные лимиты, sampling и регрессии](../../docs/performance/2026-10-10-sentry-noise.md).
Сохраняется существующая настройка DSN.

С 11 октября перед SDK transport требуется общий backend admission;
ошибкам отправки/хранения и автоматическим crashes выделены 900 reservations
за скользящие 32 дня на портал, отдельно от 100 read diagnostics.
Отказ/timeout admission влияет только на telemetry и не меняет outbox.
Anonymous endpoint передаёт только lane/hash, без ID/сообщений/payload;
worker/reload/release не обнуляют ledger. Бюджеты двух Sentry аккаунтов независимы.
[Политика 5 000, migration 0117 и проверки](../../docs/performance/2026-10-11-sentry-quota.md).

Auth provider выставляет Sentry user.id=accountId и очищает его при выходе.
Sanitizer сохраняет только user.id, удаляет остальные поля пользователя.
QueryCache/MutationCache покрывают обработанные ошибки загрузки и изменений
во всех аудиториях; ошибки отправки и локального хранилища Student записываются
отдельно с контекстом задачи. Автоматический Sentry capture необработанных
ошибок остаётся включённым. Произвольные ручные catch вне этих точек не
обещаются как полностью покрытые. Не добавлять в диагностику ответ, фото,
имя файла, ФИО, cookies, токены или полный URL с query.

Проверки: observability.test.ts, submission-error-diagnostics.test.ts,
test-answer-outbox.test.ts, written-submission-outbox.test.ts, auth-context.test.tsx.
Для выпуска нужны frontend-сборки Student/Family/Staff, серверная миграция не нужна.

## Ограничение зависшего запроса — 13 сентября 2026

Транспорт тестовых и письменных отправок ограничивает каждый HTTP-запрос 30
секундами. Дедлайн прерывает `fetch`, но также завершает клиентское ожидание,
если браузер не разрешил промис после abort. Идемпотентный outbox переводит
такой запрос в `retrying`, сохраняет ответ/фотографии и показывает отдельное
сообщение: доступность обычного интернета из таймаута не выводится.

При запуске Test UI просроченная `sending`-аренда атомарно становится
`retrying`, поэтому закрытая во время запроса вкладка не оставляет вечное
«Отправляем…». Реализация: `app-shell/src/request-deadline.ts`, клиенты
`submission-client.ts` и `written-submission-client.ts`, очереди пакета
`offline`.
