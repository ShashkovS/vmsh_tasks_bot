# Повторная загрузка после обновления конвертера — 2026-10-04

[Требование и причина](../../../vmshpwa/docs/content-recovery-20261004.md#повторная-загрузка-после-обновления-конвертера--follow-up).
Предыдущий выпуск не покрывал одинаковый SHA у terminal ready/invalid после
compiler 8 → 9. SQLite отвергал сброс immutable revision. На серверной копии
оба предоставленных CP1251 SHA совпали с gl-14 cr-71/cr-75; старые UPDATE
воспроизвели `terminal content revision is immutable`. Доступный journal не
содержал исходных двух request IDs; совпадение trace не заявляется.

## Исправление и регрессии

[Repository](../../../db_methods/pwa/content.py) использует cache key
`(source_id, source_sha256, parser_version)`; другая compiler generation создаёт
новый номер той же lineage, terminal snapshots/публикации сохраняются.
[0113](../../../migrations/0113.content_upload_compiler_generation.py) меняет
только unique constraint content_revisions, сохраняя строки и зависимые DDL.
Legacy/import append сохраняет запрет повторных байтов. Retry старой unfinished
revision при наличии новой generation возвращает version conflict без SQL 500.

Тесты: [repository](../../integration/test_content_repository.py),
[HTTP upload → compile](../../integration/test_content_http_api.py),
[atomic migration](../../integration/test_content_upload_generation_migration.py),
[startup guard](../../integration/test_runtime_schema.py).
HTTP cases покрывают published ready condition и invalid hint, CP1251 и
рисунок только в solution. Repository дополнительно покрывает superseded и
два concurrent upload, SQL uniqueness и запрет destructive downgrade.

## Проверки

Запущен `make pwa-check-fast PWA_E2E_MODES="content"`. Статические gates PASS
([receipt](gate-static.json)): dependencies/format/types/JS/CSS/i18n.
Первый полный Python выявил несовместимость legacy append; она исправлена,
полный Python повторён один раз: **2832 PASS / 7 SKIP**. Frontend: **1028 PASS**.
[Итоговый код](gate-full.json) имеет source digest
`d43185f46d1251edb4a0dbdca8780f390f35ea6e391527bee474458dd123061b`;
в процессе проверок он не менялся. Последующий Chromium `content` — **2 PASS**
([receipt](gate-e2e.json), [browser report](e2e.json)). Build cache проверен
по source/environment/artifact bytes; Firefox/WebKit не запускались.

Storybook: **355 PASS / 1 FAIL**, Large Classroom p95 68 ms при лимите 50 ms;
[отдельный повтор](gate-performance-retry.json) — 71.9 ms. Frontend и его
performance test побайтно не изменены относительно c502cd4f. Общий gate
пока не заявляется зелёным: этот performance blocker отдельно от проверок
backend upload. Проверка clean archive оказалась inconclusive из-за Vite
setup import до выполнения теста ([receipt](performance-baseline.json));
не является доказательством baseline performance. Pnpm автоматически
перенастроил workspace links для временной директории; они восстановлены
локально из прежнего frozen lockfile без сетевой загрузки. Порог не менялся.

Полные логи Python, frontend, Storybook и браузера сохранены в этом каталоге.
Неизменённые прошедшие suites не повторяются. Исправление критического
backend upload выпускается отдельно; production frontend/dependencies остаются
прежними. Разрешение владельца на push/autodeploy/manual TLF дано в этом чате.

## Серверная репетиция и rollback

[VMSh](rehearsal-vmsh.json): **158 таблиц / 610152 строки идентичны**, 1.480 s;
[TLF](rehearsal-tlf.json): **158 таблиц / 21955 строк идентичны**, 0.064 s.
Changed DDL: только content_revisions. Integrity ok; 627 прежних legacy FK
дефектов совпадают, новых нет. Точный новый resolver на disposable server
копии успешно создаёт generation и повторно возвращает её; старые terminal
snapshots идентичны. Production rows не передавались, копии удалены.
[Rehearsal](rehearse.py), [dispatcher](run-rehearsal.py).

[Rollback source](rollback-source.json) `cd18511e` в
`codex/content-upload-generation-rollback-20261004` сохраняет 0113 и schema
artifacts поверх предыдущего backend. Пустой bootstrap/startup guard PASS.
Откат не удаляет созданную compiler history; SQL downgrade после нескольких
generations запрещён. [TLF release script](deploy-tlf.sh) проверяет backup,
rehearsal, все product rows до/после остановленных writers, credentials digest,
health/25 public checks, старый frontend и NATS PID. ВМШ — штатный webhook.

## Production

Подготовлен backend release; результаты rollout будут добавлены после cutover.
Учебные материалы агент не загружает и не публикует в production.
