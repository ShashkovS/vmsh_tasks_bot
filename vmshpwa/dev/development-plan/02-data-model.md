# Целевая модель данных и границы миграции

Статус: целевая схема после закрытия продуктового опросника и classroom-уточнений 25 июля 2026 года. Имена фиксируются здесь заранее, чтобы backend, contracts и UI говорили на одном языке; миграции всё равно создаются только в своём этапе после сверки с production-копией SQLite.

## Общие правила

- SQLite остаётся authoritative storage. NATS доставляет live invalidation, но не хранит бизнес-историю.
- Legacy integer IDs сохраняются. Новые объекты, попадающие в URL, получают opaque `public_id TEXT UNIQUE`; конкретный UUID-format является внутренней реализацией и не входит в публичный контракт.
- Новые timestamps: UTC RFC 3339 с timezone. В поле с бизнес-временем всегда есть suffix `_at`; даты — `_on`.
- Soft-delete используется только там, где восстановление имеет продуктовый смысл. Reviews, audit, публикации и зафиксированные submission assets не удаляются приложением.
- JSON допустим для версионированного payload/diagnostics, но не вместо колонок, по которым фильтруют, сортируют или связывают данные.
- Каждая таблица с mutable state имеет `created_at`, `updated_at` и при конкурентном редактировании `version INTEGER`.
- Миграции получают следующий свободный номер в момент реализации. Логические filenames ниже не резервируют номер: `migrations/NNNN.pwa_<topic>.sql`.

## Существующие таблицы: сохранить и эволюционировать

| Таблица                                           | Роль сейчас                                                                                     | План                                                                                                                                                                                                                                 |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `users`                                           | Ученик/учитель/admin, Telegram, активная группа, token, online, grade, birthday, allowed groups | Сохранить primary domain identity; не переносить массово. Auth account ссылается на `users.id`. `grade`/`birthday` остаются nullable источником classroom read model. Нормализовать `allowed_groups` позже без удаления legacy-поля. |
| `student_strength`                                | Автоматические показатели `simple_prob`, `compl_prob`                                           | Сохранить и обновлять совместимым job из `a53_calc_rating_new.py`. Classroom adapter публикует nullable показатель 0–10; ручного редактирования не добавлять.                                                                        |
| `groups`                                          | Уровни/служебные группы, display/config/score weight                                            | Сохранить; связать с сезоном без изменения legacy `group_id`; добавить per-group Telegram destination, не глобальную channel-константу.                                                                                              |
| `lessons`                                         | Пара `(group_id, lesson)`                                                                       | Сохранить как legacy mapping; новая публикация ссылается на lesson/group.                                                                                                                                                            |
| `problems`                                        | Условие, тип, answer config/checker, synonyms                                                   | Сохранить существующий problem row для legacy; новая LaTeX не обязана содержать его ID, а immutable revisions связываются после позиционного сопоставления.                                                                          |
| `results`                                         | История verdict/test/oral/written events                                                        | Сохранить authoritative совместимый ledger; новый review ссылается на `results.id`.                                                                                                                                                  |
| `written_tasks_discussions`                       | Telegram-тред, text/attach path/message IDs                                                     | Двойное чтение/запись во время миграции; backfill в новый thread/entry model.                                                                                                                                                        |
| `written_tasks_queue`                             | Одна активная очередь на student/problem с 30-минутным claim                                    | Эволюционировать lease-полями, сохранив текущий Telegram path.                                                                                                                                                                       |
| `questions` и negative problem IDs                | SOS/вопросы                                                                                     | Перенести в явные support threads через dual-write, только затем убрать special IDs.                                                                                                                                                 |
| `reactions` + enums                               | Реакции на result/zoom                                                                          | Расширить actor/visibility, сохранив существующие IDs и Telegram rendering.                                                                                                                                                          |
| `user_changes_log`                                | История group/online changes                                                                    | Сохранить; новые изменения режима/уровня обязаны писать совместимое событие.                                                                                                                                                         |
| `zoom_*`                                          | Устные разговоры, события и очередь                                                             | Сохранить как legacy oral ledger; новый UI строить через adapter/read model.                                                                                                                                                         |
| `surveys`, `assigns`, `choices`, `survey_results` | Опросы/назначения                                                                               | Сохранить только для legacy; UI опросов не входит в первую версию.                                                                                                                                                                   |
| `kv`, `webtokens`, `kv_logins`                    | Технические/legacy token данные                                                                 | Не использовать как неявный новый auth contract; провести security audit и миграцию секретов.                                                                                                                                        |

## 1. Сезоны, аккаунты и права

### `seasons`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `code TEXT UNIQUE` (например `2026`), `title TEXT`, `starts_on TEXT`, `ends_on TEXT`, `timezone TEXT DEFAULT 'Europe/Moscow'`, `session_expires_on TEXT`, `status TEXT CHECK(draft|active|archived)`, `created_at TEXT`, `updated_at TEXT`.

### `auth_accounts`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `audience TEXT CHECK(student|family|staff)`, `username TEXT`, `username_normalized TEXT`, `username_algorithm_version INTEGER NULL`, `provisioning_source TEXT`, `display_name TEXT NULL`, `credential_kind TEXT CHECK(telegram_token|password)`, `credential_hash TEXT NULL`, `linked_user_id INTEGER NULL FK users(id)`, `status TEXT CHECK(active|blocked|disabled|archived)`, `credential_version INTEGER DEFAULT 1`, `last_login_at TEXT NULL`, `created_at TEXT`, `updated_at TEXT`.

