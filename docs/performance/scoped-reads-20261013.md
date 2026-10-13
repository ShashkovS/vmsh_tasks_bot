# Адресные обновления, отметки и статистика — 13 октября 2026

Владелец утвердил три отдельных коммита, общий release gate и один выпуск на
ВМШ/TLF. Исходная версия `aae27430`, [RAM-кеш уже выпущен](worker-read-cache-release.md).
Фото и длительность LLM исключены. Формулы, precedence, права, полнота таблиц
и offline/outbox сохраняются.

## 1. Realtime и RAM

Queries имеют ресурсные зависимости course/group/lesson/work; unlabelled query
не обновляется от произвольного события. Broad legacy tokens остаются доменными
fallback, scoped tokens имеют приоритет. Publication обновляет своё занятие и
его списки; banner только banners; результаты — owner work, Staff cells и course
statistics. Все подтверждённые aliases входят в область изменения.
Один QueryClient scheduler обслуживает invalidation/resync: concurrency 4,
dedupe и trailing refresh для событий во время чтения. Inactive queries только
stale. Authority и собственные mutations не задерживаются. Publication/banner
jitter 0–250 ms. Targeted cache invalidation не fence unrelated pending loads;
single-flight, bounded memory, reconnect/disconnected fallback сохраняются.

Компоненты: `helpers/pwa/read_cache.py`, `apps/pwa_api/read_cache.py`,
`apps/pwa_app.py`, `vmshpwa/packages/app-shell/src/realtime.tsx` и query clients.

## 2. Отметки

`db_methods/pwa/live_marking.py`: scoped effective results до aggregation по
разрешённым student IDs и logical task closure. Exact cell и board roster;
before/after остаются в writer transaction. Прямой student lookup. Visits
агрегируют active session mark history один раз. Миграция 0120 добавляет
`results(problem_id, student_id, id)` и partial mark-history context index;
данные не меняются. Written/manual/test, clear/undo, versions и delta сохраняются.

## 3. Статистика

Три Staff GET: bounded published course/group/lesson facts, participant-only
directory, linear indexed aggregation. Analytics worker, snapshot завершён до
pure computation. Scheduled calculations читают fresh DB, math неизменна.
Worker cache: TTL ≤60 s от начала snapshot, 128 entries / 64 MiB, single-flight,
copies, scope/filter keys, без requestId; authorization перед выдачей.
Событие сбрасывает свой course; reconnect очищает; TTL страхует legacy writes.
Invalidated in-flight statistics snapshot можно вернуть в пределах TTL, но не
сохранить. Fresh `refresh=1` на трёх GET для кнопки и manual recalculation.
Frontend staleTime 60000, focus только stale; automatic event refetch ≤1/s.
Новый polling отсутствует: 60 s ограничивает snapshot при следующем запросе.

Компоненты: `db_methods/pwa/{lesson_statistics,statistics_reports}.py`,
`models/pwa/{lesson_statistics,statistics_reports}.py`,
`apps/pwa_api/staff_statistics_routes.py` и statistics clients/pages.

## Приёмка и выпуск

Scope/no-refetch, concurrency/trailing, cache race/cancellation/limits/NATS,
SQL parity/aliases/undo/delta, migration up/down/up, три statistics responses,
permissions/TTL/cache hit/forced refresh. Real query performance guard и paired
old/new snapshot benchmark с plans, median/p95/read counts. Fixed-category cache
и computation metrics, без student/lesson IDs в labels.

`make pwa-check-release PWA_E2E_MODES="authentication content realtime live-marking statistics review submissions"`.
Перед единым release — copy migration rehearsal/backup restore checks; после —
services/NATS/HTTP/assets/journals, source/static rollback без data rollback.
Естественная нагрузка: HTTP p95/p99/counts и DB admission/queues; smoke не
доказательство ускорения вечернего окна. Квитанции сохраняются отдельно.

## Progress

- Направление 1 реализовано: scope routing, очередь 4/trailing, targeted pending
  fences и bounded metrics. Focused backend 94 PASS, realtime unit 25 PASS.
  Общий gate остаётся впереди; production пока на `aae27430`.
- Начато направление 2; статистика, final gate, rehearsal и выпуск pending.
