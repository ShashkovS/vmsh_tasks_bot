# Публикация и диагностика материалов — 4 октября 2026

## Повторная загрузка после обновления конвертера — follow-up

После первого выпуска владелец сообщил о конфликтах при загрузке условия и
подсказок (`837cdf13005b43d99d67062348ac4dbb`, `5de368c8d81841759dd91b6a5894f38f`).
SHA предоставленных CP1251 файлов совпадают с `gl-14` condition `cr-71`
(ready / compiler 8) и hint `cr-75` (invalid / compiler 8).
`resolve_source_and_append_revision` пытался перевести завершённую версию в
uploaded при смене compiler 8 → 9; immutable/status guards запрещают это.
Предыдущий тест покрывал только uploaded, поэтому пропустил оба случая.

Исправление сохраняет terminal snapshots, их diagnostics, derivatives и
публикации: [миграция 0113](../../migrations/0113.content_upload_compiler_generation.py)
меняет cache unique key на `(source_id, source_sha256, parser_version)`.
[Repository](../../db_methods/pwa/content.py) повторно использует только ту же
compiler generation; иначе добавляет новый номер в прежнюю source lineage.
Реальные HTTP upload → compile тесты покрывают опубликованное ready условие
и invalid подсказку, CP1251 и рисунок только в решении. Baseline и 0112 не меняются.
Миграция сохраняет все строки/зависимые DDL/FK-дефекты; rollback отказывает,
если уже существует несколько compiler generations одного source hash.
Проверки: Python 2832 / 7 SKIP, frontend 1028, Chromium content 2 и static
gates PASS. Storybook 355 PASS / один Large Classroom performance FAIL
(68 / 71.9 ms при лимите 50 ms); frontend не изменён, общий gate не объявляется
PASS. Серверные репетиции обеих БД сохранили все строки; rollback cd18511e
с 0113 проходит startup guard. Backend-only выпуск на обоих порталах разрешён
владельцем; материалы агент не загружает и не публикует в production.
[Доказательства, limitations и release script](../../pwa_tests/reports/content-upload-generation-20261004/README.md).

## Требования и причины

На `gl-13` публикация нового условия падает при замене предыдущего условия,
активированного расписанием: CHECK в baseline 0111 разрешает
`activated_from_schedule_id` только для состояния `published`. История должна
сохранять происхождение также после замены и скрытия. Исправление — отдельная
[миграция 0112](../../migrations/0112.scheduled_publication_lifecycle.py),
проверки — `pwa_tests/integration/test_content_repository.py`,
`test_publication_lifecycle_migration.py` (все строки, зависимые объекты и
аварийный rollback транзакции) и `test_runtime_schema.py`. Baseline 0111
остаётся неизменной.

При загрузке `usl-04-p-sol.tex` как подсказок парсер распознаёт
`rightpicture`/`includegraphics`, но требует рисунки из решения на строках
125 и 128. Выбор рисунков должен совпадать у inventory, compiler и renderer:
[selected_material_figures](../../helpers/pwa/content/figure_layout.py),
[compiler](../../helpers/pwa/content/compiler.py),
[API](../../apps/pwa_api/content_routes.py). Рисунки самого решения остаются
обязательными при загрузке решения; ошибки синтаксиса и безопасности не скрываются.

`material.parts_mismatch` сообщает номер задачи, раздел и оба списка пунктов.
Общий материал без пунктов остаётся допустимым. Старые сохранённые diagnostics
локализуются как раньше: `helpers/pwa/content/diagnostic_i18n.py`.

В [MaterialWorkflowCard](../apps/staff/src/content-page.tsx) ошибка дублируется
под подтверждением, с одним live announcement. Только `version_conflict`
обновляет данные; `content_conflict` сохраняет серверную причину и request ID.
Автоматического повторения публикации нет.

## Выполнение и выпуск

Код и регрессии готовы; i18n и артефакты схемы обновлены. Запускается единый
fast gate `content figure-layout`: реальный E2E сначала активирует условие
расписанием, затем заменяет его и выполняет откат. Storybook проверяет ошибку
под подтверждением, один live announcement и отсутствие ложного refetch.
После PASS владелец явно разрешил push, автодеплой ВМШ и ручной выпуск TLF
на `prep.leaders.tech`. Основная deployment-ветка репозитория — `vmshpwa`.
Учебные материалы публикует пользователь; текущая
версия 6 подсказок на `gl-14` и старая invalid `cr-75` автоматически не меняются.
Перед выпуском нужны backup, migration rehearsal, совместимый rollback source
с сохранённой 0112, штатный guarded deploy и read-only browser/HTTP smoke.

## Проверки перед выпуском

Fast gate `content figure-layout` завершён: 2823 Python PASS / 7 SKIP,
1028 frontend, 356 Storybook, 6 Chromium E2E. После ограничения sandbox
на локальные сокеты прогон продолжен с разрешением для изолированной среды;
прошедшие неизменённые frontend static gates не повторялись. Firefox/WebKit
в этом ограниченном выпуске не запускались.
[Receipt и доказательства](../../pwa_tests/reports/content-recovery-20261004/README.md).

Репетиция на согласованной серверной копии: 158 таблиц / 606 819 строк
сохранены, изменён только DDL `lesson_publications`; существующие 627 legacy
FK-дефектов совпали, новых нет. Зависимые триггеры и индексы сохранены.
Совместимый rollback `43b7d2f` сохраняет 0112: прежний backend проходит
startup guard и заменяет активированную расписанием публикацию.

## Production

`9a14443f` отправлен в `origin/vmshpwa` и выпущен на ВМШ штатным webhook,
на TLF — [ручным script](../../pwa_tests/reports/content-recovery-20261004/deploy-tlf.sh).
Migration 0112 current, integrity `ok`, все учебные материалы сохранены.
TLF: 158 таблиц / 18 786 строк идентичны, включая 1421 Zoom receipt;
ВМШ: 155 таблиц идентичны, в auth tables подтверждён ровно один обычный
refresh после открытия writers. По 25 public HTTP checks и authenticated
Staff browser smoke PASS, production bundles и старые assets проверены.
[Backups, rollback и безопасные доказательства](../../pwa_tests/reports/content-recovery-20261004/README.md#production--4-октября-2026).
