# Phase 10: создание Student web-входа

Дата проверки: 2 августа 2026 года.

## Что работает

- Admin создаёт web-вход для уже существующего школьника, у которого аккаунта ещё нет.
- В браузер передаётся только выбранный логин. Текущий `users.token` читается сервером, нормализуется по тем же правилам, что и Telegram-бот, и хранится в `auth_accounts` только как Argon2id hash.
- Teacher получает `403`; небезопасный legacy-токен — `422`; занятый логин или повторная привязка — `409`.
- Ответ и `auth_events` не содержат Telegram-токен. После создания тот же текущий токен действительно открывает Student PWA.
- Несохранённый логин Staff хранится в account/student-scoped `localStorage`; секретов в черновике нет.
- Для строки без аккаунта backend предлагает канонический логин
  `transliterated-surname-DD`. Предложение появляется только у admin, а
  совпадения и некорректная фамилия/дата рождения явно требуют ручного решения;
  случайный suffix не придумывается.
- Admin может выбрать небольшую ежедневную пачку строк с однозначными
  предложениями и создать входы одной кнопкой. Пачка последовательно использует
  тот же одиночный API: успешные строки применяются, ошибки остаются выбранными
  и показываются поимённо.
- Выбор пачки хранится в account-scoped `localStorage`, переживает reload и не
  содержит Telegram-токенов. Первоначальная миграция всех исторических
  аккаунтов по-прежнему выполняется отдельным guarded CLI с dry-run и отчётом.

## Реализация

- API: `POST /staff/api/v1/students/{student_public_id}/student-account` в `apps/pwa_api/admin_account_routes.py`.
- Простые SQLite-операции: `db_methods/pwa/admin_accounts.py`.
- Нормализация и проверка: `models/pwa/admin_accounts.py`.
- Zod/client/UI: `admin-student-enrollments.ts`, `admin-course-client.ts`,
  `student-account-creator.tsx`, `student-account-batch-panel.tsx` и
  `student-account-batch-draft.ts`.
- Storybook: `Pages/Staff--student-account-creation` и
  `Pages/Staff--student-account-batch-creation`.

## Выполненные проверки

- `pwa_tests/domain/test_admin_accounts.py`: 13 passed.
- `pwa_tests/integration/test_phase10_admin_accounts.py`: 9 passed.
- Directory/account focused HTTP suite: 15 passed, включая unique suggestion,
  collision и invalid-identity состояния.
- `make pwa-lint pwa-typecheck pwa-test pwa-build`:
  - frontend unit: 105 files, 575 passed;
  - Python PWA: 1509 passed, 5 skipped;
  - все три production bundles и оба `injectManifest` service workers собраны.
- Полный Python PWA suite отдельно подтверждён в `-n8`: 83,11 секунды вместо
  274,14 секунды в `-n0`; каждый worker использует собственную временную SQLite.
- Staff Storybook browser test: 1 file, 23 stories passed, включая одиночное и
  пакетное создание аккаунтов и восстановление локальных черновиков.
- `make pwa-e2e-auth`: 81 passed, 12 ожидаемо skipped. Chromium через
  production bundles и настоящий aiohttp создаёт web-вход для отдельного
  синтетического школьника без аккаунта, восстанавливает несекретный Staff draft
  после reload и входит в Student PWA по текущему bot token. Отдельный сценарий
  сохраняет выбор двух школьников после reload и создаёт оба входа. WebKit и
  Firefox продолжают проверять общую auth-регрессию; shared-SQLite provisioning
  выполняет один браузер, чтобы мутационные сценарии не конфликтовали.

## Оставшаяся граница

Индивидуальный и небольшой ежедневный пакетный пути создания Student-аккаунтов
закрыты от Staff UI до настоящего Student login без test-only HTTP backdoor.
Этап 10 всё ещё требует первоначального bulk provisioning/import с dry-run и
отчётом по неактивированным строкам.
