# Этап 10. Администрирование данных, bulk workflows и отказ от Google

## Результат

Admin из Staff импортирует Excel, создаёт/правит пользователей и task settings, показывает отчёт об ошибочных строках и полностью заменяет workflow листов «Задачи»/«Старые». Остальные Google/external scripts продолжают работать до отдельного полного cutover своего процесса.

## Объём Staff

- Users: search/filter, create/edit любого поля кроме `id`, block/archive, group, allowed groups, online mode, family account/link, credential/token reset workflow. Hard delete отсутствует.
- Groups/season: active/default/system flags, display/order, score weight, self-switch policy, fourth/future levels.
- Teacher permissions by group/capability.
- Batch Excel import: обязательны surname, name, unique token/password, birthday, grade. Valid rows применяются, invalid rows пропускаются и попадают в итоговый report; повторный import связывается по token.
- Task metadata TSV grid and version conflicts, включая answer config/checker trusted-admin surface.
- Импорт очных/устных результатов из `a19`, печатные spreadsheet flows и email откладываются на последующие версии.
- Surveys не переносятся. Email workflow относится ко второй/третьей версии. Export пользователей в первой версии не нужен.
- Staff statistics/audit of writes and imports. Teacher continues to have no broadcasts/classrooms/audit.

## Migration and compatibility

Logical migration: `pwa_normalized_groups_imports` plus only measured indexes/read models.

Potential tables:

- `data_imports(id, public_id, kind, source_asset_id, state, mapping_json, diagnostics_json, created_by, created_at, applied_at, version)`;
- `data_import_rows(id, import_id, row_number, natural_key, input_json, normalized_json, state, error_codes_json, applied_object_type/id)`;
- normalized group membership/allowed group table only after choosing source of truth;
- audit events from phase model.

Never delete `allowed_groups`, legacy settings or Google path in the same deploy that first introduces new UI. Первой заменяется загрузка task settings из листов «Задачи» и «Старые» файла `_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx`. Используется expand → dual-read/write/report → cutover → cleanup.

## Google replacement matrix

Для каждого current Google loader/import:

1. Owner and invocation path.
2. Sheet columns/types/validation/defaults.
3. Domain table/readers/writers affected.
4. Staff screen or file import replacement.
5. Golden input and expected DB diff.
6. Parallel-run report on protected production SQLite copy; DB/WAL/SHM хранятся и запускаются только в изолированном локальном окружении.
7. Cutover flag and rollback command.
8. Date after which credential/import is removed from startup/deploy.

Reference doc: `vmshpwa/docs/google-migration-roadmap.md`. Первая replacement matrix подробно покрывает листы «Задачи»/«Старые» и вызывающие их скрипты; `a01`, `a11`, `a18`, `a19`, `a23`, `a52–a54` остаются в общей инвентаризации без обещания перенести их в v1.

## Security

- `cor_ans_checker` editor admin-only, clear trusted-code warning, full revision/audit/diff and optional stored examples. Сохраняется нынешняя trusted-admin `exec` модель; отсутствие examples не блокирует урок, а недонастроенные ответы получают pending и последующую admin-перепроверку.
- Bulk import никогда не принимает type/role/permission silently по неизвестному value.
- Uploads имеют явные ограничения размера/типа; TSV paste интерпретирует ячейки как данные и не исполняет spreadsheet formulas.
- Historic migration 0038/other embedded credentials are audited and removed/rotated by separate security procedure; docs/fixtures never reproduce them.
- PII exports require explicit action and are absent from Sentry/normal logs.

## Tests

- Import parser/normalization per row, duplicate natural keys, partial invalid, encoding and TSV copy/paste as data.
- Valid-row apply is repeatable/idempotent; invalid rows do not block valid ones and получают понятный report.
- Permissions matrix all routes/mutations; audit before/after without secrets.
- Differential reports vs current Google/external pipeline on the protected production-size copy.
- 1500 students metadata/users grid virtualization and search performance.
- Storybook dense Staff pages desktop + mobile essential review; import diagnostics/conflicts/forbidden.
- Playwright upload → preview → apply → use changed student/group in Student; Google/Telegram network blocked.

## Критерии приёмки

- Листы «Задачи» и «Старые» имеют полный Staff/UI/import replacement, named owner и подтверждённый cutover; остальные Google workflows остаются явно перечисленными legacy paths.
- App factory/deploy не загружает Google settings for PWA; legacy bot path can remain explicitly enabled.
- Dry-run diff объясняет каждое создаваемое/изменяемое/пропущенное значение.
- Валидные строки импортируются, невалидные пропускаются и перечисляются в отчёте; пропущенная строка не оставляет частично записанных данных.
- Permission changes вступают в силу и отзывают доступ/session according policy.
- Cutover обратим и имеет parity report; при rollover автоматически переносятся только teachers, остальные данные импортируются заново.

## Пруфы завершения этапа

- [ ] Revision/migrations/backfills: `<sha/paths/results>`.
- [ ] Google replacement matrix with every current loader: `<path>`.
- [ ] Protected production-copy parallel-run/parity reports: `<paths/results>`.
- [ ] Demo users/groups/family/permissions/import/dry-run/apply: `<routes/evidence>`.
- [ ] Import security/idempotency/transaction tests: `<result>`.
- [ ] 1500-row performance + SQL plans: `<path/result>`.
- [ ] Storybook dense admin states/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright 3 browsers, Google/Telegram network blocked: `<result>`.
- [ ] Cutover/rollback/security credential runbook and acceptance: `<paths/issues/name/date>`.
