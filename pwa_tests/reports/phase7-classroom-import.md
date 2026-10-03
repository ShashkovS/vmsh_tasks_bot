# Phase 7C — одноразовый импорт аудиторий из Excel

Дата проверки: 2026-07-29.

## Проверяемый результат

Команда читает внешний Excel-кондуит с колонками `IDd`, `Уровень`,
`Аудитория`, не импортируя `_external_pipelines` в runtime. Preview работает на
read-only SQLite и показывает hash исходного файла, hash конкретного плана,
counts и блокирующие расхождения. Apply требует оба просмотренных hash и точное
повторное указание SQLite-файла.

Успешный apply выполняется одной транзакцией и создаёт:

- отсутствующие записи глобального каталога аудиторий;
- подтверждённую схему аудиторий выбранного очного события;
- подтверждённый план всех текущих очных школьников с `source=import`;
- одну компактную receipt-запись без исходных строк и имён.

Повтор того же apply возвращает сохранённый receipt. Другой импорт для уже
инициализированного события и apply с изменившимся source/preview hash
останавливаются до записи.

## Реализация

- migrations: `0060.pwa_classroom_import_receipts`;
- Excel parser: `helpers/pwa/classroom_import.py`;
- validation/application: `models/pwa/classroom_import.py`;
- короткие receipt/user reads and writes: `db_methods/pwa/classroom_imports.py`;
- CLI: `vmshpwa/scripts/classroom_import.py`;
- Make targets: `pwa-classroom-import-preview`, `pwa-classroom-import-apply`;
- executable proof: `pwa_tests/integration/test_phase7_classroom_import.py`.

## Проверки

- parser/header/NFKC+casefold, blocker report, transaction rollback, confirmed
  layout/plan, `source=import` и replay: **4 PASS**;
- все classroom domain/migration tests без HTTP: **23 PASS**;
- настоящий aiohttp classroom API: **4 PASS**;
- schema inventory generation/check: **PASS**, `369` product objects;
- полный frontend unit suite: **439 PASS**;
- полный Python PWA suite: **1324 PASS, 3 SKIP**; единственное предупреждение —
  существующая SymPy deprecation вне этого инкремента;
- ESLint/Stylelint, TypeScript typecheck и production builds всех трёх apps,
  включая оба `injectManifest` service workers: **PASS**. Сохранены прежние
  неблокирующие warnings о размере Student chunk и Workbox option deprecation.

## Не закрыто этим инкрементом

- Реальный рабочий кондуит отсутствует в репозитории. Книга
  `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`
  содержит метаданные задач и не используется как classroom source.
- Production-size anonymized rehearsal, owner-reviewed реальный dry-run и
  решение о cutover с legacy-печатью остаются отдельным Phase-7 gate.
- Этот инкремент не реализует Student/Family projection, явную рассылку
  аудиторий и устный контур.
