# Этап 1. Вход, сессии, principal и права

## Результат

Student входит заданным batch login и текущим Telegram-токеном, Family —
заданным отдельным login/password, Staff — staff credentials. Три кабинета
защищены настоящими server sessions до ближайшего 10 августа; cookie одного
audience не авторизует другой.

Дизайн-контракт этапа: [три login pages, form states, forbidden state и соответствующие Storybook stories](18-design-implementation-map.md#phase-1-design).

## Модель данных и миграция

Миграции этапа: `migrations/0039.pwa_auth_accounts_sessions.sql` и
`migrations/0040.pwa_courses_access.sql`, обе с точным rollback. Решение по
криптографии, ротации и отзыву: [`ADR 0003`](../../../adr/0003-pwa-authentication-cryptography-and-sessions.md).

Создать `auth_accounts`, `family_student_links`, `auth_sessions`, `auth_events`,
shared-worker `auth_throttle_buckets`, а затем `seasons`, `courses`,
course enrollment/access/events и единственный новый permission source
`staff_scopes` и `family_account_emails`. Параллельную
`staff_group_permissions` не создавать. Target batch flow:

- Student batch принимает surname, name, optional patronymic/birth date/grade,
  login и Telegram-token password; preview предлагает случайный `-NN` для
  конфликтующего login;
- student/staff account связывается с внутренним `users.id`, а controlled activation одновременно назначает отсутствующий opaque `users.public_id`; этот случайный стабильный ID является browser `userId`/`studentId` и не совпадает с `auth_accounts.public_id` (`accountId`);
- Family batch отдельно принимает name, login/password, comma-separated emails
  и child logins; связи many-to-many;
- по owner-confirmed v1 policy оба plaintext password сохраняются для внешнего
  mailer наряду с Argon2 verifier, но исключаются из обычных API/logs/proofs;
- test passwords `qwerty*` допустимы в летнем cohort и затем удаляются.

## Backend

- App factory получает auth/session dependencies без Telegram/Google imports.
- Middleware разрешает только health/runtime/login/refresh и идемпотентный
  logout как public API routes; любой другой зарегистрированный
  `/{audience}/api/v1/*` route private по умолчанию. Static boundary живёт вне
  versioned API.
- Principal содержит разные `accountId` и optional `userId`, `audience`, role/capabilities, allowed groups и session version. Отсутствующий `users.public_id` у связанной Student/Staff строки является ошибкой целостности и закрывает вход.
- Signed 15-minute access cookie + opaque single-use refresh secret; SQLite хранит только HMAC refresh secret, session/version/revocation и secret-free audit.
- Cookie: отдельное имя, `Path=/student|family|staff`, `HttpOnly`, `Secure` production, `SameSite`, общий для всех audiences срок до ближайшего 10 августа и ранний revoke.
- Origin/Referer check на всех unsafe browser methods, включая login до cookie;
  безопасными считаются только `GET`/`HEAD`/`OPTIONS`. CSP для HTML/static, nginx rate-limit
  contract для login. Public origin и доверенные reverse-proxy hops задаются
  явно: приложение не выводит security origin из произвольных
  `Forwarded`/`X-Forwarded-*` headers. Phase-0 E2E gateway отправляет upstream
  `Host` API 8380 при browser `Origin` 5380 и не считается auth/CSRF моделью.
- Production proxy удаляет клиентские forwarding headers и формирует один
  канонический chain. Для RFC 7239 первый элемент по принятой deploy-конвенции
  несёт external host/proto; convention проверяется с настоящим nginx config.
- WebSocket GET является явным исключением из safe-method policy: handshake
  требует точного browser Origin и действующей audience session до upgrade;
  после `prepare()` registry сначала создаёт pending/non-routable связь с
  server-verified account и 32-hex session ID, затем повторно проверяет SQLite
  authority и только вместе с первым cursor frame делает socket routable.
  Session-close tombstone и pending close-index закрывают отзыв между auth и
  register; per-audience broadcast lock не позволяет invalidation опередить
  `connected|resync-required` или потеряться на его cursor. Все send/close
  операции используют per-socket locks с bounded concurrency/timeout. Session
  revoke/logout закрывает связанные sockets локально и через строгий NATS
  control event, а long-lived connection периодически перепроверяет server
  state в SQLite.
- Teacher collection всегда выполняется scope-filtered query. Для конкретного
  student/resource service сначала загружает его authoritative course/group и
  проверяет этот scope; request `studentId` нельзя авторизовать в сочетании с
  независимо переданным разрешённым `groupId`.
- Помимо IP-level nginx limit, backend ведёт normalized-login/account-level throttling с bounded backoff/temporary lock, чтобы распределённые попытки не обходили защиту. Ответ и timing не подтверждают существование username.
- Перед Argon2 verify stored encoding проверяется на щедрый bounded resource
  envelope (Argon2id v16/v19, до 256 MiB, `time_cost <= 10`,
  `parallelism <= 16`, bounded encoding/salt/hash). Malformed и syntactically
  valid, но out-of-policy active hashes выбирают тот же startup dummy hash, что
  unknown account; результат dummy-проверки никогда не авторизует такую строку.
- Device list, soft revoke one, logout all, credential version invalidation; refresh rotation использует optimistic session version, replay отзывает lineage.
- API не отличает неверный login от неверного token сообщением.

Пути: `apps/pwa_api/{auth_routes,auth_service,middleware,realtime_control,websocket_sessions}.py`,
`apps/pwa_app.py`, `models/pwa/auth.py`, `db_methods/pwa/auth.py`,
`helpers/pwa/{permissions,request_security}.py`.

### Реализованный HTTP-инкремент — 27 июля 2026

- `apps/pwa_api/auth_service.py` связывает Argon2 login, SQLite throttle,
  single-use refresh rotation/replay revoke, principal projection и soft revoke;
- `apps/pwa_api/auth_routes.py` реализует все семь audience-auth routes из
  API-карты, exact cookie names/paths, server expiry и очистку cookies;
- `apps/pwa_api/middleware.py` применяет exact target/origin/proxy boundary ко
  всем versioned audience API, держит малый public allowlist и повторно
  проверяет access session в SQLite;
- `apps/pwa_app.py` создаёт auth service после verified DB lifecycle, не
  импортируя Telegram/Google settings;
- production marker `pwa-production` или `PROD=true` включает production mode,
  запрещает prototype, требует HTTPS origins и приводит к `Secure` cookies.

Проверено: focused auth/repository/HTTP/transport gate — 245 PASS; полный
`pwa_tests` на момент HTTP-инкремента — 714 PASS, 1 intentional skip. В HTTP suite покрыты три audience,
cookie isolation, default-private route, Origin/CSRF, strict payload, principal
и capabilities, refresh rotation/replay, valid/uniform logout, logout-all и
отзыв одного устройства. Отдельная регрессия доказывает server-side revoke по
живой access-сессии даже при потерянной refresh-cookie; public allowlist
проверяется точной парой method/resource. Corrupt principal/access и
post-refresh corruption проверены service tests с обязательным session revoke.

### Реализованный authenticated realtime-инкремент — 27 июля 2026

- `apps/pwa_api/websocket_sessions.py` хранит process-local индексы
  audience/account/session, поддерживает несколько вкладок одной session и
  сериализует handshake/pong/error/invalidation/close одним transport lock;
- `apps/pwa_api/realtime_control.py` валидирует exact versioned
  `session|account` close event и обеспечивает local-first, best-effort NATS
  fan-out. Ошибка publish не меняет успешный logout/revoke и закрывается
  периодической authoritative revalidation;
- `apps/pwa_app.py` проверяет exact browser Origin и audience access-cookie до
  WebSocket upgrade, после каждого reconnect требует полный refetch, запускает
  bounded SQLite revalidation и останавливает registry до broker disconnect;
- logout/revoke/logout-all немедленно закрывают только доказанные targets.
  Refresh-only logout получает internal target лишь после constant-time
  current/consumed-secret proof; malformed, wrong-secret, foreign и already
  revoked cookies сохраняют uniform `204` и не образуют close-oracle;
- invalidation поддерживает глобальный, audience и authenticated account scope.
  `accountId` разрешён только вместе с audience, не копируется в browser event
  и не логируется; course/group/student owner mapping остаётся предметному
  service layer следующих фаз.
- [`packages/app-shell/src/realtime.tsx`](../../packages/app-shell/src/realtime.tsx)
  реализует общий production-клиент трёх приложений. Он открывает exact
  same-origin audience path только после authenticated state, не кладёт
  credential в URL/storage, валидирует каждый frame общим Zod-контрактом,
  поддерживает JSON ping/pong, bounded jittered backoff и останавливается при
  offline/hidden. Первый reconnect всегда передаёт только memory cursor,
  принимает только `resync-required` и не становится ready до полного refetch
  активных TanStack Query.
- Policy close и неоднозначный clean close перепроверяют `/auth/me`:
  подтверждённая сессия возвращается в bounded reconnect, authoritative
  revocation/expiry размонтирует private shell без reconnect storm, а
  transient network/5xx не маскируется как logout и повторяет authority check
  с bounded backoff. Такое поведение учитывает transport/proxy, который может
  нормализовать `1008` в `1000`, не ослабляя exact server-code проверки Python
  integration suite.
- `RealtimeProvider` подключён в production entry Student, Family и Staff.
  Чистая state-machine проверяется в
  [`realtime-client.test.ts`](../../packages/app-shell/src/realtime-client.test.ts),
  auth/StrictMode composition — в
  [`realtime-provider.test.tsx`](../../packages/app-shell/src/realtime-provider.test.tsx),
  реальный browser/aiohttp путь — в
  [`runtime-isolation.spec.ts`](../../e2e/runtime-isolation.spec.ts).

Focused gate покрывает missing/wrong Origin, missing/cross-audience/expired/
revoked cookie до upgrade, несколько вкладок и устройств, revoke/logout-all,
refresh-only logout и wrong-secret DoS regression, cross-worker control,
publish failure fallback, periodic out-of-band revoke, owner-only invalidation,
bounded concurrent send/close и secret-free logs. Полный
`.venv/bin/pytest -q pwa_tests` — 759 PASS / 1 intentional skip.

Frontend realtime gate 27 июля 2026 года: focused Vitest — **2 файла / 17
PASS**; `make pwa-e2e-realtime` — **12/12 PASS** в Chromium, WebKit и Firefox
после production build всех трёх приложений. Снимки не обновлялись; визуальных
изменений этот context-only provider не создаёт.

Race/resource hardening после этого исторического среза добавило pending
handshake, close-before-register tombstone, atomic initial cursor frame и
Argon2 resource envelope. Барьерные тесты не используют sleeps для вывода о
порядке и не сравнивают wall-clock. Актуальное доказательство:
[`phase1-auth-race-hardening.md`](../../../pwa_tests/reports/phase1-auth-race-hardening.md);
полный Python PWA suite — 808 PASS / 1 intentional skip.

Инкремент не закрывает Phase 1 целиком: следующий proxy increment ниже закрывает
код, actual aiohttp transport и structural nginx contract, но server
`nginx -t`/live burst, controlled production import и реальный browser E2E
login/revoke остаются обязательными gates.

### Реализованный production-proxy boundary — 27 июля 2026

- [`helpers/pwa/request_security.py`](../../../helpers/pwa/request_security.py)
  и aiohttp adapter принимают exact loopback CIDR либо exact canonical
  filesystem Unix `sockname`; `AF_UNIX` сам по себе не даёт доверия. Wrong
  socket/path, abstract/relative aliases, spoofed/mixed headers, неверные
  host/proto и chain length fail-closed;
- [`vmshpwa.conf.template`](../../deploy/nginx/vmshpwa.conf.template) разводит
  static/API/WebSocket всех трёх audiences, заменяет forwarding evidence,
  задаёт body/timeouts, WebSocket upgrade, per-IP login limit `6r/m` + burst 4,
  `429`/`Retry-After` и CSP с обязательными render markers;
- [`nginx_config_check.py`](../../scripts/nginx_config_check.py) возвращает
  success только после настоящего `nginx -t`; отсутствие binary/config или
  unresolved marker даёт explicit non-zero `UNAVAILABLE`. Exact production
  hostname не предполагается заранее: обязательный `VMSH_PWA_PUBLIC_HOST`
  должен быть lowercase FQDN и совпадать в обоих `server_name`, HTTPS redirect
  и CSP WebSocket origin.

Pure + actual aiohttp TCP/Unix/WS + structural suite — 106 PASS. На локальной
macOS машине nginx отсутствует: checker завершился `exit 2` с explicit
`UNAVAILABLE`, поэтому server-side `nginx -t` и живой burst/`429` smoke честно
остаются production deploy proof, а не объявлены пройденными unit-тестами.
Полный актуальный `.venv/bin/pytest -q -n0 pwa_tests` после proxy increment —
793 PASS / 1 intentional skip.

### Канонический import preflight — 27 июля 2026

[`auth-preflight.json`](../../../pwa_tests/reports/auth-preflight.json) теперь
исполняет настоящий version 1 `transliterated-surname-DD` helper, а не нижнюю
оценку до транслитерации. В выбранном legacy cohort `users.type = 1` найдено
1617 строк: 10 имеют field/token blocker, 29 групп канонических login collision
затрагивают 58 строк, 1549 строк готовы до явных collision overrides и
утверждения launch cohort. Ни login candidates, ни IDs, ни credentials в отчёт
не попадают. Source открыт через nofollow descriptor, десериализован в
query-only in-memory SQLite и повторно проверен на неизменность; исходный
`db/vmsh.db` не модифицируется. Focused suite: 10 PASS.

Это закрывает точный aggregate dry-run генератора, но не apply: перед controlled
activation ещё нужны сохранённые admin overrides для каждой collision,
утверждённые исключения test/unknown строк и отдельный transactional import
report.

### Controlled Student import tooling — 27 июля 2026

[`auth_import.py`](../../scripts/auth_import.py) реализует три явные операции
над отдельно подготовленной migrated copy под `.runtime/auth-import/`:
owner-only `inventory`, aggregate
`preview` и transactional `apply`. У команды нет default database; она
отказывается от authoritative `db/vmsh.db`, symlink/hardlink, permissive
decision/apply target, несовпадающего confirmation path и неактуальной схемы.
Quiescent copy с `-wal`/`-shm`/`-journal` также отклоняется.
Контракт требует полный `users.type = 1` cohort, явные exclusions и override для
каждой активной строки collision group. Реальные IDs и login candidates
допустимы только в mode-`0600` detail report под ignored
`.runtime/auth-import/`; aggregate
report их не содержит.

Inventory/preview не запускают Argon2. Apply заранее хеширует только pending
credentials, затем повторно валидирует весь план под `BEGIN IMMEDIATE` и
вставляет все accounts одной транзакцией. Повторный run с теми же решениями
проверяет Argon2 и возвращает `already-applied`; несовместимое частичное
состояние блокирует run. `users.public_id` и `auth_accounts.public_id`
назначаются независимо и случайно. Этот legacy controlled importer остаётся
rehearsal/compatibility path; target Staff batch дополнительно хранит
owner-only plaintext provisioning value согласно принятому v1-решению.

Точный runbook: [`phase-1-student-auth-import.md`](../../docs/phase-1-student-auth-import.md),
focused proof: [`phase1-auth-import-tooling.md`](../../../pwa_tests/reports/phase1-auth-import-tooling.md).
Настоящий production apply не выполнялся и без утверждённых owner decisions не
должен выполняться. Этот auth-инкремент не создаёт `course_enrollments`, access
или events: mapping legacy group/mode остаётся отдельным backfill, где no-op
`G`/`O` будут coalesced, а не превращены в выдуманную историю.

Focused suite — 16 PASS, включая изменение source между pre-hash preview и
`BEGIN IMMEDIATE`. Synthetic production-size preview (1617 rows) занимает
менее `1 s` и доказал ноль Argon2 calls; три default Argon2 hashes на текущей
машине заняли `0.098 s`, что даёт непереносимую линейную оценку около `0.8 min`
для 1549 pending rows до начала write transaction и ещё около `0.8 min` для
полной post-commit credential verification.

### Реализованный browser-auth инкремент — 27 июля 2026

- Все три production entry подключены к server-authoritative
  `AuthenticationProvider`; private shell не монтируется до `/auth/me`, а
  безопасный audience-relative `returnTo` сохраняет query и hash.
- Student, Family и Staff используют настоящие login routes и audience-specific
  payload (`telegramToken` только у Student, `password` у Family/Staff).
  Teacher получает UI `forbidden` на admin-only routes; Admin открывает их.
- [`auth-credentials-v1.json`](../../../pwa_tests/fixtures/auth-credentials-v1.json)
  — единый synthetic test-only источник персон для seed и Playwright. Он не
  импортируется product-кодом и не создаёт production mock-auth/backdoor.
- [`authentication.spec.ts`](../../e2e/authentication.spec.ts) работает через
  production Vite bundles, one-origin gateway `5380`, настоящий aiohttp `8380`
  и отдельную seeded SQLite без MSW, Telegram и Google. Проверены private deep
  links, Student/Family/Teacher/Admin login и reload, одинаковая ошибка неверных
  credentials, logout, три одновременные audience-сессии, cookie Path/isolation,
  `401`, точный Host/Origin/forwarding boundary, ротация обеих cookie при refresh
  и отзыв одного устройства без завершения второго. Дополнительно reload
  private route с удалённой access-cookie выполняет ровно один автоматический
  refresh, восстанавливает shell и выдаёт новую access-cookie.
- Single-use refresh cookie теперь координируется и между вкладками одного
  audience: Web Locks сериализует contenders, а лидер после получения lock
  повторно читает `/auth/me` и расходует refresh только при сохраняющемся
  `401`. Fallback без Web Locks использует BroadcastChannel/storage только как
  сигнал, никогда как mutex, и выполняет исключительно fail-closed `/auth/me`.
- Frontend считает `policy.sessionExpiresAt` абсолютной server-owned границей:
  таймер и проверки после browser resume размонтируют private shell и очищают
  memory state ровно по expiry. Ранее подтверждённая вкладка может остаться в
  явном `offline-unverified` состоянии только до этой границы; холодный offline
  start с durable cache остаётся отдельным offline-инкрементом.
- Реальный Family E2E обнаружил несовместимость с legacy SQLite affinity:
  `users.birthday` фактически хранит ISO date, а family projection пыталась
  выполнить `int()`. [`FamilyChildRecord`](../../../db_methods/pwa/auth.py)
  теперь сохраняет nullable строку; repository regression использует ISO date.
- Storybook interaction stories
  `pages-student--login-state-matrix`,
  `pages-family--login-state-matrix` и
  `pages-staff--login-state-matrix` покрывают invalid, rate-limited,
  account-unavailable, network/error, pending и reveal; Student отдельно
  показывает blocked state.

Пруф: `make pwa-e2e-auth` — **60/60 PASS** в Chromium, WebKit и Firefox,
включая две реальные вкладки и ровно один refresh request; focused
auth/session Vitest после cross-tab/expiry hardening — **31/31 PASS**;
Vitest — **16 файлов / 139 PASS**; Python PWA — **780 PASS / 1 intentional
skip**; Storybook browser mode с addon-a11y error — **32 файла / 143 PASS**;
`make pwa-lint`, `make pwa-typecheck` и production build трёх приложений — PASS.
Повторный полный gate текущего worktree после hardening: frontend unit **19
файлов / 162 PASS**, Python PWA **808 PASS / 1 intentional skip**, Storybook
browser mode **33 файла / 152 PASS**; full lint/typecheck — PASS.

Из browser gate честно отложен только прямой Teacher→admin **API** `403`: в
Phase 1 ещё нет настоящего capability-protected Staff admin product endpoint.
UI gate и permission/API matrix уже зелёные, но искусственный production probe
ради E2E не добавляется. Browser `403` становится обязательным тестом вместе с
первым реальным admin endpoint в Phase 2, 7, 8 или 10. Server `nginx -t`/live
rate-limit smoke и controlled production import также остаются отдельными
незакрытыми gates.

### Реализованный batch-инкремент — 3 августа 2026

- `migrations/0076.pwa_account_provisioning_batches.sql` добавляет owner-only
  provisioning plaintext и упорядоченные Family emails; rollback проверяется
  циклом up/down/up;
- `models/pwa/account_batches.py` содержит только нормализацию строк и выбор
  просмотренного `-NN`, а `db_methods/pwa/account_batches.py` — короткие
  механические SQLite-операции без продуктовых текстов и HTTP-состояний;
- `apps/pwa_api/account_batch_routes.py` реализует отдельные admin-only
  preview/apply для Student и Family. Preview не возвращает secret, apply
  повторно проверяет просмотренный input и создаёт готовые строки одной
  transaction;
- Student batch создаёт legacy `users` и связанный web-account, Family batch —
  web-account, emails и связи с уже созданными Student login. Course enrollment
  сюда намеренно не включён: это отдельный batch с ещё открытым правилом выбора
  active group.

Пруф: [`phase1-account-provisioning-batches-2026-08-03.md`](../../../pwa_tests/reports/phase1-account-provisioning-batches-2026-08-03.md).

## Frontend

- Реальные login routes уже существуют: `student/family/staff/src/routes/login.tsx`.
- `packages/contracts/src/auth.ts` и `app-shell/src/auth-boundary.tsx`.
- Login error, collision/import-disabled account, rate limit, expired session, blocked, offline, password visibility, contact `vmsh@179.ru`.
- Нет onboarding v1; после первого входа redirect к intended route или home.
- Session/device management реализован domain-neutral компонентами
  `AccountSessionManager`/`SessionManagementView` в
  `packages/app-shell/src/session-management.tsx` и подключён к Student/Family
  profile. Он читает настоящий audience-relative `GET /auth/sessions`, отличает
  текущее устройство, отзывает одну чужую сессию, выполняет current logout и
  logout-all только после подтверждения и fail-closed блокирует действия при
  пустом/повреждённом/cross-audience ответе. Staff пока не получает отдельный
  выдуманный profile route: account surface будет встроен в естественное место
  shell, когда оно появится.
- `SessionOfflineWorkGuard` — явная граница будущего account-scoped
  Dexie/outbox: ошибка inspect запрещает logout, непустая очередь меняет текст
  подтверждения, а cleanup callback запускается только после подтверждённого
  server logout и не теряется при размонтировании auth shell. Реальное durable
  подключение и account cleanup остаются этапом offline/outbox; текущий профиль
  не фабрикует состояние очереди.
- `AuthenticationProvider` координирует автоматический refresh между вкладками
  через Web Locks с authoritative `/auth/me` recheck и не использует
  `localStorage` как lock. Без Web Locks клиент не отправляет competing refresh.
  Абсолютный `sessionExpiresAt` проверяется таймером и при возврате браузера;
  expiry размонтирует private UI даже в ранее подтверждённом offline-состоянии.
- Forbidden route получает осмысленную страницу, но не раскрывает admin data.
- Staff `/staff/users?tab=imports` реализует два независимых пакетных шага:
  Student TSV preview/apply, затем Family TSV preview/apply. Черновик каждого
  шага привязан к Staff account/runtime namespace и хранится в `localStorage`
  до полного receipt; preview показывает только итоговые login и диагностику,
  но не password, Telegram token или email. Course enrollment остаётся
  отдельным пакетным действием.

## Tests

- Hash/sign/expiry/revoke/credential-version unit tests с замороженным временем вокруг 10 августа.
- API matrix: anonymous/Student/Family/Teacher/Admin × all audience bases.
- Cookie path/domain/SameSite/Secure/HttpOnly assertions; session fixation and rotation tests.
- Trusted-proxy/public-origin integration: direct и разрешённый proxy request,
  неверный Origin/Referer, а также spoofed `Forwarded`, `X-Forwarded-Host`,
  `X-Forwarded-Proto` и смешанные header chains; отдельно login CSRF без cookie,
  неожиданный TRACE, cross-site/missing-Origin WebSocket handshake и production
  nginx header replacement/order.
- Permission property/matrix tests: exact legacy user types, global Admin,
  scoped Teacher, Student/Family ownership, подмена student/course/group IDs,
  collection без scope-filtered query и malformed principal rows.
- Structural rate-limit/header test уже покрывает exact login map, per-IP key,
  `429` и conditional `Retry-After`; фактический burst выполняется отдельным
  server deploy smoke после успешного `nginx -t`.
- Account-level throttling: много IP → один login, один IP → много login, окно/сброс, конкурентные workers и отсутствие user enumeration.
- No token/password in logs, Sentry events, response or fixtures.
- Playwright: login/logout/reload/revoke separate device, intended route, `401`
  vs `403`, simultaneous audiences и две вкладки одного audience с single-use
  refresh coordination в Chromium, WebKit и Firefox.
- Fake-clock Vitest: already-expired context никогда не монтирует private UI;
  активная и prior-verified offline сессии размонтируются на абсолютной границе.
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

Проверенный implementation checkpoint зафиксирован revisions `1aad776`
(auth/session/permission/HTTP/WebSocket runtime и proxy boundary) и `866e3fe`
(три browser audience, auth/realtime providers и production-build browser
flows). Общий worktree gate 28 июля 2026: lint/typecheck/build PASS, 218
TypeScript и 1028 Python tests PASS (3 skip, 1 warning), Storybook browser mode
167 PASS. Это не закрывает production `nginx -t`/live rate smoke, owner-approved
controlled import и visual approval, перечисленные ниже.

- [ ] Revision и migration: `<sha/path>`; empty/upgrade/rollback results `<path>`.
- [ ] Auth decision record: cookie/session/expiry/revoke/CSRF details `<path>`.
- [ ] Import/preflight report: canonical preflight — `pwa_tests/reports/auth-preflight.{json,md}`; controlled tooling proof — `pwa_tests/reports/phase1-auth-import-tooling.md`; production owner decisions/apply ещё не выполнены.
- [ ] Demo: Student, Family, Teacher, Admin fixture logins без публикации паролей `<route/result>`.
- [ ] Permission matrix API test report: `<path/result>`.
- [ ] Cookie/security assertions и trusted-proxy/spoofed-forwarded matrix:
      pure + actual aiohttp TCP/Unix/WS + nginx structural `106 PASS`; локальный
      syntax checker `UNAVAILABLE (exit 2: nginx absent)`; server `nginx -t` и
      live rate-limit smoke `<result>`.
- [ ] Storybook login/session/forbidden states and visual approval: login
      matrices выше; session stories `product-account-sessions--loading`,
      `--current-device`, `--multiple-devices`, `--revoke-pending`,
      `--revoke-error`, `--empty-fails-closed`, `--corrupt-fails-closed`,
      `--logout-with-offline-queue-warning`, `--network-error` — automated
      interaction/a11y 9 PASS; owner visual approval ещё не получен.
- [x] Playwright 3 browsers: `make pwa-e2e-auth` — 60/60 PASS, включая
      two-tab/single-refresh recovery.
- [ ] Telegram historical auth tests: `<result or N/A reason>`.
- [ ] Docs/runbook updated: `<paths>`.
- [ ] Known limitations/issues and acceptance: `<links/name/date>`.

Account provisioning checkpoint: backend proof
[`phase1-account-provisioning-batches-2026-08-03.md`](../../../pwa_tests/reports/phase1-account-provisioning-batches-2026-08-03.md),
Staff UI proof
[`phase1-account-provisioning-staff-ui-2026-08-03.md`](../../../pwa_tests/reports/phase1-account-provisioning-staff-ui-2026-08-03.md).

## Многокурсовый инкремент Phase 1

Создать course enrollment/access/event и Staff scope migrations/contracts. Student session получает доступ к нескольким курсам, но active group и mode меняются только внутри одного enrollment. Teacher scope допускает весь курс либо отдельные группы; прямой запрос вне scope возвращает `403`.

Дополнительный proof: backfill «Математика 5–7», один active + несколько allowed groups, per-course mode history, revoked-access history visibility, course/group permission matrix и Storybook `Product/Courses--student-multiple-courses`, `--active-and-allowed-groups`, `Pages/Staff--teacher-forbidden`.
