# Phase 2 production upload recovery — 13 August 2026

## Проверенный пользовательский результат

- Одно действие создаёт занятие для всех активных групп выбранного курса через
  существующий endpoint; при частичном успехе Staff показывает созданные и
  не созданные группы, не маскируя результат.
- Новый `.tex` в массовой загрузке получает вид «Условие» по умолчанию.
- Missing-assets не выглядит потерянной загрузкой: revision остаётся сохранённой,
  строка ведёт в соответствующую карточку материала, где можно собрать TikZ SVG
  или загрузить внешний рисунок и повторить сборку.
- Прикреплённые raster/SVG показываются небольшим превью исходного public asset;
  клик открывает тот же оригинал в увеличенном Dialog. Отдельный thumbnail не
  создаётся и новый backend endpoint не нужен.
- Реальный production-кейс подтвердил, что одна TikZ-производная сохранилась, а
  следующая загрузка списка ресурсов сломалась из-за преобразования strong ETag
  в `W/`-ETag фильтром сжатия nginx. Клиент нормализует только строгий известный
  version-token и сохраняет Brotli для остальных API-ответов.

## Реализация

- [`staff-lessons-page.tsx`](../../vmshpwa/apps/staff/src/staff-lessons-page.tsx)
- [`bulk-content-upload.tsx`](../../vmshpwa/apps/staff/src/bulk-content-upload.tsx)
- [`bulk-content-upload-model.ts`](../../vmshpwa/apps/staff/src/bulk-content-upload-model.ts)
- [`content-page.tsx`](../../vmshpwa/apps/staff/src/content-page.tsx)
- [`content-client.ts`](../../vmshpwa/packages/content/src/content-client.ts)
- [`staff-publishing.tsx`](../../vmshpwa/packages/product/src/staff-publishing.tsx)

## Пруфы

- Focused frontend unit: **22 passed**.
- `make pwa-lint`: **PASS**.
- `make pwa-typecheck`: **PASS**.
- `make pwa-build`: **PASS**, Student/Family injectManifest service workers built.
- `make pwa-storybook-test`: **265 passed**.
- `git diff --check`: **PASS**.
- Full `make pwa-test`: **611 passed / 11 failed**. Все 11 падений находятся в
  ранее известном baseline `app-shell` auth/session management и Student search
  schema; они воспроизводятся отдельно и не затрагивают изменённые модули.
- Visual snapshots не обновлялись.

## Production follow-up

Достаточно обычной публикации frontend. Nginx менять или перезагружать для этого
исправления не требуется.
