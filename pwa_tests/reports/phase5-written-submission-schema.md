# Phase 5A — схема письменных тредов и неизменяемого evidence

Дата: 2026-07-28

Revision: `5acecbb`

## Проверяемый результат

Additive migration
[`0047.pwa_submission_threads_entries_assets.sql`](../../migrations/0047.pwa_submission_threads_entries_assets.sql)
создаёт целевой граф письменной сдачи, не переключая и не изменяя действующий
Telegram-контур `written_tasks_discussions`/`written_tasks_queue`:

- один активный `submission_thread` школьника на конкретную задачу;
- versioned `submission_entries` для текста, логической сдачи и будущих
  teacher/AI/system сообщений;
- до десяти `submission_attachments` с финальными WebP ≤1920 px;
- append-only `submission_material_reassignments` и явные item rows для
  исправления ошибочной привязки текста/фото к задаче;
- связь review lock с письменным `results.res_type = 2` и неизменяемость
  evidence после lock.

Rollback удаляет только объекты `0047`; точная последовательность
`up → down → up` восстанавливает предшествующую схему и данные без расхождений.

## Неочевидные решения

`submission_threads.condition_revision_id` ссылается на `content_revisions`,
потому что существующий публичный `conditionRevisionId` обозначает именно
опубликованную LaTeX-ревизию. Trigger дополнительно требует, чтобы для concrete
problem существовал `problem_revisions` внутри этой content revision.

`submission_attachments.ordinal` является неотрицательным разреженным числом,
а не диапазоном `0..9`. SQLite проверяет `UNIQUE(entry_id, ordinal)` немедленно
и не поддерживает deferred unique constraints, поэтому временный высокий
ordinal позволяет безопасно поменять две страницы местами без удаления уже
загруженного объекта. Отдельный trigger ограничивает фактическое число страниц
десятью.

Pending/client-original bytes не записываются в `media_assets`. Строка
attachment принимает только окончательный `storage_namespace = submission`,
`image/webp`, ненулевые dimensions не более 1920 и неудалённый asset. Временный
HEIC/JPEG и progress принадлежат будущему upload/outbox pipeline, а не durable
evidence graph.

## Инварианты SQLite

[`test_phase5_written_submission_schema_migration.py`](../integration/test_phase5_written_submission_schema_migration.py)
проверяет:

- scope задачи и condition revision, один active thread и допустимые переходы
  `open → awaiting_review → needs_work|accepted` с последующей пересдачей;
- optimistic version и монотонные timestamps;
- письменный `latest_result_id` того же школьника и задачи;
- student-author ownership, idempotency uniqueness, непустую опубликованную
  запись и terminal immutability;
- namespace/MIME/dimensions final asset, лимит 10, sparse reorder и запрет
  мутации/удаления после review lock;
- source/target/student scope переноса материала, принадлежность выбранного
  текста/attachment исходной entry и append-only audit;
- scoped foreign keys, `integrity_check`, additive row counts и точный rollback.

## Автоматические проверки

Проверено на Python 3.14.3:

```text
Phase 5A migration/invariant suite
5 PASS

schema lifecycle regression (Phase 2 + Phase 5A + inventory)
30 PASS

fresh migration-derived schema inventory
261 product objects
sha256 fcec02abb06c4b8c28f113f872a39c507f790fc95aa35a67da530b279f1cf7db

full frontend unit
42 files / 323 PASS

full pwa_tests
1185 PASS / 3 intentional skips / 1 existing SymPy warning

Ruff + schema check + git diff --check
PASS
```

Generated artifacts обновлены только штатной командой `make pwa-schema-update`:

- [`schema_inventory.v1.json`](../fixtures/schema_inventory.v1.json);
- [`schema_snapshot.sql`](../fixtures/schema_snapshot.sql);
- [`docs/db_structure.sql`](../../docs/db_structure.sql).

## Изоляция

Тесты применяли migration только к временным synthetic SQLite. `db/vmsh.db`,
Telegram, Google, S3 и внешняя сеть не использовались. Legacy таблицы не
backfill-ились и не менялись.

## Следующий инкремент Phase 5

Phase 5A создаёт только durable identity/evidence boundary. Ещё не реализованы:

- repository и authenticated thread/entry HTTP API;
- streaming upload, MIME sniffing, WebP conversion и cleanup compensation;
- localStorage/Dexie composer outbox и production Student UI;
- lazy/batch import `written_tasks_discussions`;
- material reassignment repository/API/UI;
- Storybook interaction, production-browser E2E и visual owner gate.

Эти границы не считаются доказанными наличием таблиц.
