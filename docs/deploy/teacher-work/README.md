# Выпуск учёта преподавателей, 11 октября 2026

Владелец разрешил merge и выпуск на оба production. Реальная production-ветка
репозитория — `vmshpwa`; ветки `main` нет. [PR #103](https://github.com/ShashkovS/vmsh_tasks_bot/pull/103)
влит в `33f6c950bd42ac48a33b630cb3d390bec6a65190` после повторного полного gate
на свежем `ec8788ff`. [Требования и реализация](../../../vmshpwa/docs/teacher-work.md).

ВМШ выпущен штатным webhook: `33f6c950bd42-20261011133807`.
TLF выпущен вручную: `tlfprep-20261011-teacher-work-33f6c950bd42`.
На обоих миграция 0118, активные сервисы и analytics timer, maintenance снят;
по 25 HTTP checks, пять новых API возвращают anonymous 401. Все 48 подключённых
Staff JS/CSS файлов каждого сайта совпадают с release по SHA-256; provenance
четырёх приложений — production, без prototype/MSW, с действующим GlitchTip.
[Обезличенная квитанция](../../../pwa_tests/reports/teacher-work-20261011/production-proof.json).

## Данные и расчёт

Перед/после выпуска сохранены проверенные SQLite backups. Up/down/up 0118
на серверных копиях обоих порталов сохраняет 160 прежних таблиц; старые 627
FK violations совпадают, новых нет. На TLF данные также сравнены при остановленных
writers после live migration и при окончательном переключении.

TLF получил рабочие derived snapshots для обоих активных курсов; TSV прямоугольный.
На ВМШ агент имеет только чтение рабочей БД: расчёт проверен на свежей закрытой
серверной копии (39 преподавателей, 171 ячейка, менее секунды). Первый рабочий
снимок создаст admin кнопкой «Пересчитать» либо timer в 15:00 UTC 11 октября.
Исходные данные не выгружались с production. Zoom-подписи и очные распределения
подтверждает администратор; старые numeric IDs не импортировались автоматически.
Production UI acceptance под пользовательской admin-сессией не заявляется.

## TLF: безопасное восстановление

[Первый сценарий](deploy-teacher-work-tlf.sh) успешно собрал release, проверил
private sourcemaps, выполнил rehearsal и migration. Проверка JSON отчёта
остановилась из-за root-owned файла; compatible rollback `8357df87` вернул
старый адаптер с сохранённой 0118 и всей новой БД. [Resume](resume-teacher-work-tlf.sh)
проверил старые данные, сделал свежий cutover backup и выпустил готовую сборку.
Canonical settings сохранены, кроме release label; NATS не перезапускался.
Сохранённый первый сценарий исправляет доступ к JSON проверке.

[Серверный helper](teacher-work-deploy-check.py) выводит только размеры и SHA-256,
проверяет старые таблицы, FK, integrity, up/down/up и TSV. На ВМШ расчётные
модули загружаются отдельно от eager Telegram initialization; HTTP/auth не меняется.
Все файлы/копии/installation records находятся внутри `/web/vmsh_tasks_bot`.

После появления ручных данных не выполнять down 0118 или замену рабочей БД
старым backup. Для отката адаптера требуется compatible source с той же 0118;
новые смены, алиасы, поправки и аудит сохраняются.
