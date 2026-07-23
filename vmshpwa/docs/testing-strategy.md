# Стратегия тестирования

## Пирамида

1. Vitest: Zod contracts, query keys, runtime configuration, чистые преобразования, Dexie/outbox и deadline logic.
2. React Testing Library + user-event: редкие изолированные случаи, где DOM integration невозможно надёжно выразить story.
3. Storybook + addon-vitest browser mode: primitives, product components, theme/level/density matrices, loading/empty/error/offline states и interaction tests.
4. Playwright: реальные страницы и aiohttp, base paths/history fallback, runtime API, WebSocket/reconnect, PWA lifecycle, audience isolation и визуальные снимки.
5. Отдельная pytest-регрессия исторических Telegram-сценариев.

## Правила окружения

Unit и Storybook используют MSW 2. Main E2E никогда не использует MSW: Playwright поднимает профиль `pwa-e2e` с отдельной SQLite, media root и NATS prefix. Google и Telegram network calls в новых unit/E2E запрещены. Production build падает при включённом prototype MSW.

`make telegram-history-test` запускает только исторические handler-сценарии с `RecordingBot`, token-shaped заведомо фиктивным значением и без загрузки Telegram/Google credentials. Этот профиль не запускает polling/webhook и не является способом тестировать новый PWA API.

E2E выполняется в Chromium, WebKit и Firefox. Критические mobile Student flows дополнительно получают device projects при появлении реальных submission endpoints. iOS baseline — 16.4, Android — 10.

Основной E2E сначала собирает все три production bundles, затем запускает `vite preview` и настоящий aiohttp. Поэтому functional, visual, route splitting, manifests и service-worker проверки видят production CSS/chunks, а не dev/HMR-поведение. Deploy smoke остаётся отдельным коротким контролем уже разложенных сервером assets. MSW не используется ни в одном E2E-режиме.

## Visual regression

Снимки страниц хранятся по browser project, делаются при фиксированном viewport, locale, timezone и reduced motion. Сейчас reference environment — macOS машины владельца; Docker normalization откладывается. `pwa-visual-update` не является способом «починить» тест: перед обновлением человек или агент обязан открыть diff, проверить обе темы и убедиться, что изменение ожидаемо. Raw snapshots не меняются вместе с не относящимся к UI refactor.

## Accessibility

Storybook a11y violations имеют status `error`. Проверяются keyboard order, visible focus, accessible names, dialogs/focus trap, таблицы, zoom/reflow, forced colors where applicable и контраст WCAG 2.2 AA. Цвет никогда не является единственным носителем статуса.

Этот baseline одинаков для Student, Family и Staff. Отказ от сложной accessibility-модели отдельного drag-and-drop не отменяет labels, alt, валидный ARIA, keyboard navigation, focus и axe gate: Staff использует доступные buttons/select/move alternatives.

## Definition of done компонента

Публичный общий компонент имеет типы, semantic tokens, stories основных состояний, interaction/a11y test при наличии поведения и краткое назначение. Изменение общего компонента сопровождается обновлением stories; app-specific logic не переносится в `packages/ui`.

Числовой coverage threshold сознательно не вводится. Покрываются contract boundaries, рискованные чистые функции, offline/idempotency logic и наблюдаемое поведение; бессодержательные тесты ради процента не добавляются.

## Начальная приёмка каркаса

- strict typecheck, ESLint, Prettier check, Vitest и Python PWA tests проходят;
- три production bundles собираются, Student/Family создают injectManifest workers;
- Storybook строится и browser tests запускаются;
- Playwright подтверждает shell/base/history/theme/runtime/WebSocket/PWA/audience separation во всех трёх движках;
- Telegram regression запускается отдельной командой.
