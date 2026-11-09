# Phase 2: historical content backfill proof

Дата проверки: 27 июля 2026 года.

Статус инкремента: безопасный CLI, dry-run contract и синтетический apply
готовы. Production backfill занятий 1–38 **не выполнялся**: для него ещё нужны
просмотренный mapping, полный внешний source corpus и отдельная мигрированная
анонимизированная копия SQLite.

## Реализация

- CLI/module:
  [`vmshpwa/scripts/content_history_backfill.py`](../../vmshpwa/scripts/content_history_backfill.py).
- Focused tests:
  [`pwa_tests/test_content_history_backfill.py`](../test_content_history_backfill.py).
- Authoritative phase contract:
  [`vmshpwa/dev/development-plan/06-phase-2-content.md`](../../vmshpwa/dev/development-plan/06-phase-2-content.md).
- Persistence boundary:
  [`migrations/0041.pwa_content_lessons.sql`](../../migrations/0041.pwa_content_lessons.sql).

Инструмент обнаруживает legacy `lessons`/`problems` в явно заданном диапазоне,
а не содержит специального кода для занятия 39. Focused corpus доказывает
границы 1 и 38, а отдельная проверка использует реальный CP1251-файл
`_vmsh_examples/usl-21-n.tex`: 11 верхнеуровневых задач и подпункты правильно
сводятся к 16 legacy problem rows.

## Mapping contract

Mapping — строгий UTF-8 JSON без повторных ключей:

```json
{
  "schemaVersion": 1,
  "purpose": "phase2-content-history-backfill",
  "backfillId": "owner-reviewed-history-v1",
  "recordedAt": "2026-07-27T18:00:00Z",
  "seasonPublicId": "season-public-id",
  "coursePublicId": "course-public-id",
  "legacyLessonRange": { "first": 1, "last": 38 },
  "groupMappings": [
    {
      "legacyGroupId": "legacy-group-id",
      "targetGroupPublicId": "target-group-public-id"
    }
  ],
  "lessonMappings": [
    {
      "legacyGroupId": "legacy-group-id",
      "legacyLessonNumber": 1,
      "courseLessonNumber": 1,
      "cycleAnchorDate": "2025-09-01",
      "businessTimezone": "Europe/Moscow",
      "timestamps": {
        "opensAt": null,
        "submissionClosesAt": null,
        "hintScheduledAt": null,
        "solutionScheduledAt": null
      },
      "materials": [
        {
          "kind": "condition",
          "sourcePath": "relative/path/to/lesson.tex",
          "publishedAt": null
        }
      ]
    }
  ]
}
```

Каждая найденная пара `legacyGroupId + legacyLessonNumber` обязана иметь ровно
одно явное сопоставление. `condition` указывается явно; hint/solution можно не
добавлять, если исторического source нет. Пути source относительны mapping-файлу
и проходят descriptor/symlink/hard-link checks.

## Двухшаговый запуск

Сначала создаётся deterministic aggregate preview:

```console
python -m vmshpwa.scripts.content_history_backfill preview \
  --source-db /path/to/anonymized-read-only-copy.sqlite3 \
  --mapping /path/to/owner-reviewed-mapping.json \
  --report /path/to/preview.json
```

Apply требует SHA-256 именно этого preview:

```console
python -m vmshpwa.scripts.content_history_backfill apply \
  --source-db /path/to/anonymized-read-only-copy.sqlite3 \
  --target-db .runtime/content-history-backfill/migrated-copy.sqlite3 \
  --mapping /path/to/owner-reviewed-mapping.json \
  --expected-preview-sha256 PREVIEW_SHA256 \
  --report /path/to/apply.json
```

Apply target обязан:

- быть отдельным от source обычным single-link файлом с mode `0600`;
- находиться под `.runtime/content-history-backfill/`;
- быть на текущем migration head с таблицами Phase 2;
- содержать тот же fingerprint выбранных legacy lesson/problem rows;
- не быть `db/vmsh.db` либо filesystem alias этого файла.

## Доказанные инварианты

- Source читается через один checked descriptor, затем через
  `sqlite3.Connection.deserialize()` + `PRAGMA query_only = ON`; SQLite не
  открывает source path повторно для запросов.
- Source fingerprint проверяется до и внутри apply transaction. Source никогда
  не является writable SQLite target.
- Apply начинается только после совпадения reviewed preview hash, выполняется
  под `BEGIN IMMEDIATE` и откатывается целиком при конфликте. Preview включает
  только безопасный `inputBindingSha256`: он связывает подтверждение с точными
  mapping semantics, датами, target scope, hashes всех TeX-входов, compiler
  version и hashes производных, не раскрывая пути или содержимое.
