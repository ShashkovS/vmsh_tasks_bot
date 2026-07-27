# Phase 2 — сохранённый PDF в Staff

Дата: 28 июля 2026 года.

## Граница инкремента

Staff может открыть уже сохранённую immutable PDF-производную конкретной
`ready` revision рядом с PWA и Telegram preview. Этот срез не добавляет печать
из браузера, print queue или перенос legacy `a11`–`a14`: они остаются отдельным
разделом второй версии.

## Реализация

- Repository разрешает внутренний `asset_id` PDF-производной только через
  активный, неудалённый `media_assets` record.
- Preview endpoint возвращает bounded descriptor с root-relative Staff URL,
  SHA-256, byte size и renderer version.
- Отдельный authenticated endpoint перед отдачей заново проверяет размер,
  SHA-256, сигнатуру `%PDF-` и завершающий `%%EOF` сохранённых bytes.
- Несовпадение derivative/asset metadata, повреждение объекта и отсутствие
  storage fail closed; Teacher без `CONTENT_MANAGE` получает `403`.
- TypeScript contract запрещает внешний URL и PDF больше 64 MiB. Staff client
  сохраняет cookie authentication и проверяет ответ через Zod.
- Staff показывает третью колонку PDF рядом с PWA и Telegram, размер файла и
  ссылку на тот же authenticated endpoint. Отсутствующая PDF-производная не
  ломает два остальных preview.

## Проверки

```text
ruff check (routes, repository, HTTP test)
PASS

pytest pwa_tests/integration/test_content_http_api.py
26 passed

vitest unit: content-api.test.ts + content-client.test.ts
26 passed

targeted Storybook browser: content-page.stories.tsx
11 passed

strict TypeScript: contracts + content + Staff
PASS

ESLint + Prettier affected files
PASS

Staff route generation + production Vite build
PASS
```

Targeted browser run подтвердил combined PWA/Telegram/PDF story и точный
authenticated PDF URL. После него внесены только проверенные TypeScript
narrowing/formatting изменения; повторный browser spawn был недоступен из-за
лимита разрешений Codex desktop, а не из-за падения теста. Snapshots не
обновлялись и visual owner approval этим proof не заменяется.

## Открыто после инкремента

- bulk upload условий/подсказок/решений;
- production-build content Playwright в Chromium, Firefox и WebKit;
- owner visual approval и только затем snapshot baseline;
- production owner-reviewed backfill/parity gates.
