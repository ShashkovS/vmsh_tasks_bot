# Phase 8D: browser Web Push proof

Дата: 2026-07-29.

## Граница среза

- Shared contracts описывают VAPID config, browser subscription, delete receipt и native push payload.
- Существующий notification client вызывает config/register/delete endpoints напрямую.
- Student notification settings контекстно спрашивает browser permission, синхронизирует существующую subscription и позволяет отключить текущее устройство.
- Student и Family service workers проверяют audience route, подавляют native popup при открытом кабинете и открывают owner-scoped URL по нажатию.
- Некорректный JSON, payload другой аудитории и внешний click URL игнорируются.
- Server encryption/delivery и реальный browser-provider smoke не входят в этот срез.

## Проверяемое поведение

- URL-safe application server key декодируется в browser `BufferSource`;
- `PushSubscription.toJSON()` превращается только в версионированный API request;
- client использует GET/POST/DELETE своего audience base;
- service-worker parser принимает Student payload только в Student worker и Family payload только в Family worker;
- permission prompt вызывается только после нажатия пользователя;
- существующая subscription повторно синхронизируется с текущим account;
- foreground окно сохраняет in-app событие, но не получает дублирующий native popup.

## Результаты

- ESLint for affected files: passed.
- TypeScript for contracts, app-shell, offline, Student and Family: passed.
- Targeted unit tests: 5 files, 14 passed.
- Full unit tests: 67 files, 463 passed.
- Student production Vite build: passed; `injectManifest` generated 106 precache entries.
- Family production Vite build: passed; `injectManifest` generated 91 precache entries.
- Generated Student/Family `sw.js` contains audience-specific push display and click handlers.
- Visual snapshots: not updated.
- `git diff --check`: passed before staging.

## Следующий срез

Server Web Push encryption, quiet-hours sound flag, durable delivery attempts and provider failure cleanup. Family notification page remains a separate product slice.