- Все новые public IDs детерминированы из backfill identity/scope/hash; повторный
  apply создаёт ноль строк и возвращает `already-applied`.
- До/после сравнивается fingerprint всех выбранных legacy lesson/problem rows;
  legacy IDs и payload не переписываются.
- Известный legacy `foreign_key_check` baseline сравнивается до/после. Инструмент
  не объявляет старые orphan rows исправленными, но запрещает добавить новый
  defect; `integrity_check` обязан вернуть `ok`.
- Неизвестный cutoff не превращается в вымышленный `submission_closes_at`:
  `lesson_windows` не создаётся. Неизвестный publication time не создаёт
  `lesson_publications`.
- В immutable `content_revisions.provenance_json` неизвестные времена остаются
  `{value: null, source: manual_backfill, precision: unknown}`. Известные
  значения имеют provenance `explicit_mapping/exact`.
- Известная историческая публикация помечается
  `lesson_publications.provenance_kind = legacy_backfill`; исходный actor
  остаётся `null`, а не подменяется текущим администратором. Для обычных
  `interactive` публикаций database guard по-прежнему требует реального actor.
- Condition source компилируется тем же Phase-2 compiler. Flattened число задач
  и подпунктов обязано совпасть с числом legacy problem rows; metadata сохраняет
  ссылку на исходный `problems.id`.
- Равные нормализованные title разных групп одного course lesson дают только
  aggregate `duplicateTitleCandidate`; synonym-group автоматически не создаётся.
- Report не содержит имён, фамилий, Telegram token/chat ID, правильных ответов,
  checker source, problem title, source text/path либо message body. Privacy test
  специально кладёт synthetic user/token в копию и доказывает их отсутствие.

## Решения из implementation questions

Production rehearsal делается только на отдельной копии `db/vmsh.db`; до
передачи копии тестам имена и фамилии заменяются Faker-значениями. Копия и
row-level mapping/report не коммитятся. Этот content CLI вообще не читает
`users`, `user_changes_log` или `written_tasks_discussions`; synthetic test
моделирует уже анонимизированную copy shape.

Схлопывание последовательных одинаковых `G`/`O` относится к отдельному backfill
`course_enrollment_events`. Перенос `written_tasks_discussions` одной общей
хронологией без выдуманных review-round/verdict links относится к Phase 5/6.
Этот Phase-2 инструмент не затрагивает обе таблицы и тем самым не создаёт
преждевременную несовместимую интерпретацию.

## Проверка

```console
.venv/bin/ruff check \
  vmshpwa/scripts/content_history_backfill.py \
  pwa_tests/test_content_history_backfill.py
# All checks passed!

.venv/bin/pytest -q -n0 pwa_tests/test_content_history_backfill.py
# 13 passed

UV_CACHE_DIR=.runtime/uv-cache uv run pytest -q -n0 \
  pwa_tests/test_content_history_backfill.py \
  pwa_tests/integration/test_phase2_content_schema_migrations.py \
  pwa_tests/domain/test_content_compiler.py
# 50 passed
```

Покрыты:

1. deterministic dry-run без записи source/target;
2. диапазон 1–38, обнаруживаемый из SQLite;
3. apply + repeat/idempotency и отказ после изменения даты, target mapping или
   TeX с тем же числом задач;
4. запрет authoritative target и source/target alias;
5. обязательный reviewed preview hash;
6. task-count mismatch;
7. missing source и missing group lesson;
8. unsupported source encoding;
9. unknown timestamp provenance без retroactive deadline;
10. duplicate-title candidate без автоматического merge;
11. privacy-safe temporary anonymized-copy shape;
12. реальный CP1251 corpus из `_vmsh_examples`.

## Оставшиеся production gates

- Получить полный owner-reviewed mapping занятий 1–38 и пути к Dropbox/source
  corpus. В репозитории есть только выборочные уроки 21/27 и acceptance 39–41.
- На отдельной согласованной копии выполнить Faker-анонимизацию, migration
  rehearsal, preview и ручной просмотр всех diagnostics. Сам `db/vmsh.db` не
  менять.
- Разрешить все `missingSource`, `missingGroupLesson`, `taskCountMismatch` и
  compiler diagnostics до apply.
- После apply сравнить Student/Family historical read model и Telegram legacy
  projection; HTTP/UI wiring не входит в этот инкремент.
- Записать runtime proof с aggregate counts/hash без source text, task titles,
  answer/checker data или персональных данных.
