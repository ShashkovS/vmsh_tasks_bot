# Phase 2 — production-build E2E публикации контента

Дата: 28 июля 2026 года. Revision: `3b5a4e8`.

## Результат

Отдельный lock-aware target `make pwa-e2e-content` связывает production Vite
bundles, настоящий aiohttp backend, one-origin gateway и чистую
`db/vmshpwa_e2e.sqlite3`. MSW, Telegram, Google и внешняя сеть в сценарии не
используются.

Один и тот же продуктовый путь независимо прошёл в Chromium, WebKit и Firefox:

1. admin входит через настоящий Staff login;
2. загружает synthetic LaTeX условия;
3. сервер компилирует revision;
4. admin явно создаёт новую задачу, правит metadata и подтверждает publication;
5. Student входит через настоящий Student login и читает опубликованное условие;
6. Staff загружает вторую revision и сопоставляет её существующей задаче;
7. Student видит вторую и больше не видит первую revision;
8. admin явно откатывает publication;
9. Student снова видит первую и больше не видит вторую revision.

Для upload, metadata, publication и rollback дополнительно проверены реальные
HTTP status и identity revision/group lesson, а не только текст на экране.

## Изоляция и fixture

- [`e2e-content-v1.json`](../fixtures/content/e2e-content-v1.json) задаёт по
  одной независимой mutable `group_lesson` для каждого browser project;
- [`seed_e2e_content.py`](../../vmshpwa/scripts/seed_e2e_content.py) работает
  только при `VMSH_RUNTIME_PROFILE=pwa-e2e`, `VMSH_INSTANCE=e2e`, `PROD=false`
  и точном пути E2E SQLite;
- seed атомарен, идемпотентен при полном повторе и падает на частично
  присутствующем fixture;
- baseline-v1 не расширен mutable content-состоянием;
- runner по-прежнему владеет production build, lifecycle lock, SQLite и
  локальными портами целиком.

## Реализующие файлы

- [`content-publication.spec.ts`](../../vmshpwa/e2e/content-publication.spec.ts);
- [`playwright.config.ts`](../../vmshpwa/playwright.config.ts);
- [`e2e_runner.py`](../../vmshpwa/scripts/e2e_runner.py);
- [`test_e2e_content_seed.py`](../test_e2e_content_seed.py);
- [`test_e2e_runner.py`](../test_e2e_runner.py).

## Проверки

```text
strict TypeScript: root + Staff
PASS

ESLint affected frontend/E2E files
PASS

Ruff affected Python files
PASS

pytest: E2E fixture seed + runner modes
12 passed

production build: Student + Family + Staff
PASS

Student/Family injectManifest service workers
PASS; 92/91 precache entries

make pwa-e2e-content
3 passed (23.0s)
Chromium 10.3s; WebKit 14.6s; Firefox 17.7s
```

После завершения runner не оставил listeners на `8380`/`8390`. Generated
SQLite/runtime/media не попали в Git.

## Граница доказательства

Этот checkpoint закрывает production-build browser path для обычного LaTeX
условия, matching, metadata, двух публикаций и rollback. Missing-asset recovery,
TikZ/SVG/WebP и durable S3 уже имеют отдельные hermetic/live/API/Storybook
proof, но пока не объединены с этим Playwright-сценарием. Также остаются
production owner-reviewed parity/backfill и owner visual approval. Snapshots не
обновлялись.
