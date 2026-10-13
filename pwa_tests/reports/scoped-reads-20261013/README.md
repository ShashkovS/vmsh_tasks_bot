# Scoped read performance — 13 октября 2026

[Decision/implementation](../../../docs/performance/scoped-reads-20261013.md).
Владелец утвердил три коммита оптимизаций и выпуск на оба production.
Выпуск завершён: source `c8287b8f` на ВМШ/TLF, включая ремонт штатного uploader.
Полные квитанции и границы замера приведены ниже.

## Доказательства перед выпуском

- `vmsh-current-rehearsal.json` / `tlf-rehearsal.json`: свежие online copies
  со schema head 0119 → 0120, integrity ok, current schema. Исходная production
  открывалась read-only; restore/migration выполняются на isolated copies.
- `migration-data-parity.json`: SHA-256 каждой из 168 business tables совпадает
  до/после миграции: ВМШ 825909 строк, TLF 38246. Индексы не меняют данные.
- `vmsh-current-benchmark.json` / `tlf-benchmark.json`: alternating old/new
  callbacks на одной копии, 20 runs/variant; reference `aae27430`, plans,
  median/p95/read counts. Для всех scope/lesson вариантов responses совпали.
  ВМШ: 1 course / 4 scopes / 24 lessons; TLF: 2 / 4 / 10.
- `vmsh-server-sql-preflight.json` / `tlf-server-sql-preflight.json`: actual
  host Python/SQLite, migration + all real callback guards PASS на copies.
- Три warm statistics views дают 0 SQL в benchmark; HTTP regression отдельно
  проверяет requestId, refresh=1 и доступ перед cache hit. Main/summary cold
  latency почти не меняется: основная экономия — TTL/single-flight. Plus-table
  ограничена selected group/lesson. Local timings не равны HTTP production p95;
  соседний gate создавал переменную CPU-нагрузку во время local benchmark.
- `vmsh-benchmark.json` / `vmsh-rehearsal.json`: дополнительный старый Oct 11
  archive; extraction/restore проверены. Для текущего rollout использовать
  current copy, а не этот более старый snapshot.

## Выпуск

`deploy-tlf.sh`: frozen frontend/private sourcemaps, verified pre/post backups,
stop writers, 0120, all business-row hashes/config/NATS check, switch static,
runtime + public HTTP. Error path returns previous code/static; only 0120
indexes/bookkeeping can be rolled back, business data never restored.
ВМШ — штатный fixed-path signed webhook production branch. Его установленный
wrapper старше repository copy; SQL/rehearsal выполняются отдельно до push.
Никакие root-owned tools/units или credentials не обновляются этим выпуском.
Все server-side records находятся под `/web/vmsh_tasks_bot`.

Emergency VMSH return: deploy a new commit restoring pre-release application
files while retaining `migrations/0120.scoped_read_indexes.py` and current schema
artifacts; indexes remain compatible with old SQL. Rebuild prior frontend source
through the same production wrapper. This avoids restoring a SQLite backup or
removing user changes made after deployment. Static release also has the штатный
`static_release rollback` path for an administrative session.

`verify-deployment.py` проверяет HEAD, services, four production HTML/provenance,
Staff asset hashes, private sourcemaps, maintenance off и anonymous media 401.
`collect-metrics.py` читает localhost Prometheus с двумя параллельными queries,
сохраняет HTTP p95/p99/counts, DB admission/hold/queue, cache/projection metrics
без student/lesson labels. Deployment smoke доказывает работоспособность;
сопоставимые естественные нагрузки необходимы для вывода об ускорении.

Общий required gate PASS: 3031 Python / 12 SKIP, 1128 frontend, 380 Storybook,
156 E2E / 18 SKIP (три браузера), format/types/lint/i18n/build.
`release-gate-summary.json`: source_changed=false; `release-gate-e2e.json`.
Production receipts сохранены: ВМШ/TLF проверены после выпуска.
`*-evening-before-metrics.json`: исходное окно 12.10 15:30–19:30 (+03).

### История первых попыток rollout

TLF `f799f449` выпущен 12:23:28 UTC. `tlf-deployment-verification.json` и
`tlf-deployment-health.json`: verified backups, 25 HTTP, четыре HTML, 116
Staff hashes, все службы active / NRestarts=0, NATS PID сохранён, бизнес-данные
совпали, после запуска журналы без errors/traceback/disconnect.
ВМШ: две попытки штатного выпуска остановлены до maintenance/migration из-за
сетевого write timeout private sourcemap upload. Old deployed marker `aae27430`.
Временный MTU-маршрут не помог и удалён; proxy/firewall изменения отклонены
auto-review и ожидают явного разрешения. Никакие security boundaries не изменены.

### Первые 15 минут TLF

`*-immediate-*-metrics.json`: до выпуска 12:08:20–12:23:20 UTC и после
12:24–12:39. В Student tasks было около 3 GET до выпуска и 0 после; Staff
marking/statistics отсутствовали. Эти выборки не позволяют сравнивать p95/p99.
DB read/write queue max=0 в обоих окнах; read admission p95 ~0.95 ms.
HTTP auth/me около 3 и 5 запросов (включая anonymous checks), p95 ~4.75 ms;
по ним ускорение также не заявляется. Измерение вечернего окна запланировано.

### Repair of the standard upload path

Owner requested normal mechanism repair. Proxy/port changes are not approved
and remain inactive. Uploader repair uses standard authenticated HTTPS only:
8 KiB SHA-1 chunks, paired small ZIP bundles, assemble JSON <=12 KiB, gzip
responses, ten-file pages, server concurrency and three transient attempts.
65 production build/static/smoke tests PASS. Runtime application code remains
the full release-gate candidate. Live standard upload subsequently passed; see completed rollout below.

### Completed standard rollout

Both source trees are `c8287b8f9a1a02a87536109362e3eba4bf47f4a5`:
VMSH normal wrapper completed 13:08:55 UTC; TLF optimization release was
12:23:28 UTC, followed by tooling-only ff-sync, preserving runtime/static.
`vmsh-deployment-verification.json` / `tlf-current-verification.json`: on each
host 25 HTTP, four HTML and 116 Staff asset hashes PASS; no public maps,
maintenance off, services active. `vmsh-deployment-health.json`: 1145 direct
chunks, 406 artifacts verified, both indexes present, NATS PID 1409 preserved,
post-start journal errors/traceback/disconnect=0 and NRestarts=0. TLF NATS
PID 1093 preserved. `vmsh-backup-restore-verification.json`: both verified
backups restored separately, integrity OK, all 169 table counts match each
snapshot; temporary restores removed. Earlier failure records are history.

First five-minute VMSH observation (`vmsh-first-five-minutes-metrics.json`):
~199 tasks GET, p95 303 ms / p99 461 ms; ~86 auth GET, p95 8.25 ms / p99
29.5 ms; no 5xx, read/write queue max=0. Immediate before was 15 minutes,
~375 tasks, p95 244 ms / p99 467 ms, read queue max=8. After has ~40 tasks/min
vs ~25/min before and cold caches; these periods do not establish a speedup.
Staff sample absent. At 19:45 (+03) one-off heartbeat compares original evening
window and clean 13:15–16:30 UTC in both days, separately for both hosts.
