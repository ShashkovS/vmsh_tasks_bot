# Phase 8E: Web Push delivery proof

Дата: 2026-07-29.

## Граница среза

- `notification_deliveries` — единственная конкретная outbox-таблица. Второго буфера или общего delivery framework нет.
- `db_methods/pwa/notification_deliveries.py` содержит только прямые SQLite-операции: найти, создать, захватить и завершить попытку.
- Выбор текста, quiet hours, retry и реакция на ответ push-provider находятся в `helpers/pwa/push_delivery.py`.
- `helpers/pwa/web_push.py` только вызывает `pywebpush` в thread и преобразует transport status. Тело ответа provider не логируется.
- PWA startup запускает один простой цикл доставки с интервалом 5 секунд. Без полного набора VAPID-настроек Web Push не запускается.

## Проверяемое поведение

- migration проходит up/down/up и `PRAGMA integrity_check`;
- одно событие для одной browser subscription создаёт одну строку доставки;
- ночное событие доставляется без звука, а не задерживается;
- HTTP 503 переводит ту же строку в retry без дубля;
- HTTP 410 завершает попытку и удаляет недействительную browser subscription;
- выключенная категория сохраняет аудируемое состояние `suppressed`, не вызывая transport;
- classroom push не теряет курс, группу и аудиторию;
- scheduler стартует и завершается в ограниченное время;
- production-конфигурация с неполным VAPID или недопустимым subject отклоняется при startup.

## Результаты

- Focused Web Push, notification, PWA transport and app-factory regression set: 59 passed.
- Schema inventory check: 381 objects, SHA-256 `969cdc995ee2aef95de009aabf923932e1ce838328984047949ac72017236455`.
- Чистый Python-прогон внутри sandbox: 30 passed; 29 socket-based checks не запустились из-за запрета bind. Тот же набор с разрешённым loopback bind: 59 passed.
- Единственное warning — существующее `SymPyDeprecationWarning` в зависимости `mathsolvers`.
- Visual snapshots: не применимы.

## Оставшаяся граница

Живой provider smoke возможен только после регистрации реальной browser subscription. Он войдёт в device/Playwright smoke, а не в unit-тесты. Family UI, course-specific overrides и news ingest остаются отдельными срезами Phase 8.
