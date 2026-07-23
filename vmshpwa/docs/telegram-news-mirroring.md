# Новости и Telegram

## Источники

Telegram-канал остаётся основным редакционным источником новостей. Бот обрабатывает новые и изменённые channel posts, включая albums/media groups, rich text/entities и ссылки. Он переносит media в S3-compatible storage, сохраняет локальную служебную копию в разрешённом runtime и записывает нормализованную публикацию в SQLite.

Staff может создавать local-only публикации и скрывать Telegram-посты в PWA. Скрытие в PWA не удаляет исходный пост из Telegram. Редактирование Telegram-поста создаёт новую source revision; редакционные overrides не теряются и видны в moderation diff.

## Представление

Нормализованная запись содержит source, Telegram chat/message IDs, revision, publish/edit time, structured rich text, album ordering, media metadata, audience/level tags, visibility и moderation reason. Математические расширения проходят тот же безопасный renderer, что условия задач.

Перед публикацией показываются два preview: PWA card/detail и Telegram. Для новых структурированных материалов Telegram adapter использует Bot API 10.1+ `sendRichMessage` и отдельный allowlisted Rich Message HTML с `<tg-math>`/`<tg-math-block>`. Это не означает, что тот же markup можно передать в legacy `sendMessage(parse_mode=HTML)`. Renderer проверяет limits по characters, blocks, nesting, media и table columns до отправки.

## Доставка и идемпотентность

Channel update имеет устойчивый source key; повторная доставка не создаёт дубль. Media скачивается и проверяется до перевода revision в visible. После commit backend посылает NATS invalidation, foreground получает WebSocket, background — Web Push согласно категории «Новости».

## Модерация

Staff-фильтры: source, visible/hidden, tags, level, дата, missing media и divergence. Любое скрытие, восстановление, local post, override или broadcast фиксируется в audit. Удалённый в Telegram пост не удаляется физически: помечается source-deleted и требует policy/решения администратора.
