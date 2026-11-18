# Полная перепроверка тестовых попыток

## Контракт

Администратор открывает действие из подтверждённой таблицы metadata или по
`/staff/problems/{problemPublicId}`. `GET .../recheck-test-attempts` вычисляет
preview для всех PWA-попыток конкретной задачи: число ответов и школьников,
переходы `− → +`/`+ → −`, изменения формата, нерешённые конфигурации и число
изменённых автоматических реплик. Синонимы не расширяют область операции.

`POST` привязан к `conditionRevisionId + configVersion`. Смена metadata между
preview и записью возвращает `409`. Проверка выполняется вне write-транзакции;
результат применяется одной короткой транзакцией. Повторный запуск сравнивает
полную текущую проекцию и не создаёт лишних `results`.

## Хранение и чтение

Миграция [`0095.pwa_test_attempt_projection.sql`](../../migrations/0095.pwa_test_attempt_projection.sql)
добавляет `evaluation_version`, `feedback` и `checker_message`. Триггер сохраняет
неизменяемыми исходный ответ, автора, задачу и время, но разрешает атомарно
заменять производные поля оценки. При смене verdict создаётся новый append-only
`results`; при смене только текста result не создаётся. Append-only
`test_attempt_result_events` отличает эти PWA-записи от настоящих legacy/Telegram
результатов той же задачи.

View `effective_results` скрывает старые автоматические PWA rows и отдаёт только
текущие `result_id`, не затрагивая legacy-результаты без связи с attempt. Поэтому Student/Family,
прогресс, Staff statistics и архив не возвращают исторический ошибочный плюс.
Более поздняя ручная оценка продолжает иметь приоритет по `live_mark_cells`.

После commit сервер адресно инвалидирует Student и связанные Family, а Staff
получает общий `live-results` refetch. Push/notification events не создаются.

## Реализация и проверки

- domain: [`models/pwa/submissions.py`](../../models/pwa/submissions.py);
- repository: [`db_methods/pwa/submissions.py`](../../db_methods/pwa/submissions.py);
- HTTP: [`apps/pwa_api/submission_routes.py`](../../apps/pwa_api/submission_routes.py);
- Staff UI: [`test-attempt-recheck-page.tsx`](../apps/staff/src/test-attempt-recheck-page.tsx)
  и [`test-attempt-recheck.tsx`](../packages/product/src/test-attempt-recheck.tsx);
- regression: `29, 29, 30`, copy-only update, invalid-format round trip,
  stale revision, concurrency, rollback and audience invalidation in
  `pwa_tests/integration/test_submission_repository.py` and
  `pwa_tests/integration/test_content_http_api.py`.
