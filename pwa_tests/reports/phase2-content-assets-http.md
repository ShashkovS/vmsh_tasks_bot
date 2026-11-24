# Phase 2D: разрешение ресурсов и сохранение производных

Дата проверки: 28 июля 2026 года.

## Граница инкремента

Этот proof закрывает HTTP/UI-путь недостающих ресурсов конкретной LaTeX
revision и нижнюю границу хранения PDF. Он не закрывает problem matching,
metadata grid, bulk upload, открытие PDF через Staff API, production-build
content E2E или ручное визуальное принятие.

Реализация зафиксирована тремя отдельными revisions:

- `43b0323` — versioned Staff asset API, content-addressed storage,
  raster→WebP, SVG sanitizer, server-side TikZ→SVG, immutable local media route,
  app-factory, nginx и production-like E2E gateway;
- `08a8d0b` — строгие Zod/client contracts, missing-assets recovery в Staff,
  Storybook interaction states, Student/Family Workbox policy и Vite proxy;
- `d39141d` — provider-first сохранение воспроизводимой PDF-производной и
  idempotent/concurrent retry boundary. HTTP preview/download для неё остаётся
  следующим инкрементом.

## Доказанные инварианты

- GET/POST работают только с точной revision; mutation требует сильный
  `If-Match`, stale version возвращает `409`, повтор того же attachment
  идемпотентен.
- Компиляция с отсутствующими ресурсами возвращает
  `content_assets_missing`/`422`, не захватывает compile lease и оставляет
  revision в `uploaded`.
- Figure принимает raster или SVG; TikZ строится сервером из сохранённого
  LaTeX и не принимает browser-файл.
- Raster сохраняется только как WebP до 1920 px, SVG проходит allowlist
  sanitizer, а object key и SQLite metadata связаны с SHA-256.
- Локальный adapter отдаёт immutable bytes через
  `/pwa-content-assets/{assetId}` с integrity check; production S3 descriptor
  остаётся прямым credential-free HTTPS URL.
- Staff сохраняет выбранный файл после transient failure, обновляет список при
  `409` и повторно компилирует только после разрешения всех ссылок.
- Student/Family не принимают asset URL за navigation fallback и кешируют
  same-origin content images в общем recent-media cache максимум на две недели.
- PDF provider write предшествует DB metadata; exact retry и конкурентный
  identical insert сходятся, противоречивая derivative завершается fail-closed.

## Автоматические проверки

- Python backend/repository/converter/app-factory/gateway/nginx regression:
  **302 passed**; Ruff и `git diff --check` — PASS.
- Отдельный focused suite PDF persistence: **10 passed**.
- Frontend contracts/client/offline/proxy: **21 passed**.
- Storybook browser mode для Staff content и product asset states:
  **17 passed**, addon-a11y остаётся error gate.
- ESLint затронутых файлов и strict TypeScript для Student, Family, Staff,
  contracts, content, offline, product и test-utils — PASS.
- Production Vite build всех трёх приложений — PASS; Student и Family собрали
  `injectManifest` service workers. Остаётся известное upstream-предупреждение
  vite-plugin-pwa об устаревшем `inlineDynamicImports`.
- Visual snapshots не обновлялись.

## Незакрытые доказательства

- Настоящий production-build browser flow: upload → missing asset → recover →
  preview → publish → Student/Family read → rollback.
- Staff API/UI для открытия уже сохранённой PDF-производной.
- Owner visual approval новых Staff states.
