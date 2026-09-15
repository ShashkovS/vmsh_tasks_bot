# Phase 10: управление существующими аккаунтами

Дата проверки: 30 июля 2026 года.

## Что работает

- Admin видит актуальные состояния и версии Student/Family-аккаунтов в каталоге участников.
- Admin может перевести существующий аккаунт в `active`, `blocked`, `disabled` или `archived` с optimistic `If-Match`.
- Admin может заменить Telegram-токен школьника или пароль семьи. Значение хешируется, не возвращается API и не попадает в audit metadata.
- Изменение состояния или credential завершает действующие сессии аккаунта и закрывает его WebSocket-соединения.
- Teacher получает `403` на lifecycle-endpoints и не получает account/link data в каталоге.
- Токен/пароль формы намеренно не записывается в `localStorage`.

## Реализация

- HTTP: `apps/pwa_api/admin_account_routes.py`.
- Короткие SQLite-операции: `db_methods/pwa/admin_accounts.py`.
- Правила состояния и credential: `models/pwa/admin_accounts.py`.
- Runtime contracts: `vmshpwa/packages/contracts/src/admin-student-enrollments.ts`.
- Browser client: `vmshpwa/packages/app-shell/src/admin-course-client.ts`.
- Staff UI: `vmshpwa/apps/staff/src/student-account-controls.tsx` и `staff-student-directory-page.tsx`.
- Storybook: `pages-staff--student-account-lifecycle`.

## Проверки

- Python domain/API: 17 тестов Phase-10 accounts/enrollments прошли.
- Совместный startup/permission regression: 97 тестов прошли перед фиксацией backend-инкремента.
- TypeScript contracts/client: 12 тестов прошли.
- Полный frontend Vitest: 102 файла, 563 теста прошли.
- Storybook browser tests: 47 файлов, 224 теста прошли.
- Полные frontend lint, typecheck и production build трёх приложений прошли.
- Story `pages-staff--student-account-lifecycle` вручную проверена в agent-Storybook на desktop viewport; visual snapshots не обновлялись.

## Что этим proof не закрыто

- Создание нового Student/Family-аккаунта и привязка семьи.
- Выбранный владельцем способ сформировать и безопасно передать семье первоначальные данные для входа.
- Импорт участников, 1500-row performance proof и полный Playwright workflow Phase 10.
