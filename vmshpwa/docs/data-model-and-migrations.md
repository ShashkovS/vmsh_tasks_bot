# Концептуальная модель данных и миграционные границы

## Контексты

- Identity: user, student profile, family account/link, staff role, group permission, device session.
- Teaching: season, lesson, level, group, attendance mode, global classroom catalog, effective layout version and lesson assignment plan.
- Content: позиционное сопоставление source elements с legacy problem, synonym group, source revision, asset, scheduled publication by level, hint and solution.
- Work: attempt, answer, written submission, immutable attachment, annotation layer, feedback thread, verdict, oral conversation/result.
- Communication: news source/revision, local publication и notification preference/delivery. Broadcast model и Markdown content появляются во второй фазе; surveys остаются legacy.
- Operations: outbox receipt/idempotency, review lock, audit event, runtime/version marker.

## Идентичность и версии

Внутренние records имеют стабильные IDs, но исходный LaTeX не получает обязательный problem ID. Conditions/solutions сначала сопоставляются по порядку; изменение структуры создаёт blocking reconciliation rows в Staff. Submission ссылается на publication revision. До первого review lock ученик может изменить исходную отправку; после lock он может только добавить новый материал в тред. Review complete сверяет thread version, включает всё досланное до commit и затем фиксирует object keys навсегда; teacher annotation — отдельный immutable overlay. Object overwrite запрещён.

Synonym-group объединяет разные представления математически той же задачи. Совпадение названия внутри урока создаёт только кандидата. Автоматические результаты и статистика не сливаются до подтверждения.

## Время и аудит

Все серверные timestamps — UTC. Для offline mutation сохраняются клиентское время, timezone offset, серверное получение, idempotency key и решение deadline policy. Audit event append-only содержит actor, capability, object, before/after или diff, request/correlation ID, channel и время.

Lesson window хранит отдельный `submission_closes_at` в `Europe/Moscow`, затем в UTC. Ожидаемая и фактическая публикация решения — отдельные timestamps и не меняют cutoff молча. Offline answer с client time до cutoff принимается и при поздней доставке; skew больше часа маркируется. После закрытия занятия статистика сложности открывается через семь дней и только для выборки не меньше 30.

История смены группы/уровня/режима не схлопывается до текущего значения. Legacy `user_changes_log` с `ts`, `user_id`, `change_type`, `new_value` является источником backfill. Модель уровней не ограничена тремя строками: текущие три получают именованные presentation tokens по `groups.sort_order`, последующие — нейтральный доступный fallback.

Telegram destination является настройкой группы в SQLite, а не глобальным config: `groups.telegram_channel_id`, cached title, enabled и verified timestamp. ID сохраняется как возвращённый Bot API 64-bit integer без ручного преобразования UI-значения; partial unique index защищает от случайного назначения одного production channel двум группам. Bot token остаётся credential config. Telegram-derived news дополнительно snapshot-ит `group_id` и фактические chat/message IDs, чтобы смена destination не переписывала историю.

## Review locks

Lock имеет owner и lease expiry, продлевается heartbeat и может быть безопасно освобождён/перехвачен после expiry. Verdict записывается транзакционно с комментариями и release lock. Live invalidation не заменяет SQLite constraint.

## Аудитории

`classrooms` — постоянный каталог. Display-name сохраняет внутренние пробелы, но уникальность защищает отдельное значение `NFKC(trim(name)).casefold()`. Hard delete отсутствует; rename/archive/restore аудитируются.

`classroom_layout_versions` и `classroom_layout_rooms` задают наследуемую схему «аудитория → группа». Новое занятие читает последнюю confirmed-версию, а первая правка materialize-ит draft с `base_version_id`. Одна аудитория встречается в версии один раз, одна группа может использовать любое число комнат. Вместимость и веса отсутствуют.

`classroom_assignment_plans` и `classroom_assignments` сохраняют отдельную версию распределения для занятия со snapshot группы школьника. Алгоритм сохраняет прежнюю допустимую комнату, иначе выбирает наименее заполненную с natural-name tie-break. Confirmed membership/history не перезаписывается; глобальный rename меняет отображаемое имя, а старое остаётся в audit. Layout change делает plan `stale`; скрытие используемой комнаты немедленно даёт текущим затронутым школьникам `reassigning`, restore не возвращает назначение. `not_applicable` зарезервирован для школьника, которому не нужна очная комната.

One-time import текущего Excel-export использует `IDd`, `Уровень`, `Аудитория`, требует dry-run/hash/audit и не создаёт постоянный spreadsheet adapter.

## Граница текущего этапа

Каркас не проводит широкую нормализацию legacy-схемы и не переносит доменную логику из `db_methods`/`models`. Новые таблицы добавляются только yoyo migration, малыми обратимыми шагами. Adapter/translation layer допустим, дублирующая production-база или второй backend — нет. До первой бизнес-миграции отдельный ADR фиксирует connection ownership, async boundary, `busy_timeout`/bounded retry и deploy-only migration command; обычный runtime startup только проверяет schema version.

Любая будущая миграция должна определить backfill, совместимость Telegram reads/writes, rollback, indexes, data validation и тест на snapshot исторической базы. Удаление legacy column возможно только после полного цикла, когда ни bot, ни Staff, ни jobs его не используют.
