# Концептуальная модель данных и миграционные границы

## Контексты

- Identity: user, student profile, family account/link, staff role, group permission, device session.
- Teaching: season, lesson, level, group, attendance mode, classroom and assignment.
- Content: problem identity, synonym group, source revision, asset, publication by level, hint and solution.
- Work: attempt, answer, written submission, immutable attachment, annotation layer, feedback thread, verdict, oral conversation/result.
- Communication: news source/revision, local publication, notification preference/delivery, broadcast and survey.
- Operations: outbox receipt/idempotency, review lock, audit event, runtime/version marker.

## Идентичность и версии

Используются стабильные IDs, не зависящие от Telegram message ID, spreadsheet row или display number. Внешние IDs хранятся как mapping/provenance. Submission ссылается на problem source revision и lesson publication revision. Attachment после получения неизменяем; teacher annotations — отдельные versioned overlays.

Synonym-group объединяет разные представления математически той же задачи. Совпадение названия внутри урока создаёт только кандидата. Автоматические результаты и статистика не сливаются до подтверждения.

## Время и аудит

Все серверные timestamps — UTC. Для offline mutation сохраняются клиентское время, timezone offset, серверное получение, idempotency key и решение deadline policy. Audit event append-only содержит actor, capability, object, before/after или diff, request/correlation ID, channel и время.

## Review locks

Lock имеет owner и lease expiry, продлевается heartbeat и может быть безопасно освобождён/перехвачен после expiry. Verdict записывается транзакционно с комментариями и release lock. Live invalidation не заменяет SQLite constraint.

## Граница текущего этапа

Каркас не проводит широкую нормализацию legacy-схемы и не переносит доменную логику из `db_methods`/`models`. Новые таблицы добавляются только yoyo migration, малыми обратимыми шагами. Adapter/translation layer допустим, дублирующая production-база или второй backend — нет.

Любая будущая миграция должна определить backfill, совместимость Telegram reads/writes, rollback, indexes, data validation и тест на snapshot исторической базы. Удаление legacy column возможно только после полного цикла, когда ни bot, ни Staff, ни jobs его не используют.
