# Auth preflight

Источник: `db/vmsh.db`; режим: `secure pre-open fd with strongest available nofollow flag; exact bytes read+SHA-256 on that fd; in-memory sqlite deserialize; PRAGMA query_only=ON; explicit read transaction; source path/fingerprint rechecked; WAL/journal sidecars refused`.
Источник после чтения не изменился: **да**.

Отчёт содержит только агрегаты. Реальные фамилии, login candidates, tokens,
chat IDs и user IDs не сохранялись.

## Cohort

- Student (`users.type = 1`): 1617
- Исключены как non-Student по явному `type`: 662
- Строки с неизвестным `users.type`, агрегировано без raw value: 0
- Явного test-account flag нет; число доказуемо тестовых строк: **неизвестно**.

Строки не классифицировались по имени, token, group или identifier.

## Поля Student

- birthday valid ISO date: 1607
- birthday NULL/blank: 10
- birthday invalid/future: 0
- surname empty after trim: 0
- surname present, but canonical login stem empty: 0
- проходят field/token checks: 1607
- имеют field/token blocker: 10
- входят в collision канонического login v1: 58
- можно активировать до явных admin overrides: 1549

Это точный dry-run канонического генератора для выбранного `users.type = 1`
cohort до явных admin overrides. Явного признака test-account в legacy-схеме нет;
поэтому test/unknown exclusions всё равно должны быть утверждены перед apply.

### Длины token

- `0`: 0
- `1-5`: 0
- `6-7`: 9
- `8-11`: 1608
- `12-15`: 0
- `16-31`: 0
- `32+`: 0

### Консервативные guessable-shape сигналы

- `shorterThan8`: 9
- `digitsOnly`: 0
- `singleRepeatedCharacter`: 0
- `commonPlaceholder`: 0
- `sameAsChatId`: 0
- `anyGuessableShape`: 9

Категории могут пересекаться; `anyGuessableShape` считает уникальные Student rows.

## Login collisions

- Canonical Student username algorithm version:
  1.
- Точный dry-run `transliterated-surname-DD`: groups
  29, affected rows
  58. Сами login candidates не сохранялись.
- Legacy `kv_logins`: rows 627, blank
  0, normalized collision groups
  0, affected rows
  0.

До активации Phase 1 нужно явно разрешить каждую collision сохранённым уникальным
override и утвердить launch cohort. Автоматические row-ID suffixes запрещены.
