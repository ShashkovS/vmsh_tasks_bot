# Phase 10: создание Student web-входа

Дата проверки: 2 августа 2026 года.

## Что работает

- Admin создаёт web-вход для уже существующего школьника, у которого аккаунта ещё нет.
- В браузер передаётся только выбранный логин. Текущий `users.token` читается сервером, нормализуется по тем же правилам, что и Telegram-бот, и хранится в `auth_accounts` только как Argon2id hash.
- Teacher получает `403`; небезопасный legacy-токен — `422`; занятый логин или повторная привязка — `409`.
- Ответ и `auth_events` не содержат Telegram-токен. После создания тот же текущий токен действительно открывает Student PWA.
- Несохранённый логин Staff хранится в account/student-scoped `localStorage`; секретов в черновике нет.

## Реализация

- API: `POST /staff/api/v1/students/{student_public_id}/student-account` в `apps/pwa_api/admin_account_routes.py`.
- Простые SQLite-операции: `db_methods/pwa/admin_accounts.py`.
- Нормализация и проверка: `models/pwa/admin_accounts.py`.
- Zod/client/UI: `admin-student-enrollments.ts`, `admin-course-client.ts`, `student-account-creator.tsx`.
- Storybook: `Pages/Staff--student-account-creation`.

## Выполненные проверки

- `pwa_tests/domain/test_admin_accounts.py`: 13 passed.
- `pwa_tests/integration/test_phase10_admin_accounts.py`: 9 passed.
- `make pwa-lint pwa-typecheck pwa-test pwa-build`:
  - frontend unit: 104 files, 573 passed;
  - Python PWA: 1508 passed, 5 skipped;
  - все три production bundles и оба `injectManifest` service workers собраны.
- Staff Storybook browser test: 1 file, 22 stories passed, включая создание аккаунта и восстановление черновика формы.
- `make pwa-e2e-auth`: 80 passed, 10 ожидаемо skipped. Chromium через
  production bundles и настоящий aiohttp создаёт web-вход для отдельного
  синтетического школьника без аккаунта, восстанавливает несекретный Staff draft
  после reload и входит в Student PWA по текущему bot token. WebKit и Firefox
  продолжают проверять общую auth-регрессию; shared-SQLite provisioning выполняет
  один браузер, чтобы мутационные сценарии не конфликтовали.

## Оставшаяся граница

Индивидуальный путь создания Student-аккаунта закрыт от Staff UI до настоящего
Student login без test-only HTTP backdoor. Этап 10 всё ещё требует отдельного
batch provisioning/import с dry-run и отчётом по неактивированным строкам.
