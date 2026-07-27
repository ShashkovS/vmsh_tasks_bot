# Новости и Telegram

## Источники

Telegram-каналы учебных групп остаются редакционными источниками новостей. У каждой группы свой destination в `groups.telegram_channel_id`; bot token хранится только в runtime config. Бот обрабатывает новые и изменённые channel posts, включая albums/media groups, rich text/entities и ссылки. Он переносит media в S3-compatible storage, сохраняет локальную служебную копию в разрешённом runtime и записывает нормализованную публикацию с `group_id` в SQLite.

Channel mapping подтверждается Bot API probe: сохраняется возвращённый canonical `chat.id`, title используется только как diagnostic. Unmapped channel не определяется по похожему title/username и не получает случайную группу. Смена destination влияет только на следующие операции; исторические chat/message IDs публикаций остаются неизменны.

Первичная миграция подтягивает историю начиная с 1 апреля 2026 года. Telegram и PWA затем используют один нормализованный источник: изменение исходного поста обновляет публикацию в PWA, удаление исходного поста удаляет её из PWA. Неизменяемый audit при этом сохраняет факт и предыдущую ревизию операции.

Staff может создавать local-only публикации и скрывать Telegram-посты только в PWA. Скрытие в PWA не меняет исходный пост Telegram. Local-only публикации и персональные сообщения создаёт только администратор. Отправка новой Staff-публикации обратно в Telegram относится ко второй фазе; до неё Telegram остаётся источником всех общих публикаций канала.

## Представление

Нормализованная запись содержит source, Telegram chat/message IDs, revision, publish/edit time, structured rich text, album ordering, media metadata, audience/level tags, visibility и moderation reason. Математические расширения проходят тот же безопасный renderer, что условия задач.

Перед публикацией показываются два preview: PWA card/detail и Telegram. Для новых структурированных материалов Telegram adapter использует Bot API 10.1+ `sendRichMessage` и отдельный allowlisted Rich Message HTML с headings, paragraphs, emphasis/mark/sub/sup/spoiler, links, lists, quotes, code, details, tables, media и `<tg-math>`/`<tg-math-block>`. Новые условия задач отправляются полноценным текстом, не скриншотом; SVG/рисунки остаются media. Это не означает, что тот же markup можно передать в legacy `sendMessage(parse_mode=HTML)`. Renderer проверяет limits по characters, blocks, nesting, media и table columns до отправки. Исторические fixtures берутся из `_external_pipelines/ChatExport_2026-07-25`.

## Доставка и идемпотентность

Channel update имеет устойчивый source key; повторная доставка не создаёт дубль. Media скачивается и проверяется до перевода revision в visible. После commit backend посылает NATS invalidation, foreground получает WebSocket, background — Web Push согласно категории «Новости».

Общие новости для нескольких детей в Family показываются один раз. Публикация с групповой или персональной адресацией помечается ребёнком/группой, к которой относится. Неподдерживаемый редкий тип Telegram-вложения пропускается, записывается в diagnostics и не блокирует обработку остального поста.

## Модерация

Staff-фильтры: source, visible/hidden, tags, level, дата, missing media и divergence. Любое скрытие, восстановление, local post или override фиксируется в audit. Удаление Telegram-поста автоматически скрывает его в PWA; отдельного ручного решения администратора не требуется.

## Рассылки

Баннер имеет время начала и окончания; обычная публикация остаётся доступной без автоматического срока удаления. Полноценные административные рассылки, Markdown editor, расписание и delivery dashboard относятся ко второй фазе. Существующая специальная административная группа остаётся будущей допустимой целью; исторических рассылок такого типа пока нет.

## Course/group bindings

Целевая конфигурация хранится в `telegram_bindings` с owner `course|group` и purpose `news_source|materials_target`. Course и group news sources складываются; group materials targets заменяют course defaults, иначе наследуют их. Каждый `group_lesson` публикует собственные материалы и расписание. Telegram остаётся параллельным adapter, а unit/E2E работают без сети. Полный контракт: [courses-groups-and-lessons.md](courses-groups-and-lessons.md).
