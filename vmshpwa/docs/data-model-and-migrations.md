# Концептуальная модель данных и миграционные границы

## Контексты

- Identity: user, student profile, family account/link, staff role, group permission, device session.
- Teaching: season, lesson, level, group, attendance mode, classroom and assignment.
- Content: позиционное сопоставление source elements с legacy problem, synonym group, source revision, asset, scheduled publication by level, hint and solution.
- Work: attempt, answer, written submission, immutable attachment, annotation layer, feedback thread, verdict, oral conversation/result.
- Communication: news source/revision, local publication, notification preference/delivery и broadcast. Surveys остаются legacy вне первой версии.
- Operations: outbox receipt/idempotency, review lock, audit event, runtime/version marker.

## Идентичность и версии

Внутренние records имеют стабильные IDs, но исходный LaTeX не получает обязательный problem ID. Conditions/solutions сначала сопоставляются по порядку; изменение структуры создаёт blocking reconciliation rows в Staff. Submission ссылается на publication revision. До первого review lock ученик может изменить исходную отправку; после lock он может только добавить новый материал в тред. Review complete сверяет thread version, включает всё досланное до commit и затем фиксирует object keys навсегда; teacher annotation — отдельный immutable overlay. Object overwrite запрещён.

Synonym-group объединяет разные представления математически той же задачи. Совпадение названия внутри урока создаёт только кандидата. Автоматические результаты и статистика не сливаются до подтверждения.

## Время и аудит

Все серверные timestamps — UTC. Для offline mutation сохраняются клиентское время, timezone offset, серверное получение, idempotency key и решение deadline policy. Audit event append-only содержит actor, capability, object, before/after или diff, request/correlation ID, channel и время.

Deadline задаётся как момент публикации решений в `Europe/Moscow`, затем хранится в UTC. Offline answer с client time до deadline принимается и при поздней доставке; skew больше часа маркируется. После закрытия занятия статистика сложности открывается через семь дней и только для выборки не меньше 30.

История смены группы/уровня/режима не схлопывается до текущего значения. Legacy `user_changes_log` с `ts`, `user_id`, `change_type`, `new_value` является источником backfill. Модель уровней не ограничена тремя строками: текущие три получают именованные presentation tokens по `groups.sort_order`, последующие — нейтральный доступный fallback.

## Review locks

Lock имеет owner и lease expiry, продлевается heartbeat и может быть безопасно освобождён/перехвачен после expiry. Verdict записывается транзакционно с комментариями и release lock. Live invalidation не заменяет SQLite constraint.

## Граница текущего этапа

Каркас не проводит широкую нормализацию legacy-схемы и не переносит доменную логику из `db_methods`/`models`. Новые таблицы добавляются только yoyo migration, малыми обратимыми шагами. Adapter/translation layer допустим, дублирующая production-база или второй backend — нет.

Любая будущая миграция должна определить backfill, совместимость Telegram reads/writes, rollback, indexes, data validation и тест на snapshot исторической базы. Удаление legacy column возможно только после полного цикла, когда ни bot, ни Staff, ни jobs его не используют.
