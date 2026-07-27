# Этап 11. Production hardening, deployment и параллельный запуск

## Результат

Student/Family/Staff разворачиваются на `vmsh.shashkovs.ru` под своими base paths рядом с работающим Telegram-ботом; желательный staging — `devvmsh.shashkovs.ru`. После acceptance возможности включаются сразу для всех трёх уровней, без продуктового rollout по отдельным группам.

Дизайн-контракт этапа: [all-audience failure/update states, production E2E/visual baselines и Storybook release stories](18-design-implementation-map.md#phase-11-design).

## Production topology

- Nginx routes `/student`, `/family`, `/staff`, matching API and WS paths.
- aiohttp/gunicorn: минимум два workers; shared SQLite/domain/storage, NATS fan-out.
- Каждый worker владеет соединениями/serialized executor согласно принятому DB concurrency ADR; общий module-level `sqlite3.Connection` не обслуживает конкурентные coroutine. `busy_timeout`, bounded retry и transaction wait попадают в metrics.
- Telegram webhook/polling adapter запускается отдельно от PWA app factory, но использует общую domain DB.
- Beget S3-compatible bucket через configured `s3_url`; bucket/access/secret приходят из production credential file. CORS только для необходимых public reads; browser writes only through aiohttp и не получает S3 credentials.
- Converter binaries (`pdflatex`, `pdf2svg`, `cwebp`, `magick` по умолчанию) разрешаются через `PATH` реального service profile либо explicit config override; интерактивный shell и hardcoded developer paths не считаются production configuration.
- Static assets content-hashed; HTML no-cache/revalidate; SW update strategy explicitly tested.
- CSP, HSTS, MIME sniffing protection, frame/permissions/referrer policies.

## Deployment

Адаптировать server webhook/script к pnpm monorepo:

- change detection учитывает `pnpm-lock.yaml`, workspace packages и каждое app;
- deterministic `pnpm install --frozen-lockfile` when manifests change;
- build all affected apps before switching served release;
- Python `uv sync --no-dev` only when lock/project changes;
- pre-deploy SQLite backup completes before migration/restart;
- migrations under explicit lock with version report;
- runtime `DB_CONNECTION.setup()`/эквивалент не вызывает yoyo apply: migration command завершён до старта workers, а schema mismatch делает health/startup красным;
- toolchain preflight запускается под тем же service user/environment, что workers, проверяет required capabilities/versions и делает readiness красным при missing/non-executable tool;
- storage preflight под тем же service profile проверяет полный production `s3_*` config и выполняет безопасный capability probe без печати credential values;
- health checks API + static manifest + WS handshake;
- atomic static release symlink/directory and previous-release rollback;
- post-deploy backup detached only after health success;
- Telegram notification reports redacted revision/status.

Нельзя использовать `git clean -f`/hard reset without protecting runtime/media/DB and untracked operational files; exact server layout must be documented.

## Observability and privacy

- Sentry frontend/backend releases share revision; environment and audience tags.
- Error sampling/redaction removes cookies, tokens, answers/photos/comments and push secrets.
- Structured logs: request ID, route template, status, latency, principal type/pseudonymous ID, DB busy/retry, WS count, outbox lag.
- Metrics/alerts: login failures, HTTP 5xx, SQLite busy, queue claim conflicts, media failures, delivery backlog, WS reconnect, SW release adoption.
- Audit covers writes from data model, not every read.

## Backup/restore and retention

- SQLite backup три раза в день и перед каждым deploy считается достаточным baseline; restore rehearsal использует согласованную копию трёх файлов SQLite/WAL/SHM в изолированном runtime.
- Полный отдельный backup S3 не требуется. Student images не versioned; teacher-authored отправленные artifacts защищаются application immutability или отдельной policy.
- Document what «manual bucket cleanup» may safely delete; preferably manifest-driven orphan report before any deletion.
- Retention remains indefinite only as explicitly accepted interim risk. До production acceptance назначаются owner и review date по `RETENTION-01`; до этой даты доступны growth/orphan reports, а удаление остаётся manual и manifest-driven.

## Rollout strategy

1. Полный rehearsal на staging/local production copy.
2. Внутренние admin/teacher accounts и test bot/channel.
3. Acceptance занятий 39–41 во всех трёх уровнях.
4. Одновременное включение Student/Family/Staff для всех уровней с Telegram fallback.
5. Google/external cutovers затем выполняются по одному процессу.

Технические kill switches остаются server-authoritative и не могут включать mock auth/MSW, но продуктовый выпуск не делится на отдельные group cohorts.

## Test/release gates

- Full Make quality gates + historical Telegram tests.
- Production-build E2E 3 browsers on seeded SQLite.
- Real staging/local Beget S3 smoke with test credentials and disposable prefix: put/get/head/delete, retry и cleanup; production key никогда не используется в test runtime.
- Real staging toolchain smoke: LaTeX/TikZ → PDF → SVG и HEIC/raster → WebP с redacted executable/version report, timeout и cleanup assertions.
- Two-worker/NATS/WS/SQLite load and failure tests выполняются против численного workload profile этапа 0: concurrency, submit/photo sizes, write latency, queue/outbox depth и допустимые busy/error thresholds. Неопределённый «load test прошёл» gate не принимается.
- Security review: auth, IDOR, CSRF/origin, CSP, upload, checker execution, public media URLs, push payload.
- Restore rehearsal with objective RPO/RTO.
- Полный physical-device smoke на доступных Android; iPhone — по возможности. Chromium/WebKit/Firefox E2E остаются обязательными.
- Rollback test from new frontend and migration-compatible backend to previous release.

## Критерии приёмки

- Production deploy/rollback не требует Telegram/Google credentials for PWA build.
- Telegram operation continues during PWA rollout and shared writes reconcile.
- Одновременные PWA/Telegram writers не смешивают транзакции, не блокируют event loop и при исчерпании bounded `SQLITE_BUSY` retry возвращают наблюдаемую повторяемую ошибку без half-write.
- Failed deployment leaves previous static/API release usable.
- Backup restored to isolated runtime passes integrity and selected end-to-end scenarios.
- Security headers/CSP do not break KaTeX, SVG, WebSocket, Sentry or PWA updates.
- Content/media workflows не принимают shell fragments в converter config и до пользовательского задания показывают operator-visible ошибку отсутствующей capability.
- S3 secrets отсутствуют в config `repr`, logs, Sentry, health, deploy report и browser contracts; partial/missing production tuple делает readiness красным до переключения revision.
- On-call owner can identify failed request/delivery without reading private content.
- Product owner explicitly accepts remaining legacy paths and retention risk; серьёзные alerts приходят в служебную Telegram-группу.

## Пруфы завершения этапа

- [ ] Release revision/config/migrations: `<sha/manifest/paths>`.
- [ ] Service-profile toolchain probe и converter versions/capabilities: `<redacted report/result>`.
- [ ] Redacted production S3 config/capability probe и test-bucket disposable-prefix smoke: `<reports/results>`.
- [ ] Deploy and atomic rollback rehearsal: `<runbook/result>`.
- [ ] SQLite backup/restore RPO/RTO evidence and S3 immutability/retrieval checks (no separate S3 backup in v1): `<path/result>`.
- [ ] Full tests, historical Telegram, 3-browser E2E, physical-device smoke: `<results>`.
- [ ] Two-worker/NATS/WS/load/failure report: `<path>`.
- [ ] Security review/headers/CSP/upload/checker/public-media findings: `<path/issues>`.
- [ ] Sentry/log/metrics redaction and alert screenshots: `<paths>`.
- [ ] All-groups launch/reconciliation/rollback report: `<path>`.
- [ ] Final docs/runbooks/data policy/known limitations: `<paths>`.
- [ ] Product and operational acceptance: `<names/date>`.

## Многокурсовый инкремент Phase 11

Production-size rehearsal создаёт курс «Математика 5–7», backfill-ит enrollments/access/course/group lessons и сравнивает legacy/new read models, statistics, Telegram paths и classroom inheritance. Cutover сохраняет legacy IDs и допускает rollback без физического разъединения submission history.

Дополнительный proof: migration parity/repeat/rollback report, synonym identity reconciliation, multi-course load/permission test, historical Telegram regression и явно подписанное решение о включении новых reads/writes.
