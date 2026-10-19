# Публичный домен ВМШ — 8 октября 2026

## Решение владельца

Публичные файлы бакета `d3ca76cf4cf5-images-bucket` переходят с
`https://d3ca76cf4cf5-images-bucket.s3.ru1.storage.beget.cloud` на
`https://vmshstor.shashkovs.ru`. Старые URL остаются рабочими. S3 API endpoint,
имя бакета, object keys и сами файлы не меняются.

Владелец уже применил на production ВМШ `s3_public_base_url`, nginx CSP с обоими
доменами и frontend build `55ed5e9c7e9c-20261008065457`. Предоставленные HTTP
ответы подтверждают разрешения для Student HTML и обоих service workers;
build provenance содержит новый `publicMediaOrigin`. Это не означает, что
сохранённые ссылки в SQLite уже перенесены.

## Реализация

- [`Миграция 0115`](../../migrations/0115.vmsh_public_media_domain.py) заменяет
  точные HTTPS URL этого бакета в virtual-hosted и path-style форме, включая
  JSON с escaped slashes. Префикс включает `/`, поэтому другой бакет или похожее
  имя хоста не совпадают. Уже новые URL и Hetzner/TLF не меняются.
- Обновляются `media_assets.public_url`, текстовые `content_derivatives`,
  замороженные `publication_figure_layouts`, Markdown/JSON `lesson_block_revisions`,
  публичные `news_media`/`group_banner_media` и документы `news_revisions`/
  `group_banners`. Browser API читает эти сохранённые документы в
  [`get_published_content`](../../db_methods/pwa/content.py) и
  [`content_routes`](../../apps/pwa_api/content_routes.py).
- SHA-256 изменённых derivatives и Telegram snapshot пересчитывается. SHA
  самих файлов, object keys, IDs, версии, timestamps, source hashes, исходный
  LaTeX, Telegram receipts, source URLs, provenance/audit и idempotency receipts
  сохраняются. Bucket policy и файлы в S3 не меняются.
- Все изменения и временное снятие шести immutable guards находятся в одном
  `BEGIN IMMEDIATE`. Исходные определения триггеров восстанавливаются до commit;
  ошибка откатывает и DML, и DDL. Миграция допускает прежние legacy FK-дефекты,
  но требует неизменность их полного списка. DDL после миграции прежний.
- Повторное применение не меняет данные. Yoyo rollback **сохраняет новые URL**:
  обратная массовая замена затронула бы также новые ссылки, существовавшие до
  миграции или добавленные позже. Для точного восстановления данных используется
  maintenance backup; совместимость обоих доменов сохраняется в CSP.
- Новый build origin перенесён в
  [`deploy-vmsh-tasks-bot.sh`](../../docs/deploy/deploy-vmsh-tasks-bot.sh), а оба
  разрешённых CSP origin — в
  [`vmsh_tasks_bot_v3_deploy.sh`](../../docs/deploy/vmsh_tasks_bot_v3_deploy.sh) и
  renderer [`nginx template`](../deploy/nginx/vmshpwa.conf.template). Marker
  `@@CSP_MEDIA_ORIGIN@@` принимает список точных origins через пробел;
  `VITE_PUBLIC_MEDIA_ORIGIN` остаётся одним новым origin. `img-src`, `media-src`
  и `connect-src` разрешают оба домена. Другие deployment inputs остаются своими
  для каждого портала.

## Проверки и выпуск

[`Data migration regressions`](../../pwa_tests/integration/test_public_media_domain_migration.py)
проверяют сохранение всех нетранспортных product rows/полей, реальные frozen
publication и archived derivative, Markdown, escaped JSON, SHA-256, другой
бакет/похожий hostname, повторный запуск и failure после DML/при восстановлении
триггеров. [`Nginx regressions`](../../pwa_tests/test_nginx_proxy_config.py)
проверяют обе политики production map и общий renderer.

Целевые 40 тестов, Ruff и deterministic schema inventory — PASS. Product DDL
сохранил 510 объектов и прежний fingerprint. Выполнен
`make pwa-check-fast PWA_E2E_MODES="content"`: format, types, JS/CSS lint и оба
i18n — PASS. Общий Python дал 2827 PASS / 8 SKIP / 17 FAIL. После восстановления
96 allowlisted статических входных файлов из основного checkout все 14
зависевших от них тестов прошли. Production credentials не читались.

Три оставшихся сбоя воспроизведены на неизменённом HEAD `55ed5e9c7e9c` в
изолированном временном checkout: две проверки production markers требуют
отсутствующий production profile JSON; Staff scope test смешивает frozen auth
clock с реальным временем записи grants. Эти тесты и код auth/scope не менялись.
Общий gate остаётся **не зелёным**. Оставшиеся этапы выполнены отдельно без
повторения прошедших suite: frontend 1048 PASS, Storybook 362 PASS плюс один
golden-corpus test после восстановления PDF, verification build и Chromium
content 2 PASS. [Структурированный отчёт](../../pwa_tests/reports/public-media-domain-20261008/validation.json).

Применение 0115 на production **ещё не выполнено**. Оно входит в обычный
[`deploy`](../../docs/deploy/deploy-vmsh-tasks-bot.sh): backup и репетиция на
копии, maintenance, остановка writers, `migrate_runtime`, health и восстановление
services. После выпуска и следующего online запроса материалов Student/Family
получат новые URL. Офлайн сохранённые документы сохраняют прежние ссылки до
следующего online обновления; storage/черновики браузера очищать не требуется.

## Production release — 2026-10-08

Выпущено на ВМШ и TLF в объединённой ревизии `d4bf4a30`.
[Решение владельца, миграции, фактические runtime/static/backups proofs и
остаточная браузерная проверка](../../docs/performance/integrated-release-20261008.md). Оба public smoke — 25 PASS;
схема current на 0116, сервисы active, maintenance снят. Direct S3 не включался;
production speedup пока не измерен. Исторические ограничения gate выше сохранены.
