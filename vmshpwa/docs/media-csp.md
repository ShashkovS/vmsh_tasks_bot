# CSP изображений в service worker — 16 сентября 2026

## Причина

Production разрешал S3 в `img-src` и `media-src`, но не в `connect-src`.
Student/Family Workbox выполняет fetch изображения из worker, который получает
собственную CSP в ответе на `/student/sw.js` или `/family/sw.js`. Поэтому
разрешения только img-src недостаточно: запрос блокируется до получения S3.
Проверенный SVG отвечает 200. Ошибка браузера — CSP, не доказательство сбоя CORS.

## Исправление

В [nginx template](../deploy/nginx/vmshpwa.conf.template) точный
`@@CSP_MEDIA_ORIGIN@@` добавлен в connect-src. Wildcard и отключение CSP не нужны.
[nginx_config_check.py](../scripts/nginx_config_check.py) отвергает политики,
в которых явно разрешённый HTTPS image origin отсутствует в connect-src.
27 тестов [test_nginx_proxy_config.py](../../pwa_tests/test_nginx_proxy_config.py)
прошли, включая воспроизведение отсутствующего разрешения.

Действующий production-конфиг прочитан отдельно, не заменяется шаблоном:
подготовлена копия с изменением только двух connect-src в CSP map.
Для применения нужны `nginx -t` и reload от root. У SSH-агента нет sudo.

После reload требуется новый worker: одной смены HTTP-заголовков недостаточно
для гарантированного обновления уже установленного worker с прежней CSP.
Комментарии в обоих sw.ts фиксируют контракт и включают frontend build в выпуск;
production build с новым releaseId изменяет precache manifest/байты worker.
Проверить различие SHA256 обоих sw.js после выпуска. Используется обычное
обновление PWA, без удаления IndexedDB, черновиков, очередей и forced skipWaiting.

## Проверка production

До исправления: оба sw.js содержат CSP без S3 в connect-src; указанный SVG — 200.
После root reload: проверить CSP HTML и обоих sw.js, service-status и три runtime.
После frontend release: проверить новые worker bytes и загрузку рисунков после
обычного обновления PWA. Фактический результат фиксируется при завершении выпуска.