Constraints/indexes: `UNIQUE(audience, username_normalized)`, index `(linked_user_id, audience)`. Student username импортируется версионированным helper как транслитерация фамилии + день рождения; коллизия, `NULL`/невалидная дата, пустая фамилия или credential, не прошедший security policy, блокируют активацию строки и попадают в report. Источник student credential — текущий Telegram token; второй plaintext не создаётся. Family хранит только минимальное display name без email.

### `family_student_links`

`family_account_id INTEGER FK auth_accounts`, `student_user_id INTEGER FK users`, `relationship_label TEXT NULL`, `is_primary INTEGER DEFAULT 0`, `created_at TEXT`, `updated_at TEXT`, `revoked_at TEXT NULL`, PK `(family_account_id, student_user_id)`. Триггер разрешает owner только с audience `family`.

### `staff_scopes`

`id INTEGER PK`, `staff_user_id INTEGER FK users`, `course_id INTEGER FK courses`, `group_id TEXT NULL`, `role TEXT CHECK(teacher|admin)`, `valid_from TEXT`, `valid_to TEXT NULL`, `granted_by INTEGER NULL`, `revoked_by INTEGER NULL`, `reason TEXT NULL`, `created_at TEXT`, `updated_at TEXT`, `version INTEGER`. Scope без `group_id` покрывает курс, с `group_id` — только эту группу; composite FK запрещает ссылку на группу другого курса. Это единственный новый permission source: параллельная таблица `staff_group_permissions` не создаётся. Legacy admin остаётся глобальным bypass, а строка scope сама по себе не повышает teacher до admin.

### `telegram_bindings`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `owner_type TEXT CHECK(course|group)`, `owner_course_id INTEGER NULL FK courses`, `owner_group_id TEXT NULL FK groups`, `purpose TEXT CHECK(news_source|materials_target)`, `chat_id INTEGER`, `message_thread_id INTEGER NULL`, `title_cached TEXT NULL`, `status TEXT CHECK(draft|verified|disabled)`, `verified_at TEXT NULL`, audit timestamps, `version INTEGER`. Constraint требует ровно одного owner, соответствующего `owner_type`; effective-binding indexes защищают от двусмысленного активного назначения одной цели в одном scope/purpose.

`chat_id` — canonical `chat.id`, возвращённый Bot API, без ручного преобразования UI-значения. SQLite/Python используют 64-bit integer; поле не смешивается с `users.chat_id`. Перед `verified` probe проверяет `getMe`, `getChat` и требуемую capability бота. Course/group news sources складываются; group `materials_target` заменяет course default, иначе наследует его. Publication/delivery record snapshot-ит фактически использованные binding/chat/message IDs, поэтому последующая смена binding не переписывает историю. Bot token остаётся runtime credential и никогда не хранится в SQLite.

### `auth_sessions`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `account_id INTEGER FK auth_accounts`, `audience TEXT`, `refresh_secret_hash TEXT UNIQUE`, `credential_version INTEGER`, `version INTEGER`, `created_at TEXT`, `updated_at TEXT`, `last_seen_at TEXT`, `expires_at TEXT`, `revoked_at TEXT NULL`, `revoke_reason TEXT NULL`, `device_label TEXT NULL`, `user_agent_family TEXT NULL`, `ip_prefix TEXT NULL`.

`refresh_secret_hash` — только 64-символьный lowercase HMAC-SHA-256 digest. Indexes: `(account_id, revoked_at, expires_at)`, `(expires_at)`, `(audience, revoked_at, expires_at)`. Короткая signed cookie несёт только opaque session reference/version, не роль как источник истины. Refresh меняет digest и `version` атомарно.

### `auth_refresh_consumed_secrets`

`session_id INTEGER FK auth_sessions ON DELETE CASCADE`, `refresh_secret_hash TEXT`, `consumed_at TEXT`, `expires_at TEXT`, PK `(session_id, refresh_secret_hash)`, index `(expires_at)`. При успешной ротации старый HMAC сохраняется до истечения сессии. Только совпадение с этой bounded history является доказанным replay и мягко отзывает session lineage; произвольный неверный secret не выдаётся за replay и не позволяет отозвать чужую сессию по одному public ID. Raw refresh secret не сохраняется.

### `auth_events`

`id INTEGER PK`, `account_id INTEGER NULL`, `session_id INTEGER NULL`, `event_type TEXT`, `occurred_at TEXT`, `request_id TEXT`, `ip_prefix TEXT NULL`, `metadata_json TEXT`. Не хранить введённый token/password.

### `auth_throttle_buckets`

`audience`, `bucket_kind CHECK(normalized_login|account|ip)`, `bucket_key_hmac`, `key_version`, `failure_count`, `window_started_at`, `last_failed_at NULL`, `locked_until NULL`, audit timestamps и optimistic `version`; PK `(audience, bucket_kind, bucket_key_hmac, key_version)`. В таблице разрешены только HMAC-SHA-256 keys: normalized login, internal account reference и IP никогда не сохраняются открыто. nginx остаётся первым IP-level limit, а SQLite обеспечивает общий для нескольких aiohttp workers account/login state.

## 2. Контент, revisions и assets

