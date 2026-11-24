# Подключение портала

**ВМШ.** В настройках приложений ChatGPT создайте подключение «ВМШ — Администрирование занятий».
Адрес сервера — `https://vmsh.shashkovs.ru/staff/api/admin/v1/mcp`. Выберите OAuth, используйте ID клиента ВМШ, войдите в Staff ВМШ и подтвердите делегирование. Проверьте поле portal в `get_my_access`.

**Prep.** Создайте отдельное подключение «Prep — Администрирование занятий».
Адрес — `https://prep.leaders.tech/staff/api/admin/v1/mcp`. Используйте ID клиента Prep и Staff-аккаунт Prep. Проверьте, что portal равен `https://prep.leaders.tech`.

При установке задайте на каждом портале `VMSH_ADMIN_MCP_CLIENT_ID` и
`VMSH_ADMIN_MCP_REDIRECT_URI` равным регистрации клиента и точному callback,
показанному в ChatGPT. Для публичного клиента используется PKCE S256.
Прокси должен передавать на aiohttp пути под `/staff/api/admin/v1/`, включая OAuth,
и обе discovery-записи. Установите миграцию и выполните `make pwa-admin-render` на машине сборки.
Доставьте файл vmshpwa/admin-render/dist/render.cjs рядом с backend. Для экспорта нужен Node.

Отзыв через объявленный revocation_endpoint аннулирует пару токенов.
[Маршруты и проверка делегирования](../../../admin_mcp/oauth.py) · [Тест SDK](../../../pwa_tests/integration/test_admin_remote_mcp.py).

Для регистрации с секретом задайте `VMSH_ADMIN_MCP_CLIENT_SECRET` и укажите его
в ChatGPT. Тогда discovery объявляет client_secret_post. Файлы загружаются по HTTPS
с поддоменов oaiusercontent.com. Дополнительные проверенные имена файловых хостов
можно перечислить через запятую в `VMSH_ADMIN_MCP_FILE_HOSTS`.

После входа Staff показывает название портала, аккаунт и запрашиваемые права на языке кабинета.
Обе кнопки возвращают пользователя в ChatGPT. При отказе клиент получает `access_denied`.
[Страница согласия](../../../apps/pwa_api/oauth_consent.py) · [Проверка в Chromium](../../scripts/test-admin-consent.mjs).
