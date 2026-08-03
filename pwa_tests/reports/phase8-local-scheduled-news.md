# Phase 8 proof: локальная публикация PWA по расписанию

Дата проверки: 3 августа 2026 года.

## Реализовано

- Global admin создаёт course- или group-scoped plain-text публикацию через
  `POST /staff/api/v1/news/local`; teacher получает `403`.
- Post, initial visibility, revision, Student/Family notification events и
  privacy-safe audit создаются в одной SQLite-транзакции.
- `publishedAt` нормализуется в UTC. Feed, detail и in-app event API используют
  серверное `now` и не отдают данные раньше срока.
- Notification payload содержит `courseId`, а `deliver_after` совпадает со
  временем публикации.
- Staff-черновик изолирован runtime/account key и переживает reload; очистка
  происходит только после server receipt.
- Staff moderation показывает будущую локальную запись как «По расписанию».

## Автоматические доказательства

- `pwa_tests/integration/test_phase8_news_moderation.py`: создание, `403`,
  неизвестный owner, invalid body, future feed/event gate, Student/Family group
  projection, audit без текста публикации.
- `pwa_tests/integration/test_phase8_notification_core.py`: event недоступен до
  `deliver_after` и появляется ровно после него.
- `vmshpwa/packages/contracts/src/news.test.ts`: строгий runtime-контракт.
- `vmshpwa/packages/app-shell/src/news-moderation-client.test.ts`: реальный URL и
  POST method клиента.
- `vmshpwa/apps/staff/src/local-news-draft.test.ts`: reload/clear/corrupt state и
  московское wall time → UTC.
- Story IDs: `pages-staff-local-news-composer--scheduled`,
  `product-news-moderation--scheduled-local`.

Актуальные результаты после введения server-owned `isScheduled`:

- focused Phase 8 Python: **19 PASS**;
- полный PWA Python gate, восемь workers: **1573 PASS / 6 intentional skips**;
- focused TypeScript: **3 файла / 6 PASS**;
- полный frontend unit gate: **113 файлов / 592 PASS**;
- ESLint + Stylelint, strict TypeScript и production build трёх приложений:
  **PASS**.

## Границы доказательства

- V1 поддерживает обычный текст. Markdown composer и Staff→Telegram publication
  остаются второй версией.
- Существующее hide отменяет показ в PWA; edit/reschedule API ещё не добавлены.
- Due-time notification становится доступно вовремя, но точная foreground
  WebSocket invalidation для открытой вкладки без push ещё не реализована.
- Focused Storybook browser/a11y не выполнил ни одной story: установленный
  Chromium завершился до test collection на macOS `MachPortRendezvous`, error
  code 141. Этот запуск не считается PASS; нужен повтор после исправления
  внешнего launcher-состояния.
- Visual snapshots не обновлялись.

Runbook: [`vmshpwa/docs/local-scheduled-news.md`](../../vmshpwa/docs/local-scheduled-news.md).
