# Production rollout — 17 ноября 2026

По разрешению владельца выпущен `0f7ef0f9f529dc641bada70c70204b6a61b3a1f2`
на **vmshfirstvds** и **prep.leaders.tech**. Static release обоих сайтов:
`review-contribution-20261117`. Миграций и изменений production dependencies нет.

| Проверка | FirstVDS | prep.leaders.tech |
| --- | --- | --- |
| Предыдущий backend | `a20adbe00920` | `d2e5dddc2b02` |
| HTTP smoke | 25 PASS | 25 PASS |
| HTML / Staff asset hashes | 4 / 121 совпали | 4 / 121 совпали |
| Workers | 2 новых, master сохранён | 2 новых, master сохранён |
| Main + analytics backup до/после | integrity PASS | integrity PASS |
| Schema / canonical config | сохранены | сохранены |
| Другие services | Telegram/NATS PID сохранены | Zoom/NATS PID сохранены |
| Журнал PWA после runtime probe | без ERROR | без ERROR |

TLF получил всю накопленную пачку исходников, включая personal plots/printing,
диагностику фотографий, мобильную проверку и личный вклад. Его отдельный
diagnostics commit не потерян: diff с конечной версией сохраняет тот же код.
Публикации, результаты, учётные записи и настройки курсов не менялись.

На FirstVDS трёхсторонним слиянием сохранены пять прежних backend repairs,
а также три frontend media/service-worker patches. Добавленные ранее untracked
`deferred_reviews.py` и migration 0124 не затрагивались. Точный состав:
[FirstVDS](vmsh-source-summary.json), [TLF](prep-source-summary.json).

Сборки выполнены под Node 26.9.0 / pnpm 11.15.1 с frozen lockfile и отдельной
копией профиля каждого хоста. MSW/prototype выключены; публичных sourcemaps нет.
На TLF verified private upload содержит 416 artifacts. FirstVDS сохраняет
прежнюю конфигурацию Sentry DSN; private upload metadata отсутствовали и в
предыдущем source-каталоге. Рабочие credentials не менялись.

Доставка — обычный Git bundle по SSH, без push/webhook и обращения к GitHub API.
После проверки staging установлен source snapshot, индекс deployment checkout
переведён на target с `git reset --mixed`; исходные server repairs остаются
незакоммиченными изменениями. PWA workers плавно заменены через HUP. Старые
immutable assets сохранены для уже открытых вкладок.

На свежей read-only копии FirstVDS проверены пять крупнейших проверяющих:
максимум 11022 проверки, 0.219 s. На TLF — оба проверяющих, максимум 538,
0.010 s. Действующая учительская сессия во встроенном браузере после reload
показала свёрнутый «Ваш вклад»; раскрытие показало итоги, разбивку, рубежи,
дневной и недельный рекорды. Проверки или учебные данные через UI не сохранялись.
Анонимный GET нового API на обоих сайтах возвращает 401.

## Квитанции и откат

[Скрипт состоявшегося rollout](deploy.py), [итог ВМШ](vmsh-result.json),
[итог TLF](prep-result.json), [финальная проверка ВМШ](vmsh-final-check.json),
[финальная проверка TLF](prep-final-check.json).
Read-only модель: [ВМШ](vmsh-contribution-data-check.json),
[TLF](prep-contribution-data-check.json).
Backups: [ВМШ до](vmsh-backup-before.json) / [после](vmsh-backup-after.json),
[TLF до](prep-backup-before.json) / [после](prep-backup-after.json).

Закрытые source/safety snapshots и полные журналы находятся на каждом сервере:
`/web/vmsh_tasks_bot/deploy/releases/review-contribution-20261117/`.
Скрипт сохраняет каждый заменяемый файл и при ошибке возвращает source/static,
затем повторяет HUP. Данные БД не восстанавливаются из устаревшего snapshot,
поскольку схема не менялась. Автоматический откат не понадобился.

## Остаток: владелец новых каталогов исходников

Production runtime работает, но новые каталоги, перечисленные ниже, созданы
root с режимом 0750. Вложенные файлы уже принадлежат `vmsh_tasks_bot:web`;
service user не может пройти через родительский каталог, поэтому `git status`
печатает Permission denied для этих отчётов/fixture. На приложение это не
влияет. Read-only проверка подтвердила отсутствие каждого каталога в sourceBefore.

Автоматическая approval review отклонила и общий, и суженный запрос исправить
владельца, потребовав отдельное одобрение persistent access change. Изменение
владельца **не выполнено**; альтернативный обход не применялся. После явного
подтверждения нужен только `chown vmsh_tasks_bot:web` без рекурсии и chmod:

- На обоих хостах под `/web/vmsh_tasks_bot/vmsh_tasks_bot/`:
  `pwa_tests/reports/mobile-review-20261117`,
  `pwa_tests/reports/mobile-review-actions-20261117`,
  `pwa_tests/reports/review-contribution-20261117`,
  `vmshpwa/packages/contracts/fixtures/review`.
- Дополнительно на TLF: `pwa_tests/reports/written-photo-20261113`.

Ни credentials, ни runtime/media directories в этот список не входят.
Локальные [ограничения общего gate](../README.md#ограничения-общего-gate)
сохраняются; production smoke не объявляет весь тестовый набор зелёным.
