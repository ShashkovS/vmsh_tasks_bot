# Baseline-v1 seed report

Проверено 27 июля 2026 года на Python 3.14.3.

## Результат

- Fixture: `baseline-v1`.
- Canonical data SHA-256: `193cc450349f18240fe36f3f1de513fba1d827604cc6569ceff79d06b50afaa3`.
- Два последовательных `make pwa-agent-seed` создали одинаковое логическое состояние.
- Установленная база прошла `PRAGMA integrity_check` и scoped `foreign_key_check` без исключений на fresh migration head.
- В успешно установленном final artifact migration-carried `kv_logins` удалены до наполнения; после `VACUUM` их исходные байты в нём не остаются.
- В fixture нет персональных данных, live Telegram tokens/chat IDs, production URL или скопированных значений пользовательских строк из рабочей БД.

## Данные

| Таблица | Строк |
| --- | ---: |
| `groups` | 5 |
| `users` | 4 |
| `student_strength` | 1 |
| `lessons` | 9 |
| `problems` | 16 |
| `states` | 4 |
| `user_changes_log` | 4 |
| `written_tasks_discussions` | 6 |
| `written_tasks_queue` | 2 |
| `results` | 2 |
| `kv` | 1 |
| `kv_logins` | 0 |

Есть synthetic Student online, Student in-person, Teacher и Admin. Family persona пока хранится только в manifest и будет материализована миграцией Phase 1. Fixture охватывает занятия 39–41, четыре legacy `PROB_TYPE`, synonym set, queued/claimed review, discussion и результаты по обе стороны submission cutoff. Все 23 значения `ANS_TYPE` перечислены в отдельном `answer-types-v1.json`; каждый положительный и отрицательный пример проверяется против исторической валидации. Fixture намеренно сохраняет неожиданные свойства legacy regex: `7/3` проходит как `FLOAT`/`FLOAT_EPS`, а `1.5` — как `INT_SEQ`/`INT_SET`.

## Безопасность замены

Seed принимает только точные `pwa-human`, `pwa-agent` и `pwa-e2e` profile/path combinations, запрещён в production и отказывается от symlink/hardlink на authoritative database. Новая база строится и проверяется в sibling temporary file с правами `0600`, синхронизируется и устанавливается через atomic replace; обычная ошибка до replace сохраняет прежнюю базу и удаляет temporary file. Два runtime worker могут одновременно держать shared lifecycle lock, а seed/migrate получают только exclusive lock. Lock живёт до aiohttp cleanup после draining запросов; отдельный процесс не может открыть старую БД в прежнем окне между финальной проверкой и replace.

Migration 0038 сначала создаёт в этом temporary file исторические credential-bearing строки, после чего seed удаляет их и выполняет `VACUUM`. Поэтому утверждение выше относится именно к успешно установленному final artifact. Аварийное завершение процесса или `SIGKILL` между migration и purge может оставить защищённый temporary file с этими литералами; до исправления самой migration такие остатки нужно считать чувствительными и удалять по отдельной операционной процедуре.

После replace seed отдельно синхронизирует каталог. Если этот последний `fsync` недоступен, замена уже состоялась: команда возвращает отчёт с `durability_confirmed=false` и явным предупреждением, а не утверждает, что прежняя база сохранилась. Это означает, что содержимое валидно в текущем процессе, но переживание немедленного сбоя питания не подтверждено.

Оставшиеся SQLite sidecars не удаляются вручную. Seed даёт SQLite выполнить recovery/checkpoint и корректное закрытие, а при busy connection или неубранном sidecar отказывается продолжать. Проверки покрывают stale WAL recovery и активного writer.

## Проверки

- `pwa_tests/test_seed_runtime.py`, `pwa_tests/test_maintenance_commands.py`, `pwa_tests/test_app_factory.py` и `pwa_tests/integration/test_runtime_lifecycle_lock.py`: 129/129 PASS.
- Agent-profile smoke: два последовательных запуска PASS с одинаковым digest.
- Sidecar smoke: после каждого завершённого seed отсутствуют `-wal` и `-shm`.
- Fault injection: нарушение каждого из трёх пригодных FK в legacy `reactions` обнаруживается при исключении только известного malformed Zoom FK; ошибка final directory `fsync` возвращает `durability_confirmed=false` после состоявшегося replace.
