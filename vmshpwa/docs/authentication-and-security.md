# Аутентификация и безопасность

Документ описывает целевую модель. Phase 1 начат с чистых правил identity,
Argon2id и signed/opaque token primitives; production login endpoints пока не
считаются готовыми. Подробное решение и актуальные первичные источники:
[`ADR 0003`](../../adr/0003-pwa-authentication-cryptography-and-sessions.md).

## Учётные записи и сессии

Школьник входит по логину вида `transliterated-surname-DD` и текущему Telegram-токену. Алгоритм v1 использует замороженную локальную транслитерацию и двузначный день месяца; коллизия блокирует import до явного сохранённого admin override, а не получает нестабильный suffix из row ID. Версионированный import проверяет уникальность сгенерированного login. `NULL`/невалидная дата рождения, пустая фамилия и явно guessable legacy token попадают в preflight и не превращаются в активный web account молча; исключительная policy фиксируется как `AUTH-01` в фазовом плане. Family account хранит минимальное имя без email; связи с детьми many-to-many. Если один человек является parent и teacher, он использует разные logins/audience sessions. Первичная выдача и восстановление Family/Staff доступа выполняются через администраторов по `vmsh@179.ru`.

Внешняя идентичность человека отделена от учётной записи: nullable
`users.public_id` становится стабильным browser `userId`/`studentId` только
при controlled activation, тогда как `auth_accounts.public_id` является
`accountId`. Оба значения opaque и не раскрывают legacy integer `users.id`.
API не подставляет один ID вместо другого: связанный Student/Staff без
`users.public_id` считается неактивированным и получает fail-closed отказ.

Все credential hashes — Argon2id. Production использует актуальные defaults
`argon2-cffi`; после успешного входа устаревшие параметры автоматически
перехешируются. Student token проходит ту же trim/homoglyph normalization, что
и исторический Telegram-бот, но не копируется в ещё одно plaintext-поле.

Сессия использует две HttpOnly cookie на audience: короткую подписанную `itsdangerous` access cookie и ротируемую refresh cookie. SQLite хранит HMAC-digest refresh secret, но не raw secret и не hash введённого credential в session row, поэтому отдельное устройство можно отозвать без отдельного auth service.

| Audience | Access cookie         | Refresh cookie         | Path       |
| -------- | --------------------- | ---------------------- | ---------- |
| Student  | `vmsh_student_access` | `vmsh_student_refresh` | `/student` |
| Family   | `vmsh_family_access`  | `vmsh_family_refresh`  | `/family`  |
| Staff    | `vmsh_staff_access`   | `vmsh_staff_refresh`   | `/staff`   |

Production attributes: `Secure`, `HttpOnly`, `SameSite=Lax`, узкий `Path`, без токена в URL или localStorage. Student, Family и Staff refresh sessions истекают в ближайшее 10 августа 00:00 по Москве, access cookie живёт 15 минут. Конкретный `expiresAt` вычисляет server. При ротации прежний HMAC хранится в bounded consumed-history только до срока этой сессии: совпадение доказывает replay и отзывает lineage, а произвольный неверный secret даёт общий отказ без удалённого отзыва. Блокировка, сброс Telegram-токена, смена критичных прав и ручной отзыв мягко отзывают session раньше; строка и secret-free audit остаются для списка устройств и расследования.

## Обязательные механизмы

- rate limit nginx по IP плюс backend throttling по normalized login/account с безопасным сообщением и timing без user enumeration;
- журнал устройств: создание, последнее использование, приблизительное устройство, отзыв одной или всех сессий;
- CSRF baseline: `SameSite=Lax`, строгая проверка same-origin `Origin`/Fetch Metadata и ожидаемого content type. Отдельный synchronizer token пока не вводится;
- capability checks в backend на каждом объекте; скрытие кнопки не является авторизацией;
- обязательный secret-free login audit в `auth_events` и история group/mode (`user_changes_log`); legacy `signons.token` для PWA не используется, потому что пишет credential в журнал; отдельный лог самого факта чтения чужой работы не нужен;
- ограничение типов/размеров uploads, декодирование и re-encoding изображений, quarantine/scan при необходимости;
- public GET длинных непредсказуемых attachment URLs; upload всегда идёт через авторизованный aiohttp, а URL не должен попадать в public logs;
- redaction секретов, токенов и содержимого работ из operational logs.

## CSP

CSP обязательна с первого production deployment. Конкретная nginx policy задаётся после фиксации hostnames и включает только собственные scripts/styles/fonts, audience API/WebSocket, настроенный production media origin (целевой Hetzner), Web Push и Sentry ingest. `unsafe-eval` запрещён; inline allowances нельзя добавлять без причины и теста. API также возвращает `nosniff`, безопасный referrer policy и запрет framing.

## Mock/prototype

Mock auth допустим только в test wiring и никогда не компилируется как production bypass. Новые unit/E2E не обращаются к Telegram или Google. Contract fixtures не содержат настоящих токенов и персональных данных.

Доступ ученика к course/group resource проверяется через активный `course_enrollment` и исторические интервалы `course_group_access`. Отзыв доступа закрывает новые материалы, но не собственные старые работы. Staff использует `staff_scopes`: курс целиком либо перечисленные группы. Любой прямой запрос вне scope получает `403`; UI hiding не считается защитой. Course/group IDs в URL и WebSocket payload не заменяют object-level authorization.

## Доверенный checker

`cor_ans_checker` остаётся редактируемым только для доверенного admin и совместимым с текущим `exec`. UI обязан показывать предупреждение, diff, автора, время, возможность отката и, когда они добавлены, сохранённые test cases. Наличие test cases желательно, но не блокирует публикацию: ответ для ещё не настроенного checker принимается без автоматического verdict и позже проходит admin-перепроверку. Это выполнение доверенного кода, а не sandbox для недоверенного ввода; endpoint недоступен teacher и не принимает изменения без повторного подтверждения.
