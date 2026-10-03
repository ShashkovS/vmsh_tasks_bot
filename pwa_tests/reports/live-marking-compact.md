# Компактный live-приём — 10 сентября 2026

Требования: [live-marking.md](../../vmshpwa/docs/live-marking.md),
[Phase 5](../../vmshpwa/dev/design-system/05-pages-and-flows.md).

## Изменение

Zoom: 24 задачи занимают 2 строки при 1440×900 и 6 строк при 390×844;
каждая оценка и кнопка условия имеют отдельную цель минимум 44×44 px.
Полные номера подпунктов сохраняются при переносе. Условия загружаются
по требованию из опубликованной версии, общий текст и подпункты сохраняются.
Закрытие восстанавливает фокус также в Safari, оценки не меняются.

На мобильном очном экране одна строка инструментов с настройками по нажатию
на аудиторию; ФИО шириной 112 px с переносами, шрифтом 12 px. Колонка
не растягивается даже при одной задаче. На компьютере ширина ФИО 160 px.
Реакции и переход к следующему школьнику сохранены; desktop-footer — одна строка.

## Проверки

- `pytest -q -n0 pwa_tests/integration/test_live_marking.py`: **11 passed**.
  Опубликованный документ, чужая сессия, неверная задача, скрытая публикация;
  чтение не меняет оценки. Прежние mark/undo/transfer/reaction сценарии сохранены.
- `vitest run --config vitest.storybook.config.ts apps/staff/src/live-marking-grid.stories.tsx`:
  **6 passed**, axe в режиме error. 24 задачи с подпунктами, независимый просмотр
  условия, ограничение ширины при одной задаче, pending/conflict, 200×50 performance.
- Staff TypeScript, ESLint затронутых frontend-файлов, Ruff и Prettier прошли.
- Финальный `make pwa-e2e-oral`: **9 passed** во всех трёх движках, 1.8 мин.
  Все production-сборки прошли. Снимки делаются с `animations: disabled`,
  чтобы исключить промежуточные цвета при переключении темы.

E2E использует production Vite build и реальные aiohttp/SQLite/WebSocket/IndexedDB,
24 опубликованные задачи вместо прежней единственной. Проверяется отсутствие
прокрутки страницы по горизонтали при 320 px, плотность при 390 px, размер
кнопок, focus restore, условия, оценки/undo/offline, реакции/похвала, перенос,
посещение и совместная работа; старый oral flow также включён.

Все проверки используют изолированный agent/E2E профиль; схема БД и production
данные не изменялись. Физические телефоны не использовались. Визуальное
принятие владельцем открыто; прежние golden snapshots не обновлялись.

## Снимки и логи

Локальные логи: [backend](live-marking-compact/backend.log),
[Storybook](live-marking-compact/stories.log), [E2E/build](live-marking-compact/e2e.log).

| Браузер | Zoom desktop | Zoom mobile | Dark | Условие | Очное mobile |
| --- | --- | --- | --- | --- | --- |
| chromium | [снимок](live-marking-compact/chromium-live-zoom-desktop.png) | [снимок](live-marking-compact/chromium-live-zoom-mobile.png) | [снимок](live-marking-compact/chromium-live-zoom-mobile-dark.png) | [снимок](live-marking-compact/chromium-live-condition-mobile.png) | [снимок](live-marking-compact/chromium-live-classroom-mobile.png) |
| webkit | [снимок](live-marking-compact/webkit-live-zoom-desktop.png) | [снимок](live-marking-compact/webkit-live-zoom-mobile.png) | [снимок](live-marking-compact/webkit-live-zoom-mobile-dark.png) | [снимок](live-marking-compact/webkit-live-condition-mobile.png) | [снимок](live-marking-compact/webkit-live-classroom-mobile.png) |
| firefox | [снимок](live-marking-compact/firefox-live-zoom-desktop.png) | [снимок](live-marking-compact/firefox-live-zoom-mobile.png) | [снимок](live-marking-compact/firefox-live-zoom-mobile-dark.png) | [снимок](live-marking-compact/firefox-live-condition-mobile.png) | [снимок](live-marking-compact/firefox-live-classroom-mobile.png) |
