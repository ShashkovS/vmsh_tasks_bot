# Аутентификация и безопасность

Документ описывает целевую модель; production login endpoints в каркасе отсутствуют.

## Учётные записи и сессии

Школьник входит по логину и текущему Telegram-токену, используемому как пароль. Это финальная совместимая модель, а не Telegram OAuth. При пакетном импорте учеников Staff UI создаёт отдельный Family account и явную связь с ребёнком. Teacher/Admin используют Staff identity и RBAC; teacher ограничен разрешёнными группами, admin получает дополнительные capabilities.

Сессия использует две HttpOnly cookie на audience: короткую подписанную `itsdangerous` access cookie и ротируемую refresh cookie. Refresh session и hash raw token хранятся в SQLite, поэтому отдельное устройство можно отозвать без отдельного auth service.

| Audience | Access cookie         | Refresh cookie         | Path       |
| -------- | --------------------- | ---------------------- | ---------- |
| Student  | `vmsh_student_access` | `vmsh_student_refresh` | `/student` |
| Family   | `vmsh_family_access`  | `vmsh_family_refresh`  | `/family`  |
| Staff    | `vmsh_staff_access`   | `vmsh_staff_refresh`   | `/staff`   |

Production attributes: `Secure`, `HttpOnly`, `SameSite=Lax`, узкий `Path`, без токена в URL или localStorage. Refresh session истекает в ближайшее 10 августа, access cookie — существенно раньше. Блокировка пользователя, сброс Telegram-токена, смена критичных прав и ручной отзыв завершают её раньше.

## Обязательные механизмы

- rate limit nginx как минимум по login/auth и IP с безопасным сообщением без user enumeration;
- журнал устройств: создание, последнее использование, приблизительное устройство, отзыв одной или всех сессий;
- CSRF baseline: `SameSite=Lax`, строгая проверка same-origin `Origin`/Fetch Metadata и ожидаемого content type. Отдельный synchronizer token пока не вводится;
- capability checks в backend на каждом объекте; скрытие кнопки не является авторизацией;
- audit для входа, неудачных попыток, отзыва, смены ролей, публикации, массовой рассылки и trusted checker edit; отдельный лог самого факта чтения чужой работы не нужен;
- ограничение типов/размеров uploads, декодирование и re-encoding изображений, quarantine/scan при необходимости;
- public GET длинных непредсказуемых attachment URLs; upload всегда идёт через авторизованный aiohttp, а URL не должен попадать в public logs;
- redaction секретов, токенов и содержимого работ из operational logs.

## CSP

CSP обязательна с первого production deployment. Конкретная nginx policy задаётся после фиксации hostnames и включает только собственные scripts/styles/fonts, audience API/WebSocket, Hetzner media origin, Web Push и Sentry ingest. `unsafe-eval` запрещён; inline allowances нельзя добавлять без причины и теста. API также возвращает `nosniff`, безопасный referrer policy и запрет framing.

## Mock/prototype

Mock auth допустим только в test wiring и никогда не компилируется как production bypass. Новые unit/E2E не обращаются к Telegram или Google. Contract fixtures не содержат настоящих токенов и персональных данных.

## Доверенный checker

`cor_ans_checker` остаётся редактируемым только для доверенного admin и совместимым с текущим `exec`. UI обязан показывать предупреждение, diff, автора, время, test cases и возможность отката. Это выполнение доверенного кода, а не sandbox для недоверенного ввода; endpoint недоступен teacher и не принимает изменения без повторного подтверждения.
