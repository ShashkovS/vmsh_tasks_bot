# Worktree и production: финальная сверка 11 октября 2026

Владелец запросил очистку worktree и проверку отсутствия хвостов после
[выпуска учёта преподавателей](teacher-work/README.md). Обе рабочие production
копии совпали с `origin/vmshpwa` (`72a9a472` до этого документа), static release
остаётся проверенным `33f6c950`. Maintenance отсутствует, службы и analytics
timers active, схемы current: ни missing/unexpected migration, ни hash mismatch.
Зависших teacher-work queued/running операций нет; на TLF три completed.
[Обезличенный proof](../../pwa_tests/reports/worktree-cleanup-20261011.json).

## Локальная очистка

Все 15 временных worktree проверены: их HEAD уже включены в production-ветку.
Три грязных checkout содержали источники cross-backup, offline CORS и alerting,
уже выпущенные в `04badd23`; отличия только в старых status/docs и тесте,
в текущей версии расширенном additional Off/cache-time regressions.

Перед удалением сохранены Git snapshot refs, staged/working binary patches,
оба stash и полезные ignored-файлы: fixtures, БД, credentials, логи и proofs.
Частные архивы находятся в основном checkout:
`/Users/sergeyshashkov/repos/vmsh_tasks_bot/.runtime/worktree-archive-20261011/`.
Каталог 0700, архивы 0600; каждый сохранённый файл проверен по SHA-256,
`sources.bundle` verified. Generated dependencies/cache не сохранялись:
node_modules, virtualenv, Python/Vite/uv/pnpm caches и dist восстанавливаются.
Архивы не отправлялись в GitHub и не содержатся в публичном proof.

Удалены 14 завершённых checkout и одна отсутствующая rich-markdown registration.
Оба stash перенесены в durable `refs/archive/worktree-cleanup-20261011/stash-*`,
после проверки bundle/ref обычный stash list очищен. История сохранена.

Остались основной checkout и чистый текущий `051d`. Штатный Codex archive
отклонил удаление текущего: `The task's primary checkout cannot be removed.`
У обоих нет незакоммиченных файлов и невыпущенных feature commits; основной
checkout обновлён до production-ветки. Текущие Codex/MCP host processes не
являются тестовыми PWA servers и не останавливались.

## Восстановление

Каждый исходный HEAD, snapshot/ref, archive SHA и ignored-file manifest записан
в `summary.json` и подкаталогах private archive. Для восстановления источников:

```sh
git worktree add --detach /path/to/restored-checkout refs/archive/worktree-cleanup-20261011/68ae
```

Нужные ignored-файлы восстановить из соответствующего `ignored-files.tar.gz`
в закрытый каталог, сохраняя private permissions. При переносе репозитория
импортировать `sources.bundle`; его prerequisite commits уже есть в основной
production истории. Stash commit сохраняет все исходные parents и untracked tree.

## История вне текущего выпуска

PR #103 merged; текущих невыпущенных feature PR нет. Старый PR #102 от 29 июля
ведёт `vmshpwa` в legacy `prod`; обе production-службы используют `vmshpwa`.
Этот пользовательский PR сохранён, merge в legacy branch не выполнялся.
Исторические `groups_to_db`, `stripe_integration` и compatible rollback refs
сохранены по предыдущему [release audit](release-audit-20261011.md); они не
являются текущими release candidates. Первичные admin alias/roster decisions
и UI acceptance — дальнейшая работа пользователя в уже выпущенном интерфейсе.
