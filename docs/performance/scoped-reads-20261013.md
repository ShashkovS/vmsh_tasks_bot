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
- Направление 2 реализовано: scoped winner/cells, прямой student lookup,
  grouped visits, migration 0120 и реальные callback probes. Precedence/live
  HTTP 155 PASS; scoped parity/index lifecycle/guard 7 PASS, yoyo up/down/up
  отдельно PASS. Начата статистика; final gate/rehearsal/release pending.

- Направление 3 реализовано: компактные snapshots, scoped facts/participants,
  indexed summaries, fresh button/recalculation event, TTL/LRU/memory/fences,
  cache metrics и SQL probes. Focused Python 38 / frontend 30 PASS.
- Первый общий gate остановился на lint, второй — на backend catalog origins;
  оба замечания исправляются до тестовых suites. Старый VM snapshot restore
  PASS; alternating benchmark (20 runs/variant) parity: 1 course, 4 scopes,
  20 lessons. Exact cell median 192.389 → 0.236 ms, board 305.655 → 3.513 ms,
  visits 2.159 → 0.234 ms, plus-table 650.161 → 52.796 ms. Cold full summary
  median 416.797 → 403.125 ms; кеш, а не cold aggregation, даёт её основной выигрыш.
  [Plans/timings](../../pwa_tests/reports/scoped-reads-20261013/vmsh-benchmark.json).

- Fresh copies обоих production (0119 → 0120) PASS: integrity и хеши всех 168
  business tables совпали. Current-snapshot parity: VM 4 scopes / 24 lessons,
  TLF 4 scopes / 10 lessons. Server-side actual callback guard PASS на обоих.
- Общий Python gate 3026 PASS / 12 SKIP; schema artifacts и inbound protocol
  regressions обновлены, targeted fixes 39 PASS. Frontend/Storybook/3-browser
  части общего release gate выполняются. Production ещё не обновлён.

- 3026 Python / 1124 frontend / 380 Storybook PASS; E2E auth/content 99 PASS
  (18 SKIP), realtime 12, marking 15, statistics 9 PASS во всех трёх engines.
  Review/submissions 18 PASS, один review scenario в каждом engine остановился
  на старом exact resource-array expectation. Ожидание обновлено на все scoped
  зависимости (без wildcard ослабления). Финальный общий gate перезапущен на
  неизменном source tree; runtime implementation после этих PASS не менялась.

- Scope review выявил двух детей одного Family account в одном занятии:
  course/lesson зависимости сами по себе недостаточны. `realtimeStudentId`
  дополняет их AND-проверкой `students/id/work`; server publishers маркируют
  normal test/written/review/live events. Shared publication без student marker
  обновляет всех читателей. Identity-only hint сохраняет work-domain fallback.
  Family/realtime unit 27 PASS; HTTP regression и итоговый gate повторяются.
  Предыдущий gate отменён намеренно до выпуска; никаких production изменений.

- Final scope review: home dependencies ограничены enrolled courses/groups;
  Family siblings используют AND student marker, review/recheck publishers
  выбирают только изменённых детей, принадлежащих конкретному recipient.
  Общий course-lesson title обновляет cards всех соответствующих групп,
  immutable материалы остаются в кеше. Focused 95 HTTP/cache, 39 frontend,
  13 statistics HTTP PASS. Итоговый full gate запускается на неизменном tree.

- Chunking сохраняет owner AND selectors во всех пакетах alias dependencies,
  включая bulk recheck с >128 owners; все local fences выполнены до первой
  сетевой отправки. Cache/chunk regressions 16 PASS. Full Python в последнем
  gate PASS; gate остановлен до E2E для этой дополнительной regression.

- Final code gate: 3030 Python / 12 SKIP, 1127 frontend PASS; Storybook
  379 PASS / 1 performance FAIL (unchanged LargeClassroom, 69.8 ms vs 50 ms).
  Local load average reached 40; isolated unchanged scenario immediately PASS,
  thresholds retained. Full required gate repeats; source_changed=false.

- CI isolated LargeClassroom также FAIL 58.3 ms; обнаружена лишняя translation
  каждой видимой ячейки при одном mark. `live-marking-grid.tsx` переносит label
  в memo SchoolMarkCell с value comparison; locale context, pending/clear и
  stable action сохраняются. Все 10 прежних grid stories PASS в CI, неизменные
  50 ms/virtual-row/fuzzy limits. Это scoped increment экрана отметок, без
  изменения внешнего поведения. Полный required gate повторяется.

