# Быстрое сопоставление и импорт очных смен — 12 октября 2026

[Правила и реализация](../../vmshpwa/docs/teacher-work.md),
[проверки и снимки](../../pwa_tests/reports/teacher-work-inputs-20261012/README.md).
PR [#104](https://github.com/ShashkovS/vmsh_tasks_bot/pull/104) влит в
production-ветку `vmshpwa`: `278515d194d30bdfe7eccdf60c95358610360e63`.
Merged tree совпадает с прошедшим fast gate feature commit `b09e221f`;
повторение suites не требуется. Миграций, новых зависимостей и секретов нет.

ВМШ: штатный webhook, release `278515d194d3-20261011215407`.
TLF: существующий `deploy_review_photo.sh` с новым именем release; копия
сценария под `/web/vmsh_tasks_bot/deploy/teacher-inputs-20261012/deploy.sh`,
installation/build/rollback records под
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261012-teacher-inputs-278515d194d3/`.
Файлов вне `/web/vmsh_tasks_bot` не создавалось.

На каждом: 25 production HTTP checks PASS, HTML и production provenance
четырёх приложений совпадают с release; 116 Staff JS/CSS SHA-256 PASS;
public maps отсутствуют, Sentry включён, prototype/MSW false; четыре
teacher-work GET API и media требуют auth (anonymous 401), службы/timers
active, maintenance off.

TLF: все таблицы/строки совпали по stopped-writer SHA-256, canonical settings
сохранены кроме release label, NATS PID прежний. Backups
`20261011T215433.542310Z` / `20261011T215503.670125Z`: integrity ok.
ВМШ: live SQLite read-only integrity ok, 8768 Zoom-событий. Код и схема
ledger не меняются; пересчёт по кнопке и штатному таймеру.
Production rows и credentials не выгружались, тестовые сопоставления
в live БД не записывались.

[Обезличенные квитанции](../../pwa_tests/reports/teacher-work-inputs-20261012/production-proof.json).
Последующая запись этого record — только документация; production source
можно fast-forward без перестройки проверенных static releases.
