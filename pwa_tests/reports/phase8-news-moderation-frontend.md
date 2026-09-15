# Phase 8: news moderation frontend proof

Дата: 2026-07-29.

## Граница среза

- Реальный Staff route `/staff/news?state=…` заменяет prototype page.
- Strict contract/client поддерживает list и optimistic hide/restore.
- `NewsModerationList` остаётся presentation-only; HTTP и mutations принадлежат Staff app.
- Local publication editor, scheduler и banners в этот срез не входят.

## Проверяемое поведение

- URL хранит фильтр `all|visible|manual_hidden|source_deleted` с runtime-валидацией;
- teacher получает осмысленный forbidden state от реального API;
- hide/restore передаёт текущую visibility version через `If-Match`;
- pending action блокирует только изменяемую строку;
- source-deleted row не предлагает недопустимое действие;
- API/conflict error остаётся на странице до повторного действия;
- presentation story покрывает visible, hidden, source-deleted и interaction hide → restore.

## Результаты

- ESLint и TypeScript (contracts, app-shell, product, Staff): passed.
- Frontend unit: 74 files, 483 passed.
- Storybook browser interaction: 1 passed.
- Staff production build: passed.
- Manual visual inspection: desktop mobile-light composition accepted as compact; visual snapshots не обновлялись.
- Story ID: `product-news-moderation--lifecycle`.
