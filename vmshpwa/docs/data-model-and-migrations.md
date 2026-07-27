# Концептуальная модель данных и миграционные границы

## Контексты

- Identity: user, student profile, family account/link, staff role, group permission, device session.
- Teaching: season, lesson, level, group, attendance mode, global classroom catalog, effective layout version and lesson assignment plan.
- Content: позиционное сопоставление source elements с legacy problem, synonym group, source revision, asset, scheduled publication by level, hint and solution.
- Work: attempt, answer, written submission, immutable attachment, annotation layer, feedback thread, verdict, oral conversation/result.
- Communication: news source/revision, local publication и notification preference/delivery. Broadcast model и Markdown content появляются во второй фазе; surveys остаются legacy.
- Operations: outbox receipt/idempotency, review lock, audit event, runtime/version marker.

## Идентичность и версии

Legacy `users.id` остаётся внутренним FK. Browser получает отдельный opaque
`users.public_id` как `userId`/`studentId`, а `auth_accounts.public_id` как
`accountId`; эти значения имеют разные смыслы и не взаимозаменяемы. Новая
колонка пользователя nullable только на переходном этапе: controlled
activation присваивает случайное стабильное значение, а adapter fail-closed
отказывает связанной строке без него. Такой переход не требует переписывать
исторические integer foreign keys и не раскрывает последовательные IDs в URL.

Внутренние records имеют стабильные IDs, но исходный LaTeX не получает обязательный problem ID. Conditions/solutions сначала сопоставляются по порядку; изменение структуры создаёт blocking reconciliation rows в Staff. Submission ссылается на publication revision. До первого review lock ученик может изменить исходную отправку; после lock он может только добавить новый материал в тред. Review complete сверяет thread version, включает всё досланное до commit и затем фиксирует object keys навсегда; teacher annotation — отдельный immutable overlay. Object overwrite запрещён.

Synonym-group объединяет разные представления математически той же задачи. Совпадение названия внутри урока создаёт только кандидата. Автоматические результаты и статистика не сливаются до подтверждения.

## Время и аудит

Все серверные timestamps — UTC. Для offline mutation сохраняются клиентское время, timezone offset, серверное получение, idempotency key и решение deadline policy. Audit event append-only содержит actor, capability, object, before/after или diff, request/correlation ID, channel и время.

Lesson window хранит отдельный `submission_closes_at` в `Europe/Moscow`, затем в UTC. Ожидаемая и фактическая публикация решения — отдельные timestamps и не меняют cutoff молча. Offline answer с client time до cutoff принимается и при поздней доставке; skew больше часа маркируется. После закрытия занятия статистика сложности открывается через семь дней и только для выборки не меньше 30.

История смены группы/уровня/режима не схлопывается до текущего значения. Legacy `user_changes_log` с `ts`, `user_id`, `change_type`, `new_value` является источником backfill. Модель уровней не ограничена тремя строками: текущие три получают именованные presentation tokens по `groups.sort_order`, последующие — нейтральный доступный fallback.

Telegram destination является записью `telegram_bindings`, а не глобальным config или полем `groups`: owner — course/group, purpose — news source/materials target, canonical `chat_id` сохраняется как возвращённый Bot API 64-bit integer без ручного преобразования UI-значения. Bot token остаётся credential config. Telegram-derived news snapshot-ит binding, concrete owner и фактические chat/message IDs, чтобы смена destination не переписывала историю. Личный Telegram destination Student для classroom delivery разрешается server-side через существующую связь с ботом и никогда не отдаётся browser-клиенту.

## Review locks

Lock имеет owner и lease expiry, продлевается heartbeat и может быть безопасно освобождён/перехвачен после expiry. Verdict записывается транзакционно с комментариями и release lock. Live invalidation не заменяет SQLite constraint.

## Аудитории

`classrooms` — постоянный каталог. Display-name сохраняет внутренние пробелы, но уникальность защищает отдельное значение `NFKC(trim(name)).casefold()`. Hard delete отсутствует; rename/archive/restore аудитируются.

`classroom_layout_versions` и `classroom_layout_rooms` задают наследуемую схему «аудитория → группа». Новое занятие читает последнюю confirmed-версию, а первая правка materialize-ит draft с `base_version_id`. Одна аудитория встречается в версии один раз, одна группа может использовать любое число комнат. Вместимость и веса отсутствуют.

