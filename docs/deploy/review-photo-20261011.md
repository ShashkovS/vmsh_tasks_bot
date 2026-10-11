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

Выпуск начат. Окончательные release IDs и обезличенные квитанции будут
добавлены после проверки обоих порталов.
