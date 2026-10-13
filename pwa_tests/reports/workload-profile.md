# Observed workload profile

Источники прочитаны без изменения; отчёт содержит только агрегаты. Raw events,
trace/flow IDs, user/chat/Telegram IDs и payload fragments не сохранялись.

- `logs/events.jsonl`: 189 lines, 0 exact duplicate lines, 189 events, 37 traces
- `logs/events.jsonl.2026-03-02`: 17699 lines, 0 exact duplicate lines, 17699 events, 3116 traces
- `logs/events.jsonl.2026-03-03`: 53088 lines, 0 exact duplicate lines, 53088 events, 11465 traces
- `logs/events.jsonl.2026-03-04`: 4915 lines, 0 exact duplicate lines, 4915 events, 1247 traces
- `logs/events.jsonl.2026-03-05`: 4409 lines, 0 exact duplicate lines, 4409 events, 908 traces
- `logs/events.jsonl.2026-03-06`: 4196 lines, 0 exact duplicate lines, 4196 events, 879 traces
- `logs/events.jsonl.2026-03-07`: 7187 lines, 0 exact duplicate lines, 7187 events, 1504 traces
- `logs/events.jsonl.2026-03-08`: 9256 lines, 0 exact duplicate lines, 9256 events, 1877 traces
- `logs/events.jsonl.2026-03-09`: 6076 lines, 0 exact duplicate lines, 6076 events, 1041 traces
- `logs/events.jsonl.2026-03-10`: 6342 lines, 0 exact duplicate lines, 6342 events, 1503 traces
- `logs/events.jsonl.2026-03-11`: 5190 lines, 0 exact duplicate lines, 5190 events, 1310 traces
- `logs/events.jsonl.2026-03-12`: 5440 lines, 0 exact duplicate lines, 5440 events, 1117 traces
- `logs/events.jsonl.2026-03-13`: 4151 lines, 0 exact duplicate lines, 4151 events, 870 traces
- `logs/events.jsonl.2026-03-14`: 6708 lines, 0 exact duplicate lines, 6708 events, 1441 traces
- `logs/events.jsonl.2026-03-15`: 10764 lines, 0 exact duplicate lines, 10764 events, 1892 traces
- `logs/events.jsonl.2026-03-16`: 22989 lines, 0 exact duplicate lines, 22989 events, 5236 traces
- `logs/events.jsonl.2026-03-17`: 3145 lines, 0 exact duplicate lines, 3145 events, 788 traces
- `logs/events.jsonl.2026-03-18`: 3083 lines, 0 exact duplicate lines, 3083 events, 788 traces
- `logs/events.jsonl.2026-03-19`: 1886 lines, 0 exact duplicate lines, 1886 events, 389 traces

Полнота выборки неизвестна: у файлов нет season-wide coverage metadata.

## Безопасность и полнота labels

- unreviewed event labels: 0
- unreviewed source labels: 0
- legacy numeric actor labels, mapped через явную таблицу: 150
- actor label отсутствует: 6676
- unreviewed actor labels: 0
- missing actor by safe source: `{"zoom.webhook": 6676}`

Event/source/actor values сериализуются только после explicit allowlist. Неизвестное
значение становится `other-*`, поэтому динамическая строка или идентификатор не
может попасть в отчёт. Отсутствующий actor не считается неизвестной ролью:
например, Zoom webhook не всегда несёт user context.

## Raw record, metrics event и trace — разные единицы

- Raw record: одна физическая JSONL-строка.
- Metrics event: один canonical distinct valid JSON object после удаления
  byte/whitespace-equivalent duplicates.
- Trace: один distinct `trace_id`, обычно один Telegram update или Zoom webhook.
- Наблюдалось metrics events: 176713; traces: 37408.
- Raw lines: 176713; exact duplicate lines:
  0.
- Canonically duplicate valid event records: 0.
- Все combined metrics ниже рассчитаны после canonical JSON-record deduplication;
  порядок ключей и пробелы сериализации на identity не влияют.

## Minute-level proxies

- peak events/min: 870
- peak trace starts/min: 38
- peak ingress updates/min: 38
- peak submission events/min: 13
- peak review completions/min: 11
- peak distinct flows/min: 12

Это не число одновременных сессий: session intervals и надёжные handler
start/finish timestamps отсутствуют. Observed trace span также не является
request/write latency. Write latency остаётся неизвестной.

## Outcomes

- `ok=true`: 176713
- `ok=false`: 0
- `ok` missing: 0
- `ok=true`, но есть partial-failure signal: 21

`emit_trace` по умолчанию выставляет `ok=true`; поэтому положительные
`bad_count`/`errors_count` считаются отдельно и не скрываются общей метрикой.

## Media

- `photo_count` — число Telegram `PhotoSize` variants, **не страниц**.
- photo-message proxy: 1647
- written photo-message proxy: 1510
- media groups: 37
- logical page count: **неизвестно**
- photo bytes: **неизвестно**
- document size observations: 0

Один photo message можно считать только proxy одного изображения; Telegram album
приходит несколькими messages с общим media-group ID.

## Queue/outbox

- queue snapshots: 1576
- max reported written queue: 226
- max reported SOS queue: 3
- max selected batch: 27
- PWA outbox depth: **неизвестно**

Для этапа 11 всё ещё нужны server-side latency/SQLITE_BUSY metrics, media byte
telemetry, session concurrency и явно маркированное полное окно наблюдения.
