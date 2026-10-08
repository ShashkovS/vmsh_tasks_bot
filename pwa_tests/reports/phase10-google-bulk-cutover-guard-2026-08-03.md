# Phase 10: fail-closed guard полного Google import

Дата проверки: 3 августа 2026 года.

## Проверяемый результат

После первого частичного перехода на Staff владелец deployment config ставит
`allow_google_update_all=false`. С этого момента legacy-композиция шести Google
листов отказывается **до** сетевого чтения и до любой записи SQLite.

Решение намеренно мало:

- один boolean в существующем legacy JSON config;
- одна проверка в `FromGoogleSpreadsheet.update_all()`;
- одно специальное исключение без пользовательского текста;
- Telegram handler переводит его в существующий локализуемый `msgs` boundary,
  пишет privacy-safe trace и завершает команду без перерегистрации group
  commands;
- индивидуальные `update_*` методы не проверяют bulk guard и остаются явным
  recovery path до cutover собственного домена.

Новая таблица, migration, repository, feature-flag service или частичная
транзакция поверх шести legacy loaders не добавлялись. Boolean достаточен:
после первого доменного cutover полный шестилистовый import небезопасен при
любом наборе уже переведённых доменов.

## Исполняемые проверки

- disabled guard вызывает `GoogleBulkUpdateDisabled` и не вызывает
  `get_all_from_spreadsheet`;
- при disabled guard отдельный `update_problems` читает ровно свой лист и
  возвращает результат существующего importer;
- Telegram `/update_all` показывает понятный отказ и не вызывает
  `register_group_switch_commands`;
- обычный default остаётся `true`, поэтому существующий production/test config
  не меняет поведение до явного cutover.

Focused regression:

```text
tests/test_spreadsheets_loader.py + tests/test_admin_weekly_ops.py
18 passed
```

Полный regression после добавления trace label в строгий workload allowlist:

```text
legacy: 124 passed / 1 intentional skip, 11.68 s
PWA:    1586 passed / 6 intentional skips, 61.77 s
```

Первый полный запуск честно остановился на единственном новом событии
`admin.data.sync.blocked`, отсутствовавшем в `_KNOWN_EVENT_LABELS`. Label
добавлен в исполняемый allowlist; повторный полный PWA-набор прошёл. Trace не
содержит Google payload, worksheet key или credentials.

Legacy-файлы исторически не проходят полный современный Ruff из-за существующих
star-imports, bare `except` и unused imports. Эти несвязанные места не
переформатировались. Совместимый scoped Ruff с исключением только перечисленных
legacy codes прошёл, как и `git diff --check`.

## Операционная граница

Guard не объявляет ни один Google-домен переключённым и сам не меняет config.
Дата и владелец первого cutover остаются production acceptance gate. После
переключения пустую production SQLite нужно восстанавливать из проверенного
backup: автоматический `update_from_google_if_db_is_empty()` также получит тот
же fail-closed отказ, потому что вызывает `update_all()`.