### `content_sources`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `group_lesson_id INTEGER FK group_lessons`, `kind TEXT CHECK(condition|hint|solution|teacher_note)`, `logical_filename TEXT`, `source_encoding TEXT`, `created_at TEXT`, `created_by_user_id INTEGER FK users`, `archived_at TEXT NULL`. Legacy `season/lesson/group` выводятся через `group_lesson → course_lesson/group` и не являются вторым владельцем source.

Unique candidate: `(season_id, lesson_number, group_id, kind, logical_filename)`.

### `content_revisions`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `source_id INTEGER FK content_sources`, `revision_number INTEGER`, `source_sha256 TEXT`, `latex_text TEXT`, `parser_version TEXT`, `status TEXT CHECK(uploaded|compiling|ready|invalid|superseded)`, `canonical_json TEXT NULL`, `diagnostics_json TEXT`, `created_by_user_id INTEGER`, `created_at TEXT`, `supersedes_revision_id INTEGER NULL`.

Constraint: `UNIQUE(source_id, revision_number)` and `UNIQUE(source_id, source_sha256)` unless duplicate upload is intentionally logged separately.

### `media_assets`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `sha256 TEXT`, `storage_namespace TEXT CHECK(content|submission|news|annotation|generated)`, `object_key TEXT UNIQUE`, `public_url TEXT`, `media_type TEXT`, `byte_size INTEGER`, `width INTEGER NULL`, `height INTEGER NULL`, `source_filename TEXT NULL`, `conversion_version TEXT NULL`, `created_by_user_id INTEGER NULL`, `created_at TEXT`, `immutable_at TEXT NULL`, `deleted_at TEXT NULL`.

Indexes: `UNIQUE(storage_namespace, sha256, conversion_version)` для переиспользуемых content assets; submission assets могут не дедуплицироваться между учениками из соображений изоляции.

### `content_revision_assets`

`revision_id INTEGER FK content_revisions`, `asset_id INTEGER FK media_assets`, `logical_name TEXT`, `role TEXT CHECK(source|figure|tikz|pdf|preview)`, `ordinal INTEGER`, `alt_text TEXT NULL`, PK `(revision_id, logical_name, role)`.

### `content_derivatives`

`id INTEGER PK`, `revision_id INTEGER FK content_revisions`, `kind TEXT CHECK(web_ast|web_html|telegram_html|pdf|thumbnail)`, `renderer_version TEXT`, `content_text TEXT NULL`, `asset_id INTEGER NULL FK media_assets`, `sha256 TEXT`, `diagnostics_json TEXT`, `created_at TEXT`, `invalidated_at TEXT NULL`.

Unique: `(revision_id, kind, renderer_version)`.

### `content_problem_matches` и `problem_revisions`

Match: `id INTEGER PK`, `content_revision_id INTEGER`, `source_ordinal INTEGER`, `source_item TEXT`, `problem_id INTEGER NULL`, `decision TEXT CHECK(auto_position|manual_match|insert_new|omit)`, `resolved_by_user_id INTEGER NULL`, `resolved_at TEXT NULL`, `diagnostics_json TEXT`; unique `(content_revision_id, source_ordinal, source_item)`.

Revision: `id INTEGER PK`, `problem_id INTEGER FK problems`, `content_revision_id INTEGER FK content_revisions`, `source_ordinal INTEGER`, `source_item TEXT`, `display_number TEXT`, `title TEXT`, `problem_type INTEGER`, `answer_type INTEGER NULL`, `answer_config_json TEXT`, `attempt_policy_json TEXT`, `config_version INTEGER`, `created_at TEXT`, `created_by_user_id INTEGER`.

В исходном LaTeX нет обязательного stable ID. Первичное сопоставление идёт по порядку; любое структурное расхождение должно быть разрешено в `content_problem_matches` до публикации. Legacy `problems` остаётся projection для Telegram. `cor_ans_checker` хранится в versioned answer config либо в legacy row с hash revision; отсутствие готового checker не блокирует публикацию, но переводит новые ответы в pending check.

### `problem_synonym_groups` и `problem_synonym_members`

Group: `id INTEGER PK`, `public_id TEXT UNIQUE`, `course_lesson_id INTEGER FK course_lessons`, `group_key TEXT`, `display_title TEXT`, `created_by_user_id`, `created_at`, `updated_at`, `version INTEGER`.

Member: `id INTEGER PK`, `synonym_group_id INTEGER`, `problem_id INTEGER`, `added_by_user_id`, `added_at TEXT`, `removed_by_user_id NULL`, `removed_at TEXT NULL`, `membership_version INTEGER`. Active unique constraints запрещают problem одновременно состоять в двух synonym groups одного `course_lesson` и запрещают два active member одной synonym group внутри одного `group_lesson`. История merge/split не удаляется.

### `lesson_publications`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `group_lesson_id INTEGER FK group_lessons`, `kind TEXT CHECK(condition|hint|solution)`, `revision_id INTEGER FK content_revisions`, `state TEXT CHECK(scheduled|published|superseded|hidden)`, `scheduled_at TEXT NULL`, `published_at TEXT NULL`, `hidden_at TEXT NULL`, `published_by_user_id INTEGER`, `supersedes_publication_id INTEGER NULL`, `version INTEGER`. Condition/hint/solution одной группы независимы от другой даже при общем `course_lesson`.

