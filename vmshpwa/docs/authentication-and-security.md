# Аутентификация и безопасность

Документ описывает целевую модель. В Phase 1 уже реализован HTTP-контур входа,
refresh/logout, чтения principal и управления сессиями для Student, Family и
Staff поверх общих SQLite-таблиц. Authenticated WebSocket lifecycle также
реализован. Production rollout ещё не принят: остаются server-side `nginx -t`/
live rate-limit smoke, controlled account activation и browser E2E. Подробное решение и актуальные
первичные источники:
[`ADR 0003`](../../adr/0003-pwa-authentication-cryptography-and-sessions.md).

## Учётные записи и сессии

Школьник входит по заданному при пакетной загрузке login и текущему
Telegram-токену как password. Student batch содержит фамилию, имя, optional
отчество, optional дату рождения, optional класс, login и password. Дубликаты
login получают предложенный случайный suffix `-NN`, а итоговый набор проходит
preview. Синтетические `qwerty*` accounts разрешены для летнего тестирования и
удаляются до реального набора.

Family accounts создаются отдельным batch: имя, заданные login/password,
comma-separated emails и список login детей. Связи с детьми many-to-many, один
Family account показывает всех связанных детей. Каждый ребёнок использует свой
Student account; переключатель между несколькими Student accounts в одном
browser не входит в v1. Login/password обеих аудиторий в v1 рассылаются
внешними email-скриптами.

Внешняя идентичность человека отделена от учётной записи: nullable
`users.public_id` становится стабильным browser `userId`/`studentId` только
при controlled activation, тогда как `auth_accounts.public_id` является
`accountId`. Оба значения opaque и не раскрывают legacy integer `users.id`.
API не подставляет один ID вместо другого: связанный Student/Staff без
`users.public_id` считается неактивированным и получает fail-closed отказ.

Web authentication сверяет Argon2id verifier. Production использует актуальные defaults
`argon2-cffi`; после успешного входа устаревшие параметры автоматически
перехешируются. До дорогостоящей проверки encoding проходит fail-closed
resource policy: версии 16/19, не более 256 MiB памяти, `time_cost <= 10`,
`parallelism <= 16`, а также bounded encoding/salt/hash. Текущие defaults и
допустимые старые hashes остаются внутри этого заведомо широкого envelope и
после входа обновляются; синтаксически корректная, но чрезмерно дорогая запись
никогда не передаётся Argon2 verifier. Malformed/out-of-policy hash активной
строки вместо быстрого parse failure выполняет ровно одну проверку
startup-precomputed dummy hash — как неизвестный login — и всё равно не может
авторизоваться. Student token проходит ту же trim/homoglyph normalization, что
и исторический Telegram-бот. По явному owner decision v1 также хранит исходные
Student/Family passwords для внешнего provisioning mailer. Эта owner-only
plaintext-копия не является session storage, не возвращается в обычных browser
API и не попадает в logs, Sentry, fixtures или committed reports.

Controlled Student activation реализована отдельным fail-closed инструментом и
runbook: [`phase-1-student-auth-import.md`](phase-1-student-auth-import.md).
`inventory`/`preview` не выполняют Argon2, требуют explicit launch cohort,
exclusions и overrides, а `apply` работает только с явно подтверждённой
migrated disposable copy одной транзакцией. Реальные row-level решения живут
только в owner-only `.runtime` report; committed proof остаётся агрегатным.
Course enrollment/access/event backfill этим инструментом сознательно не
выполняется.

Исторические credential-like значения, однажды закоммиченные как DML migration
`0038`, по решению владельца не используются для PWA activation, fixtures или
отчётов; очистка Git history и ротация только из-за этой migration не входят в
текущий этап. Это не делает значения публичными или пригодными для повторного
использования: controlled import берёт актуальную запись пользователя, а новые
migrations не содержат credential rows.

Legacy classroom `IDd` и штрихкод кодируют numeric `users.id`, а не Student
Telegram token. Такой ID сам по себе не credential и не вызывает ротацию.
Несмотря на это, browser contract получает отдельный opaque `users.public_id`:
внутренний ID остаётся server-side implementation detail и не даёт клиенту путь
к чтению token из БД.

Сессия использует две HttpOnly cookie на audience: короткую подписанную `itsdangerous` access cookie и ротируемую refresh cookie. SQLite хранит HMAC-digest refresh secret, но не raw secret и не hash введённого credential в session row, поэтому отдельное устройство можно отозвать без отдельного auth service.

| Audience | Access cookie         | Refresh cookie         | Path       |
| -------- | --------------------- | ---------------------- | ---------- |
| Student  | `vmsh_student_access` | `vmsh_student_refresh` | `/student` |
| Family   | `vmsh_family_access`  | `vmsh_family_refresh`  | `/family`  |
| Staff    | `vmsh_staff_access`   | `vmsh_staff_refresh`   | `/staff`   |

