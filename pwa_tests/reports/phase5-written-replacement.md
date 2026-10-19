# Phase 5 — атомарная замена письменной сдачи до проверки

Дата проверки: 2026-07-28. Revisions: `1fa320b`, `6b30141`, `9d3b821`,
`34d371d`.

## Проверяемый результат

- Миграция
  [`0050.pwa_submission_entry_replacements.sql`](../../migrations/0050.pwa_submission_entry_replacements.sql)
  добавляет append-only связь прежней и новой entry. Исходные сообщения,
  фотографии и object keys не перепривязываются и не удаляются: прежняя entry
  становится `deleted`, подготовленная entry — `submitted`, а событие замены и
  обе версии сохраняются в одной SQLite-транзакции.
- Repository
  [`replace_entry`](../../db_methods/pwa/written_submissions.py) проверяет
  владельца, обе optimistic versions, текущую revision, дедлайн, полный набор
  готовых вложений и отсутствие review lock. Повтор того же idempotency key
  возвращает прежний receipt; другой payload отклоняется.
- Student API:
  `POST /student/api/v1/thread-entries/{newEntryId}/replace`. Wire-контракт и
  runtime validation находятся в
  [`written-submissions.ts`](../../vmshpwa/packages/contracts/src/written-submissions.ts),
  same-origin transport — в
  [`written-submission-client.ts`](../../vmshpwa/packages/app-shell/src/written-submission-client.ts).
- Student PWA предлагает замену только для последней собственной `submitted`
  entry. После подтверждения текст и все доступные WebP копируются через
  authenticated media endpoint в новый локальный draft. Старое решение остаётся
  действующим, пока новая версия не будет полностью загружена и атомарно
  подтверждена сервером.
- Replacement target, текст, порядок и binary pages переживают reload:
  serializable intent хранится в account/problem/revision-scoped localStorage,
  страницы — в owner-scoped Dexie. Outbox снимает immutable snapshot intent и
  выбирает `replace`, а не `submit`, только на финальном шаге resumable цепочки.
- Reconnect delivery освобождает single-flight guard до публикации состояния
  `retrying`; иначе немедленный React effect мог потерять единственную повторную
  попытку. Автоповторы используют возрастающую паузу до 30 секунд.

## Автоматические доказательства

- Contracts/draft/outbox/client focused Vitest: **4 файла / 32 PASS**.
- Полный frontend unit checkpoint после изменения: **47 файлов / 362 PASS**.
- Полный Python PWA checkpoint: **1223 PASS / 3 intentional skips / 1
  existing SymPy warning**.
- `make pwa-lint`, `make pwa-typecheck` и production build трёх приложений —
  **PASS**; Storybook browser mode — **38 файлов / 188 PASS**.
- Schema inventory после migration `0050`: **269 product objects**; focused
  inventory suite: **21 PASS**.
- Repository, migration и Student HTTP tests проверяют success/replay,
  immutable replacement event, stale versions, другой owner, locked/closed
  thread и неизменность исходных attachment rows.
- Production-build Playwright
  [`Phase 5: a written draft with a photo survives reload and resumes exactly once`](../../vmshpwa/e2e/test-submission.spec.ts)
  — **3/3 PASS** в Chromium, WebKit и Firefox; весь submissions checkpoint —
  **9/9 PASS**. Использованы real aiohttp, seeded isolated SQLite, filesystem
  object storage и фактический image converter, без MSW/Telegram/Google.
- Сценарий доказывает initial offline queue → reconnect → submit, затем
  authenticated download прежнего WebP → reload восстановленного replacement
  draft → atomic replace. Authoritative thread содержит исходную `deleted` и
  новую `submitted` entry с разными IDs и собственными фото.
- E2E service profile получил уже согласованный absolute
  `VMSH_PDFLATEX_PATH`; machine-specific путь не записан в config или bundle.
  Без override процесс корректно fail-closed показал
  `asset.tool_unavailable`, потому что его service `PATH` не содержит
  пользовательский `~/bin`.
- Guarded S3 lifecycle для настоящего `WrittenAttachmentService` отдельно
  подтверждён в
  [`phase5-written-storage-live.md`](phase5-written-storage-live.md).
- `git diff --check` и структурные проверки Markdown-ссылок — **PASS**.

## Открытые границы Phase 5

- После review lock исходное evidence не заменяется; новые сообщения и review
  UI реализуются в Phase 6.
- Legacy discussion backfill и Staff material reassignment остаются отдельными
  инкрементами: эта операция не подменяет их и ничего физически не «склеивает».
- Owner visual gate focused composer/replacement state ещё не принят; snapshots
  не обновлялись.
- Автоматические unit/E2E не обращались к S3, Telegram, Google или `db/vmsh.db`.
