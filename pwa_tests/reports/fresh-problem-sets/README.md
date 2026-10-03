# Начать загрузку задач с нуля — 2 октября 2026

Кнопка «Не метчить, начать с нуля» находится в шапке сопоставления нового
условия и доступна до выбора строк. Один запрос создаёт новый набор задач и
открывает таблицу metadata с первоначальными значениями для заполнения.
Сохранение этой таблицы остаётся обычным обязательным шагом перед публикацией.

Решение: [Phase 2, MATCH-04](../../../vmshpwa/dev/development-plan/06-phase-2-content.md#сопоставление-задач-и-metadata-review).
UI: [ProblemMatching](../../../vmshpwa/packages/product/src/problem-matching.tsx),
[ProblemReviewWorkflow](../../../vmshpwa/apps/staff/src/problem-review-workflow.tsx),
[состояния и interactions](../../../vmshpwa/packages/product/src/staff-data.stories.tsx).
Transport: [контракт](../../../vmshpwa/packages/contracts/src/content-api.ts),
[клиент](../../../vmshpwa/packages/content/src/content-client.ts),
[PUT problem-matches](../../../apps/pwa_api/content_routes.py).
Storage: [repository](../../../db_methods/pwa/content.py),
[migration 0109](../../../migrations/0109.pwa_fresh_problem_sets.sql).

Старые строки `problems`, результаты и metadata сохраняются с прежними ID.
`content_problem_slots` хранит отображаемые пункты новых записей и retirement
прежнего набора. `problem_catalog` сохраняет привычную форму чтения и номера;
`active_problems` выбирает текущий набор для Telegram и нового matching.
Новые внутренние уникальные slots позволяют повторять номера и пункты.
Для ранее проверенных revision эта команда закрыта, чтобы сохранить их
позиционную metadata. Поздний retry принятого reset не меняет следующий набор.
[Telegram-чтение](../../../db_methods/db_problems.py),
[импорт с сохранением slot](../../../db_methods/pwa/problem_imports.py),
[история](../../../db_methods/pwa/student_results.py) используют эти проекции.

## Проверки

- 51 repository/schema/migration check: `test_content_repository.py`,
  `test_schema_inventory.py`, `test_phase3_problem_identity_migration.py`.
  Проверены stale version, отдельные ID при совпадающих позициях, архив старых
  записей, повторный reset, delayed retry и legacy/import display projection.
- 143 совместимых сценария: импорт, synonyms, legacy print, статистика,
  live marking, review queue/series, результаты, support и `tests/test_db_methods.py`.
- Новый real-aiohttp flow проходит upload → start fresh → новая таблица →
  сохранение metadata. Проверены строгий boolean, повтор, история предыдущей
  версии и запрет сброса reviewed revision:
  [`test_content_http_api.py`](../../integration/test_content_http_api.py).
- 48 frontend tests проходят; финальный повтор workflow после ограничения
  shortcut — 8. [`problem-review-fresh.test.tsx`](../../../vmshpwa/apps/staff/src/problem-review-fresh.test.tsx)
  покрывает один полный запрос, обход всех локальных решений, очистку draft,
  pending, ошибку сети и конфликт без автоматического повторного reset.
- 5 Storybook/a11y scenarios проходят. Визуально проверены 1280/640 px,
  русская светлая и английская тёмная темы: [1280 px](button.png),
  [640 px](button-640.png), [English/dark](button-en-dark.png).
- Workspace typecheck, дополнительный Staff typecheck, scoped ESLint,
  Ruff и форматирование изменённых TS-файлов проходят; `git diff --check` чистый.
  Каталоги извлечены, переводы и слияние каталогов проверены; schema inventory
  соответствует migration head (503 объекта). Staff/Student/Family/Landing
  builds проходят.

Проверки используют Node 26.9.0, pnpm 11.15.1 и изолированные тестовые базы.
После автоматического пересоздания `node_modules` в песочнице зависимости
восстановлены с `--frozen-lockfile`; финальные ESLint/Vitest/Vite/Lingui команды
запущены напрямую из локальных `.bin` без изменения lockfile.

Общий frontend run: 1004 прошли, 3 упали. Два telemetry-теста прошли при
отдельном повторе; `staff-testing-page.test.tsx` продолжает ожидать русскую
строку при английском API error. Общий Python run остановлен после обнаружения
четырёх unrelated corpus failures из-за `.DS_Store`; миграционный конфликт
с rollback 0044 устранён и его тест проходит. Эти посторонние файлы сохранены.
Общий suite не объявляется зелёным. Локальные логи находятся в `.runtime/fresh-*`.

## Выпуск

Рабочий сайт и его база не менялись. Для появления кнопки нужны backend,
migration 0109 и новый Staff bundle; backend/schema устанавливаются перед UI.
Rollback 0109 разрешён до первого использования. После появления slot-записей
его guard запрещает удаление отображаемых идентичностей и архива.

## Выпуск — 3 октября 2026

Выпущено на ВМШ/TLF в `26e2f7ee` вместе с migration 0109 после уже выпущенной 0108. Актуальная schema — 507 объектов; production миграция сохранила
все 157 прежних таблиц на каждом сервере. Полные tests, backups, services
и rollout records: [общий протокол](../release-20261003/README.md).
