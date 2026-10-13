# Scoped read performance — 13 октября 2026

[Decision/implementation](../../../docs/performance/scoped-reads-20261013.md).
Владелец утвердил три коммита и один выпуск на оба production.

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
Выпуск начинается; production receipts будут добавлены после проверки.
`*-evening-before-metrics.json`: исходное окно 12.10 15:30–19:30 (+03).