### `lesson_windows`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `group_lesson_id INTEGER FK group_lessons UNIQUE`, `opens_at TEXT NULL`, `submission_closes_at TEXT`, `hint_scheduled_at TEXT NULL`, `solution_scheduled_at TEXT NULL`, `timezone TEXT`, `source TEXT CHECK(native|legacy_schedule|manual_backfill)`, `schedule_rule_version INTEGER NULL`, `created_by_user_id INTEGER NULL`, `created_at TEXT`, `updated_at TEXT`, `version INTEGER`.

Authoritative дедлайн сдачи — отдельный `submission_closes_at`, преобразованный в UTC из бизнес-зоны сезона. `solution_scheduled_at` управляет ожидаемой публикацией, а `lesson_publications.published_at` фиксирует фактическое событие. Эти timestamps могут совпасть, но один не выводится из другого. Клиент получает оба значения и никогда не вычисляет cutoff из локального календаря. По закрытому `SCHEDULE-01` правка расписания решения не меняет cutoff; дедлайн редактируется только отдельным confirmed/audited action.

Для первого запуска content migration создаёт revision/publication/window records и для уже прошедших занятий текущего сезона. Источник и точность исторического времени фиксируются в backfill report; неизвестный фактический timestamp не подменяется выдуманной точностью и не используется для ретроактивного отклонения legacy results.

### `hint_reveals` и `solution_reveals`

Одинаковая форма: `id INTEGER PK`, `student_user_id`, `problem_id`, `publication_id`, `revealed_at`, `request_id`; unique `(student_user_id, problem_id, publication_id)`. Событие создаётся после явного подтверждения.

## 3. Сдачи, тред и идемпотентность

### `submission_threads`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `student_user_id INTEGER`, `problem_id INTEGER`, `condition_revision_id INTEGER`, `status TEXT CHECK(open|awaiting_review|needs_work|accepted|closed)`, `latest_result_id INTEGER NULL`, `latest_entry_at TEXT`, `created_at TEXT`, `updated_at TEXT`, `version INTEGER`.

Recommended unique active thread: `(student_user_id, problem_id)`. История пересдач живёт внутри, а не в параллельных attempt threads.

### `submission_entries`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `thread_id INTEGER`, `author_kind TEXT CHECK(student|teacher|admin|ai|system)`, `author_user_id INTEGER NULL`, `channel TEXT CHECK(pwa|telegram|staff|system)`, `channel_group_key TEXT NULL`, `entry_kind TEXT CHECK(text|submission|teacher_comment|ai_comment|system_event)`, `state TEXT CHECK(draft|uploading|submitted|deleted|locked)`, `text TEXT NULL`, `client_created_at TEXT NULL`, `server_received_at TEXT`, `idempotency_key TEXT NULL`, `payload_sha256 TEXT NULL`, `legacy_discussion_id INTEGER NULL`, `version INTEGER`, `locked_at TEXT NULL`, `deleted_at TEXT NULL`.

Indexes: `(thread_id, server_received_at, id)`, unique `(author_user_id, idempotency_key)` when key not null.

### `submission_attachments`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `entry_id INTEGER`, `asset_id INTEGER FK media_assets`, `ordinal INTEGER`, `client_filename TEXT NULL`, `upload_status TEXT CHECK(pending|stored|failed|locked)`, `created_at TEXT`, `locked_at TEXT NULL`, `locked_by_result_id INTEGER NULL`, unique `(entry_id, ordinal)`.

Логическая письменная отправка становится `submitted` только после сохранения всех выбранных attachments. До первого review lock text/entry можно с подтверждением изменить или удалить. После lock исходная entry не меняется, но student может добавить новую entry в тот же thread. Review completion фиксирует все student entries, успевшие стать `submitted`; если thread version изменилась во время проверки, complete получает `409` и reviewer обязан обновить evidence, поэтому досланная фотография не теряется.

### `test_attempts`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `student_user_id INTEGER`, `problem_id INTEGER`, `problem_revision_id INTEGER`, `answer_payload_json TEXT`, `normalized_answer_json TEXT NULL`, `parse_status TEXT CHECK(valid|invalid_format)`, `counts_as_attempt INTEGER`, `check_status TEXT CHECK(pending_configuration|pending|checked|failed)`, `client_created_at TEXT`, `server_received_at TEXT`, `clock_skew_seconds INTEGER NULL`, `clock_suspicious INTEGER DEFAULT 0`, `idempotency_key TEXT`, `payload_sha256 TEXT`, `checker_version TEXT NULL`, `verdict INTEGER NULL`, `result_id INTEGER NULL FK results`, `created_at TEXT`, `checked_at TEXT NULL`.

Unique `(student_user_id, idempotency_key)`. Неразобранный ответ сохраняется, но `counts_as_attempt=0`. Все введённые ответы остаются в истории; после правильного разрешены новые. Ответ без настроенного checker остаётся `pending_configuration` до admin recheck. Расхождение времени больше часа ставит `clock_suspicious=1`, но offline-created-before-deadline ответ не отклоняется автоматически.

### `idempotency_records`

`id INTEGER PK`, `audience TEXT`, `account_id INTEGER`, `operation TEXT`, `idempotency_key TEXT`, `payload_sha256 TEXT`, `state TEXT CHECK(processing|completed|failed)`, `http_status INTEGER NULL`, `response_json TEXT NULL`, `created_at TEXT`, `completed_at TEXT NULL`, `expires_at TEXT NULL`, unique `(audience, account_id, operation, idempotency_key)`.

Повтор с тем же hash возвращает прежний результат; другой hash никогда не перезаписывает запись молча и требует нового ключа после явного подтверждения клиента.

