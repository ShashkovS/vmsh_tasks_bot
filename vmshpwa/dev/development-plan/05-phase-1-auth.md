# Этап 1. Вход, сессии, principal и права

## Результат

Student входит сгенерированным логином и текущим Telegram-токеном, Family — отдельным минимальным аккаунтом, Staff — staff credentials. Три кабинета защищены настоящими server sessions до ближайшего 10 августа; cookie одного audience не авторизует другой.

## Модель данных и миграция

Логическая migration: `migrations/NNNN.pwa_auth_accounts_sessions.sql`.

Создать `seasons` (если решение принято), `auth_accounts`, `family_student_links`, `staff_group_permissions`, `auth_sessions`, `auth_events`. Production backfill сначала dry-run:

- student username строится как транслитерация фамилии + день рождения; import preview блокирует коллизии и позволяет назначить уникальный вариант;
- student/staff account связывается с `users.id`;
- student credential не копирует plaintext token во второе поле;
- family accounts импортируются только из согласованного файла/Staff batch flow, хранят имя без фамилии/email и поддерживают many-to-many child links;
- конфликтующие normalized usernames попадают в report, не исправляются автоматически.

## Backend

- App factory получает auth/session dependencies без Telegram/Google imports.
- Middleware разрешает только login/health/static как public routes.
- Principal содержит `accountId`, `audience`, optional `userId`, role/capabilities, allowed groups и session version.
- Signed short cookie + server session/refresh record либо выбранная альтернатива.
- Cookie: отдельное имя, `Path=/student|family|staff`, `HttpOnly`, `Secure` production, `SameSite`, общий для всех audiences срок до ближайшего 10 августа и ранний revoke.
- Origin/Referer check на unsafe methods, CSP для HTML/static, nginx rate-limit contract для login.
- Device list, revoke one, logout all, credential version invalidation.
- API не отличает неверный login от неверного token сообщением.

Пути: `apps/pwa_api/auth_routes.py`, `apps/pwa_api/middleware.py`, `models/pwa/auth.py`, `db_methods/pwa/auth.py`, `helpers/pwa/permissions.py`.

## Frontend

- Реальные login routes уже существуют: `student/family/staff/src/routes/login.tsx`.
- `packages/contracts/src/auth.ts` и `app-shell/src/auth-boundary.tsx`.
- Login error, collision/import-disabled account, rate limit, expired session, blocked, offline, password visibility, contact `vmsh@179.ru`.
- Нет onboarding v1; после первого входа redirect к intended route или home.
- Session/device management в profile; confirmation перед logout с непустым offline outbox.
- Forbidden route получает осмысленную страницу, но не раскрывает admin data.

## Tests

- Hash/sign/expiry/revoke/credential-version unit tests с замороженным временем вокруг 10 августа.
- API matrix: anonymous/Student/Family/Teacher/Admin × all audience bases.
- Cookie path/domain/SameSite/Secure/HttpOnly assertions; session fixation and rotation tests.
- Rate-limit header integration test с nginx test config или отдельным deploy smoke.
- No token/password in logs, Sentry events, response or fixtures.
- Playwright: login/logout/reload/revoke separate device, intended route, `401` vs `403`, simultaneous audiences in isolated browser contexts.
- Historical Telegram login/token сценарии отдельно, если общий token code менялся.

## Критерии приёмки

- Прямой переход на любую private route отправляет на правильный login и затем возвращает обратно.
- Сброс Telegram token завершает student sessions согласно выбранной policy.
- Teacher не может вызвать admin endpoint вручную.
- Family поддерживает несколько детей и несколько родителей, но не может заменить child ID и открыть несвязанного ребёнка.
- App factory и тесты не требуют Telegram/Google credentials.

## Пруфы завершения этапа

- [ ] Revision и migration: `<sha/path>`; empty/upgrade/rollback results `<path>`.
- [ ] Auth decision record: cookie/session/expiry/revoke/CSRF details `<path>`.
- [ ] Demo: Student, Family, Teacher, Admin fixture logins без публикации паролей `<route/result>`.
- [ ] Permission matrix API test report: `<path/result>`.
- [ ] Cookie/security assertions: `<result>`; nginx rate-limit smoke `<result>`.
- [ ] Storybook login/session/forbidden states and visual approval: `<story ids/paths>`.
- [ ] Playwright 3 browsers: `<result>`.
- [ ] Telegram historical auth tests: `<result or N/A reason>`.
- [ ] Docs/runbook updated: `<paths>`.
- [ ] Known limitations/issues and acceptance: `<links/name/date>`.
