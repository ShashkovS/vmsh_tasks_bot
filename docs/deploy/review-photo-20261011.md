# Выпуск просмотра фотографий — 11 октября 2026

Владелец разрешил commit, push в основную production-ветку `vmshpwa` и
деплой на оба сервера. [Реализация и требования](../../vmshpwa/docs/review-photo-preview.md),
[полный gate и снимки](../../pwa_tests/reports/review-photo-preview-20261011/README.md).
Исходное состояние обоих серверов: `26859b0f`, schema 0118; рабочие checkout
не имеют tracked изменений. Существующие untracked данные сохраняются.

ВМШ выпускается штатным [GitHub webhook](vmsh-webhook-setup.md).
TLF — [сценарием](tlf-app/deploy_review_photo.sh), адаптированным из предыдущего
выпуска без установки tooling или миграций: verified backups до/после,
production build и private sourcemaps, static verify, stopped-writer comparison
всех таблиц, сохранение canonical settings и NATS, runtime/HTTP/service checks.
Предыдущая source/static revision записывается на сервере до переключения;
при ошибке возвращаются прежний код/сборка/настройки без отката данных.

Коммит `4584392b52e4d02658d5f4b5afd28bfb637da41c` отправлен в `vmshpwa`.
Оба выпуска завершены успешно:

| Сервер | Static release | HTTP | Staff JS/CSS SHA-256 |
| --- | --- | --- | --- |
| ВМШ | `4584392b52e4-20261011154513` | 25 PASS | 114 PASS |
| TLF | `tlfprep-20261011-review-photo-4584392b52e4` | 25 PASS | 114 PASS |

HTML и production provenance всех четырёх приложений совпали с release;
GlitchTip сохранён, 402 private artifacts uploaded на каждом сервере,
public maps отсутствуют. Media endpoint требует авторизацию (anonymous 401).
Все штатные службы/timers active, maintenance off. БД/schema не менялись.

На TLF stopped-writer comparison сохранил 168 таблиц / 36784 строки;
canonical settings сохранены кроме release label, NATS PID прежний.
Backups `20261011T154529.074085Z` / `20261011T154559.165336Z`: integrity ok.
ВМШ schema 0118 и post-deploy server-only backup 380153856 bytes: integrity ok,
`db/review-photo-release-20261011/post-deploy-20261011T154818Z.sqlite3`.
Webhook не создаёт дополнительные backups для выпуска без миграций.

[Обезличенная квитанция](../../pwa_tests/reports/review-photo-preview-20261011/production-proof.json),
[read-only verifier](../../pwa_tests/reports/review-photo-preview-20261011/verify-deployment.py).
TLF installation/build/config/rollback records сохранены под
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261011-review-photo-4584392b52e4/`;
ВМШ — штатные deployment log, revision marker и static reports.
Untracked production файлы сохранены; production rows не выгружались.

Ручная проверка системного копирования и вставки в графредактор остаётся
follow-up: native apps недоступны из-за заблокированного Mac. Production
acceptance под пользовательской Staff-сессией не заявляется.
