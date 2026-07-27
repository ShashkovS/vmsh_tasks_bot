# Этап 1. Вход, сессии, principal и права

## Результат

Student входит сгенерированным логином и текущим Telegram-токеном, Family — отдельным минимальным аккаунтом, Staff — staff credentials. Три кабинета защищены настоящими server sessions до ближайшего 10 августа; cookie одного audience не авторизует другой.

Дизайн-контракт этапа: [три login pages, form states, forbidden state и соответствующие Storybook stories](18-design-implementation-map.md#phase-1-design).

## Модель данных и миграция

Миграции этапа: `migrations/0039.pwa_auth_accounts_sessions.sql` и
`migrations/0040.pwa_courses_access.sql`, обе с точным rollback. Решение по
криптографии, ротации и отзыву: [`ADR 0003`](../../../adr/0003-pwa-authentication-cryptography-and-sessions.md).

Создать `auth_accounts`, `family_student_links`, `auth_sessions`, `auth_events`,
shared-worker `auth_throttle_buckets`, а затем `seasons`, `courses`,
course enrollment/access/events и единственный новый permission source
`staff_scopes`. Параллельную `staff_group_permissions` не создавать. Production
backfill сначала dry-run:

- student username строится версионированным transliteration helper как фамилия + день рождения; import preview блокирует коллизии, `NULL`/невалидную дату, пустую фамилию и позволяет исправить source либо назначить явно сохранённый уникальный вариант;
- student/staff account связывается с `users.id`;
- student credential не копирует plaintext token во второе поле;
- family accounts импортируются только из согласованного файла/Staff batch flow, хранят имя без фамилии/email и поддерживают many-to-many child links;
- конфликтующие normalized usernames попадают в report, не исправляются автоматически.
- credential profile сверяется с этапом 0. По закрытому `AUTH-01` настоящие аккаунты должны иметь корректную фамилию и пригодный Telegram token; некорректные test/unknown rows не активируются для production web и попадают в aggregate/quarantine report без plaintext/hash, по которому можно восстановить token.

## Backend

- App factory получает auth/session dependencies без Telegram/Google imports.
- Middleware разрешает только login/health/static как public routes.
- Principal содержит `accountId`, `audience`, optional `userId`, role/capabilities, allowed groups и session version.
- Signed 15-minute access cookie + opaque single-use refresh secret; SQLite хранит только HMAC refresh secret, session/version/revocation и secret-free audit.
- Cookie: отдельное имя, `Path=/student|family|staff`, `HttpOnly`, `Secure` production, `SameSite`, общий для всех audiences срок до ближайшего 10 августа и ранний revoke.
- Origin/Referer check на unsafe methods, CSP для HTML/static, nginx rate-limit
  contract для login. Public origin и доверенные reverse-proxy hops задаются
  явно: приложение не выводит security origin из произвольных
  `Forwarded`/`X-Forwarded-*` headers. Phase-0 E2E gateway отправляет upstream
  `Host` API 8380 при browser `Origin` 5380 и не считается auth/CSRF моделью.
- Помимо IP-level nginx limit, backend ведёт normalized-login/account-level throttling с bounded backoff/temporary lock, чтобы распределённые попытки не обходили защиту. Ответ и timing не подтверждают существование username.
- Device list, soft revoke one, logout all, credential version invalidation; refresh rotation использует optimistic session version, replay отзывает lineage.
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
- Trusted-proxy/public-origin integration: direct и разрешённый proxy request,
  неверный Origin/Referer, а также spoofed `Forwarded`, `X-Forwarded-Host`,
  `X-Forwarded-Proto` и смешанные header chains.
- Rate-limit header integration test с nginx test config или отдельным deploy smoke.
- Account-level throttling: много IP → один login, один IP → много login, окно/сброс, конкурентные workers и отсутствие user enumeration.
- No token/password in logs, Sentry events, response or fixtures.
- Playwright: login/logout/reload/revoke separate device, intended route, `401` vs `403`, simultaneous audiences in isolated browser contexts.
- Historical Telegram login/token сценарии отдельно, если общий token code менялся.

## Критерии приёмки

- Прямой переход на любую private route отправляет на правильный login и затем возвращает обратно.
- Сброс Telegram token завершает student sessions согласно выбранной policy.
- Teacher не может вызвать admin endpoint вручную.
- Family поддерживает несколько детей и несколько родителей, но не может заменить child ID и открыть несвязанного ребёнка.
- App factory и тесты не требуют Telegram/Google credentials.
- CSRF/security origin не зависит от недоверенного proxy header; одинаковая
  policy доказана через production-like trusted-proxy harness, а не только
  Phase-0 loopback gateway.
- Каждый активный Student из утверждённого launch cohort имеет активированный account либо явно перечисленное владельцем исключение; строка с отсутствующей birthday/небезопасным token не превращается в неожиданный production lockout.
- Сгенерированные usernames воспроизводимы на frozen transliteration fixtures и не меняются после обновления helper version.

## Пруфы завершения этапа

- [ ] Revision и migration: `<sha/path>`; empty/upgrade/rollback results `<path>`.
- [ ] Auth decision record: cookie/session/expiry/revoke/CSRF details `<path>`.
- [ ] Import/preflight report: birthday/surname/collision/credential-policy blockers без секретов; test/unknown rows исключены из production activation по `AUTH-01`: `<path/result>`.
- [ ] Demo: Student, Family, Teacher, Admin fixture logins без публикации паролей `<route/result>`.
- [ ] Permission matrix API test report: `<path/result>`.
- [ ] Cookie/security assertions и trusted-proxy/spoofed-forwarded matrix:
      `<result>`; nginx rate-limit smoke `<result>`.
- [ ] Storybook login/session/forbidden states and visual approval: `<story ids/paths>`.
- [ ] Playwright 3 browsers: `<result>`.
- [ ] Telegram historical auth tests: `<result or N/A reason>`.
- [ ] Docs/runbook updated: `<paths>`.
- [ ] Known limitations/issues and acceptance: `<links/name/date>`.

## Многокурсовый инкремент Phase 1

Создать course enrollment/access/event и Staff scope migrations/contracts. Student session получает доступ к нескольким курсам, но active group и mode меняются только внутри одного enrollment. Teacher scope допускает весь курс либо отдельные группы; прямой запрос вне scope возвращает `403`.

Дополнительный proof: backfill «Математика 5–7», один active + несколько allowed groups, per-course mode history, revoked-access history visibility, course/group permission matrix и Storybook `Product/Courses--student-multiple-courses`, `--active-and-allowed-groups`, `Pages/Staff--teacher-forbidden`.
