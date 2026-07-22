# Roadmap отказа от Google

Google остаётся только в legacy Telegram startup/import paths. Ни один `pwa-*` профиль, новый unit test или E2E не читает service-account JSON и не вызывает Google API.

## Этапы

1. **Инвентаризация.** Зафиксировать таблицы, направления sync, ручные правки, schedule, авторов и recovery-процедуры каждого loader.
2. **Read model в Staff.** Показать текущие данные, provenance и divergence без изменения write path.
3. **Нативное редактирование.** Реализовать users/groups, lesson metadata, problem grid с TSV, publications и surveys поверх SQLite с validation/audit.
4. **Двойная проверка.** Для ограниченного периода сравнивать нативный результат с legacy import в dry-run, не делая Google обязательным runtime dependency.
5. **Переключение владельца.** Staff становится единственным write path конкретного домена; Google loader переводится в ручной read-only fallback.
6. **Удаление.** После подтверждённого сезона убрать loader, credentials и инструкции домена, сохранив экспорт в открытом формате.

Миграция выполняется по доменам, а не одним большим переключением. Telegram-бот при этом продолжает читать общие SQLite-модели и не обязан знать, был объект создан Staff UI или legacy import.

## Критерий отключения loader

Есть Staff UI для всех операций домена, роли/validation/audit, массовый импорт/экспорт, rollback, тесты на исторических fixtures, наблюдение полного недельного цикла и документированное восстановление. До этого Google-код не должен проникать в новые PWA imports.
