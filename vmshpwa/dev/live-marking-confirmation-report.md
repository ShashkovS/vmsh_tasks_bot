# Подтверждение очных оценок — 14 сентября 2026

[Требования](../docs/live-marking.md#подтверждение-сохранения-оценки--2026-09-14).

Причина: `LiveMarkingPage` передавал выбранный локальный символ в
`LiveMarkButton`, который рисовал его даже для `draft`, `sending`, `queued`,
`failed` и `conflict`. Пунктир и маленький кружок не отличали его достаточно
заметно от сохранённой оценки.

Исправление в `apps/staff/src/live-marking-grid.tsx`: pending не рисуется как
«+»/«−». Во время debounce и первой секунды отправки показаны часы; далее —
«…» с предупреждающим оформлением. Ошибка и конфликт выделены отдельно.
Название выбранного значения остаётся в accessible name и tooltip. После
receipt или отмены черновика возвращается серверный символ. Компонент общий
для очного и Zoom-интерфейсов; формат очереди и серверные данные не менялись.

WebSocket уже был подключён. POST после записи публикует
`live-cells/<lessonId>`, запрос cells подписан на него. После reconnect активные
запросы перечитываются полностью; объединение ячеек не откатывает новую версию
устаревшим ответом. Backend/WS-протокол не требовали исправления.

Проверено:

- 35 Vitest: `live-marking-grid.test.tsx`, `live-marking-state.test.ts`,
  `live-marking-outbox.test.ts`, `realtime-client.test.ts`. Таймер 999/1000 ms,
  receipt, повторная отправка, queued/failed/conflict; прежние тесты сохраняют
  debounce, восстановление очереди после reload, operationId после потерянного
  ответа, явное разрешение конфликта и resync после reconnect.
- 3/3 E2E (`e2e/live-marking-confirmation.spec.ts`): Chromium/WebKit/Firefox,
  реальный изолированный aiohttp, SQLite, две независимые учительские сессии.
  Запрос временно задерживается и затем пропускается на backend без подмены
  ответа. Во время задержки нет плюса; после receipt он есть у обоих учителей.
  Зафиксирован WS frame с ресурсом live-cells. Одна сессия отключена, другая
  сохраняет минус; при reconnect первая получает минус, сохраняющийся при reload.
- TypeScript Staff, ESLint, сборки всех приложений. Миграции не нужны.

| Движок | Desktop, светлая | 390 px, тёмная |
|---|---|---|
| Chromium | [Снимок](assets/live-marking-confirmation/chromium-unconfirmed-desktop.png) | [Снимок](assets/live-marking-confirmation/chromium-unconfirmed-mobile-dark.png) |
| WebKit | [Снимок](assets/live-marking-confirmation/webkit-unconfirmed-desktop.png) | [Снимок](assets/live-marking-confirmation/webkit-unconfirmed-mobile-dark.png) |
| Firefox | [Снимок](assets/live-marking-confirmation/firefox-unconfirmed-desktop.png) | [Снимок](assets/live-marking-confirmation/firefox-unconfirmed-mobile-dark.png) |

Снимки просмотрены. Production не менялся: тест доказывает работу маршрута и
подписки на изолированном backend, а не состояние production NATS в данный момент.