## 4. Проверка и обратная связь

### Эволюция `written_tasks_queue`

Добавить: `claim_token TEXT NULL`, `claimed_at TEXT NULL`, `lease_expires_at TEXT NULL`, `lease_version INTEGER DEFAULT 0`, `updated_at TEXT`. Claim выполняется одним conditional `UPDATE`; heartbeat продлевает только совпадающий token. Telegram adapter использует тот же repository.

### `submission_reviews`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `thread_id INTEGER`, `queue_id INTEGER NULL`, `reviewer_user_id INTEGER`, `evidence_through_entry_id INTEGER`, `expected_thread_version INTEGER`, `verdict INTEGER`, `comment_entry_id INTEGER NULL`, `result_id INTEGER FK results`, `review_duration_sec INTEGER NULL`, `source TEXT CHECK(staff|telegram|ai)`, `created_at TEXT`, `corrected_at TEXT NULL`, `corrected_by_user_id INTEGER NULL`.

Review + актуальный legacy result + queue transition + asset locks записываются в одной SQLite transaction. Admin/teacher correction заменяет текущий verdict по совместимой логике `results`; prior state сохраняется только там, где это уже делает legacy history/provenance, а не через отдельный пользовательский статус спора.

### `review_annotations`

`id INTEGER PK`, `public_id TEXT UNIQUE`, `review_id INTEGER`, `attachment_id INTEGER`, `format_version INTEGER`, `rotation_quarter_turns INTEGER`, `annotation_json TEXT`, `preview_asset_id INTEGER NULL`, `telegram_composite_asset_id INTEGER NULL`, `created_by_user_id INTEGER`, `created_at TEXT`.

Original WebP не меняется. Annotation payload содержит карандаш/ластик, один из 4–5 цветов и координаты в normalized image space; zoom является viewer state. После отправки запись immutable. Для Telegram создаётся объединённый PNG derivative.

### Эволюция `reactions`

Добавить: `actor_user_id INTEGER NULL`, `actor_kind TEXT CHECK(student|teacher)`, `reaction_type_id INTEGER`, `visibility TEXT CHECK(student_family_admin|staff_admin|admin_only)`, `source TEXT CHECK(pwa|telegram|staff)`, `updated_at TEXT NULL`, `editable_until TEXT NULL`, `deleted_at TEXT NULL`, `metadata_json TEXT NULL`. Связь с конкретным verdict сохраняется через `result_id`. Partial unique index на `(result_id, actor_kind, actor_user_id) WHERE deleted_at IS NULL` разрешает одну активную реакцию соответствующего автора на проверку независимо от выбранного reaction type; PUT меняет `reaction_type_id`, DELETE ставит `deleted_at`, обе операции разрешены в течение часа.

Legacy backfill определяет `actor_kind` по `reaction_type_id`, а actor — через связанный `results.student_id`/`results.teacher_id` либо `zoom_conversation.student_id`/`teacher_id`. Перед partial unique index dry-run группирует дубли; самой поздней однозначной строке присваивается active-state, прежние сохраняются как migrated history/deleted. Строки без однозначно выводимого actor не угадываются: они попадают в quarantine/report и не участвуют в unique index до ручного решения.

### `ai_review_runs` (зарезервировано, не v1)

`id`, `thread_id`, `evidence_through_entry_id`, `model_provider`, `model_name`, `prompt_version`, `input_hash`, `status`, `output_text`, `output_svg`, `diagnostics_json`, `created_at`, `completed_at`. Не создавать до отдельного AI privacy/security решения.

## 5. Вопросы, устные занятия и аудитории

### `support_threads` и `support_entries`

Thread: `id`, `public_id`, `student_user_id`, `problem_id NULL`, `group_lesson_id NULL`, `kind CHECK(problem_question|sos|general)`, timestamps/version. Это диалоговая лента, а не назначаемая одному teacher заявка со статусом закрытия.

Entry: `id`, `thread_id`, `author_kind`, `author_user_id`, `text`, `asset_id NULL`, `channel`, `client_created_at`, `server_received_at`, `legacy_question_id NULL`, `legacy_problem_id NULL`.

### `oral_windows`

`id`, `public_id`, `group_lesson_id INTEGER FK group_lessons`, `sequence_number`, `opens_at`, `closes_at`, `join_label`, `join_url_encrypted_or_ref`, `join_code_encrypted_or_ref`, `status`, `created_by_user_id`, timestamps/version. Для одного `group_lesson` разрешено несколько окон (в текущем процессе три). Join secrets не попадают в list endpoint и логи; provider v1 — Zoom.

### `classrooms`

Глобальный каталог, не привязанный к занятию: `id INTEGER PK`, `public_id TEXT UNIQUE`, `name TEXT`, `normalized_name TEXT UNIQUE`, `status TEXT CHECK(active|archived)`, `created_by_user_id`, `updated_by_user_id`, `archived_by_user_id NULL`, `restored_by_user_id NULL`, `created_at`, `updated_at`, `archived_at NULL`, `restored_at NULL`, `version INTEGER`.

`name` сохраняет внутренние пробелы, но до записи обрезается по краям и не может стать пустым. `normalized_name` вычисляет один общий domain helper: `NFKC(trim(name)).casefold()`. Уникальный индекс на `normalized_name` ловит в том числе кириллические дубликаты `Актовый зал`/`актовый зал`. SQLite collation не является источником истины для Unicode casefold. Hard delete отсутствует; rename/archive/restore записывают audit `before/after`.

