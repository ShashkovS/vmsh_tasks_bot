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

Старые ветки без активного worktree также сохранены: rollback sources
`43b7d2f4`/`cd18511e` намеренно содержат только совместимые старые runtime;
`webapp` имеет patch-equivalent commit, уже включённый в основную ветку.
`groups_to_db` (январь–февраль 2026) и `stripe_integration` (сентябрь–октябрь
2025) не являются текущими release candidates: первая заменена современной
course/group моделью, вторая содержит незавершённую legacy payments integration.
Они не сливаются автоматически в production; старые snapshots не удалены.

Ссылки: [TikZ](../../pwa_tests/reports/tikz-itemnum-20261010/README.md),
[GlitchTip](glitchtip/migration-20261011.md),
[offline CORS](tlf-app/README.md#public-media-cors--2026-10-01),
[кросс-бекапы](cross-backup/README.md),
[мониторинг](vmsh-alerting/README.md),
[Zoom import](zoom-events-import-20261008/STATUS.md).

## Проверка и выпуск

Интеграция завершена. Gate `content offline-current` PASS на `04badd23`:
2944 Python PASS / 7 SKIP, 1088 frontend, 364 Storybook, 4 Chromium E2E
без retries; format/types/lint/i18n и четыре app builds PASS.
[Квитанции](../../pwa_tests/reports/release-audit-20261011/).
Source digest `ba42caee96980c245aef430e088be52cb14fa71e9d61017c2f1e19bee7660c72`,
`source_changed=false`. Пять изолированных Zoom importer regressions PASS.
Production cutover в работе.
Локальные reference inputs восстановлены из основного checkout в игнорируемый
`_external_pipelines`; production credentials в tests не загружаются.
Перед restart — verified SQLite backup, frozen build и private maps upload;
после — exact source/static SHA, 25 HTTP checks на каждом сайте, реальный
TikZ→SVG из production toolchain, неизменность данных/настроек/NATS и backup timers.
Grafana API 11 октября: все 13 правил enabled, health=ok, state=inactive;
изменений/тестовых уведомлений нет. На ВМШ создан свежий verified online backup
`deploy/runtime/release-audit-20261011/production-before.sqlite3`, 372101120 bytes.
При неудаче TLF guarded script восстанавливает прежний source/static/config.

Локальные snapshots/logs: `.runtime/release-audit-20261011/`.
