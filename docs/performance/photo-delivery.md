# Прямая выдача фотографий письменных решений

Решение пользователя, 27 сентября 2026: подпись GET действует 24 часа (86400 с).

`apps/pwa_api/written_submission_routes.py` сохраняет стабильные student,
family и staff `mediaPath`. После существующей проверки доступа общий
`_attachment_media_response` возвращает 302 на signed S3 GET с `no-store`.
Backend больше не скачивает объект и не пересчитывает хеш. Повторная загрузка
страницы обращается к стабильному пути и получает новую подпись: через 30 минут
или на следующий день фото продолжает открываться при действующем доступе.
Уже выданный URL действителен до истечения 24 часов; права повторно проверяются
при получении нового URL. Истёкшая внешняя ссылка сама не обновляется.

`helpers/object_storage.py:S3ObjectStorage.signed_read_url` использует локальную
SigV4-подпись SDK, runtime prefix и настроенный endpoint. Дополнительный GET/HEAD
к бакету не выполняется. Filesystem/test adapters без SignedReadStorage сохраняют
выдачу байтов. Upload validation, преобразование WebP и ключи объектов не меняются.
Контракт JSON и UI не меняются: существующие `<img src=mediaPath>` следуют 302.

Проверки: `pwa_tests/test_object_storage.py` использует настоящий signer с
синтетическими credentials, проверяет 86400, host/key и подпись;
`pwa_tests/integration/test_content_http_api.py` проверяет отсутствие storage.get,
401 до подписи и повторное получение URL без кеширования redirect.

При выпуске CSP img-src должен включать реальный подписанный S3 origin
(bucket.endpoint), а не только CDN public_base_url. Текущий шаблон
`vmshpwa/deploy/nginx/vmshpwa.conf.template` уже содержит CSP_MEDIA_ORIGIN.
Обычный `<img>` и SVG-аннотации не требуют CORS. Для fetch/canvas/offline download
нужен CORS разрешённого origin, что проверяется отдельно при изменении этих путей.
Прямая выдача реализована для письменных фото; текстовые комментарии остаются в API.

Проверено 27.09: 32 теста S3/written HTTP прошли; `git diff --check` прошёл.
Действующий production nginx уже разрешает Beget bucket origin в img-src и
connect-src. Live S3-загрузка и браузерный production smoke после выпуска
в этой задаче не выполнялись; требуется обычный backend release.
