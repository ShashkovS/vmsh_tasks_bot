# Выпуск TikZ и аудит незавершённых доработок — 11 октября 2026

Владелец разрешил выпуск на ВМШ и TLF и попросил проверить все оставшиеся
доработки. Перед интеграцией оба production source — `a926dc61`; runtime и
GlitchTip уже обновлены. Исходные worktree сохранены без изменений.

## Состав

| Работа | Фактическое состояние до выпуска | Действие |
| --- | --- | --- |
| TikZ `itemnum`/`\пункт` | Локальный проверенный fix, compiler 11 | Выпустить на оба сайта |
| GlitchTip, privacy, квота событий | Уже на обоих production, source `a926dc61` | Сохранить актуальную основную ветку и private maps |
| Offline-картинки TLF | CORS установлен; октябрьский `cache: reload` был отдельной ручной сборкой и отсутствует в свежей основной ветке | Сохранить fix/test/probe в Git и пересобрать приложения |
| Кросс-бекапы | Installed tool hashes совпадают на обоих хостах, три timers active; prep daily capture и cross-transfer успешны 11 октября | Зафиксировать готовые исходники и защиту расписания/старых архивов в основной ветке |
| Правила мониторинга ВМШ | 13 правил установлены через Grafana API 8 октября; исходники оставались untracked | Зафиксировать проверенные исходники/runbook; не повторять установку или тестовую отправку |
| Импорт Zoom и проверка webhook | Выполнены владельцем/проверены 8 октября; исходники и обезличенные отчёты сохранены только в stash | Восстановить операционные исходники/подтверждения в основной ветке; импорт/diagnostic deliveries не повторять |
| Учёт работы преподавателей | Dirty `codex/teacher-work-accounting`, статус «реализация начата», checks/rehearsal не выполнены | Не включать незавершённый код; новая 0117 конфликтует с уже выпущенной 0117 и требует rebase/перенумерации |

Остальные активные Git worktree либо чистые и уже включены в основную ветку,
либо содержат сохранённые операционные записи. Исходная локальная `vmshpwa`
отставала от `origin/vmshpwa`; release собирается поверх актуальной origin.
Git stash проверен по неизменным SHA, исходные snapshots не удаляются.
`df8de4d8` содержит завершённые Zoom operations: восстановлены все семь
файлов и актуальные webhook notes. `2a1fcc89` — старый snapshot release
3 октября: rich-files/problem-release уже входят в `origin/vmshpwa`,
исторические migrations намеренно заменены baseline 0111. Новая
`45bad0df` принадлежит текущей работе teacher accounting и не применяется.

Ссылки: [TikZ](../../pwa_tests/reports/tikz-itemnum-20261010/README.md),
[GlitchTip](glitchtip/migration-20261011.md),
[offline CORS](tlf-app/README.md#public-media-cors--2026-10-01),
[кросс-бекапы](cross-backup/README.md),
[мониторинг](vmsh-alerting/README.md),
[Zoom import](zoom-events-import-20261008/STATUS.md).

## Проверка и выпуск

Интеграция, gate `content offline-current` и production cutover в работе.
Локальные reference inputs восстановлены из основного checkout в игнорируемый
`_external_pipelines`; production credentials в tests не загружаются.
Перед restart — verified SQLite backup, frozen build и private maps upload;
после — exact source/static SHA, 25 HTTP checks на каждом сайте, реальный
TikZ→SVG из production toolchain, неизменность данных/настроек/NATS и backup timers.
При неудаче TLF guarded script восстанавливает прежний source/static/config.

Локальные snapshots/logs: `.runtime/release-audit-20261011/`.
