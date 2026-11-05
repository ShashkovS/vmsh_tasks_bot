# Controlled import Student-аккаунтов

Этот runbook относится к compatibility rehearsal legacy Student authentication.
Он не является target Staff batch, не создаёт Family/Staff accounts, курсы,
enrollments, интервалы доступа или события смены группы/режима.

Target v1 Student batch принимает явно заданные surname, name, optional
patronymic/birth date/grade, login и Telegram-token password. Конфликт login
получает предложенный случайный `-NN`; plaintext provisioning password
сохраняется для внешней email-рассылки наряду с Argon2 verifier. Ни этот
plaintext, ни email не входят в aggregate proof.

Реализация: [`auth_import.py`](../scripts/auth_import.py); проверки:
[`test_auth_import.py`](../../pwa_tests/test_auth_import.py). Канонический
генератор логина и нормализация Telegram-токена остаются в
[`models/pwa/auth.py`](../../models/pwa/auth.py).

## Жёсткая граница

- У команды нет default database path.
- `db/vmsh.db`, symlink на неё и hard link на неё всегда запрещены.
- Любой target физически находится только под dedicated
  `.runtime/auth-import/`, должен быть отдельной явно названной копией, иметь права без
  group/other access перед `apply` и уже содержать текущие yoyo migrations
  `0039`/`0040` со штатными hash.
- Snapshot обязан быть quiescent: рядом нет `-wal`, `-shm` или `-journal`.
  Сначала закрывают все процессы/соединения и штатно checkpoint-ят копию;
  importer не угадывает, полностью ли sidecar попал в backup.
- `inventory` и `preview` читают exact bytes через checked file descriptor,
  десериализуют их в query-only in-memory SQLite и не вычисляют Argon2 hashes.
- `apply` требует второй раз передать тот же точный путь через
  `PWA_AUTH_IMPORT_CONFIRM_DATABASE`/`--confirm-database`.
- Файл решений имеет mode `0600`, не может быть symlink/hard link и не содержит
  token или hash.

Подготовка disposable migration copy — отдельная maintenance/rehearsal
операция. Этот инструмент намеренно не умеет сам копировать или мигрировать
authoritative DB: смешение подготовки target и активации credentials увеличило
бы blast radius одной команды.

## Сначала локальная inventory

```bash
make pwa-auth-import-inventory \
  PWA_AUTH_IMPORT_DATABASE=.runtime/auth-import/vmsh-migrated-copy.sqlite3 \
  PWA_AUTH_IMPORT_REPORT=.runtime/auth-import/inventory-aggregate.json \
  PWA_AUTH_IMPORT_DETAIL_REPORT=.runtime/auth-import/inventory-owner-only.json
```

Aggregate report не содержит ID, фамилии, login candidates, tokens или hashes.
Owner-only report перечисляет все строки cohort и содержит только legacy user
ID, канонический login candidate, collision flag и blocker codes; так владелец
может явно отметить и валидный test account. Файл создаётся только под
`.runtime/auth-import/` с mode `0600`, игнорируется Git и не должен отправляться
в чат/issue.

## Контракт явных решений

Файл решений обязан содержать ровно эти поля. Ниже полностью синтетический
пример, а не готовое production-решение:

```json
{
  "schemaVersion": 1,
  "purpose": "phase1-student-auth-import",
  "studentUsernameAlgorithmVersion": 1,
  "cohort": { "legacyUserType": 1 },
  "excludedLegacyUserIds": [3],
  "collisionOverrides": [
    { "legacyUserId": 1, "username": "synthetic-a-02" },
    { "legacyUserId": 2, "username": "synthetic-b-02" }
  ]
}
```

`excludedLegacyUserIds` задаётся явно, даже когда список пуст. Каждая активная
строка с отсутствующей/невалидной датой рождения, пустой фамилией или
непригодным Telegram-токеном обязана быть исключена. Если после исключений
несколько строк дают один canonical username, override нужен для **каждой**
строки такой collision group. Override уже должен быть уникальным
нормализованным lowercase ASCII login; автоматического suffix по database ID
нет. Неизвестные IDs, лишние overrides, повторяющиеся IDs/usernames и строка,
одновременно указанная в двух списках, блокируют весь run.

Реальные exclusions и overrides владелец формирует по owner-only inventory.
Репозиторий их не угадывает и не содержит.

## Preview и apply

```bash
chmod 600 .runtime/auth-import/decisions.json

make pwa-auth-import-preview \
  PWA_AUTH_IMPORT_DATABASE=.runtime/auth-import/vmsh-migrated-copy.sqlite3 \
  PWA_AUTH_IMPORT_DECISIONS=.runtime/auth-import/decisions.json \
  PWA_AUTH_IMPORT_REPORT=.runtime/auth-import/preview-aggregate.json

make pwa-auth-import-apply \
  PWA_AUTH_IMPORT_DATABASE=.runtime/auth-import/vmsh-migrated-copy.sqlite3 \
  PWA_AUTH_IMPORT_CONFIRM_DATABASE=.runtime/auth-import/vmsh-migrated-copy.sqlite3 \
  PWA_AUTH_IMPORT_DECISIONS=.runtime/auth-import/decisions.json \
  PWA_AUTH_IMPORT_REPORT=.runtime/auth-import/apply-aggregate.json
```

Preview детерминирован для неизменных DB/decisions и откладывает проверку уже
существующего Argon2 hash до apply. Он не хеширует 1549 credentials и не пишет
progress state.

На текущей машине synthetic production-size preview из 1617 строк занимает
менее `1 s`; regression gate с запасом требует менее `5 s` и падает при любом
Argon2 hash/verify вызове. Три production-default Argon2 hashes синтетического
credential заняли `0.098 s` (`0.033 s` в среднем), то есть грубая линейная
оценка 1549 новых accounts — около `0.8 min` **до** write transaction. Полная
post-commit Argon2 verification добавляет примерно столько же; ориентир полного
первого apply — `1.6 min` плюс SQLite I/O. Это измерение для планирования
maintenance window, не SLA для другой машины.

Apply использует all-at-once семантику:

1. повторно строит полный план без записи;
2. вычисляет Argon2id только для ещё не созданных accounts, перед write lock;
3. открывает `BEGIN IMMEDIATE`, заново читает cohort и сравнивает полный план;
4. проверяет credentials уже существующих rows;
5. присваивает отсутствующие случайные независимые `usr-…` и `acct-…` public
   IDs и вставляет accounts одной транзакцией;
6. после commit повторно проверяет структуру результата.

Сбой до транзакции ничего не меняет; ошибка/остановка внутри неё откатывает все
rows средствами SQLite. Tokens и hashes не записываются в progress/report.
Исходный token остаётся в единственном legacy `users.token`, необходимом
параллельному Telegram-боту; новый `auth_accounts` получает только Argon2id над
`normalize_telegram_token(token)`.

Повтор с тем же decision contract идемпотентен: importer проверяет связь,
username algorithm/source/status, opaque IDs и Argon2 credential, не создаёт
новых rows и возвращает `already-applied`. Изменившийся token, decision contract
или частично несовместимое состояние блокируют run, а не чинятся молча.

## Что сознательно отложено

Этот инкремент не владеет backfill `courses`, `course_enrollments`,
`course_group_access` и `course_enrollment_events`. Для них требуется отдельное
утверждённое отображение legacy group/allowed_groups/online в курс. Повторные
одинаковые `G`/`O` строки при будущем backfill будут coalesced; текущий importer
не создаёт ни одного выдуманного события.