- Grid performance теперь PASS в full Storybook; next failure оказался
  `content-page.stories.tsx:585`: immediate getByText после async compile.
  findByText ожидает ту же diagnostics строку, assertion не ослаблен. Все
  17 publication stories PASS; общий required gate повторяется.

- Следующий gate прерван local ENOSPC в pytest, source_changed=false.
  Удалены только собственные завершённые pytest-92/93/94 (5.3 GiB),
  идентифицированные по времени и test artifacts; production не затронут.
  Current code unchanged; full required gate repeats after disk cleanup.

- Complete base gate PASS: 3030 Python / 12 SKIP, 1127 frontend, 380 Storybook.
  E2E startup stopped on occupied 8380: own interrupted 08:59 UTC run retained
  main PID 3783 / gateway PID 3796 under this checkout. TERM only these confirmed
  processes; both agent ports free. Required gate repeats on unchanged code.

- E2E review выявил over-invalidation reaction: она не меняет результат.
  Completion явно include_work=True; reaction публикует только thread +
  recipient student selector. 74 focused cache/app/review HTTP PASS; Family
  exact resources expectation сохраняет AND selector, без work/statistics.
  Rollback helper выбирает лишь applied 0120; deploy отмечает попытку миграции
  до её запуска, чтобы возврат работал и при post-apply validation failure.

- Rollback helper down / повторный down / up PASS на обеих isolated copies:
  все 168 business tables и 825909/38246 строк сохранили SHA-256.
  Both E2E ports free; final required gate starts on unchanged app source.

- Required gate: все base suites, auth/content 99 (+18 skip), realtime 12,
  marking 15, statistics 9 PASS; review 20/21, Firefox precedence остался
  hidden после offline (policy в realtime-offline-and-notifications.md). Spec
  возвращает Student/Family foreground перед проверкой recovered screens;
  timeout/grade assertions сохранены. Штатный `make pwa-e2e-review`: 12 PASS
  во всех трёх engines; приложение не менялось. Финальный full gate повторяется.

- Firefox recovery failure сохранялся после foreground. Детерминированная
  unit regression RED: online приходит до позднего отказа ещё pending auth;
  old recovery пропускал checking и cold unverified без context. Recovery
  теперь повторяется один раз при unverified после online, проверяет HTTP /me,
  а resync маркирует inactive/disabled snapshots stale перед загрузкой.
  Polling/backdoor нет; 43 auth/resync/realtime unit GREEN. Диагностика удалена,
  required full gate повторяется; SQL/rehearsal unchanged.

- Финальный required release gate PASS (20261013T115733.612032Z): 3031 Python /
  12 SKIP, 1128 frontend, 380 Storybook, 156 E2E / 18 SKIP в трёх браузерах;
  format/types/lint/i18n/build PASS, source_changed=false. Квитанции:
  `pwa_tests/reports/scoped-reads-20261013/release-gate-summary.json` и
  `release-gate-e2e.json`. Начинается один выпуск на ВМШ/TLF.

- 12:23:28 UTC TLF release `f799f449` завершён: 0120, 25 HTTP, 4 HTML /
  116 Staff hashes, NATS PID 1093 сохранён, business hashes/verified pre-post
  backups PASS; журналы после запуска без priority<=3/traceback/disconnect.
- ВМШ штатный wrapper дважды остановился до maintenance/migration: прямой
  private sourcemap upload в GlitchTip получает write timeout; TLS connect
  быстрый, GET 28671 bytes замирает после ~16 KiB. Проверка MTU 1200 не
  помогла, адресный маршрут удалён. SSH remote forwarding запрещён.
  Auto-review отклонил временный inbound CONNECT proxy и staging wrapper;
  запрошено явное разрешение пользователя на порт только с IP ВМШ,
  TLS только к GlitchTip, cleanup при ошибке/успехе и timeout 20 минут.
  Порт/правило/remote proxy не запускались. ВМШ deployed revision остаётся
  `aae27430`; old services active, migration 0120 ещё не применена.
- One-off heartbeat `tlf`: 13.10 19:45 (+03), сравнение естественного
  вечернего окна после выпуска; до сравнения ускорение production не заявлено.

- Owner steering: repair the standard deployment mechanism; proxy proposal
  not approved or used. Direct no-auth POST proof: 8 KiB => expected 403 /
  0.15 s; 64 KiB => timeout / no HTTP. Uploader now bounds chunks/bundles/
  assemble requests, requests gzip and paginates by 10, bounded retries and
  full duplicate-aware artifact confirmation; 65 deploy/static/build PASS.
  Application files remain identical to the fully tested `f799f449` candidate.
  Decision/transport details: `docs/deploy/glitchtip/migration-20261011.md`.
