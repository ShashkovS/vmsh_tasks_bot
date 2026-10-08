# Phase 8 proof: настоящие настройки уведомлений Family

Дата проверки: 3 августа 2026 года.

## Проверяемый результат

- `/family/profile/notifications` использует authenticated Family account и
  настоящий `/family/api/v1/notifications/preferences` вместо prototype.
- Family меняет push для нового урока, подсказок, решений, дедлайна и новостей.
  Individual review, oral window и classroom assignment не выдаются за
  доступные Family push-категории.
- Настройка переживает reload. E2E восстанавливает исходное значение fixture,
  чтобы повторный запуск и браузерные проекты не влияли друг на друга.
- Browser subscription handshake общий для Student и Family: существующая
  подписка сверяется с сервером, новая создаётся только после контекстного
  разрешения, отключение удаляет server row и browser subscription.
- Loading, available, enabled, denied, unsupported и error имеют явные
  product states. Weekly Family digest не объявлен готовым до ответа на вопрос
  8 development plan.

## Реализация и трассировка

- Production page и route:
  `vmshpwa/apps/family/src/family-notifications-page.tsx`,
  `vmshpwa/apps/family/src/routes/profile.notifications.tsx`.
- Browser handshake: `vmshpwa/packages/app-shell/src/push-device.ts`.
- Presentation: `vmshpwa/packages/product/src/push-device-controls.tsx`.
- Story IDs: `pages-family-notifications--ready`, `--loading`, `--error`,
  `--push-denied`, `pages-family--notifications`,
  `product-connectivity--push-device-states`.
- Production E2E scenario:
  `Phase 8: Family changes real notification preferences without individual review push`
  in `vmshpwa/e2e/news-notifications.spec.ts`.

## Автоматические проверки

- Focused unit: **2 файла / 5 PASS**.
- Focused Storybook interaction/a11y: **3 файла / 22 PASS**.
- Полный frontend unit: **114 файлов / 594 PASS**.
- Полный PWA Python: **1586 PASS / 6 intentional skips**.
- Полный Storybook browser/a11y: **52 файла / 250 PASS**.
- Production-build news E2E: **12/12 PASS** в Chromium, Firefox и WebKit без
  retry.
- ESLint, Stylelint, strict TypeScript и production build трёх приложений:
  **PASS**.

Visual snapshots не обновлялись. Ручное визуальное принятие владельцем и
server-trigger недельного Family digest остаются открытыми.
