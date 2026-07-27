# Аутентификация и безопасность

Документ описывает целевую модель; production login endpoints в каркасе отсутствуют.

## Учётные записи и сессии

Школьник входит по логину вида `transliterated-surname-birth-day` и текущему Telegram-токену. Версионированный import проверяет уникальность сгенерированного login и требует admin-разрешения коллизии. `NULL`/невалидная дата рождения, пустая фамилия и явно guessable legacy token попадают в preflight и не превращаются в активный web account молча; исключительная policy фиксируется как `AUTH-01` в фазовом плане. Family account хранит минимальное имя без email; связи с детьми many-to-many. Если один человек является parent и teacher, он использует разные logins/audience sessions. Первичная выдача и восстановление Family/Staff доступа выполняются через администраторов по `vmsh@179.ru`.

Сессия использует две HttpOnly cookie на audience: короткую подписанную `itsdangerous` access cookie и ротируемую refresh cookie. Refresh session и hash raw token хранятся в SQLite, поэтому отдельное устройство можно отозвать без отдельного auth service.

| Audience | Access cookie         | Refresh cookie         | Path       |
| -------- | --------------------- | ---------------------- | ---------- |
| Student  | `vmsh_student_access` | `vmsh_student_refresh` | `/student` |
| Family   | `vmsh_family_access`  | `vmsh_family_refresh`  | `/family`  |
| Staff    | `vmsh_staff_access`   | `vmsh_staff_refresh`   | `/staff`   |

Production attributes: `Secure`, `HttpOnly`, `SameSite=Lax`, узкий `Path`, без токена в URL или localStorage. Student, Family и Staff refresh sessions истекают в ближайшее 10 августа, access cookie — существенно раньше. Конкретный `expiresAt` вычисляет server. Блокировка, сброс Telegram-токена, смена критичных прав и ручной отзыв завершают session раньше.

## Обязательные механизмы

- rate limit nginx по IP плюс backend throttling по normalized login/account с безопасным сообщением и timing без user enumeration;
- журнал устройств: создание, последнее использование, приблизительное устройство, отзыв одной или всех сессий;
- CSRF baseline: `SameSite=Lax`, строгая проверка same-origin `Origin`/Fetch Metadata и ожидаемого content type. Отдельный synchronizer token пока не вводится;
- capability checks в backend на каждом объекте; скрытие кнопки не является авторизацией;
- обязательный совместимый login audit (`signons`) и история group/mode (`user_changes_log`); дополнительные domain revisions/provenance не заменяют эти записи; отдельный лог самого факта чтения чужой работы не нужен;
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