### `classroom_layout_versions`

Версия схемы «аудитория → группа» для очного события: `id INTEGER PK`, `public_id TEXT UNIQUE`, `in_person_event_id INTEGER FK in_person_events`, `base_version_id NULL`, `state TEXT CHECK(draft|confirmed|superseded)`, `created_by_user_id`, `confirmed_by_user_id NULL`, `created_at`, `updated_at`, `confirmed_at NULL`, `superseded_at NULL`, `version INTEGER`.

Для `in_person_event_id` существует не более одного активного draft. Просмотр нового события виртуально объединяет последние confirmed mappings участвующих групп; запрос просмотра не копирует строки. Первая мутация materialize-ит event draft со ссылкой на base/provenance versions и копией только выбранных групп. Финализированные версии не редактируются; новая confirmed-версия события supersede-ит его прежнюю версию, не меняя планы прошлых событий.

### `classroom_layout_rooms`

`layout_version_id`, `classroom_id`, `group_id`, `created_at`, `updated_at`; PK `(layout_version_id, classroom_id)`, FK на layout/classroom/group и индекс `(layout_version_id, group_id)`. Одна аудитория встречается в версии один раз, одна группа может иметь любое число аудиторий. Неиспользованная активная аудитория просто отсутствует в таблице. Полей вместимости, веса и level constraints нет.

### `classroom_assignment_plans`

Версия распределения для очного события: `id INTEGER PK`, `public_id TEXT UNIQUE`, `in_person_event_id INTEGER FK in_person_events`, `layout_version_id`, `base_plan_id NULL`, `state TEXT CHECK(draft|confirmed|stale|superseded)`, `stale_reason TEXT NULL`, `created_by_user_id`, `confirmed_by_user_id NULL`, `created_at`, `updated_at`, `confirmed_at NULL`, `superseded_at NULL`, `version INTEGER`.

Confirmed plan становится `stale`, если изменился effective layout или скрыта используемая аудитория. Транзакция скрытия материализует/обновляет replacement draft и создаёт затронутым школьникам строки `reassigning`; прежний confirmed plan не мутирует, но больше не считается действующим для текущего показа. Новый calculation всегда создаёт preview/draft; подтверждение новой версии supersede-ит старую, не перезаписывая её.

### `classroom_assignments`

`plan_id`, `course_enrollment_id`, `student_user_id`, `group_lesson_id`, `group_id` (snapshot), `classroom_id NULL`, `status TEXT CHECK(assigned|reassigning)`, `source TEXT CHECK(previous-room|least-loaded|manual|group-change|mode-change|import)`, `previous_classroom_id NULL`, `assigned_by_user_id NULL`, `created_at`, `updated_at`; PK `(plan_id, course_enrollment_id)`, indexes `(plan_id, student_user_id)` и `(plan_id, classroom_id)`.

`classroom_id` обязателен для `assigned` и отсутствует для `reassigning`. Domain validation запрещает назначить школьника в комнату другой группы или смешать группы в одной комнате. В confirmed plan каждый очный школьник имеет `assigned`; online student в плане отсутствует и получает публичный статус `not_applicable`. Очный школьник без действующего опубликованного назначения получает `reassigning`, а не `not_applicable`. Неиспользованные active rooms допустимы.

Детерминированный recalculation сначала находит последнюю историческую комнату школьника для текущей группы и сохраняет её как `previous_classroom_id`, если комната active и всё ещё связана с этой группой; это работает и при возвращении на прежний уровень. Затем остальные по одному назначаются в наименее заполненную комнату группы. Server natural sort сравнивает числовые фрагменты `normalized_name` как числа, остальные — как casefolded Unicode text, затем использует `classroom.id`; frontend не переопределяет tie-break. Смена группы/режима запускает те же правила для текущего школьника; без допустимой комнаты создаётся `reassigning` и blocking incident. Скрытие комнаты не меняет прошлые plans, а restore не возвращает назначения автоматически.

Classroom plan read model не дублирует профиль школьника в assignment row. Он join-ит `users` и `student_strength` и отдаёт: `display_name`, nullable `age_years`, nullable `grade`, nullable `strength`, текущие `group_id`/`classroom_id`, status/source и краткую confirmed classroom history. `age_years` вычисляется на текущую дату как `(today - birthday) / 365.25`, округляется до одного знака; невалидная/отсутствующая дата даёт `NULL`. UI strength — автоматически рассчитанное число 0–10 из совместимого с `a53_calc_rating_new.py` read adapter; точные внутренние simple/complex components не редактируются через Staff.

Group summary считает всех активных школьников выбранной группы, для которых на выбранное занятие действует очный режим, и отдельно число уже распределённых. Room summary считает назначенных очных школьников, средние возраст, класс и силу; каждый aggregate исключает собственные `NULL` и округляется до одного знака. Полнота age/grade/strength отдельным полем UI не показывается. История аудиторий выводится из immutable confirmed `classroom_assignment_plans` + `classroom_assignments`; отдельная таблица истории не нужна.

Select комнаты другой группы того же курса создаёт в локальном draft связанную пару `course enrollment group change + assignment`. Batch-save применяет её одной backend transaction, пишет `course_enrollment_events`, совместимый legacy event при необходимости и новую assignment row; без явного confirmation flag запрос отклоняется. Комната другого курса не является вариантом той же enrollment row. До batch-save изменения существуют только в account/event/base-version-scoped browser draft и не меняют authoritative SQLite.

