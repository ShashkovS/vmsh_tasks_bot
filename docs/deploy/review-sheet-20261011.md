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

Коммит `08d4926dfccba57058c5e9858206d44360448c36` интегрирован fast-forward
в `vmshpwa` и отправлен в origin. Оба выпуска завершены:

| Сервер | Static release | HTTP | Staff JS/CSS SHA-256 |
| --- | --- | --- | --- |
| ВМШ | `08d4926dfccb-20261011175901` | 25 PASS | 116 PASS |
| TLF | `tlfprep-20261011-review-sheet-08d4926dfccb` | 25 PASS | 116 PASS |

HTML и production provenance всех четырёх приложений совпали со сборками.
406 private artifacts uploaded на каждом сервере, public sourcemaps отсутствуют.
Новый `/staff/review/sheet` возвращает Staff HTML, API простыни и приватных
фотографий требуют авторизацию (anonymous 401). Службы/timers active,
maintenance off, schema 0118; миграции и переустановка инфраструктуры не нужны.
Сообщение штатного webhook про infrastructure вызвано новым ручным TLF script
и record в `docs/deploy`; установленные webhook/nginx/systemd файлы не менялись.

На TLF stopped-writer comparison сохранил все 168 таблиц / 36967 строк;
canonical settings сохранены, NATS PID прежний. Backups
`20261011T175916.077310Z` / `20261011T175945.181929Z`: integrity ok.
ВМШ: дополнительный server-only post-deploy backup 385581056 bytes,
`db/review-sheet-release-20261011/post-deploy-20261011T180115Z.sqlite3`,
integrity ok. Production rows не выгружались, untracked файлы сохранены.

[Обезличенная квитанция](../../pwa_tests/reports/review-sheet-20261011/production-proof.json),
[read-only verifier](../../pwa_tests/reports/review-sheet-20261011/verify-deployment.py).
TLF installation/build/config/rollback records находятся под
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261011-review-sheet-08d4926dfccb/`;
ВМШ — штатные deployment log, revision marker и static reports.
SSH восстановлен через штатный launchd agent, секреты не выгружались.

Итоговый commit документации не меняет runtime: ВМШ получает его штатным
webhook, TLF — fast-forward без пересборки/перезапуска. Static release остаётся
на проверенном feature commit. Общие ограничения E2E/visual gate из отчёта
сохраняются; authenticated browser acceptance на production не заявляется.

## Исправление повторных сообщений

После замечания владельца убран повторный блок «Материалы оценки». Решения
отображаются один раз в общем диалоге; перенос/клонирование/разметка находятся
при сообщении. Evidence/CAS не меняются, миграций/изменений зависимостей нет.
[Проверки и новые снимки](../../pwa_tests/reports/review-sheet-conversation-20261011/README.md):
fast gate PASS (2981 Python / 12 SKIP, 1102 frontend, 375 Storybook,
10 Chromium E2E), дополнительный review для сохранения снимков 4 PASS.
Выпуск исправления начат в ранее авторизованном scope; используется тот же
webhook ВМШ и [TLF script](tlf-app/deploy_review_sheet.sh).