`classroom_assignment_plans` и `classroom_assignments` сохраняют отдельную версию распределения для занятия со snapshot группы школьника. Алгоритм сохраняет прежнюю допустимую комнату, иначе выбирает наименее заполненную с natural-name tie-break. Confirmed membership/history не перезаписывается; глобальный rename меняет отображаемое имя, а старое остаётся в audit. Layout change делает plan `stale`; скрытие используемой комнаты немедленно даёт текущим затронутым школьникам `reassigning`, restore не возвращает назначение. `not_applicable` зарезервирован для школьника, которому не нужна очная комната.

`classroom_assignment_delivery_batches` и recipient rows snapshot-ят confirmed plan version, выбранные PWA/Telegram channels и Student recipients. Confirm меняет read model, но не отправляет уведомление. Delivery создаётся только отдельным admin action после preview; Family recipient rows отсутствуют, а более новая версия плана не запускает resend автоматически.

One-time import текущего Excel-export использует `IDd`, `Уровень`, `Аудитория`, требует dry-run/hash/audit и не создаёт постоянный spreadsheet adapter.

## Граница текущего этапа

Каркас не проводит широкую нормализацию legacy-схемы и не переносит доменную логику из `db_methods`/`models`. Новые таблицы добавляются только yoyo migration, малыми обратимыми шагами. Adapter/translation layer допустим, дублирующая production-база или второй backend — нет. До первой бизнес-миграции отдельный ADR фиксирует connection ownership, async boundary, `busy_timeout`/bounded retry и deploy-only migration command; обычный runtime startup только проверяет schema version.

Любая будущая миграция должна определить backfill, совместимость Telegram reads/writes, rollback, indexes, data validation и тест на snapshot исторической базы. Удаление legacy column возможно только после полного цикла, когда ни bot, ни Staff, ни jobs его не используют.

## Канонический baseline схемы

Точное состояние до первой бизнес-миграции воспроизводится из repository migrations и проверяется `db_methods/pwa/schema_inventory.py`. `pwa_tests/fixtures/schema_inventory.v1.json` содержит schema-only DDL, `table_xinfo`, foreign keys и index metadata; `schema_snapshot.sql` и `docs/db_structure.sql` генерируются из него и не используются для bootstrap. Значения product rows согласованной live-БД, включая исторические `kv_logins`, не выбираются и не попадают в artifacts. Live DDL и выражения `DEFAULT` читаются только в памяти для сравнения и сериализуются как безопасная структура/fingerprints; fresh snapshot содержит migration-authored DDL, но не DML-строки миграций.

`make pwa-schema-check` строит временную базу до migration head и сверяет committed artifacts; отдельный unit-test доказывает воспроизводимость на двух независимо созданных базах. `make pwa-schema-live-check` открывает согласованный `db/vmsh.db` через SQLite `mode=ro`, включает `query_only`, держит одну read transaction и сверяет обезличенный drift report; исходный файл не меняется. Пишущие `*-update` цели атомарно заменяют только пять заранее заданных repository-artifacts — inventory, два SQL snapshot и два live-report — и отвергают произвольный output path.

Migration-head baseline после добавочных Phase-1 миграций зафиксировал 50 product tables, 36 explicit indexes, 5 triggers и 2 views. Согласованная read-only `db/vmsh.db` намеренно остаётся на 0038 до отдельного production rehearsal: отчёт явно показывает missing 0039/0040, 46 отсутствующих объектов и изменение `groups`/`users`, не применяя миграции к файлу. В live-БД дополнительно находятся 12 явно перечисленных derived `temp_*` objects и два структурных дефекта: отсутствующий FK `reaction_enum → reaction_type_enum` и неверная FK-цель `reactions.zoom_conversation_id`. Они не нормализуются как «эквивалентный SQL»: до новых reaction writes требуется отдельная forward migration. Отчёт также фиксирует структуру yoyo и каждого allowlisted derived object. Live SQL и выражения `DEFAULT` никогда не сериализуются: сохраняются безопасные структурные сведения и SHA-256 fingerprints.

## Многокурсовое расширение

Целевые таблицы `courses`, расширенная `groups`, `course_enrollments`, `course_group_access`, `course_enrollment_events`, `staff_scopes`, `course_lessons`, `group_lessons`, schedule rules/overrides, synonym groups/members, `telegram_bindings` и `in_person_events` описаны в [courses-groups-and-lessons.md](courses-groups-and-lessons.md). Миграции 0039/0040 реализуют только auth/session и первый course/access слой; lesson/content/Telegram/event сущности появляются в своих последующих этапах.

Миграция сохраняет legacy `group_id`, `problem_id`, submission/result IDs и Telegram paths. Текущие группы сезона backfill-ятся в курс «Математика 5–7». Merge/split синонимов никогда не переносит исторические строки между задачами. Обязательный production-size rehearsal и сравнение read models входят в Phase 11.