### `group_banners`

`id`, `public_id`, `group_id`, `audience`, `html_sanitized`, `starts_at`, `ends_at`, `priority`, `dismissible`, `created_by_user_id`, timestamps/version. Разрешённый HTML минимум `i`, `b`, `a`, `code`; sanitizer policy версионируется.

## 6. Новости, push и delivery

### `news_posts`

`id`, `public_id`, `source CHECK(telegram|local)`, `source_binding_id INTEGER NULL FK telegram_bindings`, `owner_course_id INTEGER NULL`, `owner_group_id TEXT NULL`, `telegram_chat_id NULL`, `telegram_message_id NULL`, `telegram_media_group_id NULL`, `current_revision_id`, `published_at`, `hidden_at NULL`, `created_by_user_id NULL`, timestamps. Unique Telegram source identity. Для Telegram source owner определяется только по verified `telegram_bindings` с purpose `news_source`; unmapped channel update не угадывает course/group и попадает в diagnostics/quarantine. Concrete owner и фактические chat/message IDs snapshot-ятся и не переписываются после изменения binding.

### `news_revisions`

`id`, `post_id`, `revision_number`, `source_payload_json`, `pwa_html`, `telegram_html`, `plain_text`, `edited_at`, `created_at`, `source_hash`; unique `(post_id, revision_number)`.

### `news_media`

`post_id`, `asset_id`, `ordinal`, `caption`, `media_kind`; PK `(post_id, ordinal)`.

### `news_visibility`

`post_id`, `group_id NULL`, `audience`, `is_hidden`, `starts_at NULL`, `ends_at NULL`, `updated_by_user_id`, `updated_at`; unique `(post_id, group_id, audience)`.

### `notification_preferences`

`account_id`, `category`, `in_app_enabled`, `push_enabled`, `sound_enabled`, `quiet_starts_local`, `quiet_ends_local`, `timezone`, `updated_at`; PK `(account_id, category)`. Oral window defaults off, other supported categories on.

### `push_subscriptions`

`id`, `public_id`, `account_id`, `audience`, `endpoint_hash`, `endpoint_encrypted`, `p256dh_encrypted`, `auth_encrypted`, `device_label`, `created_at`, `last_success_at`, `failure_count`, `disabled_at`; unique `(account_id, endpoint_hash)`.

### `notification_events`

`id`, `public_id`, `account_id`, `category`, `dedupe_key`, `route`, `payload_json`, `occurred_at`, `deliver_after`, `read_at NULL`, `read_by_session_id NULL`, `created_at`; unique `(account_id, category, dedupe_key)`. Review events всех задач одного ученика агрегируются за 30 минут. Клиент измеряет непрерывные три секунды фактической видимости монотонным timer и отправляет идемпотентный read acknowledgement; server выставляет собственный `read_at`. Состояние общее для account и поэтому сходится между устройствами. Telegram `sent` не равен `read`.

### `notification_deliveries`

`id`, `event_id`, `channel CHECK(in_app|web_push|telegram)`, `destination_ref`, `state CHECK(pending|sending|sent|failed|suppressed)`, `attempt_count`, `next_attempt_at`, `last_error_code`, `sent_at`, timestamps.

### `classroom_assignment_delivery_batches`

`id`, `public_id`, `assignment_plan_id`, `assignment_plan_version`, `requested_by_user_id`, `channels_json`, `recipient_snapshot_hash`, `recipient_count`, `changed_since_previous_count`, `state CHECK(previewed|queued|sending|completed|completed_with_errors|cancelled)`, `idempotency_key`, `created_at`, `started_at NULL`, `completed_at NULL`, `version`. Batch создаётся только для confirmed plan и immutable snapshot получателей; draft/stale plan отправить нельзя. Изменение плана после batch не запускает доставку и появляется в следующем preview как `not announced`.

### `classroom_assignment_delivery_recipients`

`batch_id`, `student_user_id`, `course_enrollment_id`, `classroom_assignment_id`, snapshot публичного room/event text, `pwa_event_id NULL`, server-side `telegram_destination_ref NULL`, per-channel state/error/sent timestamps, unique `(batch_id, student_user_id, course_enrollment_id)`. Browser получает имя/счётчики/status preview, но не Telegram token/chat ID. PWA delivery создаёт Student in-app/push; Telegram delivery идёт в личный bot dialogue. Family rows не создаются.

### `delivery_outbox`

`id`, `topic`, `aggregate_type`, `aggregate_id`, `event_type`, `payload_json`, `created_at`, `claimed_at`, `claim_token`, `attempt_count`, `next_attempt_at`, `completed_at`. Нужен для durable side effects; NATS invalidation после commit может строиться из этого outbox.

### Вторая фаза: `broadcasts`, `broadcast_targets`, `broadcast_deliveries`

Эти таблицы не создаются в initial v1 migrations. Они проектируются вместе с финальным Markdown content contract, previews и delivery workflow второй фазы.

Broadcast: `id`, `public_id`, `title`, `pwa_html`, `telegram_html`, `category`, `state`, `scheduled_at`, `created_by_user_id`, timestamps/version.

Target: `broadcast_id`, `target_kind CHECK(group|user|audience)`, `target_id`, PK composite.

Delivery: `broadcast_id`, `account_id NULL`, `user_id NULL`, `channel`, `state`, `attempt_count`, `sent_at`, `error_code`, unique logical destination.

