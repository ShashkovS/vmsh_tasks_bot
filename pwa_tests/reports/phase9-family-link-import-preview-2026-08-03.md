# Phase 9: read-only Family-link import preview

Дата проверки: 3 августа 2026 года.

## Проверяемый результат

- CSV связывает только уже существующие Family-аккаунты и Student public IDs;
  паролей и создания аккаунтов в этом формате нет.
- Parser использует те же NFKC/login/relationship rules, что индивидуальный
  Staff flow, требует точный header и отклоняет повтор одной пары.
- Preview открывает выбранную SQLite через `mode=ro` и `PRAGMA query_only`.
  Он классифицирует строку как `create`, `restore`, `update` или `unchanged`, но
  не выполняет ни одной записи.
- JSON содержит только aggregate counts, SHA-256 локального CSV, номера строк и
  стабильные diagnostic codes. Family username и Student public ID не
  копируются в отчёт.
- Команда `make pwa-family-link-import-preview` требует явные пути БД и CSV;
  optional report остаётся локальным operational artifact.

## Автоматические доказательства

```text
Pure parser/domain
  exact header, normalization, booleans, duplicates, structural errors

Migrated SQLite integration
  create / restore / update / unchanged
  missing Family / missing Student redaction
  database SHA-256 unchanged

CLI
  exit status, JSON stdout and local report parity

Result
  5 passed

Ruff format/check
  pass

Complete Python regression (8 isolated xdist workers per suite)
  legacy: 121 passed, 1 intentional skip in 15.26 s
  PWA:    1573 passed, 6 intentional skips in 80.40 s
  wall:   99.83 s
```

Frontend, Storybook и visual snapshots этот Python/CLI-инкремент не меняет.

## Файлы

- `models/pwa/family_link_import.py` — чистый CSV parser;
- `db_methods/pwa/family_link_import.py` — три коротких SQLite read;
- `vmshpwa/scripts/family_link_import.py` — read-only preview/CLI;
- `vmshpwa/docs/family-link-import.md` — формат и runbook;
- `pwa_tests/domain/test_family_link_import.py`;
- `pwa_tests/integration/test_phase9_family_link_import.py`.

## Честная граница

Это закрывает software tooling и синтетический dry-run, но не production
acceptance. Реального файла семей владельцем пока не предоставлено, а batch
provisioning новых Family-аккаунтов и передача первого пароля зависят от
вопроса 1 в `vmshpwa/dev/development-plan/22-development-questions.md`.
Apply-команда до этого решения сознательно отсутствует.
