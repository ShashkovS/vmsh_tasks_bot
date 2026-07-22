# Аутентификация и безопасность

Документ описывает целевую модель; production login endpoints в каркасе отсутствуют.

## Учётные записи и сессии

Школьник входит по логину и текущему Telegram-токену, используемому как пароль. Это переходная совместимость, а не Telegram OAuth. Родитель получает отдельную учётную запись без обязательной связи с Telegram. Teacher/Admin используют Staff identity и RBAC; teacher ограничен разрешёнными группами, admin получает дополнительные capabilities.

Сессия хранится только в opaque HttpOnly cookie:

| Audience | Cookie                 | Path       |
| -------- | ---------------------- | ---------- |
| Student  | `vmsh_student_session` | `/student` |
| Family   | `vmsh_family_session`  | `/family`  |
| Staff    | `vmsh_staff_session`   | `/staff`   |

Production attributes: `Secure`, `HttpOnly`, `SameSite=Lax`, узкий `Path`, без токена в URL или localStorage. Сессия истекает в ближайшее 10 августа. Блокировка пользователя, сброс токена, смена критичных прав и ручной отзыв завершают её раньше.

## Обязательные механизмы

- rate limit по login/IP/device signal с нарастающей задержкой и безопасным сообщением без user enumeration;
- журнал устройств: создание, последнее использование, приблизительное устройство, отзыв одной или всех сессий;
- CSRF-защита state-changing запросов через проверку Origin и отдельный токен/двойную отправку там, где SameSite недостаточно;
- capability checks в backend на каждом объекте; скрытие кнопки не является авторизацией;
- audit для входа, неудачных попыток, отзыва, смены ролей, публикации, массовой рассылки и trusted checker edit;
- ограничение типов/размеров uploads, декодирование и re-encoding изображений, quarantine/scan при необходимости;
- short-lived signed URLs или авторизованная выдача private media;
- redaction секретов, токенов и содержимого работ из operational logs.

## Mock/prototype

Mock auth допустим только в test wiring и никогда не компилируется как production bypass. Новые unit/E2E не обращаются к Telegram или Google. Contract fixtures не содержат настоящих токенов и персональных данных.

## Доверенный checker

`cor_ans_checker` остаётся редактируемым только для доверенного admin и совместимым с текущим `exec`. UI обязан показывать предупреждение, diff, автора, время, test cases и возможность отката. Это выполнение доверенного кода, а не sandbox для недоверенного ввода; endpoint недоступен teacher и не принимает изменения без повторного подтверждения.
