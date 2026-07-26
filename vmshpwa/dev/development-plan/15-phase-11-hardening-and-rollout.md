# Этап 11. Production hardening, deployment и параллельный запуск

## Результат

Student/Family/Staff разворачиваются на `vmsh.shashkovs.ru` под своими base paths рядом с работающим Telegram-ботом; желательный staging — `devvmsh.shashkovs.ru`. После acceptance возможности включаются сразу для всех трёх уровней, без продуктового rollout по отдельным группам.

Дизайн-контракт этапа: [all-audience failure/update states, production E2E/visual baselines и Storybook release stories](18-design-implementation-map.md#phase-11-design).

## Production topology

- Nginx routes `/student`, `/family`, `/staff`, matching API and WS paths.
- aiohttp/gunicorn: минимум два workers; shared SQLite/domain/storage, NATS fan-out.
- Каждый worker владеет соединениями/serialized executor согласно принятому DB concurrency ADR; общий module-level `sqlite3.Connection` не обслуживает конкурентные coroutine. `busy_timeout`, bounded retry и transaction wait попадают в metrics.
- Telegram webhook/polling adapter запускается отдельно от PWA app factory, но использует общую domain DB.
- Hetzner S3-compatible bucket, CORS только для public reads if needed; browser writes only through aiohttp.
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
- Real staging Hetzner S3 smoke with disposable namespace.
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
- On-call owner can identify failed request/delivery without reading private content.
- Product owner explicitly accepts remaining legacy paths and retention risk; серьёзные alerts приходят в служебную Telegram-группу.

## Пруфы завершения этапа

- [ ] Release revision/config/migrations: `<sha/manifest/paths>`.
- [ ] Deploy and atomic rollback rehearsal: `<runbook/result>`.
- [ ] SQLite backup/restore RPO/RTO evidence and S3 immutability/retrieval checks (no separate S3 backup in v1): `<path/result>`.
- [ ] Full tests, historical Telegram, 3-browser E2E, physical-device smoke: `<results>`.
- [ ] Two-worker/NATS/WS/load/failure report: `<path>`.
- [ ] Security review/headers/CSP/upload/checker/public-media findings: `<path/issues>`.
- [ ] Sentry/log/metrics redaction and alert screenshots: `<paths>`.
- [ ] All-groups launch/reconciliation/rollback report: `<path>`.
- [ ] Final docs/runbooks/data policy/known limitations: `<paths>`.
- [ ] Product and operational acceptance: `<names/date>`.
