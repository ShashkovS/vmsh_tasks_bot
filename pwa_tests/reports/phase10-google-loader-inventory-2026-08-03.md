# Phase 10: полный Google loader inventory

Дата проверки: 3 августа 2026 года.

## Объём

Инвентаризация
[`google-loader-inventory-and-cutover.md`](../../vmshpwa/docs/google-loader-inventory-and-cutover.md)
сверена с реальными
[`SpreadsheetLoader`](../../helpers/loader_from_google_spreadsheets.py),
[`FromGoogleSpreadsheet`](../../models/spreadsheets.py), Telegram startup и
ручными admin-командами. В ней отдельно описаны все шесть листов:

- `Задачи`;
- `Школьники`;
- `Учителя`;
- `Группы`;
- `_BotUIMsgs`;
- `_BotSettings`.

Для каждого зафиксированы позиционные колонки, normalisation/SQLite side
effects, существующая Staff/PWA замена, parity gap, текущая recovery-команда и
условие будущего cutover. Композиционная `/update_all` отмечена как
неатомарная и небезопасная после частичного cutover без отдельного guard.

## Автоматическое доказательство

[`test_google_loader_inventory.py`](../test_google_loader_inventory.py) извлекает
фактические worksheet names из loader и требует точного множества из шести
листов. Для каждого листа он проверяет наличие соответствующей `/update_*`
команды в inventory, а также зафиксированную неатомарность `/update_all` и общую
границу удаления credentials.

Результат focused запуска:

```text
2 passed
```

## Что этим не объявлено готовым

- Production task-settings cutover всё ещё ждёт полного реального недельного
  цикла и решения владельца с датой.
- Student/Teacher import, mapping legacy group fields, `_BotUIMsgs` и
  `_BotSettings` остаются отдельными незавершёнными доменами.
- Общие Google credentials не удаляются после одного task-settings cutover.
- Guard для `/update_all` должен быть реализован до первого частичного cutover;
  inventory не маскирует его отсутствие.
