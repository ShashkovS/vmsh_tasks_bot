# Получатели новостей и объявлений

Staff-новости (`/staff/news`) и временные объявления с push
(`/staff/broadcasts`) используют одну модель получателей:

- курс и необязательная группа: без группы запись относится ко всем группам курса;
- аудитория: школьник, семья или обе аудитории;
- формат обучения: очно, онлайн или оба формата.

Student получает запись только при совпадении с его активным зачислением:
текущей группой и текущим форматом обучения. Family получает объединение записей,
подходящих хотя бы одному связанному ребёнку. `allowed_groups` не расширяет ленту:
смена группы или формата меняет выдачу после серверного сохранения профиля и
инвалидации клиентского кэша.

Существующие Telegram-новости и объявления после миграции
[`0089.pwa_communication_targeting.sql`](../../migrations/0089.pwa_communication_targeting.sql)
сохраняют прежнюю группу/курс и получают значения «обе аудитории» и «очно и
онлайн». Новые Telegram-записи используют те же значения по умолчанию.

У запланированной Staff-новости можно менять все фильтры до публикации. После
публикации разрешено исправлять только содержимое: API отвечает
`409 local_news_target_locked` на попытку изменить получателей. У активного
временного объявления фильтры менять можно; уже созданный или доставленный push
не отзывается, а будущие ещё не наступившие события пересобираются.

Backend-границы находятся в
[`news_routes.py`](../../apps/pwa_api/news_routes.py),
[`news.py`](../../db_methods/pwa/news.py),
[`group_banner_routes.py`](../../apps/pwa_api/group_banner_routes.py) и
[`group_banners.py`](../../db_methods/pwa/group_banners.py). Staff-контракты v3
добавляют поля таргетинга; старые content versions остаются без новых полей для
открытых вкладок прежнего клиента.

Проверки миграции, выборки и HTTP-контрактов находятся в
[`test_communication_targeting_migration.py`](../../pwa_tests/integration/test_communication_targeting_migration.py),
[`test_phase8_news_mirror.py`](../../pwa_tests/integration/test_phase8_news_mirror.py),
[`test_phase8_news_moderation.py`](../../pwa_tests/integration/test_phase8_news_moderation.py)
и [`test_phase8_group_banner_http_api.py`](../../pwa_tests/integration/test_phase8_group_banner_http_api.py).