## 7. Прогресс и достижения

Отдельной таблицы Family self-check нет: действие исключено из первой версии и не влияет на прогресс.

### `achievement_definitions`

`id`, `code UNIQUE`, `audience`, `title`, `description`, `rule_version`, `rule_json`, `is_active`, `created_at`, `updated_at`.

### `user_achievements`

`id`, `definition_id`, `user_id`, `earned_at`, `evidence_json`, `notified_at NULL`, unique `(definition_id, user_id, rule_version/evidence scope — уточнить схемой)`.

Accepted counts и activity calendar сначала вычисляются из `results`, `submission_entries`, `user_changes_log` и read-only SQL. Accepted count использует `VERDICT_TO_NUM >= 0.9`; denominator считает problem items. Activity calendar схлопывает все отправки одного item за день в одно событие.

Кривые силы, сложность занятия, выбранный лучший уровень и violin зависят от алгоритма `_external_pipelines/a53_calc_rating_new.py`, а не только от ledger rows. Для них планируются измеренные persistent read models:

- `analytics_runs(id, public_id, algorithm, algorithm_version, input_through_result_id, state, started_at, completed_at, diagnostics_json)`;
- `student_lesson_metrics(run_id, student_user_id, lesson_number, group_id, simple_strength, complex_strength, max_complex_strength, solved_items, total_items)` с unique `(run_id, student_user_id, lesson_number)` и индексом для latest-by-student;
- при необходимости measured `lesson_problem_statistics`, если прямой read для violin/Staff table не укладывается в budget.

Job публикует полный successful run атомарно и обновляет совместимую latest projection `student_strength`; незавершённый run не виден API. Violin показывает число решённых items, cohort для прошлого урока выбирается по сохранённому лучшему уровню и публикуется только при `n >= 30`. Названия `temp_*` из внешнего скрипта не становятся production schema.

## 8. Аудит

### `audit_events`

`id`, `public_id`, `actor_user_id NULL`, `actor_account_id NULL`, `audience`, `action`, `object_type`, `object_id`, `request_id`, `before_json NULL`, `after_json NULL`, `occurred_at`, `ip_prefix NULL`.

Обязательный минимум: login в совместимости с `signons`, group/mode change в совместимости с `user_changes_log`. Content revisions, imports, review corrections и delivery сохраняют собственную provenance/history. Чтение чужой работы отдельно не аудитируется.

## Миграционная последовательность

| Этап | Логическая миграция                              | Backfill/совместимость                                                                                                                                          |
| ---: | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    0 | `pwa_schema_metadata` при необходимости          | Только schema snapshot/characterization, бизнес-данные не менять                                                                                                |
|    1 | `pwa_auth_accounts_sessions`                     | Создать accounts для seed; production backfill dry-run по users                                                                                                 |
|    2 | `pwa_content_revisions_assets_publications`      | Связать legacy problems/lessons; добавить group Telegram destination; backfill revision/publication/window для занятий 1–38 текущего сезона с provenance report |
|    4 | `pwa_test_attempts_idempotency`                  | Новые attempts dual-write в results                                                                                                                             |
|    5 | `pwa_submission_threads_entries_assets`          | Lazy backfill discussions по открываемому thread + batch tool                                                                                                   |
|    6 | `pwa_reviews_annotations_queue_leases_reactions` | Reviews dual-write results; исправить affinity `written_tasks_queue.teacher_id`; reaction actor/dedup dry-run; Telegram queue сохраняется                       |
|    7 | `pwa_support_oral_classroom_plans_banners`       | Questions/zoom читаются через adapter; одноразовый classroom Excel import проходит dry-run, старые plans не переписываются                                      |
|    8 | `pwa_news_notifications_delivery`                | Telegram posts импортируются идемпотентно                                                                                                                       |
|    9 | `pwa_family_achievements_analytics`              | Family links batch import; historical analytics snapshots/achievements backfill по versioned `a53` parity                                                       |
|   10 | `pwa_normalized_groups_imports`                  | Google replacement только после parity report                                                                                                                   |

## Проверки целостности, обязательные после каждой миграции

- `PRAGMA foreign_key_check` и `PRAGMA integrity_check`.
- Нет orphan ссылок между новыми таблицами и `users/problems/results`.
- Количество legacy rows до/после совпадает, если migration только добавочная.
- Dual-write test доказывает один logical event без дублей при retry.
- Backfill повторяется без изменения результата.
- Публичный API не раскрывает sequential internal IDs там, где это создаёт enumeration risk.

## Multi-course schema increment

Добавляются `courses`, `course_enrollments`, `course_group_access`, `course_enrollment_events`, `staff_scopes`, `course_lessons`, `group_lessons`, `course_schedule_rules`, `group_schedule_overrides`, `problem_synonym_groups`, `problem_synonym_members`, `telegram_bindings`, `in_person_events`, `in_person_event_group_lessons`. Existing `groups` получает `public_id`, `course_id`, `status`, `color_key`, audit timestamps и optimistic `version`; legacy `group_id` сохраняется.

Точные поля, unique/invariant rules и миграционная граница зафиксированы в [`docs/courses-groups-and-lessons.md`](../../docs/courses-groups-and-lessons.md). Phase 11 backfill создаёт курс «Математика 5–7» и не переписывает problem/submission/result/Telegram IDs. Synonym membership versioned; физическое перемещение истории запрещено.
