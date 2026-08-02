# Roadmap отказа от Google

Google остаётся только в legacy Telegram startup/import paths. Ни один `pwa-*` профиль, новый unit test или E2E не читает service-account JSON и не вызывает Google API.

Основной legacy-источник еженедельной конфигурации — файл `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`. Software replacement листов «Задачи» и «Старые» уже реализован: Staff умеет course-scoped preview, apply, receipt и rollback, а затем даёт нативный metadata grid. Реальный файл на 1813 строк дал нулевой diff против изолированной копии SQLite. Доказательства собраны в [`phase10-problem-workbook-replacement.md`](../../pwa_tests/reports/phase10-problem-workbook-replacement.md).

Операционный cutover этих листов ещё не объявлен: владелец должен провести через Staff один реальный недельный цикл, назвать дату переключения и сохранить legacy loader как ручной read-only fallback на период наблюдения. Surveys в первую версию не входят. Email workflows переносятся не раньше второй–третьей фазы.

## Этапы

1. **Инвентаризация.** Зафиксировать таблицы, направления sync, ручные правки, schedule, авторов и recovery-процедуры каждого loader.
2. **Read model в Staff.** Показать текущие данные, provenance и divergence без изменения write path.
3. **Нативное редактирование — software gate пройден для задач.** Lesson metadata, problem grid и XLSX import покрывают поля листов «Задачи»/«Старые». Users и остальные процессы переносятся независимо. Surveys остаются вне первой версии.
4. **Двойная проверка — characterization gate пройден для задач.** Зафиксирован нулевой diff на защищённой production-size копии; real-week observation остаётся операционным gate.
5. **Переключение владельца — ожидает owner acceptance.** После одной реальной недели Staff становится единственным write path task settings, а Google loader переводится в ручной read-only fallback.
6. **Удаление.** После подтверждённого сезона убрать loader, credentials и инструкции домена, сохранив экспорт в открытом формате.

Миграция выполняется по доменам, а не одним большим переключением. Все еженедельно используемые скрипты `_external_pipelines` продолжают работать до полного переноса соответствующего workflow. Telegram-бот при этом продолжает читать общие SQLite-модели и не обязан знать, был объект создан Staff UI или legacy import.

## Критерий отключения loader

Есть Staff UI для всех операций домена, роли/validation/audit, массовый импорт, rollback, тесты на исторических fixtures, наблюдение полного недельного цикла и документированное восстановление. Экспорт не является обязательным для первой версии. До этого Google-код не должен проникать в новые PWA imports.
