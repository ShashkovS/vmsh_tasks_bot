# Phase 8: явная семейная сводка по занятию

Дата проверки: 3 августа 2026 года.

## Что реализовано

Администратор вручную отправляет один итог отдельно для конкретного
`group_lesson`. Пустая очередь проверки не запускает рассылку автоматически.
Повторное действие не создаёт дубликаты уже уведомлённым Family-аккаунтам, но
доставляет итог новому подходящему аккаунту, который связали со школьником
позже. Исправления результатов сами по себе повторной рассылки не создают.

Срез переиспользует `notification_events` и `audit_events`; новых таблиц,
очередей и фоновых координаторов не добавлено. Student не получает семейное
событие. Family получает account-scoped `review_completed` с
`kind=family_lesson_digest`, видит его в `/family/profile/notifications` и
может отдельно отключить push-категорию «Итоги занятия».

## Реализация

- SQLite reads/writes: [`db_methods/pwa/family_digest.py`](../../db_methods/pwa/family_digest.py).
- Простая доменная операция и дедупликация:
  [`models/pwa/family_digest.py`](../../models/pwa/family_digest.py).
- Admin GET/POST и owner-scoped invalidation:
  [`apps/pwa_api/notification_routes.py`](../../apps/pwa_api/notification_routes.py),
  [`apps/pwa_app.py`](../../apps/pwa_app.py).
- Push copy: [`helpers/pwa/push_delivery.py`](../../helpers/pwa/push_delivery.py).
- Zod-контракты и HTTP-клиент:
  [`notifications.ts`](../../vmshpwa/packages/contracts/src/notifications.ts),
  [`notification-client.ts`](../../vmshpwa/packages/app-shell/src/notification-client.ts).
- Staff preview/confirm states:
  [`family-digest-panel.tsx`](../../vmshpwa/apps/staff/src/family-digest-panel.tsx).
- Family event/settings UI:
  [`family-notifications-page.tsx`](../../vmshpwa/apps/family/src/family-notifications-page.tsx).
- Production-build scenario:
  [`news-notifications.spec.ts`](../../vmshpwa/e2e/news-notifications.spec.ts).

Коммиты: `cbb084d`, `9ed7662`, `36e9dfd`, `588f03d`.

## Проверенные инварианты

- teacher получает `403`, неизвестное занятие — `404`, неактивное — `409`;
- POST принимает только `{schemaVersion: 1}`;
- одна семья, связанная с несколькими детьми группы, получает одно событие;
- Student events не меняются;
- повторный POST создаёт `0` событий и не двигает cursor;
- поздно связанная семья получает событие без повтора прежним семьям;
- audit создаётся только при фактически созданных событиях;
- Family invalidation адресуется только затронутым account IDs;
- состояние без семейных аккаунтов не изображается как «уже разослано»;
- чтение Family-события подтверждается после трёх секунд реальной видимости.

## Выполненные проверки

- `pytest` для Family digest и push delivery: **13 PASS**;
- Vitest contracts/client: **12 PASS**;
- Staff + Family strict TypeScript и targeted ESLint: **PASS**;
- отдельные production Vite builds Staff и Family: **PASS**;
- полный production build Student/Family/Staff внутри `make pwa-e2e-news`:
  **PASS**, включая оба `injectManifest` service worker;
- Playwright discovery: **18 сценариев** в Chromium/WebKit/Firefox, включая
  `Phase 8: Admin explicitly sends one lesson digest and Family sees it`.

## Незакрытые gates

`make pwa-e2e-news` дошёл до запуска 18 browser cases, но ни один test body не
начал выполняться: Chromium аварийно завершился на macOS
`MachPortRendezvous` code 141, Firefox — `SIGABRT`, WebKit также не запустился.
Это не считается E2E PASS. Storybook browser-mode и ручной visual review в
текущем окружении по той же причине не выполнены; snapshots не обновлялись.

Физическая доставка на установленное iOS/Android устройство и визуальное
принятие владельцем остаются общими Phase-8 rollout gates.