Production attributes: `Secure`, `HttpOnly`, `SameSite=Lax`, узкий `Path`, без токена в URL или localStorage. Student, Family и Staff refresh sessions истекают в ближайшее 10 августа 00:00 по Москве, access cookie живёт 15 минут. Конкретный `expiresAt` вычисляет server. При ротации прежний HMAC хранится в bounded consumed-history только до срока этой сессии: совпадение доказывает replay и отзывает lineage, а произвольный неверный secret даёт общий отказ без удалённого отзыва. Блокировка, сброс Telegram-токена, смена критичных прав и ручной отзыв мягко отзывают session раньше; строка и secret-free audit остаются для списка устройств и расследования.

Browser не продлевает абсолютный срок локально. [`AuthenticationProvider`](../packages/app-shell/src/auth-context.tsx)
проверяет server-owned `policy.sessionExpiresAt`, ставит таймер до этого момента
и повторяет проверку после `focus`, `pageshow` и `visibilitychange`. В момент
истечения private shell размонтируется и account-owned query state очищается
даже без сети. После успешно подтверждённой в этой вкладке сессии временная
ошибка refetch допускает явное состояние `offline-unverified` только до того же
срока; холодный offline start без сохранённого account-scoped контекста
по-прежнему fail-closed.

Одна refresh cookie разделяется вкладками одного audience и является
single-use. [`auth-refresh-coordinator.ts`](../packages/app-shell/src/auth-refresh-coordinator.ts)
использует same-origin [Web Locks](https://www.w3.org/TR/web-locks/) с отдельным
именем на audience. Получив exclusive lock, вкладка сначала повторяет
authoritative `/auth/me` и вызывает `/auth/refresh` только если access cookie
всё ещё даёт `401`; ожидавшие вкладки поэтому используют уже ротированные
cookie. `BroadcastChannel` и безличный timestamp в `localStorage` служат только
сигналом завершения и никогда не считаются mutex/lease. Если Web Locks
недоступны, fallback ждёт ограниченное время, делает только `/auth/me` и
fail-closed не расходует refresh secret. Ни identity, ни session ID, ни token в
Web Storage не записываются.

Текущая HTTP-реализация находится в
[`apps/pwa_api/auth_routes.py`](../../apps/pwa_api/auth_routes.py),
[`apps/pwa_api/middleware.py`](../../apps/pwa_api/middleware.py) и
[`apps/pwa_api/auth_service.py`](../../apps/pwa_api/auth_service.py). Любой
зарегистрированный `/{audience}/api/v1/*` route по умолчанию private; public
allowlist ограничен `health`, `runtime`, `login`, `refresh` и идемпотентным
`logout`; allowlist сопоставляет точные пары HTTP method/resource. Logout
отзывает authenticated access-сессию даже при отсутствующей refresh-cookie, а
refresh credential остаётся fallback для истёкшего access. Unsafe запросы
проходят exact-origin/proxy boundary до выполнения route, а каждый access cookie
повторно сверяется с authoritative SQLite session.
HTTP tests с настоящим aiohttp и отдельной migrated SQLite лежат в
[`pwa_tests/integration/test_auth_http_api.py`](../../pwa_tests/integration/test_auth_http_api.py).

## Обязательные механизмы

- rate limit nginx по IP плюс backend throttling по normalized login/account с безопасным сообщением и timing без user enumeration;
- журнал устройств: создание, последнее использование, приблизительное устройство, отзыв одной или всех сессий;
- Student/Family profile использует общий `AccountSessionManager`: session ID
  остаётся непрозрачным mutation key и не показывается вместо имени устройства;
  current logout, revoke другого устройства и logout-all подтверждаются
  отдельно. Пустой, противоречивый или cross-audience список блокирует все
  session actions. Отдельный Staff profile route ради этой функции не создаётся;
- CSRF baseline: `SameSite=Lax`, строгая проверка same-origin `Origin` (с `Referer` только как fallback), Fetch Metadata и ожидаемого content type. Проверка обязательна для любого unsafe browser request, включая login до появления cookie; safe-набор ограничен `GET`, `HEAD`, `OPTIONS`. Отдельный synchronizer token пока не вводится;
- capability checks в backend на каждом объекте; скрытие кнопки не является авторизацией;
- обязательный secret-free login audit в `auth_events` и история group/mode (`user_changes_log`); legacy `signons.token` для PWA не используется, потому что пишет credential в журнал; отдельный лог самого факта чтения чужой работы не нужен;
- ограничение типов/размеров uploads, декодирование и re-encoding изображений, quarantine/scan при необходимости;
- public GET длинных непредсказуемых attachment URLs; upload всегда идёт через авторизованный aiohttp, а URL не должен попадать в public logs;
- redaction секретов, токенов и содержимого работ из operational logs.

## CSP

CSP обязательна с первого production deployment. Production hostname пока не
выбран и передаётся обязательным exact lowercase FQDN через
`VMSH_PWA_PUBLIC_HOST`; checker сверяет его с обоими `server_name`, HTTPS
redirect и WebSocket origin. Базовая policy уже закреплена в
[`vmshpwa.conf.template`](../deploy/nginx/vmshpwa.conf.template):
`default-src 'none'`, собственные scripts/fonts, exact same-origin API/WebSocket,
явные render-time Hetzner/Sentry origins, запрет framing/object/base injection и
`unsafe-eval`. Единственная начальная inline-уступка — `style-src
'unsafe-inline'` для фактически используемых style attributes; она описана и
должна быть сужена после их инвентаризации. Неразрешённый `@@...@@` marker
считается ошибкой deployment. API также возвращает `nosniff`, безопасный
referrer policy и запрет framing.

## Mock/prototype

Mock auth допустим только в test wiring и никогда не компилируется как production bypass. Новые unit/E2E не обращаются к Telegram или Google. Contract fixtures не содержат настоящих токенов и персональных данных.

Доступ ученика к course/group resource проверяется через активный `course_enrollment` и исторические интервалы `course_group_access`. Отзыв доступа закрывает новые материалы, но не собственные старые работы. Staff использует `staff_scopes`: курс целиком либо перечисленные группы. Только точные legacy-типы `TEACHER` и `ADMIN` образуют Staff principal; отрицательные архивные типы и составные bitmask-значения отклоняются. Только legacy admin имеет глобальные права: локальная роль scope не повышает teacher до global admin.

Любой прямой запрос вне scope получает `403`; UI hiding не считается защитой. Course/group/student IDs из URL, body и WebSocket payload не доказывают связь между объектами. Для Student/Family ownership объединяется с загруженным enrollment. Для Staff service сначала загружает целевой resource/membership из SQLite и проверяет его фактические course/group; нельзя совместить произвольный `studentId` с разрешённым `groupId`. Collection endpoint обязан выполнять scope-filtered query и не может пройти только по capability без course context.

Forwarding headers принимаются только от явно доверенной цепочки точной длины.
Production proxy удаляет входные forwarding headers и создаёт один `Forwarded`
из настоящего `$remote_addr`, фиксированного HTTPS и `$host`; клиентский
`Forwarded`/`X-Forwarded-*` никогда не добавляется к нему. Реализация находится
в [`vmshpwa-proxy-headers.conf`](../deploy/nginx/vmshpwa-proxy-headers.conf), а
чистая проверка — в
[`helpers/pwa/request_security.py`](../../helpers/pwa/request_security.py).

Immediate hop может быть exact loopback CIDR либо exact canonical Unix socket
path. Для Unix aiohttp adapter проверяет `AF_UNIX` и server-side `sockname`
против `VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON`; любой другой/relative/
abstract path отклоняется. Файловый socket размещается в dedicated directory с
mode `0750`, сам socket — `0660`. Это не создаёт общего доверия ко всем local
processes. Один exact hop и external host/proto проверяются и при Unix, и при
TCP. Реальные transport tests:
[`test_proxy_transport_boundary.py`](../../pwa_tests/integration/test_proxy_transport_boundary.py).

WebSocket handshake формально использует `GET`, но является
cookie-authenticated browser channel и потому всегда требует точного
allowlisted `Origin` до upgrade. После upgrade соединение сначала
регистрируется как pending: close-команды уже находят его, но обычный fan-out
ещё нет. Registry хранит process-local tombstone для session-close, поэтому
отзыв между первичной auth-проверкой и регистрацией не теряется; после
регистрации сессия ещё раз authoritative проверяется в SQLite. Только затем
под per-audience cursor/broadcast lock отправляется первый
`connected|resync-required` frame и socket становится routable. Поэтому
invalidation не может прийти раньше handshake или потеряться на том же cursor.
Соединение связывается с session ID без его выдачи клиентским сообщениям;
logout/revoke закрывает соответствующие sockets, а длительное соединение
периодически перепроверяет состояние сессии. Один успешный handshake не даёт
бессрочных прав.

## Доверенный checker

`cor_ans_checker` остаётся редактируемым только для доверенного admin и совместимым с текущим `exec`. UI обязан показывать предупреждение, diff, автора, время, возможность отката и, когда они добавлены, сохранённые test cases. Наличие test cases желательно, но не блокирует публикацию: ответ для ещё не настроенного checker принимается без автоматического verdict и позже проходит admin-перепроверку. Это выполнение доверенного кода, а не sandbox для недоверенного ввода; endpoint недоступен teacher и не принимает изменения без повторного подтверждения.
