# Worker RAM cache — 12 октября 2026

[Решение владельца и компоненты](../../../docs/performance/worker-read-cache.md).
Изменения без migrations. Владелец разрешил 13.10 выпуск на оба портала;
[операционный record](../../../docs/performance/worker-read-cache-release.md).

Финальный `make pwa-check-fast PWA_E2E_MODES="authentication content realtime"`:
**PASS**, 253 секунды, source unchanged. [Квитанция](check.json),
[build и Chromium E2E](e2e.json).

- Python: 3012 PASS / 12 SKIP (guarded live/legacy scenarios).
- Frontend: 1119 PASS; Storybook: 380 PASS.
- Chromium: 39 auth/content + 4 realtime = 43 PASS, без retries.
- Dependencies/format/types/lint CSS+JS/i18n/backend+frontend/build: PASS.
- `git diff --check`, scoped Ruff: PASS.

HTTP regression `test_worker_cache_avoids_sql_on_warm_me_content_and_lesson_reads`
в [content HTTP suite](../../integration/test_content_http_api.py) измеряет вызовы
общего `factory.run_read_async`: warm auth/me + материалы + список занятий
дают **0 чтений**; повторный список задач — **1 чтение** личного work state.
Это локальная синтетическая проверка числа чтений, не production percentile.

[Cache tests](../../test_worker_read_cache.py): coalescing 20 readers, TTL,
in-flight generation fence, cancellation waiter/leader, failure recovery,
entry/resident memory bounds, mutable AST copy, resource invalidation,
two-subscriber broadcast, failed local publish, reconnect, trusted cookie,
session/cookie expiry, allowed stale auth and session-control cache reset.
SQL parity и свежесть verdict/queue/discussion/answer при прямых legacy writes,
изоляция учеников и существующие reveal/consent scenarios проходят.

Scope-boundary fixtures с прямым SQL отзывом/добавлением grants теперь явно
[принуждают следующий auth miss](../../auth_cache_support.py): проверка свежих
прав сохранена, разрешённое владельцем окно кеша проверяется отдельно.
Изменение активной группы/режима, logout и locale сбрасывают кеш через
приложение; существующие browser сценарии переключения/отзыва проходят.

Первые прогоны обнаружили отсутствие ignored approved corpora в новом worktree,
затем запрет corpus validator на внешние symlinks. Финальный прогон использует
локальные копии существующих `_vmsh_examples` и `_external_pipelines`; inputs
не менялись и остаются вне Git. Старые прогоны не выдаются за PASS квитанции.

Следующие шаги: завершение разрешённого backend release и измерение HTTP/read queue/cache
memory под реальной нагрузкой. Общий RAM cache не исправляет тяжёлый live-board
SQL и широкое frontend refetch; они остаются отдельными задачами аудита.
