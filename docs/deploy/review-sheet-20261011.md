# Выпуск проверки простынёй — 11 октября 2026

Владелец разрешил commit, интеграцию в основную ветку, push и деплой на оба
сервера после сообщения об ограничениях общего release gate.
Основная production-ветка этого репозитория называется `vmshpwa`; ветки `main`
нет. [Требование и реализация](../../vmshpwa/docs/review-sheet.md),
[проверки и ограничения](../../pwa_tests/reports/review-sheet-20261011/README.md).
Миграции и изменения зависимостей не нужны.

ВМШ выпускается штатным [webhook](vmsh-webhook-setup.md); TLF —
[сценарием](tlf-app/deploy_review_sheet.sh), переиспользующим проверенный
[выпуск фотографий](review-photo-20261011.md): backups/integrity до и после,
production bundles/private sourcemaps, неизменность таблиц при остановленных
writers, canonical settings/NATS, runtime/HTTP/service checks и rollback
source/static/config без отката данных. Untracked файлы сохраняются.

Статус: выпуск начат. GitHub доступен через `gh`; SSH восстановлен через
штатный launchd agent. Оба checkout на `7dd8c5a5`, tracked изменений нет,
службы active; untracked данные сохраняются. Секреты не выгружаются.
Квитанции и итоговые source/static revisions будут добавлены после проверки.
